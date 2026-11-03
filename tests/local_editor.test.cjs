const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(new URL("../audiotag/static/app.js", `file://${__filename}`), "utf8");

// 用不同的名字导出，避免覆盖脚本自身的 api() 函数。
const EXPOSED = "globalThis.editorApi = { metadata, update, status, selectFiles, showCover }";

function createElement(id = "", tag = "div") {
  const classes = new Set();
  const handlers = {};
  const element = {
    id, tagName: tag, innerHTML: "", textContent: "", value: "",
    checked: false, hidden: false, src: "", href: "", download: "", disabled: false,
    children: [], files: [], clicks: 0,
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name)
    },
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = nodes; },
    setAttribute(name, value) { this[name] = value; },
    removeAttribute(name) { delete this[name]; },
    addEventListener(type, handler) { handlers[type] = handler; },
    dispatch(type, event = {}) { if (handlers[type]) handlers[type]({ target: this, ...event }); },
    click() { this.clicks += 1; }
  };
  Object.defineProperty(element, "className", {
    get: () => [...classes].join(" "),
    set: (value) => {
      classes.clear();
      String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name));
    }
  });
  return element;
}

function createPage(options = {}) {
  const elements = new Map();
  const objectUrls = new Map();
  const imageSize = { width: 64, height: 64 };
  let urlCount = 0;

  const get = (id) => {
    if (!elements.has(id)) elements.set(id, createElement(id));
    return elements.get(id);
  };

  const document = {
    getElementById: get,
    createElement: (tag) => createElement("", tag),
    createTextNode: (text) => ({ textContent: text })
  };

  class MockImage {
    constructor() { this._src = ""; }
    get src() { return this._src; }
    set src(value) { this._src = value; }
    get width() { return imageSize.width; }
    get height() { return imageSize.height; }
    async decode() { if (options.decodeError) throw options.decodeError; }
  }

  const url = {
    createObjectURL: (blob) => {
      const value = `blob:mock/${++urlCount}`;
      objectUrls.set(value, blob);
      return value;
    },
    revokeObjectURL: (value) => { objectUrls.delete(value); }
  };

  const calls = [];
  const fetch = async (target, init) => {
    calls.push({ target, init });
    if (options.fetch) return options.fetch(target, init);
    return { ok: true, status: 200, json: async () => ({}), blob: async () => new Blob([]), headers: { get: () => null } };
  };

  const context = { document, URL: url, Image: MockImage, fetch, FormData, File, Blob, console, setTimeout, clearTimeout };
  vm.createContext(context);
  vm.runInContext(source + "\n" + EXPOSED, context);
  return { api: context.editorApi, elements, get, calls, imageSize, objectUrls };
}

function audioFile(name = "song.mp3", size = 1024) {
  const file = new File([new Uint8Array(size)], name, { type: "audio/mpeg" });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

// 跨 realm 的对象原型不同，比较前先转成普通数据。
function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

test("渲染八个字段，输入自动勾选并汇总补丁", () => {
  const { api, get } = createPage();
  assert.equal(get("fields").children.length, 8);
  assert.deepEqual(plain(api.metadata()), {});

  get("title").value = "  歌曲标题  ";
  get("title").dispatch("input");
  assert.equal(get("check-title").checked, true);
  assert.deepEqual(plain(api.metadata()), { title: "歌曲标题" });

  get("title").value = "   ";
  get("title").dispatch("input");
  assert.equal(get("check-title").checked, false);
  assert.deepEqual(plain(api.metadata()), {});
});

test("没有文件时禁止导出，选中字段后给出待写入数量", () => {
  const { api, get } = createPage();
  assert.equal(get("export").disabled, true);
  assert.equal(get("summary").textContent, "准备好，再写入。");

  get("title").value = "标题";
  get("title").dispatch("input");
  assert.equal(get("check-title").checked, true);
  assert.equal(get("summary").textContent, "将更新 1 个字段");
  assert.equal(get("export").disabled, true, "没有文件时仍不能导出");
});

test("选择文件后读取已有标签，只填入未勾选的字段", async () => {
  const { api, get } = createPage({
    fetch: async (target) => {
      assert.equal(target, "/api/inspect");
      return { ok: true, status: 200, json: async () => ({ metadata: { title: "旧标题", artist: "旧歌手" }, format: "MP3", duration: 61 }) };
    }
  });
  await api.selectFiles([audioFile()]);
  assert.equal(get("file-count").textContent, "1 个文件");
  assert.equal(get("title").value, "旧标题");
  assert.equal(get("artist").value, "旧歌手");
  assert.equal(get("check-title").checked, false);
  assert.equal(get("file-list").children.length, 1);
});

test("超过批量上限的文件被拒绝并给出提示", async () => {
  const { api, get } = createPage();
  const many = Array.from({ length: 33 }, () => audioFile());
  await api.selectFiles(many);
  assert.match(get("status").textContent, /1–32 个/);
  assert.equal(get("status").className, "error");
});

test("不支持的格式与超限文件被拒绝", async () => {
  const { api, get } = createPage();
  await api.selectFiles([audioFile("notes.txt")]);
  assert.match(get("status").textContent, /1–32 个/);
  await api.selectFiles([audioFile("big.mp3", 600 * 1024 * 1024)]);
  assert.match(get("status").textContent, /1–32 个/);
});

test("解析文本后填入字段并勾选，同时展示警告", async () => {
  const { api, get } = createPage({
    fetch: async () => ({
      ok: true, status: 200,
      json: async () => ({ metadata: { title: "解析标题", artist: "解析歌手" }, warnings: ["重复字段"] })
    })
  });
  get("raw-text").value = "Title: 解析标题";
  get("parse").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(get("title").value, "解析标题");
  assert.equal(get("check-artist").checked, true);
  assert.equal(get("warnings").hidden, false);
  assert.equal(get("warnings").textContent, "重复字段");
  assert.equal(get("status").className, "success");
});

test("服务端报错时给出错误提示而不是成功状态", async () => {
  const { api, get } = createPage({
    fetch: async () => ({ ok: false, status: 400, json: async () => ({ detail: "标签内容过长" }) })
  });
  get("raw-text").value = "Title: 解析标题";
  get("parse").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(get("status").textContent, "标签内容过长");
  assert.equal(get("status").className, "error");
});

test("导出提交补丁并生成下载链接", async () => {
  const { api, get, calls } = createPage({
    fetch: async (target) => {
      if (target === "/api/inspect") {
        return { ok: true, status: 200, json: async () => ({ metadata: {}, format: "MP3", duration: 1 }) };
      }
      return {
        ok: true, status: 200,
        blob: async () => new Blob(["zip"]),
        headers: { get: () => 'attachment; filename="AudioTag-tagged.zip"' }
      };
    }
  });
  await api.selectFiles([audioFile()]);
  get("check-title").checked = true;
  get("title").value = "导出标题";
  get("export").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  const patch = calls.find((call) => call.target === "/api/patch");
  assert.ok(patch, "应当提交导出请求");
  assert.equal(get("download").hidden, false);
  assert.equal(get("download").download, "AudioTag-tagged.zip");
  assert.equal(get("download").clicks, 1);
  assert.equal(get("status").className, "success");
});

test("封面只接受 JPEG 与 PNG，并按分辨率上限拒绝", async () => {
  const { api, get } = createPage();
  const gif = new File([new Uint8Array(8)], "cover.gif", { type: "image/gif" });
  get("cover-file").files = [gif];
  get("cover-file").dispatch("change");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(get("status").className, "error");
  assert.match(get("status").textContent, /JPEG 或 PNG/);

  const bigPage = createPage();
  const bigGet = bigPage.get;
  bigPage.imageSize.width = 8000;
  bigPage.imageSize.height = 8000;
  const png = new File([new Uint8Array(8)], "cover.png", { type: "image/png" });
  bigGet("cover-file").files = [png];
  bigGet("cover-file").dispatch("change");
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(bigGet("status").textContent, /分辨率过大/);
});

test("移除封面后恢复原封面", async () => {
  const { api, get } = createPage({
    fetch: async (target) => {
      if (target === "/api/inspect") {
        return { ok: true, status: 200, json: async () => ({ metadata: {}, cover: "data:image/png;base64,AAAA", format: "MP3", duration: 1 }) };
      }
      return { ok: true, status: 200, json: async () => ({}), blob: async () => new Blob([]), headers: { get: () => null } };
    }
  });
  await api.selectFiles([audioFile()]);
  assert.equal(get("cover-image").src, "data:image/png;base64,AAAA");

  const png = new File([new Uint8Array(8)], "cover.png", { type: "image/png" });
  get("cover-file").files = [png];
  get("cover-file").dispatch("change");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(get("remove-cover").hidden, false);

  get("remove-cover").dispatch("click");
  assert.equal(get("remove-cover").hidden, true);
  assert.equal(get("cover-image").src, "data:image/png;base64,AAAA");
});
