/* Rig người que 11 khớp (tương thích actions.json).
 * Góc (độ): 0 = buông thẳng xuống, 90 = chỉa ngang ra trước, 180 = giơ thẳng lên, >180 = lên và ra sau, âm = ra sau.
 * Tay cộng thêm 'lean' (theo thân); chân là góc tuyệt đối; lift nhấc cả người (nhảy).
 * Nhìn 3/4: tay/chân phía sau lệch nhẹ ra sau để không chồng lên tay/chân trước.
 * Nhân vật: build slim|normal|round, hair short|long|ponytail|bun|spiky|curly|bald, outfit shirt|dress|coat,
 * accessories [glasses, tie, bowtie, scarf, mustache, beard, headphones, backpack], skin (màu đầu), hat, shirt, scale.
 * Khẩu hình nhép theo mốc từ khi nhân vật đang nói; emote (! ? ❤ 💡 💢 💧 zzz ♪ ✨) bật lên trên đầu.
 */
(function () {
  const { el, clamp, lerp, ease } = VF;
  const R = Math.PI / 180;
  const KEYS = ['lean', 'head', 'lift', 'fa1', 'fa2', 'ba1', 'ba2', 'fl1', 'fl2', 'bl1', 'bl2'];
  const STAND = { lean: 0, head: 0, lift: 0, fa1: 10, fa2: 6, ba1: -10, ba2: -6, fl1: 5, fl2: 0, bl1: -5, bl2: 0 };
  const TALK_ACTS = new Set(['talk', 'explain', 'present', 'point', 'phone_call', 'laugh', 'shrug', 'give', 'wave', 'think']);

  const mix = (a, b, k) => { const o = {}; for (const key of KEYS) o[key] = lerp(a[key] ?? STAND[key], b[key] ?? STAND[key], k); return o; };
  const full = p => Object.assign({}, STAND, p);

  // Mỗi nhóm hành động có "tính khí" chuyển động riêng thay vì luôn dùng inOut đều đều:
  // out = bật nhanh rồi chùng (nảy, vui); back = hất quá đà rồi hồi (giật mình, kịch tính);
  // elastic = đàn hồi (lắc lư); linear = đều tay (đi bộ, làm việc).
  const ACT_EASE = {
    jump: 'out', cheer: 'out', celebrate: 'out', clap: 'out', high_five: 'out', thumbs_up: 'out',
    laugh: 'out', dance: 'out', fall: 'out', push: 'out', fight: 'out',
    shocked: 'back', scared: 'back', surprised: 'back', facepalm: 'back', head_scratch: 'back',
    angry: 'back', salute: 'back',
    walk: 'linear', run: 'linear', sneak: 'linear', work: 'linear', read: 'linear', think: 'linear', sleep: 'linear',
  };
  const WALK_ACTS = new Set(['walk', 'run', 'sneak']);

  function sample(action, local, name) {
    const fr = action.frames;
    if (!fr || !fr.length) return { ...STAND };
    if (fr.length === 1) return full(fr[0].pose);
    const total = fr.reduce((s, f) => s + (f.dur || 0.4), 0);
    let x = action.loop ? local % total : Math.min(local, total);
    const easeFn = ease[ACT_EASE[name]] || ease.inOut;
    for (let i = 0; i < fr.length; i++) {
      const d = fr[i].dur || 0.4;
      if (x <= d || i === fr.length - 1) {
        const nxt = action.loop ? fr[(i + 1) % fr.length] : fr[Math.min(i + 1, fr.length - 1)];
        const p = mix(full(fr[i].pose), full(nxt.pose), easeFn(clamp(x / d)));
        if (action.loop && WALK_ACTS.has(name)) p._walk = (x / d + i) / fr.length;
        return p;
      }
      x -= d;
    }
    return full(fr[fr.length - 1].pose);
  }

  const PROPS = {
    book: (g, c) => { el('rect', { x: -14, y: -20, width: 34, height: 26, rx: 2, fill: c.a1, stroke: c.ink, 'stroke-width': 3 }, g); el('line', { x1: 3, y1: -20, x2: 3, y2: 6, stroke: c.ink, 'stroke-width': 2 }, g); },
    phone: (g, c) => { el('rect', { x: -8, y: -28, width: 18, height: 32, rx: 4, fill: '#222', stroke: c.ink, 'stroke-width': 2 }, g); el('rect', { x: -5, y: -24, width: 12, height: 22, fill: c.a2 }, g); },
    coin: (g) => { el('circle', { cx: 4, cy: -10, r: 13, fill: '#f5c518', stroke: '#a77d00', 'stroke-width': 3 }, g); el('text', { x: 4, y: -4, 'text-anchor': 'middle', 'font-size': 16, 'font-weight': 900, fill: '#a77d00', text: '$' }, g); },
    money: (g) => { el('rect', { x: -18, y: -18, width: 40, height: 22, rx: 3, fill: '#4caf50', stroke: '#1b5e20', 'stroke-width': 3 }, g); el('circle', { cx: 2, cy: -7, r: 6, fill: 'none', stroke: '#1b5e20', 'stroke-width': 2 }, g); },
    gift: (g, c) => { el('rect', { x: -18, y: -30, width: 36, height: 30, fill: c.a1, stroke: c.ink, 'stroke-width': 3 }, g); el('rect', { x: -3, y: -30, width: 6, height: 30, fill: c.a3 }, g); el('rect', { x: -18, y: -18, width: 36, height: 6, fill: c.a3 }, g); },
    bulb: (g, c) => { el('circle', { cx: 0, cy: -26, r: 16, fill: '#ffe066', stroke: c.ink, 'stroke-width': 3 }, g); el('rect', { x: -7, y: -12, width: 14, height: 10, fill: '#999', stroke: c.ink, 'stroke-width': 2 }, g); },
    sign: (g, c, txt) => { el('line', { x1: 0, y1: 10, x2: 0, y2: -60, stroke: '#8d6e63', 'stroke-width': 5 }, g); el('rect', { x: -50, y: -100, width: 100, height: 46, rx: 4, fill: '#fff', stroke: c.ink, 'stroke-width': 3 }, g); el('text', { x: 0, y: -70, 'text-anchor': 'middle', 'font-size': 20, 'font-weight': 800, fill: c.ink, text: txt || '!' }, g); },
    laptop: (g) => { el('rect', { x: -26, y: -30, width: 44, height: 28, rx: 3, fill: '#333' }, g); el('rect', { x: -30, y: -2, width: 52, height: 6, rx: 2, fill: '#666' }, g); },
    cup: (g, c) => { el('path', { d: 'M-10 -24 L10 -24 L8 2 L-8 2 Z', fill: '#fff', stroke: c.ink, 'stroke-width': 3 }, g); el('path', { d: 'M10 -18 q10 2 0 12', fill: 'none', stroke: c.ink, 'stroke-width': 3 }, g); },
    flag: (g, c) => { el('line', { x1: 0, y1: 10, x2: 0, y2: -80, stroke: c.ink, 'stroke-width': 4 }, g); el('path', { d: 'M0 -80 L46 -68 L0 -54 Z', fill: c.a1 }, g); },
    sword: (g) => { el('line', { x1: 0, y1: 0, x2: 0, y2: -80, stroke: '#cfd8dc', 'stroke-width': 7 }, g); el('line', { x1: -14, y1: -4, x2: 14, y2: -4, stroke: '#795548', 'stroke-width': 6 }, g); },
    key: (g) => { el('circle', { cx: 0, cy: -20, r: 9, fill: 'none', stroke: '#f5c518', 'stroke-width': 5 }, g); el('line', { x1: 0, y1: -11, x2: 0, y2: 14, stroke: '#f5c518', 'stroke-width': 5 }, g); },
    star: (g, c) => { el('path', { d: 'M0 -40 L9 -16 L34 -16 L14 -2 L22 22 L0 8 L-22 22 L-14 -2 L-34 -16 L-9 -16 Z', transform: 'scale(.7) translate(0,-14)', fill: '#ffd400', stroke: c.ink, 'stroke-width': 3 }, g); },
    trophy: (g, c) => { el('path', { d: 'M-16 -40 H16 V-24 Q16 -8 0 -6 Q-16 -8 -16 -24 Z', fill: '#f5c518', stroke: c.ink, 'stroke-width': 3 }, g); el('rect', { x: -8, y: -6, width: 16, height: 8, fill: '#a77d00' }, g); },
    magnifier: (g, c) => { el('circle', { cx: 0, cy: -34, r: 16, fill: 'rgba(160,220,255,.5)', stroke: c.ink, 'stroke-width': 4 }, g); el('line', { x1: 0, y1: -18, x2: 0, y2: 6, stroke: c.ink, 'stroke-width': 6 }, g); },
    map: (g, c) => { el('path', { d: 'M-24 -30 L-8 -24 L8 -30 L24 -24 L24 4 L8 -2 L-8 4 L-24 -2 Z', fill: '#f3e5ab', stroke: c.ink, 'stroke-width': 3 }, g); },
    briefcase: (g, c) => { el('rect', { x: -20, y: 0, width: 40, height: 28, rx: 3, fill: '#6d4c41', stroke: c.ink, 'stroke-width': 3 }, g); el('path', { d: 'M-7 0 v-6 h14 v6', fill: 'none', stroke: c.ink, 'stroke-width': 3 }, g); },
    microphone: (g, c) => { el('rect', { x: -4, y: -6, width: 8, height: 24, rx: 3, fill: '#333' }, g); el('circle', { cx: 0, cy: -12, r: 10, fill: '#9e9e9e', stroke: c.ink, 'stroke-width': 3 }, g); },
    pen: (g) => { el('line', { x1: 0, y1: 6, x2: 0, y2: -30, stroke: '#1565c0', 'stroke-width': 6, 'stroke-linecap': 'round' }, g); },
    pizza: (g, c) => { el('path', { d: 'M-16 -30 L16 -30 L0 6 Z', fill: '#ffcc80', stroke: c.ink, 'stroke-width': 3 }, g); el('circle', { cx: -4, cy: -22, r: 3, fill: '#e53935' }, g); el('circle', { cx: 5, cy: -16, r: 3, fill: '#e53935' }, g); },
    umbrella: (g, c) => { el('line', { x1: 0, y1: 8, x2: 0, y2: -70, stroke: c.ink, 'stroke-width': 4 }, g); el('path', { d: 'M-40 -66 Q0 -110 40 -66 Z', fill: c.a2, stroke: c.ink, 'stroke-width': 3 }, g); },
  };

  const MOUTH = {
    neutral: 'M-7 9 L7 9', happy: 'M-9 6 Q0 16 9 6', proud: 'M-9 6 Q0 15 9 6', sad: 'M-8 12 Q0 4 8 12',
    angry: 'M-8 11 Q0 6 8 11', tired: 'M-6 10 L6 10', curious: 'M-5 9 Q2 12 7 8', scared: 'M-6 8 Q0 2 6 8 Q0 15 -6 8',
    love: 'M-9 6 Q0 16 9 6', laugh: 'M-10 5 Q0 20 10 5 Z', surprised: null,
  };
  const EMOTE = { '!': ['!', '#e53935'], '?': ['?', '#1e88e5'], '❤': ['❤', '#e91e63'], '💡': ['💡'], '💢': ['💢'], '💧': ['💧'],
    zzz: ['z z', '#5c6bc0'], '♪': ['♪', '#8e24aa'], '✨': ['✨'], '💦': ['💦'], '...': ['…', '#555'] };

  let SEED = 0;
  class Stick {
    constructor(parent, char, size, colors) {
      this.c = Object.assign({ head: 'hollow', ink: colors.ink, shirt: 'none', hat: 'none', hair: null, build: 'normal', outfit: 'shirt',
        accessories: [], scale: 1, face: true, line: 0 }, char);
      if (this.c.hat === 'hair' && !this.c.hair) { this.c.hair = 'short'; this.c.hat = 'none'; }
      this.seed = (SEED++) * 1.37;
      this.col = colors;
      this.S = size * (this.c.scale || 1);
      const S = this.S, c = this.c;
      this.g = el('g', { class: 'stick' }, parent);
      const w = c.line || Math.max(4, S * 0.026);
      this.w = w;
      const st = { stroke: c.ink, 'stroke-width': w, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', fill: 'none' };
      this.seat = el('path', { fill: 'none', stroke: c.ink, 'stroke-width': w * 0.8, 'stroke-linecap': 'round', opacity: 0 }, this.g);
      this.shadow = el('ellipse', { rx: S * 0.14, ry: S * 0.018, fill: 'rgba(0,0,0,.12)' }, this.g);
      this.hairBack = el('path', { fill: c.hair_color || c.hat_color || '#3e2723', opacity: 0 }, this.g);
      this.accBack = el('g', {}, this.g);
      this.backArm = el('polyline', { ...st, opacity: 0.85 }, this.g);
      this.backHand = el('circle', { r: w * 0.75, fill: c.ink, opacity: 0.85 }, this.g);
      this.backLeg = el('polyline', { ...st, opacity: 0.85 }, this.g);
      this.backFoot = el('line', { ...st, opacity: 0.85 }, this.g);
      this.torso = el('polyline', st, this.g);
      const cloth = c.shirt && c.shirt !== 'none' ? c.shirt : (c.outfit === 'dress' ? colors.a1 : null);
      if (cloth || c.build === 'round') this.body = el('path', { fill: cloth || 'var(--bg)', stroke: c.ink, 'stroke-width': w * 0.6, 'stroke-linejoin': 'round' }, this.g);
      this.acc = el('g', {}, this.g);
      this.frontLeg = el('polyline', st, this.g);
      this.frontFoot = el('line', st, this.g);
      this.headG = el('g', {}, this.g);
      const r = S * 0.095;
      this.r = r;
      const headFill = c.skin || (c.head === 'filled' ? (c.head_fill || '#fff') : c.head === 'solid' ? c.ink : 'var(--bg)');
      el('circle', { r, fill: headFill, stroke: c.ink, 'stroke-width': w }, this.headG);
      this.faceG = el('g', {}, this.headG);
      this.hatG = el('g', {}, this.headG);
      this.drawHair(r, w);
      this.drawHat(r, w);
      this.propG = el('g', {}, this.g);
      this.frontArm = el('polyline', st, this.g);
      this.frontHand = el('circle', { r: w * 0.8, fill: c.ink }, this.g);
      this.emoteG = el('g', { opacity: 0 }, parent);
      this.bubble = el('g', { opacity: 0 }, parent);
      this._face = null; this._hold = null; this._emote = null;
    }

    drawHair(r, w) {
      const g = this.hatG, c = this.c, hc = c.hair_color || c.hat_color || '#3e2723';
      const H = {
        short: `M${-r * 1.05} ${-r * 0.1} Q${-r} ${-r * 1.3} ${r * 0.2} ${-r * 1.08} Q${r * 1.2} ${-r * 0.9} ${r * 1.05} ${-r * 0.2} Q${r * 0.3} ${-r * 0.75} ${-r * 1.05} ${-r * 0.1} Z`,
        spiky: `M${-r * 1.02} ${-r * 0.2} L${-r * 0.9} ${-r * 1.25} L${-r * 0.45} ${-r * 0.85} L${-r * 0.2} ${-r * 1.45} L${r * 0.15} ${-r * 0.9} L${r * 0.55} ${-r * 1.35} L${r * 0.7} ${-r * 0.75} L${r * 1.15} ${-r * 0.95} L${r * 1.0} ${-r * 0.3} Q${0} ${-r * 0.75} ${-r * 1.02} ${-r * 0.2} Z`,
        curly: [[-0.8, -0.55], [-0.45, -0.9], [0, -1.02], [0.45, -0.9], [0.8, -0.55], [-1, -0.15]].map(([x, y]) => `M${(x - 0.3) * r} ${y * r} a${r * 0.3} ${r * 0.3} 0 1 0 ${r * 0.6} 0 a${r * 0.3} ${r * 0.3} 0 1 0 ${-r * 0.6} 0`).join(' '),
        bun: `M${-r * 1.05} ${-r * 0.1} Q${-r} ${-r * 1.25} ${r * 0.2} ${-r * 1.08} Q${r * 1.2} ${-r * 0.9} ${r * 1.05} ${-r * 0.2} Q${r * 0.3} ${-r * 0.7} ${-r * 1.05} ${-r * 0.1} Z M${-r * 1.15} ${-r * 0.95} a${r * 0.38} ${r * 0.38} 0 1 0 ${r * 0.76} 0 a${r * 0.38} ${r * 0.38} 0 1 0 ${-r * 0.76} 0`,
      };
      const h = c.hair;
      if (!h || h === 'bald') return;
      const top = H[h === 'long' || h === 'ponytail' ? 'short' : h] || H.short;
      el('path', { d: top, fill: hc, stroke: c.ink, 'stroke-width': w * 0.35 }, g);
      if (h === 'long') { this.hairBack.setAttribute('opacity', 1); this.hairLong = true; }
      if (h === 'ponytail') { this.hairBack.setAttribute('opacity', 1); this.hairTail = true; }
    }

    drawHat(r, w) {
      const g = this.hatG, c = this.c, hc = c.hat_color || (c.hat === 'tophat' ? '#222' : this.col.a1);
      if (c.hat === 'beanie') el('path', { d: `M${-r * 1.02} ${-r * 0.15} A${r} ${r} 0 0 1 ${r * 1.02} ${-r * 0.15} L${r * 1.08} ${-r * 0.05} L${-r * 1.08} ${-r * 0.05} Z`, fill: hc, stroke: c.ink, 'stroke-width': w * 0.7 }, g);
      if (c.hat === 'cap') { el('path', { d: `M${-r} ${-r * 0.2} A${r} ${r} 0 0 1 ${r} ${-r * 0.2} Z`, fill: hc, stroke: c.ink, 'stroke-width': w * 0.6 }, g); el('path', { d: `M${r * 0.6} ${-r * 0.22} L${r * 1.7} ${-r * 0.1}`, stroke: c.ink, 'stroke-width': w * 1.2, 'stroke-linecap': 'round' }, g); }
      if (c.hat === 'crown') el('path', { d: `M${-r * 0.8} ${-r * 0.75} L${-r * 0.8} ${-r * 1.5} L${-r * 0.4} ${-r * 1.1} L0 ${-r * 1.6} L${r * 0.4} ${-r * 1.1} L${r * 0.8} ${-r * 1.5} L${r * 0.8} ${-r * 0.75} Z`, fill: '#ffd400', stroke: c.ink, 'stroke-width': w * 0.5 }, g);
      if (c.hat === 'helmet') el('path', { d: `M${-r * 1.1} ${-r * 0.05} A${r * 1.1} ${r * 1.15} 0 0 1 ${r * 1.1} ${-r * 0.05} Z`, fill: hc || '#90a4ae', stroke: c.ink, 'stroke-width': w * 0.6 }, g);
      if (c.hat === 'tophat') { el('rect', { x: -r * 0.65, y: -r * 2.1, width: r * 1.3, height: r * 1.3, fill: hc || '#222', stroke: c.ink, 'stroke-width': w * 0.5 }, g); el('rect', { x: -r * 1.05, y: -r * 0.9, width: r * 2.1, height: r * 0.22, rx: r * 0.1, fill: hc || '#222' }, g); }
      if (c.hat === 'chef') el('path', { d: `M${-r * 0.75} ${-r * 0.75} Q${-r * 1.3} ${-r * 1.7} ${-r * 0.4} ${-r * 1.75} Q0 ${-r * 2.3} ${r * 0.4} ${-r * 1.75} Q${r * 1.3} ${-r * 1.7} ${r * 0.75} ${-r * 0.75} Z`, fill: '#fff', stroke: c.ink, 'stroke-width': w * 0.5 }, g);
      if (c.hat === 'graduation') { el('path', { d: `M${-r * 1.3} ${-r * 0.95} L0 ${-r * 1.4} L${r * 1.3} ${-r * 0.95} L0 ${-r * 0.55} Z`, fill: '#222', stroke: c.ink, 'stroke-width': w * 0.4 }, g); el('line', { x1: r * 0.6, y1: -r, x2: r * 0.75, y2: -r * 0.3, stroke: '#f5c518', 'stroke-width': w * 0.5 }, g); }
      const A = c.accessories || [];
      const s = r / 26, ink = c.ink;
      if (A.includes('headphones')) { el('path', { d: `M${-r * 1.05} ${-r * 0.1} A${r * 1.1} ${r * 1.1} 0 0 1 ${r * 1.05} ${-r * 0.1}`, fill: 'none', stroke: '#333', 'stroke-width': w * 0.8 }, g); el('rect', { x: -r * 1.25, y: -r * 0.3, width: r * 0.4, height: r * 0.65, rx: r * 0.15, fill: this.col.a1 }, g); }
      this._accHead = { glasses: A.includes('glasses'), mustache: A.includes('mustache'), beard: A.includes('beard'), s, ink };
    }

    drawFace(mood, blink, open) {
      if (!this.c.face) return;
      const key = mood + (blink ? ':b' : '') + (open ? ':o' + open : '');
      if (key === this._face) return;
      this._face = key;
      const g = this.faceG; g.innerHTML = '';
      const s = this.r / 26, ink = this.c.ink;
      const fg = el('g', { transform: `translate(${this.r * 0.3} 0) scale(${s})` }, g);
      const eye = x => {
        if (mood === 'love') return el('path', { d: `M${x} -1 l-4 -4 a2.5 2.5 0 0 1 4 -3 a2.5 2.5 0 0 1 4 3 Z`, fill: '#e91e63' }, fg);
        if (blink || mood === 'tired' || mood === 'proud' || mood === 'laugh')
          return el('path', { d: `M${x - 4} -4 Q${x} ${mood === 'proud' || mood === 'laugh' ? -9 : -1} ${x + 4} -4`, stroke: ink, 'stroke-width': 3, fill: 'none', 'stroke-linecap': 'round' }, fg);
        el('ellipse', { cx: x, cy: -4, rx: 3.4, ry: mood === 'surprised' || mood === 'scared' ? 5.6 : 4.4, fill: ink }, fg);
        el('circle', { cx: x + 1.2, cy: -5.6, r: 1.2, fill: '#fff' }, fg);
      };
      eye(-8); eye(8);
      if (mood === 'angry') el('path', { d: 'M-13 -14 L-3 -10 M13 -14 L3 -10', stroke: ink, 'stroke-width': 3, 'stroke-linecap': 'round' }, fg);
      if (mood === 'sad' || mood === 'scared') el('path', { d: 'M-13 -11 L-4 -14 M13 -11 L4 -14', stroke: ink, 'stroke-width': 3, 'stroke-linecap': 'round' }, fg);
      if (mood === 'curious') el('path', { d: 'M3 -16 Q9 -20 14 -15', stroke: ink, 'stroke-width': 3, fill: 'none' }, fg);
      if (mood === 'happy' || mood === 'love' || mood === 'laugh') { el('ellipse', { cx: -15, cy: 5, rx: 4, ry: 2.4, fill: '#ff8a80', opacity: .55 }, fg); el('ellipse', { cx: 16, cy: 5, rx: 4, ry: 2.4, fill: '#ff8a80', opacity: .55 }, fg); }
      if (mood === 'sad' && !blink) el('path', { d: 'M10 0 q-2 6 0 8 q2 -2 0 -8', fill: '#4fc3f7' }, fg);
      const A = this._accHead || {};
      if (A.mustache) el('path', { d: 'M-9 5 Q-4 2 0 5 Q4 2 9 5 Q4 8 0 6 Q-4 8 -9 5 Z', fill: ink }, fg);
      if (A.beard) el('path', { d: 'M-14 4 Q-12 20 0 22 Q12 20 14 4 Q8 12 0 12 Q-8 12 -14 4 Z', fill: this.c.hair_color || ink, opacity: .9 }, fg);
      if (open && mood !== 'surprised') el('ellipse', { cx: 0, cy: 10, rx: 4 + open * 1.5, ry: 2 + open * 2.4, fill: ink }, fg);
      else if (mood === 'surprised') el('ellipse', { cx: 0, cy: 11, rx: 5, ry: 6, fill: ink }, fg);
      else if (!A.mustache || mood !== 'neutral') el('path', { d: MOUTH[mood] || MOUTH.neutral, stroke: ink, 'stroke-width': 3, fill: mood === 'laugh' ? ink : 'none', 'stroke-linecap': 'round' }, fg);
      if (A.glasses) { el('circle', { cx: -8, cy: -4, r: 7, fill: 'rgba(255,255,255,.15)', stroke: ink, 'stroke-width': 2.4 }, fg); el('circle', { cx: 8, cy: -4, r: 7, fill: 'rgba(255,255,255,.15)', stroke: ink, 'stroke-width': 2.4 }, fg); el('line', { x1: -1, y1: -4, x2: 1, y2: -4, stroke: ink, 'stroke-width': 2.4 }, fg); }
    }

    drawProp(hold, label) {
      if (hold === this._hold) return;
      this._hold = hold; this.propG.innerHTML = '';
      if (hold && PROPS[hold]) PROPS[hold](this.propG, { ...this.col, ink: this.c.ink }, label);
    }

    /** o = {mood, hold, t, label, seated, talk (0..1 độ mở miệng), emote, emoteAge} */
    pose(p, x, ground, dir, o = {}) {
      const S = this.S, c = this.c, t = o.t || 0;
      const round = c.build === 'round', slim = c.build === 'slim';
      const L = { thigh: S * 0.235, shin: S * 0.235, torso: S * (round ? 0.28 : 0.30), neck: S * 0.045, up: S * 0.16, low: S * 0.16 };
      const v = (deg, len) => [Math.sin(deg * R) * len * dir, Math.cos(deg * R) * len];
      const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
      // thở + đổi trọng tâm nhẹ khi đứng yên (mỗi nhân vật lệch pha khác nhau)
      const idle = o.idle ? 1 : 0;
      const sway = Math.sin(t * 1.3 + this.seed) * 1.6 * idle;
      p = { ...p, lean: p.lean + sway, head: p.head + Math.sin(t * 0.9 + this.seed * 2) * 2 * idle };
      const back = -dir * S * 0.028;
      const hip = [0, 0], bhip = [back, 0];
      const fk = add(hip, v(p.fl1, L.thigh)), ff = add(fk, v(p.fl2, L.shin));
      const bk = add(bhip, v(p.bl1, L.thigh)), bf = add(bk, v(p.bl2, L.shin));
      const breathe = Math.sin(t * 2.4 + this.seed) * S * 0.004;
      // nảy bước chân khi đi/chạy: mỗi lần chân chạm nền hạ nhẹ trọng tâm xuống rồi bật lên
      const walkBob = p._walk !== undefined ? Math.abs(Math.sin(p._walk * Math.PI * 2)) * S * 0.012 : 0;
      const lift = Math.max(ff[1], bf[1]) + (p.lift || 0) * S / 160 - walkBob;
      const tv = [Math.sin(p.lean * R) * dir, -Math.cos(p.lean * R)];
      const top = [tv[0] * (L.torso + breathe), tv[1] * (L.torso + breathe)];
      const sh = [tv[0] * L.torso * 0.86, tv[1] * L.torso * 0.86];
      const bsh = [sh[0] + back * 1.1, sh[1]];
      const neck = add(top, [tv[0] * L.neck, tv[1] * L.neck]);
      const hc = add(neck, [tv[0] * this.r * 0.92, tv[1] * this.r * 0.92]);
      const fe = add(sh, v(p.fa1 + p.lean, L.up)), fh = add(fe, v(p.fa2 + p.lean, L.low));
      const be = add(bsh, v(p.ba1 + p.lean, L.up)), bh = add(be, v(p.ba2 + p.lean, L.low));
      const pts = (...a) => a.map(q => q.map(n => n.toFixed(1)).join(',')).join(' ');
      const foot = (f, ang) => { const len = S * 0.05; return [f, [f[0] + dir * len * Math.cos(ang * R * 0.3), f[1] - len * 0.05]]; };
      // squash & stretch: bật cao thì giãn dọc-co ngang, rơi/đáp đất thì nén dọc-phình ngang (giữ "thể tích")
      const vlift = clamp(p._vlift || 0, -6, 6);
      const sStretch = 1 + clamp(vlift * 0.011, -0.06, 0.1);
      const sSquash = 1 / Math.sqrt(sStretch);
      this.g.setAttribute('transform', `translate(${x.toFixed(1)} ${(ground - lift).toFixed(1)}) scale(${sSquash.toFixed(3)} ${sStretch.toFixed(3)})`);
      this.shadow.setAttribute('cy', (lift / sStretch).toFixed(1));
      this.shadow.setAttribute('rx', (S * 0.14 * (1 - (p.lift || 0) / 120) / sSquash).toFixed(1));
      if (o.seated) {
        const tp = S * 0.02, half = S * 0.11, bx = -dir * S * 0.02;
        this.seat.setAttribute('d', `M${bx - half} ${tp} H${bx + half} M${bx - half * 0.8} ${tp} L${bx - half * 0.9} ${lift} M${bx + half * 0.8} ${tp} L${bx + half * 0.9} ${lift}`);
      }
      this.seat.setAttribute('opacity', o.seated ? 0.9 : 0);
      this.frontLeg.setAttribute('points', pts(hip, fk, ff));
      this.backLeg.setAttribute('points', pts(bhip, bk, bf));
      const [f1a, f1b] = foot(ff, p.fl2), [f2a, f2b] = foot(bf, p.bl2);
      this.frontFoot.setAttribute('x1', f1a[0]); this.frontFoot.setAttribute('y1', f1a[1]); this.frontFoot.setAttribute('x2', f1b[0]); this.frontFoot.setAttribute('y2', f1b[1]);
      this.backFoot.setAttribute('x1', f2a[0]); this.backFoot.setAttribute('y1', f2a[1]); this.backFoot.setAttribute('x2', f2b[0]); this.backFoot.setAttribute('y2', f2b[1]);
      this.torso.setAttribute('points', pts(hip, neck));
      this.frontArm.setAttribute('points', pts(sh, fe, fh));
      this.backArm.setAttribute('points', pts(bsh, be, bh));
      this.frontHand.setAttribute('cx', fh[0]); this.frontHand.setAttribute('cy', fh[1]);
      this.backHand.setAttribute('cx', bh[0]); this.backHand.setAttribute('cy', bh[1]);
      if (this.body) {
        const nrm = [-tv[1], tv[0]], wTop = S * (slim ? 0.04 : 0.05), wBot = S * (round ? 0.1 : slim ? 0.035 : 0.045);
        const a = add(top, [-tv[0] * S * 0.015, -tv[1] * S * 0.015]);
        const P = (base, k) => [base[0] + nrm[0] * k, base[1] + nrm[1] * k];
        if (c.outfit === 'dress') {
          const hem = [0, S * 0.12], hw = S * 0.11;
          this.body.setAttribute('d', `M${P(a, wTop)} L${P(a, -wTop)} L${hem[0] - hw} ${hem[1]} L${hem[0] + hw} ${hem[1]} Z`.replace(/,/g, ' '));
        } else if (round) {
          const mid = [tv[0] * L.torso * 0.45 + dir * S * 0.035, tv[1] * L.torso * 0.45];
          this.body.setAttribute('d', `M${P(a, wTop)} Q${P(mid, wBot * 1.6)} ${P([0, -S * 0.01], wBot * 0.5)} L${P([0, -S * 0.01], -wBot * 0.5)} Q${P(mid, -wBot * 1.2)} ${P(a, -wTop)} Z`.replace(/,/g, ' '));
        } else {
          const coatLen = c.outfit === 'coat' ? S * 0.07 : -S * 0.03;
          const b = [0, coatLen];
          this.body.setAttribute('d', `M${P(a, wTop)} L${P(a, -wTop)} L${P(b, -wBot)} L${P(b, wBot)} Z`.replace(/,/g, ' '));
        }
      }
      // phụ kiện trên thân: cà vạt, nơ, khăn, ba lô
      this.acc.innerHTML = ''; this.accBack.innerHTML = '';
      const A = c.accessories || [];
      const nrm = [-tv[1], tv[0]];
      if (A.includes('tie')) { const a = add(top, [nrm[0] * 0, 0]); const b2 = [tv[0] * L.torso * 0.45 + dir * S * 0.012, tv[1] * L.torso * 0.45]; el('path', { d: `M${a[0]} ${a[1]} L${b2[0] - S * 0.012} ${b2[1]} L${b2[0]} ${b2[1] + S * 0.02} L${b2[0] + S * 0.012} ${b2[1]} Z`, fill: c.tie_color || this.col.a1 }, this.acc); }
      if (A.includes('bowtie')) { const a = top; el('path', { d: `M${a[0]} ${a[1]} l${-S * 0.022} ${-S * 0.012} v${S * 0.024} Z M${a[0]} ${a[1]} l${S * 0.022} ${-S * 0.012} v${S * 0.024} Z`, fill: this.col.a1 }, this.acc); }
      if (A.includes('scarf')) { const a = top; el('path', { d: `M${a[0] - S * 0.04} ${a[1] - S * 0.005} h${S * 0.08} v${S * 0.025} h${-S * 0.08} Z M${a[0] - dir * S * 0.03} ${a[1]} l${-dir * S * 0.02} ${S * 0.07} l${dir * S * 0.018} ${S * 0.004} Z`, fill: c.scarf_color || this.col.a2 }, this.acc); }
      if (A.includes('backpack')) { const a = add(sh, [-dir * S * 0.06, S * 0.02]); el('rect', { x: a[0] - S * 0.04, y: a[1], width: S * 0.08, height: S * 0.12, rx: S * 0.02, fill: c.bag_color || this.col.a3, stroke: c.ink, 'stroke-width': this.w * 0.5 }, this.accBack); }
      // tóc dài / đuôi ngựa phía sau đầu
      if (this.hairLong || this.hairTail) {
        const r = this.r, hx = hc[0], hy = hc[1];
        const swing = Math.sin(t * 3 + this.seed) * r * 0.08;
        this.hairBack.setAttribute('d', this.hairLong
          ? `M${hx - dir * r * 1.0} ${hy - r * 0.5} Q${hx - dir * r * 1.4} ${hy + r * 0.8} ${hx - dir * r * 0.9 + swing} ${hy + r * 1.6} L${hx - dir * r * 0.1} ${hy + r * 1.2} Q${hx} ${hy} ${hx + dir * r * 0.3} ${hy - r * 0.9} Z`
          : `M${hx - dir * r * 0.7} ${hy - r * 0.6} Q${hx - dir * r * 1.8} ${hy - r * 0.2} ${hx - dir * r * 1.5 + swing} ${hy + r * 1.1} Q${hx - dir * r * 1.1} ${hy + r * 0.2} ${hx - dir * r * 0.6} ${hy - r * 0.2} Z`);
      }
      this.headG.setAttribute('transform', `translate(${hc[0].toFixed(1)} ${hc[1].toFixed(1)}) rotate(${((p.head + p.lean * 0.4) * dir).toFixed(1)}) scale(${dir} 1)`);
      const blink = ((t + this.seed) % 3.7) > 3.55;
      const open = o.talk ? Math.max(1, Math.round(o.talk * 3)) : 0;
      this.drawFace(o.mood || 'neutral', blink, open);
      this.drawProp(o.hold, o.label);
      this.propG.setAttribute('transform', `translate(${fh[0].toFixed(1)} ${fh[1].toFixed(1)}) scale(${(dir * S / 300).toFixed(3)} ${(S / 300).toFixed(3)})`);
      this.head = [x + hc[0], ground - lift + hc[1]];
      this.emote(o.emote, o.emoteAge ?? 99);
    }

    emote(e, age) {
      const show = e && EMOTE[e] && age < 1.8;
      if (!show) { this.emoteG.setAttribute('opacity', 0); return; }
      if (this._emote !== e) {
        this._emote = e; this.emoteG.innerHTML = '';
        const [txt, col] = EMOTE[e];
        el('text', { 'text-anchor': 'middle', 'font-size': this.S * 0.14, 'font-weight': 900, fill: col || '#000', 'font-family': 'var(--title-font)', text: txt }, this.emoteG);
      }
      const k = VF.prog(age, 0, 0.3, 'back');
      this.emoteG.setAttribute('opacity', clamp((1.8 - age) / 0.3));
      this.emoteG.setAttribute('transform', `translate(${this.head[0] + this.r * 1.3} ${this.head[1] - this.r * 1.6 - k * this.r * 0.4}) scale(${0.4 + 0.6 * k})`);
    }

    say(text, alpha) {
      if (!this.head) return;
      if (this._say !== text) {
        this._say = text; this.bubble.innerHTML = '';
        if (text) {
          const fs = Math.max(26, this.S * 0.075), w = Math.min(text.length * fs * 0.55 + fs * 1.4, this.S * 2.4);
          this._bfs = fs; this._bw = w;
          el('rect', { x: -w / 2, y: -fs * 2.2, width: w, height: fs * 1.8, rx: fs * 0.6, fill: '#fff', stroke: this.c.ink, 'stroke-width': 4 }, this.bubble);
          el('path', { d: `M-10 ${-fs * 0.42} L4 ${fs * 0.3} L12 ${-fs * 0.42}`, fill: '#fff', stroke: this.c.ink, 'stroke-width': 4, 'stroke-linejoin': 'round' }, this.bubble);
          el('text', { x: 0, y: -fs * 0.95, 'text-anchor': 'middle', 'font-size': fs, 'font-weight': 700, 'font-family': 'var(--font)', fill: '#111', text }, this.bubble);
        }
      }
      this.bubble.setAttribute('opacity', alpha);
      this.bubble.setAttribute('transform', `translate(${this.head[0]} ${this.head[1] - this.r * 1.7})`);
    }
  }

  /** Lịch diễn cho từng nhân vật; nhân vật đứng yên tự quay mặt về phía nhân vật khác. */
  function timeline(beats, names, W, lib) {
    const slots = { left: 0.3, center: 0.5, right: 0.7 };
    const home = (i, n) => (n === 1 ? 0.5 : n === 2 ? [0.3, 0.7][i] : 0.18 + 0.64 * i / (n - 1));
    const speed = 0.42;
    const tracks = {};
    names.forEach((name, i) => {
      const own = beats.filter(b => b.who === name);
      const enters = own.length && /^enter_/.test(own[0].move || '');
      let x = enters ? (own[0].move === 'enter_left' ? -0.15 : 1.15) : home(i, names.length);
      let face = null;
      const segs = [];
      let lastT = 0, cur = { act: 'stand', mood: 'neutral', hold: null };
      for (const b of own) {
        const tx = /^enter_/.test(b.move || '') ? home(i, names.length)
          : b.move === 'exit_left' ? -0.2 : b.move === 'exit_right' ? 1.2 : (slots[b.move] ?? null);
        segs.push({ t: lastT, until: b.t, x0: x, x1: x, ...cur, walk: false, face });
        let t = b.t;
        if (tx !== null && Math.abs(tx - x) > 0.01) {
          const dur = Math.abs(tx - x) / speed;
          segs.push({ t, until: t + dur, x0: x, x1: tx, act: 'walk', mood: b.mood || cur.mood, hold: b.hold ?? cur.hold, walk: true, face: tx > x ? 1 : -1 });
          x = tx; t += dur;
        }
        face = b.face ? (b.face === 'left' ? -1 : 1) : null;
        cur = { act: b.act, mood: b.mood || cur.mood, hold: b.hold !== undefined ? b.hold : cur.hold, say: b.say, sayT: t, label: b.label, emote: b.emote, emoteT: t };
        lastT = t;
      }
      segs.push({ t: lastT, until: 1e9, x0: x, x1: x, ...cur, walk: false, face });
      tracks[name] = segs;
    });
    // quay mặt về phía nhau khi không chỉ định
    names.forEach(name => {
      for (const s of tracks[name]) {
        if (s.walk || s.face) continue;
        const others = names.filter(n => n !== name).map(n => { const seg = tracks[n].find(z => s.t >= z.t && s.t < z.until) || tracks[n][0]; return seg.x1; }).filter(v => v > -0.05 && v < 1.05);
        s.face = others.length ? (others.reduce((a, b) => a + b, 0) / others.length >= s.x1 ? 1 : -1) : (s.x1 > 0.5 ? -1 : 1);
      }
    });
    return tracks;
  }

  function stateAt(segs, t, lib, W) {
    let i = segs.findIndex(s => t >= s.t && t < s.until);
    if (i < 0) i = segs.length - 1;
    const s = segs[i];
    const k = s.walk ? clamp((t - s.t) / (s.until - s.t)) : 0;
    const act = lib.actions[s.act] || lib.actions.stand;
    let p = sample(act, t - s.t, s.act);
    const liftPrev = sample(act, t - s.t - 0.04, s.act).lift || 0;
    p._vlift = ((p.lift || 0) - liftPrev) / 0.04;
    if (i > 0 && t - s.t < 0.3) {
      const prev = segs[i - 1], pa = lib.actions[prev.act] || lib.actions.stand;
      p = { ...mix(sample(pa, s.t - prev.t, prev.act), p, ease.inOut((t - s.t) / 0.3)), _walk: p._walk, _vlift: p._vlift };
    }
    return { p, seated: !!act.seated && !s.walk, x: lerp(s.x0, s.x1, k) * W, face: s.face || 1, mood: s.mood, hold: s.hold, say: s.say, sayT: s.sayT, label: s.label,
      talking: !s.walk && (TALK_ACTS.has(s.act) || !!s.say), idle: !s.walk && !act.loop && !act.seated,
      emote: s.emote, emoteAge: t - (s.emoteT ?? 0), act: s.act, since: t - s.t, walking: !!s.walk };
  }

  VF.Stick = Stick;
  VF.stick = { timeline, stateAt, sample, STAND, PROPS, EMOTE };
})();
