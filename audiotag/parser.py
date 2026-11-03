"""把粘贴的中英文歌曲信息解析成标签补丁。"""

from __future__ import annotations

import re

from .fields import ALIASES, FIELDS, validate_patch

MAX_INPUT_LENGTH = 250_000

#: 形如 “歌曲名称 (Title)：歌名” 或 “Title: 歌名” 的行。
LABELLED_LINE = re.compile(r"^\s*(?:[-*]\s*)?(.*?)\s*[:：]\s*(.*)$")

#: 艺术家字段里可选的补充说明，解析时去掉。
OPTIONAL_ARTIST_NOTE = re.compile(r"[（(]或根据你的喜好自定义[）)]")

__all__ = ["ALIASES", "FIELDS", "canonical", "parse_text", "validate_patch"]


def canonical(label: str) -> str | None:
    """把一行左侧的标签名归一化成标准字段名，无法识别时返回 None。"""
    label = label.strip().lower()
    candidates = [label, re.sub(r"[（(].*?[）)]", "", label).strip()]
    candidates += re.findall(r"[（(].*?[）)]", label)
    for key, aliases in ALIASES.items():
        if any(candidate.strip().lower() in aliases for candidate in candidates):
            return key
    return None


def parse_text(text: str) -> dict:
    """解析整段文本，返回 {"metadata": 标签, "warnings": 提示}。

    歌词以 “Lyrics:” 开头，其后的所有行都视为歌词正文，
    因此正文里的冒号不会被误判成新的标签。
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError("粘贴内容过长")
    metadata: dict[str, str] = {}
    warnings: list[str] = []
    lyrics: list[str] | None = None
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if lyrics is not None:
            lyrics.append(line)
            continue
        match = LABELLED_LINE.match(line)
        key = canonical(match[1]) if match else None
        if not key:
            if line.strip():
                warnings.append("未识别的行：" + line[:100])
            continue
        if key in metadata:
            warnings.append(f"{key} 出现多次，使用最后一次的值")
        value = match[2].strip()
        if key == "lyrics":
            lyrics = [value] if value else []
            continue
        if key == "artist":
            cleaned = OPTIONAL_ARTIST_NOTE.sub("", value).strip()
            if cleaned != value:
                warnings.append("已去除艺术家字段中的可选说明，请检查歌手名称")
            value = cleaned
        metadata[key] = value
    if lyrics is not None:
        metadata["lyrics"] = "\n".join(lyrics).strip()
    metadata = validate_patch(metadata)
    if not metadata:
        raise ValueError("没有识别到标签，请使用 Title：歌名 或 歌曲名称 (Title)：歌名")
    return {"metadata": metadata, "warnings": warnings}
