"""面向人的命令行入口：本地网页、读取标签、解析文本、写入标签。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import webbrowser

from .fields import validate_patch
from .parser import parse_text
from .tags import inspect_audio, patch_file

#: 原地修改时备份文件的后缀。
BACKUP_SUFFIX = ".bak"


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
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
    return parser


def run_serve(args):
    """启动本地网页服务，并按需打开浏览器。"""
    import uvicorn

    if not args.no_browser:
        import threading

        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    uvicorn.run("audiotag.server:app", host="127.0.0.1", port=args.port)


def run_inspect(args):
    """打印音频的标签信息。"""
    print(json.dumps(inspect_audio(args.file), ensure_ascii=False, indent=2))


def run_parse(args):
    """打印文本解析出的标签与提示。"""
    print(json.dumps(parse_text(args.text.read_text(encoding="utf-8")), ensure_ascii=False, indent=2))


def load_patch(args) -> dict:
    """读取 --text 或 --json 提供的标签补丁。"""
    if args.text:
        parsed = parse_text(args.text.read_text(encoding="utf-8"))
        for warning in parsed["warnings"]:
            print("提示：" + warning, file=sys.stderr)
        return parsed["metadata"]
    if args.json:
        return validate_patch(json.loads(args.json.read_text(encoding="utf-8")))
    return {}


def patch_in_place(source: Path, patch: dict, cover: bytes | None):
    """先生成并校验新文件，备份原文件后再原子替换。"""
    backup = source.with_name(source.name + BACKUP_SUFFIX)
    if backup.exists():
        raise ValueError(f"备份已存在，为避免覆盖，请先移走：{backup}")
    with tempfile.TemporaryDirectory(dir=source.parent, prefix=".audiotag-") as temporary:
        target = Path(temporary) / source.name
        patch_file(source, target, patch, cover)
        with backup.open("xb") as stream, source.open("rb") as original:
            shutil.copyfileobj(original, stream)
        shutil.copystat(source, backup)
        os.replace(target, source)
    print(f"已写入：{source}（备份：{backup}）")


def run_patch(args):
    """把同一份补丁写入一个或多个音频文件。"""
    patch = load_patch(args)
    cover = args.cover.read_bytes() if args.cover else None
    if not patch and not cover:
        raise ValueError("请提供 --text、--json 或 --cover")
    for path in args.files:
        source = path.resolve()
        if args.in_place:
            patch_in_place(source, patch, cover)
            continue
        directory = args.output_dir or source.parent
        target = directory / f"{source.stem}.tagged{source.suffix}"
        patch_file(source, target, patch, cover)
        print(f"已导出：{target}")


#: 各子命令对应的处理函数。
COMMANDS = {
    "serve": run_serve,
    "inspect": run_inspect,
    "parse": run_parse,
    "patch": run_patch,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        COMMANDS[args.command](args)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
