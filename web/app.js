/* AI Workflow Studio – điều hướng và các trang (dùng chung $, esc, api, toast, META… với editor.js). */
const PAGES = ['home', 'library', 'cinema', 'trends', 'write', 'narration', 'gpu', 'editor', 'render', 'char3d', 'tools', 'settings'];
const BRAIN_NAME = { api: 'API key', cli: 'Claude Code (gói Claude)', manual: 'chưa kết nối' };
const ASPECT_NAME = { '16:9': 'Ngang 16:9', '9:16': 'Dọc 9:16', '1:1': 'Vuông 1:1', '4:5': 'Dọc 4:5' };
const PLATFORM_HINT = { '16:9': 'Ngang 16:9: hợp với YouTube, Facebook, LinkedIn.', '9:16': 'Dọc 9:16: hợp với YouTube Shorts, TikTok, Instagram Reels.', '1:1': 'Vuông 1:1: hợp với Instagram feed, Facebook.', '4:5': 'Dọc 4:5: hợp với Instagram feed, Facebook.' };
const langOptions = (cur, withEmpty) => (withEmpty ? `<option value="">${withEmpty}</option>` : '') + Object.entries(META.languages).map(([k, v]) => `<option value="${k}" ${k === cur ? 'selected' : ''}>${esc(v.name)}</option>`).join('');
const langChecks = (el, skip) => { el.innerHTML = Object.entries(META.languages).filter(([k]) => k !== skip).map(([k, v]) => `<label><input type="checkbox" value="${k}">${esc(v.name)}</label>`).join(''); };
const openNew = () => go('write');
const openProjects = () => go('library');
const openBrain = () => go('settings');
let SERIES = [], PLAN = [], RESEARCH = null, WRITE = {}, CURPAGE = null;

/* ---------------- điều hướng ---------------- */
function go(page, arg) {
  location.hash = '#/' + page + (arg ? '/' + encodeURIComponent(arg) : '');
}
async function route() {
  const [, page = 'home', arg] = location.hash.split('/');
  const p = PAGES.includes(page) ? page : 'home';
  document.querySelectorAll('.nav').forEach(n => n.classList.toggle('on', n.dataset.pg === p));
  document.querySelectorAll('.page').forEach(s => s.classList.toggle('on', s.id === 'pg-' + p));
  if (p !== 'editor' && typeof pause === 'function') pause();
  CURPAGE = p;
  const arg2 = arg ? decodeURIComponent(arg) : '';
  if (p === 'editor') {
    const id = arg2 || localStorage.getItem('vf.pid');
    if (id && id !== PID) await openProject(id).catch(() => toast('Không mở được video ' + id, true));
    else if (!id) { $('#stagemsg').hidden = false; }
    setTimeout(() => { fitFrame && fitFrame(); M && renderTimeline(); }, 50);
    return;
  }
  await ({ home: pgHome, library: pgLibrary, trends: pgTrends, write: pgWrite, narration: pgNarration, gpu: pgGpu, render: pgRender, char3d: pgChar3d, cinema: pgCinema, tools: pgTools, settings: pgSettings })[p](arg2);
}
window.addEventListener('hashchange', route);
document.querySelectorAll('.nav').forEach(n => n.onclick = () => go(n.dataset.pg));

async function appBoot() {
  META = await api('/api/meta');
  $('#addTpl').innerHTML = Object.keys(META.templates).map(k => `<option value="${k}">${esc(TPL_NAMES[k] || k)}</option>`).join('');
  bindKeys();
  new ResizeObserver(() => CURPAGE === 'editor' && fitFrame()).observe($('#stage'));
  new ResizeObserver(() => CURPAGE === 'editor' && M && renderTimeline()).observe($('#track'));
  renderAiChip();
  const s = await api('/api/settings');
  $('#rootpath').textContent = '📁 ' + (s.root || '');
  SERIES = (await api('/api/library')).series.map(x => x.name).filter(Boolean);
  route();
}
function renderAiChip() {
  const b = META.brain, c = $('#aichip');
  c.textContent = 'AI: ' + BRAIN_NAME[b.backend];
  c.className = 'aichip ' + (b.backend === 'manual' ? 'no' : 'ok');
}
const page = id => $('#pg-' + id);
const html = (el, s) => { el.innerHTML = s; return el; };
function chipsHtml(items, selected, attr = 'k') { return items.map(([k, n]) => `<button class="chip2 ${selected.includes(k) ? 'on' : ''}" data-${attr}="${esc(k)}">${esc(n)}</button>`).join(''); }
function bindChips(root, sel, getSel, max, onChange) {
  root.querySelectorAll(sel).forEach(b => b.onclick = () => {
    const k = Object.values(b.dataset)[0], cur = getSel();
    const i = cur.indexOf(k);
    if (i >= 0) cur.splice(i, 1); else { if (max && cur.length >= max) return toast(`Chọn tối đa ${max}`, true); cur.push(k); }
    b.classList.toggle('on', cur.includes(k)); onChange && onChange();
  });
}
function segHtml(opts, cur, id) { return `<div class="segm" id="${id}">` + opts.map(o => `<button data-v="${o}" class="${o === cur ? 'on' : ''}">${o}</button>`).join('') + '</div>'; }
function bindSeg(id, set) { $('#' + id).querySelectorAll('button').forEach(b => b.onclick = () => { $('#' + id).querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); set(b.dataset.v); }); }

/* chạy job nền và theo dõi; el = chỗ hiện trạng thái */
function watch(jobId, el, label, onDone) {
  const tick = async () => {
    const j = await api('/api/jobs/' + jobId);
    if (el) el.innerHTML = j.done ? '' : `<span class="spin"></span>${esc(label)}${j.log ? ' · ' + esc(j.log.trim().split('\n').pop().slice(0, 90)) : ''}`;
    if (!j.done) return setTimeout(tick, 900);
    if (j.code !== 0) { if (el) el.innerHTML = `<span style="color:var(--err)">✘ ${esc((j.log || 'Lỗi').trim().split('\n').pop().replace(/^✘\s*/, ''))}</span>`; toast(label + ': lỗi', true); }
    onDone && onDone(j);
  };
  tick();
}

/* ================= ĐIỆN ẢNH (pipeline repo Skills: storyboard + anim_kit + render.py) ================= */
let CINE = { seconds: 60, aspect: '16:9' };
async function pgCinema() {
  const st = await api('/api/cinema');
  const cli = META.brain.backend === 'cli';
  const secs = [[20, '20 giây (thử)'], [30, '30 giây'], [60, '1 phút (Shorts)'], [90, '1,5 phút'], [180, '3 phút'], [480, '8 phút'], [600, '10 phút']];
  const doc = { 'storyboard.md': '📋 Storyboard', 'audit.md': '🛡 Kiểm duyệt', 'package.md': '🚀 SEO', 'qa-report.md': '✅ QA' };
  const card = p => `<div class="cine" data-slug="${esc(p.slug)}">
      <div class="cinehead"><div style="min-width:0"><div class="t">${esc(p.title)}</div>
        <div class="small muted">${esc(p.slug)} · ${p.shots} shot${p.seconds ? ' · ' + p.seconds + 's' : ''}${p.profile ? ' · ' + esc(p.profile) : ''}</div></div>
        <button class="xbtn" data-cdel="${esc(p.slug)}" title="Chuyển vào thùng rác">🗑</button></div>
      ${p.videos.length ? `<video class="outv" controls src="/files/_cinema/${esc(p.slug)}/out/${esc(p.videos.find(v => !/preview/.test(v)) || p.videos[0])}?${p.mtime}"></video>` : ''}
      ${p.stills.length ? `<div class="stills">${p.stills.filter((_, i) => i % 2 === 0).slice(0, 8).map(f => `<a href="/files/_cinema/${esc(p.slug)}/out/${esc(f)}?${p.mtime}" target="_blank"><img src="/files/_cinema/${esc(p.slug)}/out/${esc(f)}?${p.mtime}" loading="lazy"></a>`).join('')}</div>` : ''}
      ${Object.keys(p.qa).length ? `<div class="bs" style="margin:8px 0">${p.qa.duration_s != null ? `<span class="badge">${p.qa.duration_s}s</span>` : ''}${p.qa.wpm_while_speaking ? `<span class="badge">${Math.round(p.qa.wpm_while_speaking)} từ/phút</span>` : ''}${p.qa.integrated_lufs != null ? `<span class="badge">${p.qa.integrated_lufs} LUFS</span>` : ''}${p.qa.missing_assets ? `<span class="badge err">thiếu ${p.qa.missing_assets} asset</span>` : ''}${p.qa.size_mb ? `<span class="badge">${p.qa.size_mb} MB</span>` : ''}</div>` : ''}
      <div class="ac">
        ${p.has_storyboard ? `<button class="btn2" data-crun="stills">🖼 Ảnh xem thử</button><button class="btn2" data-crun="preview">⚡ Dựng nhanh</button><button class="btn2 pri" data-crun="render">🎬 Dựng video</button>` : '<span class="small muted">Chưa có storyboard</span>'}
        ${Object.entries(doc).filter(([f]) => p.files[f]).map(([f, n]) => `<button class="btn2" data-cdoc="${f}">${n}</button>`).join('')}
        ${p.videos.map(v => `<a class="btn2" href="/files/_cinema/${esc(p.slug)}/out/${esc(v)}" download>⬇ ${esc(v)}</a>`).join('')}
        <span class="st small muted" data-cst></span></div></div>`;
  html(page('cinema'), `<div class="wrap">
    <div class="ph" style="display:block"><h1>🎬 Điện ảnh</h1><p class="muted" style="margin:6px 0 0">Chạy nguyên bộ skill của repo Skills: Claude lên ý tưởng, dàn ý, storyboard, <b>viết code từng cảnh</b> (hạt, chiều sâu, ánh sáng, nhân vật 3D), kiểm duyệt chính sách, SEO; máy bạn dựng hình + nhạc + hiệu ứng âm thanh. Giọng đọc dùng edge-tts của AI Workflow.</p></div>
    ${st.ready ? '' : `<div class="card"><div class="cap">Cài đặt (1 lần)</div><p class="small">Cần thư viện dựng hình skia-python, numpy, opencv (~100 MB) ${st.ffprobe ? '' : 'và <b>ffmpeg bản đầy đủ có ffprobe</b> trong PATH'}.</p>
      <div class="row"><button class="btn2 pri" id="cnsetup">⬇ Cài thư viện dựng hình</button><span class="st small muted" id="cnsetupst"></span></div></div>`}
    <div class="card"><div class="cap">Video mới</div>
      ${cli ? '' : '<p class="small" style="color:var(--err)">Chế độ này cần AI là <b>Claude Code</b> (Cài đặt → AI) vì Claude phải tự viết và chạy code cảnh.</p>'}
      <label style="margin-top:0">Chủ đề</label><input id="cntopic" placeholder="vd: Chuyện gì xảy ra nếu bạn bé bằng con kiến?" value="${esc(CINE.topic || '')}">
      <div class="row" style="align-items:flex-end;margin-top:8px">
        <div><label style="margin-top:0">Thời lượng</label><select id="cnsec">${secs.map(([v, n]) => `<option value="${v}" ${v === CINE.seconds ? 'selected' : ''}>${n}</option>`).join('')}</select></div>
        <div style="flex:none"><label style="margin-top:0">Khung hình</label>${segHtml(['16:9', '9:16'], CINE.aspect, 'cnasp')}</div>
        <div><label style="margin-top:0">Ngôn ngữ</label><select id="cnlang">${langOptions(CINE.lang || 'vi')}</select></div>
        <div><label style="margin-top:0">Nhân vật 3D</label><select id="cnchar"><option value="">Không (nhân vật vẽ bằng code)</option>${st.characters.map(c => `<option value="${esc(c.id)}">🧍 ${esc(c.name)}</option>`).join('')}</select></div></div>
      <label>Yêu cầu thêm (tuỳ chọn)</label><input id="cnextra" placeholder="vd: kênh khoa học vui cho người lớn, nhạc hồi hộp, kết bằng câu hỏi">
      <div class="runbar" style="margin-top:12px"><button class="gbtn" id="cngo" ${cli && st.ready ? '' : 'disabled'}>✨ Viết storyboard &amp; ảnh xem thử</button>
        <div class="st"><div id="cnst">Claude làm việc 10–30 phút (tốn lượt dùng gói Claude nhiều hơn chế độ thường). Xong sẽ có ảnh xem thử để duyệt trước khi dựng.</div></div></div></div>
    <div class="cinegrid">${st.projects.map(card).join('') || '<p class="muted">Chưa có video Điện ảnh nào.</p>'}</div>
    <dialog id="cndlg"><div class="dhead"><b id="cndlgt"></b><button class="icon" onclick="cndlg.close()">✕</button></div><div class="dbody"><pre id="cndoc" style="white-space:pre-wrap;font-size:13px"></pre></div></dialog></div>`);
  const P = page('cinema');
  bindSeg('cnasp', v => { CINE.aspect = v; });
  if ($('#cnsetup')) $('#cnsetup').onclick = async () => { const r = await api('/api/cinema/setup', { method: 'POST', body: {} }); watch(r.job, $('#cnsetupst'), 'Đang cài', j => { if (j.code === 0) pgCinema(); }); };
  $('#cngo').onclick = async () => {
    const topic = $('#cntopic').value.trim(); if (!topic) return $('#cntopic').focus();
    CINE = { ...CINE, topic, seconds: +$('#cnsec').value, lang: $('#cnlang').value };
    $('#cngo').disabled = true;
    const r = await api('/api/cinema/new', { method: 'POST', body: { topic, seconds: CINE.seconds, aspect: CINE.aspect, lang: CINE.lang, char3d: $('#cnchar').value, extra: $('#cnextra').value.trim() } });
    watch(r.job, $('#cnst'), 'Claude đang làm theo skill', j => { $('#cngo').disabled = false; if (j.code === 0) { CINE.topic = ''; toast('Đã có storyboard và ảnh xem thử'); pgCinema(); } });
  };
  P.querySelectorAll('.cine').forEach(c => {
    const slug = c.dataset.slug, stEl = c.querySelector('[data-cst]');
    c.querySelectorAll('[data-crun]').forEach(b => b.onclick = async () => {
      const k = b.dataset.crun, body = { slug, action: k === 'preview' ? 'render' : k, preview: k === 'preview' };
      const r = await api('/api/cinema/run', { method: 'POST', body });
      watch(r.job, stEl, { stills: 'Đang vẽ ảnh xem thử', preview: 'Đang dựng bản nhanh', render: 'Đang dựng video' }[k], j => { if (j.code === 0) { toast('Xong'); pgCinema(); } });
    });
    c.querySelectorAll('[data-cdoc]').forEach(b => b.onclick = async () => {
      const r = await api(`/api/cinema/file?slug=${encodeURIComponent(slug)}&name=${encodeURIComponent(b.dataset.cdoc)}`);
      $('#cndlgt').textContent = b.textContent; $('#cndoc').textContent = r.text; cndlg.showModal();
    });
    c.querySelector('[data-cdel]').onclick = async () => { if (!confirm(`Chuyển "${slug}" vào thùng rác?`)) return; await fetch('/api/cinema?slug=' + encodeURIComponent(slug), { method: 'DELETE' }); pgCinema(); };
  });
}

/* ================= NHÂN VẬT 3D (Blender, từ repo Skills) ================= */
let C3SEL = null;
async function pgChar3d() {
  const st = await api('/api/char3d');
  const est = (pf, q) => st.estimates[pf][q];
  const mins = m => m < 1 ? '<1 phút' : m < 60 ? `~${Math.round(m)} phút` : `~${(m / 60).toFixed(1)} giờ`;
  const card = c => `<div class="c3 ${C3SEL === c.id ? 'on' : ''}">
      <div class="c3img" style="${c.sheet ? `background-image:url('${c.sheet}')` : ''}">${c.sheet ? '' : '<span>Chưa có bảng xem trước</span>'}</div>
      <div class="c3bd"><div class="t">${esc(c.name)} <span class="muted small">· ${esc(c.id)}</span></div>
        <div class="small muted">${esc(c.role || '')}</div>
        <div class="bs" style="margin-top:6px">${c.sets.length ? c.sets.map(k => `<span class="badge ok">${esc(k.split('_')[0])}</span>`).join('') : '<span class="badge">chưa render động tác</span>'}</div></div>
      <div class="ac">
        <button class="btn2" data-sheet="${esc(c.id)}" ${st.ready ? '' : 'disabled'}>👁 Bảng xem trước</button>
        <select data-pf="${esc(c.id)}"><option value="co_ban">6 động tác cơ bản</option><option value="day_du">12 động tác đầy đủ</option></select>
        <select data-q="${esc(c.id)}"><option value="nhap">Nháp (nhanh)</option><option value="chuan" selected>Chuẩn</option><option value="cao">Cao</option></select>
        <button class="btn2 pri" data-spr="${esc(c.id)}" ${st.ready ? '' : 'disabled'}>🎬 Render động tác</button>
        <button class="btn2" data-edit="${esc(c.id)}">✏️ Sửa ngoại hình</button>
        <span class="st small muted" data-st="${esc(c.id)}"></span></div></div>`;
  html(page('char3d'), `<div class="wrap">
    <div class="ph" style="display:block"><h1>🧍 Nhân vật 3D</h1><p class="muted" style="margin:6px 0 0">Nhân vật người thật dựng bằng Blender (bộ hero3d của repo Skills). Mỗi nhân vật render <b>1 lần</b>, mọi video sau dùng lại.
      Dùng trong video: Trình sửa cảnh → Cài đặt video → Nhân vật → chọn mục <b>🧍 Nhân vật 3D</b> (chỉ áp cho cảnh "Người que diễn").</p></div>
    <div class="card"><div class="cap">Cài đặt</div>
      ${st.ready ? `<p class="small">✔ Blender sẵn sàng · ${st.fast_gpu ? `Card <b>${esc(st.gpu)}</b>: render nhanh` : `${st.gpu ? `Card ${esc(st.gpu)} yếu, ngang CPU` : 'Không có card NVIDIA'}: render bằng CPU (chậm, nên để chạy lúc rảnh)`}</p>`
        : `<p class="small">Cần cài Blender một lần (~500 MB: Python 3.13 riêng + bpy + dữ liệu cơ thể MPFB2). Máy cần có <b>git</b>.</p>
           <div class="row"><button class="btn2 pri" id="c3setup">⬇ Cài Blender cho nhân vật 3D</button><span class="st small muted" id="c3setupst"></span></div>`}
      <div class="row" style="margin-top:8px"><span class="small" style="flex:none">Thiết bị render</span>
        <select id="c3dev">${Object.entries(st.devices).map(([k, n]) => `<option value="${k}" ${k === st.device_choice ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>
        <button class="btn2" style="flex:none" id="c3gpu" ${st.ready ? '' : 'disabled'}>🔍 Kiểm tra card rời</button></div>
      <div class="small" id="c3gpust" style="margin-top:4px">${st.device === 'gpu' ? '🟢 Đang đặt render bằng card rời' : '⚪ Đang render bằng CPU'}</div>
      <div class="row" style="margin-top:8px"><span class="small" style="flex:none">Mức dùng CPU khi render</span>
        <select id="c3cpu">${Object.entries(st.cpu_levels).map(([k, n]) => `<option value="${k}" ${k === st.cpu ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>
        <span class="small muted" style="flex:none">${st.threads}/${st.cores} luồng · luôn ưu tiên thấp</span></div>
      <p class="small muted" style="margin-top:8px">Thời gian ước tính cho 1 nhân vật trên máy này: 6 động tác chuẩn ${mins(est('co_ban', 'chuan').minutes)}, nháp ${mins(est('co_ban', 'nhap').minutes)} · 12 động tác chuẩn ${mins(est('day_du', 'chuan').minutes)}.</p></div>
    <div class="card"><div class="cap">Tạo nhân vật mới</div>
      <div class="row"><input id="c3name" placeholder="Tên nhân vật, vd Minh"><select id="c3base">${st.characters.map(c => `<option value="${esc(c.id)}">dựa trên ${esc(c.name)}</option>`).join('')}</select><button class="btn2 pri" style="flex:none" id="c3new">+ Tạo</button></div>
      <p class="small muted">Tạo xong bấm "✏️ Sửa ngoại hình" để đổi tóc, quần áo, màu da, phụ kiện; hoặc nhờ Claude Code: <i>"tạo nhân vật 3D bác sĩ trẻ cho video y tế"</i>.</p></div>
    <div class="c3grid">${st.characters.map(card).join('')}</div>
    <dialog id="c3dlg"><div class="dhead"><b>Ngoại hình (JSON)</b><button class="icon" onclick="c3dlg.close()">✕</button></div>
      <div class="dbody"><p class="small muted">tóc: none|bald|buzz|short|messy|bob|long|wavy|curly|afro|ponytail|bun · áo (length): crop|waist|hip|thigh|knee|calf · quần: pants|jeans|shorts|skirt|leggings… · giày: boots|sneakers|shoes|sandals… · phụ kiện: backpack|glasses|beanie|cap|scarf. Đổi xong render lại bảng xem trước và động tác.</p>
      <textarea id="c3json" rows="22" style="width:100%;font-family:monospace;font-size:12px"></textarea></div>
      <div class="dfoot"><button class="btn2 pri" id="c3save">Lưu</button></div></dialog></div>`);
  const P = page('char3d');
  $('#c3dev').onchange = async e => { await api('/api/settings', { method: 'POST', body: { values: { 'char3d.device': e.target.value } } }); toast('Đã đổi thiết bị render'); pgChar3d(); };
  $('#c3gpu').onclick = async () => { const r = await api('/api/char3d/gpucheck', { method: 'POST', body: {} });
    watch(r.job, $('#c3gpust'), 'Blender đang dò card đồ hoạ', j => { if (j.code === 0) $('#c3gpust').innerHTML = (j.result.ok ? '✅ ' : '⚠️ ') + esc(j.result.msg); }); };
  $('#c3cpu').onchange = async e => { await api('/api/settings', { method: 'POST', body: { values: { 'char3d.cpu': e.target.value } } }); toast('Đã đổi mức dùng CPU (áp dụng từ lần render sau)'); pgChar3d(); };
  if ($('#c3setup')) $('#c3setup').onclick = async () => { const r = await api('/api/char3d/setup', { method: 'POST', body: {} }); watch(r.job, $('#c3setupst'), 'Đang cài Blender', j => { if (j.code === 0) { toast('Đã cài Blender'); pgChar3d(); } }); };
  $('#c3new').onclick = async () => { const name = $('#c3name').value.trim(); if (!name) return toast('Nhập tên nhân vật', true);
    const r = await api('/api/char3d/new', { method: 'POST', body: { name, base: $('#c3base').value } }); if (r.error) return toast(r.error, true); C3SEL = r.id; toast('Đã tạo ' + r.name); pgChar3d(); };
  const stEl = id => P.querySelector(`[data-st="${id}"]`);
  P.querySelectorAll('[data-sheet]').forEach(b => b.onclick = async () => { const id = b.dataset.sheet;
    const r = await api('/api/char3d/sheet', { method: 'POST', body: { id, quality: 'nhap' } }); watch(r.job, stEl(id), 'Đang dựng bảng xem trước', j => { if (j.code === 0) pgChar3d(); }); });
  P.querySelectorAll('[data-spr]').forEach(b => b.onclick = async () => { const id = b.dataset.spr, pf = P.querySelector(`[data-pf="${id}"]`).value, q = P.querySelector(`[data-q="${id}"]`).value;
    if (!confirm(`Render ${pf === 'co_ban' ? 6 : 12} động tác cho ${id}, ước tính ${mins(est(pf, q).minutes)}?\nChỉ cần làm 1 lần cho nhân vật này. Đóng tab vẫn chạy tiếp, mở lại Studio để xem kết quả.`)) return;
    const r = await api('/api/char3d/sprites', { method: 'POST', body: { id, profile: pf, quality: q } }); watch(r.job, stEl(id), 'Đang render', j => { if (j.code === 0) { toast('Xong động tác cho ' + id); META.char3d = null; pgChar3d(); } }); });
  P.querySelectorAll('[data-edit]').forEach(b => b.onclick = async () => { C3SEL = b.dataset.edit; $('#c3json').value = JSON.stringify(await api('/api/char3d/spec?id=' + encodeURIComponent(C3SEL)), null, 1); c3dlg.showModal(); });
  $('#c3save').onclick = async () => { let spec; try { spec = JSON.parse($('#c3json').value); } catch (e) { return toast('JSON lỗi: ' + e.message, true); }
    const r = await api('/api/char3d/spec', { method: 'POST', body: { id: C3SEL, spec } }); if (r.error) return toast(r.error, true); c3dlg.close(); toast('Đã lưu. Bấm "Bảng xem trước" để xem lại.'); };
  api('/api/meta').then(m => { META.char3d = m.char3d; }).catch(() => {});
}

/* ================= BẮT ĐẦU ================= */
async function pgHome() {
  const h = await api('/api/home');
  html(page('home'), `<div class="wrap">
    <div class="hero"><div><h2>Hôm nay làm video gì?</h2><p>Chọn thể loại, Studio gợi ý sẵn độ dài, khung hình, phong cách hình và nền tảng đăng. Bạn chỉ cần nhập chủ đề.</p></div>
      <div class="stats"><div class="stat"><b>${h.stats.series}</b><span>series</span></div><div class="stat"><b>${h.stats.episodes}</b><span>tập</span></div><div class="stat"><b>${h.stats.rendered}</b><span>đã render</span></div></div></div>
    <div class="sec">1 · Chọn thể loại</div>
    <div class="gtiles">${h.presets.map(p => `<button class="gtile" style="--c:${p.color}" data-p="${p.id}"><div class="i">${p.icon}</div><b>${esc(p.name)}</b><span>${ASPECT_NAME[p.aspect].split(' ')[0]} ${p.aspect} · ~${p.minutes} phút</span></button>`).join('')}</div>
    <div class="sec">2 · Hoặc chọn cách làm</div>
    <div class="ways">
      <div class="way2" style="--c:#8b5cf6" data-go="write"><div class="i">✨</div><b>AI viết kịch bản</b><p>Claude viết cả kịch bản và cảnh theo khuôn mẫu. Chạy trên CPU (máy yếu vẫn được).</p><span class="badge vi">1 lần gọi Claude</span></div>
      <div class="way2" style="--c:#10b981" data-go="narration"><div class="i">✍️</div><b>Tự viết lời dẫn</b><p>Bạn dán lời dẫn, app tự chia cảnh, chọn kiểu cảnh và cho người que diễn ngay trên máy.</p><span class="badge ok">0 token</span></div>
      <div class="way2" style="--c:#f97316" data-go="gpu"><div class="i">🎨</div><b>Ảnh AI trên GPU</b><p>Ảnh Flux/SDXL, clip Wan qua ComfyUI trên GPU thuê (RunPod, Vast) hoặc máy có card mạnh.</p><span class="badge warn">GPU thuê</span></div>
      <div class="way2" style="--c:#3b82f6" data-go="tools"><div class="i">🧰</div><b>Công cụ nhanh</b><p>Đổi khung hình, dịch .srt, ảnh thumbnail, tách âm thanh cho video có sẵn.</p><span class="badge">Không cần dự án</span></div>
    </div>
    <div class="grid2" style="margin-top:22px">
      <div class="card"><div class="cap">Gần đây</div><div class="rlist">${h.recent.map(e => `<div class="r" data-id="${esc(e.id)}">🎬 <span class="sp">${esc(e.title)}</span>${e.rendered ? '<span class="badge ok">đã render</span>' : e.voiced ? '<span class="badge vi">có giọng</span>' : '<span class="badge">nháp</span>'}</div>`).join('') || '<div class="empty">Chưa có video nào. Chọn một thể loại ở trên để bắt đầu.</div>'}</div></div>
      <div class="card"><div class="cap">Kiểm tra máy</div>${h.checks.map(c => `<div class="chk"><span class="k ${c.ok ? 'ok' : 'no'}">${c.ok ? '✓' : '!'}</span><span>${esc(c.name)}</span>${c.hint ? `<span class="h">${esc(c.hint)}</span>` : ''}</div>`).join('')}</div>
    </div></div>`);
  page('home').querySelectorAll('[data-p]').forEach(b => b.onclick = () => { WRITE.preset = b.dataset.p; go('write', b.dataset.p); });
  page('home').querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
  page('home').querySelectorAll('.r[data-id]').forEach(b => b.onclick = () => go('editor', b.dataset.id));
}

/* ================= THƯ VIỆN ================= */
async function pgLibrary() {
  const lib = await api('/api/library');
  SERIES = lib.series.map(s => s.name).filter(Boolean);
  const card = e => `<div class="ep">
    <div class="th" style="${e.thumb ? `background-image:url('${e.thumb}')` : ''}" data-open="${esc(e.id)}">${e.thumb ? '' : '🎬'}<span class="ar">${e.aspect}</span></div>
    <div class="bd2"><div class="t" data-open="${esc(e.id)}">${esc(e.title)}</div><div class="id">${esc(e.id)}</div>
      <div class="bs">${e.ai ? '<span class="badge vi">✨ AI</span>' : '<span class="badge ok">✍️ Tự viết</span>'}<span class="badge">${e.scenes} cảnh</span>${e.duration ? `<span class="badge">${Math.round(e.duration)}s</span>` : ''}<span class="badge">CC ${e.subs.join(' ')}</span>${e.rendered ? '<span class="badge ok">đã dựng</span>' : e.draft ? '<span class="badge warn">bản nháp</span>' : '<span class="badge">chưa dựng</span>'}</div></div>
    <div class="ac"><button class="btn2" data-open="${esc(e.id)}">✏️ Sửa</button><button class="btn2" data-render="${esc(e.id)}">🚀 Dựng</button>
      <select data-mv="${esc(e.id)}" title="Chuyển series"><option value="">— series —</option>${SERIES.map(s => `<option ${s === e.series ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select>
      <button class="xbtn" data-del="${esc(e.id)}" title="Xoá (chuyển vào thùng rác)">🗑</button></div></div>`;
  html(page('library'), `<div class="wrap">
    <div class="ph"><h1>📚 Thư viện</h1><span class="sp"></span><input id="newSeries" placeholder="Tên series mới" style="width:240px"><button class="btn2" id="addSeries">＋ Tạo series</button></div>
    ${lib.series.length ? lib.series.map(s => `<div class="shead"><b>${s.name ? esc(s.name) : 'Chưa xếp series'}</b><span class="muted">${s.episodes.length} tập</span><span class="sp"></span>${s.name ? `<button class="xbtn" data-dels="${esc(s.name)}" title="Xoá series (giữ các tập)">🗑</button>` : ''}</div>
      <div class="eps">${s.episodes.map(card).join('') || '<div class="empty">Series trống. Tạo tập mới ở trang AI viết kịch bản hoặc Tự viết lời dẫn.</div>'}</div>`).join('')
      : '<div class="empty" style="margin-top:20px">Chưa có video nào. <a href="#/write">Tạo video đầu tiên</a></div>'}</div>`);
  const P = page('library');
  $('#addSeries').onclick = async () => { const n = $('#newSeries').value.trim(); if (!n) return $('#newSeries').focus(); await api('/api/series', { method: 'POST', body: { name: n } }); toast('Đã tạo series ' + n); pgLibrary(); };
  P.querySelectorAll('[data-open]').forEach(b => b.onclick = () => go('editor', b.dataset.open));
  P.querySelectorAll('[data-render]').forEach(b => b.onclick = () => go('render', b.dataset.render));
  P.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
    const title = b.closest('.ep')?.querySelector('.t')?.textContent || b.dataset.del;
    if (!confirm(`Chuyển "${title}" vào thùng rác (workspace/_trash)? Các tập khác trong series không bị ảnh hưởng.`)) return;
    await api('/api/p/' + b.dataset.del, { method: 'DELETE' }); if (PID === b.dataset.del) { PID = null; localStorage.removeItem('vf.pid'); } pgLibrary();
  });
  P.querySelectorAll('[data-dels]').forEach(b => b.onclick = async () => { if (!confirm('Xoá series? Các tập vẫn giữ lại.')) return; await api('/api/series?name=' + encodeURIComponent(b.dataset.dels), { method: 'DELETE' }); pgLibrary(); });
  P.querySelectorAll('[data-mv]').forEach(s => s.onchange = async () => { await api(`/api/p/${s.dataset.mv}/series`, { method: 'POST', body: { series: s.value } }); pgLibrary(); });
}

/* ================= CHỦ ĐỀ THỊNH HÀNH ================= */
let TQ = { markets: ['vi'], window: '30 ngày qua', format: 'Video dài + Shorts', count: 8, niche: '' };
async function pgTrends() {
  PLAN = await api('/api/plan');
  const saved = await api('/api/research/saved');
  const manual = META.brain.backend === 'manual';
  html(page('trends'), `<div class="wrap">
    <div class="ph"><h1>🔥 Chủ đề thịnh hành</h1></div>
    <p class="lead">Claude tìm trên web những chủ đề đang lên theo từng thị trường ngôn ngữ, chấm điểm, kiểm tra rủi ro bản quyền và quảng cáo, rồi gợi ý tiêu đề, từ khoá, Shorts. Mỗi lần tìm là 1 lần <code>claude -p</code>; cùng câu hỏi trong 12 giờ thì dùng lại kết quả.</p>
    ${manual ? '<div class="card" style="border-color:#fcd34d;background:#fffbeb;margin-bottom:16px">Chưa kết nối AI tự gọi. <a href="#/settings">Kết nối Claude Code</a> để tìm chủ đề bằng web, hoặc dùng <b>Xu hướng nhanh</b> bên dưới (miễn phí, không cần AI).</div>' : ''}
    <div class="grid2">
      <div class="card"><div class="cap">1 · Thị trường &amp; thời gian</div>
        <label style="margin-top:0">Ngôn ngữ / thị trường · chọn tối đa 5</label>
        <div class="chips" id="tmk">${chipsHtml(Object.entries(META.languages).map(([k, v]) => [k, v.name]), TQ.markets, 'm')}</div>
        <div class="row" style="margin-top:6px;align-items:flex-end">
          <div><label>Xu hướng trong</label><select id="twin">${['7 ngày qua', '30 ngày qua', '3 tháng qua', '4-8 tuần tới (sự kiện sắp tới)'].map(o => `<option ${o === TQ.window ? 'selected' : ''}>${o}</option>`).join('')}</select></div>
          <div><label>Định dạng</label><select id="tfmt">${['Video dài + Shorts', 'Chỉ Shorts', 'Chỉ video dài'].map(o => `<option ${o === TQ.format ? 'selected' : ''}>${o}</option>`).join('')}</select></div>
          <div><label>Số chủ đề</label><select id="tcnt">${[5, 8, 10, 12].map(o => `<option ${o == TQ.count ? 'selected' : ''}>${o}</option>`).join('')}</select></div>
        </div>
        <label>Hướng kênh / ngách (tuỳ chọn)</label><input id="tniche" value="${esc(TQ.niche)}" placeholder="vd: lịch sử kỳ lạ, khoa học đời thường, kinh tế dễ hiểu">
        <div class="runbar" style="margin-top:14px"><button class="gbtn" id="tgo" ${manual ? 'disabled' : ''}>🔎 Tìm chủ đề</button><label class="check" style="margin:0"><input type="checkbox" id="tfresh"> Tìm mới (bỏ qua kết quả 12 giờ)</label></div>
        <div class="st small muted" id="tst" style="margin-top:8px"></div>
      </div>
      <div class="card"><div class="cap">Lần tìm trước &amp; kế hoạch</div>
        <label style="margin-top:0">Kết quả đã lưu</label>
        <select id="tsaved"><option value="">—</option>${saved.map(s => `<option value="${esc(s.file)}">${esc(s.label)}</option>`).join('')}</select>
        <div class="cap" style="margin-top:16px;text-transform:none;letter-spacing:0;font-size:14px">⭐ Kế hoạch (chủ đề đã lưu)</div>
        <div class="plan" id="tplan"></div>
        <p class="small muted" style="margin:10px 0 0">Tiêu chí: chủ đề làm được bằng hình tự vẽ (không cần cảnh phim, nhạc, thể thao, logo); thân thiện quảng cáo; có góc nhìn riêng để kênh không bị coi là nội dung lặp lại, sản xuất hàng loạt.</p>
      </div>
    </div>
    <div id="tres"></div>
    <details class="card" style="margin-top:16px" id="tfree"><summary style="cursor:pointer;font-weight:700">⚡ Xu hướng nhanh (miễn phí, không cần AI): Google Trends, Wikipedia, Hacker News</summary><div id="tfreebody" style="margin-top:12px"></div></details>
  </div>`);
  bindChips($('#tmk'), '[data-m]', () => TQ.markets, 5);
  renderPlan();
  $('#tgo').onclick = runResearch;
  $('#tsaved').onchange = async e => { if (!e.target.value) return; RESEARCH = await api('/api/research/file?name=' + encodeURIComponent(e.target.value)); renderResearch(); };
  $('#tfree').ontoggle = () => $('#tfree').open && !$('#tfreebody').innerHTML && freeTrends();
  if (RESEARCH) renderResearch();
  else if (saved[0]) { RESEARCH = await api('/api/research/file?name=' + encodeURIComponent(saved[0].file)); $('#tsaved').value = saved[0].file; renderResearch(); }
}
function renderPlan() {
  $('#tplan').innerHTML = PLAN.length ? PLAN.map((p, i) => `<div class="row2"><span class="st">⭐</span><span class="t">${esc(p.title)}</span><button class="btn2" data-w="${i}">✍️ Viết</button><button class="xbtn" data-x="${i}">✕</button></div>`).join('')
    : '<div class="empty small">Chưa có. Bấm "Lưu vào kế hoạch" ở thẻ chủ đề.</div>';
  $('#tplan').querySelectorAll('[data-w]').forEach(b => b.onclick = () => writeFromTopic(PLAN[+b.dataset.w]));
  $('#tplan').querySelectorAll('[data-x]').forEach(b => b.onclick = async () => { PLAN.splice(+b.dataset.x, 1); await api('/api/plan', { method: 'POST', body: { items: PLAN } }); renderPlan(); });
}
async function runResearch() {
  TQ.window = $('#twin').value; TQ.format = $('#tfmt').value; TQ.count = +$('#tcnt').value; TQ.niche = $('#tniche').value.trim();
  if (!TQ.markets.length) return toast('Chọn ít nhất một thị trường', true);
  $('#tgo').disabled = true;
  const r = await api('/api/research', { method: 'POST', body: { ...TQ, fresh: $('#tfresh').checked } });
  watch(r.job, $('#tst'), 'Claude đang tìm và chấm điểm chủ đề (1–3 phút)', j => {
    $('#tgo').disabled = false;
    if (j.code === 0) { RESEARCH = j.result; renderResearch(); toast(j.result.cached ? 'Dùng lại kết quả trong 12 giờ' : 'Đã tìm xong'); }
  });
}
function renderResearch() {
  const R = RESEARCH; if (!R) return;
  const q = R.query || {};
  const label = { demand: 'Nhu cầu', competition: 'Ít cạnh tranh', fit: 'Độ hợp', evergreen: 'Độ bền', safety: 'An toàn' };
  $('#tres').innerHTML = `
    ${(R.events || []).length ? `<div class="card" style="margin-top:16px"><div class="cap">📅 Sự kiện sắp tới có thể làm mốc</div><ul class="events" style="margin:0;padding-left:20px">${R.events.map(e => `<li><b>${esc(e.date || '')}</b> · ${esc(e.title || '')}${e.note ? '. ' + esc(e.note) : ''} <span class="lg">${(e.langs || []).join(', ')}</span></li>`).join('')}</ul></div>` : ''}
    <p class="small muted" style="margin:18px 2px 10px">${esc(R.created || '')} · ${(R.topics || []).length} chủ đề · ${esc((q.markets || []).join(', '))} · ${esc(q.window || '')} · xếp theo điểm tổng (nhu cầu, cạnh tranh, độ hợp, độ bền, an toàn)${R.cached ? ' · kết quả đã lưu' : ''}</p>
    <div class="tcards">${(R.topics || []).map((t, i) => `<div class="tc">
      <h4><span>${i + 1}. ${esc(t.title)}</span><span class="s">${(+t.score || 0).toFixed(1)}</span></h4>
      <div class="bs">${t.rising ? '<span class="badge up">📈 đang lên</span>' : ''}<span class="badge ${t.risk === 'low' ? 'ok' : t.risk === 'high' ? 'err' : 'warn'}">© rủi ro ${({ low: 'thấp', medium: 'vừa', high: 'cao' })[t.risk] || '?'}</span>${t.ad_friendly ? '<span class="badge ok">$ thân thiện quảng cáo</span>' : ''}${t.format ? `<span class="badge vi">${esc(t.format)}${t.minutes ? ' · ' + t.minutes + ' phút' : ''}</span>` : ''}</div>
      ${t.hook ? `<p><b>${esc(t.hook)}</b></p>` : ''}${t.why ? `<p>${esc(t.why)}</p>` : ''}
      ${t.scores ? `<div class="bars">${Object.entries(label).filter(([k]) => t.scores[k] != null).map(([k, n]) => `<span>${n}</span><i><span style="width:${(+t.scores[k]) * 10}%"></span></i><span>${(+t.scores[k]).toFixed(0)}</span>`).join('')}</div>` : ''}
      ${(t.keywords || []).length ? `<div class="kw">${t.keywords.slice(0, 8).map(k => `<span>${esc(k)}</span>`).join('')}</div>` : ''}
      ${(t.shorts || []).length ? `<div class="small muted">Shorts: ${t.shorts.map(esc).join(' · ')}</div>` : ''}
      <div class="ac"><button class="btn2" data-save="${i}">⭐ Lưu vào kế hoạch</button><button class="btn2 pri" data-write="${i}">✍️ Viết kịch bản</button></div></div>`).join('')}</div>`;
  $('#tres').querySelectorAll('[data-save]').forEach(b => b.onclick = async () => { const t = R.topics[+b.dataset.save]; if (PLAN.some(p => p.title === t.title)) return toast('Đã có trong kế hoạch'); PLAN.push(t); await api('/api/plan', { method: 'POST', body: { items: PLAN } }); renderPlan(); toast('Đã lưu vào kế hoạch'); });
  $('#tres').querySelectorAll('[data-write]').forEach(b => b.onclick = () => writeFromTopic(R.topics[+b.dataset.write]));
}
function writeFromTopic(t) {
  WRITE = { topic: [t.topic || t.title, t.hook && `Hook: ${t.hook}`, t.angle && `Góc: ${t.angle}`].filter(Boolean).join('. '), genre: t.genre, minutes: t.minutes, lang: (t.markets || [])[0], extra: (t.keywords || []).length ? 'Từ khoá nên có: ' + t.keywords.slice(0, 6).join(', ') : '' };
  go('write');
}
async function freeTrends() {
  const box = $('#tfreebody'); box.innerHTML = '<span class="spin"></span>Đang tải…';
  const lang = TQ.markets[0] || 'vi', geo = (META.languages[lang] || {}).geo || 'VN';
  const r = await api(`/api/trends?geo=${geo}&lang=${lang}`);
  const items = (r.items || []).filter(t => !t.sensitive).slice(0, 30);
  box.innerHTML = `<p class="small muted" style="margin:0 0 10px">${esc((META.languages[lang] || {}).name || lang)} · cập nhật ${esc(r.fetched || '')}${r.dropped ? ` · đã ẩn ${r.dropped} mục không phù hợp` : ''}</p>
    <div class="tcards">${items.map((t, i) => `<div class="tc"><h4><span>${esc(t.title)}</span></h4><div class="bs"><span class="badge">${esc(t.category_name || '')}</span><span class="badge vi">${esc(t.traffic)}</span></div>${t.context?.length ? `<p class="small">${esc(t.context[0])}</p>` : ''}${t.angle ? `<p><b>Gợi ý:</b> ${esc(t.angle)}</p>` : ''}<div class="ac"><button class="btn2 pri" data-fw="${i}">✍️ Viết kịch bản</button></div></div>`).join('')}</div>`;
  box.querySelectorAll('[data-fw]').forEach(b => b.onclick = () => { const t = items[+b.dataset.fw]; WRITE = { topic: (t.angle || t.title) + (t.context?.length ? ` (bối cảnh: ${t.context[0]})` : ''), lang }; go('write'); });
}

/* ================= AI VIẾT KỊCH BẢN ================= */
async function pgWrite(presetId) {
  const presets = META.presets || (META.presets = (await api('/api/home')).presets);
  const pr = presets.find(p => p.id === (presetId || WRITE.preset));
  const W = WRITE = { topic: '', preset: pr?.id || '', genre: pr?.genre || WRITE.genre || 'explainer', aspect: pr?.aspect || '16:9', platforms: [], minutes: pr?.minutes || WRITE.minutes || 3,
    lang: WRITE.lang || 'vi', burn: 'karaoke', subs: [], tone: 'tò mò, dễ hiểu, cho người lớn', extra: '', style: pr?.style || '', series: '', ...WRITE, preset: pr?.id || WRITE.preset || '' };
  if (pr) { W.aspect = pr.aspect; W.minutes = pr.minutes; W.genre = pr.genre; W.style = pr.style; }
  if (!W.platforms.length) W.platforms = Object.entries(META.platforms || {}).filter(([, a]) => a === W.aspect).map(([k]) => k).slice(0, 1);
  const manual = META.brain.backend === 'manual';
  html(page('write'), `<div class="wrap">
    <div class="ph"><h1>✨ AI viết kịch bản</h1></div>
    <p class="lead">Nhập chủ đề, chọn thể loại; Claude viết kịch bản và cảnh rồi mở trong trình sửa cảnh. Hình dựng bằng template trên CPU, giọng đọc miễn phí.</p>
    <div class="grid2">
      <div class="card"><div class="cap">1 · Nội dung</div>
        <label style="margin-top:0" for="wtopic">Chủ đề</label><input id="wtopic" value="${esc(W.topic)}" placeholder="vd: Lịch sử của muối">
        <div class="tintbox"><div class="row" style="align-items:flex-end">
          <div><label style="margin-top:0">Thể loại</label><select id="wpreset"><option value="">Tuỳ chọn (không theo mẫu)</option>${presets.map(p => `<option value="${p.id}" ${p.id === W.preset ? 'selected' : ''}>${p.icon} ${esc(p.name)}</option>`).join('')}</select></div>
          <div style="flex:none"><label style="margin-top:0">Khung hình</label>${segHtml(['16:9', '9:16', '1:1', '4:5'], W.aspect, 'wasp')}</div></div>
          <label>Đăng lên · chọn nhiều</label><div class="chips" id="wplat">${chipsHtml(Object.keys(META.platforms || {}).map(k => [k, k]), W.platforms, 'pl')}</div>
          <p class="small muted" style="margin:8px 0 0" id="wplhint">${PLATFORM_HINT[W.aspect]}</p></div>
        <div class="row" style="align-items:flex-end">
          <div><label style="margin-top:0">Series</label><select id="wseries"><option value="">— không —</option>${SERIES.map(s => `<option ${s === W.series ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select></div>
          <div><label style="margin-top:0">Số phút</label><input id="wmin" type="number" min="0.5" max="12" step="0.5" value="${W.minutes}"></div>
          <div><label style="margin-top:0">Phong cách hình</label><select id="wstyle"><option value="">AI tự chọn</option>${Object.entries(META.styles).map(([k]) => `<option ${k === W.style ? 'selected' : ''}>${k}</option>`).join('')}</select></div>
          <div><label style="margin-top:0">Nhân vật chính</label>${char3dSelect('wchar', W.char3d)}</div></div>
      </div>
      <div class="card"><div class="cap">2 · Ngôn ngữ &amp; giọng văn</div>
        <div class="tintbox" style="margin-top:0"><div class="row">
          <div><label style="margin-top:0">Giọng đọc</label><select id="wlang">${langOptions(W.lang)}</select></div>
          <div><label style="margin-top:0">Ghép cứng phụ đề vào video</label><select id="wburn"><option value="karaoke" ${W.burn === 'karaoke' ? 'selected' : ''}>Có, karaoke theo giọng đọc</option><option value="none" ${W.burn === 'none' ? 'selected' : ''}>Không (chỉ xuất file .srt)</option></select></div></div>
          <label>Phụ đề thêm · chỉ dịch chữ, không lồng tiếng</label><div class="chips" id="wsubs"></div></div>
        <label for="wtone">Giọng văn / khán giả</label><input id="wtone" value="${esc(W.tone)}">
        <details style="margin-top:12px" ${W.extra ? 'open' : ''}><summary style="cursor:pointer">Yêu cầu thêm cho Claude</summary><textarea id="wextra" rows="3" style="margin-top:8px" placeholder="vd: có 1 nhân vật mèo tên Mun; nhắc nguồn NASA; kết bằng câu hỏi cho khán giả">${esc(W.extra)}</textarea></details>
      </div>
    </div>
    <div class="card" style="margin-top:16px"><div class="runbar"><button class="gbtn" id="wgo" ${manual ? 'disabled' : ''}>✨ Viết kịch bản</button>
      <div class="st"><div id="wst">${manual ? 'Chưa kết nối AI tự gọi: dùng nút bên phải để lấy prompt cho claude.ai, hoặc <a href="#/settings">kết nối Claude Code</a>.' : 'Kết quả hiện ở đây, rồi tự mở trình sửa cảnh.'}</div><div class="small">Engine: ${BRAIN_NAME[META.brain.backend]}</div></div>
      <span class="sp" style="flex:1"></span><button class="btn2" id="wprompt">Lấy prompt cho claude.ai</button></div>
      <div id="wpaste" hidden style="margin-top:12px"><label style="margin-top:0">Dán câu trả lời từ claude.ai</label><textarea id="wjson" class="code" rows="6"></textarea><button class="btn2 pri" id="wimport" style="margin-top:8px">Nhập kịch bản</button></div></div>
  </div>`);
  const renderSubs = () => { $('#wsubs').innerHTML = chipsHtml(Object.entries(META.languages).map(([k, v]) => [k, v.name]), W.subs, 'sb'); $('#wsubs').querySelector(`[data-sb="${W.lang}"]`)?.classList.add('dis'); bindChips($('#wsubs'), '[data-sb]', () => W.subs); };
  renderSubs();
  bindSeg('wasp', v => { W.aspect = v; $('#wplhint').textContent = PLATFORM_HINT[v]; });
  bindChips($('#wplat'), '[data-pl]', () => W.platforms, 0, () => { const a = (META.platforms || {})[W.platforms[W.platforms.length - 1]]; if (a && a !== W.aspect) { W.aspect = a; $('#wasp').querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === a)); $('#wplhint').textContent = PLATFORM_HINT[a]; } });
  $('#wpreset').onchange = e => { WRITE = { ...collectWrite(), preset: e.target.value }; pgWrite(e.target.value); };
  $('#wlang').onchange = e => { W.lang = e.target.value; W.subs = W.subs.filter(x => x !== W.lang); renderSubs(); };
  $('#wgo').onclick = async () => {
    const b = collectWrite(); if (!b.topic) return $('#wtopic').focus();
    const pr2 = presets.find(p => p.id === b.preset);
    $('#wgo').disabled = true;
    const r = await api('/api/write', { method: 'POST', body: { topic: b.topic, genre: b.genre, aspect: b.aspect, platforms: b.platforms, series: b.series, minutes: b.minutes, lang: b.lang, burn_captions: b.burn === 'karaoke', subtitle_langs: b.subs, tone: b.tone, extra: b.extra, style: b.style, preset_notes: pr2?.notes || '', char3d: b.char3d } });
    watch(r.job, $('#wst'), 'Claude đang viết kịch bản (1–3 phút)', j => {
      $('#wgo').disabled = false;
      if (j.code === 0) { WRITE = {}; toast(j.result.errors?.length ? `Đã viết, còn ${j.result.errors.length} lỗi nhỏ cần sửa` : 'Đã viết xong kịch bản'); go('editor', j.result.project_id); }
    });
  };
  $('#wprompt').onclick = async () => {
    const b = collectWrite(); if (!b.topic) return $('#wtopic').focus();
    const r = await api('/api/prompt', { method: 'POST', body: { topic: b.topic + (b.extra ? '. ' + b.extra : ''), genre: b.genre, style: b.style, aspect: b.aspect, lang: b.lang, seconds: Math.round(b.minutes * 60) } });
    try { await navigator.clipboard.writeText(r.prompt); toast(`Đã chép prompt (~${Math.round(r.prompt.length / 4)} token). Dán vào claude.ai.`); } catch { $('#wjson').value = r.prompt; toast('Prompt nằm trong ô bên dưới: hãy tự chép rồi xoá đi', true); }
    $('#wpaste').hidden = false;
  };
  $('#wimport').onclick = async () => { const r = await api('/api/import', { method: 'POST', body: { text: $('#wjson').value } }); if (r.error) return toast('Không đọc được kịch bản: ' + r.error, true); go('editor', r.id); };
}
function collectWrite() {
  const presets = META.presets || [];
  const pr = presets.find(p => p.id === $('#wpreset').value);
  return { ...WRITE, topic: $('#wtopic').value.trim(), preset: $('#wpreset').value, genre: pr?.genre || WRITE.genre || 'explainer', aspect: WRITE.aspect, minutes: +$('#wmin').value || 1,
    series: $('#wseries').value, style: $('#wstyle').value, lang: $('#wlang').value, burn: $('#wburn').value, tone: $('#wtone').value.trim(), extra: $('#wextra').value.trim(),
    char3d: $('#wchar')?.value || '' };
}
/** Ô chọn nhân vật: người que hoặc nhân vật 3D đã render động tác. */
function char3dSelect(id, cur) {
  const ready = (META.char3d || []).filter(c => c.sets.length);
  return `<select id="${id}"><option value="">Người que (mặc định)</option>${ready.map(c => `<option value="${esc(c.id)}" ${c.id === cur ? 'selected' : ''}>🧍 ${esc(c.name)} (3D)</option>`).join('')}
    ${(META.char3d || []).length > ready.length ? '<option disabled>— nhân vật 3D khác: render động tác trước —</option>' : ''}</select>`;
}

/* ================= TỰ VIẾT LỜI DẪN ================= */
let NAR = { aspect: '9:16', lang: 'vi' };
async function pgNarration() {
  html(page('narration'), `<div class="wrap">
    <div class="ph"><h1>✍️ Tự viết lời dẫn</h1><span class="badge ok">0 token</span></div>
    <p class="lead">Dán lời dẫn của bạn. App tự chia thành cảnh theo câu, chọn kiểu cảnh (con số → thẻ số, liệt kê → danh sách, năm → dòng thời gian, trích dẫn → thẻ trích, còn lại → người que diễn theo động từ) mà không gọi AI. Sau đó chỉnh tiếp trong trình sửa cảnh.</p>
    <div class="grid2" style="grid-template-columns:1.6fr 1fr">
      <div class="card"><div class="cap">Lời dẫn</div>
        <input id="ntitle" placeholder="Tiêu đề video (tuỳ chọn)">
        <textarea id="ntext" rows="16" style="margin-top:10px;font-size:15px;line-height:1.6" placeholder="Viết hoặc dán lời dẫn ở đây. Mỗi 1–2 câu sẽ thành một cảnh."></textarea>
        <p class="small muted" id="nstat" style="margin:8px 0 0">0 từ</p></div>
      <div class="card"><div class="cap">Thiết lập</div>
        <div class="tintbox" style="margin-top:0">
          <label style="margin-top:0">Ngôn ngữ giọng đọc</label><select id="nlang">${langOptions(NAR.lang)}</select>
          <label>Khung hình</label>${segHtml(['9:16', '16:9', '1:1', '4:5'], NAR.aspect, 'nasp')}
          <label>Phong cách hình</label><select id="nstyle">${Object.keys(META.styles).map(k => `<option>${k}</option>`).join('')}</select>
          <label>Nhân vật chính</label>${char3dSelect('nchar', '')}
          <label>Series</label><select id="nseries"><option value="">— không —</option>${SERIES.map(s => `<option>${esc(s)}</option>`).join('')}</select></div>
        <button class="gbtn" id="ngo" style="width:100%;margin-top:6px">✂️ Chia cảnh (0 token)</button>
        <p class="small muted" style="margin:10px 0 0">Mẹo: viết số bằng chữ số để có thẻ con số ("2600 lần"), liệt kê bằng dấu phẩy ("a, b và c"), trích dẫn trong ngoặc kép.</p></div>
    </div></div>`);
  bindSeg('nasp', v => NAR.aspect = v);
  $('#ntext').oninput = () => { const w = $('#ntext').value.split(/\s+/).filter(Boolean).length; $('#nstat').textContent = `${w} từ · khoảng ${Math.round(w / 2.5)} giây · ~${Math.max(1, Math.round(w / 18))} cảnh`; };
  $('#ngo').onclick = async () => {
    const text = $('#ntext').value.trim(); if (text.split(/\s+/).length < 5) return $('#ntext').focus();
    const r = await api('/api/narration', { method: 'POST', body: { text, title: $('#ntitle').value.trim(), lang: $('#nlang').value, aspect: NAR.aspect, style: $('#nstyle').value, series: $('#nseries').value, char3d: $('#nchar').value } });
    if (r.error) return toast(r.error, true);
    toast(`Đã chia ${r.scenes} cảnh`); go('editor', r.project_id);
  };
}

/* ================= ẢNH AI TRÊN GPU ================= */
async function pgGpu() {
  const g = await api('/api/gpu');
  html(page('gpu'), `<div class="wrap">
    <div class="ph"><h1>🎨 Ảnh AI trên GPU</h1><span class="badge warn">GPU thuê</span></div>
    <p class="lead">Khi cần hình AI (Flux, SDXL) hoặc clip (Wan 2.1, LTX-Video), máy yếu chỉ gửi yêu cầu tới ComfyUI chạy trên GPU thuê theo giờ (RunPod, Vast.ai) hoặc máy có card mạnh. Cảnh dùng <code>visual_type: comfyui</code> kèm <code>prompt</code>.</p>
    <div class="grid2">
      <div class="card"><div class="cap">Kết nối ComfyUI</div>
        <label style="margin-top:0">Địa chỉ ComfyUI</label><div class="row"><input id="gurl" value="${esc(g.url || '')}" placeholder="http://127.0.0.1:8188 hoặc https://xxxx-8188.proxy.runpod.net"><button class="btn2 pri" style="flex:none" id="gtest">Kiểm tra</button></div>
        <div id="gst" style="margin-top:12px">${g.ok ? `<span class="badge ok">✓ Đã kết nối</span> ${esc(g.device || '')} · ${g.vram || '?'} GB VRAM` : `<span class="badge warn">Chưa kết nối</span> <span class="small muted">${esc(g.error || '')}</span>`}</div>
        <div class="cap" style="margin-top:18px">Workflow có sẵn</div>
        <div class="chips">${(g.workflows || []).map(w => `<span class="badge vi">${esc(w)}</span>`).join('') || '<span class="muted small">Chưa có</span>'}</div>
        <p class="small muted">Thêm workflow: trong ComfyUI chọn Save (API Format), đặt file vào <code>templates/comfy_workflows/</code>, thay chữ prompt bằng <code>{{prompt}}</code>.</p></div>
      <div class="card"><div class="cap">Thuê GPU theo giờ</div>
        <ol style="margin:0;padding-left:20px;line-height:1.8">
          <li>Tạo pod từ template có sẵn ComfyUI (RunPod, Vast.ai), GPU 16–24 GB VRAM là đủ cho Flux / Wan.</li>
          <li>Mở cổng 8188, chép địa chỉ proxy (dạng <code>https://…-8188.proxy.runpod.net</code>) vào ô bên trái, bấm Kiểm tra.</li>
          <li>Trong trình sửa cảnh: tab Thời lượng → Nguồn hình → <b>Ảnh/clip AI (ComfyUI)</b>, nhập mô tả hình.</li>
          <li>Xuất video như bình thường; xong việc nhớ <b>tắt pod</b> để không tốn tiền.</li></ol>
        <p class="small muted">Ảnh tạo ra được lưu trong <code>assets/gen/</code> của video, render lại không tốn GPU nữa.</p></div>
    </div></div>`);
  $('#gtest').onclick = async () => { $('#gst').innerHTML = '<span class="spin"></span>Đang kiểm tra…'; const r = await api('/api/gpu', { method: 'POST', body: { url: $('#gurl').value.trim() } }); $('#gst').innerHTML = r.ok ? `<span class="badge ok">✓ Đã kết nối</span> ${esc(r.device || '')} · ${r.vram || '?'} GB VRAM` : `<span class="badge err">Không kết nối được</span> <span class="small muted">${esc(r.error || '')}</span>`; };
}

/* ================= RENDER & ĐĂNG ================= */
let RSEL = null;
async function pgRender(id) {
  const lib = await api('/api/library');
  const eps = lib.series.flatMap(s => s.episodes).sort((a, b) => b.mtime - a.mtime);
  RSEL = id || RSEL || eps[0]?.id;
  html(page('render'), `<div class="wrap">
    <div class="ph"><h1>🚀 Render &amp; đăng</h1></div>
    <p class="lead">Tạo giọng, xuất video, thêm phụ đề nhiều ngôn ngữ và gói đăng (tiêu đề, mô tả, tag, chương) cho từng nền tảng.</p>
    ${eps.length ? `<div class="rl"><div class="card" style="padding:10px">${eps.map(e => `<div class="it ${e.id === RSEL ? 'on' : ''}" data-id="${esc(e.id)}">${e.thumb ? `<img src="${e.thumb}" alt="">` : '<div class="ph2"></div>'}<div><b>${esc(e.title)}</b><span class="small muted">${e.rendered ? '✓ đã dựng' : e.voiced ? 'có giọng' : 'chưa dựng'} · ${e.aspect}</span></div></div>`).join('')}</div><div id="rdetail"></div></div>`
      : '<div class="empty">Chưa có video nào.</div>'}</div>`);
  page('render').querySelectorAll('.it').forEach(b => b.onclick = () => { RSEL = b.dataset.id; go('render', RSEL); });
  if (RSEL) renderDetail(eps.find(e => e.id === RSEL) || eps[0]);
}
function renderDetail(e) {
  const full = e.videos.find(v => !v.includes('_draft')), draft = e.videos.find(v => v.includes('_draft'));
  $('#rdetail').innerHTML = `<div class="card"><div class="ph" style="margin:0 0 4px"><h1 style="font-size:18px">${esc(e.title)}</h1><span class="sp"></span><button class="btn2" onclick="go('editor','${esc(e.id)}')">✏️ Mở trình sửa cảnh</button></div>
      <p class="small muted" style="margin:0 0 14px">${e.scenes} cảnh · ${e.duration ? Math.round(e.duration) + ' giây' : 'chưa đo thời lượng'} · ${e.aspect} · ${esc((META.languages[e.lang] || {}).name || e.lang)}</p>
      <div class="runbar"><button class="btn2" data-step="voice">🎙 Giọng đọc</button><button class="btn2" data-step="draft">⚡ Xuất bản nháp</button><button class="gbtn" data-step="all">🚀 Xuất video</button><span class="st" id="rst"></span></div>
      ${full || draft ? `<video class="outv" id="rvideo" controls src="/files/${esc(e.id)}/out/${esc(full || draft)}?${e.mtime}" style="margin-top:14px"></video>
        <div class="chips" style="margin-top:10px">${e.videos.map(v => `<a class="btn2" href="/files/${esc(e.id)}/out/${esc(v)}" download>⬇ ${esc(v)}</a>`).join('')}${e.subs.map(l => `<a class="btn2" href="/files/${esc(e.id)}/out/${esc(e.id)}${l === e.lang ? '' : '.' + l}.srt" download>⬇ phụ đề ${esc(l)}</a>`).join('')}<button class="btn2" id="rthumbgo">🖼 Lấy khung này làm ảnh đại diện</button></div>` : ''}</div>
    <div class="grid2" style="margin-top:16px">
      <div class="card"><div class="cap">Phụ đề thêm · chỉ dịch chữ</div><div class="chips" id="rsubs">${chipsHtml(Object.entries(META.languages).filter(([k]) => k !== e.lang).map(([k, v]) => [k, v.name]), [], 'rs')}</div>
        <div class="runbar" style="margin-top:12px"><button class="btn2 pri" id="rsubgo">Tạo phụ đề</button><span class="st" id="rsubst"></span></div>
        <p class="small muted">Cần video đã có giọng đọc. Mỗi ngôn ngữ 1 lần gọi model nhỏ. Muốn lồng tiếng: Trình sửa cảnh → Cài đặt video → Tạo bản dịch.</p></div>
      <div class="card"><div class="cap">Gói đăng</div><div class="row"><select id="rplat">${Object.keys(META.platforms || {}).map(p => `<option>${p}</option>`).join('')}</select><button class="btn2 pri" style="flex:none" id="rpubgo">Viết gói đăng</button></div><div class="st small muted" id="rpubst" style="margin-top:8px"></div><div id="rpub"></div></div>
      <div class="card"><div class="cap">🛡 Kiểm duyệt chính sách</div><p class="small muted" style="margin:0 0 10px">Rà lời đọc, chữ trên màn hình và tiêu đề theo chính sách YouTube/TikTok (kiếm tiền, nhãn AI, bản quyền, thân thiện quảng cáo). Có câu viết lại an toàn để áp một chạm.</p>
        <div class="row"><button class="btn2 pri" id="rauditgo">🛡 Kiểm duyệt</button><span class="st small muted" id="rauditst"></span></div><div id="raudit" style="margin-top:10px"></div></div>
      ${full || draft ? `<div class="card"><div class="cap">🎨 Thumbnail thu hút</div><p class="small muted" style="margin:0 0 10px">Tự ghép khung hình trong video với chữ to + dải màu theo đúng tông của video — thay cho 1 khung hình trần.</p>
        <input id="rthumbtext" placeholder="Chữ nổi bật (để trống thì dùng chữ ở ô 'Chữ trên thumbnail' hoặc tiêu đề video)" style="width:100%;margin-bottom:8px">
        <div class="row"><button class="btn2 pri" id="rthumbpro">🎨 Tạo thumbnail</button><span class="st small muted" id="rthumbprost"></span></div>
        <div id="rthumbprev" style="margin-top:10px"></div></div>` : ''}
    </div>`;
  const pubBox = p => { const box = (lab, val) => val ? `<label>${lab}</label><div class="copy"><textarea rows="${Math.min(8, String(val).split('\n').length + 1)}" readonly>${esc(val)}</textarea><button class="btn2" onclick="navigator.clipboard.writeText(this.previousElementSibling.value);toast('Đã chép')">Chép</button></div>` : '';
    if (p.thumbnail_text && $('#rthumbtext') && !$('#rthumbtext').value) $('#rthumbtext').value = p.thumbnail_text;
    return box('Tiêu đề', p.title) + box('Tiêu đề khác', (p.alt_titles || []).join('\n')) + box('Mô tả', [p.description, (p.chapters || []).join('\n'), (p.hashtags || []).join(' ')].filter(Boolean).join('\n\n')) + box('Tag', (p.tags || []).join(', ')) + box('Chữ trên thumbnail', p.thumbnail_text) + box('Bình luận ghim', p.pinned_comment); };
  const slug = p => p.replace(/ /g, '_').toLowerCase();
  const loadPub = async () => {
    const f = (e.publish || {})[slug($('#rplat').value)];
    $('#rpub').innerHTML = '';
    if (f) $('#rpub').innerHTML = pubBox(await (await fetch(`/files/${e.id}/out/${f}`)).json());
  };
  loadPub();
  const D = $('#rdetail');
  D.querySelectorAll('[data-step]').forEach(b => b.onclick = async () => {
    const r = await api(`/api/p/${e.id}/run`, { method: 'POST', body: { step: b.dataset.step } });
    watch(r.job, $('#rst'), { voice: 'Đang tạo giọng', draft: 'Đang xuất bản nháp', all: 'Đang xuất video' }[b.dataset.step], j => { if (j.code === 0) { toast('Xong'); pgRender(e.id); } });
  });
  const subs = []; bindChips($('#rsubs'), '[data-rs]', () => subs);
  $('#rsubgo').onclick = async () => { if (!subs.length) return toast('Chọn ngôn ngữ', true); if (META.brain.backend === 'manual') return go('settings'); const r = await api(`/api/p/${e.id}/subs`, { method: 'POST', body: { langs: subs } }); watch(r.job, $('#rsubst'), 'Đang dịch phụ đề', j => j.code === 0 && (toast('Đã tạo: ' + j.result.join(', ')), pgRender(e.id))); };
  if ($('#rthumbgo')) $('#rthumbgo').onclick = async () => {
    const v = $('#rvideo'), at = v.currentTime || 1.5;
    await fetch(`/api/p/${e.id}/thumb?at=${at.toFixed(2)}`);
    toast('Đã cập nhật ảnh đại diện'); pgRender(e.id);
  };
  if ($('#rthumbpro')) $('#rthumbpro').onclick = async () => {
    const r = await api(`/api/p/${e.id}/thumb_pro`, { method: 'POST', body: { text: $('#rthumbtext').value || undefined } });
    watch(r.job, $('#rthumbprost'), 'Đang ghép thumbnail', j => {
      if (j.code !== 0) return;
      $('#rthumbprev').innerHTML = `<img src="${j.result.thumb}" style="max-width:260px;border-radius:10px;box-shadow:0 10px 30px #0003">`;
      toast('Đã tạo thumbnail mới');
    });
  };
  const LV = { CHAN: ['err', 'Chặn'], RUI_RO: ['warn', 'Rủi ro'], LUU_Y: ['', 'Lưu ý'] };
  const showAudit = a => {
    const iss = a.issues || [], applied = new Set(a.applied || []);
    const can = i => iss[i].rewrite && (iss[i].field || 'voice_text') !== 'props' && !applied.has(i);
    const todo = iss.map((_, i) => i).filter(can);
    $('#raudit').innerHTML = `<div class="small" style="display:grid;gap:4px;margin-bottom:10px">
        <div>🏷 Nhãn AI: <b>${esc(a.ai_disclosure || '—')}</b></div><div>♻️ Nội dung lặp/không nguyên bản: <b>${esc(a.inauthentic_risk || '—')}</b></div>
        <div>💰 Quảng cáo: <b>${esc(a.ad_friendly || '—')}</b></div><div>📌 <b>${esc(a.status || '')}</b></div></div>
      ${iss.length ? iss.map((it, i) => `<div class="aud"><div><span class="badge ${LV[it.level]?.[0] || ''}">${LV[it.level]?.[1] || esc(it.level)}</span> <b>${it.scene_id ? 'Cảnh ' + it.scene_id : 'Tiêu đề'}</b> · ${esc(it.item)} — ${esc(it.problem)}</div>
          ${it.rewrite ? `<div class="small" style="margin-top:4px">→ <i>${esc(it.rewrite)}</i></div>` : ''}
          ${applied.has(i) ? '<div class="small ok" style="margin-top:4px">✓ đã áp dụng</div>' : can(i) ? `<button class="btn2" data-aud="${i}" style="margin-top:6px">Áp dụng</button>` : it.rewrite ? '<div class="small muted" style="margin-top:4px">Chữ trên màn hình: sửa trong Trình sửa cảnh</div>' : ''}</div>`).join('')
        : '<p class="small ok">✓ Không thấy vấn đề.</p>'}
      ${todo.length > 1 ? `<button class="btn2 pri" id="raudall" style="margin-top:8px">Áp dụng tất cả (${todo.length})</button>` : ''}`;
    const apply = async idx => { const r = await api(`/api/p/${e.id}/audit/apply`, { method: 'POST', body: { idx } });
      showAudit(r.audit); if (r.applied.length) toast(`Đã sửa ${r.applied.length} chỗ — bấm "Giọng đọc" để tạo lại giọng cho cảnh đã đổi lời`); };
    $('#raudit').querySelectorAll('[data-aud]').forEach(b => b.onclick = () => apply([+b.dataset.aud]));
    if ($('#raudall')) $('#raudall').onclick = () => apply(todo);
  };
  if (e.audit) fetch(`/files/${e.id}/out/audit.json?${Date.now()}`).then(r => r.json()).then(showAudit).catch(() => {});
  $('#rauditgo').onclick = async () => {
    if (META.brain.backend === 'manual') return go('settings');
    const r = await api(`/api/p/${e.id}/audit`, { method: 'POST', body: {} });
    watch(r.job, $('#rauditst'), 'Claude đang rà chính sách', j => { if (j.code === 0) showAudit(j.result); });
  };
  $('#rplat').onchange = loadPub;
  $('#rpubgo').onclick = async () => {
    if (META.brain.backend === 'manual') return go('settings');
    const r = await api(`/api/p/${e.id}/publish`, { method: 'POST', body: { platform: $('#rplat').value } });
    watch(r.job, $('#rpubst'), 'Claude đang viết tiêu đề, mô tả, tag', j => { if (j.code === 0) $('#rpub').innerHTML = pubBox(j.result); });
  };
}

/* ================= CÔNG CỤ ================= */
let TSEL = null;
async function pgTools() {
  const files = await api('/api/tools/files');
  const isVid = n => /\.(mp4|mov|mkv|webm|avi)$/i.test(n), isSrt = n => /\.srt$/i.test(n);
  if (!files.some(f => f.name === TSEL)) TSEL = files[0]?.name || null;
  html(page('tools'), `<div class="wrap">
    <div class="ph"><h1>🧰 Công cụ nhanh</h1><span class="badge">Không cần dự án</span></div>
    <p class="lead">Dùng cho video và phụ đề có sẵn: kéo thả file vào, chọn file, bấm công cụ. Kết quả nằm trong <code>workspace/_tools</code>.</p>
    <div class="grid2" style="grid-template-columns:1fr 1.4fr">
      <div class="card"><div class="drop" id="tdrop">⬆ Kéo thả video / .srt vào đây, hoặc bấm để chọn<input type="file" id="tfile" hidden multiple accept="video/*,.srt"></div>
        <div class="files" style="margin-top:12px">${files.map(f => `<div class="fr ${f.name === TSEL ? 'on' : ''}" data-f="${esc(f.name)}">${isVid(f.name) ? '🎬' : isSrt(f.name) ? '💬' : /\.(jpg|png)$/i.test(f.name) ? '🖼' : '🎵'} <span style="flex:1">${esc(f.name)}</span><span class="small muted">${(f.size / 1048576).toFixed(1)} MB</span><a class="btn2" href="/files/_tools/${encodeURIComponent(f.name)}" download onclick="event.stopPropagation()">⬇</a><button class="btn2 danger" data-del="${esc(f.name)}" title="Xoá file này" onclick="event.stopPropagation()">✕</button></div>`).join('') || '<p class="muted small">Chưa có file.</p>'}</div></div>
      <div class="card"><div class="cap">Công cụ cho: ${TSEL ? esc(TSEL) : '(chưa chọn file)'}</div><div class="tools">
        <div class="tool"><b>📐 Đổi khung hình</b><p>Video ngang ↔ dọc, nền làm mờ, không cắt mất hình.</p><select id="toAsp"><option>9:16</option><option>16:9</option><option>1:1</option><option>4:5</option></select><button class="btn2 pri" data-k="reframe" ${TSEL && isVid(TSEL) ? '' : 'disabled'}>Chạy</button></div>
        <div class="tool"><b>🖼 Ảnh thumbnail</b><p>Lấy một khung hình đẹp làm ảnh đại diện.</p><input id="toAt" type="number" value="2" min="0" step="0.5" title="giây"><button class="btn2 pri" data-k="thumbnail" ${TSEL && isVid(TSEL) ? '' : 'disabled'}>Chạy</button></div>
        <div class="tool"><b>🎵 Tách âm thanh</b><p>Xuất file mp3 từ video.</p><button class="btn2 pri" data-k="audio" ${TSEL && isVid(TSEL) ? '' : 'disabled'}>Chạy</button></div>
        <div class="tool"><b>🗜 Nén video</b><p>Giảm dung lượng để gửi nhanh (tối đa 1080p).</p><button class="btn2 pri" data-k="compress" ${TSEL && isVid(TSEL) ? '' : 'disabled'}>Chạy</button></div>
        <div class="tool"><b>💬 Dịch .srt</b><p>Giữ nguyên thời gian, dịch chữ (cần AI).</p><select id="toLang">${langOptions('en')}</select><button class="btn2 pri" data-k="translate_srt" ${TSEL && isSrt(TSEL) ? '' : 'disabled'}>Chạy</button></div>
      </div><div class="st small muted" id="tost" style="margin-top:12px"></div></div>
    </div></div>`);
  const up = async fl => { for (const f of fl) { $('#tost').innerHTML = `<span class="spin"></span>Đang tải lên ${esc(f.name)}…`; await fetch('/api/upload?name=' + encodeURIComponent(f.name), { method: 'POST', body: f }); TSEL = f.name; } pgTools(); };
  const dz = $('#tdrop');
  dz.onclick = () => $('#tfile').click(); $('#tfile').onchange = e => up(e.target.files);
  dz.ondragover = e => { e.preventDefault(); dz.classList.add('over'); }; dz.ondragleave = () => dz.classList.remove('over');
  dz.ondrop = e => { e.preventDefault(); dz.classList.remove('over'); up(e.dataTransfer.files); };
  page('tools').querySelectorAll('.fr').forEach(r => r.onclick = () => { TSEL = r.dataset.f; pgTools(); });
  page('tools').querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
    if (!confirm(`Xoá "${b.dataset.del}"?`)) return;
    await fetch('/api/tools/files?name=' + encodeURIComponent(b.dataset.del), { method: 'DELETE' });
    if (TSEL === b.dataset.del) TSEL = null;
    pgTools();
  });
  page('tools').querySelectorAll('[data-k]').forEach(b => b.onclick = async () => {
    const k = b.dataset.k, opt = { aspect: $('#toAsp').value, at: +$('#toAt').value, lang: $('#toLang').value };
    if (k === 'translate_srt' && META.brain.backend === 'manual') return go('settings');
    const r = await api('/api/tools/run', { method: 'POST', body: { kind: k, src: TSEL, opt } });
    watch(r.job, $('#tost'), 'Đang xử lý', j => { if (j.code === 0) { toast('Xong: ' + j.result); TSEL = j.result; pgTools(); } });
  });
}

/* ================= CÀI ĐẶT ================= */
async function pgSettings() {
  const s = await api('/api/settings'), v = s.values, b = s.brain;
  const sel = (k, opts) => `<select data-s="${k}">${opts.map(([val, n]) => `<option value="${val}" ${String(v[k] ?? '') === String(val) ? 'selected' : ''}>${n}</option>`).join('')}</select>`;
  html(page('settings'), `<div class="wrap">
    <div class="ph"><h1>⚙️ Cài đặt</h1></div>
    <p class="lead">Lưu vào <code>config/settings.local.yaml</code> (riêng máy này, không bị ghi đè khi cập nhật).</p>
    <div class="grid2">
      <div class="card"><div class="cap">🧠 Kết nối AI</div>
        <p style="margin:0 0 10px">Đang dùng: <b>${BRAIN_NAME[b.backend]}</b>${b.cli ? ` <span class="small muted">(${esc(b.cli)})</span>` : ''}</p>
        <label style="margin-top:0">Chế độ</label>${sel('agent.backend', [['', 'Tự chọn (API key → Claude Code → dán tay)'], ['cli', 'Claude Code (gói Claude của bạn)'], ['api', 'API key'], ['manual', 'Chỉ dán tay qua claude.ai']])}
        <div class="tintbox"><b>Claude Desktop</b><p class="small muted" style="margin:4px 0 8px">Chat "tìm chủ đề hot và làm 1 video" ngay trong Claude Desktop (mọi gói).</p><button class="btn2 pri" id="smcp">Kết nối Claude Desktop</button> <span class="small muted" id="smcpst"></span></div>
        <div class="tintbox"><b>Claude Code</b> <span class="small muted">(gói Pro/Max)</span><p class="small muted" style="margin:4px 0 6px">Cài trong PowerShell rồi gõ <code>claude</code> một lần để đăng nhập:</p><code style="display:block;background:#fff;padding:6px 9px;border-radius:7px;font-size:12.5px">irm https://claude.ai/install.ps1 | iex</code></div></div>
      <div class="card"><div class="cap">🤖 Model AI cho từng việc</div>
        <p class="small muted" style="margin:0 0 8px">Việc cần sáng tạo dùng model mạnh, việc lặp lại dùng model nhẹ để tiết kiệm lượt dùng của gói Claude (hoặc tiền API).</p>
        ${[['plan', '✍️ Viết kịch bản'], ['ideas', '🔥 Tìm & chấm chủ đề (tra web)'], ['edit', '🎛 Sửa cảnh bằng lời'], ['translate', '🌐 Dịch lồng tiếng'], ['subtitles', '💬 Phụ đề thêm, dịch .srt'], ['publish', '🚀 Gói đăng (tiêu đề, mô tả, tag)'], ['audit', '🛡 Kiểm duyệt chính sách'], ['cinema', '🎬 Điện ảnh (storyboard + code cảnh)']]
          .map(([k, n]) => `<div class="row" style="margin-top:6px"><span style="flex:1.3">${n}</span>${sel('agent.tiers.' + k, [['opus', 'Opus · mạnh nhất'], ['sonnet', 'Sonnet · cân bằng'], ['haiku', 'Haiku · nhanh, nhẹ']])}</div>`).join('')}
        <div class="row" style="margin-top:6px"><span style="flex:1.3">🎨 Ảnh AI (GPU, không dùng Claude)</span>${sel('visual.default_workflow', (s.workflows || ['sdxl_image']).map(w => [w, w]))}</div></div>
      <div class="card"><div class="cap">🎙 Giọng đọc &amp; phụ đề</div>
        <label style="margin-top:0">Bộ tạo giọng</label>${sel('tts.engine', [['auto', 'Tự động: Edge TTS, lỗi thì gTTS'], ['edge', 'Chỉ Edge TTS'], ['gtts', 'Chỉ gTTS'], ['piper', 'Piper (offline)'], ['silent', 'Không tiếng (chỉ để thử hình)']])}
        <label>Tốc độ đọc</label>${sel('tts.rate', [['-10%', 'Chậm hơn'], ['+0%', 'Bình thường'], ['+10%', 'Nhanh hơn'], ['+20%', 'Rất nhanh']])}
        <div class="row"><div><label>Kiểu phụ đề</label>${sel('render.captions_mode', [['auto', 'Tự chọn'], ['html', 'Vẽ trong khung hình'], ['ass', 'ffmpeg/libass']])}</div><div><label>Số từ mỗi cụm</label>${sel('render.caption_words', [[3, '3'], [4, '4'], [5, '5'], [6, '6']])}</div></div></div>
      <div class="card"><div class="cap">🎬 Render</div>
        <div class="row"><div><label style="margin-top:0">Số cảnh quay song song</label>${sel('render.workers', [[1, '1 (máy yếu)'], [2, '2'], [3, '3'], [4, '4']])}</div><div><label style="margin-top:0">Bộ mã hoá</label>${sel('render.encoder', [['auto', 'Tự chọn'], ['h264_qsv', 'Intel QSV'], ['h264_nvenc', 'NVIDIA NVENC'], ['libx264', 'CPU (x264)']])}</div></div>
        <div class="row"><div><label>FPS</label>${sel('fps', [[24, '24'], [30, '30'], [60, '60']])}</div><div><label>Nhạc nền mặc định</label><input data-s="render.music" value="${esc(v['render.music'] || '')}" placeholder="đường dẫn mp3"></div></div></div>
      <div class="card"><div class="cap">📐 Mặc định &amp; nguồn xu hướng</div>
        <div class="row"><div><label style="margin-top:0">Phong cách</label>${sel('default_style', s.styles.map(x => [x, x]))}</div><div><label style="margin-top:0">Khung hình</label>${sel('default_aspect', [['9:16', '9:16'], ['16:9', '16:9'], ['1:1', '1:1'], ['4:5', '4:5']])}</div><div><label style="margin-top:0">Ngôn ngữ</label><select data-s="default_lang">${langOptions(v.default_lang)}</select></div></div>
        <label>Khi đóng tab Studio</label>${sel('studio.auto_exit', [['true', 'Tự tắt máy chủ (giải phóng cổng 8765)'], ['false', 'Giữ máy chủ chạy (vd để Claude Desktop dùng)']])}
        <label>YouTube API key (tuỳ chọn, thêm nguồn YouTube Most Popular)</label><input data-s="trends.youtube_api_key" value="${esc(v['trends.youtube_api_key'] || '')}" placeholder="AIza…"></div>
    </div>
    <div class="card" style="margin-top:16px"><div class="runbar"><button class="gbtn" id="ssave">Lưu cài đặt</button><span class="st" id="sst"></span></div></div></div>`);
  $('#ssave').onclick = async () => {
    const values = {}; page('settings').querySelectorAll('[data-s]').forEach(el => { let x = el.value; if (/^\d+$/.test(x)) x = +x; if (x === 'true') x = true; if (x === 'false') x = false; values[el.dataset.s] = x; });
    await api('/api/settings', { method: 'POST', body: { values } });
    META = await api('/api/meta'); renderAiChip(); toast('Đã lưu cài đặt'); pgSettings();
  };
  $('#smcp').onclick = async () => { const r = await api('/api/mcp-install', { method: 'POST', body: {} }); $('#smcpst').textContent = r.ok ? 'Đã kết nối. Thoát hẳn Claude Desktop rồi mở lại.' : 'Lỗi: ' + r.log; };
}

/* báo máy chủ tab còn mở; đóng tab thì máy chủ tự tắt (Cài đặt: studio.auto_exit) */
const TAB_ID = Math.random().toString(36).slice(2, 10);
const ping = () => fetch('/api/ping', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tab: TAB_ID }) })
  .then(r => r.json()).then(r => { if (r.stale) staleBanner(); }).catch(() => {});
/* sau git pull: giao diện đã mới nhưng máy chủ Python vẫn là bản cũ → mời khởi động lại */
function staleBanner() {
  if ($('#stale')) return;
  const d = document.createElement('div');
  d.id = 'stale';
  d.innerHTML = '🔄 Studio vừa được cập nhật code mới. Khởi động lại để dùng bản mới (video và cài đặt giữ nguyên). <button class="btn2 pri">Khởi động lại</button>';
  Object.assign(d.style, { position: 'fixed', top: '10px', left: '50%', transform: 'translateX(-50%)', zIndex: 9999, background: '#fff7ed', border: '1px solid #fdba74', color: '#7c2d12', padding: '8px 14px', borderRadius: '12px', boxShadow: '0 8px 24px #0002', display: 'flex', gap: '10px', alignItems: 'center', fontSize: '14px' });
  document.body.appendChild(d);
  d.querySelector('button').onclick = async () => {
    const r = await api('/api/restart', { method: 'POST', body: {} });
    if (r.error) return toast(r.error, true);
    d.innerHTML = '<span class="spin"></span> Đang khởi động lại…';
    for (let i = 0; i < 30; i++) { await new Promise(z => setTimeout(z, 1000)); try { const m = await fetch('/api/meta'); if (m.ok) return location.reload(); } catch { } }
    d.textContent = 'Không khởi động lại được: mở lại bằng shortcut AI Workflow Studio.';
  };
}
ping(); setInterval(ping, 5000);
document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && ping());
window.addEventListener('pagehide', () => navigator.sendBeacon('/api/bye', JSON.stringify({ tab: TAB_ID })));

appBoot();
