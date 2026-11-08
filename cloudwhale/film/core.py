"""Rendering primitives shared by every shot: skia surfaces, numpy layers, noise."""

import numpy as np
import skia
from scipy import ndimage

W, H = 1920, 804


# ---------------------------------------------------------------- surfaces

def surface(w=W, h=H):
    info = skia.ImageInfo.Make(int(w), int(h), skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    return skia.Surface.MakeRaster(info)


def to_array(surf):
    """Premultiplied RGBA float32 in [0, 1]."""
    return surf.makeImageSnapshot().toarray().astype(np.float32) * (1.0 / 255.0)


def to_image(arr):
    """Premultiplied RGBA float array -> skia.Image."""
    a8 = np.ascontiguousarray((np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
    return skia.Image.fromarray(a8, colorType=skia.kRGBA_8888_ColorType,
                                alphaType=skia.kPremul_AlphaType)


def rgb_layer(rgb, alpha=None):
    """Straight RGB (+alpha) -> premultiplied RGBA float32."""
    h, w = rgb.shape[:2]
    out = np.empty((h, w, 4), np.float32)
    if alpha is None:
        out[..., :3] = rgb
        out[..., 3] = 1.0
    else:
        a = np.clip(alpha, 0, 1).astype(np.float32)
        out[..., :3] = rgb * a[..., None]
        out[..., 3] = a
    return out


LINEAR = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kNone)
MIPMAP = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def draw_image(canvas, img, x, y, scale=1.0, alpha=1.0, sampling=LINEAR, blend=None):
    paint = skia.Paint()
    if alpha < 1.0:
        paint.setAlphaf(max(0.0, alpha))
    if blend is not None:
        paint.setBlendMode(blend)
    if scale == 1.0:
        canvas.drawImage(img, float(x), float(y), sampling, paint)
    else:
        dst = skia.Rect.MakeXYWH(float(x), float(y), img.width() * scale, img.height() * scale)
        canvas.drawImageRect(img, dst, sampling, paint)


def color(hexstr, a=1.0):
    hexstr = hexstr.lstrip('#')
    r, g, b = (int(hexstr[i:i + 2], 16) for i in (0, 2, 4))
    return skia.Color4f(r / 255, g / 255, b / 255, a)


def rgbf(hexstr):
    hexstr = hexstr.lstrip('#')
    return np.array([int(hexstr[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def paint_fill(c, aa=True):
    p = skia.Paint(AntiAlias=aa)
    p.setColor4f(c if isinstance(c, skia.Color4f) else skia.Color4f(*c))
    return p


# ---------------------------------------------------------------- math

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sstep(e0, e1, x):
    """Scalar smoothstep."""
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_in_out(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease_in_out_sine(t):
    t = min(1.0, max(0.0, t))
    return 0.5 - 0.5 * np.cos(np.pi * t)


def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = min(1.0, max(0.0, t))
    return t ** 3


# ---------------------------------------------------------------- noise

def value_noise(h, w, cell, rng, wrap_x=False):
    """Smooth (cubic-spline) value noise in [-1, 1] with feature size ~cell px."""
    gh = int(np.ceil(h / cell)) + 4
    gw = int(np.ceil(w / cell)) + (0 if wrap_x else 4)
    grid = rng.uniform(-1, 1, (gh, gw)).astype(np.float32)
    if wrap_x:
        # Tileable horizontally: spline over a wrapped grid, sampled exactly one period.
        ys = np.arange(h, dtype=np.float32) / cell + 1.5
        xs = np.arange(w, dtype=np.float32) * (gw / w)
        yy, xx = np.meshgrid(ys, xs, indexing='ij')
        out = ndimage.map_coordinates(grid, [yy, xx], order=3, mode='grid-wrap')
    else:
        z = ndimage.zoom(grid, cell, order=3, mode='reflect')
        out = z[int(cell * 1.5):int(cell * 1.5) + h, int(cell * 1.5):int(cell * 1.5) + w]
    return out.astype(np.float32) * 1.4


def fbm(h, w, cell, rng, octaves=4, gain=0.5, wrap_x=False):
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        if cell < 1.5:
            break
        out += amp * value_noise(h, w, cell, rng, wrap_x=wrap_x)
        tot += amp
        amp *= gain
        cell /= 2.0
    return out / max(tot, 1e-6)


def blur(a, sigma):
    if a.ndim == 3:
        return ndimage.gaussian_filter(a, (sigma, sigma, 0))
    return ndimage.gaussian_filter(a, sigma)


# ---------------------------------------------------------------- paths

def smooth_path(points, closed=True, tension=0.5):
    """Catmull-Rom spline through points -> skia.Path of cubic segments."""
    pts = [tuple(map(float, p)) for p in points]
    n = len(pts)
    path = skia.Path()
    if n < 2:
        return path
    path.moveTo(*pts[0])
    segs = n if closed else n - 1
    for i in range(segs):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[0]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[-1]
        k = tension / 3.0 * 2.0
        c1 = (p1[0] + (p2[0] - p0[0]) * k / 2, p1[1] + (p2[1] - p0[1]) * k / 2)
        c2 = (p2[0] - (p3[0] - p1[0]) * k / 2, p2[1] - (p3[1] - p1[1]) * k / 2)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        path.close()
    return path


def poly_path(points, closed=True):
    path = skia.Path()
    path.moveTo(*map(float, points[0]))
    for p in points[1:]:
        path.lineTo(*map(float, p))
    if closed:
        path.close()
    return path


def mask_from_path(path, w, h, aa=True):
    """Rasterise a path into a float alpha mask (h, w)."""
    s = surface(w, h)
    c = s.getCanvas()
    c.drawPath(path, paint_fill((1, 1, 1, 1), aa))
    return to_array(s)[..., 3]
