/* Nhân vật 3D (Blender, repo BaoPV-DEV/Skills → hero3d) thay cho người que, cùng giao diện với VF.Stick:
 *   pose(p, x, ground, face, o) · say(text, alpha)
 * Ảnh động đã render sẵn (PNG trong suốt + meta.json) do engine đưa vào input.char3d[tên] = {sets:[…]}.
 * Mỗi động tác của AI Workflow (49 act) được quy về 12 động tác 3D; thiếu bộ nào thì lùi về talk/idle. */
(function () {
  const { el, clamp } = VF;
  const ANIM = {
    walk: 'walk', sneak: 'walk', run: 'run', jump: 'celebrate', cheer: 'celebrate', celebrate: 'celebrate', clap: 'celebrate',
    dance: 'celebrate', high_five: 'celebrate', thumbs_up: 'wave', wave: 'wave', greet: 'wave', bye: 'wave',
    point: 'point', present: 'point', explain: 'talk', talk: 'talk', argue: 'talk', ask: 'talk', phone: 'talk',
    think: 'look_up', look_up: 'look_up', wonder: 'look_up', idea: 'look_up', head_scratch: 'look_up',
    shocked: 'arms_up', scared: 'arms_up', surprised: 'arms_up', angry: 'arms_up',
    push: 'push', work: 'push', fight: 'push', lift: 'push', carry: 'push', type: 'push', cook: 'push',
    fall: 'fall', sit: 'crouch', sad: 'crouch', sleep: 'crouch', crouch: 'crouch', cry: 'crouch', facepalm: 'crouch',
  };
  // hướng nhìn mặc định của từng góc máy trong ảnh đã render (+1 = sang phải màn hình)
  const VIEW_DIR = { side: 1, side_l: -1, front34: 1, front34_l: -1, back34: 1, front: 0, back: 0, low_back: 0 };

  class Char3D {
    constructor(parent, char, size, info, light) {
      this.c = Object.assign({ scale: 1 }, char);
      this.S = size * (this.c.scale || 1);
      this.light = light;
      this.g = el('g', { class: 'char3d' }, parent);
      this.bubble = el('g', { opacity: 0 }, parent);
      this.sets = {};
      for (const s of (info && info.sets) || []) {
        const g = el('g', { style: 'display:none' }, this.g);
        const imgs = [];
        for (let i = 0; i < s.frames; i++) {
          const href = `${s.base}${String(i).padStart(4, '0')}.png`;
          imgs.push(el('image', { href, width: s.size[0], height: s.size[1], style: 'display:none' }, g));
          VF.waitFor(new Promise(r => { const im = new Image(); im.onload = im.onerror = r; im.src = href; }));
        }
        this.sets[s.key] = { ...s, g, imgs };
      }
      this.cur = null;
      this.head = null;
    }

    pick(anim, dir) {
      const all = Object.values(this.sets);
      const score = s => (s.anim === anim ? 100 : 0) + (s.light === this.light ? 10 : 0)
        + (dir && VIEW_DIR[s.view] === dir ? 4 : 0) + (dir && VIEW_DIR[s.view] === -dir ? 2 : 0) + (VIEW_DIR[s.view] ? 1 : 0);
      return all.filter(s => s.anim === anim).sort((a, b) => score(b) - score(a))[0];
    }

    pose(p, x, ground, face, o = {}) {
      const want = o.walking ? (o.act === 'run' ? 'run' : 'walk') : ANIM[o.act] || (o.talk > 0 ? 'talk' : 'idle');
      const dir = face < 0 ? -1 : 1;
      const set = this.pick(want, dir) || (o.talk > 0 && this.pick('talk', dir)) || this.pick('idle', dir) || Object.values(this.sets)[0];
      if (!set) return;
      if (this.cur !== set) {
        if (this.cur) this.cur.g.style.display = 'none';
        set.g.style.display = '';
        this.cur = set;
      }
      const since = Math.max(0, o.since ?? o.t ?? 0);
      let fi = Math.floor(since * set.fps);
      fi = set.loop ? fi % set.frames : Math.min(fi, set.frames - 1);
      set.imgs.forEach((im, i) => { im.style.display = i === fi ? '' : 'none'; });
      // tỉ lệ: chiều cao nhân vật trên màn hình ~ chiều cao người que
      const ppm = set.size[1] / set.ortho, sc = (this.S * 1.12) / (set.height_m * ppm);
      const F = set.feet[Math.min(fi, set.feet.length - 1)] || [0.5, 0.95];
      const fx = F[0] * set.size[0], fy = F[1] * set.size[1];
      const vd = VIEW_DIR[set.view] || 0, flip = vd && vd !== dir ? -1 : 1;
      const lift = (p && p.lift ? p.lift * this.S / 160 : 0);
      set.g.setAttribute('transform', `translate(${x} ${ground - lift}) scale(${sc * flip} ${sc}) translate(${-fx} ${-fy})`);
      const Hh = set.head && set.head[Math.min(fi, set.head.length - 1)];
      this.head = Hh ? [x + (Hh[0] * set.size[0] - fx) * sc * flip, ground - lift + (Hh[1] * set.size[1] - fy) * sc] : [x, ground - this.S];
    }

    say(text, alpha) {
      if (!this.head) return;
      if (this._say !== text) {
        this._say = text; this.bubble.innerHTML = '';
        if (text) {
          const fs = Math.max(26, this.S * 0.075), w = Math.min(text.length * fs * 0.55 + fs * 1.4, this.S * 2.4);
          el('rect', { x: -w / 2, y: -fs * 2.2, width: w, height: fs * 1.8, rx: fs * 0.6, fill: '#fff', stroke: '#222', 'stroke-width': 4 }, this.bubble);
          el('path', { d: `M-10 ${-fs * 0.42} L4 ${fs * 0.3} L12 ${-fs * 0.42}`, fill: '#fff', stroke: '#222', 'stroke-width': 4, 'stroke-linejoin': 'round' }, this.bubble);
          el('text', { x: 0, y: -fs * 0.95, 'text-anchor': 'middle', 'font-size': fs, 'font-weight': 700, 'font-family': 'var(--font)', fill: '#111', text }, this.bubble);
        }
      }
      this.bubble.setAttribute('opacity', alpha);
      this.bubble.setAttribute('transform', `translate(${this.head[0]} ${this.head[1] - this.S * 0.12})`);
    }
  }

  VF.Char3D = Char3D;
  VF.char3d = { ANIM, VIEW_DIR };
})();
