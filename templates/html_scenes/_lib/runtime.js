/* AI Workflow runtime: tua thời gian tất định cho mọi template.
 * Template gọi VF.scene({ setup(input, root), draw(t) }).
 * - Engine (Playwright) gọi window.__vfSeek(t) cho từng khung hình.
 * - Web Studio gửi postMessage {type:'vf-input'|'vf-seek'|'vf-play'} để xem thử.
 * - Mở trực tiếp file với ?play=1 sẽ chạy lặp bằng props mẫu (data-demo trong template).
 */
(function () {
  const qs = new URLSearchParams(location.search);
  let def = null, input = null, root = null, playing = false, t0 = 0;

  const ease = {
    linear: x => x,
    in: x => x * x * x,
    out: x => 1 - Math.pow(1 - x, 3),
    inOut: x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    back: x => { const c = 1.70158; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
    elastic: x => (x === 0 || x === 1 ? x : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (2 * Math.PI / 3)) + 1),
  };
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  /** tiến độ 0..1 của đoạn [start, start+dur] tại t, có easing */
  const prog = (t, start, dur, e = 'out') => ease[e](clamp((t - start) / Math.max(dur, 1e-6)));

  function el(tag, attrs = {}, parent = null, svg = false) {
    const n = svg || ['svg', 'g', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'text', 'ellipse', 'defs', 'linearGradient', 'radialGradient', 'stop', 'tspan', 'image', 'clipPath', 'mask', 'filter', 'use'].includes(tag)
      ? document.createElementNS('http://www.w3.org/2000/svg', tag) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'text') n.textContent = v;
      else if (k === 'html') n.innerHTML = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(n.style, v);
      else n.setAttribute(k, v);
    }
    if (parent) parent.appendChild(n);
    return n;
  }

  function demoInput() {
    const tag = document.querySelector('script[type="application/json"][data-demo]');
    const demo = tag ? JSON.parse(tag.textContent) : {};
    const portrait = qs.get('ar') !== '16:9';
    return Object.assign({
      props: {}, style: {}, cast: {}, acting: [], words: [], duration: 5,
      width: portrait ? 1080 : 1920, height: portrait ? 1920 : 1080, camera: 'none', text: '',
    }, demo);
  }

  function applyStyle(st) {
    const r = document.documentElement.style;
    r.setProperty('--bg', st.bg || '#fff');
    r.setProperty('--ink', st.ink || '#111');
    r.setProperty('--paper', st.paper || st.bg || '#fff');
    (st.accent || ['#ff3b30', '#0a84ff', '#ffcc00']).forEach((c, i) => r.setProperty(`--a${i + 1}`, c));
    r.setProperty('--font', st.font || "'Segoe UI', Arial, sans-serif");
    r.setProperty('--title-font', st.title_font || st.font || "'Segoe UI', Arial, sans-serif");
    r.setProperty('--W', input.width + 'px');
    r.setProperty('--H', input.height + 'px');
    document.body.classList.toggle('portrait', input.height > input.width);
  }

  function init(newInput) {
    input = newInput || window.VF_INPUT || demoInput();
    input.style = input.style || {};
    applyStyle(input.style);
    document.body.style.margin = 0;
    document.body.style.overflow = 'hidden';
    if (root) root.remove();
    root = el('div', { id: 'vf-root' }, document.body);
    Object.assign(root.style, { position: 'relative', width: input.width + 'px', height: input.height + 'px', overflow: 'hidden', background: 'var(--bg)', transformOrigin: '50% 50%' });
    if (qs.has('studio') || qs.has('play')) fit();
    if (input.style.texture) root.classList.add('tex-' + input.style.texture);
    def && def.setup && def.setup(input, root, VF);
    setupCaptions();
    seek(0);
    // template có thể đăng ký việc chờ (vd ảnh nhân vật 3D) bằng VF.waitFor(promise): chỉ báo sẵn sàng khi xong
    const pend = VF._pending.splice(0);
    if (pend.length) Promise.allSettled(pend).then(() => { seek(0); window.__vfReady = true; });
    else window.__vfReady = true;
  }

  function fit() { // thu nhỏ khung cho vừa iframe khi xem thử
    const s = Math.min(innerWidth / input.width, innerHeight / input.height);
    document.body.style.transform = `scale(${s})`;
    document.body.style.transformOrigin = '0 0';
  }

  function camera(t) {
    const d = input.duration || 5, k = ease.inOut(clamp(t / d));
    const cam = input.camera || 'none';
    const m = { zoom_in: `scale(${1 + 0.08 * k})`, zoom_out: `scale(${1.08 - 0.08 * k})`,
      pan_left: `scale(1.06) translateX(${2.5 - 5 * k}%)`, pan_right: `scale(1.06) translateX(${-2.5 + 5 * k}%)` };
    root.style.transform = m[cam] || '';
  }

  /* Phụ đề karaoke vẽ trong khung hình (khi ffmpeg không có libass). */
  let cap = null;
  function setupCaptions() {
    const c = input.captions;
    cap = null;
    if (!c || !(input.words || []).length) return;
    const H = input.height, size = (c.size ?? 0.045) < 1 ? (c.size ?? 0.045) * H : c.size;
    const box = el('div', { class: 'vf-cap' }, root);
    Object.assign(box.style, { position: 'absolute', left: '6%', right: '6%', bottom: (c.y ?? 0.2) * H + 'px', zIndex: 70, textAlign: 'center',
      font: `900 ${size}px ${c.font ? `'${c.font}', ` : ''}var(--title-font)`, lineHeight: 1.15, color: c.color || '#fff',
      textShadow: [[2, 0], [-2, 0], [0, 2], [0, -2], [2, 2], [-2, -2], [2, -2], [-2, 2]].map(([x, y]) => `${x * size / 22}px ${y * size / 22}px 0 ${c.outline || '#000'}`).join(','),
      textTransform: c.upper ? 'uppercase' : 'none' });
    cap = { box, c, n: c.chunk || 4, last: '' };
  }
  function drawCaptions(t) {
    if (!cap) return;
    const w = input.words, i = wordAt(t);
    if (i < 0 || t > w[w.length - 1].end + 0.4) { if (cap.last) { cap.box.innerHTML = ''; cap.last = ''; } return; }
    const gr = (cap.c.groups || []).find(([a, b]) => i >= a && i < b) || [Math.floor(i / cap.n) * cap.n, Math.floor(i / cap.n) * cap.n + cap.n];
    const g0 = gr[0], grp = w.slice(gr[0], gr[1]);
    const key = g0 + ':' + i;
    if (key === cap.last) return;
    cap.last = key;
    const esc = s => String(s).replace(/[&<>]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[ch]));
    cap.box.innerHTML = grp.map((x, k) => g0 + k === i ? `<span style="color:${cap.c.highlight || '#ffd400'}">${esc(x.word)}</span>` : esc(x.word)).join(cap.c.joiner ?? ' ');
  }

  function seek(t) {
    for (const a of document.getAnimations ? document.getAnimations() : []) { a.pause(); a.currentTime = t * 1000; }
    if (window.gsap) { gsap.globalTimeline.pause(); gsap.globalTimeline.time(t); }
    def && def.draw && def.draw(t, input, VF);
    drawCaptions(t);
    camera(t);
  }

  /** chỉ số từ đang đọc tại t (-1 nếu chưa) */
  function wordAt(t) {
    const w = input.words || [];
    let i = -1;
    for (let k = 0; k < w.length; k++) if (w[k].start <= t) i = k;
    return i;
  }

  /** 'từ trong lời đọc' | '60%' | 2.5 -> giây (giống engine/align.resolve_at) */
  function at(v, dflt = 0) {
    if (v === undefined || v === null || v === '') return dflt;
    if (typeof v === 'number') return v;
    const s = String(v).trim(), d = input.duration || 5;
    if (s.endsWith('%')) return d * parseFloat(s) / 100;
    if (!isNaN(parseFloat(s)) && /^[\d.]+$/.test(s)) return parseFloat(s);
    const norm = x => x.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
    const target = s.split(/\s+/).map(norm), w = (input.words || []).map(x => norm(x.word));
    for (let i = 0; i + target.length <= w.length; i++)
      if (target.every((x, k) => w[i + k] === x)) return input.words[i].start;
    return dflt;
  }

  function loop() {
    if (!playing) return;
    const t = ((performance.now() - t0) / 1000) % (input.duration || 5);
    seek(t);
    requestAnimationFrame(loop);
  }

  window.addEventListener('resize', () => { if (input && (qs.has('studio') || qs.has('play'))) fit(); });

  window.addEventListener('message', e => {
    const m = e.data || {};
    if (m.type === 'vf-input') { init(m.input); }
    if (m.type === 'vf-seek') { playing = false; seek(m.t); }
    if (m.type === 'vf-play') { playing = true; t0 = performance.now() - (m.from || 0) * 1000; loop(); }
  });

  window.VF = {
    ease, clamp, lerp, prog, el, wordAt, at,
    _pending: [], waitFor(p) { this._pending.push(p); return p; },
    get input() { return input; },
    scene(d) {
      def = d;
      const go = () => { init(); if (qs.has('play')) { playing = true; t0 = performance.now(); loop(); } };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
    },
  };
  window.__vfSeek = seek;
})();
