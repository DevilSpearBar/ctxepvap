"""Synthesized orchestral instruments. Every function returns an array starting at the onset."""
import numpy as np

from .dsp import SR, ar, bp, fade_edges, hp, lp, mtof, onepole, pan_gains, phase, saw, smooth_rand

# ------------------------------------------------------------------ piano
_PIANO = {}
VB = (0.3, 0.5, 0.7, 0.9)


def vbucket(v):
    return min(VB, key=lambda b: abs(b - v))


def piano_raw(m, vb, length):
    """Additive piano: inharmonic partials, two-stage decay, detuned unison strings, hammer."""
    key = (m, vb)
    if key in _PIANO and _PIANO[key].size >= int(length * SR):
        return _PIANO[key]
    f0 = float(mtof(m))
    r = np.random.default_rng(5000 + 37 * m + int(vb * 10))
    n = int(length * SR)
    t = (np.arange(n) / SR).astype(np.float32)
    tau = float(np.clip(2.6 * (262.0 / f0) ** 0.6, 0.35, 7.0))
    B = 7e-5 * 2 ** ((m - 48) / 14.0)
    nn = np.arange(1, int(min(18, max(3, 15000 / f0))) + 1)
    fn = nn * f0 * np.sqrt(1 + B * nn ** 2)
    nn, fn = nn[fn < 17000], fn[fn < 17000]
    amp = nn ** -(1.75 - 0.85 * vb) * (0.3 + 0.7 * np.abs(np.sin(np.pi * nn * 0.13)))
    amp /= 1 + (fn / (1100 + 5200 * vb ** 1.5)) ** 2
    tau2 = tau / (1 + (fn / 1700.0) ** 1.25)
    tau1 = 0.11 * tau2 + 0.015
    n_str = 1 if m < 34 else 2 if m < 46 else 3
    dets = [2 ** (c / 1200) for c in r.uniform(-1.0, 1.0, n_str)] if n_str > 1 else [1.0]
    y = np.zeros(n, np.float32)
    for k in range(nn.size):
        w1 = 0.45 if k == 0 else 0.62
        e = w1 * np.exp(-t / np.float32(tau1[k])) + (1 - w1) * np.exp(-t / np.float32(tau2[k]))
        s = np.zeros(n, np.float32)
        for d in dets:
            s += np.sin(np.float32(2 * np.pi * fn[k] * d) * t + np.float32(r.uniform(0, 0.4)))
        y += np.float32(amp[k]) * e * s
    y = y.astype(float)
    y /= np.max(np.abs(y)) + 1e-9
    nh = min(n, int(0.03 * SR))
    ham = bp(r.standard_normal(nh), max(2 * f0, 300), min(12 * f0, 9000))
    ham *= np.exp(-np.arange(nh) / (0.004 * SR))
    y[:nh] += ham / (np.max(np.abs(ham)) + 1e-9) * 0.1 * vb ** 2
    y *= np.clip(np.arange(n) / (0.0015 * SR), 0, 1)
    y *= (1.0 if m < 84 else 0.8) * vb ** 0.9
    _PIANO[key] = y
    return y


def piano(m, vel, dur, rel=0.4):
    """One piano note held for `dur` s (key/pedal), then damped."""
    vb = vbucket(vel)
    raw = piano_raw(m, vb, dur + rel)
    n = min(raw.size, int((dur + rel) * SR))
    x = raw[:n] * (vel / vb)
    d = int(dur * SR)
    if d < n:
        x[d:] *= np.exp(-np.arange(n - d) / (0.09 * SR))
    return fade_edges(x, 0, 15)


# ------------------------------------------------------------------ bowed / sustained
def bowed(m, dur, r, att=0.4, rel=0.8, voices=3, det=7.0, vib=1.0, trem=0.0, spread=0.6):
    """String-section note: detuned PolyBLEP saws, independent delayed vibrato. Stereo."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    f0 = float(mtof(m))
    ve = np.clip((t - 0.25) / 0.7, 0, 1)
    out = np.zeros((2, n))
    for v in range(voices):
        vd = vib * r.uniform(0.0016, 0.003)
        f = f0 * 2 ** (r.uniform(-det, det) / 1200) * (
            1 + vd * ve * np.sin(2 * np.pi * r.uniform(4.6, 6.0) * t + r.uniform(0, 6.3)))
        y = saw(f, ph0=r.uniform())
        if trem:
            y *= 1 - trem * (0.5 + 0.5 * np.cos(2 * np.pi * r.uniform(10.5, 13.0) * t + r.uniform(0, 6.3))) ** 2
        p = spread * (2 * v / (voices - 1) - 1) if voices > 1 else 0.0
        gl, gr = pan_gains(p)
        out[0] += gl * y
        out[1] += gr * y
    return out * (ar(n, att, rel, hold=dur) / voices)


def line_curves(notes, t0, n, glide=0.06, att=0.08):
    """Smoothed pitch (midi), amplitude and time-since-onset for a legato phrase.
    notes: [(t, dur, midi, vel)] in absolute seconds; curves start at t0."""
    t = t0 + np.arange(n) / SR
    st = np.array([x[0] for x in notes])
    du = np.array([x[1] for x in notes])
    k = np.clip(np.searchsorted(st, t, side='right') - 1, 0, len(notes) - 1)
    pm = np.array([x[2] for x in notes], float)[k]
    pm = onepole(pm - pm[0], 1 / (2 * np.pi * glide)) + pm[0]
    vel = np.array([x[3] for x in notes])[k] * (t >= st[0]) * (t < st[k] + du[k])
    a = onepole(vel, 1 / (2 * np.pi * att))
    since = np.maximum(t - st[k], 0)
    a *= 1 + 0.3 * (np.exp(-since / 0.18) - np.exp(-since / 0.025))
    return pm, a, since


def violin_line(notes, r, voices=5, det=8.0, att=0.12):
    """Legato violin-section melody. Returns (stereo, t0)."""
    t0 = notes[0][0] - 0.02
    n = int((notes[-1][0] + notes[-1][1] + 1.2 - t0) * SR)
    t = np.arange(n) / SR
    pm, a, since = line_curves(notes, t0, n, glide=0.07, att=att)
    ve = onepole(np.clip((since - 0.18) / 0.45, 0, 1), 6.0)
    out = np.zeros((2, n))
    for v in range(voices):
        cents = r.uniform(-det, det) + 3 * smooth_rand(n, 1.5, r, -1, 1)
        f = mtof(pm + cents / 100) * (
            1 + r.uniform(0.0022, 0.0038) * ve * np.sin(2 * np.pi * r.uniform(5.0, 6.2) * t + r.uniform(0, 6.3)))
        y = saw(f, ph0=r.uniform())
        gl, gr = pan_gains(-0.55 + 0.35 * v / max(voices - 1, 1))
        out[0] += gl * y
        out[1] += gr * y
    return out * (a / voices), t0


def flute_line(notes, r):
    """Breathy flute: sine + weak harmonics + breath noise + tonguing chiff. Returns (mono, t0)."""
    t0 = notes[0][0] - 0.02
    n = int((notes[-1][0] + notes[-1][1] + 0.8 - t0) * SR)
    t = np.arange(n) / SR
    pm, a, since = line_curves(notes, t0, n, glide=0.035, att=0.05)
    ve = onepole(np.clip((since - 0.3) / 0.5, 0, 1), 6.0)
    ph = phase(mtof(pm) * (1 + 0.0045 * ve * np.sin(2 * np.pi * 5.1 * t)))
    y = np.sin(ph) + 0.2 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph) + 0.02 * np.sin(4 * ph)
    nz = r.standard_normal(n)
    chiff = bp(nz, 2500, 8000) * 0.45 * np.exp(-since / 0.025) * (1 - np.exp(-since / 0.004))
    y = (y + bp(nz, 1500, 7000) * 0.06) * (1 + 0.03 * ve * np.sin(2 * np.pi * 5.1 * t + 0.5)) + chiff
    return y * a, t0


def choir_note(m, dur, r, att=0.8, rel=1.2, voices=4):
    """Raw 'aah' source (detuned saws, slow vibrato); formants are applied on the bus."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    f0 = float(mtof(m))
    out = np.zeros((2, n))
    for v in range(voices):
        f = f0 * 2 ** (r.uniform(-12, 12) / 1200) * (
            1 + r.uniform(0.002, 0.004) * np.sin(2 * np.pi * r.uniform(4.3, 5.6) * t + r.uniform(0, 6.3)))
        y = saw(f, ph0=r.uniform())
        gl, gr = pan_gains(0.7 * (2 * v / (voices - 1) - 1))
        out[0] += gl * y
        out[1] += gr * y
    return out * (ar(n, att, rel, hold=dur) / voices)


def horn_note(m, dur, r, att=0.35, rel=0.8):
    n = int((dur + rel) * SR)
    f0 = float(mtof(m))
    y = sum(saw(f0 * 2 ** (c / 1200), n, r.uniform()) for c in (-4, 4)) * 0.5
    y += 0.7 * np.sin(phase(f0, n))
    return y * ar(n, att, rel, hold=dur)


def bass_note(m, dur, r, att=0.3, rel=0.7):
    n = int((dur + rel) * SR)
    f0 = float(mtof(m))
    y = sum(saw(f0 * 2 ** (c / 1200), n, r.uniform()) for c in (-5, 5)) * 0.5
    y += 0.6 * np.sin(phase(f0, n))
    return y * ar(n, att, rel, hold=dur)


# ------------------------------------------------------------------ plucked (Karplus-Strong)
def ks(f0, dur, bright, t60, r):
    nd = max(2, int(SR / f0 - 0.5))
    fa = SR / (nd + 0.5)
    n_out = int(dur * SR)
    n = int(n_out * f0 / fa) + nd + 4
    x = np.zeros(n)
    burst = onepole(r.uniform(-1, 1, nd), 300 + 12000 * bright ** 2)
    x[:nd] = burst - burst.mean()
    c = 0.5 * 10 ** (-3.0 / (t60 * fa))
    yp = np.zeros(n + nd + 1)
    for s in range(0, n, nd):
        e = min(s + nd, n)
        yp[s + nd + 1:e + nd + 1] = x[s:e] + c * (yp[s + 1:e + 1] + yp[s:e])
    y = np.interp(np.arange(n_out) * (f0 / fa), np.arange(n), yp[nd + 1:])
    return y / (np.max(np.abs(y)) + 1e-9)


def pizz(m, vel, r):
    f0 = float(mtof(m))
    y = ks(f0, 1.3, 0.22 + 0.2 * vel, 0.55 + 0.4 * (110 / f0) ** 0.5, r)
    y = lp(y, 2500)
    y *= np.clip(np.arange(y.size) / (0.004 * SR), 0, 1)
    return fade_edges(y * vel, 0, 200)


def harp(m, vel, r):
    f0 = float(mtof(m))
    y = ks(f0, 3.0, 0.45 + 0.2 * vel, float(np.clip(2.6 * (220 / f0) ** 0.35, 0.8, 4.0)), r)
    y = lp(y, 6000)
    y *= np.clip(np.arange(y.size) / (0.003 * SR), 0, 1)
    return fade_edges(y * vel, 0, 300)


# ------------------------------------------------------------------ percussion
BELLS = {  # inharmonic bar partials: (ratios, amps, decay seconds at ~880 Hz)
    'glock': ((1.0, 2.76, 5.40, 8.93), (1.0, 0.5, 0.25, 0.12), (1.5, 0.55, 0.25, 0.12)),
    'celesta': ((1.0, 2.76, 5.40, 8.93), (1.0, 0.25, 0.08, 0.03), (1.0, 0.35, 0.15, 0.08)),
}


def bell(m, vel, kind='glock', dur=2.5, r=None):
    f0 = float(mtof(m))
    n = int(dur * SR)
    t = np.arange(n) / SR
    ratios, amps, decs = BELLS[kind]
    sc = (880.0 / f0) ** 0.35
    y = np.zeros(n)
    for q, a, d in zip(ratios, amps, decs):
        if f0 * q < 19000:
            y += a * np.exp(-t / (d * sc)) * np.sin(2 * np.pi * f0 * q * t)
    if r is not None and kind == 'glock':
        y[:int(0.01 * SR)] += hp(r.standard_normal(int(0.01 * SR)), 3000) * 0.08 * np.exp(-t[:int(0.01 * SR)] / 0.002)
    y *= np.clip(t / 0.001, 0, 1)
    return fade_edges(y * vel, 0, 50)


def timpani(m, vel, r, dur=2.6):
    f0 = float(mtof(m))
    n = int(dur * SR)
    t = np.arange(n) / SR
    glide = 1 + 0.02 * np.exp(-t / 0.05)
    y = np.zeros(n)
    for q, a, d in zip((1.0, 1.5, 1.99, 2.44, 2.9), (1.0, 0.45, 0.3, 0.18, 0.1), (1.8, 1.0, 0.8, 0.5, 0.35)):
        y += a * np.exp(-t / d) * np.sin(phase(f0 * q * glide))
    y += lp(r.standard_normal(n), 250) * 0.25 * np.exp(-t / 0.03)
    y *= np.clip(t / 0.002, 0, 1)
    return fade_edges(y * vel * (0.6 + 0.4 * vel), 0, 100)


def timp_roll(m, dur, v0, v1, r, rate=13.0):
    """Soft-mallet roll with a crescendo. Stereo, starts at 0."""
    n = int((dur + 2.6) * SR)
    out = np.zeros((2, n))
    k, tt = 0, 0.0
    while tt < dur:
        v = (v0 + (v1 - v0) * (tt / dur) ** 1.5) * r.uniform(0.85, 1.1)
        x = timpani(m, v, r, 2.6)
        s = int(max(0.0, tt + r.uniform(-0.008, 0.008)) * SR)
        gl, gr = pan_gains(0.1 if k % 2 else -0.1)
        e = min(n, s + x.size)
        out[0, s:e] += gl * x[:e - s]
        out[1, s:e] += gr * x[:e - s]
        k += 1
        tt += 1.0 / rate
    return out


def cymbal_swell(t_len, t_peak, r, tail=1.4):
    """Soft-mallet suspended-cymbal swell peaking at t_peak. Stereo."""
    n = int(t_len * SR)
    t = np.arange(n) / SR
    nz = r.standard_normal((2, n))
    y = hp(nz, 3500, 2) + 0.7 * bp(nz, 6000, 11000, 2) + 0.25 * bp(nz, 900, 3000, 2)
    env = np.clip(t / t_peak, 0, 1) ** 3 * np.exp(-np.clip(t - t_peak, 0, None) / tail)
    env *= 1 + 0.12 * np.sin(2 * np.pi * 6.3 * t)
    return fade_edges(y * env, 5, 300)
