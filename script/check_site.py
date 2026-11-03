"""检查静态官网与发行包的一致性。

默认要求所有发行文件就位；--draft 只列出缺失项，便于发布前预览。
"""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import tarfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent.parent
site = root / "site"
config = json.loads((root / "Config/Release.json").read_text())
SPARKLE_NAMESPACE = {"sparkle": "http://www.andymatuschak.org/xml-namespaces/sparkle"}
ENGINE_SOURCE = f"sources/audiotag-engine-{config['version']}-{config['build']}.tar.gz"
REQUIRED_FILES = {"release.json", "updates/appcast.xml", "downloads/SHA256SUMS.txt", ENGINE_SOURCE}


class Links(HTMLParser):
    """收集页面里的链接与锚点 id。"""

    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        for key in ("src", "href"):
            if attributes.get(key):
                self.links.append(attributes[key])


def collect_documents() -> dict:
    """解析网站里的每个 HTML 页面。"""
    documents = {}
    for document in site.rglob("*.html"):
        links = Links()
        links.feed(document.read_text())
        documents[document] = links
    return documents


def check_links(documents: dict, draft: bool) -> tuple[list[str], list[str]]:
    """检查站内链接指向的文件与锚点是否存在。"""
    errors, pending = [], []
    for document, links in documents.items():
        for value in links.links:
            url = urlsplit(value)
            if url.scheme or url.netloc:
                continue
            target = (document.parent / unquote(url.path)).resolve() if url.path else document
            if not target.is_relative_to(site):
                errors.append(f"链接越出网站目录：{document.relative_to(site)} → {value}")
                continue
            if target.is_dir():
                target /= "index.html"
            relative = str(target.relative_to(site))
            if not target.is_file():
                (pending if draft and relative in REQUIRED_FILES else errors).append(f"缺少链接目标：{relative}")
            elif url.fragment and target in documents and url.fragment not in documents[target].ids:
                errors.append(f"缺少页面锚点：{value}")
    return errors, pending


def check_release_manifest(errors: list[str], pending: list[str]) -> None:
    """核对版本数据、安装包摘要与 appcast 条目。"""
    manifest = site / "release.json"
    feed = site / "updates/appcast.xml"
    if not manifest.exists() or not feed.exists():
        return
    release = json.loads(manifest.read_text())
    archive = (site / release["download"]).resolve()
    if not archive.is_relative_to(site / "downloads"):
        errors.append("发行包不在 downloads 内")
    elif not archive.is_file():
        errors.append("版本数据引用的安装包不存在")
    else:
        if release["version"] != config["version"] or release["build"] != config["build"]:
            errors.append("网页版本与客户端配置不一致")
        if release["bytes"] != archive.stat().st_size or release["sha256"] != hashlib.sha256(archive.read_bytes()).hexdigest():
            errors.append("网页安装包大小或 SHA-256 不匹配")
        if release.get("notarized") is not True:
            errors.append("公开发行必须先通过 Apple 公证")
        check_appcast(errors, release, archive, feed)


def check_appcast(errors: list[str], release: dict, archive: Path, feed: Path) -> None:
    """核对 appcast 中当前构建的下载地址、字节数与签名。"""
    items = ET.parse(feed).findall("./channel/item")
    item = next((item for item in items if item.findtext("sparkle:version", namespaces=SPARKLE_NAMESPACE) == config["build"]), None)
    if item is None:
        errors.append("appcast 缺少当前构建")
        return
    enclosure = item.find("enclosure")
    base = config["feedURL"].removesuffix("updates/appcast.xml")
    if enclosure is None or enclosure.get("url") != base + release["download"] or enclosure.get("length") != str(archive.stat().st_size):
        errors.append("appcast 下载地址或字节数不匹配")
        return
    signature = enclosure.get("{" + SPARKLE_NAMESPACE["sparkle"] + "}edSignature", "")
    result = subprocess.run(["swift", str(root / "script/verify_update.swift"), str(archive),
                             signature, config["publicEDKey"]], capture_output=True, text=True)
    if result.returncode:
        errors.append("appcast 更新包签名不匹配：" + result.stderr.strip())


def check_engine_source(errors: list[str], source: Path) -> None:
    """核对公开发布的引擎源码包是否完整。

    期望的文件清单直接取自仓库里的 Python 包，
    这样拆分或新增模块后不会漏发。
    """
    if not source.exists():
        return
    with tarfile.open(source) as archive:
        names = archive.getnames()
    expected = ["COPYING", "BUILDING.md"] + sorted(path.name for path in (root / "audiotag").glob("*.py"))
    for name in expected:
        if not any(item.endswith("/" + name) for item in names):
            errors.append(f"对应引擎源码不完整：{name}")


def main():
    parser = argparse.ArgumentParser(description="检查静态官网与发行包的一致性")
    parser.add_argument("--draft", action="store_true", help="只检查已有内容，列出但不放行缺失的发行文件")
    args = parser.parse_args()
    errors: list[str] = []
    pending: list[str] = []
    link_errors, link_pending = check_links(collect_documents(), args.draft)
    errors += link_errors
    pending += link_pending
    for filename in REQUIRED_FILES:
        if not (site / filename).is_file():
            pending.append(f"缺少发行文件：{filename}")

    check_release_manifest(errors, pending)
    check_engine_source(errors, site / ENGINE_SOURCE)
    source = site / ENGINE_SOURCE
    if source.exists() and ENGINE_SOURCE.removeprefix("sources/") not in (site / "sources/index.html").read_text():
        errors.append("源码页没有当前引擎源码下载链接")

    for message in sorted(set(errors)):
        print("错误：" + message)
    for message in sorted(set(pending)):
        print("待完成：" + message)
    if errors or (pending and not args.draft):
        raise SystemExit(1)
    print("草稿已有内容检查通过，仍不可发布" if pending else "官网与发行一致性检查通过")


if __name__ == "__main__":
    main()
