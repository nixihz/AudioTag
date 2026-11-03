'use strict';

/**
 * 本地网页编辑器。
 *
 * 文件只在本机处理：上传到本地服务的临时目录，导出完成后随目录一起删除。
 * 只有勾选且非空的字段才会写入，未勾选或留空的字段保留原值。
 */

/** 字段定义：[键, 中文名, 英文名]。 */
const FIELDS = [
  ['title', '歌曲名称', 'Title'],
  ['artist', '艺术家 / 歌手', 'Artist'],
  ['album', '专辑', 'Album'],
  ['genre', '流派', 'Genre'],
  ['year', '年份', 'Year'],
  ['track', '音轨编号', 'Track No.'],
  ['bpm', '节拍', 'BPM'],
  ['lyrics', '歌词', 'Lyrics']
];

/** 允许选择的扩展名。 */
const ALLOWED_EXTENSIONS = /\.(mp3|flac|m4a|mp4|ogg|opus|wav)$/i;

/** 一批最多 32 个文件，单个最多 512 MB，总计最多 2 GB。 */
const MAX_FILES = 32;
const MAX_FILE_SIZE = 512 * 1024 * 1024;
const MAX_TOTAL_SIZE = 2 * 1024 ** 3;

/** 封面只接受 JPEG 与 PNG，最多 20 MB、4000 万像素。 */
const COVER_MIME_TYPES = ['image/jpeg', 'image/png'];
const MAX_COVER_SIZE = 20 * 1024 * 1024;
const MAX_COVER_PIXELS = 40_000_000;

/** 当前会话的状态。 */
const state = {
  files: [],
  cover: null,
  originalCover: null,
  audioUrl: null,
  coverUrl: null,
  downloadUrl: null,
  busy: false,
  inspectionGeneration: 0
};

const $ = id => document.getElementById(id);

// ------------------------------------------------------------------ 字段

/** 按定义生成八个字段的输入框与勾选框。 */
function buildFields() {
  for (const [key, name, english] of FIELDS) {
    const container = document.createElement('div');
    container.className = 'field' + (key === 'lyrics' ? ' lyrics' : '');
    container.innerHTML = `<label for="${key}"><input type="checkbox" id="check-${key}" aria-label="写入${name}">${name}<span>${english}</span></label>${
      key === 'lyrics'
        ? `<textarea id="${key}" placeholder="歌词全文，包括段落与换行" spellcheck="false"></textarea>`
        : `<input id="${key}" type="text" placeholder="保留原值" spellcheck="false">`
    }`;
    $('fields').append(container);
    $('check-' + key).addEventListener('change', update);
    $(key).addEventListener('input', () => {
      $('check-' + key).checked = Boolean($(key).value.trim());
      update();
    });
  }
}

/** 当前勾选且非空的字段，作为写入补丁。 */
function metadata() {
  return Object.fromEntries(
    FIELDS
      .filter(([key]) => $('check-' + key).checked && $(key).value.trim())
      .map(([key]) => [key, $(key).value.trim()])
  );
}

/** 刷新按钮状态与提示文字。 */
function update() {
  const count = Object.keys(metadata()).length;
  $('export').disabled = state.busy || !state.files.length || (!count && !state.cover);
  $('parse').disabled = state.busy;
  $('example').disabled = state.busy;
  $('summary').textContent = count || state.cover ? `将更新 ${count} 个字段${state.cover ? '与封面' : ''}` : '准备好，再写入。';
  $('export-note').textContent = state.files.length > 1 ? `同一份补丁应用到 ${state.files.length} 个文件，导出 ZIP。` : '导出新文件，保留未修改的标签。';
}

/** 显示一条状态提示。 */
function status(message, type = '') {
  $('status').textContent = message;
  $('status').className = type;
}

// ------------------------------------------------------------------ 请求

/** 发送请求，失败时抛出服务端给出的原因。 */
async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = '操作失败，请重试';
    try {
      const data = await response.json();
      message = typeof data.detail === 'string' ? data.detail : '请检查文件和标签格式';
    } catch {}
    throw new Error(message);
  }
  return response;
}

// ------------------------------------------------------------------ 封面

/** 显示封面预览，url 为空时清空。 */
function showCover(url) {
  $('cover-image').hidden = !url;
  if (url) $('cover-image').src = url;
  else $('cover-image').removeAttribute('src');
}

/** 读取并应用用户选择的封面。 */
async function selectCover(file) {
  if (!file) return;
  if (!COVER_MIME_TYPES.includes(file.type) || file.size > MAX_COVER_SIZE) {
    status('请选择不超过 20 MB 的 JPEG 或 PNG 封面。', 'error');
    return;
  }
  const url = URL.createObjectURL(file);
  const image = new Image();
  image.src = url;
  try {
    await image.decode();
    if (image.width * image.height > MAX_COVER_PIXELS) throw new Error('封面分辨率过大');
    if (state.coverUrl) URL.revokeObjectURL(state.coverUrl);
    state.cover = file;
    state.coverUrl = url;
    showCover(url);
    $('cover-title').textContent = '封面已准备好';
    $('cover-description').textContent = `${image.width} × ${image.height} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
    $('remove-cover').hidden = false;
    status('导出时将替换前封面。');
    update();
  } catch (error) {
    URL.revokeObjectURL(url);
    status(error.message || '无法读取图片', 'error');
  }
}

/** 取消本次封面替换，恢复原封面。 */
function removeCover() {
  if (state.busy) return;
  state.cover = null;
  if (state.coverUrl) URL.revokeObjectURL(state.coverUrl);
  state.coverUrl = null;
  $('cover-file').value = '';
  showCover(state.originalCover);
  $('remove-cover').hidden = true;
  $('cover-title').textContent = '让封面也归位';
  $('cover-description').textContent = 'JPEG 或 PNG，最多 20 MB。未上传时保留原封面。';
  update();
}

// ------------------------------------------------------------------ 文件

/** 判断一批文件是否符合数量、格式与体积限制。 */
function isAcceptable(files) {
  if (files.length > MAX_FILES) return false;
  if (files.some(file => !ALLOWED_EXTENSIONS.test(file.name) || file.size > MAX_FILE_SIZE)) return false;
  return files.reduce((total, file) => total + file.size, 0) <= MAX_TOTAL_SIZE;
}

/** 在侧栏列出选中的文件。 */
function renderFileList() {
  const list = $('file-list');
  list.replaceChildren();
  for (const [index, file] of state.files.entries()) {
    const item = document.createElement('li');
    const name = document.createElement('span');
    name.textContent = file.name;
    const size = document.createElement('small');
    size.textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB`;
    if (!index) item.className = 'active';
    item.append(name, size);
    list.append(item);
  }
}

/** 选择文件后读取首个文件的已有标签。 */
async function selectFiles(selected) {
  if (state.busy) return;
  const files = Array.from(selected);
  if (!files.length) return;
  if (!isAcceptable(files)) {
    status('请选择 1–32 个支持的音频文件，单文件最多 512 MB，每批最多 2 GB。', 'error');
    return;
  }
  state.files = files;
  const generation = ++state.inspectionGeneration;
  $('file-count').textContent = `${state.files.length} 个文件`;
  renderFileList();
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  state.audioUrl = URL.createObjectURL(state.files[0]);
  $('player').src = state.audioUrl;
  $('player').hidden = false;
  state.originalCover = null;
  if (!state.cover) showCover(null);
  for (const [key] of FIELDS) if (!$('check-' + key).checked) $(key).value = '';
  status('正在读取第一个文件的已有标签…');
  state.busy = true;
  update();
  try {
    const form = new FormData();
    form.append('file', state.files[0]);
    const data = await (await api('/api/inspect', { method: 'POST', body: form })).json();
    if (generation !== state.inspectionGeneration) return;
    for (const [key] of FIELDS) if (!$('check-' + key).checked) $(key).value = data.metadata[key] || '';
    state.originalCover = data.cover || null;
    if (!state.cover) showCover(state.originalCover);
    const minutes = Math.floor(data.duration / 60);
    const seconds = String(Math.floor(data.duration % 60)).padStart(2, '0');
    const scope = state.files.length > 1
      ? '。字段显示第一个文件的值；勾选的字段将写入全部文件。'
      : '。勾选需要修改的字段。';
    status(`已读取 ${data.format} · ${minutes}:${seconds}${scope}`);
  } catch (error) {
    status(error.message, 'error');
  } finally {
    state.busy = false;
    update();
  }
}

// ---------------------------------------------------------- 解析与导出

/** 解析粘贴的歌曲信息并填入字段。 */
async function parseText() {
  state.busy = true;
  update();
  status('正在解析信息…');
  try {
    const data = await (await api('/api/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: $('raw-text').value })
    })).json();
    for (const [key, value] of Object.entries(data.metadata)) {
      $(key).value = value;
      $('check-' + key).checked = true;
    }
    $('warnings').hidden = !data.warnings.length;
    $('warnings').textContent = data.warnings.join('\n');
    status(`已解析 ${Object.keys(data.metadata).length} 个字段。检查后即可写入。`, 'success');
  } catch (error) {
    status(error.message, 'error');
  } finally {
    state.busy = false;
    update();
  }
}

/** 载入内置示例。 */
async function loadExample() {
  try {
    const response = await api('/example.txt');
    $('raw-text').value = await response.text();
    status('示例已填入，点击「解析信息」即可。');
  } catch (error) {
    status(error.message, 'error');
  }
}

/** 取消所有字段的勾选。 */
function deselectAll() {
  if (state.busy) return;
  for (const [key] of FIELDS) $('check-' + key).checked = false;
  update();
}

/** 从响应头里取出下载文件名。 */
function downloadName(disposition, fallback) {
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  const plain = disposition.match(/filename="([^"]+)"/i);
  if (encoded) return decodeURIComponent(encoded[1]);
  if (plain) return plain[1];
  return fallback;
}

/** 导出补丁，单个文件直接下载，多个文件打包下载。 */
async function exportFiles() {
  if (state.busy) return;
  const form = new FormData();
  for (const file of state.files) form.append('files', file);
  form.append('metadata', JSON.stringify(metadata()));
  if (state.cover) form.append('cover', state.cover);
  state.busy = true;
  update();
  $('export').textContent = '正在写入…';
  status('正在写入标签并校验，较大的文件需要一点时间。');
  $('download').hidden = true;
  try {
    const response = await api('/api/patch', { method: 'POST', body: form });
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const fallback = state.files.length > 1
      ? 'AudioTag-tagged.zip'
      : state.files[0].name.replace(/(\.[^.]+)$/, '.tagged$1');
    const filename = downloadName(disposition, fallback);
    if (state.downloadUrl) URL.revokeObjectURL(state.downloadUrl);
    state.downloadUrl = URL.createObjectURL(blob);
    $('download').href = state.downloadUrl;
    $('download').download = filename;
    $('download').textContent = `下载 ${filename}`;
    $('download').hidden = false;
    $('download').click();
    status(`已写入并校验 ${state.files.length} 个文件。原文件保持完整。`, 'success');
  } catch (error) {
    status(error.message, 'error');
  } finally {
    state.busy = false;
    $('export').innerHTML = '写入并导出 <span aria-hidden="true">↗</span>';
    update();
  }
}

// ------------------------------------------------------------------ 事件

function onDragOver(event) {
  event.preventDefault();
  $('dropzone').classList.add('drag');
}

function onDragLeave(event) {
  event.preventDefault();
  $('dropzone').classList.remove('drag');
}

function onDrop(event) {
  event.preventDefault();
  $('dropzone').classList.remove('drag');
  selectFiles(event.dataTransfer.files);
}

function bindEvents() {
  $('audio-files').addEventListener('change', event => selectFiles(event.target.files));
  $('dropzone').addEventListener('dragenter', onDragOver);
  $('dropzone').addEventListener('dragover', onDragOver);
  $('dropzone').addEventListener('dragleave', onDragLeave);
  $('dropzone').addEventListener('drop', onDrop);
  $('cover-file').addEventListener('change', event => {
    if (!state.busy) selectCover(event.target.files[0]);
  });
  $('remove-cover').addEventListener('click', removeCover);
  $('parse').addEventListener('click', parseText);
  $('deselect').addEventListener('click', deselectAll);
  $('example').addEventListener('click', loadExample);
  $('export').addEventListener('click', exportFiles);
}

buildFields();
bindEvents();
update();
