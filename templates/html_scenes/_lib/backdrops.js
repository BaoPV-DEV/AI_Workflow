/* Thư viện bối cảnh vector cho sân khấu người que.
 * VF.backdrops.draw(g, name, ctx) -> update(t)  (hàm gọi mỗi khung hình cho mây trôi, sóng, mưa…)
 * ctx = {W, H, gy (mặt đất), style, time: day|sunset|night, weather: none|rain|snow|leaves|fog}
 * Màu tự lấy từ style (bg, ink, accent) và pha nhạt để nhân vật luôn nổi bật.
 */
(function () {
  const { el } = VF;
  const hex = h => { h = (h || '#ffffff').replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
  const mix = (a, b, k) => { const A = hex(a), B = hex(b); return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * k).toString(16).padStart(2, '0')).join(''); };
  const lum = h => { const [r, g, b] = hex(h); return (0.299 * r + 0.587 * g + 0.114 * b) / 255; };
  const rnd = s => { let x = s; return () => (x = (x * 9301 + 49297) % 233280) / 233280; };

  function palette(st, time) {
    const bg = st.bg || '#ffffff', ink = st.ink || '#111111', ac = st.accent || ['#ff3b30', '#0a84ff', '#ffcc00'];
    const dark = lum(bg) < 0.45;
    const C = { bg, ink, a1: ac[0], a2: ac[1], a3: ac[2], dark };
    C.wall = dark ? mix(bg, ac[1], 0.12) : mix(bg, ac[1], 0.08);
    C.wall2 = mix(C.wall, ink, 0.06);
    C.floor = dark ? mix(bg, '#ffffff', 0.08) : mix(bg, '#a1887f', 0.28);
    C.wood = dark ? '#5d4037' : '#c8a27a';
    C.woodD = mix(C.wood, '#000000', 0.25);
    C.line = mix(bg, ink, dark ? 0.35 : 0.3);
    C.soft = mix(bg, ink, 0.1);
    C.green = dark ? '#2e7d32' : '#7cb342'; C.greenD = mix(C.green, '#000000', 0.25);
    C.glass = dark ? '#1e3a5f' : '#cfe8fb';
    const skies = { day: ['#bfe3ff', '#eaf6ff'], sunset: ['#ff9a76', '#ffe0a8'], night: ['#0b1537', '#24305e'] };
    C.sky = st.sky && time === 'day' ? st.sky : skies[time] || skies.day;
    if (dark && time === 'day') C.sky = [mix(bg, ac[1], 0.25), mix(bg, ac[1], 0.1)];
    C.sun = time === 'sunset' ? '#ff7043' : '#ffd54f';
    return C;
  }

  /* ---------- tiện ích vẽ ---------- */
  function sky(g, ctx, C, h = ctx.gy) {
    const id = 'sky' + Math.random().toString(36).slice(2, 7);
    const d = el('defs', {}, g), lg = el('linearGradient', { id, x1: 0, y1: 0, x2: 0, y2: 1 }, d);
    el('stop', { offset: 0, 'stop-color': C.sky[0] }, lg); el('stop', { offset: 1, 'stop-color': C.sky[1] }, lg);
    el('rect', { width: ctx.W, height: h, fill: `url(#${id})` }, g);
  }
  function stars(g, ctx, n = 60, maxY = 0.6) {
    const r = rnd(7), out = [];
    for (let i = 0; i < n; i++) out.push(el('circle', { cx: r() * ctx.W, cy: r() * ctx.gy * maxY, r: 1 + r() * 2.4 * ctx.u, fill: '#fff', opacity: 0.7 }, g));
    return t => out.forEach((s, i) => s.setAttribute('opacity', 0.35 + 0.45 * Math.abs(Math.sin(t * 1.3 + i))));
  }
  function sunMoon(g, ctx, C, x = 0.8, y = 0.14) {
    if (ctx.time === 'night') { el('circle', { cx: ctx.W * x, cy: ctx.H * y, r: 48 * ctx.u, fill: '#fdf6d8' }, g); el('circle', { cx: ctx.W * x + 18 * ctx.u, cy: ctx.H * y - 10 * ctx.u, r: 44 * ctx.u, fill: C.sky[0] }, g); }
    else el('circle', { cx: ctx.W * x, cy: ctx.H * y + (ctx.time === 'sunset' ? ctx.gy * 0.25 : 0), r: 60 * ctx.u, fill: C.sun, opacity: 0.95 }, g);
  }
  function clouds(g, ctx, n = 3, y = 0.12) {
    if (ctx.time === 'night') return () => {};
    const list = [];
    for (let i = 0; i < n; i++) {
      const c = el('g', { opacity: 0.9 }, g), s = (0.8 + (i % 3) * 0.25) * ctx.u;
      [[0, 0, 40], [38, -14, 46], [80, 0, 38], [40, 10, 40]].forEach(([x, yy, r]) => el('circle', { cx: x * s, cy: yy * s, r: r * s, fill: '#ffffff' }, c));
      list.push({ c, x0: (i / n) * ctx.W * 1.1, y: ctx.H * (y + (i % 2) * 0.06), sp: 14 + i * 6 });
    }
    return t => list.forEach(o => o.c.setAttribute('transform', `translate(${((o.x0 + t * o.sp * ctx.u) % (ctx.W + 300 * ctx.u)) - 150 * ctx.u} ${o.y})`));
  }
  function hills(g, ctx, col, h, k = 0.25, off = 0) {
    const W = ctx.W, gy = ctx.gy;
    el('path', { d: `M0 ${gy} Q${W * (0.2 + off)} ${gy - h} ${W * 0.45} ${gy - h * 0.4} T${W} ${gy - h * 0.6} V${gy} Z`, fill: col, opacity: 1 - k }, g);
  }
  function tree(g, ctx, x, s, C, kind = 'round') {
    const gy = ctx.gy, u = ctx.u * s;
    el('rect', { x: x - 9 * u, y: gy - 120 * u, width: 18 * u, height: 120 * u, fill: C.woodD }, g);
    if (kind === 'pine') [0, 1, 2].forEach(i => el('path', { d: `M${x - (70 - i * 15) * u} ${gy - (90 + i * 55) * u} L${x} ${gy - (190 + i * 55) * u} L${x + (70 - i * 15) * u} ${gy - (90 + i * 55) * u} Z`, fill: i % 2 ? C.greenD : C.green }, g));
    else if (kind === 'palm') { el('path', { d: `M${x} ${gy} Q${x + 30 * u} ${gy - 150 * u} ${x + 10 * u} ${gy - 260 * u}`, stroke: C.woodD, 'stroke-width': 16 * u, fill: 'none' }, g); [-60, -20, 20, 60, 100].forEach(a => el('path', { d: `M${x + 10 * u} ${gy - 260 * u} q${Math.cos(a * Math.PI / 180) * 60 * u} -40 ${Math.cos(a * Math.PI / 180) * 120 * u} ${Math.abs(a) * 0.6 * u}`, stroke: C.green, 'stroke-width': 16 * u, fill: 'none', 'stroke-linecap': 'round' }, g)); }
    else { el('circle', { cx: x, cy: gy - 165 * u, r: 70 * u, fill: C.green }, g); el('circle', { cx: x - 45 * u, cy: gy - 130 * u, r: 45 * u, fill: C.greenD, opacity: 0.8 }, g); el('circle', { cx: x + 45 * u, cy: gy - 135 * u, r: 50 * u, fill: C.green }, g); }
  }
  function windowPane(g, ctx, C, x, y, w, h, opts = {}) {
    el('rect', { x, y, width: w, height: h, rx: 6 * ctx.u, fill: ctx.time === 'night' ? '#1c2a52' : C.glass, stroke: C.line, 'stroke-width': 6 * ctx.u }, g);
    if (ctx.time === 'night') el('circle', { cx: x + w * 0.7, cy: y + h * 0.3, r: Math.min(w, h) * 0.12, fill: '#fdf6d8' }, g);
    else el('circle', { cx: x + w * 0.75, cy: y + h * 0.28, r: Math.min(w, h) * 0.1, fill: C.sun, opacity: 0.7 }, g);
    el('line', { x1: x + w / 2, y1: y, x2: x + w / 2, y2: y + h, stroke: C.line, 'stroke-width': 4 * ctx.u }, g);
    el('line', { x1: x, y1: y + h / 2, x2: x + w, y2: y + h / 2, stroke: C.line, 'stroke-width': 4 * ctx.u }, g);
    if (opts.curtain) [x - w * 0.12, x + w * 0.9].forEach(cx => el('path', { d: `M${cx} ${y - 10 * ctx.u} h${w * 0.22} q${-w * 0.08} ${h * 0.5} 0 ${h + 20 * ctx.u} h${-w * 0.22} q${w * 0.06} ${-h * 0.5} 0 ${-h - 20 * ctx.u} Z`, fill: C.a1, opacity: 0.55 }, g));
  }
  function interior(g, ctx, C, wallCol) {
    const { W, gy, H } = ctx;
    el('rect', { width: W, height: gy, fill: wallCol || C.wall }, g);
    el('rect', { y: gy, width: W, height: H - gy, fill: C.floor }, g);
    el('rect', { y: gy - 14 * ctx.u, width: W, height: 14 * ctx.u, fill: C.wall2 }, g);
  }
  function shelf(g, ctx, C, x, y, w, rows = 3) {
    const u = ctx.u, r = rnd(Math.round(x));
    for (let i = 0; i < rows; i++) {
      const yy = y + i * 90 * u;
      el('rect', { x, y: yy + 70 * u, width: w, height: 8 * u, fill: C.woodD }, g);
      let bx = x + 6 * u;
      while (bx < x + w - 20 * u) { const bw = (12 + r() * 14) * u, bh = (40 + r() * 28) * u; el('rect', { x: bx, y: yy + 70 * u - bh, width: bw, height: bh, fill: [C.a1, C.a2, C.a3, C.line][Math.floor(r() * 4)], opacity: 0.8 }, g); bx += bw + 3 * u; }
    }
  }
  function lamp(g, ctx, C, x, h) { const u = ctx.u, gy = ctx.gy; el('line', { x1: x, y1: gy, x2: x, y2: gy - h * u, stroke: C.line, 'stroke-width': 6 * u }, g); el('path', { d: `M${x - 34 * u} ${gy - h * u} L${x + 34 * u} ${gy - h * u} L${x + 20 * u} ${gy - (h + 50) * u} L${x - 20 * u} ${gy - (h + 50) * u} Z`, fill: C.a3, opacity: 0.85 }, g); }
  function plant(g, ctx, C, x) { const u = ctx.u, gy = ctx.gy; el('path', { d: `M${x - 26 * u} ${gy} L${x - 20 * u} ${gy - 50 * u} L${x + 20 * u} ${gy - 50 * u} L${x + 26 * u} ${gy} Z`, fill: C.a1, opacity: 0.8 }, g); [-40, -15, 10, 35].forEach((a, i) => el('ellipse', { cx: x + a * 0.6 * u, cy: gy - (85 + (i % 2) * 15) * u, rx: 14 * u, ry: 40 * u, transform: `rotate(${a} ${x + a * 0.6 * u} ${gy - (85 + (i % 2) * 15) * u})`, fill: C.green }, g)); }
  function frame(g, ctx, C, x, y, w, h) { el('rect', { x, y, width: w, height: h, fill: '#fff', stroke: C.woodD, 'stroke-width': 8 * ctx.u }, g); el('path', { d: `M${x + 8} ${y + h - 8} L${x + w * 0.4} ${y + h * 0.45} L${x + w * 0.6} ${y + h * 0.7} L${x + w * 0.75} ${y + h * 0.5} L${x + w - 8} ${y + h - 8} Z`, fill: C.a2, opacity: 0.6 }, g); }
  function clock(g, ctx, C, x, y, r) { el('circle', { cx: x, cy: y, r: r * ctx.u, fill: '#fff', stroke: C.line, 'stroke-width': 6 * ctx.u }, g); const hand = el('line', { x1: x, y1: y, x2: x, y2: y - r * 0.7 * ctx.u, stroke: C.ink, 'stroke-width': 4 * ctx.u, 'stroke-linecap': 'round' }, g); el('line', { x1: x, y1: y, x2: x + r * 0.45 * ctx.u, y2: y, stroke: C.ink, 'stroke-width': 5 * ctx.u, 'stroke-linecap': 'round' }, g); return t => hand.setAttribute('transform', `rotate(${t * 36} ${x} ${y})`); }
  function building(g, ctx, C, x, w, h, lit) {
    const gy = ctx.gy, u = ctx.u, r = rnd(Math.round(x + h));
    el('rect', { x, y: gy - h, width: w, height: h, fill: lit ? '#1f2a4a' : mix(C.wall, C.ink, 0.12) }, g);
    for (let yy = gy - h + 20 * u; yy < gy - 40 * u; yy += 44 * u) for (let xx = x + 14 * u; xx < x + w - 24 * u; xx += 34 * u)
      el('rect', { x: xx, y: yy, width: 18 * u, height: 24 * u, fill: lit ? (r() > 0.45 ? '#ffd166' : '#2c3a63') : C.glass, opacity: lit ? 1 : 0.9 }, g);
  }
  function road(g, ctx, C) { const { W, H, gy, u } = ctx; el('rect', { y: gy, width: W, height: H - gy, fill: ctx.time === 'night' ? '#20252e' : '#8d949e' }, g); for (let x = 0; x < W; x += 140 * u) el('rect', { x, y: gy + (H - gy) * 0.35, width: 70 * u, height: 8 * u, fill: '#f5f5f5', opacity: 0.8 }, g); }

  /* ---------- weather ---------- */
  function weather(g, ctx) {
    const { W, H, u } = ctx, kind = ctx.weather;
    if (!kind || kind === 'none') return () => {};
    if (kind === 'fog') { el('rect', { width: W, height: H, fill: '#ffffff', opacity: 0.22 }, g); return () => {}; }
    const r = rnd(11), n = kind === 'rain' ? 90 : 60, ps = [];
    for (let i = 0; i < n; i++) {
      const x = r() * W, y = r() * H, sp = kind === 'rain' ? 900 + r() * 400 : 60 + r() * 60;
      const e = kind === 'rain' ? el('line', { x1: 0, y1: 0, x2: -6 * u, y2: 28 * u, stroke: '#8fb8de', 'stroke-width': 2.5 * u, opacity: 0.7 }, g)
        : kind === 'snow' ? el('circle', { r: (3 + r() * 4) * u, fill: '#fff', opacity: 0.9 }, g)
          : el('ellipse', { rx: 9 * u, ry: 4 * u, fill: ['#e67e22', '#d35400', '#f1c40f'][i % 3], opacity: 0.85 }, g);
      ps.push({ e, x, y, sp, ph: r() * 6 });
    }
    return t => ps.forEach(p => { const y = (p.y + t * p.sp * u) % (H + 40 * u) - 20 * u; const x = p.x + (kind === 'rain' ? -t * 80 * u : Math.sin(t * 1.5 + p.ph) * 30 * u); p.e.setAttribute('transform', `translate(${((x % W) + W) % W} ${y}) rotate(${kind === 'leaves' ? t * 90 + p.ph * 50 : 0})`); });
  }

  /* ---------- các bối cảnh ---------- */
  const B = {};
  B.plain = (g, ctx, C) => () => {};
  B.room = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C);
    windowPane(g, ctx, C, W * 0.08, gy - 470 * u, 210 * u, 230 * u, { curtain: true });
    frame(g, ctx, C, W * 0.72, gy - 430 * u, 150 * u, 110 * u);
    el('rect', { x: W * 0.62, y: gy - 120 * u, width: W * 0.34, height: 80 * u, rx: 24 * u, fill: C.a2, opacity: 0.55 }, g);
    el('rect', { x: W * 0.6, y: gy - 170 * u, width: W * 0.38, height: 60 * u, rx: 24 * u, fill: C.a2, opacity: 0.45 }, g);
    lamp(g, ctx, C, W * 0.05, 300); el('ellipse', { cx: W * 0.5, cy: gy + 40 * u, rx: W * 0.3, ry: 26 * u, fill: C.a1, opacity: 0.18 }, g);
    return () => {};
  };
  B.bedroom = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, C.a2, 0.1));
    windowPane(g, ctx, C, W * 0.38, gy - 480 * u, 220 * u, 220 * u, { curtain: true });
    el('rect', { x: W * 0.66, y: gy - 110 * u, width: W * 0.33, height: 110 * u, rx: 10 * u, fill: C.wood }, g);
    el('rect', { x: W * 0.66, y: gy - 140 * u, width: W * 0.33, height: 40 * u, rx: 14 * u, fill: '#fff' }, g);
    el('rect', { x: W * 0.95, y: gy - 230 * u, width: 30 * u, height: 230 * u, fill: C.woodD }, g);
    el('rect', { x: W * 0.06, y: gy - 100 * u, width: 90 * u, height: 100 * u, fill: C.wood }, g); lamp(g, ctx, C, W * 0.06 + 45 * u, 100 + 60);
    return () => {};
  };
  B.kitchen = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, '#fff3e0', 0.5));
    for (let x = 0; x < W; x += 50 * u) el('line', { x1: x, y1: gy - 330 * u, x2: x, y2: gy - 150 * u, stroke: C.soft, 'stroke-width': 2 }, g);
    el('rect', { x: 0, y: gy - 150 * u, width: W, height: 150 * u, fill: C.wood }, g);
    el('rect', { x: 0, y: gy - 160 * u, width: W, height: 16 * u, fill: C.woodD }, g);
    el('rect', { x: W * 0.82, y: gy - 420 * u, width: W * 0.16, height: 420 * u, rx: 12 * u, fill: '#eceff1', stroke: C.line, 'stroke-width': 4 * u }, g);
    el('rect', { x: W * 0.06, y: gy - 470 * u, width: W * 0.3, height: 110 * u, fill: C.wood, opacity: 0.9 }, g);
    [0.45, 0.52, 0.59].forEach((x, i) => { el('line', { x1: W * x, y1: gy - 480 * u, x2: W * x, y2: gy - 420 * u, stroke: C.line, 'stroke-width': 3 * u }, g); el('circle', { cx: W * x, cy: gy - 395 * u, r: (24 + i * 4) * u, fill: '#607d8b' }, g); });
    return () => {};
  };
  B.office = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C);
    windowPane(g, ctx, C, W * 0.06, gy - 500 * u, 260 * u, 260 * u);
    const tick = clock(g, ctx, C, W * 0.5, gy - 430 * u, 40);
    el('rect', { x: W * 0.62, y: gy - 110 * u, width: W * 0.34, height: 14 * u, fill: C.woodD }, g);
    el('line', { x1: W * 0.65, y1: gy - 96 * u, x2: W * 0.65, y2: gy, stroke: C.woodD, 'stroke-width': 8 * u }, g); el('line', { x1: W * 0.93, y1: gy - 96 * u, x2: W * 0.93, y2: gy, stroke: C.woodD, 'stroke-width': 8 * u }, g);
    el('rect', { x: W * 0.72, y: gy - 220 * u, width: W * 0.14, height: 100 * u, rx: 6 * u, fill: '#263238' }, g); el('rect', { x: W * 0.725, y: gy - 214 * u, width: W * 0.13, height: 86 * u, fill: C.a2, opacity: 0.6 }, g);
    plant(g, ctx, C, W * 0.04 + 30 * u); shelf(g, ctx, C, W * 0.72, gy - 520 * u, W * 0.22, 2);
    return tick;
  };
  B.classroom = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, '#fff8e1', 0.4));
    el('rect', { x: W * 0.1, y: gy - 460 * u, width: W * 0.8, height: 260 * u, rx: 8 * u, fill: '#2f4f3e', stroke: C.wood, 'stroke-width': 12 * u }, g);
    const scr = el('path', { d: `M${W * 0.16} ${gy - 400 * u} q40 -30 80 0 t80 0 M${W * 0.16} ${gy - 340 * u} h${W * 0.3} M${W * 0.6} ${gy - 380 * u} l40 40 m0 -40 l-40 40`, stroke: '#e8f5e9', 'stroke-width': 5 * u, fill: 'none', opacity: 0.8, 'stroke-linecap': 'round' }, g);
    const tick = clock(g, ctx, C, W * 0.9, gy - 520 * u, 32);
    [0.08, 0.86].forEach(x => { el('rect', { x: W * x - 50 * u, y: gy - 90 * u, width: 120 * u, height: 12 * u, fill: C.wood }, g); el('line', { x1: W * x - 40 * u, y1: gy - 80 * u, x2: W * x - 40 * u, y2: gy, stroke: C.woodD, 'stroke-width': 6 * u }, g); el('line', { x1: W * x + 60 * u, y1: gy - 80 * u, x2: W * x + 60 * u, y2: gy, stroke: C.woodD, 'stroke-width': 6 * u }, g); });
    return tick;
  };
  B.library = (g, ctx, C) => { const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, C.wood, 0.15)); shelf(g, ctx, C, W * 0.02, gy - 560 * u, W * 0.3, 5); shelf(g, ctx, C, W * 0.68, gy - 560 * u, W * 0.3, 5); lamp(g, ctx, C, W * 0.5, 260); return () => {}; };
  B.lab = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, '#e0f7fa', 0.5));
    el('rect', { x: 0, y: gy - 120 * u, width: W, height: 16 * u, fill: '#90a4ae' }, g);
    const bubbles = [];
    [[0.08, '#4dd0e1'], [0.16, '#ff8a65'], [0.82, '#aed581'], [0.9, '#ba68c8']].forEach(([x, col], i) => {
      el('path', { d: `M${W * x - 12 * u} ${gy - 200 * u} v50 l-30 ${50 * u} h${84 * u} l-30 ${-50 * u} v-50 Z`.replace('v50', `v${50 * u}`).replace('v-50', `v${-50 * u}`), fill: col, opacity: 0.7, stroke: C.line, 'stroke-width': 3 * u }, g);
      bubbles.push(el('circle', { cx: W * x + 6 * u, cy: gy - 150 * u, r: 6 * u, fill: '#fff', opacity: 0.8 }, g));
    });
    windowPane(g, ctx, C, W * 0.38, gy - 480 * u, 240 * u, 200 * u);
    return t => bubbles.forEach((b, i) => b.setAttribute('cy', ctx.gy - 150 * u - ((t * 40 + i * 20) % 50) * u));
  };
  B.cafe = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, '#efebe9', 0.5));
    el('rect', { x: W * 0.06, y: gy - 470 * u, width: W * 0.3, height: 190 * u, rx: 6 * u, fill: '#3e2723' }, g);
    [0, 1, 2].forEach(i => el('line', { x1: W * 0.09, y1: gy - (420 - i * 45) * u, x2: W * (0.25 + (i % 2) * 0.06), y2: gy - (420 - i * 45) * u, stroke: '#fff', 'stroke-width': 5 * u, opacity: 0.8 }, g));
    el('rect', { x: W * 0.6, y: gy - 150 * u, width: W * 0.4, height: 150 * u, fill: C.wood }, g); el('rect', { x: W * 0.58, y: gy - 162 * u, width: W * 0.42, height: 14 * u, fill: C.woodD }, g);
    [0.68, 0.8, 0.92].forEach(x => { el('rect', { x: W * x - 14 * u, y: gy - 190 * u, width: 28 * u, height: 30 * u, rx: 4 * u, fill: '#fff', stroke: C.line, 'stroke-width': 3 * u }, g); });
    const steam = [0.68, 0.8, 0.92].map(x => el('path', { d: `M${W * x} ${gy - 196 * u} q-8 -14 0 -28 t0 -28`, stroke: C.line, 'stroke-width': 3 * u, fill: 'none', opacity: 0.6 }, g));
    return t => steam.forEach((s, i) => s.setAttribute('opacity', 0.3 + 0.4 * Math.abs(Math.sin(t * 1.5 + i))));
  };
  B.shop = (g, ctx, C) => {
    const { W, gy, u } = ctx; sky(g, ctx, C); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: C.floor }, g);
    [[0.02, C.a1], [0.36, C.a2], [0.7, C.a3]].forEach(([x, col]) => {
      el('rect', { x: W * x, y: gy - 260 * u, width: W * 0.28, height: 260 * u, fill: mix(C.wall, C.ink, 0.06) }, g);
      for (let i = 0; i < 6; i++) el('path', { d: `M${W * x + i * W * 0.28 / 6} ${gy - 300 * u} h${W * 0.28 / 6} v${50 * u} q${-W * 0.28 / 12} ${24 * u} ${-W * 0.28 / 6} 0 Z`, fill: i % 2 ? col : '#fff' }, g);
      el('rect', { x: W * x + 10 * u, y: gy - 90 * u, width: W * 0.28 - 20 * u, height: 70 * u, fill: C.wood }, g);
      for (let i = 0; i < 6; i++) el('circle', { cx: W * x + 30 * u + i * 32 * u, cy: gy - 100 * u, r: 14 * u, fill: ['#ef5350', '#ffa726', '#9ccc65'][i % 3] }, g);
    });
    return clouds(g, ctx, 2, 0.06);
  };
  B.street = (g, ctx, C) => {
    const { W, gy, u } = ctx; sky(g, ctx, C); const tw = ctx.time === 'night' ? stars(g, ctx, 40, 0.4) : () => {}; sunMoon(g, ctx, C);
    const cl = clouds(g, ctx, 2, 0.08);
    [[0, 0.24, 520], [0.26, 0.2, 380], [0.6, 0.18, 460], [0.8, 0.22, 600]].forEach(([x, w, h]) => building(g, ctx, C, W * x, W * w, h * u, ctx.time === 'night'));
    road(g, ctx, C);
    const lampX = W * 0.9; el('line', { x1: lampX, y1: gy, x2: lampX, y2: gy - 330 * u, stroke: '#455a64', 'stroke-width': 8 * u }, g); el('circle', { cx: lampX - 20 * u, cy: gy - 330 * u, r: 18 * u, fill: '#ffd54f' }, g);
    const car = el('g', {}, g); el('rect', { x: 0, y: -60 * u, width: 200 * u, height: 50 * u, rx: 14 * u, fill: C.a1 }, car); el('rect', { x: 40 * u, y: -100 * u, width: 110 * u, height: 45 * u, rx: 12 * u, fill: C.a1 }, car); el('rect', { x: 52 * u, y: -92 * u, width: 40 * u, height: 30 * u, fill: C.glass }, car); [40, 160].forEach(x => el('circle', { cx: x * u, cy: -10 * u, r: 20 * u, fill: '#263238' }, car));
    return t => { tw(t); cl(t); car.setAttribute('transform', `translate(${((t * 260 * u) % (W + 600 * u)) - 300 * u} ${gy + (ctx.H - gy) * 0.75})`); };
  };
  B.city_night = (g, ctx, C) => { ctx.time = 'night'; const C2 = palette(ctx.style, 'night'); return B.street(g, ctx, C2); };
  B.park = (g, ctx, C) => {
    const { W, gy, u } = ctx; sky(g, ctx, C); sunMoon(g, ctx, C, 0.85); const cl = clouds(g, ctx, 3);
    hills(g, ctx, C.green, 140 * u, 0.4); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: mix(C.green, '#ffffff', 0.25) }, g);
    el('path', { d: `M${W * 0.35} ${ctx.H} Q${W * 0.5} ${gy + 40 * u} ${W * 0.65} ${gy} H${W * 0.75} Q${W * 0.6} ${gy + 60 * u} ${W * 0.6} ${ctx.H} Z`, fill: '#d7ccc8', opacity: 0.8 }, g);
    tree(g, ctx, W * 0.08, 1.2, C); tree(g, ctx, W * 0.92, 1, C);
    el('rect', { x: W * 0.74, y: gy - 60 * u, width: 150 * u, height: 14 * u, fill: C.wood }, g); el('rect', { x: W * 0.74, y: gy - 100 * u, width: 150 * u, height: 12 * u, fill: C.wood }, g);
    const birds = [0, 1, 2].map(i => el('path', { d: `M0 0 q10 -10 20 0 q10 -10 20 0`, stroke: C.ink, 'stroke-width': 3 * u, fill: 'none', opacity: 0.6 }, g));
    return t => { cl(t); birds.forEach((b, i) => b.setAttribute('transform', `translate(${(t * 60 * u + i * 90 * u) % W} ${ctx.H * 0.2 + i * 30 * u + Math.sin(t * 3 + i) * 10 * u}) scale(${u})`)); };
  };
  B.nature = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, C); sunMoon(g, ctx, C); const tw = ctx.time === 'night' ? stars(g, ctx) : () => {}; const cl = clouds(g, ctx, 3); hills(g, ctx, C.greenD, 260 * u, 0.5, 0.2); hills(g, ctx, C.green, 170 * u, 0.2); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: C.green, opacity: 0.6 }, g); tree(g, ctx, W * 0.1, 1, C); tree(g, ctx, W * 0.9, 0.8, C); return t => { tw(t); cl(t); }; };
  B.forest = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, C); const tw = ctx.time === 'night' ? stars(g, ctx) : () => {}; for (let i = 0; i < 9; i++) tree(g, ctx, W * (i / 8), 0.7 + (i % 3) * 0.25, { ...C, green: mix(C.greenD, C.sky[0], 0.4), greenD: mix(C.greenD, C.sky[0], 0.3) }, 'pine'); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: C.greenD, opacity: 0.55 }, g); [0.05, 0.95].forEach(x => tree(g, ctx, W * x, 1.4, C, 'pine')); return tw; };
  B.beach = (g, ctx, C) => {
    const { W, gy, H, u } = ctx; sky(g, ctx, C); sunMoon(g, ctx, C, 0.7, 0.16); const cl = clouds(g, ctx, 2);
    const sea = el('path', { fill: ctx.time === 'night' ? '#123' : '#4fc3f7' }, g);
    el('rect', { y: gy, width: W, height: H - gy, fill: '#f6d7a7' }, g);
    tree(g, ctx, W * 0.1, 1.2, C, 'palm');
    el('path', { d: `M${W * 0.86} ${gy} L${W * 0.86} ${gy - 220 * u}`, stroke: C.woodD, 'stroke-width': 6 * u }, g); el('path', { d: `M${W * 0.86 - 110 * u} ${gy - 200 * u} Q${W * 0.86} ${gy - 300 * u} ${W * 0.86 + 110 * u} ${gy - 200 * u} Z`, fill: C.a1 }, g);
    return t => { cl(t); let d = `M0 ${gy - 160 * u}`; for (let x = 0; x <= W + 40; x += 40 * u) d += ` L${x} ${gy - 160 * u + Math.sin(x / (60 * u) + t * 2) * 8 * u}`; sea.setAttribute('d', d + ` L${W} ${gy} L0 ${gy} Z`); };
  };
  B.mountain = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, C); sunMoon(g, ctx, C, 0.2); const cl = clouds(g, ctx, 3, 0.2); [[0.25, 520, '#78909c'], [0.6, 640, '#607d8b'], [0.9, 460, '#90a4ae']].forEach(([x, h, col]) => { el('path', { d: `M${W * x - 360 * u} ${gy} L${W * x} ${gy - h * u} L${W * x + 360 * u} ${gy} Z`, fill: col }, g); el('path', { d: `M${W * x - 70 * u} ${gy - (h - 100) * u} L${W * x} ${gy - h * u} L${W * x + 70 * u} ${gy - (h - 100) * u} l-30 20 l-20 -15 l-20 20 Z`, fill: '#fff' }, g); }); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: C.green, opacity: 0.5 }, g); return cl; };
  B.desert = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, { ...C, sky: ctx.time === 'night' ? C.sky : ['#ffcc80', '#fff3e0'] }); sunMoon(g, ctx, C, 0.78, 0.15); hills(g, ctx, '#e6b980', 200 * u, 0.2, 0.1); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: '#f2d29b' }, g); [[0.12, 1], [0.9, 0.8]].forEach(([x, s]) => { const xx = W * x, uu = u * s; el('rect', { x: xx - 18 * uu, y: gy - 220 * uu, width: 36 * uu, height: 220 * uu, rx: 18 * uu, fill: '#558b2f' }, g); el('path', { d: `M${xx - 18 * uu} ${gy - 120 * uu} h-40 v-60`.replace('h-40', `h${-40 * uu}`).replace('v-60', `v${-60 * uu}`), stroke: '#558b2f', 'stroke-width': 26 * uu, fill: 'none', 'stroke-linecap': 'round' }, g); }); return () => {}; };
  B.farm = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, C); sunMoon(g, ctx, C); const cl = clouds(g, ctx, 3); hills(g, ctx, C.green, 120 * u, 0.3); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: '#c5e1a5' }, g); for (let i = 0; i < 6; i++) el('line', { x1: 0, y1: gy + (i + 1) * 30 * u, x2: W, y2: gy + (i + 1) * 30 * u, stroke: '#8bc34a', 'stroke-width': 6 * u }, g); const bx = W * 0.78; el('rect', { x: bx, y: gy - 220 * u, width: 200 * u, height: 220 * u, fill: '#c62828' }, g); el('path', { d: `M${bx - 20 * u} ${gy - 220 * u} L${bx + 100 * u} ${gy - 320 * u} L${bx + 220 * u} ${gy - 220 * u} Z`, fill: '#8e0000' }, g); el('rect', { x: bx + 70 * u, y: gy - 120 * u, width: 60 * u, height: 120 * u, fill: '#fff' }, g); for (let x = 0; x < W * 0.6; x += 60 * u) el('line', { x1: x, y1: gy - 60 * u, x2: x, y2: gy, stroke: C.wood, 'stroke-width': 8 * u }, g); el('line', { x1: 0, y1: gy - 45 * u, x2: W * 0.6, y2: gy - 45 * u, stroke: C.wood, 'stroke-width': 8 * u }, g); return cl; };
  B.space = (g, ctx, C) => { const { W, H, u } = ctx; el('rect', { width: W, height: H, fill: '#070b1f' }, g); const tw = stars(g, { ...ctx, gy: H }, 120, 1); el('circle', { cx: W * 0.78, cy: H * 0.2, r: 90 * u, fill: '#ff8a65' }, g); el('ellipse', { cx: W * 0.78, cy: H * 0.2, rx: 150 * u, ry: 26 * u, fill: 'none', stroke: '#ffe0b2', 'stroke-width': 8 * u, transform: `rotate(-15 ${W * 0.78} ${H * 0.2})` }, g); el('circle', { cx: W * 0.15, cy: H * 0.35, r: 40 * u, fill: '#81d4fa' }, g); el('rect', { y: ctx.gy, width: W, height: H - ctx.gy, fill: '#9e9e9e', opacity: 0.35 }, g); return tw; };
  B.night = (g, ctx, C) => { ctx.time = 'night'; return B.nature(g, ctx, palette(ctx.style, 'night')); };
  B.stage = (g, ctx, C) => {
    const { W, gy, H, u } = ctx; el('rect', { width: W, height: H, fill: '#1a1033' }, g);
    [0, 1].forEach(s => { const x = s ? W : 0, d = s ? -1 : 1; el('path', { d: `M${x} 0 h${d * W * 0.16} q${-d * W * 0.05} ${gy * 0.5} ${d * W * 0.02} ${gy} h${-d * W * 0.18} Z`, fill: '#b71c1c' }, g); });
    el('rect', { width: W, height: 60 * u, fill: '#8e0000' }, g);
    const spot = el('path', { d: `M${W * 0.5} 0 L${W * 0.2} ${gy} L${W * 0.8} ${gy} Z`, fill: '#fff', opacity: 0.1 }, g);
    el('rect', { y: gy, width: W, height: H - gy, fill: '#5d4037' }, g); el('ellipse', { cx: W / 2, cy: gy + 10 * u, rx: W * 0.3, ry: 24 * u, fill: '#fff59d', opacity: 0.3 }, g);
    return t => spot.setAttribute('opacity', 0.08 + 0.04 * Math.sin(t * 2));
  };
  B.studio = (g, ctx, C) => { const { W, gy, H, u } = ctx; const id = 'st' + Math.random().toString(36).slice(2, 6); const d = el('defs', {}, g), rg = el('radialGradient', { id, cx: 0.5, cy: 0.45, r: 0.7 }, d); el('stop', { offset: 0, 'stop-color': mix(C.bg, C.a2, 0.15) }, rg); el('stop', { offset: 1, 'stop-color': mix(C.bg, C.ink, 0.12) }, rg); el('rect', { width: W, height: H, fill: `url(#${id})` }, g); el('ellipse', { cx: W / 2, cy: gy, rx: W * 0.42, ry: 30 * u, fill: C.a1, opacity: 0.12 }, g); return () => {}; };
  B.hospital = (g, ctx, C) => {
    const { W, gy, u } = ctx; interior(g, ctx, C, '#e8f5e9');
    const cx = W * 0.08 + 45 * u, cy = gy - 425 * u;
    el('rect', { x: cx - 45 * u, y: cy - 45 * u, width: 90 * u, height: 90 * u, rx: 8 * u, fill: '#fff' }, g);
    el('rect', { x: cx - 12 * u, y: cy - 32 * u, width: 24 * u, height: 64 * u, fill: '#e53935' }, g); el('rect', { x: cx - 32 * u, y: cy - 12 * u, width: 64 * u, height: 24 * u, fill: '#e53935' }, g);
    el('rect', { x: W * 0.66, y: gy - 120 * u, width: W * 0.32, height: 50 * u, rx: 10 * u, fill: '#fff', stroke: C.line, 'stroke-width': 4 * u }, g);
    el('rect', { x: W * 0.66, y: gy - 70 * u, width: 10 * u, height: 70 * u, fill: '#90a4ae' }, g); el('rect', { x: W * 0.96, y: gy - 70 * u, width: 10 * u, height: 70 * u, fill: '#90a4ae' }, g);
    el('rect', { x: W * 0.82, y: gy - 360 * u, width: 150 * u, height: 100 * u, fill: '#102027', stroke: C.line, 'stroke-width': 6 * u }, g);
    const mon = el('polyline', { fill: 'none', stroke: '#69f0ae', 'stroke-width': 4 * u }, g);
    return t => { let pts = ''; for (let i = 0; i <= 20; i++) { const x = W * 0.82 + i * 7.5 * u, ph = (i + t * 20) % 20; pts += `${x},${gy - 310 * u - (ph > 9 && ph < 11 ? 35 * u : 0)} `; } mon.setAttribute('points', pts); };
  };
  B.temple = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, { ...C, sky: ctx.time === 'night' ? C.sky : ['#f3e3bf', '#fff8e1'] }); sunMoon(g, ctx, C, 0.85); el('path', { d: `M${W * 0.05} ${gy - 470 * u} L${W * 0.5} ${gy - 600 * u} L${W * 0.95} ${gy - 470 * u} Z`, fill: '#d7ccc8', stroke: C.line, 'stroke-width': 4 * u }, g); el('rect', { x: W * 0.05, y: gy - 470 * u, width: W * 0.9, height: 30 * u, fill: '#bcaaa4' }, g); for (let i = 0; i < 6; i++) { const x = W * (0.09 + i * 0.165); el('rect', { x: x - 22 * u, y: gy - 440 * u, width: 44 * u, height: 420 * u, fill: '#efebe9', stroke: C.line, 'stroke-width': 3 * u }, g); } el('rect', { y: gy - 20 * u, width: W, height: 20 * u, fill: '#bcaaa4' }, g); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: '#d7ccc8' }, g); return () => {}; };
  B.castle = (g, ctx, C) => { const { W, gy, u } = ctx; sky(g, ctx, C); const tw = ctx.time === 'night' ? stars(g, ctx) : clouds(g, ctx, 2); hills(g, ctx, C.green, 100 * u, 0.3); const cx = W * 0.5, col = '#9e9e9e'; el('rect', { x: cx - 260 * u, y: gy - 300 * u, width: 520 * u, height: 300 * u, fill: col }, g); [-260, 180].forEach(dx => { el('rect', { x: cx + dx * u, y: gy - 430 * u, width: 80 * u, height: 430 * u, fill: mix(col, '#000', 0.1) }, g); el('path', { d: `M${cx + (dx - 10) * u} ${gy - 430 * u} L${cx + (dx + 40) * u} ${gy - 520 * u} L${cx + (dx + 90) * u} ${gy - 430 * u} Z`, fill: C.a1 }, g); }); for (let i = 0; i < 8; i++) el('rect', { x: cx - 260 * u + i * 66 * u, y: gy - 330 * u, width: 36 * u, height: 32 * u, fill: col }, g); el('path', { d: `M${cx - 60 * u} ${gy} V${gy - 120 * u} Q${cx} ${gy - 190 * u} ${cx + 60 * u} ${gy - 120 * u} V${gy} Z`, fill: '#4e342e' }, g); el('rect', { y: gy, width: W, height: ctx.H - gy, fill: C.green, opacity: 0.5 }, g); return tw; };
  B.river = (g, ctx, C) => { const { W, gy, H, u } = ctx; sky(g, ctx, C); sunMoon(g, ctx, C); const cl = clouds(g, ctx, 3); hills(g, ctx, C.green, 160 * u, 0.3); el('rect', { y: gy, width: W, height: H - gy, fill: C.green, opacity: 0.5 }, g); const water = el('rect', { y: gy + (H - gy) * 0.3, width: W, height: (H - gy) * 0.4, fill: '#4fc3f7', opacity: 0.8 }, g); el('path', { d: `M0 ${gy} Q${W / 2} ${gy - 160 * u} ${W} ${gy}`, stroke: C.woodD, 'stroke-width': 18 * u, fill: 'none' }, g); for (let i = 1; i < 10; i++) { const x = W * i / 10, y = gy - 160 * u * 4 * (i / 10) * (1 - i / 10); el('line', { x1: x, y1: y, x2: x, y2: gy, stroke: C.wood, 'stroke-width': 6 * u }, g); } const sh = [0, 1, 2, 3].map(i => el('line', { x1: 0, y1: 0, x2: 60 * u, y2: 0, stroke: '#fff', 'stroke-width': 4 * u, opacity: 0.6 }, g)); return t => { cl(t); sh.forEach((s, i) => s.setAttribute('transform', `translate(${(t * 80 * u + i * W / 4) % W} ${gy + (H - gy) * (0.38 + (i % 2) * 0.15)})`)); }; };
  B.bus = (g, ctx, C) => { const { W, gy, u } = ctx; interior(g, ctx, C, mix(C.wall, '#eceff1', 0.5)); const out = el('g', {}, g); for (let i = 0; i < 4; i++) { const x = W * (0.04 + i * 0.245); el('rect', { x, y: gy - 470 * u, width: W * 0.21, height: 200 * u, rx: 18 * u, fill: C.glass, stroke: C.line, 'stroke-width': 6 * u }, g); } const trees = []; for (let i = 0; i < 8; i++) trees.push(el('circle', { r: 50 * u, fill: C.green, opacity: 0.6 }, out)); el('line', { x1: 0, y1: gy - 520 * u, x2: W, y2: gy - 520 * u, stroke: C.line, 'stroke-width': 6 * u }, g); for (let x = W * 0.1; x < W; x += W * 0.2) el('line', { x1: x, y1: gy - 520 * u, x2: x, y2: gy - 470 * u, stroke: C.line, 'stroke-width': 3 * u }, g); return t => trees.forEach((tr, i) => { tr.setAttribute('cx', W - ((t * 300 * u + i * W / 4) % (W + 100 * u))); tr.setAttribute('cy', gy - 330 * u); }); };

  function draw(g, name, ctx, frontG) {
    ctx.u = Math.min(ctx.W, ctx.H) / 1080 * (ctx.H > ctx.W ? 1 : 1.25);
    ctx.time = ctx.time || 'day';
    const painter = B[name] || B.plain;
    const C = palette(ctx.style || {}, ctx.time);
    const back = el('g', {}, g);
    const upd = painter(back, ctx, C) || (() => {});
    if (!['space', 'stage', 'studio', 'plain'].includes(name))
      el('line', { x1: 0, y1: ctx.gy, x2: ctx.W, y2: ctx.gy, stroke: (ctx.style || {}).ground || C.ink, 'stroke-width': Math.max(3, ctx.W * 0.004), opacity: 0.6 }, back);
    if (ctx.time === 'sunset' && !['space', 'stage'].includes(name)) el('rect', { width: ctx.W, height: ctx.H, fill: '#ff7043', opacity: 0.08 }, back);
    if (ctx.time === 'night' && !['space', 'stage', 'city_night', 'night'].includes(name)) el('rect', { width: ctx.W, height: ctx.H, fill: '#0b1537', opacity: 0.32 }, back);
    const front = frontG || el('g', { 'pointer-events': 'none' }, g);
    const wx = weather(front, ctx);
    const dark = ctx.dark || ['space', 'stage', 'night', 'city_night'].includes(name) || (ctx.time === 'night' && !['plain', 'studio'].includes(name));
    return { update: t => { upd(t); wx(t); }, front, dark };
  }

  const H = { sky, stars, sunMoon, clouds, hills, tree, windowPane, interior, shelf, lamp, plant, frame, clock, building, road, mix, rnd, lum };
  VF.backdrops = { draw, palette, B, H, add: (name, fn) => { B[name] = fn; }, get NAMES() { return Object.keys(B); } };
})();
