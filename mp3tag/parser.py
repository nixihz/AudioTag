import re

FIELDS = ("title", "artist", "album", "genre", "year", "track", "bpm", "lyrics")
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


def canonical(label):
    label = label.strip().lower()
    candidates = [label, re.sub(r"[（(].*?[）)]", "", label).strip()]
    candidates += re.findall(r"[（(](.*?)[）)]", label)
    for key, aliases in ALIASES.items():
        if any(candidate.strip().lower() in aliases for candidate in candidates):
            return key
    return None


def validate_patch(data):
    if not isinstance(data, dict):
        raise ValueError("标签必须是 JSON 对象")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValueError("不支持的字段：" + ", ".join(sorted(unknown)))
    result = {}
    for key, value in data.items():
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError(f"{key} 必须是文字或数字")
        value = str(value).strip()
        if not value:
            continue
        if len(value) > (200_000 if key == "lyrics" else 4096):
            raise ValueError(f"{key} 内容过长")
        if key == "year" and not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
            raise ValueError("年份格式应为 2024 或 2024-01-01")
        if key == "track":
            match = re.fullmatch(r"(\d+)\s*(?:/\s*(\d+))?", value)
            if not match or int(match[1]) < 1 or (match[2] and int(match[2]) < int(match[1])):
                raise ValueError("音轨格式应为 1 或 1/12，编号不能超过总数")
            value = str(int(match[1])) + ("/" + str(int(match[2])) if match[2] else "")
        if key == "bpm":
            if not re.fullmatch(r"\d+(?:\.\d+)?", value) or not 0 < float(value) <= 999:
                raise ValueError("BPM 应为大于 0、最多 999 的数字")
        result[key] = value
    return result


def parse_text(text):
    if len(text) > 250_000:
        raise ValueError("粘贴内容过长")
    result, warnings, lyrics = {}, [], None
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        # 歌词里的冒号可能是正文，因此歌词开始后不再解析标签。
        if lyrics is not None:
            lyrics.append(line)
            continue
        match = re.match(r"^\s*(?:[-*]\s*)?(.*?)\s*[:：]\s*(.*)$", line)
        key = canonical(match[1]) if match else None
        if key:
            if key in result:
                warnings.append(f"{key} 出现多次，使用最后一次的值")
            value = match[2].strip()
            if key == "lyrics":
                lyrics = [value] if value else []
            else:
                if key == "artist":
                    cleaned = re.sub(r"[（(]或根据你的喜好自定义[）)]", "", value).strip()
                    if cleaned != value:
                        warnings.append("已去除艺术家字段中的可选说明，请检查歌手名称")
                    value = cleaned
                result[key] = value
        elif line.strip():
            warnings.append("未识别的行：" + line[:100])
    if lyrics is not None:
        result["lyrics"] = "\n".join(lyrics).strip()
    result = validate_patch(result)
    if not result:
        raise ValueError("没有识别到标签，请使用 Title：歌名 或 歌曲名称 (Title)：歌名")
    return {"metadata": result, "warnings": warnings}
