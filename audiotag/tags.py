"""音频标签读写的门面。

对外只暴露少量函数：格式差异交给 formats.py，图片校验交给 cover.py，
成品的发布方式交给 fsutil.py。
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import shutil
import tempfile

import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from .cover import MAX_COVER_BYTES, Cover, read_cover
from .fields import validate_patch
from .formats import adapter_for
from .fsutil import publish_atomically

EXTENSIONS = {".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus", ".wav"}

SUPPORTED_AUDIO = (MP3, WAVE, MP4, FLAC, OggVorbis, OggOpus)

__all__ = [
    "EXTENSIONS",
    "Cover",
    "get_cover",
    "inspect_audio",
    "load_audio",
    "patch_file",
    "read_cover",
    "write_tags",
]


def load_audio(path):
    """读取音频对象，类型或内容不受支持时抛出 ValueError。"""
    if Path(path).suffix.lower() not in EXTENSIONS:
        raise ValueError("不支持的文件类型")
    try:
        audio = mutagen.File(path)
    except (mutagen.MutagenError, OSError) as exc:
        raise ValueError("无法读取音频，文件可能损坏") from exc
    if not isinstance(audio, SUPPORTED_AUDIO):
        raise ValueError("文件内容不是支持的音频格式")
    return audio


def get_cover(audio) -> bytes | None:
    """读出前封面的原始字节，没有封面时返回 None。"""
    return adapter_for(audio).cover(audio)


def inspect_audio(path, include_cover: bool = False) -> dict:
    """读出音频的标签、格式、时长与封面情况。"""
    audio = load_audio(path)
    metadata = adapter_for(audio).read(audio)
    cover = get_cover(audio)
    result = {
        "metadata": metadata,
        "format": type(audio).__name__,
        "duration": round(audio.info.length, 2),
        "has_cover": bool(cover),
    }
    if include_cover and cover and len(cover) <= MAX_COVER_BYTES:
        try:
            image = read_cover(cover)
            result["cover"] = f"data:{image.mime};base64," + base64.b64encode(cover).decode()
        except ValueError:
            pass
    return result


def write_tags(path, patch: dict[str, str], cover: Cover | None = None) -> None:
    """把补丁和封面写入指定音频文件。"""
    audio = load_audio(path)
    if audio.tags is None:
        audio.add_tags()
    adapter_for(audio).write(audio, patch, cover)


def patch_file(source, destination, patch: dict[str, str], cover_bytes: bytes | None = None) -> dict:
    """写入标签并生成副本，返回写入后的标签信息。

    成品先写到临时文件，逐项校验通过后才发布到目标路径，
    因此失败时既不会覆盖已有文件，也不会留下半成品。
    """
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    patch = validate_patch(patch)
    if source == destination:
        raise ValueError("请使用原地修改模式，或指定另一个输出路径")
    if destination.exists():
        raise ValueError(f"输出文件已存在：{destination}")
    if source.suffix.lower() != destination.suffix.lower():
        raise ValueError("输出扩展名必须与原文件相同，标签编辑不会转换格式")
    if not patch and not cover_bytes:
        raise ValueError("请选择至少一个标签或封面")
    cover = read_cover(cover_bytes) if cover_bytes else None
    load_audio(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(suffix=source.suffix, dir=destination.parent)
    os.close(handle)
    try:
        shutil.copy2(source, temporary)
        write_tags(temporary, patch, cover)
        result = inspect_audio(temporary)
        verify_written_tags(result, patch)
        if cover and get_cover(load_audio(temporary)) != cover.data:
            raise ValueError("封面写入校验失败")
        publish_atomically(Path(temporary), destination)
        return result
    except mutagen.MutagenError as exc:
        raise ValueError("标签写入失败，原文件未修改") from exc
    finally:
        Path(temporary).unlink(missing_ok=True)


def verify_written_tags(result: dict, patch: dict[str, str]) -> None:
    """逐项核对写入结果与补丁是否一致。"""
    for key, value in patch.items():
        actual = result["metadata"].get(key)
        if actual != value and not (key == "bpm" and actual and float(actual) == float(value)):
            raise ValueError(f"写入后的 {key} 校验失败")
