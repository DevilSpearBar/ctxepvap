"""Painted landscape: rolling hills, grass fields, the big tree, foreground grass."""

import numpy as np
import skia
from scipy.interpolate import CubicSpline

from .core import (fbm, lerp, paint_fill, rgb_layer, rgbf, smoothstep, surface, to_array,
                   value_noise)
from .sky import Puff, Sprite, _boundary_points, fit_puffs, render_puffs

LEAF_DAY = dict(lit=rgbf('b1d45a'), mid=rgbf('72a73d'), shadow=rgbf('3d7236'),
                deep=rgbf('244e2d'), rim=rgbf('d8ec8a'), light=(-0.55, -0.72, 0.42))
LEAF_SUNSET = dict(lit=rgbf('b07a3e'), mid=rgbf('4a3d36'), shadow=rgbf('2f2930'),
                   deep=rgbf('231e27'), rim=rgbf('ffb764'), light=(0.95, 0.05, 0.12))

GDAY = dict(
    far_mtn=rgbf('8fb0c9'), far_mtn_dark=rgbf('7695b5'),
    far_hill=rgbf('7aa585'), far_hill_dark=rgbf('5f8f73'),
    hill_lit=rgbf('9cc95a'), hill_mid=rgbf('6fa441'), hill_shadow=rgbf('477f39'), hill_dark=rgbf('2f6232'),
    grass_lit=rgbf('bfe06c'), grass_mid=rgbf('84bb47'), grass_shadow=rgbf('4f8e39'), grass_dark=rgbf('2f6831'),
    blade=[rgbf('3f7d34'), rgbf('4f9139'), rgbf('639f40'), rgbf('7fb84a'), rgbf('2f6a2e')],
    flower=[rgbf('fffaf0'), rgbf('fff2a8'), rgbf('f7d2e6')],
    bark_lit=rgbf('8e6c50'), bark_mid=rgbf('6a4f3c'), bark_shadow=rgbf('45342b'),
    leaf=LEAF_DAY,
    haze=rgbf('d3e9f2'),
)

GSUNSET = dict(
    far_mtn=rgbf('a17a9c'), far_mtn_dark=rgbf('86668f'),
    far_hill=rgbf('6e5872'), far_hill_dark=rgbf('5a4866'),
    hill_lit=rgbf('9a7448'), hill_mid=rgbf('5d4a3f'), hill_shadow=rgbf('3e3338'), hill_dark=rgbf('2c2530'),
    grass_lit=rgbf('c99549'), grass_mid=rgbf('6a5540'), grass_shadow=rgbf('3d3237'), grass_dark=rgbf('29222b'),
    blade=[rgbf('2c2430'), rgbf('362b33'), rgbf('453636'), rgbf('5a4538'), rgbf('241e29')],
    flower=[rgbf('ffd9a0'), rgbf('ffc890'), rgbf('f2b0a0')],
    bark_lit=rgbf('4a3631'), bark_mid=rgbf('33282a'), bark_shadow=rgbf('241d24'),
    leaf=LEAF_SUNSET,
    haze=rgbf('ffc58a'),
)


# ---------------------------------------------------------------- 1-D noise

def noise1d(n, cell, rng):
    k = int(n / cell) + 5
    knots = rng.uniform(-1, 1, k)
    xs = (np.arange(k) - 2) * cell
    return CubicSpline(xs, knots)(np.arange(n)).astype(np.float32)


def fbm1d(n, cell, rng, octaves=4, gain=0.5):
    out = np.zeros(n, np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        out += amp * noise1d(n, cell, rng)
        tot += amp
        amp *= gain
        cell /= 2.0
    return out / tot


def ridge(w, seed, base, amp, cell=500, octaves=4):
    rng = np.random.default_rng(seed)
    return base + amp * fbm1d(w, cell, rng, octaves)


# ---------------------------------------------------------------- ground

def paint_ground(w, h, top_y, cols, seed, *, strokes=0, stroke_len=(8, 16), stroke_w=(1.4, 2.6),
                 lean=6.0, flowers=0, haze=0.0, haze_col=None, patch=0.10, rim=0.35,
                 grad_depth=160.0, persp=None, fold=0.0):
    """Paint a grassy region below the ridge line top_y (array of length w).

    cols = (lit, mid, shadow, dark). persp: (y_far, y_near) scales strokes with depth.
    Returns premultiplied RGBA float32.
    """
    rng = np.random.default_rng(seed)
    lit, mid, shadow, dark = cols
    yy = np.arange(h, dtype=np.float32)[:, None]
    depth = yy - top_y[None, :]
    alpha = np.clip(depth + 0.5, 0, 1)
    # slope facing the light (upper-left): ridge rising to the right faces left
    slope = np.gradient(top_y)
    face = np.clip(-slope * 1.2, -1, 1)[None, :]
    g = np.clip(depth / grad_depth, 0, 1)
    shade = 0.62 - 0.35 * g + 0.25 * face
    shade = shade + patch * fbm(h, w, 140, rng, octaves=3) + 0.05 * fbm(h, w, 30, rng, octaves=2)
    if fold:
        shade -= fold * smoothstep(0.2, 0.9, fbm(h, w, 260, rng, octaves=2))
    t = np.clip(shade, 0, 1)[..., None]
    c1 = lerp(dark, shadow, np.clip(t / 0.33, 0, 1))
    c2 = lerp(shadow, mid, np.clip((t - 0.33) / 0.33, 0, 1))
    c3 = lerp(mid, lit, np.clip((t - 0.66) / 0.34, 0, 1))
    col = np.where(t < 0.33, c1, np.where(t < 0.66, c2, c3))
    # sunlit rim along the crest
    crest = np.exp(-np.maximum(depth, 0) / 5.0)[..., None]
    col = col + (lit - col) * (rim * crest)
    if haze:
        hc = haze_col if haze_col is not None else lit
        col = lerp(col, hc, haze)
    layer = rgb_layer(np.clip(col, 0, 1), alpha)
    if strokes or flowers:
        layer = _add_strokes(layer, top_y, cols, rng, strokes, stroke_len, stroke_w, lean,
                             flowers, haze, haze_col, persp)
    return layer


def _add_strokes(layer, top_y, cols, rng, n, slen, swid, lean, flowers, haze, haze_col, persp):
    h, w = layer.shape[:2]
    lit, mid, shadow, dark = cols
    s = surface(w, h)
    c = s.getCanvas()
    from .core import to_image
    c.drawImage(to_image(layer), 0, 0)
    xs = rng.uniform(0, w, n)
    ty = top_y[np.clip(xs.astype(int), 0, w - 1)]
    ys = ty + rng.uniform(0, 1, n) ** 1.3 * (h - ty)
    order = np.argsort(ys)
    paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                       StrokeCap=skia.Paint.kRound_Cap)
    base = layer[..., :3] / np.maximum(layer[..., 3:4], 1e-4)
    for i in order:
        x, y = xs[i], ys[i]
        k = 1.0
        if persp is not None:
            k = lerp(0.5, 1.6, np.clip((y - persp[0]) / (persp[1] - persp[0]), 0, 1))
        L = rng.uniform(*slen) * k
        bw = rng.uniform(*swid) * k
        bc = base[min(h - 1, int(y)), min(w - 1, int(x))]
        r = rng.random()
        if r < 0.45:
            cc = bc * rng.uniform(1.08, 1.22)
        elif r < 0.8:
            cc = bc * rng.uniform(0.78, 0.92)
        else:
            cc = lerp(bc, lit if rng.random() < 0.6 else dark, 0.35)
        if haze:
            cc = lerp(cc, haze_col, haze * 0.5)
        cc = np.clip(cc, 0, 1)
        paint.setColor4f(skia.Color4f(float(cc[0]), float(cc[1]), float(cc[2]), 0.85))
        paint.setStrokeWidth(float(bw))
        dx = (lean + rng.normal(0, 4)) * L / 14.0
        p = skia.Path()
        p.moveTo(x, y)
        p.quadTo(x + dx * 0.2, y - L * 0.6, x + dx, y - L)
        c.drawPath(p, paint)
    if flowers:
        fp = paint_fill((1, 1, 1, 1))
        fx = rng.uniform(0, w, flowers)
        fty = top_y[np.clip(fx.astype(int), 0, w - 1)]
        fy = fty + 6 + rng.uniform(0, 1, flowers) ** 1.5 * (h - fty - 6)
        for x, y in zip(fx, fy):
            k = 1.0 if persp is None else lerp(0.5, 1.6, np.clip((y - persp[0]) / (persp[1] - persp[0]), 0, 1))
            fc = [rgbf('fffaf0'), rgbf('fff1a0'), rgbf('f8d4e4')][rng.integers(3)]
            if haze:
                fc = lerp(fc, haze_col, haze * 0.5)
            fp.setColor4f(skia.Color4f(float(fc[0]), float(fc[1]), float(fc[2]), 0.9))
            c.drawCircle(float(x), float(y), float(rng.uniform(1.0, 2.0) * k), fp)
    out = to_array(s)
    return out


# ---------------------------------------------------------------- foreground grass

class Blades:
    """Foreground grass blades drawn as vector shapes every frame (they sway)."""

    def __init__(self, seed, n, x0, x1, y_fn, h_range, w_range, colors, depth_dark=0.0):
        rng = np.random.default_rng(seed)
        self.x = rng.uniform(x0, x1, n)
        self.y = np.array([y_fn(x) for x in self.x]) + rng.uniform(0, 1, n) * 0
        self.h = rng.uniform(*h_range, n)
        self.w = rng.uniform(*w_range, n)
        self.lean = rng.normal(0, 0.18, n)
        self.ph = rng.uniform(0, 2 * np.pi, n)
        self.col = [colors[i] for i in rng.integers(len(colors), size=n)]
        self.col = [c * rng.uniform(0.9, 1.08) for c in self.col]
        order = np.argsort(self.y + rng.uniform(0, 1, n))
        for k in ('x', 'y', 'h', 'w', 'lean', 'ph'):
            setattr(self, k, getattr(self, k)[order])
        self.col = [self.col[i] for i in order]

    def draw(self, canvas, t, wind=0.4, wind_dir=1, scroll=0.0, wrap=None, gust=0.0, wave_k=0.004,
             wave_speed=2.2, tint=None, alpha=1.0, xmin=-200, xmax=2120):
        paint = skia.Paint(AntiAlias=True)
        for i in range(len(self.x)):
            x = self.x[i] - scroll
            if wrap:
                x = (x - xmin) % wrap + xmin
            if x < xmin or x > xmax:
                continue
            y = self.y[i]
            h = self.h[i]
            sway = (wind * (0.55 + 0.45 * np.sin(wave_k * x * 6.0 - wave_speed * t * 2 + self.ph[i]))
                    + gust * (0.7 + 0.3 * np.sin(13 * t + self.ph[i])))
            bend = (self.lean[i] + wind_dir * sway * 0.75) * h
            bend = np.clip(bend, -0.95 * h, 0.95 * h)
            tipx = x + bend
            tipy = y - np.sqrt(max(h * h - bend * bend * 0.6, (0.25 * h) ** 2))
            cx = x + bend * 0.15
            cy = y - (y - tipy) * 0.65
            bw = self.w[i]
            p = skia.Path()
            p.moveTo(x - bw * 0.5, y)
            p.quadTo(cx - bw * 0.35, cy, tipx, tipy)
            p.quadTo(cx + bw * 0.35, cy, x + bw * 0.5, y)
            p.close()
            cc = self.col[i] if tint is None else self.col[i] * tint
            paint.setColor4f(skia.Color4f(float(cc[0]), float(cc[1]), float(cc[2]), alpha))
            canvas.drawPath(p, paint)


# ---------------------------------------------------------------- the big tree

def _limb(path_pts, w0, w1):
    """Tapered limb polygon along a centre-line (list of points)."""
    pts = np.array(path_pts, np.float32)
    n = len(pts)
    left, right = [], []
    for i in range(n):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        d = b - a
        d /= np.linalg.norm(d) + 1e-6
        nrm = np.array([-d[1], d[0]])
        wdt = lerp(w0, w1, i / (n - 1)) * 0.5
        left.append(pts[i] + nrm * wdt)
        right.append(pts[i] - nrm * wdt)
    from .core import smooth_path
    return smooth_path(left + right[::-1], closed=True, tension=0.5)


def make_tree(seed=7, pal=GDAY, scale=1.0, silhouette=False):
    """A big, wide camphor-like tree. Returns Sprite with anchor at the trunk base."""
    rng = np.random.default_rng(seed)
    S = scale
    W_, H_ = int(1560 * S), int(1110 * S)
    bx, by = 780 * S, 1070 * S
    # ---- trunk & limbs (vector)
    surf = surface(W_, H_)
    c = surf.getCanvas()
    P = lambda dx, dy: (bx + dx * S, by - dy * S)
    limbs = [
        ([P(-6, 0), P(-12, 120), P(-4, 230), P(-60, 330), P(-190, 430), P(-330, 500), P(-470, 540)], 150 * S, 30 * S),
        ([P(4, 180), P(40, 290), P(150, 390), P(290, 460), P(440, 500)], 92 * S, 28 * S),
        ([P(-10, 250), P(10, 380), P(30, 520), P(10, 680)], 70 * S, 24 * S),
        ([P(-150, 410), P(-210, 540), P(-230, 640)], 40 * S, 16 * S),
        ([P(200, 420), P(290, 560), P(320, 630)], 36 * S, 14 * S),
        ([P(-300, 480), P(-400, 600)], 26 * S, 12 * S),
        ([P(330, 470), P(470, 580)], 24 * S, 10 * S),
    ]
    trunk_paths = [_limb(pts, w0, w1) for pts, w0, w1 in limbs]
    roots = skia.Path()
    roots.moveTo(*P(-150, -6))
    roots.quadTo(*P(-80, 20), *P(-66, 130))
    roots.lineTo(*P(60, 130))
    roots.quadTo(*P(80, 20), *P(160, -6))
    roots.close()
    trunk_paths.append(roots)
    union = trunk_paths[0]
    for p in trunk_paths[1:]:
        union = skia.Op(union, p, skia.PathOp.kUnion_PathOp) or union
    if silhouette:
        c.drawPath(union, paint_fill(skia.Color4f(*pal['bark_shadow'], 1)))
    else:
        # bark: lit left edge, shadow right, vertical texture strokes
        sh = skia.GradientShader.MakeLinear(
            [skia.Point(bx - 90 * S, 0), skia.Point(bx + 80 * S, 0)],
            [skia.Color4f(*pal['bark_lit'], 1).toColor(), skia.Color4f(*pal['bark_mid'], 1).toColor(),
             skia.Color4f(*pal['bark_shadow'], 1).toColor()], [0.0, 0.45, 1.0])
        p = skia.Paint(AntiAlias=True)
        p.setShader(sh)
        c.drawPath(union, p)
        c.save()
        c.clipPath(union, doAntiAlias=True)
        # cooler shade under the crown
        shade = skia.Paint(AntiAlias=True)
        shade.setShader(skia.GradientShader.MakeLinear(
            [skia.Point(0, by - 560 * S), skia.Point(0, by - 200 * S)],
            [skia.Color4f(*(pal['bark_shadow'] * 0.7), 0.85).toColor(),
             skia.Color4f(*(pal['bark_shadow'] * 0.7), 0.0).toColor()]))
        c.drawRect(skia.Rect.MakeWH(W_, H_), shade)
        st = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
        for _ in range(int(420 * S) + 40):
            x = bx + rng.uniform(-480, 480) * S
            y = by - rng.uniform(0, 640) * S
            L = rng.uniform(16, 60) * S
            dark = rng.random() < 0.6
            col = pal['bark_shadow'] * 0.8 if dark else pal['bark_lit'] * 1.1
            st.setColor4f(skia.Color4f(*np.clip(col, 0, 1), 0.5))
            st.setStrokeWidth(max(1.0, rng.uniform(1.5, 4) * S))
            q = skia.Path()
            q.moveTo(x, y)
            q.quadTo(x + rng.normal(0, 4) * S, y - L * 0.5, x + rng.normal(0, 6) * S, y - L)
            c.drawPath(q, st)
        c.restore()
    trunk = to_array(surf)
    # ---- foliage clumps: a wide, slightly drooping dome
    cx, cy = bx, by - 650 * S
    ax_, ay_ = 640 * S, 290 * S
    clumps = []
    tries = 0
    while len(clumps) < 62 and tries < 6000:
        tries += 1
        u, v = rng.uniform(-1, 1), rng.uniform(-1, 0.95)
        lim = 0.45 + 0.5 * abs(u)          # sides droop lower than the middle
        if u * u + v * v > 1 or v > lim:
            continue
        x, y = cx + u * ax_, cy + v * ay_
        r = rng.uniform(62, 112) * S * (1.12 - 0.35 * (u * u + v * v))
        if any(np.hypot(x - q.x, y - q.y) < (r + q.r) * 0.55 for q in clumps):
            continue
        z = (1 - (u * u + v * v)) * 160 * S + rng.uniform(0, 70) * S + v * 50 * S
        clumps.append(Puff(x, y, z, r))
    pts = _boundary_points(clumps, 0.9, rng, min_up=-1.0)
    rng.shuffle(pts)
    chosen = []
    for (x, y, par) in pts:
        r = par.r * rng.uniform(0.26, 0.42)
        if any(np.hypot(x - q[0], y - q[1]) < (r + q[2]) * 0.7 for q in chosen):
            continue
        chosen.append((x, y, r))
        dx, dy = x - par.x, y - par.y
        L = np.hypot(dx, dy) + 1e-6
        clumps.append(Puff(x - dx / L * r * 0.45, y - dy / L * r * 0.45, par.z + r * 0.3, r))
    leaf = pal['leaf']
    fol = render_puffs(clumps, W_, H_, leaf, seed=seed, base_y=cy + ay_ * 0.9, warp=7 * S,
                       warp_cell=13 * S, edge=1.0, shade_noise=0.30, shade_cell=11 * S,
                       local_w=0.5, rim=0.25, bottom_dark=0.5, cut_base=False, tex_amp=2.5)
    if silhouette:
        fol[..., :3] = fol[..., 3:4] * pal['leaf']['deep'][None, None]
    out = fol + trunk * (1 - fol[..., 3:4])
    return Sprite(out, bx, by)


def draw_bushes(canvas, rng, n, x0, x1, y_fn, size, cols, haze=0.0, haze_col=None):
    """Rows of small painted trees/bushes on distant hills (dark mass + lit top-left)."""
    lit, mid, shadow, dark = cols
    p = skia.Paint(AntiAlias=True)

    def setc(cc, a=1.0):
        if haze:
            cc = lerp(cc, haze_col, haze)
        p.setColor4f(skia.Color4f(*np.clip(cc, 0, 1), a))

    for _ in range(n):
        x = rng.uniform(x0, x1)
        y = y_fn(x)
        s = size * rng.uniform(0.6, 1.3)
        blobs = [(x + rng.uniform(-1, 1) * s, y - rng.uniform(0.2, 1.0) * s, s * rng.uniform(0.6, 1.0))
                 for _ in range(rng.integers(3, 6))]
        setc(dark)
        for bx, by, r in blobs:
            canvas.drawCircle(bx, by, r, p)
        setc(shadow)
        for bx, by, r in blobs:
            canvas.drawCircle(bx - r * 0.12, by - r * 0.15, r * 0.82, p)
        setc(mid)
        for bx, by, r in blobs:
            canvas.drawCircle(bx - r * 0.3, by - r * 0.35, r * 0.5, p)
