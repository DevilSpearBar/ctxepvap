"""The nine shots of «Облачный кит». Each shot draws one frame onto a skia canvas.

Assets are built lazily per process and cached, so rendering can be parallel.
Characters animate "on twos" (new drawing every 2 frames) like hand-drawn cels;
cameras, clouds and grass move on ones.
"""

import math

import numpy as np
import skia

import timeline as TL
from . import land, sky
from .core import (H, W, LINEAR, MIPMAP, draw_image, ease_in_out, ease_in_out_sine, ease_out,
                   fbm, lerp, paint_fill, rgb_layer, rgbf, smoothstep, sstep, surface, to_image,
                   value_noise)
from .whale import Whale, make_mist_puffs

FPS = TL.FPS

try:
    from . import girl as G
except Exception:  # pragma: no cover - placeholder until the character module exists
    G = None


# ============================================================ girl adapter
class _StubGirl:
    """Placeholder figure so shots can be laid out before the real rig exists."""

    @staticmethod
    def pose_run(phase):
        return ('run', phase)

    pose_stand = staticmethod(lambda t: ('stand', t))
    pose_look_up = staticmethod(lambda k, t: ('look', k))
    pose_reach_up = staticmethod(lambda k, t: ('reach', k))
    pose_catch = staticmethod(lambda k: ('catch', k))
    pose_hat_on = staticmethod(lambda k: ('haton', k))
    pose_wave = staticmethod(lambda t: ('wave', t))
    lerp_pose = staticmethod(lambda a, b, k: b if k > 0.5 else a)
    hand_position = staticmethod(lambda p: (40.0, -330.0))
    head_top = staticmethod(lambda p: (0.0, -400.0, 0.0))

    @staticmethod
    def draw_girl(c, pose, wind=0.3, wind_dir=1, t=0.0, hat_on=True, smile=0.0, palette='day'):
        p = paint_fill((0.85, 0.28, 0.23, 1))
        c.drawRect(skia.Rect.MakeLTRB(-45, -260, 45, -90), p)
        c.drawCircle(0, -330, 68, paint_fill((0.23, 0.15, 0.13, 1)))
        c.drawRect(skia.Rect.MakeLTRB(-30, -90, 30, 0), paint_fill((0.98, 0.85, 0.78, 1)))
        if hat_on:
            _StubGirl.draw_hat(c.__class__ and c, t=t) if False else None
            c.save(); c.translate(0, -392); _StubGirl.draw_hat(c); c.restore()

    @staticmethod
    def draw_hat(c, rot_deg=0.0, tilt=0.0, spin=0.0, t=0.0, wind=0.5, palette='day'):
        c.save(); c.rotate(rot_deg)
        c.drawOval(skia.Rect.MakeLTRB(-75, -12 - 40 * abs(tilt), 75, 12 + 40 * abs(tilt)),
                   paint_fill((0.95, 0.87, 0.63, 1)))
        c.drawOval(skia.Rect.MakeLTRB(-38, -40, 38, 6), paint_fill((0.93, 0.84, 0.58, 1)))
        c.restore()

    @staticmethod
    def draw_girl_closeup(c, blink=0.0, mouth_open=0.0, smile=0.0, gaze=(0.6, -0.5), wind=0.6,
                          t=0.0, palette='day'):
        c.drawCircle(760, 430, 190, paint_fill((0.98, 0.87, 0.79, 1)))
        c.drawCircle(760, 380, 200, paint_fill((0.23, 0.15, 0.13, 1)))


def girl():
    return G if G is not None else _StubGirl


def twos(f):
    return f - (f % 2)


# ============================================================ shared helpers
_CACHE = {}


def cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def img_of(arr):
    return to_image(arr)


def sky_img(h, pal=sky.DAY, horizon=None, top=0.0, seed=1, w=W, mid=0.55):
    def build():
        g = sky.sky_gradient(w, h, pal, horizon_y=horizon if horizon else h, top_y=top, seed=seed,
                             mid_pos=mid)
        return to_image(rgb_layer(g))
    return cached(('sky', h, id(pal), horizon, top, seed, w, mid), build)


def cloud(seed, w, h, pal=sky.DAY, **kw):
    def build():
        spr = sky.make_cumulus(seed, w, h, pal=pal, **kw)
        return (to_image(spr.rgba), spr)
    return cached(('cu', seed, w, h, id(pal), tuple(sorted(kw.items()))), build)


def stratus(seed, w, h, pal=sky.DAY, **kw):
    def build():
        spr = sky.make_stratus(seed, w, h, pal=pal, **kw)
        return (to_image(spr.rgba), spr)
    return cached(('st', seed, w, h, id(pal), tuple(sorted(kw.items()))), build)


def band(seed, w, h, pal=sky.SUNSET, **kw):
    def build():
        spr = sky.make_band(seed, w, h, pal=pal, **kw)
        return (to_image(spr.rgba), spr)
    return cached(('band', seed, w, h, id(pal), tuple(sorted(kw.items()))), build)


def put(c, cl, x, y, scale=1.0, alpha=1.0):
    img, spr = cl
    sky.blit_sprite(c, img, spr, x, y, scale=scale, alpha=alpha)


def tree_day():
    def build():
        spr = land.make_tree(7, land.GDAY, scale=0.75)
        return (to_image(spr.rgba), spr)
    return cached('tree_day', build)


def tree_sunset():
    def build():
        spr = land.make_tree(7, land.GSUNSET, scale=0.5)
        return (to_image(spr.rgba), spr)
    return cached('tree_sunset', build)


def draw_tree(c, tr, x, y, scale, t, sway=0.0, gust=0.0, strip=8):
    """Tree with anchor (trunk base) at (x, y). Sway bends the crown sideways in strips."""
    img, spr = tr
    h = spr.rgba.shape[0]
    w = spr.rgba.shape[1]
    if sway == 0 and gust == 0:
        draw_image(c, img, x - spr.ax * scale, y - spr.ay * scale, scale=scale, sampling=MIPMAP)
        return
    c.save()
    c.translate(x - spr.ax * scale, y - spr.ay * scale)
    c.scale(scale, scale)
    for sy in range(0, h, strip):
        hh = min(strip, h - sy)
        up = max(0.0, (spr.ay - (sy + hh * 0.5)) / spr.ay)       # 0 at base, 1 at top
        k = up ** 1.6
        dx = (sway * math.sin(t * 1.3 + up * 1.2) * 6 + gust * (14 + 5 * math.sin(t * 9.0 + up * 3))) * k
        src = skia.Rect.MakeXYWH(0, sy, w, hh + 1)
        dst = skia.Rect.MakeXYWH(dx, sy, w, hh + 1)
        c.drawImageRect(img, src, dst, MIPMAP, skia.Paint())
    c.restore()


def wave_tex(w, h, seed, color, max_a=0.22, cell=70, vstretch=4):
    """Horizontally tileable light-band texture: wind running over grass."""
    def build():
        rng = np.random.default_rng(seed)
        n = value_noise(max(4, h // vstretch), w, cell, rng, wrap_x=True)
        n2 = value_noise(max(4, h // vstretch), w, cell / 2.3, rng, wrap_x=True)
        n = 0.7 * n + 0.3 * n2
        from scipy import ndimage
        n = ndimage.zoom(n, (h / n.shape[0], 1), order=1)[:h]
        a = smoothstep(0.15, 0.75, n) * max_a
        col = np.broadcast_to(color, (h, w, 3))
        return to_image(rgb_layer(col, a))
    return cached(('wave', w, h, seed, tuple(color), max_a, cell), build)


def draw_waves(c, tex, offset, y, alpha=1.0, blend=skia.BlendMode.kSrcATop):
    """Draw a tileable wave texture with horizontal offset (call inside a saveLayer)."""
    tw = tex.width()
    o = offset % tw
    p = skia.Paint()
    p.setBlendMode(blend)
    if alpha < 1:
        p.setAlphaf(alpha)
    for k in (-1, 0, 1):
        c.drawImage(tex, -o + k * tw, y, LINEAR, p)


def ground_img(key, w, h, top_y, cols, seed, **kw):
    return cached(('gnd', key), lambda: to_image(land.paint_ground(w, h, top_y, cols, seed, **kw)))


def leaf_path(size):
    p = skia.Path()
    p.moveTo(-size, 0)
    p.quadTo(0, -size * 0.55, size, 0)
    p.quadTo(0, size * 0.55, -size, 0)
    p.close()
    return p


class Leaves:
    """Leaves torn off by the gust, tumbling downwind."""

    def __init__(self, seed, n, spawn_box, t0, t1, vx=(9, 16), vy=(-4, 2), size=(5, 9),
                 cols=None):
        rng = np.random.default_rng(seed)
        self.n = n
        self.t = rng.uniform(t0, t1, n)
        x0, y0, x1, y1 = spawn_box
        self.x = rng.uniform(x0, x1, n)
        self.y = rng.uniform(y0, y1, n)
        self.vx = rng.uniform(*vx, n)
        self.vy = rng.uniform(*vy, n)
        self.s = rng.uniform(*size, n)
        self.ph = rng.uniform(0, 6.28, n)
        self.spin = rng.uniform(4, 10, n) * rng.choice([-1, 1], n)
        cols = cols or [rgbf('6fa63c'), rgbf('8cbf4a'), rgbf('4f8a36'), rgbf('a9cf5a')]
        self.c = [cols[i] for i in rng.integers(len(cols), size=n)]

    def draw(self, c, f, alpha=1.0):
        p = skia.Paint(AntiAlias=True)
        for i in range(self.n):
            age = f - self.t[i]
            if age < 0 or age > 90:
                continue
            x = self.x[i] + self.vx[i] * age + 10 * math.sin(age * 0.2 + self.ph[i])
            y = self.y[i] + self.vy[i] * age + 0.04 * age * age + 14 * math.sin(age * 0.13 + self.ph[i])
            if x < -40 or x > W + 40 or y < -40 or y > H + 40:
                continue
            c.save()
            c.translate(x, y)
            c.rotate(self.ph[i] * 57 + self.spin[i] * age)
            c.scale(1.0, 0.35 + 0.65 * abs(math.sin(age * 0.25 + self.ph[i])))
            col = self.c[i]
            p.setColor4f(skia.Color4f(*col, alpha))
            c.drawPath(leaf_path(self.s[i]), p)
            c.restore()


def draw_birds(c, f, birds):
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=2.2,
                   StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    p.setColor4f(skia.Color4f(0.18, 0.22, 0.32, 0.85))
    for (f0, x0, y0, vx, vy, s, ph) in birds:
        age = f - f0
        if age < 0:
            continue
        x, y = x0 + vx * age, y0 + vy * age + 6 * math.sin(age * 0.08 + ph)
        flap = math.sin(age * 0.75 + ph)
        wy = -s * 0.55 * flap
        path = skia.Path()
        path.moveTo(x - s, y + wy)
        path.quadTo(x - s * 0.45, y - s * 0.25 + wy * 0.3, x, y)
        path.quadTo(x + s * 0.45, y - s * 0.25 + wy * 0.3, x + s, y + wy)
        c.drawPath(path, p)


def sparkle(c, x, y, r, a):
    if a <= 0.01:
        return
    p = paint_fill(skia.Color4f(1, 1, 0.94, a))
    path = skia.Path()
    path.moveTo(x, y - r)
    path.quadTo(x, y, x + r * 0.28, y)
    path.quadTo(x, y, x, y + r)
    path.quadTo(x, y, x - r * 0.28, y)
    path.quadTo(x, y, x, y - r)
    path.moveTo(x - r * 0.75, y)
    path.quadTo(x, y, x, y - r * 0.2)
    path.quadTo(x, y, x + r * 0.75, y)
    path.quadTo(x, y, x, y + r * 0.2)
    path.quadTo(x, y, x - r * 0.75, y)
    c.drawPath(path, p)
    g = skia.Paint(AntiAlias=True)
    g.setShader(skia.GradientShader.MakeRadial(
        skia.Point(x, y), r * 0.9, [skia.Color4f(1, 1, 0.9, 0.55 * a).toColor(), skia.Color4f(1, 1, 1, 0).toColor()]))
    c.drawCircle(x, y, r * 0.9, g)


def hat_tumble(t, seed=0.0):
    """Rotation/tilt/spin of the flying hat as smooth functions of time (s)."""
    rot = 25 * math.sin(t * 2.1 + seed) + 18 * math.sin(t * 3.7 + 1.3 + seed)
    tilt = 0.55 * math.sin(t * 2.6 + 0.4 + seed)
    spin = (t * 160 + seed * 40) % 360
    return rot, tilt, spin


def draw_hat_at(c, x, y, scale, t, rot=0.0, tilt=0.0, spin=0.0, wind=0.5, palette='day'):
    c.save()
    c.translate(x, y)
    c.scale(scale, scale)
    girl().draw_hat(c, rot_deg=rot, tilt=tilt, spin=spin, t=t, wind=wind, palette=palette)
    c.restore()


def draw_girl_at(c, x, y, scale, pose, **kw):
    c.save()
    c.translate(x, y)
    c.scale(scale, scale)
    girl().draw_girl(c, pose, **kw)
    c.restore()


def local_to_world(x, y, scale, p):
    return x + p[0] * scale, y + p[1] * scale


GRASS_DAY = (land.GDAY['grass_lit'], land.GDAY['grass_mid'], land.GDAY['grass_shadow'], land.GDAY['grass_dark'])
HILL_DAY = (land.GDAY['hill_lit'], land.GDAY['hill_mid'], land.GDAY['hill_shadow'], land.GDAY['hill_dark'])
FARH_DAY = (land.GDAY['far_hill'], land.GDAY['far_hill'], land.GDAY['far_hill_dark'], land.GDAY['far_hill_dark'])
MTN_DAY = (land.GDAY['far_mtn'], land.GDAY['far_mtn'], land.GDAY['far_mtn_dark'], land.GDAY['far_mtn_dark'])
WAVE_COL = rgbf('e9f7a6')


def distant_land(key, w, h, base, seed=1, bushes=True, haze=0.0):
    """Mountains + far hills + mid hills with bushes as one pre-rendered layer."""
    def build():
        s = surface(w, h)
        c = s.getCanvas()
        G_ = land.GDAY
        r_m = land.ridge(w, seed, base, 34, cell=420)
        c.drawImage(to_image(land.paint_ground(w, h, r_m, MTN_DAY, seed + 1, patch=0.05, rim=0.0,
                                               haze=0.38 + haze, haze_col=G_['haze'])), 0, 0)
        r_f = land.ridge(w, seed + 2, base + 34, 16, cell=300)
        c.drawImage(to_image(land.paint_ground(w, h, r_f, FARH_DAY, seed + 3, patch=0.12, rim=0.05,
                                               haze=0.26 + haze, haze_col=G_['haze'])), 0, 0)
        rng = np.random.default_rng(seed + 9)
        if bushes:
            land.draw_bushes(c, rng, int(w / 36), 0, w, lambda xx: r_f[int(np.clip(xx, 0, w - 1))] + 5, 5,
                             FARH_DAY, haze=0.3 + haze, haze_col=G_['haze'])
        r_h = land.ridge(w, seed + 4, base + 78, 30, cell=520)
        c.drawImage(to_image(land.paint_ground(w, h, r_h, HILL_DAY, seed + 5, strokes=int(w * h / 260),
                                               stroke_len=(4, 8), stroke_w=(1, 1.8), haze=0.14 + haze,
                                               haze_col=G_['haze'], grad_depth=220, rim=0.12)), 0, 0)
        if bushes:
            land.draw_bushes(c, rng, int(w / 30), 0, w, lambda xx: r_h[int(np.clip(xx, 0, w - 1))] + 16, 9,
                             HILL_DAY, haze=0.18 + haze, haze_col=G_['haze'])
        return s.makeImageSnapshot()
    return cached(('distant', key), build)


# ============================================================ S1 establishing
def s1_establish(c, f, t):
    T = f / FPS
    WW, HH = W + 80, H + 620
    tilt = ease_in_out_sine((f - 10) / 150.0)
    cam_y = 620 * tilt + 6 * sstep(150, 192, f)
    cam_x = 30 - 30 * (f / 192.0)
    c.save()
    c.translate(-cam_x, -cam_y)
    c.drawImage(sky_img(HH, horizon=1150, top=0, seed=3, w=WW, mid=0.6), 0, 0)
    drift = f * 0.12
    put(c, cloud(41, 600, 330, height_frac=0.5, n_base=3, tower=0.3), 1680 + drift * 0.6, 640, 0.9)
    put(c, cloud(3, 1100, 760, height_frac=0.85, n_base=5, tower=0.75), 760 + drift, 990, 1.0)
    put(c, cloud(21, 700, 420, height_frac=0.6, n_base=3, tower=0.4), 1560 + drift * 0.8, 1000, 0.85)
    put(c, stratus(5, 1500, 170, thickness=0.42), 980 + drift * 0.4, 1112, 1.0, alpha=0.9)
    draw_birds(c, f, [(20, -60, 330, 3.2, -0.4, 13, 0.0), (26, -120, 365, 3.0, -0.3, 11, 1.7),
                      (30, -90, 300, 3.4, -0.5, 10, 3.1)])
    c.drawImage(distant_land('s1', WW, HH, 1088, seed=11), 0, 0)
    # near hill with the tree
    xs = np.arange(WW)
    r_n = 1262 - 105 * np.exp(-((xs - 1500) / 560.0) ** 2) + land.ridge(WW, 12, 0, 8, cell=300) + (xs < 700) * 0
    gnd = ground_img('s1_near', WW, HH, r_n, GRASS_DAY, 13, strokes=16000, stroke_len=(7, 15),
                     stroke_w=(1.3, 2.4), flowers=600, persp=(1150, HH), grad_depth=300)
    draw_tree(c, tree_day(), 1530, r_n[1530] + 10, 0.52, T, sway=0.6)
    c.saveLayer()
    c.drawImage(gnd, 0, 0)
    draw_waves(c, wave_tex(WW, 300, 5, WAVE_COL, 0.2), f * 7.0, 1124)
    c.restore()
    blades = cached('s1_blades', lambda: land.Blades(3, 420, -60, WW + 60, lambda x: HH + 12, (60, 150), (5, 10),
                                                     land.GDAY['blade']))
    blades.draw(c, T, wind=0.45, gust=0.0, xmax=WW + 60)
    c.restore()


# ============================================================ S2 run
RUN_START = 196   # first right-foot contact (timeline run_footfalls)


def s2_run(c, f, t):
    lf = f - 192
    T = f / FPS
    c.drawImage(sky_img(H, horizon=640, seed=4, mid=0.5), 0, 0)
    put(c, cloud(52, 900, 520, height_frac=0.7, n_base=4, tower=0.55), 1250 - lf * 0.5, 470, 0.8)
    put(c, cloud(57, 600, 320, height_frac=0.5, n_base=3, tower=0.3), 380 - lf * 0.5, 430, 0.7)
    put(c, cloud(58, 500, 300, height_frac=0.5, n_base=3, tower=0.3), 2150 - lf * 0.5, 400, 0.6)
    DW = W + 1300
    c.drawImage(distant_land('s2', DW, H, 452, seed=21), -lf * 2.6, 0)
    # running ground (tileable strip)
    GW = 2600
    xs = np.arange(GW)
    r_g = 548 + 10 * np.sin(xs / GW * 2 * np.pi) + 6 * np.sin(xs / GW * 6 * np.pi + 1)
    gnd = ground_img('s2_near', GW, H, r_g, GRASS_DAY, 23, strokes=26000, stroke_len=(8, 18),
                     stroke_w=(1.4, 2.8), flowers=700, persp=(540, H), grad_depth=260, rim=0.15)
    off = (lf * 17.0) % GW
    c.saveLayer()
    c.drawImage(gnd, -off, 0)
    c.drawImage(gnd, -off + GW, 0)
    draw_waves(c, wave_tex(GW, 300, 7, WAVE_COL, 0.16), lf * 17.0 + lf * 5, 520)
    c.restore()
    # back grass row (behind her legs)
    back = cached('s2_back', lambda: land.Blades(31, 260, 0, 2600, lambda x: 700, (70, 140), (5, 9),
                                                 land.GDAY['blade'][1:4]))
    back.draw(c, T, wind=0.5, wind_dir=-1, scroll=lf * 17.0, wrap=2600, xmin=-100, xmax=2500)
    # the girl
    g = girl()
    fp = twos(f)
    phase = ((fp - RUN_START) / 16.0) % 1.0
    gx = 720 + 120 * ease_in_out(lf / 192.0)
    draw_girl_at(c, gx, 712, 1.0, g.pose_run(phase), wind=0.55, wind_dir=-1, t=fp / FPS, hat_on=True)
    # front grass hides the feet
    front = cached('s2_front', lambda: land.Blades(33, 330, 0, 2600, lambda x: 735 + (x % 7) * 3, (90, 170), (6, 11),
                                                   land.GDAY['blade']))
    front.draw(c, T, wind=0.55, wind_dir=-1, scroll=lf * 17.0, wrap=2600, xmin=-100, xmax=2500)
    fg = cached('s2_fg', lambda: land.Blades(35, 90, 0, 3000, lambda x: H + 40, (200, 330), (12, 20),
                                             [land.GDAY['blade'][0] * 0.8, land.GDAY['blade'][4] * 0.85]))
    fg.draw(c, T, wind=0.7, wind_dir=-1, scroll=lf * 30.0, wrap=3000, xmin=-200, xmax=2800)


# ============================================================ S3 hilltop & gust
STOP_CONTACTS = [388, 397, 407, 418]
GUST = TL.EVENTS['gust']
HAT_OFF_F = TL.t2f(TL.EVENTS['hat_lift_off'])


def gust_amount(T):
    s, p, e = GUST
    if T < s or T > e + 1.0:
        return 0.0
    if T < p:
        return ease_in_out((T - s) / (p - s))
    return 1.0 - ease_in_out((T - p) / (e + 1.0 - p))


def s3_girl_state(f):
    """Pose + position for the girl in S3 (frame f is global, already on twos)."""
    g = girl()
    T = f / FPS
    # phase: runs in, then decelerating contacts at STOP_CONTACTS (phase 0, .5, 1, 1.5)
    keys_f = [384 - 8, 388, 397, 407, 418]
    keys_p = [-0.5, 0.0, 0.5, 1.0, 1.5]
    x_keys = [140, 330, 545, 720, 850]
    if f <= 418:
        phase = float(np.interp(f, keys_f, keys_p))
        x = float(np.interp(f, keys_f, x_keys))
        pose = g.pose_run(phase % 1.0)
        if f > 407:
            pose = g.lerp_pose(pose, g.pose_stand(T), sstep(407, 420, f) * 0.6)
        return x, pose
    x = 850 + 40 * ease_out((f - 418) / 14.0)
    k_stop = sstep(418, 432, f)
    pose = g.lerp_pose(g.pose_run(0.5), g.pose_stand(T), 0.6 + 0.4 * k_stop)
    if f >= 432:
        pose = g.pose_stand(T)
    if f >= 440:
        pose = g.lerp_pose(g.pose_stand(T), g.pose_look_up(0.35, T), sstep(440, 456, f))
    if f >= HAT_OFF_F:
        k = sstep(HAT_OFF_F, HAT_OFF_F + 14, f)
        pose = g.lerp_pose(g.pose_look_up(0.35, T), g.pose_reach_up(1.0, T), k)
    return x, pose


def hat_flight_s3(f, gx, gy, scale, pose0):
    """Hat position after lift-off: from her head up and away to the upper right."""
    g = girl()
    hx, hy, ha = g.head_top(pose0)
    x0, y0 = gx + hx * scale, gy + hy * scale
    age = (f - HAT_OFF_F)
    a = age / FPS
    x = x0 + 60 * a + 260 * a * a
    y = y0 - 90 * a - 150 * a * a + 20 * math.sin(a * 6)
    rot, tilt, spin = hat_tumble(a * 1.3, 0.5)
    rot = lerp(ha, rot, min(1.0, a * 3)) + 40 * a
    return x, y, rot, tilt * min(1, a * 2), spin


def s3_hilltop(c, f, t):
    T = f / FPS
    lf = f - 384
    gust = gust_amount(T)
    zoom = 1.0 + 0.03 * (lf / 144.0)
    c.save()
    c.translate(W / 2, H / 2)
    c.scale(zoom, zoom)
    c.translate(-W / 2, -H / 2)
    c.drawImage(sky_img(H, horizon=560, seed=6, mid=0.55), 0, 0)
    drift = lf * 0.15 + gust * 3
    put(c, cloud(61, 1000, 640, height_frac=0.8, n_base=4, tower=0.7), 980 + drift, 420, 0.82)
    put(c, cloud(64, 640, 380, height_frac=0.55, n_base=3, tower=0.3), 260 + drift, 380, 0.6)
    put(c, stratus(66, 1300, 150, thickness=0.42), 1500 + drift, 470, 0.9, alpha=0.95)
    c.drawImage(distant_land('s3', W, H, 428, seed=31, haze=0.04), 0, 0)
    xs = np.arange(W)
    r_n = 598 - 26 * np.exp(-((xs - 1100) / 700.0) ** 2) + land.ridge(W, 32, 0, 5, cell=260)
    gnd = ground_img('s3_near', W, H, r_n, GRASS_DAY, 33, strokes=15000, stroke_len=(8, 16),
                     stroke_w=(1.4, 2.6), flowers=420, persp=(560, H), grad_depth=220)
    # soft shade under the tree
    c.saveLayer()
    c.drawImage(gnd, 0, 0)
    draw_waves(c, wave_tex(W, 260, 9, WAVE_COL, 0.16 + 0.12 * gust), lf * (6 + 16 * gust) + 900, 560)
    sh = skia.Paint(AntiAlias=True)
    sh.setShader(skia.GradientShader.MakeRadial(skia.Point(1540, 640), 520,
                                                [skia.Color4f(0.1, 0.25, 0.12, 0.42).toColor(),
                                                 skia.Color4f(0.1, 0.25, 0.12, 0.0).toColor()]))
    c.save()
    c.scale(1.0, 0.22)
    c.translate(0, 640 / 0.22 - 640)
    c.drawCircle(1540, 640, 520, sh)
    c.restore()
    c.restore()
    draw_tree(c, tree_day(), 1560, r_n[1560] + 12, 0.72, T, sway=0.5, gust=gust)
    back = cached('s3_back', lambda: land.Blades(41, 240, -40, W + 40, lambda x: 640 + (x % 5) * 2, (40, 90), (4, 8),
                                                 land.GDAY['blade'][1:4]))
    back.draw(c, T, wind=0.35 + 0.5 * gust, gust=gust * 0.4)
    # girl
    g = girl()
    fp = twos(f)
    gx, pose = s3_girl_state(fp)
    gy, gs = 684, 0.74
    hat_on = f < HAT_OFF_F
    wind = 0.3 + 0.7 * gust
    draw_girl_at(c, gx, gy, gs, pose, wind=wind, wind_dir=1, t=fp / FPS, hat_on=hat_on,
                 smile=0.0)
    front = cached('s3_front', lambda: land.Blades(43, 300, -40, W + 40, lambda x: 700 + (x % 9) * 4, (50, 110), (5, 9),
                                                   land.GDAY['blade']))
    front.draw(c, T, wind=0.35 + 0.5 * gust, gust=gust * 0.5)
    leaves = cached('s3_leaves', lambda: Leaves(44, 60, (1150, 80, 1800, 420), 446, 505, vx=(10, 22),
                                                vy=(-5, 1)))
    leaves.draw(c, f)
    if not hat_on:
        _, pose0 = s3_girl_state(HAT_OFF_F)
        x, y, rot, tilt, spin = hat_flight_s3(f, gx, gy, gs, pose0)
        if y > -200:
            draw_hat_at(c, x, y, gs, T, rot, tilt, spin, wind=0.9)
    fg = cached('s3_fg', lambda: land.Blades(45, 70, -100, W + 100, lambda x: H + 40, (160, 280), (12, 18),
                                             [land.GDAY['blade'][0] * 0.8, land.GDAY['blade'][4] * 0.85]))
    fg.draw(c, T, wind=0.4 + 0.6 * gust, gust=gust * 0.6)
    c.restore()


# ============================================================ S4 close-up
def s4_closeup(c, f, t):
    T = f / FPS
    lf = f - 528
    push = 1.0 + 0.035 * ease_in_out(lf / 96.0)
    c.drawImage(sky_img(H, horizon=1100, top=-200, seed=8, mid=0.5), 0, 0)
    put(c, cloud(71, 1000, 700, height_frac=0.85, n_base=4, tower=0.8), 1450 + lf * 0.25, 900, 0.95)
    put(c, cloud(73, 600, 340, height_frac=0.5, n_base=3, tower=0.3), 260 + lf * 0.3, 870, 0.8)
    # canopy edge at the top-left, rustling (trunk stays off-frame to the left)
    draw_tree(c, tree_day(), -175, 695, 1.6, T, sway=1.0, gust=0.35)
    leaves = cached('s4_leaves', lambda: Leaves(46, 40, (-200, 0, 700, 300), 520, 610, vx=(8, 16),
                                                vy=(-2, 3), size=(8, 15)))
    leaves.draw(c, f)
    fp = twos(f)
    tt = fp / FPS
    blink_f = TL.t2f(TL.EVENTS['close_up_blink'])
    bl = max(0.0, 1.0 - abs(fp - blink_f - 2) / 3.0)
    mouth = lerp(0.75, 0.25, sstep(540, 600, fp))
    smile = 0.35 * sstep(590, 620, fp)
    gaze = (0.6 + 0.1 * math.sin(tt * 1.5), -0.55 - 0.15 * sstep(528, 560, fp))
    wind = lerp(0.75, 0.45, lf / 96.0)
    c.save()
    c.translate(760, 430)
    c.scale(push, push)
    c.translate(-760, -430)
    girl().draw_girl_closeup(c, blink=bl, mouth_open=mouth, smile=smile, gaze=gaze, wind=wind, t=tt)
    c.restore()


# ============================================================ S5 the hat in the sky
def s5_hat_sky(c, f, t):
    T = f / FPS
    lf = f - 624
    k = lf / 96.0
    cam = 1100 * ease_in_out_sine(k * 0.9 + 0.05)          # camera tilts up (content moves down)
    c.drawImage(sky_img(H + 1200, horizon=H + 1250, top=0, seed=9, mid=0.7), 0, -1150 + cam * 0.9)
    # far clouds (slow), mid clouds, near wisps (fast) — staggered in depth
    put(c, cloud(81, 900, 520, height_frac=0.7, n_base=4, tower=0.5), 1580, 260 + cam * 0.3, 0.55)
    put(c, cloud(82, 700, 420, height_frac=0.6, n_base=3, tower=0.45), 260, -60 + cam * 0.3, 0.5)
    put(c, cloud(86, 600, 360, height_frac=0.55, n_base=3, tower=0.4), 900, -520 + cam * 0.3, 0.45)
    put(c, cloud(83, 1000, 600, height_frac=0.7, n_base=4, tower=0.6), 380, 980 + cam * 0.62, 1.0)
    put(c, cloud(84, 800, 500, height_frac=0.6, n_base=4, tower=0.5), 1560, 420 + cam * 0.62, 0.9)
    put(c, cloud(87, 900, 520, height_frac=0.65, n_base=4, tower=0.5), 300, -380 + cam * 0.62, 0.85)
    # the hat rises through frame centre-right, tumbling
    a = lf / FPS
    hx = 620 + 420 * ease_in_out(k) + 60 * math.sin(a * 2.2)
    hy = 720 - 380 * ease_out(k) + 34 * math.sin(a * 3.1)
    rot, tilt, spin = hat_tumble(a + 1.8, 1.1)
    draw_hat_at(c, hx, hy, 1.45, T, rot, tilt, spin, wind=0.9)
    # near translucent wisp passing in front (around 28.2 s)
    wisp_y = -520 + cam * 1.35
    put(c, stratus(85, 1600, 200, thickness=0.45), 1000, wisp_y, 1.4, alpha=0.7)


# ============================================================ S6 the whale awakens
def whale_day():
    return cached('whale_day', lambda: Whale(L=1500, pal=sky.DAY, seed=5))


def s6_whale(c, f, t):
    T = f / FPS
    lf = f - 720
    zoom = 1.06 - 0.06 * ease_in_out(lf / 192.0)
    c.save()
    c.translate(W / 2, H / 2)
    c.scale(zoom, zoom)
    c.translate(-W / 2, -H / 2)
    c.drawImage(sky_img(H, horizon=1500, top=-300, seed=10, mid=0.5), 0, 0)
    put(c, cloud(91, 800, 420, height_frac=0.55, n_base=4, tower=0.4), 260, 760, 0.7)
    put(c, cloud(95, 1100, 640, height_frac=0.7, n_base=5, tower=0.5), 1560 + lf * 0.2, 640, 0.95)
    wh = whale_day()
    ws = 0.92
    move = 0.95 * ease_in_out_sine((f - 730) / 182.0) + 0.05 * (lf / 192.0)
    wx = 1026 - 920 * move          # snout from x~1150 to x~230
    wy = 40 + 20 * math.sin(T * 0.6)
    eye_f = TL.t2f(TL.EVENTS['whale_eye_open'])
    sh_f = TL.t2f(TL.EVENTS['whale_shimmer'])
    feat = sstep(sh_f, eye_f + 4, f)
    eye = sstep(eye_f, eye_f + 10, f)
    if f > eye_f + 80:  # one slow blink later on
        eye *= 1 - max(0.0, 1 - abs(f - (eye_f + 86)) / 4.0)
    swim = 0.25 + 0.75 * sstep(eye_f, eye_f + 40, f)
    wh.draw(c, wx, wy, ws, t=T, swim=swim, eye_open=eye, look=(-0.4, 0.2), features=feat)
    # cloud bank in front: the whale slides out of it
    put(c, cloud(93, 1300, 700, height_frac=0.6, n_base=5, tower=0.4), 1640, 930, 1.0)
    put(c, cloud(94, 900, 500, height_frac=0.5, n_base=4, tower=0.35), 2080, 760, 0.9)
    # sparkles as it awakens
    rng = np.random.default_rng(12)
    for i in range(30):
        st = sh_f + rng.uniform(-4, 24)
        px_, py_ = rng.uniform(150, 900), rng.uniform(170, 560)
        rr = rng.uniform(10, 22)
        life = (f - st) / 14.0
        if 0 <= life <= 1:
            sparkle(c, wx + ws * px_ + 120, wy + ws * py_, rr, math.sin(math.pi * life))
    # the hat drifts up to the head and settles there
    land_f = TL.t2f(TL.EVENTS['hat_lands_on_whale'])
    hx0, hy0 = wh.head_top
    off = wh.offset_at(hx0, T, swim)
    head = (wx + hx0 * ws, wy + (hy0 + off) * ws)
    if f < land_f:
        k = (f - 720) / (land_f - 720)
        e = ease_out(k)
        sx, sy = 980, 900
        x = lerp(sx, head[0] + 10, e) + 60 * math.sin(k * 5) * (1 - k)
        y = lerp(sy, head[1] - 14, e) - 140 * math.sin(math.pi * e) * 0.6
        rot, tilt, spin = hat_tumble(T, 2.0)
        damp = 1 - ease_in_out(k)
        draw_hat_at(c, x, y, 0.62, T, rot * damp - 10 * (1 - damp), tilt * damp + 0.15 * (1 - damp),
                    spin * damp, wind=0.6)
    else:
        bounce = math.exp(-(f - land_f) / 5.0) * math.sin((f - land_f) * 0.9) * 8
        draw_hat_at(c, head[0] + 10, head[1] - 14 - bounce, 0.62, T, -10, 0.15, 30, wind=0.4)
    c.restore()


# ============================================================ S7 from below
def s7_below(c, f, t):
    T = f / FPS
    lf = f - 912
    c.drawImage(sky_img(H, horizon=700, seed=11, mid=0.55), 0, 0)
    put(c, cloud(101, 900, 500, height_frac=0.6, n_base=4, tower=0.5), 1500 + lf * 0.1, 640, 0.6)
    put(c, cloud(102, 700, 400, height_frac=0.5, n_base=3, tower=0.4), 380 + lf * 0.1, 650, 0.55)
    wh = whale_day()
    ws = 0.40
    wx = 1250 - 4.4 * lf
    wy = 70 - 0.12 * lf + 10 * math.sin(T * 0.5)
    wh.draw(c, wx, wy, ws, t=T, swim=1.0, eye_open=1.0, look=(0.0, 0.6))
    # breath: mist puffs from the blowhole
    blow_f = TL.t2f(TL.EVENTS['whale_blow'])
    mist = cached('mist', lambda: make_mist_puffs(sky.DAY, 3, 5, 120))
    bx, by = wh.blowhole
    for i in range(10):
        st = blow_f + i * 1.5
        age = (f - st)
        if 0 <= age < 70:
            img, w_, h_ = mist[i % len(mist)]
            k = age / 70.0
            sc = ws * (0.35 + 1.1 * ease_out(k)) * (0.8 + 0.08 * i)
            px = wx + bx * ws + (i - 4.5) * 6 + 30 * k * math.sin(i * 1.7)
            py = wy + by * ws - 30 - 160 * ease_out(k) * (0.7 + 0.05 * i)
            a = (1 - k) ** 1.3 * min(1.0, age / 4.0)
            draw_image(c, img, px - w_ * sc / 2, py - h_ * sc / 2, scale=sc, alpha=a)
    # land
    c.drawImage(distant_land('s7', W, H, 600, seed=71), 0, 0)
    # the whale's shadow sweeping the far hills
    sx = wx + 700 * ws - 200
    sh = skia.Paint(AntiAlias=True)
    sh.setShader(skia.GradientShader.MakeRadial(skia.Point(0, 0), 1.0,
                                                [skia.Color4f(0.05, 0.1, 0.25, 0.35).toColor(),
                                                 skia.Color4f(0.05, 0.1, 0.25, 0.0).toColor()]))
    c.save()
    c.clipRect(skia.Rect.MakeLTRB(0, 600, W, H))
    c.translate(sx, 690)
    c.scale(330, 60)
    c.drawCircle(0, 0, 1.0, sh)
    c.restore()
    xs = np.arange(W)
    r_n = 742 - 120 * np.exp(-((xs - 420) / 520.0) ** 2) + land.ridge(W, 72, 0, 6, cell=260)
    gnd = ground_img('s7_near', W, H, r_n, GRASS_DAY, 73, strokes=7000, stroke_len=(6, 12),
                     stroke_w=(1.2, 2.2), flowers=200, persp=(600, H), grad_depth=160)
    draw_tree(c, tree_day(), 360, r_n[360] + 8, 0.40, T, sway=0.4)
    c.saveLayer()
    c.drawImage(gnd, 0, 0)
    draw_waves(c, wave_tex(W, 200, 13, WAVE_COL, 0.14), lf * 5 + 300, 600)
    c.restore()
    # tiny girl looking up at the sky
    fp = twos(f)
    g = girl()
    gx, gy, gs = 640, r_n[640] + 14, 0.2
    pose = g.pose_look_up(1.0, fp / FPS)
    draw_girl_at(c, gx, gy, gs, pose, wind=0.3, wind_dir=1, t=fp / FPS, hat_on=False)
    # the hat slides off and drifts down like a leaf
    off_f = TL.t2f(TL.EVENTS['hat_drift_down'][0])
    hx0, hy0 = wh.head_top
    if f < off_f:
        hx = wx + hx0 * ws + 4
        hy = wy + (hy0 + wh.offset_at(hx0, T)) * ws - 6
        draw_hat_at(c, hx, hy, 0.62 * ws / 0.92 * 0.92, T, -10, 0.15, 30, wind=0.4)
    else:
        k = (f - off_f) / (1152 - off_f)
        start_x = wx_at(off_f) + hx0 * ws + 4
        start_y = 70 - 0.12 * (off_f - 912) + (hy0) * ws - 6
        tx_, ty_ = gx + 30, gy - 150
        e = ease_in_out_sine(k)
        x = lerp(start_x, tx_, e) + 90 * math.sin(k * 9.0) * (1 - 0.6 * k)
        y = lerp(start_y, ty_, e) - 12 * abs(math.sin(k * 9.0))
        rot = 35 * math.cos(k * 9.0)
        sc = lerp(0.27, 0.32, k)
        draw_hat_at(c, x, y, sc, T, rot, 0.25 * math.sin(k * 9), (k * 300) % 360, wind=0.4)
    fg = cached('s7_fg', lambda: land.Blades(75, 260, -60, W + 60, lambda x: H + 14, (70, 170), (6, 12),
                                             land.GDAY['blade']))
    fg.draw(c, T, wind=0.4)


def wx_at(f):
    return 1250 - 4.4 * (f - 912)


# ============================================================ S8 the catch
CATCH_F = TL.t2f(TL.EVENTS['hat_catch'])
PUT_F = TL.t2f(TL.EVENTS['hat_put_on'])
WAVE_F0 = TL.t2f(TL.EVENTS['wave'][0])


def s8_pose(fp):
    g = girl()
    T = fp / FPS
    if fp < 1172:
        return g.pose_look_up(1.0, T), 0.0
    if fp < CATCH_F:
        return g.lerp_pose(g.pose_look_up(1.0, T), g.pose_catch(1.0), sstep(1172, CATCH_F - 2, fp)), 0.1
    if fp < PUT_F:
        k = sstep(CATCH_F + 2, PUT_F, fp)
        return g.lerp_pose(g.pose_catch(1.0), g.pose_hat_on(1.0), k), 0.4
    if fp < WAVE_F0:
        k = sstep(PUT_F, PUT_F + 14, fp)
        return g.lerp_pose(g.pose_hat_on(1.0), g.pose_stand(T), k), 0.8
    k = sstep(WAVE_F0, WAVE_F0 + 10, fp)
    return g.lerp_pose(g.pose_stand(T), g.pose_wave(T), k), 1.0


def s8_catch(c, f, t):
    T = f / FPS
    lf = f - 1152
    c.drawImage(sky_img(H, horizon=760, seed=12, mid=0.5), 0, 0)
    put(c, cloud(111, 1000, 620, height_frac=0.75, n_base=4, tower=0.6), 1500 + lf * 0.15, 660, 0.85)
    put(c, cloud(112, 700, 380, height_frac=0.5, n_base=3, tower=0.35), 300 + lf * 0.15, 640, 0.7)
    wh = whale_day()
    wh.draw(c, 1250 + lf * 1.2, 120 - lf * 0.2, 0.12, t=T, swim=1.0, eye_open=1.0, alpha=0.92)
    c.drawImage(distant_land('s8', W, H, 640, seed=81), 0, 0)
    xs = np.arange(W)
    r_n = 735 + 14 * np.sin(xs / 700.0) + land.ridge(W, 82, 0, 5, cell=260)
    gnd = ground_img('s8_near', W, H, r_n, GRASS_DAY, 83, strokes=6000, stroke_len=(8, 16),
                     stroke_w=(1.4, 2.6), flowers=160, persp=(700, H), grad_depth=120)
    c.saveLayer()
    c.drawImage(gnd, 0, 0)
    draw_waves(c, wave_tex(W, 120, 15, WAVE_COL, 0.14), lf * 5, 700)
    c.restore()
    draw_tree(c, tree_day(), -120, 1150, 1.1, T, sway=0.5)
    fp = twos(f)
    pose, smile = s8_pose(fp)
    g = girl()
    gx, gy, gs = 860, 952, 1.32
    hat_on = fp >= PUT_F
    draw_girl_at(c, gx, gy, gs, pose, wind=0.3, wind_dir=1, t=fp / FPS, hat_on=hat_on, smile=smile)
    if not hat_on:
        if f < CATCH_F:
            k = (f - 1152) / (CATCH_F - 1152)
            hp = local_to_world(gx, gy, gs, g.hand_position(g.pose_catch(1.0)))
            e = ease_out(k)
            x = lerp(1250, hp[0], e) + 120 * math.sin(k * 7.5) * (1 - k)
            y = lerp(-120, hp[1] - 12 * gs, e)
            rot = 30 * math.cos(k * 7.5) * (1 - k)
            draw_hat_at(c, x, y, gs, T, rot, 0.25 * (1 - k), 200 * k, wind=0.4)
        else:
            # from the hands up onto her head, ending exactly where draw_girl puts it
            k = sstep(CATCH_F + 2, PUT_F, fp)
            hp = local_to_world(gx, gy, gs, g.hand_position(pose))
            hx, hy, ha = g.head_top(pose)
            top = (gx + hx * gs, gy + (hy + 13) * gs)
            x = lerp(hp[0], top[0], k)
            y = lerp(hp[1] - 12 * gs, top[1], k)
            draw_hat_at(c, x, y, gs * lerp(1.0, 0.97, k), T, lerp(0.0, ha - 6, k), lerp(0.25, 0.12, k),
                        200, wind=0.3)
        if CATCH_F - 2 <= f <= CATCH_F + 16:
            rng = np.random.default_rng(5)
            hp = local_to_world(gx, gy, gs, g.hand_position(g.pose_catch(1.0)))
            for i in range(9):
                a = rng.uniform(0, 2 * math.pi)
                d = (f - CATCH_F + 2) * rng.uniform(4, 9)
                sparkle(c, hp[0] + math.cos(a) * d, hp[1] - 40 + math.sin(a) * d, rng.uniform(7, 13),
                        math.sin(math.pi * min(1, (f - CATCH_F + 2) / 18.0)))
    fg = cached('s8_fg', lambda: land.Blades(85, 200, -60, W + 60, lambda x: H + 16, (80, 180), (6, 12),
                                             land.GDAY['blade']))
    fg.draw(c, T, wind=0.35)


# ============================================================ S9 sunset & title
def whale_sunset():
    return cached('whale_sunset', lambda: Whale(L=900, pal=sky.SUNSET, seed=5))


def s9_sunset(c, f, t):
    T = f / FPS
    lf = f - 1296
    c.drawImage(sky_img(H, pal=sky.SUNSET, horizon=600, seed=13, mid=0.5), 0, 0)
    # sun + glow
    sx, sy = 1430, 548 + lf * 0.12
    g = skia.Paint(AntiAlias=True)
    g.setShader(skia.GradientShader.MakeRadial(skia.Point(sx, sy), 520,
                                               [skia.Color4f(1, 0.88, 0.6, 0.55).toColor(),
                                                skia.Color4f(1, 0.7, 0.45, 0.18).toColor(),
                                                skia.Color4f(1, 0.6, 0.4, 0.0).toColor()], [0, 0.35, 1]))
    c.drawCircle(sx, sy, 520, g)
    c.drawCircle(sx, sy, 46, paint_fill(skia.Color4f(1, 0.97, 0.85, 1)))
    # god rays
    rp = skia.Paint(AntiAlias=True)
    rp.setBlendMode(skia.BlendMode.kScreen)
    rng = np.random.default_rng(19)
    for i in range(9):
        ang = rng.uniform(-170, -10)
        spread = rng.uniform(1.5, 3.5)
        a = 0.05 + 0.03 * math.sin(T * 0.8 + i)
        rp.setColor4f(skia.Color4f(1, 0.85, 0.6, a))
        path = skia.Path()
        path.moveTo(sx, sy)
        for d in (ang - spread, ang + spread):
            path.lineTo(sx + 1600 * math.cos(math.radians(d)), sy + 1600 * math.sin(math.radians(d)))
        path.close()
        c.drawPath(path, rp)
    put(c, band(121, 1300, 120, pal=sky.SUNSET), 520 + lf * 0.12, 455, 1.0)
    put(c, band(122, 1500, 110, pal=sky.SUNSET), 1380 + lf * 0.15, 400, 1.0)
    put(c, band(123, 1000, 80, pal=sky.SUNSET), 300 + lf * 0.12, 300, 0.9, alpha=0.95)
    put(c, band(124, 900, 70, pal=sky.SUNSET), 1650 + lf * 0.15, 250, 0.8, alpha=0.9)
    ws = whale_sunset()
    ws.draw(c, 1130 + lf * 0.9, 300 - lf * 0.15, 0.3, t=T, swim=1.0, eye_open=1.0)
    # land silhouettes
    sland = cached('s9_land', lambda: _sunset_land())
    c.drawImage(sland[0], 0, 0)
    xs_r = sland[1]
    draw_tree(c, tree_sunset(), 760, xs_r[760] + 8, 0.62, T, sway=0.4)
    c.drawImage(sland[2], 0, 0)
    fp = twos(f)
    gg = girl()
    gx = 1000
    draw_girl_at(c, gx, xs_r[gx] + 40, 0.36, gg.pose_look_up(0.5, fp / FPS), wind=0.25, wind_dir=1,
                 t=fp / FPS, hat_on=True, smile=0.6, palette='sunset')
    fg = cached('s9_fg', lambda: land.Blades(95, 260, -60, W + 60, lambda x: H + 14, (60, 160), (6, 12),
                                             land.GSUNSET['blade']))
    fg.draw(c, T, wind=0.3)
    # title
    t0, t1 = TL.EVENTS['title_in']
    if T >= t0 - 0.05:
        try:
            from . import lettering
            prog = min(1.0, (T - t0) / (t1 - t0))
            lettering.draw_title(c, W / 2, 205, 104, progress=prog, alpha=1.0, glow=0.65)
        except Exception:
            pass


def _sunset_land():
    G_ = land.GSUNSET
    s = surface(W, H)
    c = s.getCanvas()
    r_m = land.ridge(W, 91, 600, 30, cell=420)
    c.drawImage(to_image(land.paint_ground(W, H, r_m, (G_['far_mtn'], G_['far_mtn'], G_['far_mtn_dark'], G_['far_mtn_dark']),
                                           92, patch=0.04, rim=0.15, haze=0.25, haze_col=G_['haze'])), 0, 0)
    r_f = land.ridge(W, 93, 640, 16, cell=300)
    c.drawImage(to_image(land.paint_ground(W, H, r_f, (G_['far_hill'], G_['far_hill'], G_['far_hill_dark'], G_['far_hill_dark']),
                                           94, patch=0.06, rim=0.25, haze=0.12, haze_col=G_['haze'])), 0, 0)
    back = s.makeImageSnapshot()
    s2 = surface(W, H)
    c2 = s2.getCanvas()
    xs = np.arange(W)
    r_n = 708 - 70 * np.exp(-((xs - 800) / 600.0) ** 2) + land.ridge(W, 95, 0, 5, cell=260)
    c2.drawImage(to_image(land.paint_ground(W, H, r_n, (G_['grass_lit'], G_['grass_mid'], G_['grass_shadow'], G_['grass_dark']),
                                            96, strokes=5000, stroke_len=(6, 12), stroke_w=(1.2, 2.2),
                                            grad_depth=90, rim=0.6, patch=0.05)), 0, 0)
    return back, r_n, s2.makeImageSnapshot()


# ============================================================ dispatch
SHOT_FUNCS = {
    's1_establish': s1_establish, 's2_run': s2_run, 's3_hilltop': s3_hilltop,
    's4_closeup': s4_closeup, 's5_hat_sky': s5_hat_sky, 's6_whale': s6_whale,
    's7_below': s7_below, 's8_catch': s8_catch, 's9_sunset': s9_sunset,
}


def shot_of(f):
    for name, a, b, _ in TL.SHOTS:
        if a <= f < b:
            return name, a, b
    return TL.SHOTS[-1][0], TL.SHOTS[-1][1], TL.SHOTS[-1][2]


def draw_frame(c, f):
    name, a, b = shot_of(f)
    SHOT_FUNCS[name](c, f, f / FPS)
