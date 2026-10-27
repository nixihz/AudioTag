import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
binary = Path(sys.argv[1])
app = Path(sys.argv[2])
identity = sys.argv[3]
config = json.loads((root / "Config/Release.json").read_text())
contents = app / "Contents"
for directory in ["MacOS", "Resources", "Frameworks"]:
    (contents / directory).mkdir(parents=True, exist_ok=True)
shutil.copy2(binary, contents / "MacOS/AudioTag")
engine = contents / "Resources/audiotag"
legacy_engine = contents / "Resources/mp3tag"
if legacy_engine.is_file() or legacy_engine.is_symlink():
    legacy_engine.unlink()
shutil.copy2(Path(os.environ.get("ENGINE_BINARY", str(root / "dist/audiotag"))), engine)
shutil.copy2(root / "examples/beneath-the-metal-sky.txt", contents / "Resources/example.txt")
subprocess.run(["ditto", os.environ.get("TOOLS_BUNDLE", str(root / "dist/tools")), str(contents / "Resources/tools")], check=True)
framework = root / ".build/artifacts/sparkle/Sparkle/Sparkle.xcframework/macos-arm64_x86_64/Sparkle.framework"
subprocess.run(["ditto", str(framework), str(contents / "Frameworks/Sparkle.framework")], check=True)
licenses = root / "Config/Licenses"
if licenses.exists():
    subprocess.run(["ditto", str(licenses), str(contents / "Resources/Licenses")], check=True)
icon = root / "assets/Mp3tag.icns"
if icon.exists():
    shutil.copy2(icon, contents / "Resources/AudioTag.icns")
info = {
    "CFBundleExecutable": "AudioTag", "CFBundleIdentifier": "com.brian.mp3tag",
    "CFBundleName": "AudioTag", "CFBundleDisplayName": "AudioTag", "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": config["version"], "CFBundleVersion": config["build"],
    "LSMinimumSystemVersion": config["minimumSystemVersion"], "NSPrincipalClass": "NSApplication",
    "CFBundleIconFile": "AudioTag.icns", "NSHighResolutionCapable": True,
    "SUFeedURL": config["feedURL"], "SUPublicEDKey": config["publicEDKey"],
    "SUVerifyUpdateBeforeExtraction": True,
    "SUEnableAutomaticChecks": True, "SUAutomaticallyUpdate": False
}
(contents / "Info.plist").write_bytes(plistlib.dumps(info))

def sign(path):
    command = ["codesign", "--force", "--sign", identity, "--preserve-metadata=entitlements"]
    if identity != "-":
        command += ["--options", "runtime", "--timestamp"]
    subprocess.run(command + [str(path)], check=True, capture_output=True)

# 嵌套代码由内向外签名；保留 Sparkle 辅助进程自带的权限。
files = [p for p in contents.rglob("*") if p.is_file() and not p.is_symlink()]
for path in sorted(files, key=lambda p: len(p.parts), reverse=True):
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic in [b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"]:
        sign(path)
for path in sorted(contents.rglob("*"), key=lambda p: len(p.parts), reverse=True):
    if path.is_dir() and not path.is_symlink() and path.suffix in [".xpc", ".app", ".framework"]:
        sign(path)
sign(app)
subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
print(f"已生成 {app}，版本 {config['version']}（{config['build']}）")
