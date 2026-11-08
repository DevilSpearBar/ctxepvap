"""Preview / QA renders for film.lettering (writes build/title_*.png)."""
import sys
import time
from pathlib import Path

import numpy as np
import skia
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from film import lettering as L  # noqa: E402

W, H = 1920, 804
OUT = Path(__file__).resolve().parents[1] / "build"
OUT.mkdir(exist_ok=True)


def sky(w=W, h=H):
    y = np.linspace(0, 1, h)[:, None]
    stops = [(0.0, (104, 92, 152)), (0.38, (212, 136, 162)), (0.62, (243, 168, 136)),
             (0.82, (250, 196, 128)), (1.0, (253, 222, 150))]
    img = np.zeros((h, w, 4), np.uint8)
    for c in range(3):
        img[..., c] = np.interp(y, [s[0] for s in stops], [s[1][c] for s in stops])
    img[..., 3] = 255
    return img


def surface(bg):
    s = skia.Surface.MakeRaster(skia.ImageInfo.Make(bg.shape[1], bg.shape[0], skia.kRGBA_8888_ColorType,
                                                    skia.kPremul_AlphaType))
    s.getCanvas().drawImage(skia.Image.fromarray(bg, colorType=skia.kRGBA_8888_ColorType,
                                                 alphaType=skia.kPremul_AlphaType), 0, 0)
    return s


def snap(s):
    return s.makeImageSnapshot().toarray()[..., :3]


def main(which="all"):
    t0 = time.perf_counter()
    s = surface(sky())
    L.draw_title(s.getCanvas(), 960, 300, 110)
    print(f"first call (build) {1000 * (time.perf_counter() - t0):.0f} ms")
    Image.fromarray(snap(s)).save(OUT / "title_preview.png")

    # timing
    bg = sky()
    for p in (1.0, 0.5):
        s = surface(bg)
        c = s.getCanvas()
        L.draw_title(c, 960, 300, 110, p)
        n = 20
        t = time.perf_counter()
        for _ in range(n):
            L.draw_title(c, 960, 300, 110, p)
        print(f"progress={p}: {1000 * (time.perf_counter() - t) / n:.2f} ms/call")

    rows = []
    for p in (0.15, 0.35, 0.55, 0.8, 1.0):
        s = surface(bg)
        L.draw_title(s.getCanvas(), 960, 300, 110, p)
        rows.append(snap(s)[300 - 110:300 + 110, 960 - 560:960 + 560])
    Image.fromarray(np.vstack(rows)).save(OUT / "title_progress.png")

    s = surface(sky(1100, 260))
    L.draw_title(s.getCanvas(), 550, 130, 60)
    Image.fromarray(snap(s)).save(OUT / "title_small.png")

    if which in ("all", "debug"):
        debug()


def debug(height=230):
    """Big render on a dark ground with skeletons, control points and guide lines."""
    w, h = 3000, 640
    s = skia.Surface.MakeRaster(skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    c = s.getCanvas()
    c.clear(skia.Color(40, 44, 58))
    cx, cy = w / 2, h / 2
    L.draw_title(c, cx, cy, height, glow=0.0, color=(235, 235, 235))
    R = L._get_render(height)

    def px(p):
        return (cx + (p[..., 0] - R.cu[0]) * R.scale, cy - (p[..., 1] - R.cu[1]) * R.scale)

    guide = skia.Paint(AntiAlias=True, Color=skia.Color(120, 170, 255, 120), StrokeWidth=1, Style=skia.Paint.kStroke_Style)
    for yv in (0.0, 1.0, 1.6):
        _, yy = px(np.array([0.0, yv]))
        c.drawLine(0, float(yy), w, float(yy), guide)
    line = skia.Paint(AntiAlias=True, Color=skia.Color(255, 60, 60, 200), StrokeWidth=1.2, Style=skia.Paint.kStroke_Style)
    dot = skia.Paint(AntiAlias=True, Color=skia.Color(30, 120, 255, 255))
    cdot = skia.Paint(AntiAlias=True, Color=skia.Color(255, 160, 0, 255))
    for sk in R.strokes:
        st = sk.src
        for pc in st["pieces"]:
            X, Y = px(pc.xy)
            path = skia.Path()
            path.moveTo(float(X[0]), float(Y[0]))
            for x, y in zip(X[1:], Y[1:]):
                path.lineTo(float(x), float(y))
            c.drawPath(path, line)
        X, Y = px(st["ctrl"][:, :2])
        for i, (x, y) in enumerate(zip(X, Y)):
            c.drawCircle(float(x), float(y), 4.5 if st["ctrl"][i, 3] else 3.2, cdot if st["ctrl"][i, 3] else dot)
    img = s.makeImageSnapshot().toarray()[..., :3]
    Image.fromarray(img[:, :1560]).save(OUT / "title_debug_a.png")
    Image.fromarray(img[:, 1440:]).save(OUT / "title_debug_b.png")
    s2 = skia.Surface.MakeRaster(skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    c2 = s2.getCanvas()
    c2.clear(skia.Color(40, 44, 58))
    L.draw_title(c2, cx, cy, height, glow=0.0, color=(235, 235, 235))
    img = s2.makeImageSnapshot().toarray()[..., :3]
    Image.fromarray(img[:, :1560]).save(OUT / "title_clean_a.png")
    Image.fromarray(img[:, 1440:]).save(OUT / "title_clean_b.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
