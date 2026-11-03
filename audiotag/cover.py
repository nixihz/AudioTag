"""封面图片的读取与校验。"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

MAX_COVER_BYTES = 20 * 1024 * 1024
MAX_COVER_PIXELS = 40_000_000
SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png"}


@dataclass(frozen=True)
class Cover:
    """一张通过校验的前封面。"""

    data: bytes
    mime: str
    width: int
    height: int


def read_cover(data: bytes) -> Cover:
    """校验封面图片并返回其内容与尺寸，不合法时抛出 ValueError。"""
    if len(data) > MAX_COVER_BYTES:
        raise ValueError("封面不能超过 20 MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in SUPPORTED_FORMATS:
                raise ValueError("封面仅支持 JPEG 或 PNG")
            if image.width * image.height > MAX_COVER_PIXELS:
                raise ValueError("封面分辨率过大")
            mime = SUPPORTED_FORMATS[image.format]
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("无法读取封面图片") from exc
    return Cover(data=data, mime=mime, width=width, height=height)
