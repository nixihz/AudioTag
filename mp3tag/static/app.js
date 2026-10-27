const $ = id => document.getElementById(id);
const definitions = [['title','歌曲名称','Title'],['artist','艺术家 / 歌手','Artist'],['album','专辑','Album'],['genre','流派','Genre'],['year','年份','Year'],['track','音轨编号','Track No.'],['bpm','节拍','BPM'],['lyrics','歌词','Lyrics']];
let files = [], cover = null, originalCover = null, audioUrl = null, coverUrl = null, downloadUrl = null, busy = false, inspectionGeneration = 0;
for (const [key, name, english] of definitions) {
  const container = document.createElement('div');
  container.className = 'field' + (key === 'lyrics' ? ' lyrics' : '');
  container.innerHTML = `<label for="${key}"><input type="checkbox" id="check-${key}" aria-label="写入${name}">${name}<span>${english}</span></label>${key === 'lyrics' ? `<textarea id="${key}" placeholder="歌词全文，包括段落与换行" spellcheck="false"></textarea>` : `<input id="${key}" type="text" placeholder="保留原值" spellcheck="false">`}`;
  $('fields').append(container);
  $(key).addEventListener('input', () => { $('check-'+key).checked = Boolean($(key).value.trim()); update(); });
  $('check-'+key).addEventListener('change', update);
}
function metadata() {
  return Object.fromEntries(definitions.filter(([key]) => $('check-'+key).checked && $(key).value.trim()).map(([key]) => [key, $(key).value.trim()]));
}
function update() {
  const count = Object.keys(metadata()).length;
  $('export').disabled = busy || !files.length || (!count && !cover);
  $('parse').disabled = busy;
  $('example').disabled = busy;
  $('summary').textContent = count || cover ? `将更新 ${count} 个字段${cover ? '与封面' : ''}` : '准备好，再写入。';
  $('export-note').textContent = files.length > 1 ? `同一份补丁应用到 ${files.length} 个文件，导出 ZIP。` : '导出新文件，保留未修改的标签。';
}
function status(message, type='') { $('status').textContent = message; $('status').className = type; }
async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = '操作失败，请重试';
    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : '请检查文件和标签格式'; } catch {}
    throw new Error(message);
  }
  return response;
}
function showCover(url) {
  $('cover-image').hidden = !url;
  if (url) $('cover-image').src = url; else $('cover-image').removeAttribute('src');
}
async function selectFiles(selected) {
  if (busy) return;
  const chosen = Array.from(selected);
  const allowed = /\.(mp3|flac|m4a|mp4|ogg|opus|wav)$/i;
  if (!chosen.length) return;
  if (chosen.length > 32 || chosen.some(file => !allowed.test(file.name) || file.size > 512*1024*1024) || chosen.reduce((n,file) => n + file.size, 0) > 2*1024**3) {
    status('请选择 1–32 个支持的音频文件，单文件最多 512 MB，每批最多 2 GB。', 'error'); return;
  }
  files = chosen;
  const generation = ++inspectionGeneration;
  $('file-count').textContent = `${files.length} 个文件`;
  $('file-list').replaceChildren();
  for (const [index, file] of files.entries()) {
    const item = document.createElement('li');
    const name = document.createElement('span'); name.textContent = file.name;
    const size = document.createElement('small'); size.textContent = `${(file.size/1024/1024).toFixed(1)} MB`;
    if (!index) item.className='active'; item.append(name, size); $('file-list').append(item);
  }
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = URL.createObjectURL(files[0]); $('player').src = audioUrl; $('player').hidden=false;
  originalCover = null; if (!cover) showCover(null);
  for (const [key] of definitions) if (!$('check-'+key).checked) $(key).value = '';
  status('正在读取第一个文件的已有标签…');
  busy = true; update();
  try {
    const form = new FormData(); form.append('file', files[0]);
    const data = await (await api('/api/inspect', {method:'POST', body:form})).json();
    if (generation !== inspectionGeneration) return;
    for (const [key] of definitions) if (!$('check-'+key).checked) $(key).value = data.metadata[key] || '';
    originalCover = data.cover || null;
    if (!cover) showCover(originalCover);
    status(`已读取 ${data.format} · ${Math.floor(data.duration/60)}:${String(Math.floor(data.duration%60)).padStart(2,'0')}${files.length > 1 ? '。字段显示第一个文件的值；勾选的字段将写入全部文件。' : '。勾选需要修改的字段。'}`);
  } catch (error) { status(error.message, 'error'); }
  finally { busy=false; update(); }
}
$('audio-files').addEventListener('change', event => selectFiles(event.target.files));
for (const event of ['dragenter','dragover']) $('dropzone').addEventListener(event, e => {e.preventDefault(); $('dropzone').classList.add('drag');});
for (const event of ['dragleave','drop']) $('dropzone').addEventListener(event, e => {e.preventDefault(); $('dropzone').classList.remove('drag');});
$('dropzone').addEventListener('drop', event => selectFiles(event.dataTransfer.files));
$('cover-file').addEventListener('change', async event => {
  if (busy) return;
  const file = event.target.files[0]; if (!file) return;
  if (!['image/jpeg','image/png'].includes(file.type) || file.size > 20*1024*1024) { status('请选择不超过 20 MB 的 JPEG 或 PNG 封面。','error'); return; }
  const url = URL.createObjectURL(file), img = new Image(); img.src = url;
  try {
    await img.decode();
    if (img.width*img.height > 40000000) throw new Error('封面分辨率过大');
    if (coverUrl) URL.revokeObjectURL(coverUrl);
    cover = file; coverUrl = url; showCover(url);
    $('cover-title').textContent = '封面已准备好'; $('cover-description').textContent = `${img.width} × ${img.height} · ${(file.size/1024/1024).toFixed(2)} MB`;
    $('remove-cover').hidden=false; status('导出时将替换前封面。'); update();
  } catch(error) { URL.revokeObjectURL(url); status(error.message || '无法读取图片','error'); }
});
$('remove-cover').addEventListener('click', () => {
  if (busy) return;
  cover=null; if (coverUrl) URL.revokeObjectURL(coverUrl); coverUrl=null;
  $('cover-file').value=''; showCover(originalCover); $('remove-cover').hidden=true;
  $('cover-title').textContent='让封面也归位'; $('cover-description').textContent='JPEG 或 PNG，最多 20 MB。未上传时保留原封面。'; update();
});
$('parse').addEventListener('click', async () => {
  busy=true; update(); status('正在解析信息…');
  try {
    const data = await (await api('/api/parse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('raw-text').value})})).json();
    for (const [key,value] of Object.entries(data.metadata)) { $(key).value=value; $('check-'+key).checked=true; }
    $('warnings').hidden=!data.warnings.length; $('warnings').textContent=data.warnings.join('\n');
    status(`已解析 ${Object.keys(data.metadata).length} 个字段。检查后即可写入。`, 'success');
  } catch(error) { status(error.message,'error'); }
  finally {busy=false; update();}
});
$('deselect').addEventListener('click', () => { if (busy) return; for (const [key] of definitions) $('check-'+key).checked=false; update(); });
$('example').addEventListener('click', async () => { try { const response=await api('/example.txt'); $('raw-text').value=await response.text(); status('示例已填入，点击「解析信息」即可。'); } catch(error) {status(error.message,'error');} });
$('export').addEventListener('click', async () => {
  if (busy) return;
  const form = new FormData(); for (const file of files) form.append('files',file);
  form.append('metadata',JSON.stringify(metadata())); if (cover) form.append('cover',cover);
  busy=true; update(); $('export').textContent='正在写入…'; status('正在写入标签并校验，较大的文件需要一点时间。'); $('download').hidden=true;
  try {
    const response=await api('/api/patch',{method:'POST',body:form});
    const blob=await response.blob();
    const disposition=response.headers.get('Content-Disposition') || '';
    const encoded=disposition.match(/filename\*=UTF-8''([^;]+)/i), plain=disposition.match(/filename="([^"]+)"/i);
    const filename=encoded ? decodeURIComponent(encoded[1]) : plain ? plain[1] : files.length>1 ? 'AudioTag-tagged.zip' : files[0].name.replace(/(\.[^.]+)$/,'.tagged$1');
    if (downloadUrl) URL.revokeObjectURL(downloadUrl); downloadUrl=URL.createObjectURL(blob);
    $('download').href=downloadUrl; $('download').download=filename; $('download').textContent=`下载 ${filename}`; $('download').hidden=false; $('download').click();
    status(`已写入并校验 ${files.length} 个文件。原文件保持完整。`, 'success');
  } catch(error) {status(error.message,'error');}
  finally {busy=false; $('export').innerHTML='写入并导出 <span aria-hidden="true">↗</span>'; update();}
});
update();
