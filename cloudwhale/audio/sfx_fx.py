"""Event SFX: footfalls, gust + leaves, whooshes, whale shimmer/calls/blow, hat sparkle/catch/put-on."""
import numpy as np

import timeline as T

from .dsp import SR, ar, bp, colored, fade_edges, hp, lp, mix, phase, reson, saw, smooth, smooth_rand
from .instruments import bell
from .score import nm


def _norm(x, peak=1.0):
    return x * (peak / (np.max(np.abs(x)) + 1e-12))


def footfall(r, weight=1.0, swish=1.0):
    """Grass footstep: muffled thud + earthy contact + grass swish + a few crunches."""
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    nz = r.standard_normal(n)
    thump = np.sin(phase(70 + 55 * np.exp(-t / 0.018))) * np.exp(-t / 0.05) * (1 - np.exp(-t / 0.0025))
    mid = bp(nz, 300, 1200) * np.exp(-t / 0.03) * (1 - np.exp(-t / 0.002))
    sw = bp(nz, 1700, 6500) * np.exp(-t / 0.06) * (1 - np.exp(-t / 0.005))
    crunch = hp(nz * (r.random(n) < 0.006), 2500) * np.exp(-t / 0.045) * 3
    y = weight * (0.9 * thump + 0.35 * mid) + swish * (0.35 * sw + 0.2 * crunch)
    return fade_edges(y, 0.3, 40)


def shuffle(r):
    """Feet coming together: two soft brushes."""
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for ts, v in ((0.0, 1.0), (0.09, 0.7)):
        u = np.clip(t - ts, 0, None)
        y += v * bp(r.standard_normal(n), 1200, 5000) * np.exp(-u / 0.06) * (t >= ts) * (1 - np.exp(-u / 0.008))
    y += 0.4 * footfall(r, 0.6, 0.3)[:n]
    return fade_edges(y, 0.3, 40)


def _band_sweep(src, cen, fcs, q):
    """Moving band-pass approximated by a bank of resonators weighted around log2 centre `cen`."""
    return sum(np.exp(-0.5 * ((np.log2(fc) - cen) / 0.7) ** 2) * reson(src, fc, q) for fc in fcs)


def gust(r):
    """Big wind swell (start, peak, end) + tree-leaf rustle. Stereo, starts at gust start."""
    g0, gp, g1 = T.EVENTS['gust']
    n = int((g1 - g0 + 1.2) * SR)
    t = np.arange(n) / SR
    tp, te = gp - g0, g1 - g0
    rise = np.clip(t / tp, 0, 1)
    rise = rise * rise * (3 - 2 * rise)
    fall = 0.5 + 0.5 * np.cos(np.pi * np.clip((t - tp) / (te - tp + 1.0), 0, 1))
    env = rise * fall * (1 + 0.25 * smooth_rand(n, 3, r, -1, 1))
    a = colored(n, r, 1.2)
    src = np.stack([a, 0.5 * a + 0.87 * colored(n, r, 1.2)])
    cen = np.log2(250) + (np.log2(1500) - np.log2(250)) * env
    w = _band_sweep(src, cen, (150, 250, 420, 700, 1150, 1900, 3100), 1.6)
    w = w / np.std(w) * env + 0.5 * lp(src, 120) / np.std(lp(a, 120)) * env
    leaves = hp(r.standard_normal((2, n)), 2500) * smooth_rand(n, 40, r) ** 6 * (0.3 + 0.7 * smooth_rand(n, 8, r))
    lenv = np.clip((t - 0.15) / tp, 0, 1) ** 1.5 * fall
    out = w / np.max(np.abs(w)) + 0.6 * leaves / np.max(np.abs(leaves)) * lenv
    bal = np.clip(t / te, 0, 1)  # sweeps from left-behind to right, with the hat
    out[0] *= 1.15 - 0.3 * bal
    out[1] *= 0.85 + 0.3 * bal
    return _norm(fade_edges(out, 5, 200))


def whoosh(r, dur, f_lo, f_hi, skew=0.4):
    """Noise whoosh whose band brightens towards the peak at `skew` (fraction of dur). Mono."""
    n = int(dur * SR)
    u = np.arange(n) / n
    env = np.sin(np.pi * u ** (np.log(0.5) / np.log(skew))) ** 2
    cen = np.log2(f_lo) + (np.log2(f_hi) - np.log2(f_lo)) * env
    y = _band_sweep(r.standard_normal(n), cen, np.geomspace(f_lo, f_hi, 7), 3.0) * env
    return _norm(fade_edges(y, 5, 30))


def shimmer(r, dur=2.4, count=28):
    """Rising glock/celesta shimmer + airy sparkle noise. Stereo."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    notes = [nm(p) for p in 'G5 A5 B5 D6 E6 G6 A6 B6 D7 E7 G7'.split()]
    for i in range(count):
        ts = max(0.0, 1.5 * (i / count) ** 1.2 + r.uniform(-0.03, 0.03))
        j = int(np.clip(i / count * len(notes) + r.integers(-1, 2), 0, len(notes) - 1))
        kind = 'glock' if i % 3 else 'celesta'
        mix(out, bell(notes[j], r.uniform(0.25, 0.5), kind, 0.9), ts, pan=r.uniform(-0.7, 0.7))
    air = bp(r.standard_normal((2, n)), 6000, 13000) * (0.7 + 0.3 * np.sin(2 * np.pi * 11 * t))
    out += 0.15 * air * np.clip(t / 1.5, 0, 1) ** 2 * np.exp(-np.clip(t - 1.5, 0, None) / 0.4)
    return _norm(fade_edges(out, 1, 100))


def whale_call(r, dur, traj, shift=1.0):
    """Deep gentle moan: sliding pitch, slow vibrato, oo->aa->oo formants. Mono."""
    n = int((dur + 0.6) * SR)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    f = smooth(np.interp(u, (0, .15, .45, .8, 1), traj), 3.0)
    f = f * (1 + 0.012 * np.sin(2 * np.pi * 4.0 * t) * np.clip(t / 0.6, 0, 1))
    ph = phase(f)
    src = 0.55 * saw(f) + 0.8 * np.sin(ph) + 0.3 * np.sin(0.5 * ph)
    v = np.sin(np.pi * u) ** 1.2
    oo = reson(src, 320 * shift, 4) + 0.45 * reson(src, 750 * shift, 5)
    aa = reson(src, 620 * shift, 4) + 0.6 * reson(src, 1100 * shift, 6) + 0.18 * reson(src, 2500 * shift, 8)
    y = (1 - v) * oo + v * aa + 0.6 * lp(src, 220) + 0.06 * np.sin(4.02 * ph) * v
    y *= ar(n, 0.45, 0.9, hold=dur - 0.3) * (1 + 0.1 * np.sin(2 * np.pi * 0.9 * t))
    return _norm(y)


def blow(r, dur=2.4):
    """Whale's breathy mist puff: bright breath that darkens, plus a soft low whump. Stereo."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = r.standard_normal((2, n))
    env = (1 - np.exp(-t / 0.06)) * np.exp(-t / 0.55)
    y = (bp(nz, 900, 5000) * np.exp(-t / 0.35) + 1.5 * lp(nz, 350)) * env
    y += np.sin(2 * np.pi * 48 * t) * np.exp(-t / 0.25) * (1 - np.exp(-t / 0.01)) * 0.8 * np.std(y)
    return _norm(fade_edges(y, 2, 200))


def sparkle(r, count=6):
    out = np.zeros((2, int(1.4 * SR)))
    for i in range(count):
        p = 'D7 E7 G7 A7 B7 D8'.split()[r.integers(0, 6)]
        mix(out, bell(nm(p), r.uniform(0.3, 0.6), 'glock', 1.0), 0.05 * i + r.uniform(0, 0.03),
            pan=r.uniform(-0.5, 0.5))
    return _norm(out)


def straw(r, dur=0.35, bumps=((0.0, 1.0),), lo=900, hi=3500, tau=0.025):
    """Straw-hat contact: filtered noise bumps + crackle + tiny thump."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = r.standard_normal(n)
    y = np.zeros(n)
    for ts, v in bumps:
        u = np.clip(t - ts, 0, None)
        e = np.exp(-u / tau) * (1 - np.exp(-u / 0.002)) * (t >= ts)
        y += v * (bp(nz, lo, hi) * e + 0.8 * hp(nz * (r.random(n) < 0.01), 3000) * e
                  + 0.4 * np.sin(2 * np.pi * 140 * u) * e)
    return _norm(fade_edges(y, 0.3, 40))


def render(bus, r, G):
    E = T.EVENTS
    k = 0
    for t in E['run_footfalls']:
        bus.add(footfall(r, r.uniform(0.9, 1.1), r.uniform(0.85, 1.15)), t, pan=0.18 if k % 2 == 0 else -0.18,
                gain=G['steps'] * r.uniform(0.9, 1.05), verb=0.05)
        k += 1
    for t, wgt, sw in zip(E['stop_footfalls'], (1.0, 1.05, 1.1, 0.9), (0.9, 0.8, 0.7, 0.5)):
        bus.add(footfall(r, wgt, sw), t, pan=0.15 if k % 2 == 0 else -0.15, gain=G['steps'], verb=0.05)
        k += 1
    bus.add(shuffle(r), E['stop_feet_together'], gain=G['steps'] * 0.5, verb=0.05)
    bus.add(gust(r), E['gust'][0], gain=G['gust'], verb=0.15)
    n = int(0.9 * SR)
    bus.add(whoosh(r, 0.9, 300, 2600, 0.35), E['hat_lift_off'] - 0.15, pan=np.linspace(-0.1, 0.85, n),
            gain=G['whoosh'], verb=0.2)
    for t, (p0, p1) in zip(E['hat_whoosh_sky'], ((0.35, -0.25), (-0.3, 0.35))):
        bus.add(whoosh(r, 1.3, 350, 3000, 0.45), t - 0.4, pan=np.linspace(p0, p1, int(1.3 * SR)),
                gain=G['whoosh'] * 0.7, verb=0.3)
    bus.add(shimmer(r), E['whale_shimmer'], gain=G['shimmer'], verb=0.4, big=0.3)
    for (a, b), traj, sh, g, p in ((E['whale_call_1'], (78, 92, 135, 90, 64), 1.0, 1.0, -0.1),
                                   (E['whale_call_2'], (98, 115, 165, 112, 80), 1.15, 0.72, 0.15)):
        bus.add(whale_call(r, b - a, traj, sh), a, pan=p, gain=G['whale'] * g, verb=0.1, big=0.9)
    bus.add(blow(r), E['whale_blow'], gain=G['blow'], verb=0.25, big=0.4)
    bus.add(sparkle(r), E['hat_lands_on_whale'], gain=G['sparkle'], verb=0.4, big=0.2)
    bus.add(straw(r), E['hat_catch'], pan=0.05, gain=G['catch'], verb=0.12)
    bus.add(bell(nm('E7'), 0.5, 'glock', 1.6, r), E['hat_catch'] + 0.02, pan=0.1, gain=G['catch'] * 0.25,
            verb=0.4)
    bus.add(straw(r, 0.55, ((0.0, 1.0), (0.18, 0.6)), 1500, 7000, 0.06), E['hat_put_on'], gain=G['puton'],
            verb=0.1)
