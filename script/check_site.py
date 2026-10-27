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
parser = argparse.ArgumentParser(description="检查静态官网与发行包的一致性")
parser.add_argument("--draft", action="store_true", help="只检查已有内容，列出但不放行缺失的发行文件")
args = parser.parse_args()
errors = []
pending = []
name = f"audiotag-{config['version']}-{config['build']}"
engine_source = f"sources/mp3tag-engine-{config['version']}-{config['build']}.tar.gz"
required = {"release.json", "updates/appcast.xml", "downloads/SHA256SUMS.txt", engine_source}


class Links(HTMLParser):
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


documents = {}
for document in site.rglob("*.html"):
    links = Links()
    links.feed(document.read_text())
    documents[document] = links

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
            (pending if args.draft and relative in required else errors).append(f"缺少链接目标：{relative}")
        elif url.fragment and target in documents and url.fragment not in documents[target].ids:
            errors.append(f"缺少页面锚点：{value}")

for filename in required:
    if not (site / filename).is_file():
        pending.append(f"缺少发行文件：{filename}")

manifest = site / "release.json"
feed = site / "updates/appcast.xml"
if manifest.exists() and feed.exists():
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
        namespace = {"sparkle": "http://www.andymatuschak.org/xml-namespaces/sparkle"}
        items = ET.parse(feed).findall("./channel/item")
        item = next((item for item in items if item.findtext("sparkle:version", namespaces=namespace) == config["build"]), None)
        if item is None:
            errors.append("appcast 缺少当前构建")
        else:
            enclosure = item.find("enclosure")
            base = config["feedURL"].removesuffix("updates/appcast.xml")
            if enclosure is None or enclosure.get("url") != base + release["download"] or enclosure.get("length") != str(archive.stat().st_size):
                errors.append("appcast 下载地址或字节数不匹配")
            else:
                signature = enclosure.get("{" + namespace["sparkle"] + "}edSignature", "")
                result = subprocess.run(["swift", str(root / "script/verify_update.swift"), str(archive),
                                         signature, config["publicEDKey"]], capture_output=True, text=True)
                if result.returncode:
                    errors.append("appcast 更新包签名不匹配：" + result.stderr.strip())
    source = site / engine_source
    if source.exists():
        with tarfile.open(source) as archive:
            names = archive.getnames()
        for expected in ["COPYING", "BUILDING.md", "mp3tag/engine.py", "mp3tag/tags.py"]:
            if not any(name.endswith("/" + expected) for name in names):
                errors.append(f"对应引擎源码不完整：{expected}")
        if engine_source.removeprefix("sources/") not in (site / "sources/index.html").read_text():
            errors.append("源码页没有当前引擎源码下载链接")

for message in sorted(set(errors)):
    print("错误：" + message)
for message in sorted(set(pending)):
    print("待完成：" + message)
if errors or (pending and not args.draft):
    raise SystemExit(1)
print("草稿已有内容检查通过，仍不可发布" if pending else "官网与发行一致性检查通过")
