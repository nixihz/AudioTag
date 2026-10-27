import argparse
import base64
import json
from pathlib import Path
import sys
import tempfile

from .media import executable, extract_mp3, first_frame, probe_media
from .parser import parse_text, validate_patch
from .tags import inspect_audio, patch_file


class JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"ok": False, "error": {"code": "invalid_arguments", "message": message}}, ensure_ascii=False))
        self.exit(2)


def perform(request):
    operation = request.get("operation")
    if operation == "capabilities":
        dependencies = {}
        for name in ("ffmpeg", "ffprobe"):
            try:
                dependencies[name] = executable(name)
            except ValueError:
                dependencies[name] = None
        return {"version": "0.2.0", "operations": ["capabilities", "parse", "inspect", "probe", "frame", "patch", "extract"], "formats": ["mp3", "flac", "m4a", "mp4", "ogg", "opus", "wav"], "dependencies": dependencies}
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
        if request.get("output"):
            target = Path(request["output"]).expanduser().resolve()
            if target.exists():
                raise ValueError("首帧输出文件已存在")
            if target.suffix.lower() != ".jpg":
                raise ValueError("首帧输出应为 .jpg 文件")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target.parent) as temp:
                frame = first_frame(source, Path(temp) / "frame.jpg")
                import os
                os.link(frame, target)
            return {"output": str(target)}
        with tempfile.TemporaryDirectory() as temp:
            frame = first_frame(source, Path(temp) / "frame.jpg")
            return {"cover": "data:image/jpeg;base64," + base64.b64encode(frame.read_bytes()).decode()}
    if operation not in ("patch", "extract"):
        raise ValueError("不支持的 operation")
    output = request.get("output")
    if not isinstance(output, str) or not output:
        raise ValueError("请提供 output 文件路径")
    metadata = validate_patch(request.get("metadata", {}))
    warnings = []
    if request.get("text"):
        parsed = parse_text(request["text"])
        metadata = {**parsed["metadata"], **metadata}
        warnings = parsed["warnings"]
    cover = Path(request["cover"]).expanduser().read_bytes() if request.get("cover") else None
    if operation == "extract":
        result = extract_mp3(source, output, metadata, cover, request.get("first_frame", True), request.get("bitrate", 320), request.get("audio_stream"))
    else:
        result = {"output": str(Path(output).expanduser().resolve()), **patch_file(source, output, metadata, cover)}
    return {**result, "warnings": warnings}


def main():
    parser = JSONArgumentParser(description="AudioTag AI 接口：标准输出为 JSON，操作失败退出码 1，参数错误退出码 2")
    parser.add_argument("operation", choices=["request", "capabilities", "parse", "inspect", "probe", "frame", "patch", "extract"])
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output")
    parser.add_argument("--text", help="信息文本文件，UTF-8")
    parser.add_argument("--metadata", help="标签 JSON 文件")
    parser.add_argument("--cover")
    parser.add_argument("--no-first-frame", action="store_true")
    parser.add_argument("--bitrate", type=int, default=320)
    parser.add_argument("--audio-stream", type=int)
    parser.add_argument("--include-cover", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "request":
            raw = sys.stdin.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("请求内容过大")
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("请求必须是 JSON 对象")
        else:
            request = {"operation": args.operation, "input": args.input, "output": args.output, "cover": args.cover, "first_frame": not args.no_first_frame, "bitrate": args.bitrate, "audio_stream": args.audio_stream, "include_cover": args.include_cover}
            if args.text:
                request["text"] = Path(args.text).read_text(encoding="utf-8")
            if args.metadata:
                request["metadata"] = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
            if args.operation == "parse":
                request["text"] = Path(args.input).read_text(encoding="utf-8")
        result = perform(request)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "operation_failed", "message": str(exc)}}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
