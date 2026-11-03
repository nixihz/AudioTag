"""供 AI 调用的 JSON 接口。

标准输出只有一行 JSON：成功为 {"ok": true, "result": …}，
失败为 {"ok": false, "error": {"code": …, "message": …}}。
退出码 0 表示成功，1 表示操作失败，2 表示参数错误。
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys
import tempfile

from . import ENGINE_PROTOCOL_VERSION
from .fields import validate_patch
from .fsutil import publish_atomically
from .media import executable, extract_mp3, first_frame, probe_media
from .parser import parse_text
from .tags import inspect_audio, patch_file

#: 支持的操作名，顺序与 capabilities 的输出一致。
OPERATIONS = ("capabilities", "parse", "inspect", "probe", "frame", "patch", "extract")

#: 支持的音频与视频容器。
FORMATS = ("mp3", "flac", "m4a", "mp4", "ogg", "opus", "wav")

#: 单条 JSON 请求的大小上限。
MAX_REQUEST_BYTES = 2_000_000


class JSONArgumentParser(argparse.ArgumentParser):
    """参数错误时也输出 JSON，保持标准输出格式统一。"""

    def error(self, message):
        print(json.dumps({"ok": False, "error": {"code": "invalid_arguments", "message": message}}, ensure_ascii=False))
        self.exit(2)


def capabilities() -> dict:
    """列出可用操作、格式与本机的媒体工具位置。"""
    dependencies = {}
    for name in ("ffmpeg", "ffprobe"):
        try:
            dependencies[name] = executable(name)
        except ValueError:
            dependencies[name] = None
    return {
        "version": ENGINE_PROTOCOL_VERSION,
        "operations": list(OPERATIONS),
        "formats": list(FORMATS),
        "dependencies": dependencies,
    }


def export_frame(source: str, request: dict) -> dict:
    """导出视频首帧；不指定 output 时返回 data URI。"""
    output = request.get("output")
    if not output:
        with tempfile.TemporaryDirectory() as temporary:
            frame = first_frame(source, Path(temporary) / "frame.jpg")
            encoded = base64.b64encode(frame.read_bytes()).decode()
            return {"cover": "data:image/jpeg;base64," + encoded}
    target = Path(output).expanduser().resolve()
    if target.exists():
        raise ValueError("首帧输出文件已存在")
    if target.suffix.lower() != ".jpg":
        raise ValueError("首帧输出应为 .jpg 文件")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        frame = first_frame(source, Path(temporary) / "frame.jpg")
        publish_atomically(frame, target)
    return {"output": str(target)}


def write_output(operation: str, source: str, request: dict) -> dict:
    """执行 patch 或 extract，返回写入结果与解析提示。"""
    output = request.get("output")
    if not isinstance(output, str) or not output:
        raise ValueError("请提供 output 文件路径")
    metadata = validate_patch(request.get("metadata", {}))
    warnings: list[str] = []
    if request.get("text"):
        parsed = parse_text(request["text"])
        metadata = {**parsed["metadata"], **metadata}
        warnings = parsed["warnings"]
    cover = Path(request["cover"]).expanduser().read_bytes() if request.get("cover") else None
    if operation == "extract":
        result = extract_mp3(
            source,
            output,
            metadata,
            cover,
            request.get("first_frame", True),
            request.get("bitrate", 320),
            request.get("audio_stream"),
        )
    else:
        result = {"output": str(Path(output).expanduser().resolve()), **patch_file(source, output, metadata, cover)}
    return {**result, "warnings": warnings}


def perform(request: dict) -> dict:
    """执行一条请求并返回结果字段。"""
    operation = request.get("operation")
    if operation == "capabilities":
        return capabilities()
    if operation == "parse":
        return parse_text(request.get("text", ""))
    source = request.get("input")
    if not isinstance(source, str) or not source:
        raise ValueError("请提供 input 文件路径")
    if operation == "inspect":
        return inspect_audio(source, include_cover=request.get("include_cover", False))
    if operation == "probe":
        return probe_media(source)
    if operation == "frame":
        return export_frame(source, request)
    if operation not in ("patch", "extract"):
        raise ValueError("不支持的 operation")
    return write_output(operation, source, request)


def build_parser() -> JSONArgumentParser:
    """构造命令行解析器。"""
    parser = JSONArgumentParser(description="AudioTag AI 接口：标准输出为 JSON，操作失败退出码 1，参数错误退出码 2")
    parser.add_argument("operation", choices=["request", *OPERATIONS])
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output")
    parser.add_argument("--text", help="信息文本文件，UTF-8")
    parser.add_argument("--metadata", help="标签 JSON 文件")
    parser.add_argument("--cover")
    parser.add_argument("--no-first-frame", action="store_true")
    parser.add_argument("--bitrate", type=int, default=320)
    parser.add_argument("--audio-stream", type=int)
    parser.add_argument("--include-cover", action="store_true")
    return parser


def read_request(args) -> dict:
    """把命令行参数或标准输入整理成一条请求。"""
    if args.operation == "request":
        raw = sys.stdin.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("请求内容过大")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("请求必须是 JSON 对象")
        return request
    request = {
        "operation": args.operation,
        "input": args.input,
        "output": args.output,
        "cover": args.cover,
        "first_frame": not args.no_first_frame,
        "bitrate": args.bitrate,
        "audio_stream": args.audio_stream,
        "include_cover": args.include_cover,
    }
    if args.text:
        request["text"] = Path(args.text).read_text(encoding="utf-8")
    if args.metadata:
        request["metadata"] = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    if args.operation == "parse":
        request["text"] = Path(args.input).read_text(encoding="utf-8")
    return request


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = perform(read_request(args))
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "operation_failed", "message": str(exc)}}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
