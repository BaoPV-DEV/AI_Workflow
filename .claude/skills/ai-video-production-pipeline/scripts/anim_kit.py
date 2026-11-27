"""anim_kit — procedural animation helpers for render.py "scene" shots.

A scene function draws one frame:   def s01(t, dur, ctx) -> PIL.Image (RGB/RGBA, ctx.W x ctx.H)
`ctx` is a SceneContext (size, cached layers, persistent particle systems).
Everything is deterministic in t, so any frame can be drawn on its own (stills, partial re-renders).

Needs: skia-python (pip install skia-python), numpy, Pillow.
"""
import math
from functools import lru_cache

import numpy as np
import skia
from PIL import Image, ImageFilter


# ---------------------------------------------------------------- colour / paint
def col(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return skia.Color(r, g, b, int(max(0, min(1, a)) * 255))


def paint(color="#ffffff", a=1.0, stroke=0, blur=0, blend=None, cap_round=True, shader=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor(col(color, a))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke)
        if cap_round:
            p.setStrokeCap(skia.Paint.kRound_Cap); p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend == "add":
        p.setBlendMode(skia.BlendMode.kPlus)
    elif blend == "screen":
        p.setBlendMode(skia.BlendMode.kScreen)
    elif blend == "multiply":
        p.setBlendMode(skia.BlendMode.kMultiply)
    if shader is not None:
        p.setShader(shader)
    return p


def lin(x0, y0, x1, y1, stops):
    """stops: [(pos, '#hex', alpha), ...]"""
    return skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)],
                                          [col(c, a) for _, c, a in stops], [p for p, _, _ in stops])


def rad(cx, cy, r, stops):
    return skia.GradientShader.MakeRadial(skia.Point(cx, cy), r,
                                          [col(c, a) for _, c, a in stops], [p for p, _, _ in stops])


def ease(t, kind="inout"):
    t = min(max(t, 0.0), 1.0)
    if kind == "out": return 1 - (1 - t) ** 3
    if kind == "in": return t ** 3
    if kind == "back":  # overshoot
        c = 1.70158; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
    return 3 * t * t - 2 * t * t * t


def lerp(a, b, t):
    return a + (b - a) * t


def hash01(*k):
    """Deterministic pseudo-random in [0,1) from ints/floats."""
    x = math.sin(sum((i + 1) * 12.9898 * v for i, v in enumerate(k)) + 78.233) * 43758.5453
    return x - math.floor(x)


# ---------------------------------------------------------------- context
_GR = None          # skia GPU context (OpenGL) when enabled and working
_GL_WINDOW = None


def init_gpu():
    """Try to create an OpenGL-backed skia context (needs `pip install glfw` and a GPU driver with a display).
    Returns True on success; on any failure stays on CPU raster. Headless servers usually fail here -> CPU."""
    global _GR, _GL_WINDOW
    if _GR is not None:
        return True
    try:
        import glfw
        if not glfw.init():
            return False
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        _GL_WINDOW = glfw.create_window(16, 16, "anim_kit", None, None)
        if not _GL_WINDOW:
            return False
        glfw.make_context_current(_GL_WINDOW)
        gr = skia.GrDirectContext.MakeGL()
        if gr is None:
            return False
        _GR = gr
        return True
    except Exception:
        return False


def new_surface(w, h):
    """Raster surface, or a GPU render target when init_gpu() succeeded."""
    w, h = max(1, int(w)), max(1, int(h))
    if _GR is not None:
        s = skia.Surface.MakeRenderTarget(_GR, skia.Budgeted.kNo, skia.ImageInfo.MakeN32Premul(w, h))
        if s is not None:
            return s
    return skia.Surface(w, h)


class SceneContext:
    """W, H are LOGICAL units the scene code draws in (e.g. 1920x1080).
    scale < 1 renders smaller physical frames (preview) with identical composition."""

    def __init__(self, W, H, fps=30, scale=1.0, gpu=False):
        self.W, self.H, self.fps, self.scale = W, H, fps, scale
        self.PW, self.PH = int(round(W * scale)), int(round(H * scale))
        self.gpu = init_gpu() if gpu else False
        self.cache = {}

    def surface(self):
        s = new_surface(self.PW, self.PH)
        if self.scale != 1.0:
            s.getCanvas().scale(self.scale, self.scale)
        return s

    def get(self, key, make):
        if key not in self.cache:
            self.cache[key] = make()
        return self.cache[key]


def to_pil(surface):
    if _GR is not None:
        surface.flushAndSubmit()
    arr = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return Image.fromarray(arr, "RGBA")


def soft(canvas, W, H, draw, scale=0.25, blend=None, alpha=1.0):
    """Draw soft/blurred content (rays, bokeh, glows, fog) into a low-res layer, then upscale onto `canvas`.
    The layer follows the canvas's current transform (camera moves apply). `draw(c)` uses logical W x H units.
    CPU note: skia's raster path is ~10x slower when an image is scaled AND blended with screen/add in one draw,
    so on CPU we upscale normally first, then blend 1:1 (≈14 ms instead of ≈75 ms per 1080p layer)."""
    m = canvas.getTotalMatrix()
    dev = canvas.getBaseLayerSize()
    DW, DH = dev.width(), dev.height()
    lw, lh = max(1, int(DW * scale)), max(1, int(DH * scale))
    layer = new_surface(lw, lh)
    c = layer.getCanvas(); c.clear(skia.Color(0, 0, 0, 0))
    c.scale(lw / DW, lh / DH); c.concat(m)
    draw(c)
    img = layer.makeImageSnapshot()
    p = skia.Paint(AntiAlias=True); p.setAlphaf(alpha)
    bm = {"add": skia.BlendMode.kPlus, "screen": skia.BlendMode.kScreen}.get(blend)
    canvas.save(); canvas.resetMatrix()
    lin_s = skia.SamplingOptions(skia.FilterMode.kLinear)
    if bm is None or _GR is not None:
        if bm is not None: p.setBlendMode(bm)
        canvas.drawImageRect(img, skia.Rect.MakeWH(DW, DH), lin_s, p)
    else:
        up = new_surface(DW, DH); uc = up.getCanvas(); uc.clear(skia.Color(0, 0, 0, 0))
        uc.drawImageRect(img, skia.Rect.MakeWH(DW, DH), lin_s)
        p.setBlendMode(bm)
        canvas.drawImage(up.makeImageSnapshot(), 0, 0, skia.SamplingOptions(), p)
    canvas.restore()


# ---------------------------------------------------------------- background layers
_SKY = {}


def sky(canvas, W, H, top="#070a1e", mid="#1b1240", bottom="#5a1a5e", glow=("#ff2e88", 0.35)):
    """Static gradient sky — rendered once per look and reused (a full-frame screen-blended gradient costs ~70 ms on CPU)."""
    key = (W, H, top, mid, bottom, glow, _GR is not None)
    if key not in _SKY:
        srf = new_surface(W, H); _sky(srf.getCanvas(), W, H, top, mid, bottom, glow)
        _SKY[key] = srf.makeImageSnapshot()
    canvas.drawImageRect(_SKY[key], skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear))


def _sky(canvas, W, H, top, mid, bottom, glow):
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint(shader=lin(0, 0, 0, H, [(0, top, 1), (0.55, mid, 1), (1, bottom, 1)])))
    c, a = glow
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint(shader=rad(W * 0.5, H * 0.75, W * 0.6, [(0, c, a), (1, c, 0)]), blend="screen"))


def make_city_layer(W, H, seed, horizon, hmin, hmax, wmin, wmax, body, win_p, win_a, gap=None, neon=0):
    """Pre-render one skyline layer (wider than the frame for parallax). Returns skia.Image."""
    LW = int(W * 1.4)
    s = skia.Surface(LW, H); c = s.getCanvas(); c.clear(skia.Color(0, 0, 0, 0))
    rng = np.random.default_rng(seed)
    x = -40.0
    hy = H * horizon
    palette = ["#ffcf8a", "#8ee6ff", "#ff8fc4", "#fff1c9"]
    while x < LW:
        bw = rng.uniform(wmin, wmax); bh = H * rng.uniform(hmin, hmax)
        cxn = (x + bw / 2 - LW * 0.2) / W
        if gap and gap[0] < cxn < gap[1]:
            x += bw * 0.6; continue
        top = hy - bh
        body_sh = lin(0, top, 0, hy, [(0, body[0], 1), (1, body[1], 1)])
        c.drawRect(skia.Rect.MakeLTRB(x, top, x + bw, hy + 4), paint(shader=body_sh))
        # roof details
        if rng.random() < 0.5:
            c.drawRect(skia.Rect.MakeLTRB(x + bw * 0.3, top - bh * 0.06, x + bw * 0.42, top), paint(body[0]))
        # edge light
        c.drawLine(x + 1, top, x + 1, hy, paint("#9fdcff", 0.10, stroke=2))
        ws = max(6, bw / 18); step = ws * 2.1
        for wy in np.arange(top + step, hy - step, step * 1.15):
            for wx in np.arange(x + step * 0.7, x + bw - step * 0.7, step):
                if rng.random() < win_p:
                    pc = palette[int(rng.integers(0, len(palette)))]
                    c.drawRect(skia.Rect.MakeXYWH(wx, wy, ws, ws * 1.2), paint(pc, win_a * rng.uniform(0.5, 1)))
        x += bw + rng.uniform(4, 30)
    return s.makeImageSnapshot()


def make_neon_layer(W, H, seed, horizon, count=10, gap=(0.36, 0.64)):
    """Generic unbranded neon shapes (no text). Returns list of shapes for per-frame drawing (flicker)."""
    rng = np.random.default_rng(seed)
    LW = W * 1.4; shapes = []
    for i in range(count):
        while True:
            x = rng.uniform(0, LW)
            if not (gap[0] < (x - LW * 0.2) / W < gap[1]): break
        y = rng.uniform(H * 0.18, H * horizon * 0.85)
        kind = rng.choice(["rect", "ring", "bar", "chevron"])
        colr = ["#ff2e88", "#2ee6ff", "#ffd23f", "#b46bff"][int(rng.integers(0, 4))]
        size = rng.uniform(40, 120)
        shapes.append((x, y, kind, colr, size, rng.uniform(0, 10)))
    return shapes


def draw_neon(canvas, shapes, t, ox=0.0, flicker=True, dim=1.0):
    for x, y, kind, c, s, ph in shapes:
        a = 1.0
        if flicker:
            f = hash01(int(t * 12), ph)
            a = 0.35 if f < 0.04 else (0.85 + 0.15 * math.sin(t * 7 + ph))
        a *= dim
        x = x + ox
        for width, alpha, blur in ((16, 0.35 * a, 14), (5, a, 0)):
            p = paint(c, alpha, stroke=width, blur=blur, blend="add" if blur else None)
            if kind == "rect":
                canvas.drawRoundRect(skia.Rect.MakeXYWH(x, y, s * 1.8, s * 0.7), 14, 14, p)
            elif kind == "ring":
                canvas.drawCircle(x, y, s * 0.45, p)
            elif kind == "bar":
                canvas.drawLine(x, y, x + s * 2.2, y, p)
            else:
                path = skia.Path(); path.moveTo(x, y); path.lineTo(x + s * 0.5, y + s * 0.4); path.lineTo(x, y + s * 0.8)
                canvas.drawPath(path, p)


@lru_cache(maxsize=8)
def fog_texture(W, H, seed=3, scale=6):
    rng = np.random.default_rng(seed)
    small = rng.random((H // (scale * 8) + 2, W // (scale * 8) + 2)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC)
    im = im.filter(ImageFilter.GaussianBlur(40))
    a = np.array(im).astype(np.float32) / 255.0
    a = np.clip((a - 0.35) * 1.8, 0, 1)
    rgba = np.zeros((H, W * 2, 4), np.uint8)
    rgba[..., :3] = 255; rgba[..., 3] = (a * 255).astype(np.uint8)
    return skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType)


_FOG = {}


def draw_fog(canvas, W, H, t, color="#9ad8ff", alpha=0.18, speed=30, y=0.0):
    """Drifting fog. Uses a pre-tinted half-resolution texture (plain src-over draw = fast path on CPU)."""
    key = (W, H, color)
    if key not in _FOG:
        base = fog_texture(W, H)
        hw, hh = W, H // 2                      # texture is 2W x H -> keep it at W x H/2 (half res)
        srf = new_surface(hw, hh); c = srf.getCanvas(); c.clear(skia.Color(0, 0, 0, 0))
        p = skia.Paint(AntiAlias=True)
        p.setColorFilter(skia.ColorFilters.Blend(col(color, 1.0), skia.BlendMode.kSrcIn))
        c.drawImageRect(base, skia.Rect.MakeWH(hw, hh), skia.SamplingOptions(skia.FilterMode.kLinear), p)
        _FOG[key] = srf.makeImageSnapshot()
    img = _FOG[key]
    p = skia.Paint(AntiAlias=True); p.setAlphaf(alpha)
    off = -(t * speed) % W
    canvas.drawImageRect(img, skia.Rect.MakeXYWH(off - W, y * H, 2 * W, H), skia.SamplingOptions(skia.FilterMode.kLinear), p)


def draw_road(canvas, W, H, horizon, t, lamps=("#ff2e88", "#2ee6ff", "#ffd23f"), speed=0.0, reflect=1.0):
    hy = H * horizon
    canvas.drawRect(skia.Rect.MakeLTRB(0, hy, W, H), paint(shader=lin(0, hy, 0, H, [(0, "#1a1430", 1), (1, "#040409", 1)])))
    # wet reflections: long vertical streaks of the neon colours (soft -> low-res layer)
    soft(canvas, W, H, lambda c: _reflections(c, W, H, hy, t, lamps, reflect), scale=0.25, blend="add")
    _lane_dashes(canvas, W, H, hy, t, speed)


def _reflections(canvas, W, H, hy, t, lamps, reflect):
    for i in range(26):
        x = (hash01(i, 1) * W * 1.2 - W * 0.1)
        c = lamps[i % len(lamps)]
        w = 10 + 40 * hash01(i, 2)
        a = 0.10 + 0.18 * hash01(i, 3)
        a *= 0.8 + 0.2 * math.sin(t * 3 + i)
        canvas.drawRect(skia.Rect.MakeLTRB(x - w / 2, hy, x + w / 2, H),
                        paint(shader=lin(0, hy, 0, H, [(0, c, a * reflect), (1, c, 0)]), blur=8))


def _lane_dashes(canvas, W, H, hy, t, speed):
    for i in range(10):
        z0 = ((i + speed * t) % 10) / 10; z1 = z0 + 0.045
        y0, y1 = hy + (H - hy) * z0 ** 2, hy + (H - hy) * z1 ** 2
        w0, w1 = 2 + 26 * z0 ** 2, 2 + 26 * z1 ** 2
        path = skia.Path(); path.moveTo(W / 2 - w0, y0); path.lineTo(W / 2 + w0, y0); path.lineTo(W / 2 + w1, y1); path.lineTo(W / 2 - w1, y1); path.close()
        canvas.drawPath(path, paint("#e9dcc0", 0.55))


# ---------------------------------------------------------------- rain / particles
class Rain:
    """Deterministic rain that can decelerate to a frozen state.
    speed(t) = 1 before freeze_at, then decays to 0 over `stop` seconds; positions integrate that speed."""

    def __init__(self, W, H, n=1400, seed=1, freeze_at=None, stop=0.35, wind=0.18, fall=1500, depth=(0.25, 1.0)):
        rng = np.random.default_rng(seed)
        self.W, self.H = W, H
        self.x = rng.uniform(-0.1 * W, 1.1 * W, n)
        self.y = rng.uniform(-0.2 * H, 1.2 * H, n)
        self.z = rng.uniform(depth[0], depth[1], n) ** 1.4
        self.ph = rng.uniform(0, 1, n)
        self.freeze_at, self.stop, self.wind, self.fall = freeze_at, stop, wind, fall

    def travelled(self, t):
        """Integral of the speed curve from 0..t (seconds of 'full-speed' fall)."""
        if self.freeze_at is None or t <= self.freeze_at:
            return t
        k = 3.0 / self.stop
        return self.freeze_at + (1 - math.exp(-k * (t - self.freeze_at))) / k

    def speed(self, t):
        if self.freeze_at is None or t <= self.freeze_at:
            return 1.0
        return math.exp(-3.0 / self.stop * (t - self.freeze_at))

    def draw(self, canvas, t, cam=(0.0, 0.0), color="#cfe6ff", bead_color="#bff3ff", glow=True, layer=None, offset=0.0):
        d = self.travelled(t + offset); v = self.speed(t + offset)
        H, W = self.H, self.W
        span = H * 1.4
        ys = (self.y + self.fall * self.z * d) % span - 0.2 * H
        xs = self.x + self.wind * self.fall * self.z * d * 0.25
        xs = (xs + 0.1 * W) % (1.2 * W) - 0.1 * W
        xs = xs + cam[0] * self.z; ys = ys + cam[1] * self.z
        sel = np.ones(len(xs), bool) if layer is None else ((self.z >= layer[0]) & (self.z < layer[1]))
        streak = paint(color, 0.5, stroke=1)
        bead = paint(bead_color, 0.9)
        hl = paint("#ffffff", 0.95)
        glowp = paint("#2ee6ff", 0.35, blur=7, blend="add")
        for i in np.nonzero(sel)[0]:
            x, y, z = xs[i], ys[i], self.z[i]
            if v > 0.08:
                ln = (28 + 90 * z) * v
                streak.setStrokeWidth(0.8 + 2.4 * z); streak.setAlphaf(min(1, (0.15 + 0.55 * z) * (0.4 + 0.6 * v)))
                canvas.drawLine(x, y, x - self.wind * ln, y - ln, streak)
            if v < 0.6:
                k = 1 - v / 0.6
                r = (1.2 + 6.5 * z * z) * k
                if r < 0.4: continue
                bead.setAlphaf(min(1, (0.35 + 0.6 * z) * k))
                oval = skia.Rect.MakeLTRB(x - r * 0.72, y - r * 1.05, x + r * 0.72, y + r * 1.05)
                if glow and z > 0.7:
                    glowp.setAlphaf(0.35 * k); canvas.drawCircle(x, y, r * 2.2, glowp)
                canvas.drawOval(oval, bead)
                canvas.drawCircle(x - r * 0.25, y - r * 0.45, r * 0.28, hl)


# ---------------------------------------------------------------- the hero (yellow raincoat, seen from behind)
def hero(canvas, x, feet_y, h, t=0.0, pose="stand", phase=0.0, rim="#2ee6ff", rim_side=-1, sway=1.0,
         coat="#ffd23f", coat_dark="#c98a00", arms_up=0.0, lean=0.0):
    """Draw the consistent HERO. h = full height in px. pose: stand | walk. arms_up 0..1. lean in radians."""
    s = h / 600.0
    canvas.save()
    canvas.translate(x, feet_y)
    canvas.rotate(math.degrees(lean))
    canvas.scale(s, s)
    breath = math.sin(t * 2.4) * 3 * sway
    hem = math.sin(t * 3.1) * 6 * sway

    # contact shadow
    canvas.drawOval(skia.Rect.MakeLTRB(-130, -16, 130, 16), paint("#000000", 0.55, blur=10))

    # legs (boots), walk cycle via phase
    def leg(side, swing):
        p = skia.Path()
        hipx = side * 26
        kx = hipx + swing * 40; fy = 0 if swing <= 0 else -abs(swing) * 30
        p.moveTo(hipx - 22, -230); p.lineTo(hipx + 22, -230)
        p.lineTo(kx + 20, -20 + fy); p.lineTo(kx + 30, fy); p.lineTo(kx - 30, fy); p.lineTo(kx - 20, -20 + fy); p.close()
        canvas.drawPath(p, paint(shader=lin(0, -230, 0, 0, [(0, "#1a1a26", 1), (1, "#07070b", 1)])))
        canvas.drawLine(kx - 24, -6 + fy, kx + 26, -6 + fy, paint(rim, 0.35, stroke=3))
    sw = math.sin(phase) if pose == "walk" else 0.0
    leg(-1, sw); leg(1, -sw)

    # arms (behind the body when down)
    def arm(side, up):
        sx, sy = side * 62, -470 + breath
        ang_down, ang_up = math.radians(100 + side * -12), math.radians(-60 if side > 0 else -120)
        a = lerp(ang_down if side > 0 else math.pi - ang_down, ang_up, ease(up))
        L = 190
        ex, ey = sx + math.cos(a) * L, sy + math.sin(a) * L
        p = paint(coat, 1, stroke=58)
        p.setShader(lin(sx, sy, ex, ey, [(0, coat, 1), (1, coat_dark, 1)]))
        canvas.drawLine(sx, sy, ex, ey, p)
        canvas.drawCircle(ex, ey, 24, paint("#e7c08a"))  # glove/hand
        return ex, ey
    hands = [arm(-1, arms_up), arm(1, arms_up)]

    # coat body: bezier silhouette with swinging hem
    body = skia.Path()
    body.moveTo(-58, -520 + breath)
    body.cubicTo(-95, -470, -105, -380, -112, -300)
    body.cubicTo(-118, -250, -126 + hem * 0.5, -215, -132 + hem, -190)
    body.cubicTo(-60, -176 + hem * 0.6, 60, -176 - hem * 0.6, 132 - hem, -190)
    body.cubicTo(126 - hem * 0.5, -215, 118, -250, 112, -300)
    body.cubicTo(105, -380, 95, -470, 58, -520 + breath)
    body.close()
    canvas.drawPath(body, paint(shader=lin(-130, 0, 130, 0, [(0, coat, 1), (0.55, coat, 1), (1, coat_dark, 1)])))
    # vertical shading + wet sheen
    canvas.save(); canvas.clipPath(body, skia.ClipOp.kIntersect, True)
    canvas.drawRect(skia.Rect.MakeLTRB(-140, -540, 140, -170), paint(shader=lin(0, -540, 0, -170, [(0, "#ffffff", 0.10), (0.5, "#000000", 0), (1, "#5a3000", 0.35)])))
    for i, xx in enumerate((-70, -20, 45)):
        canvas.drawLine(xx, -500, xx + 8 + hem * 0.3, -200, paint("#ffffff", 0.10 + 0.05 * i, stroke=6, blur=3))
    canvas.drawLine(0, -505 + breath, 0, -185, paint("#8a5a00", 0.6, stroke=4))  # back seam
    canvas.drawLine(-110, -300, 110, -300, paint("#8a5a00", 0.35, stroke=5))       # belt line
    canvas.restore()

    # hood
    hood = skia.Path()
    hood.moveTo(-70, -505 + breath)
    hood.cubicTo(-92, -560, -80, -640, 0, -652 + breath)
    hood.cubicTo(80, -640, 92, -560, 70, -505 + breath)
    hood.cubicTo(30, -488, -30, -488, -70, -505 + breath)
    hood.close()
    canvas.drawPath(hood, paint(shader=rad(-25, -610, 120, [(0, "#ffe27a", 1), (0.7, coat, 1), (1, coat_dark, 1)])))
    canvas.drawPath(hood, paint("#8a5a00", 0.4, stroke=3))

    # rim light on one side (clip to a half-plane, blurred stroke of the outline)
    outline = skia.Path(body); outline.addPath(hood)
    canvas.save()
    canvas.clipRect(skia.Rect.MakeLTRB(-400, -800, 0, 50) if rim_side < 0 else skia.Rect.MakeLTRB(0, -800, 400, 50))
    canvas.drawPath(outline, paint(rim, 0.9, stroke=7, blur=2))
    canvas.drawPath(outline, paint(rim, 0.5, stroke=24, blur=14, blend="add"))
    canvas.restore()
    canvas.restore()
    # return hand positions in canvas space
    return [(x + (hx * math.cos(lean) - hy * math.sin(lean)) * s, feet_y + (hx * math.sin(lean) + hy * math.cos(lean)) * s) for hx, hy in hands]


# ---------------------------------------------------------------- nature / macro
def bokeh(canvas, W, H, t, seed=1, n=28, colors=("#ffcf6b", "#bff58a", "#ffffff"), drift=12, alpha=0.22, size=(30, 120)):
    """Out-of-focus light discs (shallow depth of field background). Drawn in a low-res layer."""
    soft(canvas, W, H, lambda c: _bokeh(c, W, H, t, seed, n, colors, drift, alpha, size), scale=0.25, blend="screen")


def _bokeh(canvas, W, H, t, seed, n, colors, drift, alpha, size):
    for i in range(n):
        x = hash01(seed, i, 1) * W + math.sin(t * 0.6 + i) * drift
        y = hash01(seed, i, 2) * H + math.cos(t * 0.5 + i) * drift
        r = size[0] + (size[1] - size[0]) * hash01(seed, i, 3)
        c = colors[i % len(colors)]
        a = alpha * (0.5 + 0.5 * hash01(seed, i, 4))
        canvas.drawCircle(x, y, r, paint(shader=rad(x, y, r, [(0, c, a), (0.8, c, a * 0.8), (1, c, 0)]), blend="screen"))


def light_rays(canvas, W, H, t, origin=(0.8, -0.1), n=7, color="#ffe3a0", alpha=0.10, spread=0.5):
    """Volumetric god rays. Drawn in a quarter-resolution layer (the blur hides it; ~15x faster)."""
    soft(canvas, W, H, lambda c: _rays(c, W, H, t, origin, n, color, alpha, spread), scale=0.25, blend="screen")


def _rays(canvas, W, H, t, origin, n, color, alpha, spread):
    ox, oy = origin[0] * W, origin[1] * H
    for i in range(n):
        ang = math.radians(100 + (i - n / 2) * spread * 12 + 3 * math.sin(t * 0.4 + i))
        L = math.hypot(W, H) * 1.3; w = 60 + 90 * hash01(i, 9)
        a = alpha * (0.6 + 0.4 * math.sin(t * 0.7 + i * 1.7))
        p = skia.Path(); p.moveTo(ox, oy)
        ex, ey = ox + math.cos(ang) * L, oy + math.sin(ang) * L
        nx, ny = -math.sin(ang) * w, math.cos(ang) * w
        p.lineTo(ex + nx, ey + ny); p.lineTo(ex - nx, ey - ny); p.close()
        canvas.drawPath(p, paint(shader=lin(ox, oy, ex, ey, [(0, color, a), (1, color, 0)]), blur=18, blend="screen"))


def motes(canvas, W, H, t, seed=2, n=80, color="#fff2c4", speed=1.0, frozen=False):
    """Floating dust / pollen with soft glow."""
    tt = 0 if frozen else t
    for i in range(n):
        z = 0.3 + 0.7 * hash01(seed, i, 3)
        x = (hash01(seed, i, 1) * W + tt * 18 * z * speed + 30 * math.sin(tt * 0.8 + i)) % W
        y = (hash01(seed, i, 2) * H - tt * 10 * z * speed + 20 * math.cos(tt * 0.6 + i)) % H
        r = 1.2 + 3.5 * z
        canvas.drawCircle(x, y, r * 3, paint(color, 0.10 * z, blur=r * 2, blend="add"))
        canvas.drawCircle(x, y, r, paint(color, 0.6 * z))


def grass_blade(canvas, x, base_y, height, width, t, bend=0.25, sway=1.0, seed=0, dark="#0f3d2a", light="#5fbf5a", rim="#ffe3a0"):
    """One curved grass blade, swaying. Tapers to a point."""
    s = math.sin(t * 1.3 + seed * 1.7) * 0.06 * sway
    b = bend + s
    tipx, tipy = x + height * b, base_y - height
    c1x, c1y = x + height * b * 0.15, base_y - height * 0.55
    path = skia.Path()
    path.moveTo(x - width / 2, base_y)
    path.cubicTo(c1x - width * 0.45, c1y, tipx - width * 0.15, tipy + height * 0.25, tipx, tipy)
    path.cubicTo(tipx + width * 0.05, tipy + height * 0.25, c1x + width * 0.45, c1y, x + width / 2, base_y)
    path.close()
    canvas.drawPath(path, paint(shader=lin(x - width, 0, x + width, 0, [(0, dark, 1), (0.55, light, 1), (1, dark, 1)])))
    canvas.drawPath(path, paint(shader=lin(0, base_y, 0, tipy, [(0, "#000000", 0.45), (1, "#000000", 0)])))
    # midrib + backlit rim
    rib = skia.Path(); rib.moveTo(x, base_y); rib.quadTo(c1x, c1y, tipx, tipy)
    canvas.drawPath(rib, paint(light, 0.35, stroke=max(1, width * 0.06)))
    canvas.drawPath(path, paint(rim, 0.35, stroke=max(1.5, width * 0.05), blur=2))


def water_drop(canvas, cx, cy, r, t=0.0, wobble=0.0, squash=0.0, alpha=1.0, tint="#7fe3ff"):
    """Refractive-looking water drop: dark rim, bright caustic, specular highlight. squash>0 flattens (sitting)."""
    k = 1 + 0.06 * wobble * math.sin(t * 18)
    rx, ry = r * k * (1 + squash * 0.35), r / k * (1 - squash * 0.35)
    oval = skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry)
    canvas.drawOval(oval, paint(shader=rad(cx, cy + ry * 0.2, max(rx, ry), [(0, tint, 0.10 * alpha), (0.75, tint, 0.28 * alpha), (1, "#0a3a4a", 0.75 * alpha)])))
    canvas.drawOval(skia.Rect.MakeLTRB(cx - rx * 0.55, cy + ry * 0.15, cx + rx * 0.55, cy + ry * 0.8),
                    paint(shader=rad(cx, cy + ry * 0.5, rx * 0.6, [(0, "#eaffff", 0.30 * alpha), (1, "#eaffff", 0)]), blend="screen"))
    canvas.drawOval(oval, paint("#d9fbff", 0.55 * alpha, stroke=max(1.5, r * 0.025)))
    canvas.drawOval(skia.Rect.MakeLTRB(cx - rx * 0.55, cy - ry * 0.72, cx - rx * 0.15, cy - ry * 0.42), paint("#ffffff", 0.85 * alpha, blur=r * 0.03))


def ant(canvas, x, y, size, t, walk=1.0, facing=1, color="#1a0f0a"):
    """Stylised generic ant (side view) with a walking leg cycle."""
    canvas.save(); canvas.translate(x, y); canvas.scale(facing * size / 100, size / 100)
    body = paint(shader=lin(0, -40, 0, 10, [(0, "#5a3020", 1), (1, color, 1)]))
    for i, side in enumerate((-1, 1, -1)):
        for j, lx in enumerate((-25, 5, 35)):
            ph = t * 10 * walk + j * 2.1 + (math.pi if side > 0 else 0)
            kx, ky = lx + 18 * math.sin(ph), -2
            fx, fy = lx + 30 * math.sin(ph) + 12, 22 - 6 * max(0, math.cos(ph))
            canvas.drawLine(lx, -12, kx, ky - 14, paint(color, 0.9, stroke=3.2))
            canvas.drawLine(kx, ky - 14, fx, fy, paint(color, 0.9, stroke=2.6))
    canvas.drawOval(skia.Rect.MakeLTRB(-95, -38, -30, 4), body)     # abdomen
    canvas.drawOval(skia.Rect.MakeLTRB(-34, -28, 30, -6), body)     # thorax
    canvas.drawOval(skia.Rect.MakeLTRB(26, -40, 66, -8), body)      # head
    for a in (-1, 1):
        canvas.drawLine(58, -34, 80, -58 + a * 6 + 4 * math.sin(t * 6 + a), paint(color, 0.9, stroke=2.4))
    canvas.drawOval(skia.Rect.MakeLTRB(-80, -34, -50, -24), paint("#ffffff", 0.25, blur=2))
    canvas.restore()


# ---------------------------------------------------------------- 3D character sprites (hero3d/build_character.py)
SPRITE_ROOT = None          # folder holding <char>/<anim>_<view>_<light>/ (or legacy <anim>_<view>_<light>/)
_SPRITES = {}
HERO_HEIGHT_M = 1.84        # legacy sets without height_m in meta.json
ORTHO_SCALE = 2.6
SPRITE_BLEND = True         # interpolate between sprite frames when the video fps is higher than the sprite fps


def _sprite_set(name):
    import json as _json
    from pathlib import Path as _P
    if name not in _SPRITES:
        folder = _P(SPRITE_ROOT or "") / name
        if not (folder / "meta.json").exists():
            _SPRITES[name] = None
        else:
            meta = _json.loads((folder / "meta.json").read_text())
            frames = sorted(folder.glob("[0-9]*.png"))
            _SPRITES[name] = {"meta": meta, "paths": frames, "imgs": {}}
    return _SPRITES[name]


def has_sprite(name):
    return _sprite_set(name) is not None


def _sprite_img(S, i):
    if i not in S["imgs"]:
        if len(S["imgs"]) > 96:
            S["imgs"].pop(next(iter(S["imgs"])))
        img = skia.Image.open(str(S["paths"][i]))
        S["imgs"][i] = img.withDefaultMipmaps() if hasattr(img, "withDefaultMipmaps") else img
    return S["imgs"][i]


def character(canvas, x, feet_y, h, name, t, start=0.0, speed=1.0, hold_last=None, flip=False, lean=0.0, alpha=1.0,
              frame=None):
    """Draw a pre-rendered 3D character frame. name = '<char>/<anim>_<view>_<light>'. h = character height in px
    (feet to top of head/hood/hat); (x, feet_y) = ground point. Loops or holds per meta (override with hold_last);
    frame = fixed (float ok) frame index. Neighbouring frames are blended so 12-24 fps sprites play smoothly at 30 fps.
    Returns the hand positions in canvas space."""
    S = _sprite_set(name)
    if S is None:
        raise FileNotFoundError(f"sprite set '{name}' not found under {SPRITE_ROOT} — run hero3d/make_character.py")
    m = S["meta"]; n = len(S["paths"])
    loop = m["loop"] if hold_last is None else not hold_last
    pos = float(frame) if frame is not None else max(0.0, t - start) * m["fps"] * speed
    if loop:
        pos %= n
    else:
        pos = min(pos, n - 1)
    i0 = int(pos); frac = pos - i0 if SPRITE_BLEND else 0.0
    i1 = (i0 + 1) % n if loop else min(i0 + 1, n - 1)
    if i1 == i0:
        frac = 0.0
    sw, sh_ = m["size"]
    ppm = sh_ / m.get("ortho", ORTHO_SCALE)
    sc = h / (m.get("height_m", HERO_HEIGHT_M) * ppm)
    F = m["feet"]
    fx = (F[min(i0, len(F) - 1)][0] * (1 - frac) + F[min(i1, len(F) - 1)][0] * frac) * sw
    fy = (F[min(i0, len(F) - 1)][1] * (1 - frac) + F[min(i1, len(F) - 1)][1] * frac) * sh_
    samp = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)
    canvas.save()
    canvas.translate(x, feet_y)
    if lean:
        canvas.rotate(math.degrees(lean))
    canvas.scale(-sc if flip else sc, sc)
    if frac < 0.02 or frac > 0.98:
        p = skia.Paint(AntiAlias=True); p.setAlphaf(alpha)
        canvas.drawImage(_sprite_img(S, i1 if frac > 0.98 else i0), -fx, -fy, samp, p)
    else:   # premultiplied lerp of the two frames == what a camera shutter would record between them
        canvas.saveLayerAlpha(None, int(255 * alpha))
        p0 = skia.Paint(AntiAlias=True); p0.setAlphaf(1 - frac)
        canvas.drawImage(_sprite_img(S, i0), -fx, -fy, samp, p0)
        p1 = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kPlus); p1.setAlphaf(frac)
        canvas.drawImage(_sprite_img(S, i1), -fx, -fy, samp, p1)
        canvas.restore()
    canvas.restore()
    out = []
    H0 = m.get("hands") or []
    if H0:
        h0 = H0[min(i0, len(H0) - 1)]; h1 = H0[min(i1, len(H0) - 1)]
        for (ax, ay), (bx, by) in zip(h0, h1):
            hx, hy = ax * (1 - frac) + bx * frac, ay * (1 - frac) + by * frac
            lx, ly = (hx * sw - fx) * sc * (-1 if flip else 1), (hy * sh_ - fy) * sc
            ca, sa = math.cos(lean), math.sin(lean)
            out.append((x + lx * ca - ly * sa, feet_y + lx * sa + ly * ca))
    return out


hero_sprite = character   # backwards-compatible name


# ---------------------------------------------------------------- effects
def ripple(canvas, cx, cy, t, rings=5, speed=520, life=1.3, color="#d8f6ff", squash=0.8, width=10):
    for i in range(rings):
        tt = t - i * 0.08
        if tt <= 0 or tt > life: continue
        r = speed * tt * (1 - 0.35 * tt / life)
        a = (1 - tt / life) ** 1.5
        rect = skia.Rect.MakeLTRB(cx - r, cy - r * squash, cx + r, cy + r * squash)
        canvas.drawOval(rect, paint(color, a * 0.9, stroke=max(1.5, width * (1 - tt / life))))
        canvas.drawOval(rect, paint("#2ee6ff", a * 0.4, stroke=width * 3, blur=10, blend="add"))


def flare(canvas, x, y, r, a=1.0, color="#ffffff", tint="#9ff0ff"):
    canvas.drawCircle(x, y, r * 4, paint(shader=rad(x, y, r * 4, [(0, tint, 0.55 * a), (1, tint, 0)]), blend="add"))
    canvas.drawCircle(x, y, r, paint(color, a, blur=r * 0.4, blend="add"))
    canvas.drawLine(x - r * 7, y, x + r * 7, y, paint(tint, 0.35 * a, stroke=3, blur=3, blend="add"))


_VIG = {}


def vignette(canvas, W, H, strength=0.75, color="#000000"):
    """Edge darkening; rendered once at 1/4 size per (size, strength) and reused (smooth gradient upsamples cleanly)."""
    key = (W, H, round(strength, 3), color, _GR is not None)
    if key not in _VIG:
        lw, lh = W // 4, H // 4
        s = new_surface(lw, lh); c = s.getCanvas(); c.clear(skia.Color(0, 0, 0, 0)); c.scale(lw / W, lh / H)
        c.drawRect(skia.Rect.MakeWH(W, H), paint(shader=rad(W / 2, H / 2, math.hypot(W, H) / 2,
                                                         [(0, color, 0), (0.55, color, 0), (1, color, strength)])))
        _VIG[key] = s.makeImageSnapshot()
    canvas.drawImageRect(_VIG[key], skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear))


# ---------------------------------------------------------------- post (numpy) — used by render.py
try:
    import cv2
    cv2.setNumThreads(1)   # we parallelise across processes already
except ImportError:
    cv2 = None


def bloom(img, threshold=170, strength=0.7, radius=18):
    if cv2 is not None:
        base = np.asarray(img.convert("RGB"))
        h, w = base.shape[:2]
        small = cv2.resize(base, (w // 4, h // 4), interpolation=cv2.INTER_AREA).astype(np.float32)
        lum = small[..., 0:1] * 0.2126 + small[..., 1:2] * 0.7152 + small[..., 2:3] * 0.0722
        bright = small * np.clip((lum - threshold) / (255 - threshold), 0, 1)
        k = max(3, int(radius / 4) * 2 + 1)
        bright = cv2.GaussianBlur(bright, (k, k), radius / 8)
        up = cv2.resize(bright, (w, h), interpolation=cv2.INTER_LINEAR)
        out = cv2.addWeighted(base.astype(np.float32), 1.0, up, strength, 0)
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
    small = img.convert("RGB").resize((img.width // 4, img.height // 4), Image.BILINEAR)
    arr = np.asarray(small).astype(np.float32)
    # perceptual luminance, so saturated mid-tones (a yellow coat) don't bloom — only real highlights do
    lum = (arr[..., :1] * 0.2126 + arr[..., 1:2] * 0.7152 + arr[..., 2:3] * 0.0722)
    bright = np.clip(arr * np.clip((lum - threshold) / (255 - threshold), 0, 1), 0, 255).astype(np.uint8)
    b = Image.fromarray(bright).filter(ImageFilter.GaussianBlur(radius / 4)).resize(img.size, Image.BILINEAR)
    base = np.asarray(img.convert("RGB")).astype(np.int16)
    out = np.clip(base + np.asarray(b).astype(np.int16) * strength, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


_grain_cache = {}


def grain(img, amount=0.035, frame=0):
    if cv2 is not None:
        key = ("cv", img.size, frame % 6)
        if key not in _grain_cache:
            rng = np.random.default_rng(frame % 6)
            n = rng.standard_normal((img.height, img.width, 1)) * 255 * amount
            n = np.repeat(n, 3, axis=2)
            _grain_cache[key] = (np.clip(n, 0, 255).astype(np.uint8), np.clip(-n, 0, 255).astype(np.uint8))
        pos, neg = _grain_cache[key]
        a = np.asarray(img.convert("RGB"))
        return Image.fromarray(cv2.subtract(cv2.add(a, pos), neg), "RGB")
    key = (img.size, frame % 6)
    if key not in _grain_cache:
        rng = np.random.default_rng(frame % 6)
        _grain_cache[key] = (rng.standard_normal((img.height, img.width, 1)) * 255 * amount).astype(np.int16)
    arr = np.asarray(img.convert("RGB")).astype(np.int16) + _grain_cache[key]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def chroma(img, px=2):
    if px <= 0: return img
    r, g, b = img.convert("RGB").split()
    r = r.transform(img.size, Image.AFFINE, (1, 0, -px, 0, 1, 0))
    b = b.transform(img.size, Image.AFFINE, (1, 0, px, 0, 1, 0))
    return Image.merge("RGB", (r, g, b))
