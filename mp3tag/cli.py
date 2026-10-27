import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import webbrowser

from .parser import parse_text, validate_patch
from .tags import inspect_audio, patch_file


def main():
    parser = argparse.ArgumentParser(description="AudioTag 本地音频标签编辑工具")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="打开本地网页")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true")
    inspect = commands.add_parser("inspect", help="读取音频标签")
    inspect.add_argument("file", type=Path)
    parse = commands.add_parser("parse", help="解析信息文本")
    parse.add_argument("text", type=Path)
    patch = commands.add_parser("patch", help="写入标签或封面")
    patch.add_argument("files", nargs="+", type=Path)
    source = patch.add_mutually_exclusive_group()
    source.add_argument("--text", type=Path, help="中英标签信息文本")
    source.add_argument("--json", type=Path, help="标签 JSON")
    patch.add_argument("--cover", type=Path, help="JPEG/PNG 封面")
    output = patch.add_mutually_exclusive_group()
    output.add_argument("--output-dir", type=Path, default=None)
    output.add_argument("--in-place", action="store_true", help="先备份再原地修改")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn
            if not args.no_browser:
                import threading
                threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
            uvicorn.run("mp3tag.server:app", host="127.0.0.1", port=args.port)
        elif args.command == "inspect":
            print(json.dumps(inspect_audio(args.file), ensure_ascii=False, indent=2))
        elif args.command == "parse":
            print(json.dumps(parse_text(args.text.read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
        else:
            data = {}
            if args.text:
                parsed = parse_text(args.text.read_text(encoding="utf-8"))
                data = parsed["metadata"]
                for warning in parsed["warnings"]:
                    print("提示：" + warning, file=sys.stderr)
            elif args.json:
                data = validate_patch(json.loads(args.json.read_text(encoding="utf-8")))
            cover = args.cover.read_bytes() if args.cover else None
            if not data and not cover:
                raise ValueError("请提供 --text、--json 或 --cover")
            for source in args.files:
                source = source.resolve()
                if args.in_place:
                    backup = source.with_name(source.name + ".bak")
                    if backup.exists():
                        raise ValueError(f"备份已存在，为避免覆盖，请先移走：{backup}")
                    with tempfile.TemporaryDirectory(dir=source.parent, prefix=".mp3tag-") as temp:
                        target = Path(temp) / source.name
                        patch_file(source, target, data, cover)
                        with backup.open("xb") as stream, source.open("rb") as original:
                            shutil.copyfileobj(original, stream)
                        shutil.copystat(source, backup)
                        os.replace(target, source)
                    print(f"已写入：{source}（备份：{backup}）")
                else:
                    directory = args.output_dir or source.parent
                    target = directory / f"{source.stem}.tagged{source.suffix}"
                    patch_file(source, target, data, cover)
                    print(f"已导出：{target}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
