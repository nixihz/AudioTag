import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .parser import validate_patch
from .tags import inspect_audio, load_audio, patch_file, read_cover


def executable(name):
    override = os.environ.get("MP3TAG_" + name.upper())
    candidates = [override] if override else []
    candidates += [str(Path(sys.executable).parent / "tools" / name), shutil.which(name), f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError(f"未找到 {name}，请安装 FFmpeg（brew install ffmpeg）")


def run_media(name, args):
    try:
        result = subprocess.run([executable(name), *args], capture_output=True, timeout=1800)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("媒体处理超过 30 分钟，操作已停止") from exc
    if result.returncode:
        raise ValueError("媒体处理失败：" + result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.stdout


def probe_media(source):
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ValueError("输入文件不存在")
    data = json.loads(run_media("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = data.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    video = [s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    if not audio:
        raise ValueError("文件没有音轨，无法导出 MP3")
    metadata = {}
    tags = {k.lower(): v for k, v in data.get("format", {}).get("tags", {}).items()}
    tags.update({k.lower(): v for k, v in audio[0].get("tags", {}).items()})
    mapping = {"title": "title", "artist": "artist", "album": "album", "genre": "genre", "date": "year", "year": "year", "track": "track", "bpm": "bpm", "lyrics": "lyrics"}
    for old, new in mapping.items():
        if old in tags:
            try:
                metadata.update(validate_patch({new: tags[old]}))
            except ValueError:
                pass
    return {"path": str(path), "duration": float(data.get("format", {}).get("duration") or 0), "audio_streams": [{"index": s["index"], "codec": s.get("codec_name", ""), "channels": s.get("channels", 0)} for s in audio], "video_streams": [{"index": s["index"], "codec": s.get("codec_name", ""), "width": s.get("width", 0), "height": s.get("height", 0)} for s in video], "metadata": metadata}


def first_frame(source, destination):
    info = probe_media(source)
    if not info["video_streams"]:
        raise ValueError("文件没有视频画面，无法提取首帧")
    path = Path(destination)
    # 不使用时间偏移，确保截取的是解码得到的第一个视频帧。
    run_media("ffmpeg", ["-nostdin", "-v", "error", "-n", "-i", info["path"], "-map", f"0:{info['video_streams'][0]['index']}", "-frames:v", "1", "-vf", "scale='min(2000,iw)':'min(2000,ih)':force_original_aspect_ratio=decrease", "-q:v", "2", "-update", "1", str(path)])
    read_cover(path.read_bytes())
    return path


def extract_mp3(source, destination, metadata=None, cover_bytes=None, use_first_frame=True, bitrate=320, audio_stream=None):
    custom_cover = bool(cover_bytes)
    source, destination = Path(source).expanduser().resolve(), Path(destination).expanduser().resolve()
    if destination.suffix.lower() != ".mp3":
        raise ValueError("输出路径必须以 .mp3 结尾")
    if destination.exists():
        raise ValueError(f"输出文件已存在：{destination}")
    if bitrate not in (128, 192, 256, 320):
        raise ValueError("码率应为 128、192、256 或 320 kbps")
    info = probe_media(source)
    index = info["audio_streams"][0]["index"] if audio_stream is None else audio_stream
    if index not in [s["index"] for s in info["audio_streams"]]:
        raise ValueError("指定的音轨不存在，请使用 probe 查看流编号")
    patch = {**info["metadata"], **validate_patch(metadata or {})}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mp3tag-extract-", dir=destination.parent) as temp:
        temp = Path(temp)
        if cover_bytes:
            read_cover(cover_bytes)
        elif use_first_frame:
            cover_bytes = first_frame(source, temp / "first-frame.jpg").read_bytes()
        encoded = temp / "audio.mp3"
        run_media("ffmpeg", ["-nostdin", "-v", "error", "-n", "-i", str(source), "-map", f"0:{index}", "-vn", "-map_metadata", "-1", "-c:a", "libmp3lame", "-b:a", f"{bitrate}k", "-ac", "2", str(encoded)])
        if patch or cover_bytes:
            result = patch_file(encoded, destination, patch, cover_bytes)
        else:
            result = inspect_audio(encoded)
            os.link(encoded, destination)
        load_audio(destination)
    return {"output": str(destination), "audio_stream": index, "bitrate_kbps": bitrate, "cover_source": "custom" if custom_cover else "first_frame" if use_first_frame else "none", **result}
