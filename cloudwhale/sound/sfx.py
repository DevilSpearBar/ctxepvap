"""Sound effects and ambience, all synthesized and placed on timeline.EVENTS."""

import numpy as np

import timeline as TL
from . import synth as S
from .music import Bus

E = TL.EVENTS
SR = S.SR


def _env_curve(n, pts):
    """Piecewise-linear envelope from [(t_sec, value), ...] over n samples."""
    ts = np.array([p[0] for p in pts]) * SR
    vs = np.array([p[1] for p in pts])
    return np.interp(np.arange(n), ts, vs)


def wind_bed(rng, n):
    """Stereo wind: two decorrelated pink/brown bands with gusty swells, scene-dependent level."""
    out = np.zeros((2, n))
    t = np.arange(n) / SR
    # scene level: calm land, louder sky, calm sunset
    lvl = np.interp(t, [0, 7.5, 8, 15.5, 16, 18.4, 19.5, 21.5, 22, 26, 30, 38, 48, 54, 60],
                    [.35, .35, .30, .30, .34, .40, 1.0, .55, .45, .70, .75, .60, .40, .26, .20])
    for ch in range(2):
        lo = S.lp(S.brown(n, rng), 500) * 1.2
        mid = S.bp(S.pink(n, rng), 300, 2200) * 0.22
        hiss = S.bp(rng.standard_normal(n), 2500, 7000) * 0.025
        g1 = 0.6 + 0.4 * S.smooth_rand(n, 0.35, rng)
        g2 = 0.5 + 0.5 * S.smooth_rand(n, 0.6, rng)
        out[ch] = (lo * g1 + mid * g2 + hiss * g2) * lvl
    return out * 0.16


def cicadas(rng, n, t0, t1, level=0.03, f=(3800, 6200), pulse=14.0):
    t = np.arange(n) / SR
    x = S.bp(rng.standard_normal(n), *f)
    am = 0.55 + 0.45 * np.sin(2 * np.pi * pulse * t) ** 2
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * t + 1.0)
    gate = np.clip((t - t0) / 1.0, 0, 1) * np.clip((t1 - t) / 1.0, 0, 1)
    return x * am * swell * gate * level


def higurashi(rng, dur=3.2):
    """Evening cicada: a descending, pulsing 'kana-kana-kana' trill."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 4600 - 700 * (t / dur) ** 0.8
    ph = 2 * np.pi * np.cumsum(f) / SR
    car = np.sin(ph) + 0.3 * np.sin(2 * ph)
    rate = 9.5 - 3.0 * t / dur
    am = (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(rate) / SR)) ** 3
    env = np.clip(t / 0.15, 0, 1) * np.exp(-t / (dur * 0.6))
    return car * am * env * 0.05


def chirp(rng, f0, n_notes=4):
    parts = []
    for i in range(n_notes):
        d = rng.uniform(0.05, 0.11)
        n = int(d * SR)
        t = np.arange(n) / SR
        fa, fb = f0 * rng.uniform(0.85, 1.1), f0 * rng.uniform(1.2, 1.6)
        f = fa + (fb - fa) * np.sin(np.pi * t / d)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2
        parts += [x, np.zeros(int(rng.uniform(0.03, 0.09) * SR))]
    return np.concatenate(parts) * 0.05


def furin(rng):
    """Japanese glass wind chime: a few struck inharmonic partials, long ring, a clapper re-strike."""
    out = np.zeros(int(3.6 * SR))
    for k, (dt, v) in enumerate(((0.0, 1.0), (0.23, 0.45), (0.61, 0.3))):
        n = int((3.6 - dt) * SR)
        t = np.arange(n) / SR
        x = np.zeros(n)
        for r, a, d in ((1.0, 1.0, 2.2), (2.32, 0.5, 1.2), (4.25, 0.32, 0.7), (6.63, 0.18, 0.4)):
            fr = 2350 * r * (1 + rng.uniform(-0.002, 0.002))
            x += a * np.exp(-t / d) * np.sin(2 * np.pi * fr * t)
        x[:int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
        i = int(dt * SR)
        out[i:i + n] += x * v
    return out * 0.05


def footstep(rng, soft=1.0):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (70 + 40 * np.exp(-t / 0.01)) * t) * np.exp(-t / 0.025)
    crunch = S.bp(rng.standard_normal(n), 500, 3500) * np.exp(-t / 0.035) * 0.5
    swish = S.bp(rng.standard_normal(n), 2500, 8000) * np.exp(-((t - 0.04) / 0.03) ** 2) * 0.35
    return (thump * 0.8 + crunch + swish) * soft * 0.12


def whoosh(rng, dur, lo=400, hi=3000, peak=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-((t / dur - peak) / 0.22) ** 2)
    a = S.bp(rng.standard_normal(n), lo, hi)
    b = S.bp(rng.standard_normal(n), hi, min(hi * 3, 12000)) * 0.5
    k = t / dur
    return (a * (1 - k) + b * k) * env * 0.12


def rustle(rng, dur, density=1.0):
    n = int(dur * SR)
    x = S.hp(rng.standard_normal(n), 3000)
    cr = (rng.random(n) < 0.004 * density).astype(float)
    cr = S.lp(cr, 6000) * 8
    mod = 0.5 + 0.5 * S.smooth_rand(n, 9, rng)
    return (x * 0.5 + cr) * mod * 0.05


def whale_call(rng, dur, base=88.0, shape=(1.0, 1.45, 1.25, 0.9), level=1.0):
    """Deep, gentle moan: gliding harmonic source through 'oo'/'ah' formants, slow vibrato."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    contour = np.interp(t / dur, np.linspace(0, 1, len(shape)), shape)
    f = base * contour * (1 + 0.012 * np.sin(2 * np.pi * 4.2 * t))
    src = S.saw_blep(f, rng) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR)
    voc = S.bp(src, 180, 420) * 1.0 + S.bp(src, 600, 1000) * 0.45 + S.bp(src, 1900, 2600) * 0.08
    upper = np.sin(2 * np.pi * np.cumsum(f * 4.02) / SR) * 0.12 * contour
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.4
    return (voc + upper) * env * 0.26 * level


def mist_puff(rng, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.55)
    x = S.bp(rng.standard_normal(n), 250, 2500) * 0.7 + S.lp(rng.standard_normal(n), 300) * 0.6
    return x * env * 0.16


def pat(rng):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    x = S.bp(rng.standard_normal(n), 800, 5000) * np.exp(-t / 0.02)
    x += np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.015) * 0.5
    return x * 0.1


def render_sfx():
    rng = np.random.default_rng(31)
    bus = Bus(TL.DURATION + 1.0)
    n = bus.n
    bus.buf += wind_bed(rng, n)
    for lr in (-0.6, 0.6):
        c = cicadas(rng, n, 0.0, 16.5, level=0.022)
        bus.add(0.0, c, lr)
    for tb in E['birds']:
        bus.add(tb, chirp(rng, rng.uniform(2800, 4200), int(rng.integers(3, 6))), rng.uniform(-0.6, 0.6))
    for tc in E['wind_chime']:
        bus.add(tc, furin(rng), 0.35)
    for i, tf in enumerate(E['run_footfalls']):
        bus.add(tf, footstep(rng, rng.uniform(0.8, 1.0)), -0.15 if i % 2 else 0.15)
    for i, tf in enumerate(E['stop_footfalls']):
        bus.add(tf, footstep(rng, 0.9 - 0.12 * i), 0.1 if i % 2 else -0.1)
    bus.add(E['stop_feet_together'], footstep(rng, 0.4), 0.0)
    # grass swishing while running through it
    ra, rb = E['run_footfalls'][0] - 0.2, E['run_footfalls'][-1] + 0.3
    sw = S.bp(rng.standard_normal(int((rb - ra) * SR)), 1800, 7000)
    m = np.arange(len(sw)) / SR
    sw *= (0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * m) ** 2) * np.clip(m / 0.4, 0, 1) * np.clip((rb - ra - m) / 0.4, 0, 1)
    bus.add(ra, sw * 0.03, -0.2)
    bus.add(ra + 0.01, sw[::-1] * 0.02, 0.3)
    # the gust
    gs, gp, ge = E['gust']
    gd = ge - gs + 1.0
    gn = int(gd * SR)
    env = _env_curve(gn, [(0, 0), (gp - gs, 1.0), (gd, 0)]) ** 1.5
    for lr in (-0.5, 0.5):
        g = S.bp(S.pink(gn, rng), 200, 2400) * env * 0.5
        bus.add(gs, g, lr)
        bus.add(gs + 0.15, rustle(rng, gd, 1.6) * env * 3.0, lr * 1.2)
    bus.add(E['hat_lift_off'] - 0.1, whoosh(rng, 1.3, 600, 3500, 0.45), 0.0)
    bus.add(E['hat_lift_off'] + 0.4, whoosh(rng, 1.1, 900, 4500, 0.4) * 0.6, 0.6)
    # sky
    for tw in E['hat_whoosh_sky']:
        bus.add(tw - 0.4, whoosh(rng, 1.2, 400, 2500, 0.45) * 1.2, rng.uniform(-0.3, 0.3))
    sh = E['whale_shimmer']
    sn = int(2.0 * SR)
    shim = S.hp(rng.standard_normal(sn), 7000) * np.sin(np.pi * np.arange(sn) / sn) ** 2 * 0.04
    bus.add(sh - 0.2, shim, 0.2)
    for key, base, lvl in (('whale_call_1', 82.0, 1.0), ('whale_call_2', 104.0, 0.75)):
        a, b = E[key]
        bus.add(a, whale_call(rng, b - a, base, level=lvl), -0.1)
        bus.add(a + 0.35, whale_call(rng, b - a, base * 2.01, shape=(1.0, 1.3, 1.5, 1.0), level=0.25 * lvl), 0.3)
    bus.add(E['hat_lands_on_whale'], pat(rng) * 0.6, 0.0)
    bus.add(E['whale_blow'], mist_puff(rng), 0.1)
    bus.add(E['hat_catch'], pat(rng), 0.05)
    bus.add(E['hat_put_on'], rustle(rng, 0.35, 0.6) * 1.5, 0.0)
    for tc in E['evening_cicadas']:
        bus.add(tc, higurashi(rng), -0.4 if tc < 56 else 0.45)
    return bus.buf
