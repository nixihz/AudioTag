"""把可执行文件、标签引擎、媒体工具与框架组装成 AudioTag.app。

用法：stage_app.py <可执行文件> <应用包路径> <签名身份>
"""

import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent.parent

#: 应用包内的框架与工具位置。
SPARKLE_FRAMEWORK = ".build/artifacts/sparkle/Sparkle/Sparkle.xcframework/macos-arm64_x86_64/Sparkle.framework"
EXAMPLE_SOURCE = "examples/beneath-the-metal-sky.txt"


def stage_contents(binary: Path, app: Path) -> Path:
    """拷贝应用需要的所有资源，返回 Contents 目录。"""
    contents = app / "Contents"
    for directory in ["MacOS", "Resources", "Frameworks"]:
        (contents / directory).mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, contents / "MacOS/AudioTag")
    engine = contents / "Resources/audiotag"
    shutil.copy2(Path(os.environ.get("ENGINE_BINARY", str(root / "dist/audiotag"))), engine)
    shutil.copy2(root / EXAMPLE_SOURCE, contents / "Resources/example.txt")
    subprocess.run(["ditto", os.environ.get("TOOLS_BUNDLE", str(root / "dist/tools")), str(contents / "Resources/tools")], check=True)
    subprocess.run(["ditto", str(root / SPARKLE_FRAMEWORK), str(contents / "Frameworks/Sparkle.framework")], check=True)
    licenses = root / "Config/Licenses"
    if licenses.exists():
        subprocess.run(["ditto", str(licenses), str(contents / "Resources/Licenses")], check=True)
    if (root / "LICENSE").is_file():
        shutil.copy2(root / "LICENSE", contents / "Resources/LICENSE")
    icon = root / "assets/AudioTag.icns"
    if icon.exists():
        shutil.copy2(icon, contents / "Resources/AudioTag.icns")
    return contents


def write_info_plist(contents: Path) -> None:
    """写出应用信息，版本与更新配置来自 Config/Release.json。"""
    config = json.loads((root / "Config/Release.json").read_text())
    info = {
        "CFBundleExecutable": "AudioTag", "CFBundleIdentifier": "com.brian.audiotag",
        "CFBundleName": "AudioTag", "CFBundleDisplayName": "AudioTag", "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": config["version"], "CFBundleVersion": config["build"],
        "LSMinimumSystemVersion": config["minimumSystemVersion"], "NSPrincipalClass": "NSApplication",
        "CFBundleIconFile": "AudioTag.icns", "NSHighResolutionCapable": True,
        "SUFeedURL": config["feedURL"], "SUPublicEDKey": config["publicEDKey"],
        "SUVerifyUpdateBeforeExtraction": True,
        "SUEnableAutomaticChecks": True, "SUAutomaticallyUpdate": False
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))


def sign(path: Path, identity: str) -> None:
    """按给定身份签名，ad-hoc 签名不带运行时与时间戳。"""
    command = ["codesign", "--force", "--sign", identity, "--preserve-metadata=entitlements"]
    if identity != "-":
        command += ["--options", "runtime", "--timestamp"]
    subprocess.run(command + [str(path)], check=True, capture_output=True)


def sign_bundle(app: Path, identity: str) -> None:
    """嵌套代码由内向外签名，最后校验整个应用包。"""
    contents = app / "Contents"
    files = [path for path in contents.rglob("*") if path.is_file() and not path.is_symlink()]
    for path in sorted(files, key=lambda item: len(item.parts), reverse=True):
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic in [b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"]:
            sign(path, identity)
    for path in sorted(contents.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink() and path.suffix in [".xpc", ".app", ".framework"]:
            sign(path, identity)
    sign(app, identity)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)


def main():
    binary, app, identity = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    config = json.loads((root / "Config/Release.json").read_text())
    contents = stage_contents(binary, app)
    write_info_plist(contents)
    sign_bundle(app, identity)
    print(f"已生成 {app}，版本 {config['version']}（{config['build']}）")


if __name__ == "__main__":
    main()
