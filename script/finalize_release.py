import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlsplit

root = Path(__file__).resolve().parent.parent
app = Path(sys.argv[1]).resolve()
config = json.loads((root / "Config/Release.json").read_text())
info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
expected = {
    "CFBundleShortVersionString": config["version"],
    "CFBundleVersion": config["build"],
    "SUFeedURL": config["feedURL"],
    "SUPublicEDKey": config["publicEDKey"],
    "LSMinimumSystemVersion": config["minimumSystemVersion"],
}
for key, value in expected.items():
    if info.get(key) != value:
        raise SystemExit(f"发行配置与应用不一致：{key}")
subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
subprocess.run(["xcrun", "stapler", "validate", str(app)], check=True)
subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose=2", str(app)], check=True)

feed = urlsplit(config["feedURL"])
if feed.scheme != "https" or feed.path != "/updates/appcast.xml" or feed.query or feed.fragment:
    raise SystemExit("此发行脚本要求官网根目录下的 HTTPS 更新源")
base = f"https://{feed.netloc}/"
downloads = root / "site/downloads"
updates = root / "site/updates"
downloads.mkdir(parents=True, exist_ok=True)
updates.mkdir(parents=True, exist_ok=True)
name = f"audiotag-{config['version']}-{config['build']}"
archive = downloads / f"{name}.zip"
notes = downloads / f"{name}.html"
if archive.exists() or notes.exists():
    raise SystemExit("同版本制品已存在；禁止覆盖，请使用新构建号")
shutil.copy2(root / "Config/ReleaseNotes.html", notes)
subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
tools = root / ".build/artifacts/sparkle/Sparkle/bin"
subprocess.run([
    str(tools / "generate_appcast"), "--account", "mp3tag",
    "--download-url-prefix", base + "downloads/",
    "--release-notes-url-prefix", base + "downloads/",
    "--link", base, "--maximum-deltas", "0", "--maximum-versions", "0",
    "-o", str(updates / "appcast.xml"), str(downloads)
], check=True)
signature = subprocess.check_output([str(tools / "sign_update"), "--account", "mp3tag", "-p", str(archive)], text=True).strip()
subprocess.run([str(tools / "sign_update"), "--account", "mp3tag", "--verify", str(archive), signature], check=True)
release = {
    "version": config["version"], "build": config["build"],
    "date": datetime.now().astimezone().date().isoformat(),
    "minimumSystemVersion": config["minimumSystemVersion"], "architecture": "Apple Silicon",
    "download": f"downloads/{archive.name}", "notes": f"downloads/{notes.name}",
    "bytes": archive.stat().st_size, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "notarized": True,
    "summary": "陶土红原生工作台；标签、歌词与封面批量整理，MP4 转 MP3，以及带签名校验的 Sparkle 在线更新。"
}
(root / "site/release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n")
checksums = [
    f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}"
    for file in sorted(downloads.iterdir()) if file.suffix in [".zip", ".dmg", ".html"]
]
(downloads / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n")
print(json.dumps(release, ensure_ascii=False, indent=2))
