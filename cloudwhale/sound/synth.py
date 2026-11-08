"""Small synthesis toolkit: envelopes, filters, reverb and the orchestra's instruments.

Everything is generated from oscillators and noise; no recorded material.
"""

import numpy as np
from scipy import signal

SR = 48000


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def tvec(n):
    return np.arange(n, dtype=np.float64) / SR


def adsr(n, a, d, s, r, curve=1.0):
    """Linear-segment ADSR (seconds); release starts at n - r."""
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = max(1, min(na, n))
    e[:na] = np.linspace(0, 1, na) ** curve
    if nd > 0 and na < n:
        k = min(nd, n - na)
        e[na:na + k] = np.linspace(1, s, nd)[:k]
    if nr > 0:
        k = min(nr, n)
        e[n - k:] *= np.linspace(1, 0, k) ** 1.5
    return e


def fade(n, fin=0.005, fout=0.01):
    e = np.ones(n)
    a, b = max(1, int(fin * SR)), max(1, int(fout * SR))
    e[:min(a, n)] = np.linspace(0, 1, min(a, n))
    e[n - min(b, n):] *= np.linspace(1, 0, min(b, n))
    return e


def lp(x, fc, order=2):
    sos = signal.butter(order, min(fc, SR * 0.45), 'low', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


def hp(x, fc, order=2):
    sos = signal.butter(order, fc, 'high', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, min(hi, SR * 0.45)], 'band', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


def pink(n, rng):
    w = rng.standard_normal(n)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, w) * 3.5


def brown(n, rng):
    y = np.cumsum(rng.standard_normal(n))
    y = hp(y, 20.0, 1)
    return y / (np.max(np.abs(y)) + 1e-9)


def smooth_rand(n, rate_hz, rng):
    """Slow random control curve in [-1, 1]."""
    k = max(4, int(n / SR * rate_hz) + 4)
    pts = rng.uniform(-1, 1, k)
    x = np.linspace(0, k - 3, n)
    return np.interp(x, np.arange(k), pts)


def pan(x, p):
    """Equal-power pan, p in [-1, 1] (scalar or array) -> (2, n)."""
    a = (np.asarray(p) + 1) * np.pi / 4
    return np.vstack([x * np.cos(a), x * np.sin(a)])


def reverb_ir(seconds=2.6, seed=7, damp=5000.0, predelay=0.012):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = tvec(n)
    env = np.exp(-6.9 * t / seconds)
    out = []
    for ch in range(2):
        nz = rng.standard_normal(n) * env
        # high frequencies die faster: blend a darker copy in over time
        dark = lp(nz, damp * 0.35)
        k = np.clip(t / (seconds * 0.6), 0, 1)
        ir = nz * (1 - k) + dark * k * 1.6
        ir = lp(ir, damp)
        pd = int(predelay * SR) + ch * 37
        ir = np.concatenate([np.zeros(pd), ir])[:n]
        for d, g in ((0.019, 0.5), (0.027, 0.4), (0.041, 0.33), (0.053, 0.25)):
            i = int((d + 0.003 * ch) * SR)
            ir[i] += g
        out.append(ir / np.sqrt(np.sum(ir ** 2)))
    return np.array(out)


def convolve_stereo(x, ir):
    """x: (2, n) or (n,); returns (2, n) wet signal (same length)."""
    if x.ndim == 1:
        x = np.vstack([x, x])
    n = x.shape[1]
    return np.vstack([signal.oaconvolve(x[c], ir[c])[:n] for c in range(2)])


# ---------------------------------------------------------------- oscillators
def saw_blep(freq, rng=None, phase0=None):
    """Band-limited sawtooth from an instantaneous-frequency array (PolyBLEP)."""
    dt = freq / SR
    ph0 = (rng.uniform() if rng is not None else 0.0) if phase0 is None else phase0
    ph = (np.cumsum(dt) + ph0) % 1.0
    y = 2.0 * ph - 1.0
    m = ph < dt
    u = ph[m] / dt[m]
    y[m] -= u + u - u * u - 1.0
    m = ph > 1.0 - dt
    u = (ph[m] - 1.0) / dt[m]
    y[m] -= u * u + u + u + 1.0
    return y


def vibrato_freq(f0, n, rng, rate=5.2, depth=0.004, delay=0.25, drift=0.0015):
    t = tvec(n)
    onset = np.clip(t / max(delay, 1e-3), 0, 1)
    v = depth * onset * np.sin(2 * np.pi * (rate + rng.uniform(-0.3, 0.3)) * t + rng.uniform(0, 6.28))
    return f0 * (1 + v + drift * smooth_rand(n, 1.5, rng))


# ---------------------------------------------------------------- instruments
def piano(m, dur, vel, rng, ring=None):
    """Additive piano tone. dur = key-down time; ring = how long to let it sound (pedal)."""
    f0 = float(mtof(m))
    ring = dur if ring is None else max(dur, ring)
    n = int((ring + 0.35) * SR)
    t = tvec(n)
    B = 0.00025 * (f0 / 261.6) ** 0.9 + 0.00005
    T0 = 3.2 * (261.6 / f0) ** 0.55 + 0.5
    out = np.zeros(n)
    bright = 0.55 + 0.6 * vel
    for k in range(1, 18):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        if fk > 11000:
            break
        amp = (1.0 / k ** (1.35 - 0.35 * bright)) * (0.6 + 0.4 * np.cos(k * 0.9))
        Tk = T0 / (1 + 0.45 * (k - 1))
        dec = 0.7 * np.exp(-t / (Tk * 0.18)) + 0.3 * np.exp(-t / Tk)
        det = 1 + rng.uniform(-0.7, 0.7) * 1e-3 * (0.5 if k == 1 else 1)
        ph = rng.uniform(0, 6.28)
        out += amp * dec * (np.sin(2 * np.pi * fk * t + ph) + 0.6 * np.sin(2 * np.pi * fk * det * t + ph * 0.7))
    # hammer knock
    hn = int(0.012 * SR)
    knock = bp(rng.standard_normal(hn), 600, 4000) * np.linspace(1, 0, hn) ** 2 * 0.25 * vel
    out[:hn] += knock
    rel = np.ones(n)
    r0 = int(ring * SR)
    if r0 < n:
        rel[r0:] = np.exp(-np.arange(n - r0) / (0.09 * SR))
    out *= rel * fade(n, 0.002, 0.02)
    return out * (0.25 + 0.75 * vel) * 0.22


def strings(m, dur, vel, rng, voices=5, attack=0.35, release=0.9, bright=3500.0, tremolo=0.0):
    f0 = float(mtof(m))
    n = int((dur + release) * SR)
    out = np.zeros(n)
    for v in range(voices):
        det = 1 + rng.uniform(-1, 1) * 0.0045
        fr = vibrato_freq(f0 * det, n, rng, rate=5.0, depth=0.0035, delay=0.4)
        out += saw_blep(fr, rng)
    out /= voices
    out = lp(out, bright * (0.7 + 0.5 * vel), 2)
    out = lp(out, bright * 1.6, 1)
    env = adsr(n, attack, 0.3, 0.9, release)
    if tremolo:
        tt = tvec(n)
        env *= 1 - 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * tremolo * tt))
    return out * env * vel * 0.28


def choir(m, dur, vel, rng, attack=0.6, release=1.2):
    f0 = float(mtof(m))
    n = int((dur + release) * SR)
    src = np.zeros(n)
    for v in range(4):
        fr = vibrato_freq(f0 * (1 + rng.uniform(-1, 1) * 0.004), n, rng, rate=5.5, depth=0.006, delay=0.5)
        src += saw_blep(fr, rng)
    out = 0
    for fc, bw, g in ((800, 160, 1.0), (1150, 200, 0.6), (2900, 400, 0.18)):
        out = out + bp(src, fc - bw, fc + bw) * g
    out = lp(out, 4000)
    return out * adsr(n, attack, 0.4, 0.85, release) * vel * 0.30


def horn(m, dur, vel, rng, attack=0.25, release=0.6):
    f0 = float(mtof(m))
    n = int((dur + release) * SR)
    fr = vibrato_freq(f0, n, rng, rate=4.8, depth=0.002, delay=0.6)
    x = 0.6 * saw_blep(fr, rng) + 0.4 * saw_blep(fr * 1.003, rng)
    env = adsr(n, attack, 0.3, 0.85, release)
    x = lp(x, 600 + 1400 * vel, 2)
    return x * env * vel * 0.32


def flute(m, dur, vel, rng, release=0.25):
    f0 = float(mtof(m))
    n = int((dur + release) * SR)
    fr = vibrato_freq(f0, n, rng, rate=5.3, depth=0.006, delay=0.35)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    x = np.sin(ph) + 0.18 * np.sin(2 * ph + 0.3) + 0.06 * np.sin(3 * ph)
    breath = bp(rng.standard_normal(n), 1500, 6000) * 0.06
    env = adsr(n, 0.08, 0.1, 0.9, release)
    return (x + breath) * env * vel * 0.18


def bell(m, dur, vel, rng, ratios=(1.0, 2.0, 3.0, 4.16), decay=1.2, bright=1.0):
    f0 = float(mtof(m))
    n = int((decay * 2.5 + 0.05) * SR)
    t = tvec(n)
    out = np.zeros(n)
    for i, r in enumerate(ratios):
        fk = f0 * r
        if fk > 16000:
            continue
        a = (0.9 ** i) / (1 + i * (1.5 - bright))
        out += a * np.exp(-t / (decay / (1 + 0.8 * i))) * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6))
    return out * fade(n, 0.001, 0.05) * vel * 0.2


def celesta(m, dur, vel, rng):
    return bell(m, dur, vel, rng, ratios=(1.0, 2.0, 3.0, 4.2), decay=0.9)


def glock(m, dur, vel, rng):
    return bell(m, dur, vel, rng, ratios=(1.0, 2.76, 5.40, 8.93), decay=1.1, bright=1.2)


def pluck(m, dur, vel, rng, decay=0.996, bright=0.5, ring=None):
    """Karplus-Strong string (harp / pizzicato)."""
    f0 = float(mtof(m))
    N = max(2, int(round(SR / f0)))
    ring = dur if ring is None else ring
    n = int((ring + 0.1) * SR)
    x = np.zeros(n)
    burst = rng.uniform(-1, 1, N)
    burst = lp(burst, 1500 + 6000 * bright, 1)
    x[:N] = burst
    a = np.zeros(N + 2)
    a[0] = 1.0
    a[N] = -decay * 0.5
    a[N + 1] = -decay * 0.5
    y = signal.lfilter([1.0], a, x)
    y *= fade(n, 0.001, 0.08)
    return y / (np.max(np.abs(y)) + 1e-9) * vel * 0.3


def timpani(m, dur, vel, rng):
    f0 = float(mtof(m))
    n = int((dur + 1.2) * SR)
    t = tvec(n)
    f = f0 * (1 + 0.08 * np.exp(-t / 0.05))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / 0.9) + 0.4 * np.sin(1.5 * ph) * np.exp(-t / 0.4)
    x += lp(rng.standard_normal(n), 900) * np.exp(-t / 0.03) * 0.3
    return x * vel * 0.4
