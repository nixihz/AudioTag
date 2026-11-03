"""生成官网发行文件：安装包、发行说明、appcast 与校验和。

用法：finalize_release.py <已签名并已公证的 AudioTag.app>
"""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlsplit

root = Path(__file__).resolve().parent.parent


def check_configuration(app: Path, config: dict) -> None:
    """确认应用包的版本与更新配置和发行配置一致。"""
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


def check_distribution(app: Path) -> None:
    """校验签名、公证与 Gatekeeper 放行情况。"""
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    subprocess.run(["xcrun", "stapler", "validate", str(app)], check=True)
    subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose=2", str(app)], check=True)


def download_base(config: dict) -> str:
    """给出官网根地址，要求更新源位于官网的固定路径。"""
    feed = urlsplit(config["feedURL"])
    if feed.scheme != "https" or feed.path != "/updates/appcast.xml" or feed.query or feed.fragment:
        raise SystemExit("此发行脚本要求官网根目录下的 HTTPS 更新源")
    return f"https://{feed.netloc}/"


def build_archive(app: Path, downloads: Path, config: dict) -> tuple[Path, Path]:
    """打包应用并复制发行说明，返回安装包与说明文件路径。"""
    name = f"audiotag-{config['version']}-{config['build']}"
    archive = downloads / f"{name}.zip"
    notes = downloads / f"{name}.html"
    if archive.exists() or notes.exists():
        raise SystemExit("同版本制品已存在；禁止覆盖，请使用新构建号")
    shutil.copy2(root / "Config/ReleaseNotes.html", notes)
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
    return archive, notes


def publish_appcast(archive: Path, downloads: Path, updates: Path, base: str) -> None:
    """生成并签名 appcast。"""
    tools = root / ".build/artifacts/sparkle/Sparkle/bin"
    sparkle_account = os.environ.get("SPARKLE_KEY_ACCOUNT")
    if not sparkle_account:
        raise SystemExit("请设置 SPARKLE_KEY_ACCOUNT（Sparkle 私钥所在的钥匙串账户名）")
    subprocess.run([
        str(tools / "generate_appcast"), "--account", sparkle_account,
        "--download-url-prefix", base + "downloads/",
        "--release-notes-url-prefix", base + "downloads/",
        "--link", base, "--maximum-deltas", "0", "--maximum-versions", "0",
        "-o", str(updates / "appcast.xml"), str(downloads)
    ], check=True)
    signature = subprocess.check_output([str(tools / "sign_update"), "--account", sparkle_account, "-p", str(archive)], text=True).strip()
    subprocess.run([str(tools / "sign_update"), "--account", sparkle_account, "--verify", str(archive), signature], check=True)


def write_release_data(archive: Path, notes: Path, config: dict) -> dict:
    """写出官网使用的版本数据与校验和。"""
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
    downloads = archive.parent
    checksums = [
        f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}"
        for file in sorted(downloads.iterdir()) if file.suffix in [".zip", ".dmg", ".html"]
    ]
    (downloads / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n")
    return release


def main():
    app = Path(sys.argv[1]).resolve()
    config = json.loads((root / "Config/Release.json").read_text())
    check_configuration(app, config)
    check_distribution(app)
    base = download_base(config)
    downloads = root / "site/downloads"
    updates = root / "site/updates"
    downloads.mkdir(parents=True, exist_ok=True)
    updates.mkdir(parents=True, exist_ok=True)
    archive, notes = build_archive(app, downloads, config)
    publish_appcast(archive, downloads, updates, base)
    release = write_release_data(archive, notes, config)
    print(json.dumps(release, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
