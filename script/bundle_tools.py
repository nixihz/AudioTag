import os
from pathlib import Path
import shutil
import subprocess
import sys


def dependencies(path):
    output = subprocess.check_output(["otool", "-L", str(path)], text=True)
    return [line.strip().split(" (")[0] for line in output.splitlines()[1:] if line.startswith("\t")]


def main():
    destination = Path(sys.argv[1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    library_directory = destination / "lib"
    library_directory.mkdir(exist_ok=True)
    roots = {name: Path(shutil.which(name) or "") for name in ("ffmpeg", "ffprobe")}
    if any(not path.is_file() for path in roots.values()):
        raise RuntimeError("请先安装 FFmpeg：brew install ffmpeg")
    graph = {}
    private_prefix = os.environ.get("MP3TAG_TOOLS_PREFIX")
    allowed_prefixes = ("/opt/homebrew/", "/usr/local/")
    if private_prefix:
        allowed_prefixes += (str(Path(private_prefix).resolve()) + "/",)
    pending = [path.resolve() for path in roots.values()]
    while pending:
        path = pending.pop()
        if path in graph:
            continue
        deps = dependencies(path)
        graph[path] = deps
        for dependency in deps:
            if dependency.startswith(allowed_prefixes):
                resolved = Path(dependency).resolve()
                if resolved != path:
                    pending.append(resolved)
            elif dependency.startswith("@"):
                raise RuntimeError(f"尚未解析的动态库路径：{dependency}，请检查 FFmpeg 构建方式")
            elif not dependency.startswith(("/usr/lib/", "/System/Library/")):
                raise RuntimeError(f"未允许的外部动态库：{dependency}")
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
    version = subprocess.check_output([str(destination / "ffmpeg"), "-version"], text=True)
    (destination / "BUILD-NOTICES.txt").write_text("本地打包的 FFmpeg 与动态库，保留原软件许可要求。构建信息：\n" + version, encoding="utf-8")
    print(f"已打包 FFmpeg、FFprobe 与 {len(copied) - 2} 个动态库")


if __name__ == "__main__":
    main()
