"""Ambience SFX: wind bed, summer cicadas, birds, fūrin wind chime, grass during the run, higurashi."""
import numpy as np

import timeline as T

from .dsp import N, SR, ar, bp, colored, curve, fade_edges, hp, lp, phase, reson, smooth_rand

SHOT = {name.split('_')[0]: (f0 / T.FPS, f1 / T.FPS) for name, f0, f1, _ in T.SHOTS}


def _norm(x, peak=1.0):
    return x * (peak / (np.max(np.abs(x)) + 1e-12))


def wind(r):
    """Stereo wind bed over the whole film: wandering band-pass bank, slow gusting, sky air."""
    look = dict(s1=(0.55, 420, 0.2), s2=(0.5, 520, 0.25), s3=(0.55, 480, 0.25), s4=(0.42, 460, 0.15),
                s5=(1.0, 1200, 1.0), s6=(0.8, 950, 0.7), s7=(0.5, 520, 0.3), s8=(0.42, 450, 0.2),
                s9=(0.3, 360, 0.08))
    pl, pc, pa = [], [], []
    for k, (a, b) in SHOT.items():
        lv, c, ai = look[k]
        for t in (a + 0.1, b - 0.1):
            pl.append((t, lv))
            pc.append((t, np.log2(c)))
            pa.append((t, ai))
    lvl = curve(pl, smooth_hz=2.5)
    cen = curve(pc, smooth_hz=0.8) + smooth_rand(N, 0.3, r, -0.7, 0.7)
    air = curve(pa, smooth_hz=1.5)
    gust = 0.55 + 0.45 * smooth_rand(N, 0.2, r) ** 1.5
    a = colored(N, r, 1.5)
    src = np.stack([a, 0.55 * a + 0.83 * colored(N, r, 1.5)])
    out = np.zeros((2, N))
    for fc in (160, 260, 420, 680, 1100, 1800, 2900):
        out += np.exp(-0.5 * ((np.log2(fc) - cen) / 0.8) ** 2) * reson(src, fc, 2.0)
    out = out / np.std(out) + 0.3 * lp(src, 140) / np.std(lp(src[0], 140))
    out += air * hp(r.standard_normal((2, N)), 3500) * 0.25
    return out * lvl * gust


def cicadas(r, t0, t1, n_bugs=3):
    """Pulsing tymbal buzz around 3.5-6 kHz (summer, aburazemi-like). Stereo, starts at t0."""
    n = int((t1 - t0) * SR)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    for _ in range(n_bugs):
        fc = r.uniform(3600, 5600)
        car = bp(r.standard_normal(n), fc * 0.85, fc * 1.18)
        buzz = (0.5 + 0.5 * np.sin(2 * np.pi * r.uniform(140, 220) * t)) ** 2
        pulse = 0.25 + 0.75 * (0.5 + 0.5 * np.sin(2 * np.pi * r.uniform(2.5, 6.0) * t + r.uniform(0, 6.3))) ** 3
        x = _norm(car * buzz * pulse * smooth_rand(n, 0.5, r, 0.25, 1.0))
        p = r.uniform(-0.75, 0.75)
        out[0] += x * np.cos((p + 1) * np.pi / 4)
        out[1] += x * np.sin((p + 1) * np.pi / 4)
    return out * ar(n, 0.4, 0.35)


def bird(r):
    """A short phrase of 2-4 FM chirps."""
    out = np.zeros(int(1.0 * SR))
    t = 0.0
    for _ in range(r.integers(2, 5)):
        dur = r.uniform(0.05, 0.12)
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f0 = r.uniform(2600, 4200)
        f1 = f0 * (r.uniform(1.2, 1.6) if r.random() < 0.6 else r.uniform(0.6, 0.85))
        f = (f0 + (f1 - f0) * (tt / dur) ** 0.6) * (1 + 0.04 * np.sin(2 * np.pi * r.uniform(30, 70) * tt))
        ph = phase(f)
        s = int(t * SR)
        out[s:s + n] += (np.sin(ph) + 0.12 * np.sin(2 * ph)) * np.sin(np.pi * tt / dur) ** 2
        t += dur + r.uniform(0.03, 0.12)
    return _norm(lp(out, 8000))


def furin(r, f0=2350.0):
    """Glass fūrin: clapper strikes it 3 times; beating partial pair, long ring."""
    n = int(4.5 * SR)
    out = np.zeros(n)
    hits = [(0.0, 1.0), (r.uniform(0.17, 0.25), r.uniform(0.45, 0.6)), (r.uniform(0.42, 0.55), r.uniform(0.2, 0.3))]
    parts = ((1.0, 1.0, 3.0), (1.0042, 0.7, 2.8), (2.61, 0.4, 1.3), (2.635, 0.25, 1.1), (4.87, 0.15, 0.5),
             (7.3, 0.06, 0.25))
    for ts, v in hits:
        s = int(ts * SR)
        t = np.arange(n - s) / SR
        y = sum(a * np.exp(-t / d) * np.sin(2 * np.pi * f0 * q * t + r.uniform(0, 0.5)) for q, a, d in parts)
        k = int(0.004 * SR)
        y[:k] += hp(r.standard_normal(k), 5000) * 0.3 * np.exp(-t[:k] / 0.001)
        y *= np.clip(t / 0.0005, 0, 1)
        out[s:] += v * y
    return _norm(fade_edges(out, 0, 300))


def grass_run(r):
    """Continuous grass swishing through the run shot, pulsing with the strides."""
    a, b = SHOT['s2']
    n = int((b - a) * SR)
    t = a + np.arange(n) / SR
    bumps = np.zeros(n)
    for f in T.EVENTS['run_footfalls']:
        bumps += np.exp(-0.5 * ((t - (f - 0.07)) / 0.07) ** 2)
    nz = r.standard_normal((2, n))
    x = bp(nz, 1800, 7500) + 0.4 * bp(nz, 500, 1800)
    x *= 0.6 + 0.4 * smooth_rand(n, 25, r)
    return _norm(x * (0.35 + 0.65 * bumps) * ar(n, 0.12, 0.3))


def higurashi(r, dur=3.0, f_hi=4800.0, f_lo=4100.0):
    """Evening cicada: descending, slowing 'kana-kana-kana' pulse train."""
    n = int((dur + 0.4) * SR)
    out = np.zeros(n)
    t = 0.0
    while t < dur:
        u = t / dur
        f = f_hi + (f_lo - f_hi) * u
        pd = 0.075 + 0.02 * u
        m = int(pd * SR)
        tt = np.arange(m) / SR
        ph = phase(f * (1.06 - 0.09 * tt / pd))
        y = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * (0.75 + 0.25 * np.sin(2 * np.pi * 260 * tt))
        s = int(t * SR)
        out[s:s + m] += y * np.sin(np.pi * tt / pd) ** 1.5 * min(1.0, t / 0.35 + 0.15) * (1 - 0.65 * u)
        t += pd + 0.035 + 0.045 * u
    return _norm(lp(out, 7000))


def render(bus, r, G):
    bus.add(wind(r), 0.0, gain=G['wind'], verb=0.1)
    for (a, b) in (SHOT['s1'], SHOT['s3']):
        bus.add(cicadas(r, a, b), a, gain=G['cicadas'], verb=0.25)
    for t, p in zip(T.EVENTS['birds'], (-0.5, 0.45, -0.2)):
        bus.add(bird(r), t, pan=p, gain=G['birds'], verb=0.35)
    for t in T.EVENTS['wind_chime']:
        bus.add(furin(r), t, pan=0.4, gain=G['chime'], verb=0.35)
    bus.add(grass_run(r), SHOT['s2'][0], gain=G['grass'], verb=0.08)
    for t, p in zip(T.EVENTS['evening_cicadas'], (-0.45, 0.4)):
        bus.add(higurashi(r), t, pan=p, gain=G['higurashi'], verb=0.7)
