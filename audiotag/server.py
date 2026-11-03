"""本地网页服务。

只绑定 127.0.0.1，并拒绝来自其他网页来源的写入请求。
上传的音频只存在于临时目录，下载完成后随目录一起删除。
"""

from __future__ import annotations

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

from .fields import validate_patch
from .parser import parse_text
from .tags import EXTENSIONS, inspect_audio, patch_file

#: 单个音频文件的大小上限。
MAX_AUDIO = 512 * 1024 * 1024

#: 单个封面的大小上限。
MAX_COVER = 20 * 1024 * 1024

#: 一批最多可处理的文件数。
MAX_BATCH_FILES = 32

#: 一批文件的总大小上限。
MAX_BATCH_TOTAL = 2 * 1024**3

#: 标签 JSON 文本的长度上限。
MAX_METADATA_LENGTH = 250_000

#: 批量导出时使用的压缩包名称。
BATCH_ARCHIVE_NAME = "AudioTag-tagged.zip"

#: 文件名里不允许出现的字符。
UNSAFE_NAME = re.compile(r'[\x00-\x1f<>:"|?*]')

app = FastAPI(title="AudioTag 本地标签编辑器", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])


@app.middleware("http")
async def local_requests(request, call_next):
    """拒绝来自其他来源的写请求，并禁止缓存。"""
    if request.method not in ("GET", "HEAD"):
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "仅接受本地网页请求"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def safe_name(name: str | None) -> str:
    """把上传的文件名整理成安全的本地文件名。"""
    name = Path((name or "audio").replace("\\", "/")).name
    name = UNSAFE_NAME.sub("_", name)
    return name[:180] or "audio"


async def save_upload(upload: UploadFile, destination: Path, limit: int) -> int:
    """分块保存上传内容，超过上限时中止并报错。"""
    size = 0
    with open(destination, "wb") as stream:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError(f"文件超过 {limit // 1024 // 1024} MB 限制")
            stream.write(chunk)
    return size


def unique_target(directory: Path, name: str) -> Path:
    """为导出文件挑一个未被占用的名字。"""
    stem, suffix = Path(name).stem, Path(name).suffix
    target = directory / f"{stem}.tagged{suffix}"
    counter = 2
    while target.exists():
        target = directory / f"{stem}.{counter}.tagged{suffix}"
        counter += 1
    return target


def bundle_zip(target: Path, results: list[Path]) -> None:
    """把多个导出结果打包成一个不压缩的 ZIP。"""
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in results:
            archive.write(path, path.name)


@app.post("/api/parse")
async def parse(payload: dict):
    """解析歌曲信息文本。"""
    try:
        text = payload.get("text", "")
        if not isinstance(text, str):
            raise ValueError("信息应为文字")
        return parse_text(text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/inspect")
async def inspect(file: UploadFile = File(...)):
    """读取上传音频的标签与封面。"""
    try:
        with tempfile.TemporaryDirectory(prefix="audiotag-inspect-") as directory:
            path = Path(directory) / safe_name(file.filename)
            await save_upload(file, path, MAX_AUDIO)
            return await run_in_threadpool(inspect_audio, path, True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await file.close()


@app.post("/api/patch")
async def patch(files: list[UploadFile] = File(...), metadata: str = Form(...), cover: UploadFile | None = File(None)):
    """写入标签与封面，单个文件直接下载，多个文件打包下载。"""
    directory = Path(tempfile.mkdtemp(prefix="audiotag-export-"))
    delivered = False
    try:
        if not 1 <= len(files) <= MAX_BATCH_FILES:
            raise ValueError(f"每批支持 1–{MAX_BATCH_FILES} 个音频文件")
        if len(metadata) > MAX_METADATA_LENGTH:
            raise ValueError("标签内容过长")
        try:
            data = validate_patch(json.loads(metadata))
        except json.JSONDecodeError as exc:
            raise ValueError("标签 JSON 格式无效") from exc
        cover_bytes = None
        if cover:
            await save_upload(cover, directory / "cover", MAX_COVER)
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
            if total > MAX_BATCH_TOTAL:
                raise ValueError("每批总大小不能超过 2 GB")
            target = unique_target(output, name)
            await run_in_threadpool(patch_file, source, target, data, cover_bytes)
            results.append(target)
        if len(results) == 1:
            result = results[0]
            media_type = "application/octet-stream"
        else:
            result = directory / BATCH_ARCHIVE_NAME
            await run_in_threadpool(bundle_zip, result, results)
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
