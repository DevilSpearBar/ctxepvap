"""The heroine: a ~10-year-old girl in a coral sundress and straw hat (side view rig).

Local coordinates: origin = ground point between the feet, y down, +x = facing
direction, standing height ~400 px. Callers translate/scale the canvas first.
Drawn as cels: warm-brown outline, flat fill, one crisp shadow tone.
"""

import math
from dataclasses import dataclass, fields

import skia

# ---------------------------------------------------------------- palettes
_DAY = dict(
    skin=(0.988, 0.878, 0.796), skin_sh=(0.929, 0.706, 0.608), blush=(0.957, 0.651, 0.627),
    hair=(0.227, 0.149, 0.125), hair_hi=(0.369, 0.247, 0.200),
    dress=(0.851, 0.282, 0.231), dress_sh=(0.659, 0.204, 0.227), collar=(0.98, 0.96, 0.92),
    sandal=(0.541, 0.353, 0.235),
    straw=(0.945, 0.867, 0.627), straw_sh=(0.804, 0.698, 0.467), weave=(0.75, 0.63, 0.40),
    ribbon=(0.184, 0.290, 0.541), ribbon_sh=(0.133, 0.208, 0.416),
    line=(0.290, 0.173, 0.149), eye=(0.17, 0.10, 0.09), white=(1.0, 1.0, 1.0),
    rim=None,
)
_SUNSET = dict(
    skin=(0.62, 0.42, 0.38), skin_sh=(0.42, 0.27, 0.28), blush=(0.70, 0.40, 0.38),
    hair=(0.13, 0.08, 0.09), hair_hi=(0.25, 0.15, 0.14),
    dress=(0.55, 0.17, 0.18), dress_sh=(0.36, 0.11, 0.16), collar=(0.62, 0.52, 0.50),
    sandal=(0.30, 0.18, 0.14),
    straw=(0.66, 0.52, 0.36), straw_sh=(0.42, 0.32, 0.26), weave=(0.48, 0.36, 0.26),
    ribbon=(0.14, 0.15, 0.30), ribbon_sh=(0.10, 0.10, 0.22),
    line=(0.16, 0.09, 0.10), eye=(0.08, 0.05, 0.05), white=(0.85, 0.78, 0.74),
    rim=(1.0, 0.72, 0.42),
)
PALETTES = {'day': _DAY, 'sunset': _SUNSET}

LINE_W = 2.6
HS = 1.13          # head scale: Ghibli children have big heads


def _paint(col, a=1.0):
    p = skia.Paint(AntiAlias=True)
    p.setColor4f(skia.Color4f(col[0], col[1], col[2], a))
    return p


def _stroke(col, w, a=1.0):
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                   StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    p.setColor4f(skia.Color4f(col[0], col[1], col[2], a))
    return p


# ---------------------------------------------------------------- geometry helpers
def _rot(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _limb_pt(origin, length, ang):
    """Point at `length` from origin along angle `ang` (0 = straight down, + = toward +x)."""
    a = math.radians(ang)
    return (origin[0] + math.sin(a) * length, origin[1] + math.cos(a) * length)


def _union(paths):
    out = paths[0]
    for p in paths[1:]:
        r = skia.Op(out, p, skia.PathOp.kUnion_PathOp)
        if r is not None:
            out = r
    return out


def _circle(c, r):
    p = skia.Path()
    p.addCircle(c[0], c[1], r)
    return p


def _capsule(a, ra, b, rb):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    if d < 1e-3:
        return _circle(a, max(ra, rb))
    base = math.atan2(dy, dx)
    k = max(-1.0, min(1.0, (ra - rb) / d))
    off = math.pi / 2 + math.asin(k)
    quad = skia.Path()
    pts = []
    for s in (1, -1):
        ang = base + s * off
        pts.append(((a[0] + ra * math.cos(ang), a[1] + ra * math.sin(ang)),
                    (b[0] + rb * math.cos(ang), b[1] + rb * math.sin(ang))))
    quad.moveTo(*pts[0][0])
    quad.lineTo(*pts[0][1])
    quad.lineTo(*pts[1][1])
    quad.lineTo(*pts[1][0])
    quad.close()
    return _union([quad, _circle(a, ra), _circle(b, rb)])


def _smooth(points, closed=True, t=0.5):
    n = len(points)
    path = skia.Path()
    path.moveTo(*points[0])
    segs = n if closed else n - 1
    for i in range(segs):
        p0 = points[(i - 1) % n] if (closed or i > 0) else points[0]
        p1 = points[i % n]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n] if (closed or i + 2 < n) else points[-1]
        k = t / 3.0
        c1 = (p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k)
        c2 = (p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        path.close()
    return path


def _shift(path, dx, dy):
    q = skia.Path(path)
    q.offset(dx, dy)
    return q


def _cel(c, path, fill, shade, line, sx=5.0, sy=4.0, lw=LINE_W, rim=None):
    """Fill, crisp shadow crescent (away from upper-left light), optional rim, outline."""
    c.drawPath(path, _paint(fill))
    sh = skia.Op(path, _shift(path, -sx, -sy), skia.PathOp.kDifference_PathOp)
    if sh is not None:
        c.drawPath(sh, _paint(shade))
    if rim is not None:
        rp = skia.Op(path, _shift(path, -3.0, 0.0), skia.PathOp.kDifference_PathOp)
        if rp is not None:
            c.drawPath(rp, _paint(rim, 0.85))
    c.drawPath(path, _stroke(line, lw))


# ---------------------------------------------------------------- pose
@dataclass
class Pose:
    root_x: float = 0.0
    root_y: float = 0.0
    lean: float = 0.0
    head: float = 0.0
    hip_f: float = 2.0
    knee_f: float = 4.0
    foot_f: float = 0.0
    hip_b: float = -2.0
    knee_b: float = 3.0
    foot_b: float = 0.0
    sh_f: float = -4.0
    el_f: float = 12.0
    sh_b: float = 6.0
    el_b: float = 12.0
    mouth: float = 0.0


def lerp_pose(a, b, k):
    k = max(0.0, min(1.0, k))
    return Pose(**{f.name: getattr(a, f.name) + (getattr(b, f.name) - getattr(a, f.name)) * k
                   for f in fields(Pose)})


def pose_run(phase):
    th = 2 * math.pi * (phase % 1.0)

    def leg(t):
        hip = 32 * math.cos(t) + 6
        knee = 16 + 84 * max(0.0, -math.sin(t)) ** 0.9
        foot = -20 * max(0.0, -math.sin(t)) + 10 * max(0.0, math.sin(t))
        return hip, knee, foot

    hf, kf, ff = leg(th)
    hb, kb, fb = leg(th + math.pi)
    return Pose(
        root_x=2 * math.sin(2 * th), root_y=6 * math.cos(2 * (th - 0.5)) - 10,
        lean=12.0, head=-10 + 2 * math.sin(2 * th),
        hip_f=hf, knee_f=kf, foot_f=ff, hip_b=hb, knee_b=kb, foot_b=fb,
        sh_f=-36 * math.cos(th) + 12, el_f=78 + 14 * math.sin(th),
        sh_b=36 * math.cos(th) + 12, el_b=78 - 14 * math.sin(th),
        mouth=0.25,
    )


def pose_stand(t):
    br = math.sin(2 * math.pi * t / 3.2)
    return Pose(root_y=0.8 * br, lean=-1.0 + 0.6 * br, head=1.5 * br,
                sh_f=-5 + 1.5 * br, el_f=14, sh_b=7 - 1.5 * br, el_b=12)


def pose_look_up(k, t):
    p = pose_stand(t)
    q = Pose(**{f.name: getattr(p, f.name) for f in fields(Pose)})
    q.head = p.head + 30.0
    q.lean = p.lean - 5.0
    q.sh_f, q.el_f = -10.0, 18.0
    q.sh_b, q.el_b = 10.0, 14.0
    q.mouth = 0.3
    return lerp_pose(p, q, k)


def pose_reach_up(k, t):
    p = pose_stand(t)
    q = Pose(root_y=-7.0, lean=6.0, head=34.0, hip_f=6, knee_f=4, foot_f=-12, hip_b=-10, knee_b=10,
             foot_b=-25, sh_f=150 + 4 * math.sin(t * 3), el_f=8, sh_b=48, el_b=30, mouth=0.8)
    return lerp_pose(p, q, k)


def pose_catch(k):
    p = pose_stand(0.0)
    q = Pose(root_y=-4.0, lean=-2.0, head=26.0, hip_f=4, knee_f=3, hip_b=-5, knee_b=6,
             sh_f=146, el_f=26, sh_b=138, el_b=34, mouth=0.6)
    return lerp_pose(p, q, k)


def pose_hat_on(k):
    p = pose_catch(1.0)
    q = Pose(root_y=0.0, lean=0.0, head=6.0, sh_f=150, el_f=72, sh_b=142, el_b=80, mouth=0.2)
    return lerp_pose(p, q, k)


def pose_wave(t):
    w = math.sin(2 * math.pi * 1.6 * t)
    return Pose(root_y=-1.0, lean=-3.0, head=22.0 + 1.5 * w, hip_f=3, knee_f=3, hip_b=-4, knee_b=5,
                sh_f=166 + 5 * w, el_f=16 + 24 * w, sh_b=8, el_b=16, mouth=0.0)


# ---------------------------------------------------------------- skeleton
_PELVIS = (0.0, -188.0)
_THIGH, _SHIN = 92.0, 90.0
_TORSO = 98.0
_UPPER, _FORE = 60.0, 54.0


def _skeleton(p):
    pel = (_PELVIS[0] + p.root_x, _PELVIS[1] + p.root_y)
    up = _rot((0.0, -_TORSO), p.lean)
    neck = _add(pel, up)
    sh = _add(pel, _rot((0.0, -_TORSO + 8), p.lean))
    sk = {'pel': pel, 'neck': neck, 'sh': sh}
    for side, hip, knee, foot in (('f', p.hip_f, p.knee_f, p.foot_f), ('b', p.hip_b, p.knee_b, p.foot_b)):
        h = (pel[0] + (2 if side == 'f' else -2), pel[1])
        k = _limb_pt(h, _THIGH, hip)
        a = _limb_pt(k, _SHIN, hip - knee)
        sk['hip' + side], sk['knee' + side], sk['ank' + side] = h, k, a
        sk['foot' + side] = foot + (hip - knee) * 0.25
    for side, s_, e_ in (('f', p.sh_f, p.el_f), ('b', p.sh_b, p.el_b)):
        a0 = p.lean + s_
        e = _limb_pt(sh, _UPPER, a0)
        w = _limb_pt(e, _FORE, a0 + e_)
        hand = _limb_pt(e, _FORE + 9, a0 + e_)
        sk['el' + side], sk['wr' + side], sk['hand' + side] = e, w, hand
    head_ang = p.lean + p.head
    sk['head_ang'] = head_ang
    sk['head'] = _add(neck, _rot((5.0 * HS, -46.0 * HS), head_ang))
    return sk


def hand_position(pose):
    sk = _skeleton(pose)
    a, b = sk['handf'], sk['handb']
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def head_top(pose):
    sk = _skeleton(pose)
    top = _add(sk['head'], _rot((-2.0 * HS, -40.0 * HS), sk['head_ang']))
    return (top[0], top[1], sk['head_ang'] * 0.6)


# ---------------------------------------------------------------- body parts
def _leg_path(sk, side):
    h, k, a = sk['hip' + side], sk['knee' + side], sk['ank' + side]
    return _union([_capsule(h, 14.5, k, 10.0), _capsule(k, 10.0, a, 6.8)])


def _foot_path(sk, side):
    a = sk['ank' + side]
    ang = sk['foot' + side]
    heel = _add(a, _rot((-6.0, 6.0), ang))
    toe = _add(a, _rot((22.0, 6.5), ang))
    return _capsule(heel, 6.5, toe, 5.5)


def _arm_path(sk, side):
    s, e, w, hand = sk['sh'], sk['el' + side], sk['wr' + side], sk['hand' + side]
    return _union([_capsule(s, 9.0, e, 7.0), _capsule(e, 7.0, w, 5.6), _circle(hand, 8.2)])


def _dress_paths(sk, p, wind, wind_dir, t):
    pel, neck = sk['pel'], sk['neck']
    L = lambda v: _add(pel, _rot(v, p.lean))
    # bodice: shoulders to waist
    bod = _smooth([L((-21, -92)), L((-6, -100)), L((16, -96)), L((25, -80)), L((24, -52)),
                   L((22, -36)), L((-22, -36)), L((-25, -60)), L((-24, -84))], closed=True, t=0.6)
    # skirt: waist to hem, swings with legs and wind
    hl = (sk['kneef'][0] + sk['kneeb'][0]) * 0.5 - pel[0]
    front_k = max(sk['kneef'][0], sk['kneeb'][0]) - pel[0]
    back_k = min(sk['kneef'][0], sk['kneeb'][0]) - pel[0]
    wv = wind * wind_dir
    hem_y = 70.0
    pts = [L((24, -40)), L((26, -20))]
    n = 7
    hem = []
    for i in range(n + 1):
        u = i / n                       # 0 = front, 1 = back
        x = (52 - 108 * u) + hl * 0.25
        x = max(x, front_k + 10) if u < 0.2 else x
        x = min(x, back_k - 10) if u > 0.8 else x
        flutter = math.sin(t * 9.0 + u * 5.0) * (3 + 9 * wind) * (0.4 + 0.6 * u)
        x += wv * (16 + 22 * u) + flutter * 0.4
        y = hem_y + 6 * math.sin(u * math.pi * 2 + t * 6) * (0.3 + wind) - wv * wv * 8 * u
        hem.append((pel[0] + x, pel[1] + y + flutter * 0.3))
    pts += hem
    pts += [L((-30, -20)), L((-24, -40))]
    skirt = _smooth(pts, closed=True, t=0.5)
    return bod, skirt, hem


def _hair_back(head, ang, wind, wind_dir, t):
    H = lambda v: _add(head, _rot((v[0] * HS, v[1] * HS), ang))
    wv = wind * wind_dir
    f = lambda i: math.sin(t * 8.0 + i * 1.3) * (2 + 6 * wind)
    pts = [H((30, -34)), H((4, -48)), H((-26, -42)),
           H((-44 + wv * 10 + f(0), -18)), H((-46 + wv * 16 + f(1), 8)),
           H((-38 + wv * 20 + f(2), 30 + abs(wv) * 4)), H((-22 + wv * 14 + f(3), 38)),
           H((-6, 34)), H((6, 18)), H((14, -6)), H((30, -18))]
    return _smooth(pts, closed=True, t=0.55)


def _hair_front(head, ang, wind, wind_dir, t):
    H = lambda v: _add(head, _rot((v[0] * HS, v[1] * HS), ang))
    wv = wind * wind_dir
    f = lambda i: math.sin(t * 9.0 + i * 1.7) * (1.5 + 5 * wind)
    # fringe and the near-side lock over the ear
    pts = [H((-30, -40)), H((2, -50)), H((28, -40)), H((42 + wv * 4, -22)),
           H((38 + wv * 6 + f(0), -12)), H((30, -17)), H((24 + wv * 4 + f(1), -9)),
           H((16, -16)), H((8, -14)), H((2 + wv * 4, 4)), H((-2 + wv * 8 + f(2), 26)),
           H((-12 + wv * 6, 30)), H((-18, 10)), H((-28, -12))]
    return _smooth(pts, closed=True, t=0.55)


def _face(head, ang):
    H = lambda v: _add(head, _rot((v[0] * HS, v[1] * HS), ang))
    pts = [H((-4, -28)), H((24, -30)), H((36, -18)), H((38, -6)), H((44, 2)), H((40, 6)),
           H((38, 14)), H((36, 20)), H((32, 28)), H((22, 34)), H((8, 34)), H((-6, 26)), H((-12, 6))]
    return _smooth(pts, closed=True, t=0.5)


def _draw_face_details(c, head, ang, P, smile, mouth, blink=0.0):
    H = lambda v: _add(head, _rot((v[0] * HS, v[1] * HS), ang))
    ex, ey = H((25, -6))
    eh = 9.5 * (1 - 0.35 * smile) * (1 - blink)
    if eh > 1.2:
        c.save()
        c.translate(ex, ey)
        c.rotate(ang)
        c.drawOval(skia.Rect.MakeLTRB(-4.2, -eh * 0.62, 4.2, eh * 0.62), _paint(P['eye']))
        c.drawCircle(-1.2, -eh * 0.25, 1.5, _paint(P['white']))
        c.restore()
    lash = skia.Path()
    lash.moveTo(*H((19, -12)))
    lash.quadTo(*H((25, -16)), *H((32, -10)))
    c.drawPath(lash, _stroke(P['line'], 2.4))
    brow = skia.Path()
    brow.moveTo(*H((19, -23)))
    brow.quadTo(*H((26, -26)), *H((32, -22)))
    c.drawPath(brow, _stroke(P['line'], 1.6, 0.8))
    c.drawOval(skia.Rect.MakeXYWH(H((20, 8))[0] - 7, H((20, 8))[1] - 4, 14, 8), _paint(P['blush'], 0.55))
    m = skia.Path()
    if mouth > 0.35:
        mx, my = H((33, 21))
        o = 1.5 + 3.5 * mouth
        c.drawOval(skia.Rect.MakeLTRB(mx - 3, my - o * 0.6, mx + 2.5, my + o * 0.6), _paint((0.45, 0.16, 0.16)))
    else:
        m.moveTo(*H((30, 20 - 2 * smile)))
        m.quadTo(*H((34, 23 + 1.5 * smile)), *H((38, 19 - 1.0 * smile)))
        c.drawPath(m, _stroke(P['line'], 1.8))


# ---------------------------------------------------------------- hat
def _hat_paths(tilt, spin):
    """Brim ellipse + crown for a hat seen at `tilt` (-1 below .. +1 above), centre at origin."""
    br = 75.0
    bry = max(5.0, abs(tilt) * br)
    crown_r = 36.0
    up = math.sqrt(max(0.0, 1 - tilt * tilt))
    brim = skia.Path()
    brim.addOval(skia.Rect.MakeLTRB(-br, -bry, br, bry))
    ch = 34.0 * up
    top_ry = max(3.0, crown_r * abs(tilt))
    crown = skia.Path()
    crown.moveTo(-crown_r, 0)
    crown.lineTo(-crown_r * 0.92, -ch)
    crown.arcTo(skia.Rect.MakeLTRB(-crown_r * 0.92, -ch - top_ry, crown_r * 0.92, -ch + top_ry), 180, 180, False)
    crown.lineTo(crown_r, 0)
    crown.arcTo(skia.Rect.MakeLTRB(-crown_r, -top_ry, crown_r, top_ry), 0, 180, False)
    crown.close()
    return brim, crown, bry, ch, top_ry


def draw_hat(canvas, *, rot_deg=0.0, tilt=0.0, spin=0.0, t=0.0, wind=0.5, palette='day', wind_dir=-1):
    P = PALETTES[palette]
    c = canvas
    c.save()
    c.rotate(rot_deg)
    tilt = max(-1.0, min(1.0, tilt))
    brim, crown, bry, ch, top_ry = _hat_paths(tilt, spin)
    sp = math.radians(spin)
    bow_x = 36.0 * math.cos(sp)
    bow_front = math.sin(sp) > 0
    # ribbon tails (behind)
    tails = []
    for k, off in ((0, 0.0), (1, 1.4)):
        base = (bow_x * 0.9, -6.0)
        L = 46.0
        pts = [base]
        for i in range(1, 6):
            u = i / 5
            wx = wind_dir * (L * u) * (0.6 + 0.4 * wind) + math.sin(t * 10 + u * 4 + off) * 7 * wind * u
            wy = u * L * (0.5 - 0.35 * wind) + math.cos(t * 8 + u * 3 + off) * 4 * u + k * 6 * u
            pts.append((base[0] + wx, base[1] + wy))
        tails.append(pts)

    def draw_tails():
        for pts in tails:
            path = skia.Path()
            path.moveTo(*pts[0])
            for q in pts[1:]:
                path.lineTo(*q)
            c.drawPath(path, _stroke(P['line'], 9.0))
            c.drawPath(path, _stroke(P['ribbon'], 6.2))

    if not bow_front:
        draw_tails()
    if tilt >= -0.15:
        # seen from the side/above: brim top, then crown
        c.drawPath(brim, _paint(P['straw']))
        if tilt > 0.2:
            for r in (0.62, 0.75, 0.88):
                ring = skia.Path()
                ring.addOval(skia.Rect.MakeLTRB(-75 * r, -bry * r, 75 * r, bry * r))
                c.drawPath(ring, _stroke(P['weave'], 1.2, 0.7))
        under = skia.Op(brim, _shift(brim, 0, -max(2.0, 6 * (1 - abs(tilt)))), skia.PathOp.kDifference_PathOp)
        if under is not None:
            c.drawPath(under, _paint(P['straw_sh']))
        c.drawPath(brim, _stroke(P['line'], 2.4))
        _cel(c, crown, P['straw'], P['straw_sh'], P['line'], sx=6, sy=0, lw=2.4)
        # ribbon band around the crown base
        band = skia.Path()
        band.addRect(skia.Rect.MakeLTRB(-38, -10 * max(0.3, 1 - abs(tilt)) - 2, 38, 1))
        band = skia.Op(band, crown, skia.PathOp.kIntersect_PathOp) or band
        c.drawPath(band, _paint(P['ribbon']))
        if tilt > 0.25:
            top = skia.Path()
            top.addOval(skia.Rect.MakeLTRB(-33, -ch - top_ry, 33, -ch + top_ry))
            c.drawPath(top, _paint(P['straw']))
            c.drawPath(top, _stroke(P['line'], 2.0))
    else:
        # seen from below: underside of the brim and the dark inside of the crown
        c.drawPath(brim, _paint(P['straw_sh']))
        inner = skia.Path()
        inner.addOval(skia.Rect.MakeLTRB(-34, -34 * abs(tilt), 34, 34 * abs(tilt)))
        c.drawPath(inner, _paint((P['straw_sh'][0] * 0.55, P['straw_sh'][1] * 0.5, P['straw_sh'][2] * 0.5)))
        for r in (0.7, 0.86):
            ring = skia.Path()
            ring.addOval(skia.Rect.MakeLTRB(-75 * r, -bry * r, 75 * r, bry * r))
            c.drawPath(ring, _stroke(P['weave'], 1.1, 0.6))
        c.drawPath(brim, _stroke(P['line'], 2.4))
    if bow_front:
        draw_tails()
    if bow_front or abs(tilt) > 0.4:
        bx, by = bow_x, -5.0
        for s in (-1, 1):
            loop = _smooth([(bx, by), (bx + s * 13, by - 8), (bx + s * 15, by + 2), (bx + s * 4, by + 3)])
            c.drawPath(loop, _paint(P['ribbon']))
            c.drawPath(loop, _stroke(P['line'], 1.8))
        c.drawCircle(bx, by, 4.0, _paint(P['ribbon_sh']))
    c.restore()


# ---------------------------------------------------------------- full figure
def draw_girl(canvas, pose, *, wind=0.3, wind_dir=1, t=0.0, hat_on=True, smile=0.0, palette='day'):
    P = PALETTES[palette]
    c = canvas
    sk = _skeleton(pose)
    rim = P['rim']
    dark = lambda col, k=0.82: (col[0] * k, col[1] * k, col[2] * k)
    head, ang = sk['head'], sk['head_ang']
    # far arm and leg (darker, behind)
    _cel(c, _arm_path(sk, 'b'), dark(P['skin']), dark(P['skin_sh']), P['line'])
    _cel(c, _leg_path(sk, 'b'), dark(P['skin']), dark(P['skin_sh']), P['line'])
    _cel(c, _foot_path(sk, 'b'), dark(P['sandal']), dark(P['sandal'], 0.6), P['line'], sx=3, sy=3)
    # hair mass behind the head
    hb = _hair_back(head, ang, wind, wind_dir, t)
    _cel(c, hb, P['hair'], dark(P['hair'], 0.7), P['line'], sx=6, sy=5, rim=rim)
    # near leg under the skirt
    _cel(c, _leg_path(sk, 'f'), P['skin'], P['skin_sh'], P['line'], rim=rim)
    _cel(c, _foot_path(sk, 'f'), P['sandal'], dark(P['sandal'], 0.65), P['line'], sx=3, sy=3)
    # neck
    neck = _capsule(sk['neck'], 7.5, _add(sk['neck'], _rot((3.0, -14.0), ang)), 7.0)
    _cel(c, neck, P['skin'], P['skin_sh'], P['line'], sx=4, sy=0)
    # dress
    bod, skirt, hem = _dress_paths(sk, pose, wind, wind_dir, t)
    dress = _union([bod, skirt])
    _cel(c, dress, P['dress'], P['dress_sh'], P['line'], sx=7, sy=3, rim=rim)
    # skirt folds
    pel = sk['pel']
    for hx, hy in hem[2:-2:2]:
        fold = skia.Path()
        fold.moveTo(pel[0] + (hx - pel[0]) * 0.35, pel[1] + 6)
        fold.quadTo(pel[0] + (hx - pel[0]) * 0.75, pel[1] + (hy - pel[1]) * 0.6, hx, hy - 4)
        c.drawPath(fold, _stroke(P['line'], 1.3, 0.55))
    # collar
    col = _smooth([_add(sk['neck'], _rot(v, pose.lean)) for v in ((-12, 4), (2, 0), (16, 3), (14, 10), (2, 9), (-10, 11))])
    c.drawPath(col, _paint(P['collar']))
    c.drawPath(col, _stroke(P['line'], 1.6))
    # head
    face = _face(head, ang)
    _cel(c, face, P['skin'], P['skin_sh'], P['line'], sx=0, sy=0, rim=rim)
    _draw_face_details(c, head, ang, P, smile, pose.mouth)
    hf = _hair_front(head, ang, wind, wind_dir, t)
    _cel(c, hf, P['hair'], dark(P['hair'], 0.7), P['line'], sx=5, sy=5, rim=rim)
    hi = skia.Path()
    H = lambda v: _add(head, _rot((v[0] * HS, v[1] * HS), ang))
    hi.moveTo(*H((-18, -36)))
    hi.quadTo(*H((2, -46)), *H((22, -36)))
    c.drawPath(hi, _stroke(P['hair_hi'], 4.0, 0.9))
    # near arm in front
    _cel(c, _arm_path(sk, 'f'), P['skin'], P['skin_sh'], P['line'], rim=rim)
    if hat_on:
        hx, hy, ha = head_top(pose)
        c.save()
        c.translate(hx, hy + 13)
        c.rotate(ha - 6)
        c.scale(0.97, 0.97)
        draw_hat(c, rot_deg=0.0, tilt=0.12, spin=200.0, t=t, wind=wind, palette=palette,
                 wind_dir=-1 if wind_dir < 0 else 1)
        c.restore()


def draw_girl_closeup(canvas, **kw):
    from .girl_closeup import draw_girl_closeup as _d
    _d(canvas, **kw)
