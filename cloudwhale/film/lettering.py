"""Hand-lettered brush title «Облачный кит» — every pixel drawn from code.

No fonts, no text APIs, no images.  Each glyph below is a set of stroke
skeletons designed by hand: control points of a centripetal Catmull-Rom centre
line (glyph units: baseline y=0, x-height 1, y up) with a pressure value per
point.  A stroke is painted as the sweep of an elliptical brush footprint held
at NIB_ANGLE_DEG (thick downstrokes, hairline upstrokes), swollen by pressure,
tapered at both ends, with a seeded edge wobble so it reads as hand-painted.

Rendering: the swept outline (vector, anti-aliased by skia) is rasterised once
per device size into a coverage map plus an "arrival time" map (when the brush
reaches each pixel).  A frame at any `progress` is then cheap numpy masking —
the reveal follows the real writing order with a soft round brush head.

Public API: draw_title(canvas, cx, cy, height, progress, color, alpha, glow).
"""
import math

import numpy as np
import skia
from scipy.ndimage import gaussian_filter, gaussian_filter1d, minimum_filter

# ----------------------------------------------------------------- knobs
TEXT = "Облачный кит"
NIB_ANGLE_DEG = 32.0   # brush held at this angle (deg, CCW from the baseline)
SLANT_DEG = 9.0        # italic lean of the letterforms
WIDTH = 1.06           # horizontal stretch of every glyph (and its advance)
TRACKING = 0.0         # extra space between letters (x-height units)
WORD_SPACE = 0.55      # extra space between words (x-height units)
BRUSH = 0.11           # nib half-length at full pressure (x-height units)
NIB_RATIO = 0.28       # thin/thick ratio of the nib ellipse
HAIRLINE = 0.021       # minimum half-width of a hairline (x-height units)
UPSTROKE = 0.42        # share of pressure kept on a pure upstroke
EDGE_WOBBLE = 0.04     # seeded edge irregularity (fraction of half-width)
SEED = 11

# reveal timing (abstract time units, normalised so progress 0..1 spans it)
SPEED = 1.0            # x-height units of stroke per time unit
LIFT = 0.55            # extra time per stroke (approach / press / lift)
OVERLAP = 0.2          # next stroke starts when this share of the previous remains
WORD_PAUSE = 0.15      # breath between the words
EASE = 0.5             # 0 = constant brush speed, 1 = full ease-in-out per stroke
HEAD_SOFT_PX = 2.5     # softness of the growing brush head (device px)

# halo
GLOW_RGB = (255, 236, 206)
GLOW_SIGMA = 0.075     # x title height
GLOW_GAIN = 2.2
GLOW_OPACITY = 0.75    # multiplied by `glow`
SHADOW_RGB = (92, 38, 62)
SHADOW_SIGMA = 0.03
SHADOW_OFFSET = 0.018  # x title height, downwards
SHADOW_OPACITY = 0.3   # multiplied by `glow`

_ELLIPSE_N = 20


def _S(*pts, taper_in=0.07, taper_out=0.11, e_in=0.35, e_out=0.12):
    return dict(pts=pts, taper_in=taper_in, taper_out=taper_out, e_in=e_in, e_out=e_out)


C = "c"  # corner flag: the brush turns sharply at this control point

# Glyph skeletons, upright (slant is applied at layout).
# Point = (x, y, pressure) or (x, y, p_in, C, p_out) for a sharp turn where the
# brush arrives with p_in and leaves with p_out (thin hairline in, pressed stem out).
# entry: stroke that receives the joining hairline from the previous letter.
# exit:  stroke whose tail flows into the next letter.
_U_BODY = (  # и / й: stem, round bottom, hairline up, second stem, exit flick
    (0.06, 1.00, 0.30, C, 0.88), (0.05, 0.55, 1.00), (0.07, 0.16, 0.95), (0.18, 0.00, 0.65),
    (0.36, 0.05, 0.40), (0.52, 0.40, 0.30), (0.60, 1.00, 0.30, C, 0.88), (0.59, 0.50, 1.00),
    (0.58, 0.08, 0.95), (0.64, -0.01, 0.60), (0.74, 0.05, 0.35), (0.84, 0.18, 0.20))

_GLYPHS = {
    "О": dict(adv=1.16, strokes=[_S(
        (0.827, 1.364, 0.30), (0.627, 1.489, 0.45), (0.411, 1.474, 0.60), (0.186, 1.280, 0.85),
        (0.057, 0.944, 1.00), (0.057, 0.556, 1.00), (0.175, 0.212, 0.95), (0.411, 0.026, 0.80),
        (0.669, 0.026, 0.65), (0.905, 0.212, 0.55), (1.023, 0.556, 0.50), (1.023, 0.944, 0.45),
        (0.894, 1.280, 0.40), (0.711, 1.455, 0.32), (0.459, 1.437, 0.20))]),
    "б": dict(adv=0.74, strokes=[_S(
        (0.80, 1.52, 0.85), (0.68, 1.45, 0.55), (0.50, 1.49, 0.60), (0.30, 1.42, 0.75),
        (0.13, 1.12, 0.95), (0.05, 0.72, 1.00), (0.09, 0.24, 0.95), (0.30, -0.01, 0.80),
        (0.56, 0.12, 0.60), (0.64, 0.46, 0.50), (0.53, 0.82, 0.45), (0.31, 0.93, 0.40),
        (0.13, 0.81, 0.32), (0.07, 0.64, 0.22), e_in=0.85)]),
    "л": dict(adv=0.96, exit=0, strokes=[_S(
        (0.04, 0.10, 0.85), (0.10, 0.03, 0.50), (0.20, 0.12, 0.35), (0.32, 0.45, 0.32),
        (0.43, 0.82, 0.32), (0.52, 1.00, 0.32, C, 0.88), (0.53, 0.50, 1.00), (0.52, 0.08, 0.95),
        (0.58, -0.01, 0.60), (0.68, 0.05, 0.35), (0.74, 0.14, 0.20), e_in=0.9)]),
    "а": dict(adv=1.04, exit=0, strokes=[_S(
        (0.54, 0.86, 0.45), (0.40, 0.99, 0.50), (0.18, 0.92, 0.75), (0.05, 0.55, 1.00),
        (0.10, 0.14, 0.90), (0.28, -0.01, 0.70), (0.47, 0.10, 0.45), (0.57, 0.42, 0.35),
        (0.61, 0.80, 0.32), (0.62, 1.00, 0.32, C, 0.88), (0.61, 0.50, 1.00), (0.60, 0.08, 0.95),
        (0.66, -0.01, 0.60), (0.76, 0.05, 0.35), (0.86, 0.18, 0.20), e_in=0.6)]),
    "ч": dict(adv=1.04, entry=0, exit=0, strokes=[_S(
        (0.06, 1.00, 0.30, C, 0.88), (0.05, 0.76, 1.00), (0.10, 0.52, 0.85), (0.26, 0.42, 0.55),
        (0.46, 0.46, 0.40), (0.56, 0.66, 0.32), (0.60, 1.00, 0.30, C, 0.88), (0.59, 0.50, 1.00),
        (0.58, 0.08, 0.95), (0.64, -0.01, 0.60), (0.74, 0.05, 0.35), (0.84, 0.18, 0.20))]),
    "н": dict(adv=1.04, entry=0, exit=1, strokes=[
        _S((0.06, 1.00, 0.30, C, 0.88), (0.05, 0.50, 1.00), (0.04, 0.04, 0.90), e_out=0.35),
        _S((0.07, 0.50, 0.60), (0.30, 0.53, 0.90), (0.50, 0.57, 0.80), (0.58, 0.72, 0.40),
           (0.61, 1.00, 0.30, C, 0.88), (0.60, 0.50, 1.00), (0.59, 0.08, 0.95),
           (0.65, -0.01, 0.60), (0.75, 0.05, 0.35), (0.85, 0.18, 0.20), e_in=0.6)]),
    "ы": dict(adv=1.24, entry=0, exit=1, strokes=[
        _S((0.06, 1.00, 0.30, C, 0.88), (0.05, 0.50, 1.00), (0.05, 0.12, 0.95), (0.13, 0.00, 0.75),
           (0.32, -0.01, 0.60), (0.48, 0.14, 0.50), (0.46, 0.42, 0.45), (0.30, 0.54, 0.40),
           (0.12, 0.48, 0.30), (0.07, 0.40, 0.20)),
        _S((0.80, 1.00, 0.85), (0.79, 0.50, 1.00), (0.78, 0.08, 0.95), (0.84, -0.01, 0.60),
           (0.94, 0.05, 0.35), (1.04, 0.18, 0.20), e_in=0.6)]),
    "й": dict(adv=0.86, entry=0, exit=0, strokes=[
        _S(*_U_BODY),
        _S((0.16, 1.36, 0.40), (0.24, 1.24, 0.75), (0.36, 1.19, 0.80), (0.48, 1.25, 0.55),
           (0.55, 1.36, 0.30))]),
    "к": dict(adv=0.98, entry=0, exit=1, strokes=[
        _S((0.06, 1.00, 0.85), (0.05, 0.50, 1.00), (0.04, 0.04, 0.90), e_in=0.6, e_out=0.35),
        _S((0.58, 0.98, 0.70), (0.44, 0.82, 0.50), (0.26, 0.62, 0.45), (0.12, 0.50, 0.40, C, 0.50),
           (0.28, 0.40, 0.85), (0.44, 0.20, 1.00), (0.52, 0.06, 0.95), (0.60, -0.01, 0.60),
           (0.70, 0.05, 0.35), (0.80, 0.18, 0.20), e_in=0.7)]),
    "и": dict(adv=0.92, entry=0, exit=0, strokes=[_S(*_U_BODY)]),
    "т": dict(adv=0.80, strokes=[
        _S((0.00, 0.95, 0.60), (0.14, 1.01, 1.20), (0.36, 1.02, 1.40), (0.58, 1.00, 1.30),
           (0.72, 1.04, 0.60), e_in=0.6, taper_out=0.08),
        _S((0.36, 1.00, 0.85), (0.35, 0.50, 1.00), (0.34, 0.10, 0.95), (0.42, -0.01, 0.60),
           (0.58, 0.03, 0.40), (0.72, 0.16, 0.25), (0.80, 0.32, 0.15), e_in=0.6)]),
}


# ----------------------------------------------------------------- layout
def _layout():
    """Place glyphs, apply slant + per-letter liveliness, merge joined strokes.

    Returns a list of strokes in writing order: dict(ctrl=(n,4) array [x,y,p,corner],
    word=int, taper params).
    """
    rng = np.random.default_rng(SEED)
    tan_s = math.tan(math.radians(SLANT_DEG))
    strokes = []
    x0 = 0.0
    for wi, word in enumerate(TEXT.split(" ")):
        pending = None
        for ci, ch in enumerate(word):
            g = _GLYPHS[ch]
            dy = rng.uniform(-0.018, 0.018)
            rot = math.radians(rng.uniform(-1.2, 1.2))
            cr, sr = math.cos(rot), math.sin(rot)

            def tf(pt, x0=x0, dy=dy, cr=cr, sr=sr):
                x, y = pt[0] * WIDTH - 0.35, pt[1] - 0.5
                x, y = x * cr - y * sr + 0.35, x * sr + y * cr + 0.5 + dy
                corner = len(pt) > 3 and pt[3] == C
                return [x + y * tan_s + x0, y, pt[2], 1.0 if corner else 0.0,
                        pt[4] if corner else pt[2]]

            nxt = word[ci + 1] if ci + 1 < len(word) else None
            joins_in = pending is not None and g.get("entry") is not None
            exit_idx = None
            for si, st in enumerate(g["strokes"]):
                pts = [tf(p) for p in st["pts"]]
                if si == g.get("entry") and joins_in:
                    strokes[pending]["ctrl"].extend(pts)
                    strokes[pending]["taper_out"] = st["taper_out"]
                    strokes[pending]["e_out"] = st["e_out"]
                    idx = pending
                else:
                    if pts[0][3]:  # nothing joins in: start directly with the pressed stem
                        pts[0][3] = 0.0
                        pts[0][2] = pts[0][4]
                    strokes.append(dict(ctrl=pts, word=wi, taper_in=st["taper_in"],
                                        taper_out=st["taper_out"], e_in=st["e_in"],
                                        e_out=st["e_out"]))
                    idx = len(strokes) - 1
                if si == g.get("exit"):
                    exit_idx = idx
            joinable = nxt is not None and _GLYPHS[nxt].get("entry") is not None
            pending = exit_idx if (joinable and exit_idx is not None) else None
            x0 += g["adv"] * WIDTH + TRACKING
        x0 += WORD_SPACE
    for s in strokes:
        s["ctrl"] = np.array(s["ctrl"], float)
    return strokes


# ----------------------------------------------------------------- geometry
def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _catmull_rom(P, pr, step):
    """Centripetal Catmull-Rom through P (m,2) with pressure pr (m,). Dense output."""
    m = len(P)
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    xs, ps = [], []
    for i in range(m - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        t1 = max(np.linalg.norm(p1 - p0), 1e-9) ** 0.5
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-9) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-9) ** 0.5
        n = max(3, int(math.ceil(np.linalg.norm(p2 - p1) / step)))
        t = np.linspace(t1, t2, n, endpoint=False)[:, None]
        a1 = (t1 - t) / t1 * p0 + t / t1 * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / t2 * a1 + t / t2 * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        c = (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2
        xs.append(c)
        ps.append(pr[i] + (pr[i + 1] - pr[i]) * _smoothstep((t[:, 0] - t1) / (t2 - t1)))
    xs.append(P[-1:])
    ps.append(pr[-1:])
    return np.vstack(xs), np.concatenate(ps)


def _resample(xy, pr, ds):
    seg = np.hypot(*np.diff(xy, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = s[-1]
    n = max(2, int(math.ceil(L / ds)) + 1)
    si = np.linspace(0.0, L, n)
    return np.stack([np.interp(si, s, xy[:, 0]), np.interp(si, s, xy[:, 1])], 1), np.interp(si, s, pr), si


def _noise(s, rng, step=0.07):
    knots = rng.uniform(-1.0, 1.0, int(s[-1] / step) + 3)
    f = s / step
    i = np.floor(f).astype(int)
    w = _smoothstep(f - i)
    return knots[i] * (1 - w) + knots[i + 1] * w


def _ease(u):
    return (1 - EASE) * u + EASE * _smoothstep(u)


class _Piece:
    """One corner-free run of a stroke, sampled uniformly in arc length."""
    pass


def _build_strokes(ds):
    """Sample all strokes at spacing ds (x-height units) and compute footprints."""
    strokes = _layout()
    th = math.radians(NIB_ANGLE_DEG)
    u = np.array([math.cos(th), math.sin(th)])
    v = np.array([-math.sin(th), math.cos(th)])
    out = []
    for k, st in enumerate(strokes):
        ctrl = st["ctrl"]
        rng = np.random.default_rng(SEED * 1000 + k)
        cuts = [0] + [i for i in range(1, len(ctrl) - 1) if ctrl[i, 3]] + [len(ctrl) - 1]
        pieces = []
        s_off = 0.0
        for a, b in zip(cuts[:-1], cuts[1:]):
            prs = ctrl[a:b + 1, 2].copy()
            prs[0] = ctrl[a, 4]
            xy, pr = _catmull_rom(ctrl[a:b + 1, :2], prs, ds * 0.25)
            xy, pr, s = _resample(xy, pr, ds)
            pc = _Piece()
            pc.xy, pc.pr, pc.s = xy, pr, s + s_off
            s_off += s[-1]
            pieces.append(pc)
        L = s_off
        nl_all = _noise(np.linspace(0, L, 2), rng)  # advance rng deterministically
        del nl_all
        for pc in pieces:
            xy, s = pc.xy, pc.s
            tg = np.gradient(xy, axis=0)
            tg /= np.maximum(np.hypot(tg[:, 0], tg[:, 1]), 1e-12)[:, None]
            down = -tg[:, 1]
            D = UPSTROKE + (1 - UPSTROKE) * np.clip((1 + down) / 2, 0, 1) ** 1.2
            sig = max(0.02 / ds, 0.5)
            D = gaussian_filter1d(D, sig, mode="nearest")
            P = gaussian_filter1d(pc.pr, max(0.03 / ds, 0.5), mode="nearest")
            ein = st["e_in"] + (1 - st["e_in"]) * np.sin(0.5 * np.pi * np.clip(s / st["taper_in"], 0, 1))
            eout = st["e_out"] + (1 - st["e_out"]) * np.sin(0.5 * np.pi * np.clip((L - s) / st["taper_out"], 0, 1))
            E = np.minimum(ein, eout)
            a = BRUSH * P * D * E
            b = np.maximum(HAIRLINE * np.sqrt(E), NIB_RATIO * a)
            a = np.maximum(a, b)
            n = np.stack([-tg[:, 1], tg[:, 0]], 1)
            nu = n @ u
            nv = n @ v
            h = np.sqrt(a * a * nu * nu + b * b * nv * nv)
            S = (np.outer(a * a * nu, u) + np.outer(b * b * nv, v)) / h[:, None]
            pc.a, pc.b, pc.tg = a, b, tg
            pc.Sl, pc.Sr = S, S
            out_piece_noise = None
            del out_piece_noise
        # seeded edge wobble, continuous along the whole stroke
        sall = np.concatenate([pc.s for pc in pieces])
        nl = _noise(sall, rng) * EDGE_WOBBLE
        nr = _noise(sall, rng) * EDGE_WOBBLE
        i0 = 0
        for pc in pieces:
            m = len(pc.s)
            pc.L = pc.xy + pc.Sl * (1 + nl[i0:i0 + m, None])
            pc.R = pc.xy - pc.Sr * (1 + nr[i0:i0 + m, None])
            i0 += m
        out.append(dict(pieces=pieces, length=L, word=st["word"], ctrl=ctrl))
    return out, u, v


def _timeline(strokes):
    """Start/duration of each stroke in normalised time (0..1)."""
    t = 0.0
    starts, durs = [], []
    for k, st in enumerate(strokes):
        d = (st["length"] + LIFT) / SPEED
        if k > 0:
            prev_end = starts[-1] + durs[-1]
            if st["word"] != strokes[k - 1]["word"]:
                t = prev_end + WORD_PAUSE
            else:
                t = prev_end - OVERLAP * min(durs[-1], d)
            t = max(t, starts[-1] + 0.05)
        starts.append(t)
        durs.append(d)
    total = max(s + d for s, d in zip(starts, durs))
    return np.array(starts) / total, np.array(durs) / total


_UTAB = np.linspace(0.0, 1.0, 513)
_ETAB = _ease(_UTAB)


def _arrival(st, start, dur):
    """Normalised time at which the brush head reaches each sample of a stroke."""
    out = []
    for pc in st["pieces"]:
        frac = pc.s / max(st["length"], 1e-9)
        out.append(start + dur * np.interp(frac, _ETAB, _UTAB))
    return out


# ----------------------------------------------------------------- raster maps
_HDR_WINDING = 5


def _path_from_polys(polys):
    """polys: (n, k, 2) float array of closed polygons -> skia.Path (non-zero winding)."""
    n, k, _ = polys.shape
    verbs = np.empty((n, k + 1), np.uint8)
    verbs[:, 0] = 0
    verbs[:, 1:k] = 1
    verbs[:, k] = 5
    blob = (np.array([_HDR_WINDING, n * k, 0, n * (k + 1)], np.int32).tobytes()
            + polys.astype(np.float32).tobytes() + verbs.tobytes())
    blob += b"\0" * ((-len(blob)) % 4)
    path = skia.Path()
    path.readFromMemory(blob)
    return path


def _orient(polys):
    """Make every polygon counter-clockwise so overlapping pieces only ever add."""
    x, y = polys[..., 0], polys[..., 1]
    area = (x * np.roll(y, -1, 1) - np.roll(x, -1, 1) * y).sum(1)
    polys[area < 0] = polys[area < 0, ::-1]
    return polys


def _ellipses(xy, a, b, u, v, n=_ELLIPSE_N):
    ph = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return (xy[:, None, :] + (a[:, None] * np.cos(ph))[..., None] * u
            + (b[:, None] * np.sin(ph))[..., None] * v)


class _Render:
    pass


def _build_render(dev_height):
    """Coverage + arrival-time maps for the whole title at a device size."""
    # unit geometry at a reference resolution decides the scale (О ink height)
    scale = dev_height / _o_height_units()
    ds = 0.6 / scale
    strokes, u, v = _build_strokes(ds)
    starts, durs = _timeline(strokes)
    # bbox in units
    allp = []
    for st in strokes:
        for pc in st["pieces"]:
            allp += [pc.L, pc.R, pc.xy - pc.a[:, None], pc.xy + pc.a[:, None]]
    allp = np.vstack(allp)
    lo, hi = allp.min(0), allp.max(0)
    cu = (lo + hi) / 2
    margin = int(math.ceil(dev_height * (GLOW_SIGMA * 3.2 + SHADOW_OFFSET) + 6))
    wpx = (hi[0] - lo[0]) * scale + 2 * margin
    hpx = (hi[1] - lo[1]) * scale + 2 * margin
    W = int(math.ceil(wpx / 4)) * 4
    H = int(math.ceil(hpx / 4)) * 4
    ox, oy = W // 2, H // 2

    def px(p):
        return np.stack([ox + (p[..., 0] - cu[0]) * scale, oy - (p[..., 1] - cu[1]) * scale], -1)

    # ---- coverage (AA union of every footprint sweep)
    polys = []
    tri_all = []
    ell_all = []
    for st in strokes:
        for pc in st["pieces"]:
            Lp, Rp = px(pc.L), px(pc.R)
            q1 = np.stack([Lp[:-1], Lp[1:], Rp[1:]], 1)
            q2 = np.stack([Lp[:-1], Rp[1:], Rp[:-1]], 1)
            tri_all += [q1, q2]
            # caps / corners: footprint ellipses at the run ends
            ends = np.array([0, len(pc.s) - 1])
            e = _ellipses(pc.xy[ends], pc.a[ends], pc.b[ends], u, v)
            ell_all.append(px(e))
    tri = _orient(np.concatenate(tri_all))
    ell = _orient(np.concatenate(ell_all))
    path = _path_from_polys(tri)
    path.addPath(_path_from_polys(ell))
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kAlpha_8_ColorType, skia.kPremul_AlphaType))
    cv = surf.getCanvas()
    cv.clear(skia.ColorTRANSPARENT)
    cv.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.ColorBLACK))
    cov = surf.makeImageSnapshot().toarray().astype(np.float32) / 255.0
    if cov.ndim == 3:
        cov = cov[..., 0]

    # ---- arrival time: earliest brush pass over each pixel (non-AA, 16-bit code)
    surf2 = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    cv2 = surf2.getCanvas()
    cv2.clear(skia.Color(255, 255, 255, 255))
    items = []
    soft = []
    for k, st in enumerate(strokes):
        times = _arrival(st, starts[k], durs[k])
        Lpx = st["length"] * scale
        soft.append(HEAD_SOFT_PX / max(Lpx, 1.0) * durs[k] * 1.6)
        for pc, t in zip(st["pieces"], times):
            P = px(pc.xy)
            Lp, Rp = px(pc.L), px(pc.R)
            for i in range(len(t)):
                j = min(i + 1, len(t) - 1)
                items.append((t[i], k, P[i], pc.a[i] * scale, pc.b[i] * scale, Lp[i], Lp[j], Rp[j], Rp[i]))
    items.sort(key=lambda it: -it[0])
    paint = skia.Paint(AntiAlias=False)
    nib_deg = -NIB_ANGLE_DEG
    for t, k, P, a, b, l0, l1, r1, r0 in items:
        code = int(round(min(max(t, 0.0), 1.0) * 65534))
        paint.setColor(skia.Color(code >> 8, code & 255, k, 255))
        cv2.save()
        cv2.translate(float(P[0]), float(P[1]))
        cv2.rotate(nib_deg)
        cv2.drawOval(skia.Rect(-a, -b, a, b), paint)
        cv2.restore()
        quad = skia.Path()
        quad.addPoly([skia.Point(*l0), skia.Point(*l1), skia.Point(*r1), skia.Point(*r0)], True)
        cv2.drawPath(quad, paint)
    rgba = surf2.makeImageSnapshot().toarray()
    code = rgba[..., 0].astype(np.int32) * 256 + rgba[..., 1]
    arr = code.astype(np.float32) / 65534.0
    sid = rgba[..., 2].astype(np.int32)
    undefined = code >= 65535
    # anti-aliased fringe pixels outside every non-AA footprint inherit a neighbour's time
    need = undefined & (cov > 0)
    for _ in range(4):
        if not need.any():
            break
        arr2 = minimum_filter(np.where(undefined, 2.0, arr), size=3)
        fill = need & (arr2 < 2.0)
        arr[fill] = arr2[fill]
        undefined = undefined & ~fill
        need = need & ~fill
    arr[undefined] = 1.0
    soft = np.array(soft + [0.002] * (256 - len(soft)), np.float32)
    wmap = soft[np.clip(sid, 0, 255)]
    # normalise so that progress=1 shows everything fully
    tmax = float((arr + 0.5 * wmap)[cov > 0].max())
    R = _Render()
    R.W, R.H, R.ox, R.oy = W, H, ox, oy
    R.cov = cov
    R.arr = arr / tmax
    R.wmap = wmap / tmax
    R.scale = scale
    R.dev_height = dev_height
    R.full = None
    R.strokes = strokes
    R.cu = cu
    return R


_O_H = None


def _o_height_units():
    """Ink height of the capital О in x-height units (stroke width included)."""
    global _O_H
    if _O_H is None:
        strokes, _, _ = _build_strokes(0.01)
        # the О is the first stroke of the title
        pts = np.vstack([np.vstack([pc.L, pc.R]) for pc in strokes[0]["pieces"]])
        _O_H = float(pts[:, 1].max() - pts[:, 1].min())
    return _O_H


_CACHE = {}


def _get_render(dev_height):
    key = round(float(dev_height), 2)
    R = _CACHE.get(key)
    if R is None:
        if len(_CACHE) >= 4:
            _CACHE.pop(next(iter(_CACHE)))
        R = _CACHE[key] = _build_render(key)
    return R


def _a8(arr):
    a = np.ascontiguousarray(np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8))
    return skia.Image.fromarray(a, colorType=skia.kAlpha_8_ColorType, alphaType=skia.kPremul_AlphaType)


def _halo_maps(R, cov):
    H, W = cov.shape
    small = cov.reshape(H // 4, 4, W // 4, 4).mean((1, 3))
    sg = GLOW_SIGMA * R.dev_height / 4.0
    ss = SHADOW_SIGMA * R.dev_height / 4.0
    glow = 1.0 - np.exp(-GLOW_GAIN * gaussian_filter(small, sg))
    shadow = np.clip(gaussian_filter(small, ss) * 1.6, 0, 1)
    return _a8(glow), _a8(shadow)


def _frame_images(R, progress):
    if progress >= 1.0:
        if R.full is None:
            R.full = (_a8(R.cov),) + _halo_maps(R, R.cov)
        return R.full
    vis = np.clip((progress - R.arr) / R.wmap + 0.5, 0.0, 1.0)
    cov = R.cov * vis
    return (_a8(cov),) + _halo_maps(R, cov)


_LINEAR = skia.SamplingOptions(skia.FilterMode.kLinear)


def draw_title(canvas, cx: float, cy: float, height: float, progress: float = 1.0,
               color=(255, 246, 228), alpha: float = 1.0, glow: float = 0.6) -> None:
    """Paint «Облачный кит» centred at (cx, cy); `height` = ink height of the capital О (px).

    progress 0..1 writes the title stroke by stroke in natural order; alpha fades
    everything; glow scales the warm halo and the faint shadow behind the letters.
    """
    if alpha <= 0.0 or progress <= 0.0 or height <= 0.0:
        return
    m = canvas.getTotalMatrix()
    dsc = m.getMaxScale()
    if not (dsc > 0.0):
        dsc = 1.0
    R = _get_render(height * dsc)
    img, glow_img, shadow_img = _frame_images(R, min(float(progress), 1.0))
    canvas.save()
    canvas.translate(cx, cy)
    if abs(dsc - 1.0) > 1e-6:
        canvas.scale(1.0 / dsc, 1.0 / dsc)
    rect = skia.Rect.MakeXYWH(-R.ox, -R.oy, R.W, R.H)
    if glow > 0.0:
        so = SHADOW_OFFSET * R.dev_height
        a = min(1.0, SHADOW_OPACITY * glow) * alpha
        canvas.drawImageRect(shadow_img, rect.makeOffset(0, so), _LINEAR,
                             skia.Paint(Color=skia.Color4f(*(c / 255 for c in SHADOW_RGB), a)))
        a = min(1.0, GLOW_OPACITY * glow) * alpha
        canvas.drawImageRect(glow_img, rect, _LINEAR,
                             skia.Paint(Color=skia.Color4f(*(c / 255 for c in GLOW_RGB), a)))
    canvas.drawImage(img, -R.ox, -R.oy, _LINEAR,
                     skia.Paint(Color=skia.Color4f(*(c / 255 for c in color), min(1.0, alpha))))
    canvas.restore()
