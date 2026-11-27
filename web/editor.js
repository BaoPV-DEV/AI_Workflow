const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const api = async (u, o = {}) => {
  const r = await fetch(u, { headers: { 'Content-Type': 'application/json' }, ...o, body: o.body ? JSON.stringify(o.body) : undefined });
  if (r.status === 404 && u.startsWith('/api/') && typeof staleBanner === 'function') staleBanner(true);  // máy chủ cũ chưa có chức năng này
  return r.json();
};
const ENGINE = ['audio_path', 'duration', 'word_timings', 'speech'];
const GENRES = { animation: 'Hoạt hình người que', motion_graphic: 'Motion graphics', news: 'Tin tức', explainer: 'Giải thích' };
const TPL_NAMES = { stickman_stage: 'Người que diễn', title_card_neon: 'Tiêu đề', kinetic_text: 'Chữ theo giọng', stat_card: 'Con số', bullet_list: 'Danh sách ý', bar_chart: 'Biểu đồ cột', compare_split: 'So sánh', timeline: 'Dòng thời gian', quote_card: 'Trích dẫn', headline_news: 'Bản tin' };
const TPL_COLOR = { stickman_stage: '#f2a516', kinetic_text: '#e5484d', title_card_neon: '#e5484d', headline_news: '#e5484d', quote_card: '#e5484d', stat_card: '#2f5bea', bar_chart: '#2f5bea', timeline: '#2f5bea', bullet_list: '#1f9d6b', compare_split: '#1f9d6b' };
const PROP_LABEL = { title: 'Tiêu đề', title_at: 'Hiện tiêu đề lúc', backdrop: 'Bối cảnh', items: 'Các mục', heading: 'Tiêu đề chính', subheading: 'Dòng phụ', kicker: 'Nhãn nhỏ phía trên', value: 'Con số', prefix: 'Chữ trước số', suffix: 'Chữ sau số', label: 'Nhãn', sub: 'Ghi chú nhỏ', at: 'Bắt đầu lúc', decimals: 'Số chữ số lẻ', icon: 'Ký hiệu đầu dòng', quote: 'Câu trích', author: 'Tác giả', bars: 'Các cột', unit: 'Đơn vị', left: 'Bên thứ nhất', right: 'Bên thứ hai', vs: 'Chữ ở giữa', winner: 'Bên được tô nổi', events: 'Các mốc', emphasize: 'Từ cần tô màu', group: 'Số từ mỗi lượt', bg_word: 'Chữ mờ phía sau', headline: 'Tiêu đề tin', ticker: 'Dòng chữ chạy', source: 'Nguồn tin', image: 'Ảnh nền', fit: 'Cách lấp khung' };
const MOOD_VI = { neutral: 'bình thường', happy: 'vui', sad: 'buồn', surprised: 'ngạc nhiên', angry: 'tức giận', scared: 'sợ', tired: 'mệt', curious: 'tò mò', proud: 'tự hào', love: 'yêu thích', laugh: 'cười lớn' };
const MOVE_VI = { stay: 'đứng yên', enter_left: 'vào từ trái', enter_right: 'vào từ phải', exit_left: 'ra phía trái', exit_right: 'ra phía phải', left: 'sang trái', center: 'ra giữa', right: 'sang phải' };
const HOLD_VI = { book: 'sách', phone: 'điện thoại', coin: 'đồng xu', money: 'tiền', gift: 'quà', bulb: 'bóng đèn', sign: 'tấm biển', laptop: 'laptop', cup: 'cốc', flag: 'cờ', sword: 'kiếm', key: 'chìa khoá', star: 'ngôi sao', trophy: 'cúp', magnifier: 'kính lúp', map: 'bản đồ', briefcase: 'cặp', microphone: 'micro', pen: 'bút', pizza: 'pizza', umbrella: 'ô' };
const VTYPES = { html_animation: 'Template dựng sẵn', svg_graphic: 'SVG tự vẽ', image: 'Ảnh có sẵn', video: 'Clip có sẵn', comfyui: 'Ảnh/clip AI (ComfyUI)', color: 'Nền màu' };
const tplName = s => s.visual_type === 'html_animation' ? (TPL_NAMES[s.template_name] || s.template_name) : ({ svg_graphic: 'SVG', image: 'Ảnh', video: 'Clip', comfyui: 'ComfyUI', color: 'Nền màu' }[s.visual_type] || s.visual_type);

let META, PID, M, ST, ERR = [], CUR = -1, TAB = 'content';
let hist = [], fut = [], lastPush = 0, histKey = null, saveTimer, saving = false;
let playing = false, auto = true, muted = false, t = 0, clock0 = 0, raf, frameTpl = null, frameInput = null;
let job = null;

/* ================= khởi động ================= */
/* ================= dự án ================= */
async function openProject(id) {
  const r = await api('/api/p/' + encodeURIComponent(id));
  if (r.error) throw r.error;
  PID = id; M = r.manifest; ERR = r.errors; ST = r.status; hist = []; fut = []; CUR = -1;
  localStorage.setItem('vf.pid', id);
  for (const el of ['#ptitle', '#steps', '#btnSettings', '#btnDraft', '#btnRender', '#transport', '#addrow', '#btnLog']) $(el).hidden = false;
  $('#stagemsg').hidden = true;
  $('#ptitle').value = M.title || M.project_id;
  $('#savestate').textContent = '';
  frameTpl = null;
  renderAll();
  select(0);
}

async function refreshStatus() {
  const r = await api('/api/p/' + PID);
  ST = r.status; ERR = r.errors;
  // engine đã điền duration/word_timings: lấy về, giữ thay đổi đang gõ
  r.manifest.scenes.forEach(s => { const mine = M.scenes.find(x => x.scene_id === s.scene_id); if (mine && mine.voice_text === s.voice_text) for (const k of ENGINE) if (s[k] !== undefined) mine[k] = s[k]; });
  renderSteps(); renderTimeline(); renderParasMeta(); loadFrame();
}

/* ================= thay đổi, tự lưu, hoàn tác ================= */
function change(fn, coalesceKey) {
  const now = Date.now();
  if (!coalesceKey || now - lastPush > 1200 || coalesceKey !== histKey) { hist.push(JSON.stringify(M)); if (hist.length > 80) hist.shift(); fut = []; }
  histKey = coalesceKey; lastPush = now;
  fn(M);
  scheduleSave();
}
function scheduleSave() { $('#savestate').textContent = 'Đang sửa…'; clearTimeout(saveTimer); saveTimer = setTimeout(save, 650); }
async function save() {
  clearTimeout(saveTimer);
  if (!PID) return;
  saving = true; $('#savestate').textContent = 'Đang lưu…';
  const r = await api('/api/p/' + PID, { method: 'PUT', body: M });
  saving = false;
  if (r.error) { $('#savestate').textContent = 'Chưa lưu được'; return toast(r.error, true); }
  ERR = r.errors || [];
  $('#savestate').textContent = ERR.length ? `Đã lưu, còn ${ERR.length} lỗi` : 'Đã lưu';
  renderSteps(); renderParasMeta(); renderTimeline(); renderErrors(); loadFrame();
}
function undo() { if (!hist.length) return toast('Không còn gì để hoàn tác'); fut.push(JSON.stringify(M)); M = JSON.parse(hist.pop()); histKey = null; afterHistory('Đã hoàn tác'); }
function redo() { if (!fut.length) return; hist.push(JSON.stringify(M)); M = JSON.parse(fut.pop()); histKey = null; afterHistory('Đã làm lại'); }
function afterHistory(msg) { const keep = Math.min(CUR, M.scenes.length - 1); CUR = -1; renderAll(); select(keep); scheduleSave(); toast(msg); }
const sc = () => M?.scenes[CUR];
const scKey = s => typeof s.scene_id === 'number' ? 's' + String(s.scene_id).padStart(3, '0') : String(s.scene_id);
const estDur = s => s.duration || Math.max(2.5, (s.voice_text || '').split(/\s+/).filter(Boolean).length / 2.5 + 0.3);
const invalidate = s => ENGINE.forEach(k => delete s[k]);

/* ================= vẽ giao diện ================= */
function renderAll() { renderSteps(); renderParas(); renderTimeline(); renderInspector(); }

function renderSteps() {
  const n = M.scenes.length, v = ST.voiced, th = Object.keys(ST.thumbs).length, vids = Object.keys(ST.videos);
  const full = vids.includes(PID + '.mp4');
  const steps = [
    { t: 'Kịch bản', done: !ERR.length, warn: ERR.length > 0, act: () => ERR.length ? toast(ERR[0], true) : toast('Kịch bản hợp lệ') },
    { t: `Giọng đọc <span class="long num">${v}/${n}</span>`, done: v === n, act: () => run('voice') },
    { t: `Xem trước <span class="long num">${th}/${n}</span>`, done: th === n, act: () => run('preview') },
    { t: full ? 'Video đã xuất' : 'Xuất video', done: full, act: () => full ? showOutput(PID + '.mp4') : run('all') },
  ];
  const next = steps.find(s => !s.done);
  $('#steps').innerHTML = steps.map((s, i) => `<button class="step ${s.done ? 'done' : ''} ${s.warn ? 'warn' : ''} ${s === next && !s.warn ? 'next' : ''}" data-i="${i}" title="${s.done ? 'Đã xong, bấm để làm lại' : 'Bấm để chạy bước này'}"><b>${s.done ? '✓' : s.warn ? '!' : i + 1}</b><span>${s.t}</span></button>`).join('');
  $('#steps').querySelectorAll('.step').forEach(b => b.onclick = () => steps[+b.dataset.i].act());
}

function renderParas() {
  $('#paras').innerHTML = M.scenes.map((s, i) => `
    <div class="para ${i === CUR ? 'on' : ''}" data-i="${i}">
      <span class="n">${i + 1}</span>
      <div class="tools"><button title="Đưa lên" onclick="moveScene(${i},-1)">↑</button><button title="Đưa xuống" onclick="moveScene(${i},1)">↓</button><button title="Nhân đôi" onclick="dupScene(${i})">⧉</button><button title="Xoá cảnh" onclick="delScene(${i})">✕</button></div>
      <textarea rows="1" aria-label="Lời đọc cảnh ${i + 1}" placeholder="Lời đọc cho cảnh này…">${esc(s.voice_text)}</textarea>
      <div class="meta"></div>
    </div>`).join('');
  $('#paras').querySelectorAll('.para').forEach(p => {
    const i = +p.dataset.i, ta = p.querySelector('textarea');
    requestAnimationFrame(() => autosize(ta));
    p.addEventListener('mousedown', e => { if (!e.target.closest('.tools')) select(i); });
    ta.addEventListener('focus', () => select(i));
    ta.addEventListener('input', () => { autosize(ta); change(m => { m.scenes[i].voice_text = ta.value; invalidate(m.scenes[i]); }, 'voice' + i); renderParaMeta(i); });
  });
  renderParasMeta();
}
function autosize(ta) { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; }
function renderParasMeta() {
  M.scenes.forEach((_, i) => renderParaMeta(i));
  const w = M.scenes.reduce((a, s) => a + (s.voice_text || '').split(/\s+/).filter(Boolean).length, 0);
  $('#scriptStats').textContent = `${w} từ, ~${Math.round(M.scenes.reduce((a, s) => a + estDur(s), 0))} giây`;
}
function renderParaMeta(i) {
  const el = document.querySelector(`.para[data-i="${i}"] .meta`); if (!el) return;
  const s = M.scenes[i], words = (s.voice_text || '').split(/\s+/).filter(Boolean).length, errs = errorsOf(i);
  el.innerHTML = `<span>${esc(tplName(s))}</span><span class="num">${s.duration ? s.duration.toFixed(1) + ' giây' : '~' + estDur(s).toFixed(1) + ' giây'}</span>${words > 22 ? '<span class="bad">dài, nên tách cảnh</span>' : ''}${errs.length ? `<span class="bad">${errs.length} lỗi</span>` : ''}`;
}
const errorsOf = i => ERR.filter(e => new RegExp(`^scenes/${i}(:|/)`).test(e)).map(e => e.replace(/^scenes\/\d+[^:]*:\s*/, ''));

function renderTimeline() {
  if (!M) return;
  const W = $('#track').clientWidth - 28, total = M.scenes.reduce((a, s) => a + estDur(s), 0) || 1;
  const pps = Math.max(18, (W - 3 * M.scenes.length) / total);
  $('#blocks').innerHTML = M.scenes.map((s, i) => {
    const k = scKey(s), th = ST.thumbs[k];
    const bg = th ? `background-image:url('/files/${PID}/preview/${k}.jpg?${th}')` : '';
    return `<div class="blk ${s.duration ? '' : 'est'} ${i === CUR ? 'on' : ''}" draggable="true" data-i="${i}" style="width:${Math.max(56, estDur(s) * pps)}px;${bg}" title="${esc((s.voice_text || '').slice(0, 140))}">
      <div class="bar" style="background:${TPL_COLOR[s.template_name] || '#8892a3'}"></div><div class="lab">${i + 1}. ${esc(tplName(s))} <span class="num">${estDur(s).toFixed(1)}s</span></div></div>`;
  }).join('');
  let ruler = '';
  const stepS = total > 120 ? 10 : 5;
  for (let x = 0; x <= total; x += stepS) ruler += `<span style="left:${14 + x * pps}px">${x}s</span>`;
  $('#ruler').innerHTML = ruler;
  const est = ST.voiced < M.scenes.length;
  $('#tlinfo').textContent = `${M.scenes.length} cảnh, ${total.toFixed(1)} giây${est ? ' (viền đứt: chưa có giọng, thời lượng ước tính)' : ''}`;
  $('#blocks').querySelectorAll('.blk').forEach(b => {
    const i = +b.dataset.i;
    b.onclick = e => { const r = b.getBoundingClientRect(); select(i); scrubTo((e.clientX - r.left) / r.width * estDur(M.scenes[i])); };
    b.ondragstart = e => { e.dataTransfer.setData('text/plain', i); b.classList.add('dragging'); };
    b.ondragend = () => b.classList.remove('dragging');
    b.ondragover = e => { e.preventDefault(); const r = b.getBoundingClientRect(), left = e.clientX < r.left + r.width / 2; b.classList.toggle('dropL', left); b.classList.toggle('dropR', !left); };
    b.ondragleave = () => b.classList.remove('dropL', 'dropR');
    b.ondrop = e => { e.preventDefault(); const from = +e.dataTransfer.getData('text/plain'), r = b.getBoundingClientRect(); let to = i + (e.clientX > r.left + r.width / 2 ? 1 : 0); if (from < to) to--; b.classList.remove('dropL', 'dropR'); if (from !== to) reorder(from, to); };
  });
  placePlayhead();
}
function placePlayhead() {
  const b = document.querySelector(`.blk[data-i="${CUR}"]`), ph = $('#playhead');
  if (!b) return (ph.hidden = true);
  const d = frameInput?.duration || estDur(sc());
  ph.hidden = false; ph.style.top = '16px';
  ph.style.left = (b.offsetLeft + 14 + Math.min(1, t / d) * b.offsetWidth) + 'px';
}

/* ================= bảng chỉnh ================= */
function renderInspector() {
  const s = sc(); if (!s) { $('#insp').innerHTML = '<p class="hint">Chọn một cảnh để chỉnh.</p>'; return; }
  const doc = s.visual_type === 'html_animation' ? META.templates[s.template_name] : null;
  const isStick = s.visual_type === 'html_animation' && s.template_name === 'stickman_stage';
  if (TAB === 'acting' && !isStick) TAB = 'content';
  const tabs = [['content', 'Nội dung'], ...(isStick ? [['acting', `Diễn xuất (${(s.acting || []).length})`]] : []), ['timing', 'Thời lượng'], ['json', 'JSON']];
  $('#insp').innerHTML = `
    <label for="iTpl" style="margin-top:0">Cảnh ${CUR + 1}: kiểu cảnh</label>
    <select id="iTpl">${s.visual_type === 'html_animation' ? '' : `<option value="">${esc(VTYPES[s.visual_type])}</option>`}
      ${Object.keys(META.templates).map(k => `<option value="${k}" ${k === s.template_name && s.visual_type === 'html_animation' ? 'selected' : ''}>${esc(TPL_NAMES[k] || k)}</option>`).join('')}</select>
    ${doc ? `<p class="desc">${esc(doc.desc)}</p>` : ''}
    <div id="ierr"></div>
    <div class="tabs" role="tablist">${tabs.map(([k, n]) => `<button class="tab ${TAB === k ? 'on' : ''}" role="tab" aria-selected="${TAB === k}" data-tab="${k}">${n}</button>`).join('')}</div>
    <div id="ipanel"></div>`;
  $('#insp').querySelectorAll('.tab').forEach(b => b.onclick = () => { TAB = b.dataset.tab; renderInspector(); });
  $('#iTpl').onchange = e => {
    const v = e.target.value; if (!v) return;
    change(m => { const x = m.scenes[CUR]; x.visual_type = 'html_animation'; x.template_name = v; x.props = Object.assign(structuredClone(META.templates[v].demo || {}), keepText(x.props)); if (v !== 'stickman_stage') delete x.acting; else x.acting = x.acting || []; });
    renderAll(); loadFrame(true);
  };
  renderErrors();
  ({ content: panelContent, acting: panelActing, timing: panelTiming, json: panelJson })[TAB](s, doc);
}
function keepText(p = {}) { const o = {}; for (const k of ['title', 'heading', 'headline', 'label']) if (p[k]) o[k] = p[k]; return o; }
function renderErrors() { const e = errorsOf(CUR), box = $('#ierr'); if (box) box.innerHTML = e.length ? `<div class="errbox">${e.map(esc).join('<br>')}</div>` : ''; }

function panelContent(s, doc) {
  const P = $('#ipanel');
  if (s.visual_type !== 'html_animation') {
    const f = { svg_graphic: ['svg_code', 'Mã SVG'], image: ['src', 'Tên file ảnh trong thư mục assets'], video: ['src', 'Tên file clip trong thư mục assets'], comfyui: ['prompt', 'Mô tả hình cần tạo'] }[s.visual_type];
    P.innerHTML = f ? `<label for="fx">${f[1]}</label><textarea rows="${f[0] === 'svg_code' ? 12 : 3}" class="${f[0] === 'svg_code' ? 'code' : ''}" id="fx">${esc(s[f[0]])}</textarea>` : '<p class="hint">Cảnh nền màu không cần nhập nội dung.</p>';
    if (f) $('#fx').oninput = e => change(m => m.scenes[CUR][f[0]] = e.target.value, 'fx');
    return;
  }
  const props = s.props || {}, demo = doc?.demo || {};
  P.innerHTML = Object.entries(doc?.props || {}).map(([k, d]) => fieldHtml(k, d, props[k], demo[k])).join('') || '<p class="hint">Kiểu cảnh này không có tham số.</p>';
  P.querySelectorAll('[data-prop]').forEach(el => el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
    const k = el.dataset.prop, kind = el.dataset.kind; let v = el.value;
    if (kind === 'number') v = v === '' ? undefined : +v;
    if (kind === 'list') v = v.split('\n').map(x => x.trim()).filter(Boolean);
    if (kind === 'json') { try { v = v.trim() ? JSON.parse(v) : undefined; el.style.borderColor = ''; } catch { el.style.borderColor = 'var(--err)'; return; } }
    if (v === '' || (Array.isArray(v) && !v.length)) v = undefined;
    change(m => { const p = m.scenes[CUR].props = m.scenes[CUR].props || {}; if (v === undefined) delete p[k]; else p[k] = v; }, 'p' + k);
  }));
}
function fieldHtml(k, desc, val, demo) {
  const sample = val !== undefined ? val : demo;
  const en = String(desc).match(/^([\w]+(?:\|[\w]+)+)/);
  const help = esc(String(desc).replace(/^([\w]+(?:\|[\w]+)+)\s*[–-]?\s*/, ''));
  const lab = `<label for="f_${k}">${esc(PROP_LABEL[k] || k)}</label>${help ? `<div class="hint" style="margin:-2px 0 5px">${help}</div>` : ''}`;
  if (en) return lab + `<select id="f_${k}" data-prop="${k}"><option value="">(mặc định)</option>${en[1].split('|').map(o => `<option ${o === val ? 'selected' : ''}>${o}</option>`).join('')}</select>`;
  if (typeof sample === 'number') return lab + `<input id="f_${k}" type="number" data-prop="${k}" data-kind="number" value="${val ?? ''}" placeholder="${demo ?? ''}">`;
  if (Array.isArray(sample) && sample.every(x => typeof x === 'string')) return lab + `<textarea id="f_${k}" rows="${Math.max(3, (val || []).length + 1)}" data-prop="${k}" data-kind="list" placeholder="Mỗi dòng một mục">${esc((val || []).join('\n'))}</textarea>`;
  if (sample && typeof sample === 'object') return lab + `<textarea id="f_${k}" class="code" rows="5" data-prop="${k}" data-kind="json" placeholder='${esc(JSON.stringify(demo))}'>${val !== undefined ? esc(JSON.stringify(val, null, 1)) : ''}</textarea>`;
  const long = /quote|ticker/.test(k);
  return lab + (long ? `<textarea id="f_${k}" rows="3" data-prop="${k}">${esc(val)}</textarea>` : `<input id="f_${k}" data-prop="${k}" value="${esc(val)}" placeholder="${esc(typeof demo === 'string' ? demo : '')}">`);
}

function panelActing(s) {
  const cast = Object.keys(M.cast || { hero: {} });
  const words = (s.voice_text || '').split(/\s+/).map(w => w.replace(/[^\p{L}\p{N}]/gu, '')).filter(Boolean);
  const opt = (list, v, empty) => (empty ? `<option value="">${empty}</option>` : '') + list.map(([k, n]) => `<option value="${esc(k)}" ${k === v ? 'selected' : ''}>${esc(n)}</option>`).join('');
  const acts = Object.entries(META.actions).map(([k, l]) => [k, l]), pair = x => [x, x];
  $('#ipanel').innerHTML = `<p class="hint">Mỗi nhịp: ai làm gì, bắt đầu khi đọc tới từ nào. Nhân vật tự đi bộ khi đổi vị trí.</p>
    <datalist id="dlw">${[...new Set(words)].map(w => `<option value="${esc(w)}">`).join('')}<option value="50%"></datalist>
    ${(s.acting || []).map((b, j) => `<div class="beat" data-j="${j}">
      <button class="x" data-del="${j}" title="Xoá nhịp">✕</button>
      <div><small>Ai</small><select data-b="who">${opt(cast.map(pair), b.who)}</select></div>
      <div><small>Khi đọc tới</small><input data-b="at" list="dlw" value="${esc(b.at ?? '')}" placeholder="từ, 50% hoặc giây"></div>
      <div><small>Hành động</small><select data-b="act">${opt(acts, b.act)}</select></div>
      <div><small>Di chuyển</small><select data-b="move">${opt(META.moves.map(x => [x, MOVE_VI[x] || x]), b.move, '—')}</select></div>
      <div><small>Cảm xúc</small><select data-b="mood">${opt(META.moods.map(x => [x, MOOD_VI[x] || x]), b.mood, '—')}</select></div>
      <div><small>Cầm</small><select data-b="hold">${opt(META.holds.map(x => [x, HOLD_VI[x] || x]), b.hold, '—')}</select></div>
      <div><small>Biểu tượng</small><select data-b="emote">${opt((META.emotes || []).map(pair), b.emote, '—')}</select></div>
      <div style="grid-column: span 2"><small>Thoại trong bong bóng (tối đa 4 từ)</small><input data-b="say" value="${esc(b.say ?? '')}"></div>
    </div>`).join('')}
    <button id="addBeat">Thêm nhịp diễn</button>`;
  $('#addBeat').onclick = addBeat;
  $('#ipanel').querySelectorAll('[data-del]').forEach(b => b.onclick = () => delBeat(+b.dataset.del));
  $('#ipanel').querySelectorAll('[data-b]').forEach(el => el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
    const j = +el.closest('.beat').dataset.j, k = el.dataset.b; let v = el.value;
    if (k === 'at' && /^\d+(\.\d+)?$/.test(v)) v = +v;
    change(m => { const b = m.scenes[CUR].acting[j]; if (v === '') delete b[k]; else b[k] = v; }, 'b' + j + k);
  }));
}
function addBeat() { change(m => { const s = m.scenes[CUR]; s.acting = s.acting || []; const last = s.acting[s.acting.length - 1]; s.acting.push({ who: last?.who || Object.keys(m.cast || { hero: 1 })[0], at: '50%', act: 'talk' }); }); renderInspector(); }
function delBeat(j) { change(m => m.scenes[CUR].acting.splice(j, 1)); renderInspector(); }

function panelTiming(s) {
  const CAM = { none: 'Đứng yên', zoom_in: 'Đẩy vào', zoom_out: 'Kéo ra', pan_left: 'Lia trái', pan_right: 'Lia phải' };
  $('#ipanel').innerHTML = `
    <div class="row"><div><label for="tpause">Nghỉ thêm cuối cảnh (giây)</label><input id="tpause" type="number" step="0.25" min="0" value="${s.pause ?? ''}" placeholder="0"></div>
    <div><label for="tmin">Dài tối thiểu (giây)</label><input id="tmin" type="number" step="0.5" min="0" value="${s.min_duration ?? ''}" placeholder="theo lời đọc"></div></div>
    <label for="tcam">Chuyển động máy quay</label>
    <select id="tcam">${Object.entries(CAM).map(([c, n]) => `<option value="${c}" ${c === (s.camera || 'none') ? 'selected' : ''}>${n}</option>`).join('')}</select>
    <label class="check"><input type="checkbox" id="tcap" ${s.captions === false ? '' : 'checked'}> Hiện phụ đề ở cảnh này</label>
    <label for="tvt">Nguồn hình</label>
    <select id="tvt">${Object.entries(VTYPES).map(([v, n]) => `<option value="${v}" ${v === s.visual_type ? 'selected' : ''}>${n}</option>`).join('')}</select>
    <p class="hint">${s.duration ? `Thời lượng đo được: ${s.duration.toFixed(2)} giây.` : 'Thời lượng thật được đo sau khi tạo giọng đọc.'}</p>`;
  const num = (id, key) => $(id).oninput = e => change(m => { const v = e.target.value; if (v === '') delete m.scenes[CUR][key]; else m.scenes[CUR][key] = +v; delete m.scenes[CUR].duration; }, key);
  num('#tpause', 'pause'); num('#tmin', 'min_duration');
  $('#tcam').onchange = e => change(m => { if (e.target.value === 'none') delete m.scenes[CUR].camera; else m.scenes[CUR].camera = e.target.value; });
  $('#tcap').onchange = e => change(m => { if (e.target.checked) delete m.scenes[CUR].captions; else m.scenes[CUR].captions = false; });
  $('#tvt').onchange = e => { change(m => { m.scenes[CUR].visual_type = e.target.value; }); renderAll(); loadFrame(true); };
}

function panelJson(s) {
  const clean = Object.fromEntries(Object.entries(s).filter(([k]) => !ENGINE.includes(k)));
  $('#ipanel').innerHTML = `<p class="hint">Sửa trực tiếp cảnh này. Phần thời gian do máy tạo không hiện ở đây.</p><textarea id="jx" class="code" rows="22">${esc(JSON.stringify(clean, null, 2))}</textarea><div class="row" style="margin-top:8px"><span class="hint" id="jmsg"></span><button class="pri" style="flex:none" onclick="applyJson()">Áp dụng</button></div>`;
}
function applyJson() {
  try {
    const o = JSON.parse($('#jx').value);
    change(m => { const old = m.scenes[CUR], keep = o.voice_text === old.voice_text ? Object.fromEntries(ENGINE.filter(k => old[k] !== undefined).map(k => [k, old[k]])) : {}; m.scenes[CUR] = Object.assign(keep, o); });
    renderAll(); loadFrame(true); toast('Đã áp dụng');
  } catch (e) { $('#jmsg').textContent = 'JSON lỗi: ' + e.message; }
}

/* ================= cảnh ================= */
function select(i) {
  if (!M || i < 0 || i >= M.scenes.length) return;
  const changed = i !== CUR; CUR = i;
  document.querySelectorAll('.para').forEach(p => p.classList.toggle('on', +p.dataset.i === i));
  document.querySelectorAll('.blk').forEach(b => b.classList.toggle('on', +b.dataset.i === i));
  if (changed) { stopAudio(); t = 0; renderInspector(); loadFrame(); }
  document.querySelector(`.para[data-i="${i}"]`)?.scrollIntoView({ block: 'nearest' });
  document.querySelector(`.blk[data-i="${i}"]`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  updateTransport();
}
function go(d) { const was = playing; pause(); select(Math.max(0, Math.min(M.scenes.length - 1, CUR + d))); if (was) play(); }
function nextId() { return Math.max(0, ...M.scenes.map(s => +s.scene_id || 0)) + 1; }
function addScene() {
  const k = $('#addTpl').value, at = CUR + 1;
  change(m => m.scenes.splice(at, 0, { scene_id: nextId(), visual_type: 'html_animation', template_name: k, voice_text: '', props: structuredClone(META.templates[k].demo || {}), ...(k === 'stickman_stage' ? { acting: [] } : {}) }));
  CUR = -1; renderAll(); select(at); document.querySelector(`.para[data-i="${at}"] textarea`)?.focus();
}
function dupScene(i) { change(m => { const c = structuredClone(m.scenes[i]); c.scene_id = nextId(); m.scenes.splice(i + 1, 0, c); }); CUR = -1; renderAll(); select(i + 1); }
function delScene(i) { if (M.scenes.length < 2) return toast('Video cần ít nhất một cảnh', true); change(m => m.scenes.splice(i, 1)); CUR = -1; renderAll(); select(Math.min(i, M.scenes.length - 1)); toast('Đã xoá cảnh. Ctrl+Z để hoàn tác'); }
function moveScene(i, d) { const j = i + d; if (j >= 0 && j < M.scenes.length) reorder(i, j); }
function reorder(from, to) { const keep = CUR === from ? to : CUR; change(m => { const [x] = m.scenes.splice(from, 1); m.scenes.splice(to, 0, x); }); CUR = -1; renderAll(); select(keep); }

/* ================= màn xem & phát ================= */
function fitFrame() {
  if (!M) return;
  const st = $('#stage'), [aw, ah] = (M.aspect_ratio || '9:16').split(':').map(Number);
  const s = Math.min((st.clientWidth - 36) / aw, (st.clientHeight - 36) / ah);
  $('#frame').style.width = Math.floor(aw * s) + 'px'; $('#frame').style.height = Math.floor(ah * s) + 'px';
}
let loadSeq = 0;
async function loadFrame(force) {
  const s = sc(); if (!s) return;
  const seq = ++loadSeq;
  if (force || /Đang sửa/.test($('#savestate').textContent)) await save();
  const r = await api(`/api/p/${PID}/scene/${s.scene_id}`);
  if (seq !== loadSeq || r.error) return;
  frameInput = r.input; fitFrame();
  const f = $('#frame'); f.hidden = false;
  $('#scrub').max = r.input.duration;
  if (!r.template) { frameTpl = null; f.srcdoc = `<body style="margin:0;height:100vh;display:grid;place-items:center;background:#111;color:#aaa;font:15px sans-serif;text-align:center;padding:20px">${esc(tplName(s))}<br>${esc(s.src || s.prompt || '')}<br><small>Xem bằng ảnh xem trước hoặc bản nháp</small></body>`; updateTransport(); return; }
  if (frameTpl === r.template && f.contentWindow) { f.contentWindow.postMessage({ type: 'vf-input', input: r.input }, '*'); seekFrame(); }
  else { frameTpl = r.template; f.removeAttribute('srcdoc'); f.onload = () => { f.contentWindow.postMessage({ type: 'vf-input', input: frameInput }, '*'); seekFrame(); }; f.src = `/tpl/${r.template}.html?studio=1`; }
  updateTransport();
}
function seekFrame() { $('#frame').contentWindow?.postMessage({ type: 'vf-seek', t }, '*'); updateTransport(); }
function scrubTo(v) { t = Math.max(0, v); if (playing) { clock0 = performance.now() - t * 1000; const au = $('#au'); if (!au.paused) au.currentTime = t; } seekFrame(); }
function updateTransport() {
  if (!sc()) return;
  const d = frameInput?.duration || estDur(sc());
  $('#scrub').value = t; $('#tc').textContent = `${t.toFixed(1)} / ${d.toFixed(1)} giây`;
  $('#btnPlay').textContent = playing ? '⏸' : '▶';
  $('#novoice').textContent = ST.audio[scKey(sc())] ? '' : 'Cảnh này chưa có giọng đọc nên thời lượng đang là ước tính. Bấm bước "Giọng đọc" ở thanh trên để nghe thử.';
  placePlayhead();
}
function togglePlay() { playing ? pause() : play(); }
function play() {
  if (!sc()) return;
  const d = () => frameInput?.duration || estDur(sc());
  if (t >= d() - 0.05) t = 0;
  playing = true; clock0 = performance.now() - t * 1000;
  const a = ST.audio[scKey(sc())], au = $('#au');
  if (a && !muted) { au.src = a + '?' + ST.mtime; au.currentTime = t; au.play().catch(() => {}); }
  cancelAnimationFrame(raf);
  const tick = () => {
    if (!playing) return;
    t = (performance.now() - clock0) / 1000;
    if (t >= d()) {
      if (auto && CUR < M.scenes.length - 1) { stopAudio(); playing = false; select(CUR + 1); setTimeout(play, 200); return; }
      t = d(); pause(); seekFrame(); return;
    }
    seekFrame(); raf = requestAnimationFrame(tick);
  };
  tick();
}
function pause() { playing = false; cancelAnimationFrame(raf); stopAudio(); updateTransport(); }
function stopAudio() { $('#au').pause(); }
function toggleAuto() { auto = !auto; $('#btnAuto').classList.toggle('on', auto); }
function toggleMute() { muted = !muted; $('#btnMute').textContent = muted ? 'Tắt tiếng' : 'Có tiếng'; $('#btnMute').classList.toggle('on', !muted); if (muted) stopAudio(); }

/* ================= chạy engine ================= */
const STEP_NAME = { voice: 'Tạo giọng đọc', preview: 'Tạo ảnh xem trước', draft: 'Xuất bản nháp', all: 'Xuất video', new: 'Viết kịch bản', translate: 'Dịch', auto: 'Tự động' };
async function run(step, extra = {}) {
  if (job && !job.done) return toast('Đang chạy một việc khác, đợi xong đã', true);
  if (ERR.length && step !== 'preview') return toast('Kịch bản còn lỗi: ' + ERR[0], true);
  pause(); await save();
  const r = await api(`/api/p/${PID}/run`, { method: 'POST', body: { step, ...extra } });
  startJob(r.job, step);
}
function startJob(id, step, onDone) {
  job = { id, step, done: false, onDone };
  for (const b of ['#btnDraft', '#btnRender']) $(b).disabled = true;
  $('#logTitle').textContent = STEP_NAME[step] || step; $('#log').textContent = '';
  $('#progress').style.width = '4%';
  poll();
}
async function poll() {
  const j = await api('/api/jobs/' + job.id);
  $('#log').textContent = j.log; $('#log').scrollTop = 1e9;
  const pct = progressOf(job.step, j.log);
  $('#progress').style.width = Math.max(4, pct) + '%';
  $('#savestate').textContent = `${STEP_NAME[job.step]}… ${Math.round(pct)}%`;
  if (!j.done) return setTimeout(poll, 600);
  job.done = true;
  for (const b of ['#btnDraft', '#btnRender']) $(b).disabled = false;
  setTimeout(() => $('#progress').style.width = '0', 600);
  const ok = j.code === 0;
  $('#savestate').textContent = ok ? `${STEP_NAME[job.step]}: xong` : `${STEP_NAME[job.step]}: lỗi`;
  if (!ok) { toast(lastError(j.log), true); $('#logbox').hidden = false; }
  else toast(`${STEP_NAME[job.step]}: xong`);
  if (job.onDone) return job.onDone(j);
  await refreshStatus();
  if (ok && (job.step === 'all' || job.step === 'draft')) showOutput(job.step === 'draft' ? PID + '_draft.mp4' : PID + '.mp4');
}
function progressOf(step, log) {
  if (step === 'auto') return /📄 Báo cáo/.test(log) ? 100 : (log.match(/✅/g) || []).length ? 70 : 35;
  if (/✅|🖼|✔ Project/.test(log)) return 100;
  const n = M?.scenes.length || 1, voiced = (log.match(/🎙/g) || []).length;
  const clips = (log.match(/ ✔ (clip|draft):/g) || []).length, todo = +((log.match(/Quay (\d+)\//) || [])[1] ?? 0);
  if (step === 'voice') return voiced / n * 100;
  if (step === 'preview' || step === 'new' || step === 'translate' || step === 'auto') return /✅/.test(log) ? 70 : 45;
  const v = step === 'all' ? (/Giọng đọc xong/.test(log) ? 20 : voiced / n * 20) : 0;
  const q = todo ? clips / todo * (step === 'all' ? 70 : 90) : (/Quay 0\//.test(log) ? (step === 'all' ? 70 : 90) : 0);
  return v + q;
}
function lastError(log) { const l = log.trim().split('\n').filter(x => /✘|Error|lỗi/i.test(x)); return (l[l.length - 1] || 'Có lỗi, mở Nhật ký để xem chi tiết').replace(/^✘\s*/, '').slice(0, 220); }
function toggleLog() { $('#logbox').hidden = !$('#logbox').hidden; }
function showOutput(name) {
  const ts = ST.videos?.[name] || Date.now();
  $('#outTitle').textContent = name.includes('_draft') ? 'Bản nháp (nửa độ phân giải)' : 'Video đã xuất';
  $('#outVideo').src = `/files/${PID}/out/${name}?${ts}`; $('#outDl').href = `/files/${PID}/out/${name}`;
  $('#outPath').textContent = `Lưu tại workspace/${PID}/out/${name}, kèm phụ đề .srt cùng tên.`;
  dlgOut.showModal();
}

/* ================= tạo video ================= */
function swatches(el, current, onPick, withAuto) {
  const items = (withAuto ? [['', { label: 'Để AI chọn theo chủ đề', bg: '#ffffff', ink: '#687284', accent: ['#d5dae3'] }]] : []).concat(Object.entries(META.styles));
  el.innerHTML = items.map(([k, s]) => `<button class="sw ${k === current ? 'on' : ''}" data-k="${k}" title="${esc(s.label)}"><div class="pv" style="background:${s.bg};color:${s.ink}"><b>${k ? 'Aa' : '?'}</b>${(s.accent || []).map(c => `<i style="background:${c}"></i>`).join('')}</div><span>${esc(k ? k.replace(/_/g, ' ') : 'Tự chọn')}</span></button>`).join('');
  el.querySelectorAll('.sw').forEach(b => b.onclick = () => { el.querySelectorAll('.sw').forEach(x => x.classList.toggle('on', x === b)); onPick(b.dataset.k); });
}
function seg(el, options, current, onPick) {
  el.innerHTML = Object.entries(options).map(([k, n]) => `<button class="${k === current ? 'on' : ''}" data-k="${k}">${esc(n)}</button>`).join('');
  el.querySelectorAll('button').forEach(b => b.onclick = () => { el.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); onPick(b.dataset.k); });
}
/* ================= cài đặt video ================= */
function openSettings() {
  swatches($('#sstyle'), M.style || 'classic_light', k => { change(m => m.style = k); loadFrame(true); });
  seg($('#saspect'), { '9:16': 'Dọc 9:16', '16:9': 'Ngang 16:9', '1:1': 'Vuông' }, M.aspect_ratio || '9:16', k => { change(m => m.aspect_ratio = k); frameTpl = null; loadFrame(true); });
  $('#slang').innerHTML = langOptions(M.lang || 'vi');
  const fillVoices = () => { const L = META.languages[$('#slang').value] || { voices: {} }; $('#svoice').innerHTML = '<option value="">Mặc định</option>' + Object.entries(L.voices).map(([k, n]) => `<option value="${k}" ${k === M.voice ? 'selected' : ''}>${esc(n)}</option>`).join(''); };
  fillVoices();
  $('#slang').onchange = () => { change(m => { m.lang = $('#slang').value; delete m.voice; m.scenes.forEach(invalidate); }); fillVoices(); toast('Đổi ngôn ngữ giọng đọc: nhớ sửa lời đọc sang ngôn ngữ mới, hoặc dùng "Tạo bản dịch"'); };
  $('#svoice').onchange = () => change(m => { if ($('#svoice').value) m.voice = $('#svoice').value; else delete m.voice; m.scenes.forEach(invalidate); });
  $('#smusic').value = M.music || '';
  langChecks($('#trlangs'), M.lang || 'vi');
  renderCast(); dlgSettings.showModal();
}
function renderCast() {
  const presets = Object.keys(META.characters);
  const color = c => /^#[0-9a-f]{6}$/i.test(c.shirt || '') ? c.shirt : (/^#/.test(META.characters[c.preset]?.shirt || '') ? META.characters[c.preset].shirt : '#7fb3d5');
  $('#castlist').innerHTML = Object.entries(M.cast || {}).map(([name, c]) => `<div class="cast" data-n="${esc(name)}">
    <input value="${esc(name)}" data-c="name" aria-label="Tên nhân vật">
    <select data-c="preset" aria-label="Mẫu nhân vật"><optgroup label="Người que">${presets.map(p => `<option ${!c.model3d && p === c.preset ? 'selected' : ''}>${p}</option>`).join('')}</optgroup>
      ${(META.char3d || []).length ? `<optgroup label="Nhân vật 3D (Blender)">${META.char3d.map(x => `<option value="3d:${esc(x.id)}" ${c.model3d === x.id ? 'selected' : ''} ${x.sets.length ? '' : 'disabled'}>🧍 ${esc(x.name)}${x.sets.length ? '' : ' (chưa render)'}</option>`).join('')}</optgroup>` : ''}</select>
    <input type="color" data-c="shirt" value="${color(c)}" title="Màu áo">
    <button class="icon" data-c="del" title="Xoá nhân vật">✕</button></div>`).join('') || '<p class="hint">Chưa có nhân vật. Cảnh người que sẽ dùng nhân vật mặc định.</p>';
  $('#castlist').querySelectorAll('.cast').forEach(row => {
    const name = row.dataset.n;
    row.querySelector('[data-c=name]').onchange = e => { const nn = e.target.value.trim(); if (!nn || nn === name || M.cast[nn]) return; change(m => { m.cast[nn] = m.cast[name]; delete m.cast[name]; m.scenes.forEach(s => (s.acting || []).forEach(b => { if (b.who === name) b.who = nn; })); }); renderCast(); renderInspector(); };
    row.querySelector('[data-c=preset]').onchange = e => {
      const v = e.target.value;
      change(m => { if (v.startsWith('3d:')) m.cast[name].model3d = v.slice(3); else { delete m.cast[name].model3d; m.cast[name].preset = v; } });
      loadFrame(true);
    };
    row.querySelector('[data-c=shirt]').oninput = e => change(m => m.cast[name].shirt = e.target.value, 'shirt' + name);
    row.querySelector('[data-c=shirt]').onchange = () => loadFrame(true);
    row.querySelector('[data-c=del]').onclick = () => { change(m => delete m.cast[name]); renderCast(); };
  });
}
function addCast() { change(m => { m.cast = m.cast || {}; let k = 1; while (m.cast['Nv' + k]) k++; m.cast['Nv' + k] = { preset: 'cozy' }; }); renderCast(); }
async function translateTo() {
  const to = [...document.querySelectorAll('#trlangs input:checked')].map(x => x.value).join(',');
  if (!to) return toast('Chọn ít nhất một ngôn ngữ', true);
  if (META.brain.backend === 'manual') { dlgSettings.close(); return openBrain(); }
  dlgSettings.close(); await save();
  const r = await api(`/api/p/${PID}/translate`, { method: 'POST', body: { to, render: $('#trrender').checked } });
  startJob(r.job, 'translate', j => j.code === 0 && toast('Đã tạo bản dịch. Mở trong "Video của tôi"'));
}

/* ================= phím tắt, thông báo ================= */
function bindKeys() {
  document.addEventListener('keydown', e => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || document.querySelector('dialog[open]');
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return; }
    if (mod && e.key === 'Enter' && M) { e.preventDefault(); run('draft'); return; }
    if (mod && e.key.toLowerCase() === 'z' && !typing && M) { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
    if (typing || !M) return;
    if (e.key === ' ') { e.preventDefault(); togglePlay(); }
    else if (e.key === 'ArrowLeft') go(-1);
    else if (e.key === 'ArrowRight') go(1);
    else if (e.key === 'Delete') delScene(CUR);
  });
  window.addEventListener('beforeunload', e => { if (/Đang sửa|Đang lưu/.test($('#savestate').textContent)) { save(); e.preventDefault(); } });
  bindDialogs();
}
/* Chặn lỗi "dialog không tắt được": click ra ngoài khung (vào phần nền mờ) để đóng,
 * và luôn dừng/xoá video khi đóng dialog xem video (kể cả khi đang ở chế độ toàn màn hình). */
function bindDialogs() {
  document.querySelectorAll('dialog').forEach(d => d.addEventListener('click', e => { if (e.target === d) d.close(); }));
  dlgOut.addEventListener('close', () => { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); outVideo.pause(); outVideo.removeAttribute('src'); outVideo.load(); });
}
let toastT;
function toast(msg, err) { const el = $('#toast'); el.textContent = msg; el.className = err ? 'err' : ''; el.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => el.hidden = true, err ? 6000 : 2600); }


