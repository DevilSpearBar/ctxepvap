"""Painted skies and cumulus clouds.

Clouds are heaps of spherical puffs rendered with a z-buffer: each pixel takes the
normal of the front-most puff, gets a stylised two-tone light ramp and a domain-
warped edge, which gives the bright-top / lavender-shadow look of anime skies.
"""

from dataclasses import dataclass

import numpy as np

from .core import fbm, rgbf, rgb_layer, smoothstep, value_noise

DAY = dict(
    sky_top=rgbf('1b55ad'), sky_mid=rgbf('3f86d6'), sky_hor=rgbf('cde7f2'),
    lit=rgbf('fffdf6'), mid=rgbf('e6ebf3'), shadow=rgbf('a5b4d6'), deep=rgbf('8796c0'),
    rim=rgbf('ffffff'),
    light=(-0.55, -0.72, 0.42),
)

SUNSET = dict(
    sky_top=rgbf('2a356f'), sky_mid=rgbf('b0668a'), sky_hor=rgbf('ffbf73'),
    lit=rgbf('ffe2a8'), mid=rgbf('f7a985'), shadow=rgbf('8a6290'), deep=rgbf('5e4a7c'),
    rim=rgbf('fff1c4'),
    light=(0.80, 0.05, 0.40),
)


def sky_gradient(w, h, pal, horizon_y, top_y=0.0, seed=1, mid_pos=0.55):
    """Vertical three-stop sky with a faint painterly breath of noise."""
    rng = np.random.default_rng(seed)
    y = np.arange(h, dtype=np.float32)[:, None]
    t = np.clip((y - top_y) / max(1.0, horizon_y - top_y), 0.0, 1.0)
    # top -> mid over [0, mid_pos], mid -> horizon over [mid_pos, 1] (eased toward the horizon)
    a = np.clip(t / mid_pos, 0, 1)[..., None]
    b = (np.clip((t - mid_pos) / (1 - mid_pos), 0, 1) ** 1.6)[..., None]
    col = (pal['sky_top'] * (1 - a) + pal['sky_mid'] * a)
    col = col * (1 - b) + pal['sky_hor'] * b
    col = np.broadcast_to(col, (h, w, 3)).copy()
    n = fbm(h, w, 220, rng, octaves=3)
    col *= (1.0 + 0.025 * n)[..., None]
    # slightly lighter toward the left (sun side) in daylight
    x = np.linspace(-1, 1, w, dtype=np.float32)[None, :, None]
    col += 0.02 * (-x) * (1 - t[..., None])
    return np.clip(col, 0, 1)


@dataclass
class Puff:
    x: float
    y: float
    z: float
    r: float


def _boundary_points(puffs, step_frac, rng, min_up=-0.25):
    """Points on the outer boundary of a union of puffs (upper/side part only)."""
    pts = []
    arr = np.array([(p.x, p.y, p.r) for p in puffs], np.float32)
    for p in puffs:
        n = max(6, int(2 * np.pi * p.r / (step_frac * p.r + 1e-6)))
        ang = np.linspace(0, 2 * np.pi, n, endpoint=False) + rng.uniform(0, 2 * np.pi)
        bx = p.x + np.cos(ang) * p.r
        by = p.y + np.sin(ang) * p.r
        for x, y, a in zip(bx, by, ang):
            if -np.sin(a) < min_up:          # skip the downward-facing part
                continue
            d = np.hypot(arr[:, 0] - x, arr[:, 1] - y) - arr[:, 2]
            if np.all(d > -0.5):
                pts.append((x, y, p))
    return pts


def gen_cumulus(seed, w, h, base_y, height, n_base=4, spread=0.92, tower=0.6,
                levels=(0.42, 0.22), interior=40, flat=True):
    """Generate puffs for a cumulus heap inside a w x h sprite.

    base_y: y of the flat base; height: approximate tower height above the base.
    """
    rng = np.random.default_rng(seed)
    puffs = []
    cx = w * 0.5
    half = w * spread * 0.5
    # base row
    xs = np.linspace(cx - half * 0.78, cx + half * 0.78, n_base) + rng.uniform(-0.05, 0.05, n_base) * w
    for x in xs:
        prof = np.exp(-((x - cx) / (half * 0.9)) ** 2)
        r = (0.085 + 0.115 * prof) * w * rng.uniform(0.85, 1.1)
        r = min(r, height * 0.55)
        puffs.append(Puff(x, base_y - r * 0.62, r * rng.uniform(0.3, 0.9), r))
    # tower: stack lobes upward following a bell profile
    top_target = lambda x: base_y - height * (np.exp(-((x - cx) / (half * (0.45 + 0.3 * (1 - tower)))) ** 2) * 0.85 + 0.15)
    for _ in range(40):
        cand = [p for p in puffs if p.y - p.r > top_target(p.x) + p.r * 0.35]
        if not cand:
            break
        par = cand[rng.integers(len(cand))]
        r = par.r * rng.uniform(0.62, 0.85)
        ang = np.deg2rad(rng.uniform(-50, 50) - 90)
        d = (par.r + r) * 0.55
        nx, ny = par.x + np.cos(ang) * d, par.y + np.sin(ang) * d
        if abs(nx - cx) > half:
            continue
        puffs.append(Puff(nx, ny, par.z + rng.uniform(-0.45, 0.25) * r, r))
    # cauliflower boundary detail
    for lvl, frac in enumerate(levels):
        parents = list(puffs)
        pts = _boundary_points(parents, 1.0, rng)
        rng.shuffle(pts)
        chosen = []
        for (x, y, par) in pts:
            r = par.r * frac * rng.uniform(0.7, 1.25)
            if y > base_y - r * 0.6:
                continue
            if any(np.hypot(x - c[0], y - c[1]) < (r + c[2]) * 0.62 for c in chosen):
                continue
            chosen.append((x, y, r))
            inward = 0.35 if lvl == 0 else 0.5
            # pull the centre slightly inside so the bump grows out of its parent
            dx, dy = x - par.x, y - par.y
            L = np.hypot(dx, dy) + 1e-6
            puffs.append(Puff(x - dx / L * r * inward, y - dy / L * r * inward,
                              par.z + r * rng.uniform(0.2, 0.5), r))
    # interior billows protruding from the face of big puffs
    big = [p for p in puffs if p.r > w * 0.06]
    for _ in range(interior if big else 0):
        par = big[rng.integers(len(big))]
        a = rng.uniform(0, 2 * np.pi)
        rr = par.r * np.sqrt(rng.uniform(0.0, 0.7))
        x, y = par.x + np.cos(a) * rr, par.y + np.sin(a) * rr * 0.8
        if y > base_y - 10:
            continue
        r = par.r * rng.uniform(0.25, 0.45)
        surf = par.z + np.sqrt(max(par.r ** 2 - rr ** 2, 0))
        puffs.append(Puff(x, y, surf - r * rng.uniform(0.55, 0.8), r))
    return puffs


def render_puffs(puffs, w, h, pal, seed=0, base_y=None, base_soft=10.0, warp=7.0,
                 warp_cell=46.0, edge=1.3, light=None, shade_noise=0.10, bottom_dark=0.6,
                 extra_alpha=None, rim=0.3, tint=None, local_w=0.34, form_sigma=None,
                 return_fields=False, shade_cell=34.0, cut_base=True, tex_amp=1.0):
    """Z-buffered puff shading -> premultiplied RGBA float32 (h, w, 4).

    Lighting mixes each puff's own sphere normal (billows) with the normal of a
    blurred height field (the big form), so light and shadow read as large masses.
    """
    rng = np.random.default_rng(seed + 977)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    wx = fbm(h, w, warp_cell, rng, octaves=4) * warp
    wy = fbm(h, w, warp_cell, rng, octaves=4) * warp
    X = xx + wx
    Y = yy + wy
    zb = np.full((h, w), -1e9, np.float32)
    nx = np.zeros((h, w), np.float32)
    ny = np.zeros((h, w), np.float32)
    nz = np.ones((h, w), np.float32)
    sdf = np.full((h, w), 1e9, np.float32)
    pad = warp * 1.6 + 3
    for p in puffs:
        x0, x1 = max(0, int(p.x - p.r - pad)), min(w, int(p.x + p.r + pad) + 1)
        y0, y1 = max(0, int(p.y - p.r - pad)), min(h, int(p.y + p.r + pad) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        sl = (slice(y0, y1), slice(x0, x1))
        dx = (X[sl] - p.x) / p.r
        dy = (Y[sl] - p.y) / p.r
        d2 = dx * dx + dy * dy
        np.minimum(sdf[sl], (np.sqrt(d2) - 1.0) * p.r, out=sdf[sl])
        inside = d2 < 1.0
        hz = np.sqrt(np.maximum(1.0 - d2, 0.0))
        z = hz * p.r + p.z
        upd = inside & (z > zb[sl])
        zb[sl][upd] = z[upd]
        nx[sl][upd] = dx[upd]
        ny[sl][upd] = dy[upd]
        nz[sl][upd] = hz[upd]
    # big-form normal from a blurred height field
    hf = np.where(zb > -1e8, zb, 0.0).astype(np.float32)
    rmax = max(p.r for p in puffs)
    sig = form_sigma if form_sigma is not None else max(6.0, rmax * 0.35)
    from scipy import ndimage
    small = 4 if sig > 12 else 1
    hs = ndimage.gaussian_filter(hf[::small, ::small], sig / small)
    gy, gx = np.gradient(hs)
    gx /= small
    gy /= small
    if small > 1:
        gx = ndimage.zoom(gx, small, order=1)[:h, :w]
        gy = ndimage.zoom(gy, small, order=1)[:h, :w]
        gx = np.pad(gx, ((0, h - gx.shape[0]), (0, w - gx.shape[1])), mode='edge')
        gy = np.pad(gy, ((0, h - gy.shape[0]), (0, w - gy.shape[1])), mode='edge')
    bnx, bny, bnz = -gx * 2.6, -gy * 2.6, np.ones_like(gx)
    bl = np.sqrt(bnx ** 2 + bny ** 2 + bnz ** 2)
    bnx, bny, bnz = bnx / bl, bny / bl, bnz / bl
    # pixels in the soft fringe outside every puff borrow the big-form normal
    outside = zb < -1e8
    nx = np.where(outside, bnx, nx)
    ny = np.where(outside, bny, ny)
    nz = np.where(outside, bnz, nz)
    mx = local_w * nx + (1 - local_w) * bnx
    my = local_w * ny + (1 - local_w) * bny
    mz = local_w * nz + (1 - local_w) * bnz
    ml = np.sqrt(mx * mx + my * my + mz * mz) + 1e-6
    mx, my, mz = mx / ml, my / ml, mz / ml
    L = np.array(light if light is not None else pal['light'], np.float32)
    L /= np.linalg.norm(L)
    diff = mx * L[0] + my * L[1] + mz * L[2]
    diff += shade_noise * fbm(h, w, shade_cell, rng, octaves=3)
    t1 = smoothstep(-0.12, 0.20, diff)        # shadow -> mid
    t2 = smoothstep(0.30, 0.60, diff)         # mid -> lit
    col = pal['shadow'][None, None] * (1 - t1[..., None]) + pal['mid'][None, None] * t1[..., None]
    col = col * (1 - t2[..., None]) + pal['lit'][None, None] * t2[..., None]
    # denser, darker underside
    if base_y is not None:
        top = float(np.min([p.y - p.r for p in puffs]))
        v = smoothstep(top + (base_y - top) * 0.35, base_y + 2, Y) ** 1.2
        v = v * (1 - 0.45 * t2)
        col = col * (1 - bottom_dark * v[..., None]) + pal['deep'][None, None] * (bottom_dark * v[..., None])
    # bright rim where the silhouette faces the light
    edge_band = smoothstep(10.0, 0.0, -sdf) * np.clip(diff + 0.1, 0, 1) * smoothstep(-0.1, 0.45, -bny)
    col = col + (pal['rim'][None, None] - col) * (rim * edge_band[..., None])
    # soft brush mottling, stronger in shadow
    tex = fbm(h, w, 16, rng, octaves=2)
    col *= (1.0 + tex_amp * (0.005 + 0.022 * (1 - t2)) * tex)[..., None]
    if tint is not None:
        col *= tint
    edge_w = edge + 5.0 * np.clip(bny, 0, 1)    # crisp tops, softer undersides
    alpha = np.clip(0.5 - sdf / edge_w, 0.0, 1.0)
    alpha *= 0.88 + 0.12 * smoothstep(0.0, 5.0, -sdf)
    if base_y is not None and cut_base:
        wob = value_noise(h, w, 60, rng) * base_soft * 0.6
        alpha *= smoothstep(base_y + base_soft, base_y - base_soft, Y + wob)
    if extra_alpha is not None:
        alpha *= extra_alpha
    out = rgb_layer(np.clip(col, 0, 1), alpha)
    if return_fields:
        return out, dict(sdf=sdf, diff=diff, X=X, Y=Y)
    return out


@dataclass
class Sprite:
    rgba: np.ndarray      # premultiplied RGBA float32
    ax: float             # anchor (cloud base centre) in sprite pixels
    ay: float


def fit_puffs(puffs, pad):
    """Shift puffs so that they fit a tight sprite; returns (w, h, dx, dy)."""
    x0 = min(p.x - p.r for p in puffs) - pad
    y0 = min(p.y - p.r for p in puffs) - pad
    x1 = max(p.x + p.r for p in puffs) + pad
    y1 = max(p.y + p.r for p in puffs) + pad
    for p in puffs:
        p.x -= x0
        p.y -= y0
    return int(np.ceil(x1 - x0)), int(np.ceil(y1 - y0)), -x0, -y0


def make_cumulus(seed, w, h, pal=DAY, height_frac=0.75, n_base=4, tower=0.6,
                 interior=8, levels=(0.4, 0.2), warp=7.0, base_soft=10.0, **kw):
    """Cumulus roughly w wide and h*height_frac tall -> Sprite (anchor = base centre)."""
    base_y = h * 0.9
    puffs = gen_cumulus(seed, w, h, base_y, h * height_frac, n_base=n_base, tower=tower,
                        interior=interior, levels=levels)
    sw, sh, dx, dy = fit_puffs(puffs, warp * 2 + 4)
    base = base_y + dy
    sh = int(min(sh, base + base_soft * 2 + 4))
    rgba = render_puffs(puffs, sw, sh, pal, seed=seed, base_y=base, warp=warp,
                        base_soft=base_soft, **kw)
    return Sprite(rgba, w * 0.5 + dx, base)


def make_stratus(seed, w, h, pal=DAY, n=26, thickness=0.35, **kw):
    """A long, low cloud bank made of overlapping puffs -> Sprite."""
    rng = np.random.default_rng(seed)
    base_y = h * 0.78
    puffs = []
    for i in range(n):
        x = w * (0.06 + 0.88 * i / max(1, n - 1)) + rng.uniform(-0.02, 0.02) * w
        prof = np.sin(np.pi * (x / w)) ** 0.7
        r = h * thickness * rng.uniform(0.6, 1.0) * (0.45 + 0.55 * prof)
        puffs.append(Puff(x, base_y - r * 0.55, r * 0.4, r))
    for _ in range(n):
        par = puffs[rng.integers(len(puffs))]
        a = np.deg2rad(rng.uniform(-160, -20))
        r = par.r * rng.uniform(0.35, 0.6)
        puffs.append(Puff(par.x + np.cos(a) * par.r * 0.8, par.y + np.sin(a) * par.r * 0.8,
                          par.z + r * 0.3, r))
    warp = kw.pop('warp', 7.0)
    base_soft = kw.pop('base_soft', 10.0)
    sw, sh, dx, dy = fit_puffs(puffs, warp * 2 + 4)
    base = base_y + dy
    sh = int(min(sh, base + base_soft * 2 + 4))
    rgba = render_puffs(puffs, sw, sh, pal, seed=seed, base_y=base, warp=warp,
                        base_soft=base_soft, **kw)
    return Sprite(rgba, w * 0.5 + dx, base)


def blit_sprite(canvas, spr_img, spr, x, y, scale=1.0, alpha=1.0):
    """Draw a cloud Sprite (already converted to skia.Image) with its anchor at (x, y)."""
    from .core import draw_image
    draw_image(canvas, spr_img, x - spr.ax * scale, y - spr.ay * scale, scale=scale, alpha=alpha)
