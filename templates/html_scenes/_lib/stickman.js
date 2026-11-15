/* Rig người que 11 khớp (tương thích định dạng actions.json của VF Studio).
 * Góc tính bằng độ: 0 = buông thẳng xuống, 90 = chỉa ngang về phía trước, âm = ra sau.
 * Tay cộng thêm 'lean' (theo thân), chân là góc tuyệt đối. lift nâng cả người (nhảy).
 * Stick.timeline(beats) dựng lịch diễn; stick.draw(t) vẽ đúng tư thế tại t (tất định).
 */
(function () {
  const { el, clamp, lerp, ease } = VF;
  const R = Math.PI / 180;
  const KEYS = ['lean', 'head', 'lift', 'fa1', 'fa2', 'ba1', 'ba2', 'fl1', 'fl2', 'bl1', 'bl2'];
  const STAND = { lean: 0, head: 0, lift: 0, fa1: 8, fa2: 4, ba1: -8, ba2: -4, fl1: 6, fl2: 0, bl1: -6, bl2: 0 };

  const mix = (a, b, k) => { const o = {}; for (const key of KEYS) o[key] = lerp(a[key] ?? STAND[key], b[key] ?? STAND[key], k); return o; };
  const full = p => Object.assign({}, STAND, p);

  /** Tư thế của một action tại thời điểm local (giây kể từ khi bắt đầu act) */
  function sample(action, local) {
    const fr = action.frames;
    if (!fr || !fr.length) return { ...STAND };
    if (fr.length === 1) return full(fr[0].pose);
    const total = fr.reduce((s, f) => s + (f.dur || 0.4), 0);
    let x = action.loop ? local % total : Math.min(local, total);
    for (let i = 0; i < fr.length; i++) {
      const d = fr[i].dur || 0.4;
      if (x <= d || i === fr.length - 1) {
        const nxt = action.loop ? fr[(i + 1) % fr.length] : fr[Math.min(i + 1, fr.length - 1)];
        return mix(full(fr[i].pose), full(nxt.pose), ease.inOut(clamp(x / d)));
      }
      x -= d;
    }
    return full(fr[fr.length - 1].pose);
  }

  const PROPS = {
    book: (g, c) => { el('rect', { x: -14, y: -20, width: 34, height: 26, rx: 2, fill: c.a1, stroke: c.ink, 'stroke-width': 3 }, g); el('line', { x1: 3, y1: -20, x2: 3, y2: 6, stroke: c.ink, 'stroke-width': 2 }, g); },
    phone: (g, c) => { el('rect', { x: -8, y: -28, width: 18, height: 32, rx: 4, fill: '#222', stroke: c.ink, 'stroke-width': 2 }, g); el('rect', { x: -5, y: -24, width: 12, height: 22, fill: c.a2 }, g); },
    coin: (g, c) => { el('circle', { cx: 4, cy: -10, r: 13, fill: '#f5c518', stroke: '#a77d00', 'stroke-width': 3 }, g); el('text', { x: 4, y: -4, 'text-anchor': 'middle', 'font-size': 16, 'font-weight': 900, fill: '#a77d00', text: '$' }, g); },
    money: (g, c) => { el('rect', { x: -18, y: -18, width: 40, height: 22, rx: 3, fill: '#4caf50', stroke: '#1b5e20', 'stroke-width': 3 }, g); el('circle', { cx: 2, cy: -7, r: 6, fill: 'none', stroke: '#1b5e20', 'stroke-width': 2 }, g); },
    gift: (g, c) => { el('rect', { x: -18, y: -30, width: 36, height: 30, fill: c.a1, stroke: c.ink, 'stroke-width': 3 }, g); el('rect', { x: -3, y: -30, width: 6, height: 30, fill: c.a3 }, g); el('rect', { x: -18, y: -18, width: 36, height: 6, fill: c.a3 }, g); },
    bulb: (g, c) => { el('circle', { cx: 0, cy: -26, r: 16, fill: '#ffe066', stroke: c.ink, 'stroke-width': 3 }, g); el('rect', { x: -7, y: -12, width: 14, height: 10, fill: '#999', stroke: c.ink, 'stroke-width': 2 }, g); },
    sign: (g, c, txt) => { el('line', { x1: 0, y1: 10, x2: 0, y2: -60, stroke: '#8d6e63', 'stroke-width': 5 }, g); el('rect', { x: -50, y: -100, width: 100, height: 46, rx: 4, fill: '#fff', stroke: c.ink, 'stroke-width': 3 }, g); el('text', { x: 0, y: -70, 'text-anchor': 'middle', 'font-size': 20, 'font-weight': 800, fill: c.ink, text: txt || '!' }, g); },
    laptop: (g, c) => { el('rect', { x: -26, y: -30, width: 44, height: 28, rx: 3, fill: '#333', stroke: c.ink, 'stroke-width': 2 }, g); el('rect', { x: -30, y: -2, width: 52, height: 6, rx: 2, fill: '#666' }, g); },
    cup: (g, c) => { el('path', { d: 'M-10 -24 L10 -24 L8 2 L-8 2 Z', fill: '#fff', stroke: c.ink, 'stroke-width': 3 }, g); el('path', { d: 'M10 -18 q10 2 0 12', fill: 'none', stroke: c.ink, 'stroke-width': 3 }, g); },
    flag: (g, c) => { el('line', { x1: 0, y1: 10, x2: 0, y2: -80, stroke: c.ink, 'stroke-width': 4 }, g); el('path', { d: 'M0 -80 L46 -68 L0 -54 Z', fill: c.a1 }, g); },
    sword: (g, c) => { el('line', { x1: 0, y1: 0, x2: 0, y2: -80, stroke: '#cfd8dc', 'stroke-width': 7 }, g); el('line', { x1: -14, y1: -4, x2: 14, y2: -4, stroke: '#795548', 'stroke-width': 6 }, g); },
    key: (g, c) => { el('circle', { cx: 0, cy: -20, r: 9, fill: 'none', stroke: '#f5c518', 'stroke-width': 5 }, g); el('line', { x1: 0, y1: -11, x2: 0, y2: 14, stroke: '#f5c518', 'stroke-width': 5 }, g); },
    star: (g, c) => { el('path', { d: 'M0 -40 L9 -16 L34 -16 L14 -2 L22 22 L0 8 L-22 22 L-14 -2 L-34 -16 L-9 -16 Z', transform: 'scale(.7) translate(0,-14)', fill: '#ffd400', stroke: c.ink, 'stroke-width': 3 }, g); },
    trophy: (g, c) => { el('path', { d: 'M-16 -40 H16 V-24 Q16 -8 0 -6 Q-16 -8 -16 -24 Z', fill: '#f5c518', stroke: c.ink, 'stroke-width': 3 }, g); el('rect', { x: -8, y: -6, width: 16, height: 8, fill: '#a77d00' }, g); },
    magnifier: (g, c) => { el('circle', { cx: 0, cy: -34, r: 16, fill: 'rgba(160,220,255,.5)', stroke: c.ink, 'stroke-width': 4 }, g); el('line', { x1: 0, y1: -18, x2: 0, y2: 6, stroke: c.ink, 'stroke-width': 6 }, g); },
    map: (g, c) => { el('path', { d: 'M-24 -30 L-8 -24 L8 -30 L24 -24 L24 4 L8 -2 L-8 4 L-24 -2 Z', fill: '#f3e5ab', stroke: c.ink, 'stroke-width': 3 }, g); },
    briefcase: (g, c) => { el('rect', { x: -20, y: 0, width: 40, height: 28, rx: 3, fill: '#6d4c41', stroke: c.ink, 'stroke-width': 3 }, g); el('path', { d: 'M-7 0 v-6 h14 v6', fill: 'none', stroke: c.ink, 'stroke-width': 3 }, g); },
  };

  const MOUTH = {
    neutral: 'M-7 9 L7 9', happy: 'M-9 6 Q0 16 9 6', proud: 'M-9 6 Q0 15 9 6', sad: 'M-8 12 Q0 4 8 12',
    angry: 'M-8 11 Q0 6 8 11', tired: 'M-6 10 L6 10', curious: 'M-5 9 Q2 12 7 8', scared: 'M-6 8 Q0 2 6 8 Q0 15 -6 8',
    surprised: null,
  };

  class Stick {
    /** char: {head, ink, shirt, hat, hat_color, scale, face, line}; size = chiều cao người (px) */
    constructor(parent, char, size, colors) {
      this.c = Object.assign({ head: 'hollow', ink: colors.ink, shirt: 'none', hat: 'none', scale: 1, face: true, line: 0 }, char);
      this.col = colors;
      this.S = size * (this.c.scale || 1);
      this.g = el('g', { class: 'stick' }, parent);
      const w = this.c.line || Math.max(4, this.S * 0.028);
      const st = { stroke: this.c.ink, 'stroke-width': w, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', fill: 'none' };
      this.seat = el('path', { fill: 'none', stroke: this.c.ink, 'stroke-width': w * 0.8, 'stroke-linecap': 'round', opacity: 0 }, this.g);
      this.shadow = el('ellipse', { rx: this.S * 0.13, ry: this.S * 0.018, fill: 'rgba(0,0,0,.12)' }, this.g);
      this.backArm = el('polyline', st, this.g);
      this.backLeg = el('polyline', st, this.g);
      this.torso = el('polyline', st, this.g);
      if (this.c.shirt && this.c.shirt !== 'none') {
        this.shirt = el('path', { fill: this.c.shirt, stroke: this.c.ink, 'stroke-width': w * 0.6, 'stroke-linejoin': 'round' }, this.g);
      }
      this.frontLeg = el('polyline', st, this.g);
      this.headG = el('g', {}, this.g);
      const r = this.S * 0.09;
      this.r = r;
      el('circle', { r, fill: this.c.head === 'filled' ? (this.c.head_fill || '#fff') : (this.c.head === 'solid' ? this.c.ink : 'var(--bg)'), stroke: this.c.ink, 'stroke-width': w }, this.headG);
      this.faceG = el('g', {}, this.headG);
      this.hatG = el('g', {}, this.headG);
      this.drawHat(r, w);
      this.propG = el('g', {}, this.g);
      this.frontArm = el('polyline', st, this.g);
      this.bubble = el('g', { opacity: 0 }, parent);
      this._mood = null; this._hold = null;
    }

    drawHat(r, w) {
      const g = this.hatG, c = this.c, hc = c.hat_color || this.col.a1;
      if (c.hat === 'beanie') el('path', { d: `M${-r * 1.02} ${-r * 0.15} A${r} ${r} 0 0 1 ${r * 1.02} ${-r * 0.15} L${r * 1.08} ${-r * 0.05} L${-r * 1.08} ${-r * 0.05} Z`, fill: hc, stroke: c.ink, 'stroke-width': w * 0.7 }, g);
      if (c.hat === 'cap') { el('path', { d: `M${-r} ${-r * 0.2} A${r} ${r} 0 0 1 ${r} ${-r * 0.2} Z`, fill: hc, stroke: c.ink, 'stroke-width': w * 0.6 }, g); el('path', { d: `M${r * 0.6} ${-r * 0.22} L${r * 1.7} ${-r * 0.1}`, stroke: c.ink, 'stroke-width': w * 1.2, 'stroke-linecap': 'round' }, g); }
      if (c.hat === 'crown') el('path', { d: `M${-r * 0.8} ${-r * 0.75} L${-r * 0.8} ${-r * 1.5} L${-r * 0.4} ${-r * 1.1} L0 ${-r * 1.6} L${r * 0.4} ${-r * 1.1} L${r * 0.8} ${-r * 1.5} L${r * 0.8} ${-r * 0.75} Z`, fill: '#ffd400', stroke: c.ink, 'stroke-width': w * 0.5 }, g);
      if (c.hat === 'helmet') el('path', { d: `M${-r * 1.1} ${-r * 0.05} A${r * 1.1} ${r * 1.15} 0 0 1 ${r * 1.1} ${-r * 0.05} Z`, fill: hc || '#90a4ae', stroke: c.ink, 'stroke-width': w * 0.6 }, g);
      if (c.hat === 'hair') el('path', { d: `M${-r * 1.05} ${-r * 0.1} Q${-r} ${-r * 1.3} ${r * 0.2} ${-r * 1.08} Q${r * 1.2} ${-r * 0.9} ${r * 1.05} ${-r * 0.2} Q${r * 0.3} ${-r * 0.75} ${-r * 1.05} ${-r * 0.1} Z`, fill: hc || c.ink }, g);
    }

    drawFace(mood, blink) {
      if (!this.c.face) return;
      const key = mood + (blink ? ':b' : '');
      if (key === this._mood) return;
      this._mood = key;
      const g = this.faceG; g.innerHTML = '';
      const s = this.r / 26, ink = this.c.ink;
      const fg = el('g', { transform: `translate(${this.r * 0.28} 0) scale(${s})` }, g);
      const eye = (x) => blink || mood === 'tired' || mood === 'proud'
        ? el('path', { d: `M${x - 4} -4 Q${x} ${mood === 'proud' ? -9 : -1} ${x + 4} -4`, stroke: ink, 'stroke-width': 3, fill: 'none', 'stroke-linecap': 'round' }, fg)
        : el('ellipse', { cx: x, cy: -4, rx: 3.2, ry: mood === 'surprised' || mood === 'scared' ? 5.5 : 4.2, fill: ink }, fg);
      eye(-8); eye(8);
      if (mood === 'angry') { el('path', { d: 'M-13 -14 L-3 -10 M13 -14 L3 -10', stroke: ink, 'stroke-width': 3, 'stroke-linecap': 'round' }, fg); }
      if (mood === 'sad' || mood === 'scared') { el('path', { d: 'M-13 -11 L-4 -14 M13 -11 L4 -14', stroke: ink, 'stroke-width': 3, 'stroke-linecap': 'round' }, fg); }
      if (mood === 'curious') { el('path', { d: 'M3 -16 Q9 -20 14 -15', stroke: ink, 'stroke-width': 3, fill: 'none' }, fg); }
      if (mood === 'surprised') el('ellipse', { cx: 0, cy: 11, rx: 5, ry: 6, fill: ink }, fg);
      else el('path', { d: MOUTH[mood] || MOUTH.neutral, stroke: ink, 'stroke-width': 3, fill: 'none', 'stroke-linecap': 'round' }, fg);
    }

    drawProp(hold, label) {
      if (hold === this._hold) return;
      this._hold = hold; this.propG.innerHTML = '';
      if (hold && PROPS[hold]) PROPS[hold](this.propG, { ...this.col, ink: this.c.ink }, label);
    }

    /** vẽ tư thế p tại chân (x, ground), quay mặt dir (1 phải, -1 trái) */
    pose(p, x, ground, dir, mood, hold, t, label, seated) {
      const S = this.S, L = { thigh: S * 0.24, shin: S * 0.24, torso: S * 0.30, neck: S * 0.03, up: S * 0.165, low: S * 0.165 };
      const v = (deg, len) => [Math.sin(deg * R) * len * dir, Math.cos(deg * R) * len];
      const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
      const hip = [0, 0];
      const fk = add(hip, v(p.fl1, L.thigh)), ff = add(fk, v(p.fl2, L.shin));
      const bk = add(hip, v(p.bl1, L.thigh)), bf = add(bk, v(p.bl2, L.shin));
      const breathe = Math.sin(t * 2.4) * S * 0.004;
      const lift = Math.max(ff[1], bf[1]) + (p.lift || 0) * S / 160;
      const tv = [Math.sin(p.lean * R) * dir, -Math.cos(p.lean * R)];
      const sh = [tv[0] * (L.torso + breathe), tv[1] * (L.torso + breathe)];
      const neck = add(sh, [tv[0] * L.neck, tv[1] * L.neck]);
      const hc = add(neck, [tv[0] * this.r, tv[1] * this.r]);
      const fe = add(sh, v(p.fa1 + p.lean, L.up)), fh = add(fe, v(p.fa2 + p.lean, L.low));
      const be = add(sh, v(p.ba1 + p.lean, L.up)), bh = add(be, v(p.ba2 + p.lean, L.low));
      const pts = (...a) => a.map(q => q.join(',')).join(' ');
      this.g.setAttribute('transform', `translate(${x} ${ground - lift})`);
      this.shadow.setAttribute('cx', 0); this.shadow.setAttribute('cy', lift);
      this.shadow.setAttribute('rx', S * 0.13 * (1 - (p.lift || 0) / 120));
      if (seated) {
        const top = S * 0.025, half = S * 0.11, bx = -dir * S * 0.02;
        this.seat.setAttribute('d', `M${bx - half} ${top} H${bx + half} M${bx - half * 0.8} ${top} L${bx - half * 0.9} ${lift} M${bx + half * 0.8} ${top} L${bx + half * 0.9} ${lift}`);
      }
      this.seat.setAttribute('opacity', seated ? 0.9 : 0);
      this.frontLeg.setAttribute('points', pts(hip, fk, ff));
      this.backLeg.setAttribute('points', pts(hip, bk, bf));
      this.torso.setAttribute('points', pts(hip, neck));
      this.frontArm.setAttribute('points', pts(sh, fe, fh));
      this.backArm.setAttribute('points', pts(sh, be, bh));
      if (this.shirt) {
        const n = [-tv[1] * S * 0.05, tv[0] * S * 0.05];
        const top = add(sh, [tv[0] * S * 0.01, tv[1] * S * 0.01]);
        this.shirt.setAttribute('d', `M${top[0] + n[0]} ${top[1] + n[1]} L${top[0] - n[0]} ${top[1] - n[1]} L${-n[0] * 0.85} ${-n[1] * 0.85 - S * 0.03} L${n[0] * 0.85} ${n[1] * 0.85 - S * 0.03} Z`);
      }
      this.headG.setAttribute('transform', `translate(${hc[0]} ${hc[1]}) rotate(${(p.head + p.lean * 0.4) * dir}) scale(${dir} 1)`);
      const blink = (t % 3.7) > 3.55;
      this.drawFace(mood || 'neutral', blink);
      this.drawProp(hold, label);
      this.propG.setAttribute('transform', `translate(${fh[0]} ${fh[1]}) scale(${dir * S / 300} ${S / 300})`);
      this.head = [x + hc[0], ground - lift + hc[1]];
    }

    say(text, alpha) {
      if (!this.head) return;
      if (this._say !== text) {
        this._say = text; this.bubble.innerHTML = '';
        if (text) {
          const fs = Math.max(26, this.S * 0.075), w = Math.min(text.length * fs * 0.55 + fs * 1.4, this.S * 2.4);
          el('rect', { x: -w / 2, y: -fs * 2.2, width: w, height: fs * 1.8, rx: fs * 0.6, fill: '#fff', stroke: this.c.ink, 'stroke-width': 4 }, this.bubble);
          el('path', { d: `M-10 ${-fs * 0.42} L4 ${fs * 0.3} L12 ${-fs * 0.42}`, fill: '#fff', stroke: this.c.ink, 'stroke-width': 4, 'stroke-linejoin': 'round' }, this.bubble);
          el('text', { x: 0, y: -fs * 0.95, 'text-anchor': 'middle', 'font-size': fs, 'font-weight': 700, 'font-family': 'var(--font)', fill: '#111', text }, this.bubble);
        }
      }
      this.bubble.setAttribute('opacity', alpha);
      this.bubble.setAttribute('transform', `translate(${this.head[0]} ${this.head[1] - this.r * 1.6})`);
    }
  }

  /** Dựng lịch diễn cho từng nhân vật từ danh sách beat đã có t (giây). */
  function timeline(beats, names, W, lib) {
    const slots = { left: 0.3, center: 0.5, right: 0.7 };
    const home = (i, n) => (n === 1 ? 0.5 : n === 2 ? [0.32, 0.68][i] : 0.2 + 0.6 * i / (n - 1));
    const speed = 0.42; // phần bề ngang / giây khi đi bộ
    const tracks = {};
    names.forEach((name, i) => {
      const own = beats.filter(b => b.who === name);
      const enters = own.length && /^enter_/.test(own[0].move || '');
      let x = enters ? (own[0].move === 'enter_left' ? -0.15 : 1.15) : home(i, names.length);
      let face = x > 0.5 ? -1 : 1;
      const segs = [];
      let lastT = 0, cur = { act: 'stand', mood: 'neutral', hold: null };
      for (const b of own) {
        const tx = /^enter_/.test(b.move || '') ? home(i, names.length)
          : b.move === 'exit_left' ? -0.2 : b.move === 'exit_right' ? 1.2 : (slots[b.move] ?? null);
        segs.push({ t: lastT, until: b.t, x0: x, x1: x, ...cur, walk: false, face });
        let t = b.t;
        if (tx !== null && Math.abs(tx - x) > 0.01) {
          const dur = Math.abs(tx - x) / speed;
          face = tx > x ? 1 : -1;
          segs.push({ t, until: t + dur, x0: x, x1: tx, act: 'walk', mood: b.mood || cur.mood, hold: b.hold ?? cur.hold, walk: true, face });
          x = tx; t += dur;
        }
        if (b.face) face = b.face === 'left' ? -1 : 1;
        cur = { act: b.act, mood: b.mood || cur.mood, hold: b.hold !== undefined ? b.hold : cur.hold, say: b.say, sayT: t, label: b.label };
        lastT = t;
      }
      segs.push({ t: lastT, until: 1e9, x0: x, x1: x, ...cur, walk: false, face });
      tracks[name] = segs;
    });
    return tracks;
  }

  function stateAt(segs, t, lib, W) {
    let i = segs.findIndex(s => t >= s.t && t < s.until);
    if (i < 0) i = segs.length - 1;
    const s = segs[i];
    const k = s.walk ? clamp((t - s.t) / (s.until - s.t)) : 0;
    const act = lib.actions[s.act] || lib.actions.stand;
    let p = sample(act, t - s.t);
    // chuyển mượt 0.25s từ tư thế trước
    if (i > 0 && t - s.t < 0.25) {
      const prev = segs[i - 1], pa = lib.actions[prev.act] || lib.actions.stand;
      p = mix(sample(pa, s.t - prev.t), p, ease.inOut((t - s.t) / 0.25));
    }
    return { p, seated: !!act.seated && !s.walk, x: lerp(s.x0, s.x1, k) * W, face: s.face, mood: s.mood, hold: s.hold, say: s.say, sayT: s.sayT, label: s.label };
  }

  VF.Stick = Stick;
  VF.stick = { timeline, stateAt, sample, STAND, PROPS };
})();
