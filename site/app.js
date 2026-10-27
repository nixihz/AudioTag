const safeLocalFile = (value, prefix) => {
  if (typeof value !== "string" || !value.startsWith(prefix) || value.includes("..")) return null;
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(value.slice(prefix.length))) return null;
  const url = new URL(value, document.baseURI);
  const directory = new URL(prefix, document.baseURI);
  return url.origin === location.origin && url.pathname.startsWith(directory.pathname) &&
    !url.search && !url.hash && !url.username && !url.password ? url : null;
};

async function loadRelease() {
  try {
    const response = await fetch("release.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("版本数据暂时不可用");
    const release = await response.json();
    const file = safeLocalFile(release.download, "downloads/");
    const notes = safeLocalFile(release.notes, "downloads/");
    if (!file || !notes || !Number.isSafeInteger(release.bytes) || release.bytes < 1) throw new Error("版本数据不完整");
    document.querySelector("[data-version]").textContent = `${release.version}（${release.build}）· ${release.date}`;
    const download = document.querySelector("[data-download]");
    download.href = file.href;
    download.setAttribute("download", "");
    download.replaceChildren(document.createTextNode("下载 Mac 版"));
    const arrow = document.createElement("span");
    arrow.textContent = "↓";
    arrow.setAttribute("aria-hidden", "true");
    download.append(arrow);
    document.querySelector("[data-checksums]").hidden = false;
    document.querySelector("[data-download-meta]").textContent = `${(release.bytes / 1024 / 1024).toFixed(1)} MB · ${release.architecture} · ${release.notarized ? "Developer ID 签名 / Apple 公证" : "签名状态请见发行说明"}`;
    const article = document.createElement("article");
    const date = document.createElement("time");
    date.dateTime = release.date;
    date.textContent = release.date;
    const title = document.createElement("h3");
    title.textContent = `AudioTag ${release.version}（${release.build}）`;
    const description = document.createElement("p");
    description.textContent = release.summary;
    const link = document.createElement("a");
    link.href = notes.href;
    link.textContent = "阅读完整发行说明 ↗";
    article.append(date, title, description, link);
    document.querySelector("#release-list").replaceChildren(article);
  } catch {
    document.querySelector("[data-download-meta]").textContent = "版本数据暂时不可用，请稍后重试或查看版本清单。";
  }
}

loadRelease();
