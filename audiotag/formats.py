"""按容器区分的标签读写适配器。

MP3/WAV 使用 ID3 文本帧，MP4 使用 iTunes atom，
FLAC/OGG/Opus 使用 Vorbis 标签。三者的差异集中在各自的适配器里，
调用方只面向同一组接口。
"""

from __future__ import annotations

import base64

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, TALB, TBPM, TCON, TDRC, TIT2, TPE1, TRCK, USLT
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.wave import WAVE

from .cover import Cover

#: ID3 封面类型 3 表示“前封面”。
FRONT_COVER = 3

ID3_FIELDS = {"title": TIT2, "artist": TPE1, "album": TALB, "genre": TCON, "year": TDRC, "track": TRCK, "bpm": TBPM}
MP4_FIELDS = {"title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb", "genre": "\xa9gen", "year": "\xa9day", "lyrics": "\xa9lyr", "track": "trkn", "bpm": "tmpo"}
VORBIS_FIELDS = {"title": "title", "artist": "artist", "album": "album", "genre": "genre", "year": "date", "track": "tracknumber", "bpm": "bpm", "lyrics": "lyrics"}


class FormatAdapter:
    """一类音频容器的标签读写方式。"""

    def read(self, audio) -> dict[str, str]:
        """读出全部可识别的标签字段。"""
        raise NotImplementedError

    def write(self, audio, patch: dict[str, str], cover: Cover | None) -> None:
        """把补丁和封面写入音频对象并保存。"""
        raise NotImplementedError

    def cover(self, audio) -> bytes | None:
        """读出前封面的原始字节。"""
        raise NotImplementedError


class ID3Adapter(FormatAdapter):
    """MP3 与 WAV 共用的 ID3 标签。"""

    def read(self, audio) -> dict[str, str]:
        tags = audio.tags or {}
        metadata = {}
        for key, frame_type in ID3_FIELDS.items():
            frame = tags.get(frame_type.__name__)
            if frame and frame.text:
                metadata[key] = str(frame.text[0])
        lyrics = tags.getall("USLT") if audio.tags else []
        if lyrics:
            metadata["lyrics"] = lyrics[0].text
        return metadata

    def write(self, audio, patch: dict[str, str], cover: Cover | None) -> None:
        tags = audio.tags
        for key, frame_type in ID3_FIELDS.items():
            if key in patch:
                tags.setall(frame_type.__name__, [frame_type(encoding=3, text=[patch[key]])])
        if "lyrics" in patch:
            tags.setall("USLT", [USLT(encoding=3, lang="eng", desc="", text=patch["lyrics"])])
        if cover:
            remaining = [picture for picture in tags.getall("APIC") if picture.type != FRONT_COVER]
            tags.setall("APIC", remaining + [self._front_cover(cover, remaining)])
        audio.save(v2_version=3 if tags.version[1] == 3 else 4)

    def cover(self, audio) -> bytes | None:
        pictures = audio.tags.getall("APIC") if audio.tags else []
        if not pictures:
            return None
        front = next((picture for picture in pictures if picture.type == FRONT_COVER), pictures[0])
        return front.data

    @staticmethod
    def _front_cover(cover: Cover, existing: list) -> APIC:
        # 同名描述的封面不允许重复，必要时追加空格区分。
        description = "Front cover"
        while any(picture.desc == description for picture in existing):
            description += " "
        return APIC(encoding=3, mime=cover.mime, type=FRONT_COVER, desc=description, data=cover.data)


class MP4Adapter(FormatAdapter):
    """M4A/MP4 的 iTunes atom。"""

    def read(self, audio) -> dict[str, str]:
        tags = audio.tags or {}
        metadata = {}
        for key, atom in MP4_FIELDS.items():
            values = tags.get(atom)
            if not values:
                continue
            if key == "track":
                number, total = values[0]
                metadata[key] = str(number) + (f"/{total}" if total else "")
            else:
                metadata[key] = str(values[0])
        return metadata

    def write(self, audio, patch: dict[str, str], cover: Cover | None) -> None:
        self._check_limits(patch)
        tags = audio.tags
        for key, value in patch.items():
            if key == "track":
                parts = [int(number) for number in value.split("/")]
                tags["trkn"] = [(parts[0], parts[1] if len(parts) > 1 else 0)]
            elif key == "bpm":
                tags["tmpo"] = [int(float(value))]
            else:
                tags[MP4_FIELDS[key]] = [value]
        if cover:
            image_format = MP4Cover.FORMAT_PNG if cover.mime == "image/png" else MP4Cover.FORMAT_JPEG
            tags["covr"] = [MP4Cover(cover.data, imageformat=image_format)]
        audio.save()

    def cover(self, audio) -> bytes | None:
        covers = (audio.tags or {}).get("covr", [])
        return bytes(covers[0]) if covers else None

    @staticmethod
    def _check_limits(patch: dict[str, str]) -> None:
        if "bpm" in patch and not float(patch["bpm"]).is_integer():
            raise ValueError("M4A 的 BPM 标签仅支持整数，请调整 BPM")
        if "track" in patch and any(int(number) > 65535 for number in patch["track"].split("/")):
            raise ValueError("M4A 的音轨编号不能超过 65535")


class VorbisAdapter(FormatAdapter):
    """FLAC 与 Ogg 共用的 Vorbis 文本标签，封面存放方式由子类决定。"""

    def read(self, audio) -> dict[str, str]:
        tags = audio.tags or {}
        metadata = {}
        for key, tag in VORBIS_FIELDS.items():
            values = tags.get(tag)
            if values:
                metadata[key] = str(values[0])
        total = tags.get("tracktotal") or tags.get("totaltracks")
        if total and "track" in metadata and "/" not in metadata["track"]:
            metadata["track"] += "/" + str(total[0])
        return metadata

    def write(self, audio, patch: dict[str, str], cover: Cover | None) -> None:
        tags = audio.tags
        for key, value in patch.items():
            if key == "track":
                self._write_track(tags, value)
            else:
                tags[VORBIS_FIELDS[key]] = [value]
        if cover:
            self.write_cover(audio, cover)
        audio.save()

    def write_cover(self, audio, cover: Cover) -> None:
        raise NotImplementedError

    @staticmethod
    def _write_track(tags, value: str) -> None:
        parts = value.split("/")
        tags["tracknumber"] = [parts[0]]
        # 显式修改音轨时清掉旧总数，避免出现 1/1 和 1/12 两套矛盾值。
        for total_key in ("tracktotal", "totaltracks"):
            if total_key in tags:
                del tags[total_key]
        if len(parts) > 1:
            tags["tracktotal"] = [parts[1]]


class FlacAdapter(VorbisAdapter):
    """FLAC 的图片块。"""

    def write_cover(self, audio, cover: Cover) -> None:
        picture = build_picture(cover)
        remaining = [old for old in audio.pictures if old.type != FRONT_COVER]
        audio.clear_pictures()
        for old in remaining:
            audio.add_picture(old)
        audio.add_picture(picture)

    def cover(self, audio) -> bytes | None:
        if not audio.pictures:
            return None
        front = next((picture for picture in audio.pictures if picture.type == FRONT_COVER), audio.pictures[0])
        return front.data


class OggAdapter(VorbisAdapter):
    """Ogg Vorbis 与 Opus 的 metadata_block_picture。"""

    def write_cover(self, audio, cover: Cover) -> None:
        picture = build_picture(cover)
        tags = audio.tags
        remaining = []
        for item in tags.get("metadata_block_picture", []):
            try:
                if Picture(base64.b64decode(item)).type != FRONT_COVER:
                    remaining.append(item)
            except (ValueError, mutagen.MutagenError):
                remaining.append(item)
        tags["metadata_block_picture"] = remaining + [base64.b64encode(picture.write()).decode()]

    def cover(self, audio) -> bytes | None:
        for item in (audio.tags or {}).get("metadata_block_picture", []):
            try:
                picture = Picture(base64.b64decode(item))
            except (ValueError, mutagen.MutagenError):
                continue
            if picture.type == FRONT_COVER:
                return picture.data
        return None


def build_picture(cover: Cover) -> Picture:
    """按 Vorbis 约定把封面转成图片块。"""
    picture = Picture()
    picture.type, picture.mime, picture.desc = FRONT_COVER, cover.mime, "Front cover"
    picture.width, picture.height, picture.depth = cover.width, cover.height, 24
    picture.data = cover.data
    return picture


def adapter_for(audio) -> FormatAdapter:
    """按音频对象的类型选择对应的标签适配器。"""
    if isinstance(audio, (MP3, WAVE)):
        return ID3Adapter()
    if isinstance(audio, MP4):
        return MP4Adapter()
    if isinstance(audio, FLAC):
        return FlacAdapter()
    return OggAdapter()
