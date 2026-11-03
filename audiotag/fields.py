"""标签字段的定义、别名与校验规则。

字段元数据集中在本模块，文本解析、补丁校验和写入三处共用同一份定义，
避免同一个字段在不同位置出现不同的取值规则。
"""

from __future__ import annotations

import re

#: 支持写入的标准字段，顺序与网页、命令行展示一致。
FIELDS = ("title", "artist", "album", "genre", "year", "track", "bpm", "lyrics")

#: 文本里可识别的字段别名，键为标准字段名，值为可接受的写法。
ALIASES = {
    "title": ("title", "歌曲名称", "歌名", "标题", "曲名"),
    "artist": ("artist", "艺术家", "歌手", "艺术家/歌手", "艺术家 / 歌手"),
    "album": ("album", "唱片集", "专辑", "唱片集/专辑", "唱片集 / 专辑"),
    "genre": ("genre", "流派", "风格"),
    "year": ("year", "年份", "发行年份", "date", "日期"),
    "track": ("track", "track no.", "track no", "track number", "tracknumber", "音轨编号", "曲目编号", "音轨"),
    "bpm": ("bpm", "节拍", "速度"),
    "lyrics": ("lyrics", "歌词"),
}

MAX_TEXT_LENGTH = 4096
MAX_LYRICS_LENGTH = 200_000

YEAR_PATTERN = re.compile(r"\d{4}(?:-\d{2}(?:-\d{2})?)?")
TRACK_PATTERN = re.compile(r"(\d+)\s*(?:/\s*(\d+))?")
BPM_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def _keep(value: str) -> str:
    return value


def _validate_year(value: str) -> str:
    if not YEAR_PATTERN.fullmatch(value):
        raise ValueError("年份格式应为 2024 或 2024-01-01")
    return value


def _validate_track(value: str) -> str:
    match = TRACK_PATTERN.fullmatch(value)
    if not match or int(match[1]) < 1 or (match[2] and int(match[2]) < int(match[1])):
        raise ValueError("音轨格式应为 1 或 1/12，编号不能超过总数")
    number = int(match[1])
    total = match[2]
    return f"{number}" + (f"/{int(total)}" if total else "")


def _validate_bpm(value: str) -> str:
    if not BPM_PATTERN.fullmatch(value) or not 0 < float(value) <= 999:
        raise ValueError("BPM 应为大于 0、最多 999 的数字")
    return value


#: 逐字段的规范化与校验，缺省的字段只做去空白处理。
VALIDATORS = {
    "year": _validate_year,
    "track": _validate_track,
    "bpm": _validate_bpm,
}


def validate_patch(data) -> dict[str, str]:
    """校验并规范化一份标签补丁。

    只保留受支持的字段；空值视为“不修改”，直接丢弃。
    任何不合法的取值都抛出 ValueError，由调用方转成用户可读的错误。
    """
    if not isinstance(data, dict):
        raise ValueError("标签必须是 JSON 对象")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValueError("不支持的字段：" + ", ".join(sorted(unknown)))
    result: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError(f"{key} 必须是文字或数字")
        text = str(value).strip()
        if not text:
            continue
        limit = MAX_LYRICS_LENGTH if key == "lyrics" else MAX_TEXT_LENGTH
        if len(text) > limit:
            raise ValueError(f"{key} 内容过长")
        result[key] = VALIDATORS.get(key, _keep)(text)
    return result
