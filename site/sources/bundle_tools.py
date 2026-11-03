"""把 FFmpeg、FFprobe 及其依赖的动态库打包到一起，并改成相对路径。

用法：bundle_tools.py <目标目录>
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

#: 允许打包的动态库来源；其他路径视为不受控的外部依赖。
ALLOWED_PREFIXES = ("/opt/homebrew/", "/usr/local/")

#: 系统自带、可以留在原处的动态库。
SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")


def dependencies(path):
    """列出二进制依赖的动态库路径。"""
    output = subprocess.check_output(["otool", "-L", str(path)], text=True)
    return [line.strip().split(" (")[0] for line in output.splitlines()[1:] if line.startswith("\t")]


def allowed_prefixes():
    """本机允许打包的动态库前缀，含自行编译的 FFmpeg 前缀。"""
    prefixes = ALLOWED_PREFIXES
    private_prefix = os.environ.get("AUDIOTAG_TOOLS_PREFIX")
    if private_prefix:
        prefixes += (str(Path(private_prefix).resolve()) + "/",)
    return prefixes


def collect_graph(roots):
    """顺着依赖关系收集所有需要一起打包的动态库。"""
    prefixes = allowed_prefixes()
    graph = {}
    pending = [path.resolve() for path in roots.values()]
    while pending:
        path = pending.pop()
        if path in graph:
            continue
        deps = dependencies(path)
        graph[path] = deps
        for dependency in deps:
            if dependency.startswith(prefixes):
                resolved = Path(dependency).resolve()
                if resolved != path:
                    pending.append(resolved)
            elif dependency.startswith("@"):
                raise RuntimeError(f"尚未解析的动态库路径：{dependency}，请检查 FFmpeg 构建方式")
            elif not dependency.startswith(SYSTEM_PREFIXES):
                raise RuntimeError(f"未允许的外部动态库：{dependency}")
    return graph


def copy_libraries(graph, destination, roots):
    """把动态库复制到目标目录，返回源路径到目标路径的映射。"""
    library_directory = destination / "lib"
    library_directory.mkdir(exist_ok=True)
    root_paths = {path.resolve(): name for name, path in roots.items()}
    copied = {}
    names = {}
    for source in graph:
        target = destination / root_paths[source] if source in root_paths else library_directory / source.name
        if target in names and names[target] != source:
            raise RuntimeError(f"动态库名字冲突：{target.name}")
        names[target] = source
        if target.exists():
            target.chmod(target.stat().st_mode | 0o200)
        shutil.copy2(source, target)
        target.chmod(target.stat().st_mode | 0o200)
        copied[source] = target
    return copied, root_paths


def rewrite_library_paths(graph, copied, root_paths):
    """把动态库路径改成包内的相对路径，并重新签名。"""
    for source, target in copied.items():
        for dependency in graph[source]:
            resolved = Path(dependency).resolve()
            if resolved in copied and resolved != source:
                # 动态库随工具打包并改为相对路径，避免依赖 Homebrew 的版本目录。
                relative = os.path.relpath(copied[resolved], target.parent)
                subprocess.run(["install_name_tool", "-change", dependency, "@loader_path/" + relative, str(target)], check=True, capture_output=True)
        if source not in root_paths:
            subprocess.run(["install_name_tool", "-id", "@loader_path/" + target.name, str(target)], check=True, capture_output=True)
        subprocess.run(["codesign", "--force", "--sign", "-", str(target)], check=True, capture_output=True)


def write_build_notices(destination):
    """记录实际使用的 FFmpeg 配置，便于第三方许可追溯。"""
    version = subprocess.check_output([str(destination / "ffmpeg"), "-version"], text=True)
    # FFmpeg 会把编译选项写进版本信息，这里去掉本机的目录路径。
    version = re.sub(r"/(?:Users|opt|private|home)/\S+/(include|lib)\b", r"<local-path>/\1", version)
    version = re.sub(r"/(?:Users|opt|private|home)/\S+", "<local-path>", version)
    (destination / "BUILD-NOTICES.txt").write_text("本地打包的 FFmpeg 与动态库，保留原软件许可要求。构建信息：\n" + version, encoding="utf-8")


def main():
    destination = Path(sys.argv[1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    roots = {name: Path(shutil.which(name) or "") for name in ("ffmpeg", "ffprobe")}
    if any(not path.is_file() for path in roots.values()):
        raise RuntimeError("请先安装 FFmpeg：brew install ffmpeg")
    graph = collect_graph(roots)
    copied, root_paths = copy_libraries(graph, destination, roots)
    rewrite_library_paths(graph, copied, root_paths)
    write_build_notices(destination)
    print(f"已打包 FFmpeg、FFprobe 与 {len(copied) - 2} 个动态库")


if __name__ == "__main__":
    main()
