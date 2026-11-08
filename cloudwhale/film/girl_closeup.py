"""Close-up of the heroine (3/4 view, looking up-right at the sky), no hat.

Drawn in absolute pixels of a 1920x804 frame; the head pivots around (760, 440).
"""

import math

import skia

from .girl import PALETTES, _paint, _shift, _smooth, _stroke

CX, CY = 760.0, 440.0


def _cel(c, path, fill, shade, line, sx, sy, lw=3.2):
    c.drawPath(path, _paint(fill))
    sh = skia.Op(path, _shift(path, -sx, -sy), skia.PathOp.kDifference_PathOp)
    if sh is not None:
        c.drawPath(sh, _paint(shade))
    c.drawPath(path, _stroke(line, lw))


def _flut(t, i, wind, amp=1.0):
    return math.sin(t * 7.0 + i * 1.9) * amp * (3 + 10 * wind) + math.sin(t * 11.3 + i * 0.7) * amp * 3 * wind


def _hair_back(t, wind):
    w = wind
    pts = [(0, -200), (-120, -175), (-190, -95), (-212, 10), (-206 + _flut(t, 1, w, 0.4), 110),
           (-186 + _flut(t, 2, w, 0.6), 190), (-150, 205), (-120, 170), (110, 160),
           (172 + 40 * w + _flut(t, 3, w), 175 + 10 * w), (196 + 50 * w + _flut(t, 4, w), 110),
           (214 + 30 * w + _flut(t, 5, w, 0.7), 10), (190 + 12 * w, -100), (120, -172)]
    return _smooth(pts, closed=True, t=0.55)


def _face():
    pts = [(-150, -60), (-148, 30), (-128, 106), (-84, 162), (-24, 198), (24, 210), (70, 188),
           (116, 138), (144, 64), (150, -30), (110, -150), (0, -172), (-110, -140)]
    return _smooth(pts, closed=True, t=0.5)


def _bangs(t, wind):
    w = wind
    f = lambda i, a=1.0: _flut(t, i + 10, w, a)
    top = [(-172, -40), (-166, -120), (-100, -185), (0, -206), (110, -185), (172, -112), (182, -30)]
    tips = [(168 + 20 * w + f(0), 4 + f(1, 0.5)), (128, -44), (96 + 10 * w + f(2), -2), (62, -50),
            (24 + 8 * w + f(3, 0.8), -8), (-14, -54), (-52 + 5 * w + f(4, 0.7), -10), (-92, -56),
            (-132 + f(5, 0.5), -6), (-156, -40)]
    return _smooth(top + tips, closed=True, t=0.3)


def _side_lock(side, t, wind):
    w = wind
    if side < 0:
        pts = [(-176, -50), (-150, -40), (-142, 40), (-128 + 6 * w + _flut(t, 20, w, 0.6), 150),
               (-150 + _flut(t, 21, w, 0.5), 168), (-170, 90), (-182, 0)]
    else:
        pts = [(150, -40), (182, -46), (196 + 18 * w, 30), (214 + 46 * w + _flut(t, 22, w), 132),
               (186 + 34 * w + _flut(t, 23, w), 120), (160 + 10 * w, 60), (146, 0)]
    return _smooth(pts, closed=True, t=0.5)


def _strands(c, t, wind, P):
    """Loose wisps streaming right in the wind."""
    if wind < 0.05:
        return
    for i, (x0, y0, L) in enumerate(((120, -175, 120), (60, -200, 110), (175, -90, 100), (-40, -205, 90))):
        p = skia.Path()
        p.moveTo(x0, y0)
        ex = x0 + L * wind * 1.4 + _flut(t, 30 + i, wind, 0.8)
        ey = y0 - 20 + _flut(t, 40 + i, wind, 0.6)
        p.cubicTo(x0 + L * 0.3, y0 - 30, ex - L * 0.3, ey + 25, ex, ey)
        c.drawPath(p, _stroke(P['line'], 5.0 * wind + 1))
        c.drawPath(p, _stroke(P['hair'], 3.0 * wind + 0.4))


def _eye(c, ex, ey, ew, eh, blink, gaze, P, far=False):
    open_k = max(0.0, 1.0 - blink)
    if open_k < 0.12:
        p = skia.Path()
        p.moveTo(ex - ew * 0.55, ey + 4)
        p.quadTo(ex, ey + eh * 0.28, ex + ew * 0.55, ey + 2)
        c.drawPath(p, _stroke(P['line'], 5.0))
        return
    top = ey - eh * 0.5 * open_k + eh * 0.5 * (1 - open_k) * 0.6
    bot = ey + eh * 0.5
    shape = skia.Path()
    shape.moveTo(ex - ew * 0.5, ey + eh * 0.05)
    shape.cubicTo(ex - ew * 0.45, top - 4, ex + ew * 0.4, top - 6, ex + ew * 0.52, ey - eh * 0.05)
    shape.cubicTo(ex + ew * 0.5, bot - 6, ex - ew * 0.3, bot + 2, ex - ew * 0.5, ey + eh * 0.05)
    shape.close()
    c.drawPath(shape, _paint(P['white']))
    c.save()
    c.clipPath(shape, doAntiAlias=True)
    ix, iy = ex + gaze[0] * ew * 0.16, ey + gaze[1] * eh * 0.12
    irw, irh = ew * 0.40, eh * 0.47
    g = skia.Paint(AntiAlias=True)
    g.setShader(skia.GradientShader.MakeLinear(
        [skia.Point(ix, iy - irh), skia.Point(ix, iy + irh)],
        [skia.Color4f(0.12, 0.07, 0.06, 1).toColor(), skia.Color4f(0.26, 0.14, 0.10, 1).toColor(),
         skia.Color4f(0.50, 0.30, 0.20, 1).toColor()], [0.0, 0.55, 1.0]))
    c.drawOval(skia.Rect.MakeLTRB(ix - irw, iy - irh, ix + irw, iy + irh), g)
    c.drawOval(skia.Rect.MakeLTRB(ix - irw * 0.5, iy - irh * 0.45, ix + irw * 0.5, iy + irh * 0.45),
               _paint((0.07, 0.04, 0.04)))
    # lid shadow on the eyeball
    sh = skia.Path()
    sh.addRect(skia.Rect.MakeLTRB(ex - ew, top - 20, ex + ew, top + eh * 0.12))
    c.drawPath(sh, _paint((0.55, 0.45, 0.5), 0.25))
    c.drawCircle(ix - irw * 0.35, iy - irh * 0.4, max(3.0, ew * 0.12), _paint((1, 1, 1)))
    c.drawCircle(ix + irw * 0.35, iy + irh * 0.35, max(1.5, ew * 0.05), _paint((1, 1, 1), 0.85))
    c.restore()
    lash = skia.Path()
    lash.moveTo(ex - ew * 0.56, ey + eh * 0.08)
    lash.cubicTo(ex - ew * 0.45, top - 5, ex + ew * 0.4, top - 7, ex + ew * 0.56, ey - eh * 0.06)
    if not far:
        lash.lineTo(ex + ew * 0.68, ey - eh * 0.16)
    c.drawPath(lash, _stroke(P['line'], 6.0))
    low = skia.Path()
    low.moveTo(ex - ew * 0.1, bot + 1)
    low.quadTo(ex + ew * 0.25, bot, ex + ew * 0.45, bot - eh * 0.12)
    c.drawPath(low, _stroke(P['line'], 2.2, 0.8))


def draw_girl_closeup(canvas, *, blink=0.0, mouth_open=0.0, smile=0.0, gaze=(0.6, -0.5),
                      wind=0.6, t=0.0, palette='day'):
    P = PALETTES[palette]
    c = canvas
    br = math.sin(t * 2.0) * 2.0
    # ---- body (does not tilt with the head)
    c.save()
    c.translate(CX, CY + br)
    neck = _smooth([(-50, 120), (42, 128), (48, 262), (-56, 266)], closed=True, t=0.3)
    c.drawPath(neck, _paint(P['skin']))
    c.drawPath(neck, _stroke(P['line'], 3.0))
    nsh = _smooth([(-50, 150), (42, 150), (46, 205), (-10, 190), (-52, 214)], closed=True, t=0.4)
    c.drawPath(nsh, _paint(P['skin_sh']))
    shoulders = _smooth([(-52, 236), (-150, 290), (-320, 360), (-360, 520), (330, 520), (300, 360),
                         (160, 288), (46, 240)], closed=True, t=0.4)
    _cel(c, shoulders, P['skin'], P['skin_sh'], P['line'], 10, 0)
    cover = _smooth([(-50, 200), (44, 200), (40, 250), (-48, 252)], closed=True, t=0.3)
    c.drawPath(cover, _paint(P['skin']))
    dress = _smooth([(-370, 360), (-200, 318), (-120, 330), (-10, 372), (110, 330), (190, 316),
                     (340, 350), (340, 540), (-370, 540)], closed=True, t=0.35)
    _cel(c, dress, P['dress'], P['dress_sh'], P['line'], 16, 0)
    collar = _smooth([(-128, 318), (-10, 360), (118, 318), (126, 336), (-10, 386), (-136, 336)],
                     closed=True, t=0.4)
    c.drawPath(collar, _paint(P['collar']))
    c.drawPath(collar, _stroke(P['line'], 2.6))
    c.restore()
    # ---- head, tilted up toward the sky
    c.save()
    c.translate(CX, CY + br * 0.5)
    c.rotate(-11.0 + 1.0 * math.sin(t * 0.9))
    hb = _hair_back(t, wind)
    _cel(c, hb, P['hair'], (P['hair'][0] * 0.7, P['hair'][1] * 0.7, P['hair'][2] * 0.7), P['line'], 18, 8)
    face = _face()
    _cel(c, face, P['skin'], P['skin_sh'], P['line'], 12, 0)
    # blush
    for bx, by, rw in ((-82, 92, 34), (112, 86, 24)):
        g = skia.Paint(AntiAlias=True)
        g.setShader(skia.GradientShader.MakeRadial(skia.Point(bx, by), rw,
                                                   [skia.Color4f(*P['blush'], 0.6).toColor(),
                                                    skia.Color4f(*P['blush'], 0.0).toColor()]))
        c.save()
        c.scale(1.0, 0.6)
        c.translate(0, by / 0.6 - by)
        c.drawCircle(bx, by, rw * 1.4, g)
        c.restore()
    gz = gaze
    _eye(c, -58, 44, 80, 98, blink, gz, P)
    _eye(c, 92, 38, 60, 94, blink, gz, P, far=True)
    # nose
    n = skia.Path()
    n.moveTo(28, 82)
    n.quadTo(40, 100, 30, 106)
    c.drawPath(n, _stroke(P['line'], 2.6, 0.85))
    # mouth
    mx, my = 30, 146
    if mouth_open > 0.08:
        oh = 5 + 22 * mouth_open
        ow = 13 + 6 * mouth_open - 4 * smile
        m = skia.Path()
        m.addOval(skia.Rect.MakeLTRB(mx - ow, my - oh * 0.45, mx + ow, my + oh * 0.55))
        c.drawPath(m, _paint((0.45, 0.15, 0.15)))
        c.save()
        c.clipPath(m, doAntiAlias=True)
        c.drawOval(skia.Rect.MakeLTRB(mx - ow, my + oh * 0.1, mx + ow, my + oh * 1.0), _paint((0.92, 0.52, 0.52)))
        c.restore()
        c.drawPath(m, _stroke(P['line'], 2.6))
    else:
        m = skia.Path()
        m.moveTo(mx - 16, my - 2 * smile)
        m.quadTo(mx, my + 3 + 9 * smile, mx + 16, my - 5 * smile)
        c.drawPath(m, _stroke(P['line'], 2.8))
    # fringe & side locks
    hair_sh = (P['hair'][0] * 0.7, P['hair'][1] * 0.7, P['hair'][2] * 0.7)
    for side in (-1, 1):
        _cel(c, _side_lock(side, t, wind), P['hair'], hair_sh, P['line'], 8, 6)
    bangs = _bangs(t, wind)
    _cel(c, bangs, P['hair'], hair_sh, P['line'], 10, 8)
    hi = skia.Path()
    hi.moveTo(-118, -142)
    hi.cubicTo(-70, -176, 30, -184, 96, -160)
    c.drawPath(hi, _stroke(P['hair_hi'], 6.0, 0.75))
    for x0 in (-90, -20, 50):
        p = skia.Path()
        p.moveTo(x0, -170)
        p.quadTo(x0 + 10, -120, x0 + 4, -80)
        c.drawPath(p, _stroke(P['line'], 1.8, 0.6))
    c.restore()
