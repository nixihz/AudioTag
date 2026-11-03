const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(new URL("../site/app.js", `file://${__filename}`), "utf8");

function page(fetch) {
  const elements = new Map();
  const element = () => ({
    textContent: "", children: [], attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); }
  });
  const document = {
    baseURI: "https://audiotag.xiezhixin.com/",
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, element());
      return elements.get(selector);
    },
    createElement: element,
    createTextNode(text) { return { textContent: text }; }
  };
  const context = { URL, document, location: { origin: "https://audiotag.xiezhixin.com" }, fetch };
  vm.runInNewContext(source + "\nglobalThis.api = {safeLocalFile, loadRelease};", context);
  return { api: context.api, elements };
}

test("下载地址限制在本站发行目录，拒绝编码路径、外链与查询凭据", () => {
  const { api } = page(() => new Promise(() => {}));
  assert.equal(api.safeLocalFile("downloads/audiotag-1.0.0-1.zip", "downloads/").href,
    "https://audiotag.xiezhixin.com/downloads/audiotag-1.0.0-1.zip");
  for (const path of [
    "https://attacker.invalid/app.zip", "//attacker.invalid/app.zip", "downloads/../secret",
    "downloads/%2e%2e/secret", "downloads/%252e%252e/secret", "downloads/sub/app.zip",
    "downloads/app.zip?token=private", "downloads/app.zip#fragment", "downloads/\\attacker.zip"
  ]) assert.equal(api.safeLocalFile(path, "downloads/"), null, path);
});

test("版本数据更新下载入口、体积、公证提示与发行说明", async () => {
  const release = {
    download: "downloads/audiotag-1.0.0-1.zip", notes: "downloads/audiotag-1.0.0-1.html",
    bytes: 10 * 1024 * 1024, version: "1.0.0", build: "1", date: "2026-10-27",
    architecture: "Apple Silicon", notarized: true, summary: "<script>不应作为 HTML 执行</script>"
  };
  const { api, elements } = page(async () => ({ ok: true, json: async () => release }));
  await api.loadRelease();
  assert.equal(elements.get("[data-download]").href, "https://audiotag.xiezhixin.com/downloads/audiotag-1.0.0-1.zip");
  assert.match(elements.get("[data-download-meta]").textContent, /10\.0 MB.*Apple 公证/);
  assert.equal(elements.get("#release-list").children[0].children[1].textContent, "AudioTag 1.0.0（1）");
  assert.equal(elements.get("#release-list").children[0].children[2].textContent, release.summary);
});

test("非法版本记录和服务器失败不生成下载链接", async () => {
  for (const response of [
    { ok: false },
    { ok: true, json: async () => ({ download: "downloads/../secret", notes: "downloads/notes.html", bytes: 5 }) }
  ]) {
    const { api, elements } = page(async () => response);
    await api.loadRelease();
    assert.match(elements.get("[data-download-meta]").textContent, /暂时不可用/);
    assert.equal(elements.has("[data-download]"), false);
  }
});
