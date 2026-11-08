"""Verification: loudness tables, onset checks and an annotated log-frequency spectrogram PNG."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import timeline as T

from .dsp import N, SR, bp, k_weight

SHOTS = [(nm.split('_')[0], f0 / T.FPS, f1 / T.FPS) for nm, f0, f1, _ in T.SHOTS]


def loud_db(x):
    """Ungated K-weighted loudness (LUFS-like) of a stereo segment."""
    y = k_weight(x)
    return float(-0.691 + 10 * np.log10(np.sum(np.mean(y * y, axis=1)) + 1e-20))


def per_second(x):
    y = k_weight(x)
    p = np.sum(y * y, axis=0)[:N].reshape(int(T.DURATION), SR).mean(axis=1)
    return -0.691 + 10 * np.log10(p + 1e-20)


def section_table(stems):
    rows = []
    for nm, a, b in SHOTS:
        s, e = int(a * SR), int(b * SR)
        rows.append((nm, a, b, [loud_db(x[:, s:e]) for x in stems.values()]))
    return rows


def onsets(x, times, pre=0.03, post=0.06):
    """Find the strongest energy rise near each expected time. Returns (offsets_ms, strengths)."""
    y = bp(x.mean(axis=0), 250, 7000)
    h = int(0.0025 * SR)
    e = np.sqrt(np.mean(y[:y.size // h * h].reshape(-1, h) ** 2, axis=1)) + 1e-9
    d = np.maximum(np.diff(20 * np.log10(e), prepend=0.0), 0)
    d = np.convolve(d, np.ones(4), 'same')
    med = np.median(d) + 1e-6
    offs, strg = [], []
    for t in np.atleast_1d(times):
        a, b = int((t - pre) * SR / h), int((t + post) * SR / h)
        i = a + int(np.argmax(d[a:b]))
        offs.append((i * h / SR - t) * 1000)
        strg.append(d[i] / med)
    return np.array(offs), np.array(strg)


_LUT = np.array([(0, 0, 4), (40, 11, 84), (101, 21, 110), (159, 42, 99), (212, 72, 66), (245, 125, 21),
                 (250, 193, 39), (252, 255, 164)], float)


def _cmap(v):
    v = np.clip(v, 0, 1) * (len(_LUT) - 1)
    i = np.minimum(v.astype(int), len(_LUT) - 2)
    w = (v - i)[..., None]
    return (_LUT[i] * (1 - w) + _LUT[i + 1] * w).astype(np.uint8)


def spectrogram_png(mixd, stems, path, W=1800, H=420):
    mono = mixd.mean(axis=0)
    nfft, hop = 4096, N // W
    pad = np.concatenate([np.zeros(nfft // 2), mono, np.zeros(nfft)])
    fr = np.lib.stride_tricks.sliding_window_view(pad, nfft)[::hop][:W] * np.hanning(nfft)
    S = 10 * np.log10(np.abs(np.fft.rfft(fr, axis=1)) ** 2 + 1e-12)
    freqs = np.geomspace(20000, 30, H)
    fi = freqs / (SR / nfft)
    lo = fi.astype(int)
    w = fi - lo
    img = S[:, lo] * (1 - w) + S[:, lo + 1] * w          # (W, H)
    top = img.max()
    rgb = _cmap((img.T - (top - 90)) / 80)
    top_m, strip, bot = 40, 150, 22
    canvas = Image.new('RGB', (W + 50, top_m + H + strip + bot), (12, 12, 16))
    canvas.paste(Image.fromarray(rgb), (50, top_m))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    px = lambda t: 50 + int(t / T.DURATION * W)
    for f in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        y = top_m + int(np.interp(np.log(f), np.log(freqs[::-1]), np.arange(H)[::-1]))
        d.line([(46, y), (50 + W, y)], fill=(70, 70, 80))
        d.text((2, y - 6), f'{f // 1000}k' if f >= 1000 else str(f), fill=(200, 200, 200), font=font)
    for nm, a, b in SHOTS:
        d.line([(px(a), top_m - 4), (px(a), top_m + H + strip)], fill=(255, 255, 255))
        d.text((px(a) + 3, 2), nm, fill=(255, 255, 255), font=font)
    ev = T.EVENTS
    marks = [(t, 'step', (120, 255, 120)) for t in ev['run_footfalls'] + ev['stop_footfalls']]
    for k, c in (('hat_lift_off', (255, 120, 120)), ('whale_shimmer', (150, 220, 255)), ('whale_blow', (200, 200, 255)),
                 ('hat_lands_on_whale', (255, 255, 150)), ('hat_catch', (255, 120, 255)), ('hat_put_on', (255, 180, 255))):
        marks.append((ev[k], k.split('_')[-1], c))
    for k in ('wind_chime', 'birds', 'hat_whoosh_sky', 'evening_cicadas'):
        marks += [(t, k[:5], (255, 220, 120)) for t in ev[k]]
    for k in ('gust', 'whale_call_1', 'whale_call_2'):
        a, b = ev[k][0], ev[k][-1]
        d.rectangle([px(a), top_m - 6, px(b), top_m - 2], fill=(90, 200, 255))
    for i, (t, lab, c) in enumerate(marks):
        d.line([(px(t), top_m - 12), (px(t), top_m + 10)], fill=c)
        if lab != 'step':
            d.text((px(t) + 2, 14 + 10 * (i % 2)), lab, fill=c, font=font)
    y0 = top_m + H
    d.rectangle([50, y0, 50 + W, y0 + strip], fill=(20, 20, 26))
    ly = lambda db: y0 + strip - int(np.clip((db + 50) / 50, 0, 1) * strip)
    for db in (-40, -30, -20, -16, -10):
        d.line([(50, ly(db)), (50 + W, ly(db))], fill=(90, 60, 60) if db == -16 else (50, 50, 60))
        d.text((2, ly(db) - 6), f'{db}', fill=(180, 180, 180), font=font)
    cols = [(240, 240, 240), (100, 160, 255), (255, 160, 60)]
    for (name, x), c, off in zip(stems.items(), cols, (0, 8, 16)):
        for s, v in enumerate(per_second(x)):
            xs = px(s) + 2 + off
            if name == 'mix':
                d.rectangle([px(s) + 1, ly(v), px(s + 1) - 2, y0 + strip], outline=c)
            else:
                d.rectangle([xs, ly(v) - 1, xs + 6, ly(v) + 1], fill=c)
    for s in range(0, 61, 2):
        d.text((px(s) - 4, y0 + strip + 5), str(s), fill=(200, 200, 200), font=font)
    d.text((60, y0 + 3), 'per-second K-weighted loudness: mix=box, music=blue, sfx=orange, red line=-16',
           fill=(200, 200, 200), font=font)
    canvas.save(path)
