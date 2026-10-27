import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .parser import parse_text, validate_patch
from .tags import EXTENSIONS, inspect_audio, patch_file

app = FastAPI(title="AudioTag 本地标签编辑器", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
MAX_AUDIO = 512 * 1024 * 1024


@app.middleware("http")
async def local_requests(request, call_next):
    if request.method not in ("GET", "HEAD"):
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "仅接受本地网页请求"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def safe_name(name):
    name = Path((name or "audio").replace("\\", "/")).name
    name = re.sub(r'[\x00-\x1f<>:"|?*]', "_", name)
    return name[:180] or "audio"


async def save_upload(upload, destination, limit):
    size = 0
    with open(destination, "wb") as stream:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError(f"文件超过 {limit // 1024 // 1024} MB 限制")
            stream.write(chunk)
    return size


@app.post("/api/parse")
async def parse(payload: dict):
    try:
        text = payload.get("text", "")
        if not isinstance(text, str):
            raise ValueError("信息应为文字")
        return parse_text(text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/inspect")
async def inspect(file: UploadFile = File(...)):
    try:
        with tempfile.TemporaryDirectory(prefix="mp3tag-inspect-") as directory:
            path = Path(directory) / safe_name(file.filename)
            await save_upload(file, path, MAX_AUDIO)
            return await run_in_threadpool(inspect_audio, path, True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await file.close()


@app.post("/api/patch")
async def patch(files: list[UploadFile] = File(...), metadata: str = Form(...), cover: UploadFile | None = File(None)):
    directory = Path(tempfile.mkdtemp(prefix="mp3tag-export-"))
    delivered = False
    try:
        if not 1 <= len(files) <= 32:
            raise ValueError("每批支持 1–32 个音频文件")
        if len(metadata) > 250_000:
            raise ValueError("标签内容过长")
        try:
            data = validate_patch(json.loads(metadata))
        except json.JSONDecodeError as exc:
            raise ValueError("标签 JSON 格式无效") from exc
        cover_bytes = None
        if cover:
            await save_upload(cover, directory / "cover", 20 * 1024 * 1024)
            cover_bytes = (directory / "cover").read_bytes()
        output = directory / "output"
        output.mkdir()
        results, total = [], 0
        for index, upload in enumerate(files):
            name = safe_name(upload.filename)
            if Path(name).suffix.lower() not in EXTENSIONS:
                raise ValueError(f"不支持的音频：{name}")
            source = directory / f"source-{index}{Path(name).suffix}"
            total += await save_upload(upload, source, MAX_AUDIO)
            if total > 2 * 1024**3:
                raise ValueError("每批总大小不能超过 2 GB")
            target = output / f"{Path(name).stem}.tagged{Path(name).suffix}"
            counter = 2
            while target.exists():
                target = output / f"{Path(name).stem}.{counter}.tagged{Path(name).suffix}"
                counter += 1
            await run_in_threadpool(patch_file, source, target, data, cover_bytes)
            results.append(target)
        if len(results) == 1:
            result = results[0]
            media_type = "application/octet-stream"
        else:
            result = directory / "AudioTag-tagged.zip"
            def bundle():
                with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
                    for path in results:
                        archive.write(path, path.name)
            await run_in_threadpool(bundle)
            media_type = "application/zip"
        delivered = True
        return FileResponse(result, filename=result.name, media_type=media_type, background=BackgroundTask(shutil.rmtree, directory))
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        for upload in files:
            await upload.close()
        if cover:
            await cover.close()
        if not delivered:
            shutil.rmtree(directory, ignore_errors=True)


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
