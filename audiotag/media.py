"""FFmpeg 与 FFprobe 的封装，以及视频转 MP3 的完整流程。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .cover import read_cover
from .fields import validate_patch
from .fsutil import publish_atomically
from .tags import inspect_audio, load_audio, patch_file

#: 单次媒体处理的最长等待时间。
TIMEOUT_SECONDS = 1800

#: 允许选择的 MP3 码率（kbps）。
BITRATE_CHOICES = (128, 192, 256, 320)

#: 首帧封面允许的最大边长。
MAX_FRAME_EDGE = 2000

#: 首帧按视频方向解码，等比例缩放到边长上限内。
FRAME_SCALE = f"scale='min({MAX_FRAME_EDGE},iw)':'min({MAX_FRAME_EDGE},ih)':force_original_aspect_ratio=decrease"

#: ffprobe 标签名到标准字段名的对应关系。
PROBE_TAG_FIELDS = {
    "title": "title",
    "artist": "artist",
    "album": "album",
    "genre": "genre",
    "date": "year",
    "year": "year",
    "track": "track",
    "bpm": "bpm",
    "lyrics": "lyrics",
}


def executable(name: str) -> str:
    """定位 FFmpeg 工具，优先使用内置副本，其次是系统安装。"""
    override = os.environ.get("AUDIOTAG_" + name.upper())
    candidates = [override] if override else []
    candidates += [
        str(Path(sys.executable).parent / "tools" / name),
        shutil.which(name),
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
    ]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError(f"未找到 {name}，请安装 FFmpeg（brew install ffmpeg）")


def run_media(name: str, args: list[str]) -> bytes:
    """执行一个媒体工具并返回标准输出，失败时抛出 ValueError。"""
    try:
        result = subprocess.run(
            [executable(name), *args],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("媒体处理超过 30 分钟，操作已停止") from exc
    if result.returncode:
        raise ValueError("媒体处理失败：" + result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.stdout


def probe_media(source) -> dict:
    """读取媒体的音视频流与标签信息。"""
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ValueError("输入文件不存在")
    data = json.loads(run_media("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = data.get("streams", [])
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    video = [stream for stream in streams if stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic")]
    if not audio:
        raise ValueError("文件没有音轨，无法导出 MP3")
    audio_streams = [
        {"index": stream["index"], "codec": stream.get("codec_name", ""), "channels": stream.get("channels", 0)}
        for stream in audio
    ]
    video_streams = [
        {"index": stream["index"], "codec": stream.get("codec_name", ""), "width": stream.get("width", 0), "height": stream.get("height", 0)}
        for stream in video
    ]
    return {
        "path": str(path),
        "duration": float(data.get("format", {}).get("duration") or 0),
        "audio_streams": audio_streams,
        "video_streams": video_streams,
        "metadata": _probe_metadata(data, audio[0]),
    }


def _probe_metadata(data: dict, audio_stream: dict) -> dict[str, str]:
    """从 ffprobe 的容器与音轨标签里提取标准字段，非法取值直接忽略。"""
    tags = {key.lower(): value for key, value in data.get("format", {}).get("tags", {}).items()}
    tags.update({key.lower(): value for key, value in audio_stream.get("tags", {}).items()})
    metadata: dict[str, str] = {}
    for source_key, field in PROBE_TAG_FIELDS.items():
        if source_key not in tags:
            continue
        try:
            metadata.update(validate_patch({field: tags[source_key]}))
        except ValueError:
            continue
    return metadata


def first_frame(source, destination) -> Path:
    """截取视频的第一个解码画面并保存为 JPEG。"""
    info = probe_media(source)
    if not info["video_streams"]:
        raise ValueError("文件没有视频画面，无法提取首帧")
    path = Path(destination)
    # 不使用时间偏移，确保截取的是解码得到的第一个视频帧。
    run_media(
        "ffmpeg",
        [
            "-nostdin", "-v", "error", "-n",
            "-i", info["path"],
            "-map", f"0:{info['video_streams'][0]['index']}",
            "-frames:v", "1",
            "-vf", FRAME_SCALE,
            "-q:v", "2",
            "-update", "1",
            str(path),
        ],
    )
    read_cover(path.read_bytes())
    return path


def extract_mp3(
    source,
    destination,
    metadata: dict | None = None,
    cover_bytes: bytes | None = None,
    use_first_frame: bool = True,
    bitrate: int = 320,
    audio_stream: int | None = None,
) -> dict:
    """把源文件转成 MP3，并按需写入标签与封面。"""
    custom_cover = bool(cover_bytes)
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if destination.suffix.lower() != ".mp3":
        raise ValueError("输出路径必须以 .mp3 结尾")
    if destination.exists():
        raise ValueError(f"输出文件已存在：{destination}")
    if bitrate not in BITRATE_CHOICES:
        raise ValueError("码率应为 128、192、256 或 320 kbps")
    info = probe_media(source)
    index = info["audio_streams"][0]["index"] if audio_stream is None else audio_stream
    if index not in [stream["index"] for stream in info["audio_streams"]]:
        raise ValueError("指定的音轨不存在，请使用 probe 查看流编号")
    patch = {**info["metadata"], **validate_patch(metadata or {})}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".audiotag-extract-", dir=destination.parent) as temporary:
        workspace = Path(temporary)
        if cover_bytes:
            read_cover(cover_bytes)
        elif use_first_frame:
            cover_bytes = first_frame(source, workspace / "first-frame.jpg").read_bytes()
        encoded = workspace / "audio.mp3"
        run_media(
            "ffmpeg",
            [
                "-nostdin", "-v", "error", "-n",
                "-i", str(source),
                "-map", f"0:{index}",
                "-vn", "-map_metadata", "-1",
                "-c:a", "libmp3lame",
                "-b:a", f"{bitrate}k",
                "-ac", "2",
                str(encoded),
            ],
        )
        if patch or cover_bytes:
            result = patch_file(encoded, destination, patch, cover_bytes)
        else:
            result = inspect_audio(encoded)
            publish_atomically(encoded, destination)
        load_audio(destination)
    return {
        "output": str(destination),
        "audio_stream": index,
        "bitrate_kbps": bitrate,
        "cover_source": "custom" if custom_cover else "first_frame" if use_first_frame else "none",
        **result,
    }
