"""The cloud whale: a whale-shaped cumulus with a gentle eye.

The body is a heap of puffs placed along a spine with a thickness profile and
rendered with the same z-buffered cloud shader as the sky, so it reads as a cloud
until the eye opens. Swimming = vertical strip warp travelling toward the tail.
"""

import numpy as np
import skia
from scipy.interpolate import PchipInterpolator

from .core import paint_fill, smoothstep, surface, to_image
from .sky import DAY, Puff, Sprite, render_puffs

_S = [0.0, 0.025, 0.08, 0.2, 0.34, 0.5, 0.66, 0.8, 0.9, 0.97, 1.0]
_TH = [0.0, 0.055, 0.10, 0.128, 0.13, 0.112, 0.08, 0.05, 0.032, 0.024, 0.02]


class Whale:
    def __init__(self, L=1800, pal=DAY, seed=5, sunset=False):
        self.L = L
        self.pal = pal
        rng = np.random.default_rng(seed)
        th_f = PchipInterpolator(_S, _TH)
        self.W_ = int(L * 1.3)
        self.H_ = int(L * 0.66)
        x0, ymid = L * 0.09, L * 0.25
        self.x0, self.ymid = x0, ymid

        def X(s):
            return x0 + s * L

        def YC(s):
            return ymid - L * 0.018 * np.sin(np.pi * s) - L * 0.035 * smoothstep(0.62, 1.0, s)

        def TH(s):
            return float(th_f(s)) * L

        self.X, self.YC, self.TH = X, YC, TH
        top = lambda s: YC(s) - TH(s) * 0.92
        bot = lambda s: YC(s) + TH(s) * 1.08
        puffs = []
        # interior core
        for s in np.linspace(0.035, 0.97, 48):
            th = TH(s)
            puffs.append(Puff(X(s), YC(s) + th * 0.08, th * 0.25, th * 0.98))
        # billowy back (irregular sizes and spacing so it never reads as ribs)
        s = 0.02
        while s < 0.78:
            th = TH(s)
            r = th * 0.36 * rng.uniform(0.6, 1.35)
            y = top(s) + r * rng.uniform(0.35, 0.6)
            puffs.append(Puff(X(s), y, th * 0.55 + r * rng.uniform(0.0, 0.5), r))
            s += r * rng.uniform(0.6, 1.1) / L
        # a few finer billows on the back
        s = 0.04
        while s < 0.7:
            th = TH(s)
            r = th * 0.16 * rng.uniform(0.7, 1.4)
            puffs.append(Puff(X(s), top(s) + r * 0.35, th * 0.72, r))
            s += r * rng.uniform(2.0, 4.5) / L
        # smoother belly
        s = 0.04
        while s < 0.9:
            th = TH(s)
            r = th * 0.42 * rng.uniform(0.85, 1.1)
            puffs.append(Puff(X(s), bot(s) - r * 0.62, th * 0.45, r))
            s += r * 0.9 / L
        # snout
        puffs.append(Puff(X(0.03), YC(0.03) + TH(0.08) * 0.05, TH(0.1) * 0.5, TH(0.08) * 0.75))
        # tail flukes (stylised, both lobes visible)
        tx, ty = X(0.985), YC(0.985)
        for (dx, dy) in ((0.13, -0.11), (0.14, 0.075)):
            for k in np.linspace(0, 1, 40):
                r = L * (0.026 * (1 - k) + 0.008)
                bend = np.sin(np.pi * k) * L * 0.012
                puffs.append(Puff(tx + dx * L * k, ty + dy * L * k - bend, L * 0.02 - k * L * 0.01, r))
        self.puffs = puffs
        body = render_puffs(puffs, self.W_, self.H_, pal, seed=seed, base_y=bot(0.3) + 10,
                            cut_base=False, warp=9.0, warp_cell=50.0, bottom_dark=0.42,
                            form_sigma=L * 0.03, local_w=0.36, shade_noise=0.08)
        self.body = self._features(body)
        # pectoral fin (separate so it can flap)
        fin = []
        rx, ry = X(0.27), bot(0.27) - TH(0.27) * 0.25
        self.fin_root = (rx, ry)
        for k in np.linspace(0, 1, 48):
            r = L * (0.034 * (1 - k) ** 0.8 + 0.009)
            fx = rx + L * 0.22 * k
            fy = ry + L * 0.13 * k - np.sin(np.pi * k) * L * 0.025
            fin.append(Puff(fx, fy, L * 0.05 - k * L * 0.02, r))
        self.fin = render_puffs(fin, self.W_, self.H_, pal, seed=seed + 1, warp=6.0,
                                warp_cell=30.0, form_sigma=L * 0.012, local_w=0.4)
        self.body_img = to_image(self.body)
        self.fin_img = to_image(self.fin)
        self.eye = (X(0.155), YC(0.155) + TH(0.155) * 0.18)
        self.head_top = (X(0.11), top(0.11) + TH(0.11) * 0.02)
        self.blowhole = (X(0.2), top(0.2))
        self.eye_r = L * 0.0135

    def _features(self, body):
        """Mouth line and throat grooves painted onto the body (subtle)."""
        L, X, YC, TH = self.L, self.X, self.YC, self.TH
        s = surface(self.W_, self.H_)
        c = s.getCanvas()
        c.drawImage(to_image(body), 0, 0)
        sh = self.pal['deep']
        p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
        p.setColor4f(skia.Color4f(*sh, 0.55))
        p.setStrokeWidth(L * 0.0035)
        path = skia.Path()
        path.moveTo(X(0.012), YC(0.012) + TH(0.05) * 0.25)
        path.cubicTo(X(0.06), YC(0.06) + TH(0.06) * 0.42, X(0.13), YC(0.13) + TH(0.13) * 0.42,
                     X(0.2), YC(0.2) + TH(0.2) * 0.30)
        c.drawPath(path, p)
        p.setStrokeWidth(L * 0.0022)
        p.setColor4f(skia.Color4f(*sh, 0.28))
        for i in range(5):
            o = 0.52 + i * 0.1
            path = skia.Path()
            path.moveTo(X(0.04), YC(0.04) + TH(0.06) * o)
            path.cubicTo(X(0.12), YC(0.12) + TH(0.12) * (o + 0.12), X(0.22), YC(0.22) + TH(0.22) * (o + 0.1),
                         X(0.32), YC(0.32) + TH(0.32) * (o + 0.02))
            c.drawPath(path, p)
        from .core import to_array
        out = to_array(s)
        out[..., 3] = body[..., 3]
        return out

    # ------------------------------------------------------------------ drawing
    def draw(self, canvas, x, y, scale=1.0, t=0.0, swim=1.0, eye_open=1.0, fin_phase=0.0,
             alpha=1.0, look=(0.0, 0.0), strip=6):
        """Draw with sprite origin at (x, y) (top-left of the sprite box) and uniform scale."""
        L = self.L
        canvas.save()
        canvas.translate(x, y)
        canvas.scale(scale, scale)
        paint = skia.Paint()
        if alpha < 1:
            paint.setAlphaf(alpha)
        samp = skia.SamplingOptions(skia.FilterMode.kLinear)

        def dy_at(px):
            s = (px - self.x0) / L
            env = 0.25 + 0.75 * smoothstep(0.25, 1.05, s)
            return swim * L * 0.022 * env * np.sin(2 * np.pi * (0.55 * s) - 2 * np.pi * t / 4.0)

        # fin behind? the near fin is in front; draw body first
        for img, rot in ((self.body_img, 0.0),):
            for sx in range(0, self.W_, strip):
                w = min(strip, self.W_ - sx)
                d = dy_at(sx + w * 0.5)
                src = skia.Rect.MakeXYWH(sx, 0, w + 1, self.H_)
                dst = skia.Rect.MakeXYWH(sx, d, w + 1, self.H_)
                canvas.drawImageRect(img, src, dst, samp, paint)
        # flapping pectoral fin, rotated about its root
        rx, ry = self.fin_root
        ang = 6.0 * np.sin(2 * np.pi * t / 4.0 + fin_phase) * swim
        canvas.save()
        canvas.translate(rx, ry + dy_at(rx))
        canvas.rotate(ang)
        canvas.translate(-rx, -ry)
        canvas.drawImage(self.fin_img, 0, 0, samp, paint)
        canvas.restore()
        # eye
        ex, ey = self.eye
        ey += dy_at(ex)
        self._draw_eye(canvas, ex, ey, eye_open, look, alpha)
        canvas.restore()

    def offset_at(self, px, t, swim=1.0):
        s = (px - self.x0) / self.L
        env = 0.25 + 0.75 * smoothstep(0.25, 1.05, s)
        return swim * self.L * 0.022 * env * np.sin(2 * np.pi * (0.55 * s) - 2 * np.pi * t / 4.0)

    def _draw_eye(self, c, ex, ey, k, look, alpha):
        r = self.eye_r
        sh = self.pal['deep']
        line = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
        line.setColor4f(skia.Color4f(*(sh * 0.75), 0.9 * alpha))
        line.setStrokeWidth(r * 0.32)
        k = float(np.clip(k, 0, 1))
        if k < 0.04:
            # closed: a gentle downward arc (sleeping)
            p = skia.Path()
            p.moveTo(ex - r * 1.5, ey - r * 0.1)
            p.quadTo(ex, ey + r * 0.9, ex + r * 1.5, ey - r * 0.1)
            c.drawPath(p, line)
            return
        open_h = r * 1.15 * k
        almond = skia.Path()
        almond.moveTo(ex - r * 1.55, ey)
        almond.cubicTo(ex - r * 0.8, ey - open_h * 1.25, ex + r * 0.8, ey - open_h * 1.25, ex + r * 1.55, ey)
        almond.cubicTo(ex + r * 0.8, ey + open_h * 0.9, ex - r * 0.8, ey + open_h * 0.9, ex - r * 1.55, ey)
        almond.close()
        white = paint_fill(skia.Color4f(0.97, 0.98, 1.0, alpha))
        c.drawPath(almond, white)
        c.save()
        c.clipPath(almond, doAntiAlias=True)
        ix, iy = ex + look[0] * r * 0.5 - r * 0.15, ey + look[1] * r * 0.4
        c.drawCircle(ix, iy, r * 1.0, paint_fill(skia.Color4f(0.17, 0.22, 0.36, alpha)))
        c.drawCircle(ix, iy, r * 0.55, paint_fill(skia.Color4f(0.07, 0.09, 0.16, alpha)))
        c.drawCircle(ix - r * 0.35, iy - r * 0.38, r * 0.3, paint_fill(skia.Color4f(1, 1, 1, alpha)))
        c.drawCircle(ix + r * 0.3, iy + r * 0.3, r * 0.12, paint_fill(skia.Color4f(1, 1, 1, 0.8 * alpha)))
        c.restore()
        # upper lid line + lash flick, lower lid hint
        p = skia.Path()
        p.moveTo(ex - r * 1.65, ey + r * 0.05)
        p.cubicTo(ex - r * 0.8, ey - open_h * 1.3, ex + r * 0.8, ey - open_h * 1.3, ex + r * 1.7, ey - r * 0.05)
        c.drawPath(p, line)
        lw = skia.Paint(line)
        lw.setStrokeWidth(r * 0.15)
        lw.setColor4f(skia.Color4f(*(sh * 0.75), 0.5 * alpha))
        p = skia.Path()
        p.moveTo(ex - r * 1.0, ey + open_h * 0.75)
        p.quadTo(ex, ey + open_h * 1.0, ex + r * 1.0, ey + open_h * 0.7)
        c.drawPath(p, lw)


def make_mist_puffs(pal=DAY, seed=3, n=5, size=140):
    """Small round cloud puffs (for the whale's breath) -> list of (img, w, h)."""
    out = []
    from .sky import fit_puffs
    for i in range(n):
        rng = np.random.default_rng(seed + i)
        puffs = [Puff(0, 0, 0, size * 0.42)]
        for _ in range(6):
            a = rng.uniform(0, 2 * np.pi)
            r = size * rng.uniform(0.18, 0.3)
            puffs.append(Puff(np.cos(a) * size * 0.35, np.sin(a) * size * 0.3, size * 0.1, r))
        w, h, dx, dy = fit_puffs(puffs, 14)
        rgba = render_puffs(puffs, w, h, pal, seed=seed + i, warp=5, warp_cell=20, form_sigma=8)
        out.append((to_image(rgba), w, h))
    return out
