"""Hand-lettered brush title «Облачный кит» — every pixel drawn from code.

No fonts, no text APIs, no images.  Each glyph below is a set of stroke
skeletons designed by hand: control points of a centripetal Catmull-Rom centre
line (glyph units: baseline y=0, x-height 1, y up) with a pressure value per
point.  A stroke is painted as the sweep of an elliptical brush footprint held
at NIB_ANGLE_DEG (thick downstrokes, hairline upstrokes), swollen by pressure,
tapered at both ends, with a seeded edge wobble so it reads as hand-painted.

Rendering: the sweep is a skia path of footprint-to-footprint quads plus round
footprint caps, anti-aliased by skia.  Completed strokes are cached as coverage
maps per device size; only the 1-2 strokes being painted at a given `progress`
are re-rasterised (their visible prefix ends in a round brush head).

Public API: draw_title(canvas, cx, cy, height, progress, color, alpha, glow);
reveal_schedule() gives the stroke timing (for syncing brush sounds).
"""
import math

import numpy as np
import skia
from scipy.ndimage import gaussian_filter, gaussian_filter1d

__all__ = ["draw_title", "reveal_schedule"]

# ----------------------------------------------------------------- knobs
TEXT = "Облачный кит"
NIB_ANGLE_DEG = 32.0   # brush held at this angle (deg, CCW from the baseline)
SLANT_DEG = 8.0        # italic lean of the letterforms
WIDTH = 1.06           # horizontal stretch of every glyph (and its advance)
TRACKING = 0.0         # extra space between letters (x-height units)
WORD_SPACE = 0.55      # extra space between words (x-height units)
BRUSH = 0.11           # nib half-length at full pressure (x-height units)
NIB_RATIO = 0.28       # thin/thick ratio of the nib ellipse
HAIRLINE = 0.021       # minimum half-width of a hairline (x-height units)
UPSTROKE = 0.42        # share of pressure kept on a pure upstroke
EDGE_WOBBLE = 0.04     # seeded edge irregularity (fraction of half-width)
BOUNCE = 0.018         # seeded per-letter baseline shift (x-height units)
TILT_DEG = 1.2         # seeded per-letter rotation
SEED = 11

# reveal timing (abstract units, normalised so that progress 0..1 spans it)
SPEED = 1.0            # x-height units of stroke per time unit
LIFT = 0.55            # extra time per stroke (approach / press / lift)
OVERLAP = 0.2          # next stroke starts this share (of the shorter one) before the last ends
WORD_PAUSE = 0.15      # breath between the words
EASE = 0.5             # 0 = constant brush speed, 1 = full ease-in-out per stroke

# halo
GLOW_RGB = (255, 236, 206)
GLOW_SIGMA = 0.075     # x О height
GLOW_GAIN = 2.2
GLOW_OPACITY = 0.75    # multiplied by `glow`
SHADOW_RGB = (92, 38, 62)
SHADOW_SIGMA = 0.022   # x О height
SHADOW_GAIN = 1.5
SHADOW_OFFSET = 0.02   # x О height, downwards
SHADOW_OPACITY = 0.55  # multiplied by `glow`

SAMPLE_PX = 0.6        # centre-line sampling step in device pixels


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
        (0.894, 1.280, 0.40), (0.711, 1.455, 0.34), (0.48, 1.475, 0.26), (0.30, 1.40, 0.16),
        taper_out=0.2)]),
    "б": dict(adv=0.74, strokes=[_S(
        (0.80, 1.52, 0.85), (0.68, 1.45, 0.55), (0.50, 1.49, 0.60), (0.30, 1.42, 0.75),
        (0.13, 1.12, 0.95), (0.05, 0.72, 1.00), (0.09, 0.24, 0.95), (0.30, -0.01, 0.80),
        (0.56, 0.12, 0.60), (0.64, 0.46, 0.50), (0.53, 0.82, 0.45), (0.31, 0.93, 0.40),
        (0.13, 0.81, 0.32), (0.07, 0.64, 0.22), e_in=0.85)]),
    "л": dict(adv=0.96, exit=0, strokes=[_S(
        (-0.03, 0.17, 0.75), (0.00, 0.05, 0.80), (0.09, 0.00, 0.55), (0.21, 0.10, 0.36),
        (0.33, 0.44, 0.32), (0.43, 0.82, 0.32), (0.52, 1.00, 0.32, C, 0.88), (0.53, 0.50, 1.00),
        (0.52, 0.08, 0.95), (0.58, -0.01, 0.60), (0.68, 0.05, 0.35), (0.74, 0.14, 0.20),
        e_in=0.75)]),
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
        _S((0.58, 0.98, 0.70), (0.44, 0.82, 0.50), (0.26, 0.62, 0.45), (0.12, 0.50, 0.40, C, 0.45),
           (0.28, 0.40, 0.80), (0.44, 0.20, 1.00), (0.52, 0.06, 0.95), (0.60, -0.01, 0.60),
           (0.70, 0.05, 0.35), (0.80, 0.18, 0.20), e_in=0.7)]),
    "и": dict(adv=0.92, entry=0, exit=0, strokes=[_S(*_U_BODY)]),
    "т": dict(adv=0.80, strokes=[
        _S((-0.04, 0.91, 0.40), (0.06, 0.99, 0.95), (0.34, 1.035, 1.35), (0.60, 1.02, 1.25),
           (0.76, 1.05, 0.55), e_in=0.3, taper_out=0.1),
        _S((0.36, 1.00, 0.85), (0.35, 0.50, 1.00), (0.34, 0.10, 0.95), (0.42, -0.01, 0.60),
           (0.58, 0.03, 0.40), (0.72, 0.16, 0.25), (0.80, 0.32, 0.15), e_in=0.6)]),
}


# ----------------------------------------------------------------- layout
def _layout():
    """Place glyphs, apply slant + per-letter liveliness, merge joined strokes.

    Returns strokes in writing order: dict(ctrl=(n,5) [x, y, p_in, corner, p_out],
    word, label, taper params).
    """
    rng = np.random.default_rng(SEED)
    tan_s = math.tan(math.radians(SLANT_DEG))
    strokes = []
    x0 = 0.0
    for wi, word in enumerate(TEXT.split(" ")):
        pending = None
        for ci, ch in enumerate(word):
            g = _GLYPHS[ch]
            dy = rng.uniform(-BOUNCE, BOUNCE)
            rot = math.radians(rng.uniform(-TILT_DEG, TILT_DEG))
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
                    strokes[pending]["label"] += ch
                    idx = pending
                else:
                    if pts[0][3]:  # nothing joins in: start directly with the pressed stem
                        pts[0][3] = 0.0
                        pts[0][2] = pts[0][4]
                    strokes.append(dict(ctrl=pts, word=wi, label=ch, taper_in=st["taper_in"],
                                        taper_out=st["taper_out"], e_in=st["e_in"],
                                        e_out=st["e_out"]))
                    idx = len(strokes) - 1
                if si == g.get("exit"):
                    exit_idx = idx
            joinable = nxt is not None and _GLYPHS[nxt].get("entry") is not None
            pending = exit_idx if joinable else None
            x0 += g["adv"] * WIDTH + TRACKING
        x0 += WORD_SPACE
    for s in strokes:
        s["ctrl"] = np.array(s["ctrl"], float)
    return strokes


# ----------------------------------------------------------------- geometry
def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _ease(u):
    return (1 - EASE) * u + EASE * _smoothstep(u)


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
        xs.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
        ps.append(pr[i] + (pr[i + 1] - pr[i]) * _smoothstep((t[:, 0] - t1) / (t2 - t1)))
    xs.append(P[-1:])
    ps.append(pr[-1:])
    return np.vstack(xs), np.concatenate(ps)


def _resample(xy, pr, ds):
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(xy, axis=0).T))])
    n = max(2, int(math.ceil(s[-1] / ds)) + 1)
    si = np.linspace(0.0, s[-1], n)
    return (np.stack([np.interp(si, s, xy[:, 0]), np.interp(si, s, xy[:, 1])], 1),
            np.interp(si, s, pr), si)


def _noise(s, rng, step=0.07):
    """Smooth seeded 1-D value noise in [-1, 1] along arc length s (units)."""
    knots = rng.uniform(-1.0, 1.0, int(s[-1] / step) + 3)
    f = s / step
    i = np.floor(f).astype(int)
    w = _smoothstep(f - i)
    return knots[i] * (1 - w) + knots[i + 1] * w


class _Piece:
    """One corner-free run of a stroke, sampled uniformly in arc length."""


def _nib_axes():
    th = math.radians(NIB_ANGLE_DEG)
    return np.array([math.cos(th), math.sin(th)]), np.array([-math.sin(th), math.cos(th)])


def _build_strokes(ds):
    """Sample every stroke at spacing ds (x-height units); footprints + outline points."""
    u, v = _nib_axes()
    out = []
    for k, st in enumerate(_layout()):
        ctrl = st["ctrl"]
        rng = np.random.default_rng(SEED * 1000 + k)
        cuts = [0] + [i for i in range(1, len(ctrl) - 1) if ctrl[i, 3]] + [len(ctrl) - 1]
        pieces = []
        s_off = 0.0
        for a, b in zip(cuts[:-1], cuts[1:]):
            prs = ctrl[a:b + 1, 2].copy()
            prs[0] = ctrl[a, 4]  # leaving a corner with the out-pressure
            xy, pr = _catmull_rom(ctrl[a:b + 1, :2], prs, ds * 0.25)
            pc = _Piece()
            pc.xy, pc.pr, s = _resample(xy, pr, ds)
            pc.s = s + s_off
            s_off += s[-1]
            pieces.append(pc)
        L = s_off
        for pc in pieces:
            s = pc.s
            tg = np.gradient(pc.xy, axis=0)
            tg /= np.maximum(np.hypot(tg[:, 0], tg[:, 1]), 1e-12)[:, None]
            # pointed-brush pressure: downstrokes press, upstrokes lighten
            D = UPSTROKE + (1 - UPSTROKE) * np.clip((1 - tg[:, 1]) / 2, 0, 1) ** 1.2
            D = gaussian_filter1d(D, max(0.02 / ds, 0.5), mode="nearest")
            P = gaussian_filter1d(pc.pr, max(0.03 / ds, 0.5), mode="nearest")
            ein = st["e_in"] + (1 - st["e_in"]) * np.sin(0.5 * np.pi * np.clip(s / st["taper_in"], 0, 1))
            eout = st["e_out"] + (1 - st["e_out"]) * np.sin(
                0.5 * np.pi * np.clip((L - s) / st["taper_out"], 0, 1))
            E = np.minimum(ein, eout)
            a = BRUSH * P * D * E
            b = np.maximum(HAIRLINE * np.sqrt(E), NIB_RATIO * a)
            a = np.maximum(a, b)
            # support point of the rotated nib ellipse along the left normal
            n = np.stack([-tg[:, 1], tg[:, 0]], 1)
            nu, nv = n @ u, n @ v
            h = np.sqrt(a * a * nu * nu + b * b * nv * nv)
            pc.S = (np.outer(a * a * nu, u) + np.outer(b * b * nv, v)) / h[:, None]
            pc.a, pc.b = a, b
        # seeded edge wobble, continuous along the whole stroke, separate per side
        sall = np.concatenate([pc.s for pc in pieces])
        nl = _noise(sall, rng) * EDGE_WOBBLE
        nr = _noise(sall, rng) * EDGE_WOBBLE
        i0 = 0
        for pc in pieces:
            m = len(pc.s)
            pc.L = pc.xy + pc.S * (1 + nl[i0:i0 + m, None])
            pc.R = pc.xy - pc.S * (1 + nr[i0:i0 + m, None])
            # round caps / brush head use the tighter side so they never bulge past the edges
            pc.kcap = 1 + np.minimum(nl[i0:i0 + m], nr[i0:i0 + m])
            i0 += m
        out.append(dict(pieces=pieces, length=L, word=st["word"], label=st["label"], ctrl=ctrl))
    return out


def _timeline(strokes):
    """Start and duration of each stroke in normalised time (last stroke ends at 1)."""
    starts, durs = [], []
    for k, st in enumerate(strokes):
        d = (st["length"] + LIFT) / SPEED
        t = 0.0
        if k > 0:
            prev_end = starts[-1] + durs[-1]
            if st["word"] != strokes[k - 1]["word"]:
                t = prev_end + WORD_PAUSE
            else:
                t = prev_end - OVERLAP * min(durs[-1], d)
        starts.append(t)
        durs.append(d)
    total = starts[-1] + durs[-1]
    return np.array(starts) / total, np.array(durs) / total


_GEOM_UNITS = {}


def _o_height_units():
    """Ink height of the capital О (first stroke) in x-height units."""
    if "o" not in _GEOM_UNITS:
        pcs = _build_strokes(0.004)[0]["pieces"]
        y = np.concatenate([np.concatenate([pc.L[:, 1], pc.R[:, 1]]) for pc in pcs])
        _GEOM_UNITS["o"] = float(y.max() - y.min())
    return _GEOM_UNITS["o"]


def reveal_schedule():
    """[(start, end, label)] of every brush stroke in progress units, in writing order."""
    strokes = _build_strokes(0.01)
    starts, durs = _timeline(strokes)
    return [(float(s), float(s + d), st["label"]) for s, d, st in zip(starts, durs, strokes)]


# ----------------------------------------------------------------- rasterising
_HDR_WINDING = 5  # SkPath serialisation header: version 5, non-zero winding


def _path_from_polys(*poly_sets):
    """(n, k, 2) arrays of closed polygons -> one skia.Path, built straight from numpy."""
    path = skia.Path()
    for polys in poly_sets:
        n, k = polys.shape[:2]
        if n == 0:
            continue
        verbs = np.empty((n, k + 1), np.uint8)
        verbs[:, 0] = 0
        verbs[:, 1:k] = 1
        verbs[:, k] = 5
        blob = (np.array([_HDR_WINDING, n * k, 0, n * (k + 1)], np.int32).tobytes()
                + np.ascontiguousarray(polys, np.float32).tobytes() + verbs.tobytes())
        blob += b"\0" * ((-len(blob)) % 4)
        part = skia.Path()
        part.readFromMemory(blob)
        path.addPath(part)
    return path


def _orient(polys):
    """Make every polygon counter-clockwise so that overlapping pieces only ever add."""
    x, y = polys[..., 0], polys[..., 1]
    area = (x * np.roll(y, -1, 1) - np.roll(x, -1, 1) * y).sum(1)
    flip = area < 0
    polys[flip] = polys[flip, ::-1]
    return polys


def _cross(o, a, b):
    return (a[..., 0] - o[..., 0]) * (b[..., 1] - o[..., 1]) - (a[..., 1] - o[..., 1]) * (b[..., 0] - o[..., 0])


def _quads(L, R):
    """Footprint-to-footprint quads; twisted ones (tight inner turns) become 4 triangles."""
    l0, l1, r1, r0 = L[:-1], L[1:], R[1:], R[:-1]
    q = np.stack([l0, l1, r1, r0], 1)
    # cross-sections l0-r0 and l1-r1 intersect -> bow-tie
    d1, d2 = _cross(l0, r0, l1), _cross(l0, r0, r1)
    d3, d4 = _cross(l1, r1, l0), _cross(l1, r1, r0)
    bow = (d1 * d2 < 0) & (d3 * d4 < 0)
    idx = np.arange(len(q))
    quads = _orient(q[~bow].copy())
    tb = q[bow]
    tris = _orient(np.concatenate([tb[:, [0, 1, 2]], tb[:, [0, 2, 3]], tb[:, [0, 1, 3]], tb[:, [1, 2, 3]]]))
    tri_idx = np.tile(idx[bow], 4)
    order = np.argsort(tri_idx, kind="stable")
    return quads, idx[~bow], tris[order], tri_idx[order]


class _Stroke:
    pass


class _Render:
    pass


def _build_render(dev_height):
    """Geometry in device pixels + cached coverage of every finished stroke."""
    scale = dev_height / _o_height_units()        # px per x-height
    strokes = _build_strokes(SAMPLE_PX / scale)
    starts, durs = _timeline(strokes)
    u, v = _nib_axes()

    pts = np.vstack([np.vstack([pc.L, pc.R, pc.xy - pc.a[:, None], pc.xy + pc.a[:, None]])
                     for st in strokes for pc in st["pieces"]])
    lo, hi = pts.min(0), pts.max(0)
    cu = (lo + hi) / 2
    margin = int(math.ceil(dev_height * (GLOW_SIGMA * 3.2 + SHADOW_OFFSET) + 6))
    W = int(math.ceil(((hi[0] - lo[0]) * scale + 2 * margin) / 4)) * 4
    H = int(math.ceil(((hi[1] - lo[1]) * scale + 2 * margin) / 4)) * 4
    ox, oy = W // 2, H // 2
    # device y points down; the nib axes flip with it
    U, V = np.array([u[0], -u[1]]), np.array([v[0], -v[1]])
    amax = max(float(pc.a.max()) for st in strokes for pc in st["pieces"]) * scale
    n_ell = int(np.clip(math.ceil(2 * math.pi * amax / 1.5), 16, 96))
    phase = np.linspace(0, 2 * np.pi, n_ell, endpoint=False)
    cosp, sinp = np.cos(phase)[:, None], np.sin(phase)[:, None]

    def px(p):
        return np.stack([ox + (p[..., 0] - cu[0]) * scale, oy - (p[..., 1] - cu[1]) * scale], -1)

    R = _Render()
    R.W, R.H, R.ox, R.oy, R.scale, R.cu, R.dev_height = W, H, ox, oy, scale, cu, dev_height
    R.starts, R.ends, R.durs = starts, starts + durs, durs
    R.ellipse = lambda c, a, b: _orient((c[:, None, :] + a[:, None, None] * cosp.T[..., None] * U
                                         + b[:, None, None] * sinp.T[..., None] * V).copy())
    R.strokes = []
    full = np.zeros((H, W), np.uint8)
    for k, st in enumerate(strokes):
        sk = _Stroke()
        sk.length = st["length"]
        sk.src = st
        sk.ellipse = R.ellipse
        sk.pieces = []
        allp = []
        for pc in st["pieces"]:
            q = _Piece()
            q.s = pc.s
            q.L, q.R, q.xy = px(pc.L), px(pc.R), px(pc.xy)
            q.a, q.b = pc.a * pc.kcap * scale, pc.b * pc.kcap * scale
            q.quads, q.qi, q.tris, q.ti = _quads(q.L, q.R)
            q.caps = R.ellipse(q.xy[[0, -1]], q.a[[0, -1]], q.b[[0, -1]])
            sk.pieces.append(q)
            allp += [q.L, q.R, q.xy - q.a[:, None], q.xy + q.a[:, None]]
        allp = np.vstack(allp)
        x0, y0 = np.floor(allp.min(0)).astype(int) - 2
        x1, y1 = np.ceil(allp.max(0)).astype(int) + 3
        sk.box = (max(x0, 0), max(y0, 0), min(x1, W), min(y1, H))
        bx0, by0, bx1, by1 = sk.box
        sk.surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(bx1 - bx0, by1 - by0, skia.kAlpha_8_ColorType, skia.kPremul_AlphaType))
        sk.full = _raster(sk, sk.length + 1.0)
        np.maximum(full[by0:by1, bx0:bx1], sk.full, out=full[by0:by1, bx0:bx1])
        R.strokes.append(sk)
    R.full_cov = full
    R.union = {len(R.strokes): full}
    R.full_images = None
    return R


_PAINT = skia.Paint(AntiAlias=True, Color=skia.ColorBLACK)


def _raster(sk, ell):
    """Anti-aliased coverage (uint8, stroke box) of the first `ell` units of a stroke."""
    polys_q, polys_t, caps = [], [], []
    for q in sk.pieces:
        if ell <= q.s[0]:
            break
        caps.append(q.caps[:1])
        if ell >= q.s[-1]:
            polys_q.append(q.quads)
            polys_t.append(q.tris)
            caps.append(q.caps[1:])
            continue
        i = int(np.searchsorted(q.s, ell, side="right")) - 1  # s[i] <= ell < s[i+1]
        polys_q.append(q.quads[:np.searchsorted(q.qi, i)])
        polys_t.append(q.tris[:np.searchsorted(q.ti, i)])
        f = (ell - q.s[i]) / max(q.s[i + 1] - q.s[i], 1e-12)
        lh = q.L[i] + f * (q.L[i + 1] - q.L[i])
        rh = q.R[i] + f * (q.R[i + 1] - q.R[i])
        head = np.array([[q.L[i], lh, rh, q.R[i]]])
        polys_t.append(_orient(np.concatenate([head[:, [0, 1, 2]], head[:, [0, 2, 3]]])))
        ch = q.xy[i] + f * (q.xy[i + 1] - q.xy[i])
        caps.append(sk.ellipse(ch[None], np.array([q.a[i] + f * (q.a[i + 1] - q.a[i])]),
                               np.array([q.b[i] + f * (q.b[i + 1] - q.b[i])])))
        break
    bx0, by0, bx1, by1 = sk.box
    cv = sk.surface.getCanvas()
    cv.clear(skia.ColorTRANSPARENT)
    if polys_q or polys_t or caps:
        cv.save()
        cv.translate(-bx0, -by0)
        cv.drawPath(_path_from_polys(*(polys_q + polys_t + caps)), _PAINT)
        cv.restore()
    a = sk.surface.makeImageSnapshot().toarray()
    return a[..., 0] if a.ndim == 3 else a


def _union(R, m):
    """Coverage of the first m strokes, all finished (cached)."""
    cov = R.union.get(m)
    if cov is None:
        cov = _union(R, m - 1).copy() if m > 0 else np.zeros((R.H, R.W), np.uint8)
        if m > 0:
            sk = R.strokes[m - 1]
            bx0, by0, bx1, by1 = sk.box
            np.maximum(cov[by0:by1, bx0:bx1], sk.full, out=cov[by0:by1, bx0:bx1])
        R.union[m] = cov
    return cov


def _coverage(R, t):
    """uint8 coverage of the whole title at normalised time t (0..1)."""
    m = int(np.searchsorted(R.ends, t, side="right"))   # strokes 0..m-1 are finished
    cov = _union(R, m)
    live = [k for k in range(m, len(R.strokes)) if R.starts[k] < t]
    if not live:
        return cov
    cov = cov.copy()
    for k in live:
        sk = R.strokes[k]
        uu = (t - R.starts[k]) / R.durs[k]
        part = _raster(sk, float(_ease(np.float64(uu))) * sk.length)
        bx0, by0, bx1, by1 = sk.box
        np.maximum(cov[by0:by1, bx0:bx1], part, out=cov[by0:by1, bx0:bx1])
    return cov


_CACHE = {}


def _get_render(dev_height):
    key = round(float(dev_height), 2)
    R = _CACHE.get(key)
    if R is None:
        if len(_CACHE) >= 8:
            _CACHE.pop(next(iter(_CACHE)))
        R = _CACHE[key] = _build_render(key)
    return R


def _a8(arr):
    return skia.Image.fromarray(np.ascontiguousarray(arr), colorType=skia.kAlpha_8_ColorType,
                                alphaType=skia.kPremul_AlphaType)


def _images(R, cov):
    """Crisp A8 coverage + halo (1/4 res) + shadow (1/2 res) images."""
    H, W = cov.shape
    half = cov.reshape(H // 2, 2, W // 2, 2).mean((1, 3), dtype=np.float32) / 255.0
    quarter = half.reshape(H // 4, 2, W // 4, 2).mean((1, 3))
    glow = 1.0 - np.exp(-GLOW_GAIN * gaussian_filter(quarter, GLOW_SIGMA * R.dev_height / 4.0))
    shadow = np.clip(gaussian_filter(half, SHADOW_SIGMA * R.dev_height / 2.0) * SHADOW_GAIN, 0, 1)
    to8 = lambda x: (x * 255.0 + 0.5).astype(np.uint8)  # noqa: E731
    return _a8(cov), _a8(to8(glow)), _a8(to8(shadow))


_LINEAR = skia.SamplingOptions(skia.FilterMode.kLinear)


def _rgb4(color, a):
    c = [float(x) for x in color[:3]]
    if max(c) <= 1.0 and any(x != int(x) for x in c):
        c = [x * 255.0 for x in c]  # accept 0..1 floats too
    return skia.Color4f(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0, a)


def draw_title(canvas, cx: float, cy: float, height: float, progress: float = 1.0,
               color=(255, 246, 228), alpha: float = 1.0, glow: float = 0.6) -> None:
    """Paint «Облачный кит» centred at (cx, cy) (ink bounding box centre).

    height   ink height of the capital «О» in px (title is ~7.7x as wide).
    progress 0..1: the title is written stroke by stroke in natural writing order
             (linear in writing time; see reveal_schedule()); 1 = complete.
    color    RGB 0..255; alpha multiplies everything; glow (0..~1.5) scales the warm
             halo and the faint soft shadow behind the letters.
    """
    if alpha <= 0.0 or progress <= 0.0 or height <= 0.0:
        return
    dsc = canvas.getTotalMatrix().getMaxScale()
    if not (dsc > 0.0):
        dsc = 1.0
    dev_h = float(height) * dsc
    # maps are built per device size in 0.5 px steps; an animated size only rebuilds
    # every half pixel and the residual is absorbed by a tiny scale
    key = max(4.0, round(dev_h * 2.0) / 2.0)
    R = _get_render(key)
    if progress >= 1.0:
        if R.full_images is None:
            R.full_images = _images(R, R.full_cov)
        img, glow_img, shadow_img = R.full_images
    else:
        img, glow_img, shadow_img = _images(R, _coverage(R, float(progress)))
    alpha = min(1.0, float(alpha))
    canvas.save()
    canvas.translate(cx, cy)
    k = dev_h / key / dsc
    if abs(k - 1.0) > 1e-6:
        canvas.scale(k, k)
    rect = skia.Rect.MakeXYWH(-R.ox, -R.oy, R.W, R.H)
    if glow > 0.0:
        # wide warm halo first, then a tight soft shadow that keeps the edges defined
        canvas.drawImageRect(glow_img, rect, _LINEAR,
                             skia.Paint(Color=_rgb4(GLOW_RGB, min(1.0, GLOW_OPACITY * glow) * alpha)))
        canvas.drawImageRect(shadow_img, rect.makeOffset(0, SHADOW_OFFSET * R.dev_height), _LINEAR,
                             skia.Paint(Color=_rgb4(SHADOW_RGB, min(1.0, SHADOW_OPACITY * glow) * alpha)))
    canvas.drawImage(img, -R.ox, -R.oy, _LINEAR, skia.Paint(Color=_rgb4(color, alpha)))
    canvas.restore()
