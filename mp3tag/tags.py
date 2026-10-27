import base64
import io
import os
from pathlib import Path
import shutil
import tempfile

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, TALB, TBPM, TCON, TDRC, TIT2, TPE1, TRCK, USLT
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE
from PIL import Image, UnidentifiedImageError

from .parser import validate_patch

EXTENSIONS = {".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus", ".wav"}
ID3_KEYS = {"title": TIT2, "artist": TPE1, "album": TALB, "genre": TCON, "year": TDRC, "track": TRCK, "bpm": TBPM}
MP4_KEYS = {"title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb", "genre": "\xa9gen", "year": "\xa9day", "lyrics": "\xa9lyr", "track": "trkn", "bpm": "tmpo"}
VORBIS_KEYS = {"title": "title", "artist": "artist", "album": "album", "genre": "genre", "year": "date", "track": "tracknumber", "bpm": "bpm", "lyrics": "lyrics"}


def load_audio(path):
    if Path(path).suffix.lower() not in EXTENSIONS:
        raise ValueError("不支持的文件类型")
    try:
        audio = mutagen.File(path)
    except (mutagen.MutagenError, OSError) as exc:
        raise ValueError("无法读取音频，文件可能损坏") from exc
    if not isinstance(audio, (MP3, WAVE, MP4, FLAC, OggVorbis, OggOpus)):
        raise ValueError("文件内容不是支持的音频格式")
    return audio


def read_cover(data):
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("封面不能超过 20 MB")
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ("JPEG", "PNG"):
                raise ValueError("封面仅支持 JPEG 或 PNG")
            if im.width * im.height > 40_000_000:
                raise ValueError("封面分辨率过大")
            mime = "image/jpeg" if im.format == "JPEG" else "image/png"
            width, height = im.size
            im.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("无法读取封面图片") from exc
    return {"data": data, "mime": mime, "width": width, "height": height}


def get_cover(audio):
    if isinstance(audio, (MP3, WAVE)):
        pictures = audio.tags.getall("APIC") if audio.tags else []
        picture = next((p for p in pictures if p.type == 3), pictures[0] if pictures else None)
        return picture.data if picture else None
    if isinstance(audio, MP4):
        covers = (audio.tags or {}).get("covr", [])
        return bytes(covers[0]) if covers else None
    if isinstance(audio, FLAC):
        picture = next((p for p in audio.pictures if p.type == 3), audio.pictures[0] if audio.pictures else None)
        return picture.data if picture else None
    for item in (audio.tags or {}).get("metadata_block_picture", []):
        try:
            picture = Picture(base64.b64decode(item))
            if picture.type == 3:
                return picture.data
        except (ValueError, mutagen.MutagenError):
            continue
    return None


def inspect_audio(path, include_cover=False):
    audio = load_audio(path)
    tags, metadata = audio.tags or {}, {}
    if isinstance(audio, (MP3, WAVE)):
        for key, cls in ID3_KEYS.items():
            frame = tags.get(cls.__name__)
            if frame and frame.text:
                metadata[key] = str(frame.text[0])
        frames = audio.tags.getall("USLT") if audio.tags else []
        if frames:
            metadata["lyrics"] = frames[0].text
    elif isinstance(audio, MP4):
        for key, tag in MP4_KEYS.items():
            values = tags.get(tag)
            if values:
                if key == "track":
                    number, total = values[0]
                    metadata[key] = str(number) + (f"/{total}" if total else "")
                else:
                    metadata[key] = str(values[0])
    else:
        for key, tag in VORBIS_KEYS.items():
            values = tags.get(tag)
            if values:
                metadata[key] = str(values[0])
        total = tags.get("tracktotal") or tags.get("totaltracks")
        if total and "track" in metadata and "/" not in metadata["track"]:
            metadata["track"] += "/" + str(total[0])
    result = {"metadata": metadata, "format": type(audio).__name__, "duration": round(audio.info.length, 2), "has_cover": bool(get_cover(audio))}
    if include_cover:
        cover = get_cover(audio)
        if cover and len(cover) <= 20 * 1024 * 1024:
            try:
                im = read_cover(cover)
                result["cover"] = f"data:{im['mime']};base64," + base64.b64encode(cover).decode()
            except ValueError:
                pass
    return result


def write_tags(path, patch, cover=None):
    audio = load_audio(path)
    if isinstance(audio, MP4) and "bpm" in patch and not float(patch["bpm"]).is_integer():
        raise ValueError("M4A 的 BPM 标签仅支持整数，请调整 BPM")
    if isinstance(audio, MP4) and "track" in patch and any(int(n) > 65535 for n in patch["track"].split("/")):
        raise ValueError("M4A 的音轨编号不能超过 65535")
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    if isinstance(audio, (MP3, WAVE)):
        for key, cls in ID3_KEYS.items():
            if key in patch:
                tags.setall(cls.__name__, [cls(encoding=3, text=[patch[key]])])
        if "lyrics" in patch:
            tags.setall("USLT", [USLT(encoding=3, lang="eng", desc="", text=patch["lyrics"])])
        if cover:
            remaining = [p for p in tags.getall("APIC") if p.type != 3]
            description = "Front cover"
            while any(p.desc == description for p in remaining):
                description += " "
            tags.setall("APIC", remaining + [APIC(encoding=3, mime=cover["mime"], type=3, desc=description, data=cover["data"])])
        audio.save(v2_version=3 if tags.version[1] == 3 else 4)
    elif isinstance(audio, MP4):
        for key, value in patch.items():
            if key == "track":
                parts = [int(n) for n in value.split("/")]
                tags["trkn"] = [(parts[0], parts[1] if len(parts) > 1 else 0)]
            elif key == "bpm":
                tags["tmpo"] = [int(float(value))]
            else:
                tags[MP4_KEYS[key]] = [value]
        if cover:
            tags["covr"] = [MP4Cover(cover["data"], imageformat=MP4Cover.FORMAT_PNG if cover["mime"] == "image/png" else MP4Cover.FORMAT_JPEG)]
        audio.save()
    else:
        for key, value in patch.items():
            if key == "track":
                parts = value.split("/")
                tags["tracknumber"] = [parts[0]]
                # 显式修改音轨时清掉旧总数，避免出现 1/1 和 1/12 两套矛盾值。
                for total_key in ("tracktotal", "totaltracks"):
                    if total_key in tags:
                        del tags[total_key]
                if len(parts) > 1:
                    tags["tracktotal"] = [parts[1]]
            else:
                tags[VORBIS_KEYS[key]] = [value]
        if cover:
            picture = Picture()
            picture.type, picture.mime, picture.desc = 3, cover["mime"], "Front cover"
            picture.width, picture.height, picture.depth = cover["width"], cover["height"], 24
            picture.data = cover["data"]
            if isinstance(audio, FLAC):
                remaining = [p for p in audio.pictures if p.type != 3]
                audio.clear_pictures()
                for old in remaining:
                    audio.add_picture(old)
                audio.add_picture(picture)
            else:
                remaining = []
                for item in tags.get("metadata_block_picture", []):
                    try:
                        if Picture(base64.b64decode(item)).type != 3:
                            remaining.append(item)
                    except (ValueError, mutagen.MutagenError):
                        remaining.append(item)
                tags["metadata_block_picture"] = remaining + [base64.b64encode(picture.write()).decode()]
        audio.save()


def patch_file(source, destination, patch, cover_bytes=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
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
    fd, temp = tempfile.mkstemp(suffix=source.suffix, dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temp)
        write_tags(temp, patch, cover)
        result = inspect_audio(temp)
        for key, value in patch.items():
            actual = result["metadata"].get(key)
            if actual != value and not (key == "bpm" and actual and float(actual) == float(value)):
                raise ValueError(f"写入后的 {key} 校验失败")
        if cover and get_cover(load_audio(temp)) != cover["data"]:
            raise ValueError("封面写入校验失败")
        # 硬链接以排他方式发布成品，避免覆盖同时创建的文件。
        os.link(temp, destination)
        return result
    except mutagen.MutagenError as exc:
        raise ValueError("标签写入失败，原文件未修改") from exc
    finally:
        Path(temp).unlink(missing_ok=True)
