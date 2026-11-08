"""Core DSP: constants, filters, noise, envelopes, oscillators, reverb, dynamics, loudness."""
import numpy as np
from scipy import ndimage, signal
from scipy.io import wavfile

import timeline as T

SR = T.SAMPLE_RATE
N = int(round(T.DURATION * SR))          # 2,880,000 samples


def idx(t):
    return int(round(t * SR))


def bar_t(bar, beat=0.0):
    """Absolute time of `beat` (0-based, quarter notes) inside 1-based `bar`."""
    return T.BAR_SEC * (bar - 1) + beat * T.BAR_SEC / T.BEATS_PER_BAR


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def rng(seed):
    return np.random.default_rng(seed)


# ------------------------------------------------------------------ filters
def _fc(f, lo=5.0):
    return float(min(max(f, lo), SR * 0.47))


def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, _fc(fc), 'low', fs=SR, output='sos'), x, axis=-1)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, _fc(fc), 'high', fs=SR, output='sos'), x, axis=-1)


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [_fc(lo), _fc(hi)], 'bandpass', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


def reson(x, fc, q):
    """Constant 0 dB peak-gain resonant band-pass (RBJ cookbook)."""
    w0 = 2 * np.pi * _fc(fc) / SR
    al = np.sin(w0) / (2 * q)
    a = np.array([1 + al, -2 * np.cos(w0), 1 - al])
    return signal.lfilter(np.array([al, 0.0, -al]) / a[0], a / a[0], x, axis=-1)


def peq(x, fc, gain_db, q=1.0):
    """RBJ peaking EQ."""
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * _fc(fc) / SR
    al = np.sin(w0) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w0), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w0), 1 - al / A])
    return signal.lfilter(b / a[0], a / a[0], x, axis=-1)


def onepole(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    return signal.lfilter([1 - a], [1, -a], x, axis=-1)


def smooth(x, fc):
    """Zero-phase low-pass for control curves."""
    sos = signal.butter(2, _fc(fc, 0.05), 'low', fs=SR, output='sos')
    return signal.sosfiltfilt(sos, x, axis=-1)


# ------------------------------------------------------------------ noise / control
def colored(n, r, alpha=1.0, fmin=20.0):
    """Unit-variance noise with a 1/f^alpha power spectrum."""
    X = np.fft.rfft(r.standard_normal(n))
    f = np.maximum(np.fft.rfftfreq(n, 1 / SR), fmin)
    y = np.fft.irfft(X * f ** (-alpha / 2), n)
    return y / (np.std(y) + 1e-12)


def smooth_rand(n, rate, r, lo=0.0, hi=1.0):
    """Cosine-interpolated random curve with about `rate` new values per second."""
    k = int(n / SR * rate) + 3
    pts = r.uniform(lo, hi, k)
    x = np.arange(n) * (rate / SR)
    i = x.astype(np.int64)
    w = 0.5 - 0.5 * np.cos(np.pi * (x - i))
    return pts[i] * (1 - w) + pts[i + 1] * w


def curve(points, n=N, t0=0.0, smooth_hz=None):
    """Piecewise-linear automation from (time, value) points (absolute seconds)."""
    ts, vs = zip(*sorted(points))
    y = np.interp(t0 + np.arange(n) / SR, ts, vs)
    return smooth(y, smooth_hz) if smooth_hz else y


def ar(n, att, rel, hold=None):
    """Raised-cosine attack, sustain until `hold` s, raised-cosine release of `rel` s."""
    t = np.arange(n) / SR
    hold = n / SR - rel if hold is None else hold
    a = np.clip(t / max(att, 1e-4), 0, 1)
    r = np.clip((t - hold) / max(rel, 1e-4), 0, 1)
    return (0.5 - 0.5 * np.cos(np.pi * a)) * (0.5 + 0.5 * np.cos(np.pi * r))


def fade_edges(x, ms_in=2.0, ms_out=10.0):
    n = x.shape[-1]
    for ms, sl in ((ms_in, 0), (ms_out, 1)):
        k = min(int(ms * SR / 1000), n // 2)
        if k > 1:
            w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
            if sl == 0:
                x[..., :k] *= w
            else:
                x[..., n - k:] *= w[::-1]
    return x


# ------------------------------------------------------------------ oscillators
def _farr(f, n):
    return np.full(n, float(f)) if np.ndim(f) == 0 else np.asarray(f, dtype=float)


def phase(f, n=None, ph0=0.0):
    """Running phase in radians for a (possibly time-varying) frequency."""
    return ph0 + 2 * np.pi * np.cumsum(_farr(f, n)) / SR


def saw(f, n=None, ph0=0.0):
    """PolyBLEP band-limited sawtooth."""
    f = _farr(f, n)
    dt = f / SR
    ph = (ph0 + np.cumsum(dt)) % 1.0
    y = 2.0 * ph - 1.0
    m = ph < dt
    u = ph[m] / dt[m]
    y[m] -= u + u - u * u - 1.0
    m = ph > 1.0 - dt
    u = (ph[m] - 1.0) / dt[m]
    y[m] -= u * u + u + u + 1.0
    return y


# ------------------------------------------------------------------ panning / mixing
def pan_gains(p):
    a = (np.clip(p, -1.0, 1.0) + 1.0) * np.pi / 4
    return np.cos(a), np.sin(a)


def mix(buf, x, t0, pan=0.0, gain=1.0):
    """Add mono (pan applied, may be an array) or stereo `x` into `buf` at time t0."""
    s = idx(t0)
    n = x.shape[-1]
    a0, a1 = max(s, 0), min(s + n, buf.shape[-1])
    if a1 <= a0:
        return
    seg = x[..., a0 - s:a1 - s]
    if x.ndim == 1:
        gl, gr = pan_gains(pan)
        if np.ndim(pan):
            gl, gr = gl[a0 - s:a1 - s], gr[a0 - s:a1 - s]
        buf[0, a0:a1] += seg * gl * gain
        buf[1, a0:a1] += seg * gr * gain
    else:
        buf[:, a0:a1] += seg * gain


class Bus:
    """Dry buffer plus two reverb sends (room and big hall)."""

    def __init__(self):
        self.dry = np.zeros((2, N))
        self.verb = np.zeros((2, N))
        self.big = np.zeros((2, N))

    def add(self, x, t0, pan=0.0, gain=1.0, verb=0.0, big=0.0):
        mix(self.dry, x, t0, pan, gain)
        if verb:
            mix(self.verb, x, t0, pan, gain * verb)
        if big:
            mix(self.big, x, t0, pan, gain * big)


# ------------------------------------------------------------------ reverb
def make_ir(rt60=2.5, seed=11, predelay=0.018, length=None, tilt=1.0, n_er=12):
    """Synthetic stereo IR: banded decaying noise (HF dies faster), early reflections."""
    length = length or min(rt60 * 1.25, 7.0)
    n = int(length * SR)
    r = rng(seed)
    t = np.arange(n) / SR
    bands = ((0, 350, 1.2), (350, 1400, 1.0), (1400, 4500, 0.7), (4500, 0, 0.4))
    ir = np.zeros((2, n))
    for ch in range(2):
        w = r.standard_normal(n)
        for lo, hi, mul in bands:
            b = lp(w, hi, 4) if lo == 0 else hp(w, lo, 4) if hi == 0 else bp(w, lo, hi, 2)
            ir[ch] += b * np.exp(-6.91 * t / (rt60 * mul ** tilt))
        ir[ch] *= np.clip(t / 0.06, 0, 1) ** 2
        ref = 3.0 * np.std(ir[ch, idx(0.06):idx(0.12)])
        for _ in range(n_er):
            d = r.uniform(0.005, 0.07)
            ir[ch, idx(d)] += ref * r.uniform(0.3, 1.0) * (1 - d / 0.09) * r.choice([-1, 1])
    pd = idx(predelay)
    ir = np.concatenate([np.zeros((2, pd)), ir[:, :n - pd]], axis=1)
    ir = fade_edges(ir, 0, 200)
    return ir / np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True))


def reverb(x, ir, xfeed=0.25):
    n = x.shape[-1]
    left = x[0] * (1 - xfeed) + x[1] * xfeed
    right = x[1] * (1 - xfeed) + x[0] * xfeed
    return np.stack([signal.oaconvolve(left, ir[0])[:n], signal.oaconvolve(right, ir[1])[:n]])


# ------------------------------------------------------------------ dynamics
def compress(x, thr_db=-20.0, ratio=2.0, att_ms=15.0, rel_ms=250.0, knee=8.0):
    """Gentle stereo-linked RMS compressor (symmetric gain smoothing)."""
    p = onepole(np.max(x * x, axis=0), 1 / (2 * np.pi * att_ms / 1000))
    lvl = 10 * np.log10(np.maximum(p, 1e-12))
    over = lvl - thr_db
    s = 1 - 1 / ratio
    gr = np.where(over <= -knee / 2, 0.0,
                  np.where(over >= knee / 2, s * over, s * (over + knee / 2) ** 2 / (2 * knee)))
    g = onepole(-gr, 1 / (2 * np.pi * rel_ms / 1000))
    return x * 10 ** (g / 20), float(np.max(gr))


def limit(x, ceiling_db=-1.5, look_ms=2.5, rel_ms=120.0):
    """Look-ahead peak limiter: min-filter + box smoothing + slow release."""
    c = 10 ** (ceiling_db / 20)
    g = np.minimum(1.0, c / np.maximum(np.max(np.abs(x), axis=0), 1e-9))
    w = max(2, int(look_ms * SR / 1000))
    g = ndimage.minimum_filter1d(g, 2 * w + 1)
    g = ndimage.uniform_filter1d(g, w)
    # smooth the reduction (1 - g), not g, so the filter state starts at "no reduction"
    g = np.minimum(g, 1 - onepole(1 - g, 1 / (2 * np.pi * rel_ms / 1000)))
    return x * g, float(20 * np.log10(np.min(g)))


# ------------------------------------------------------------------ measurement / io
def k_weight(x):
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=-1), axis=-1)


def block_power(x, block=0.4, hop=0.1, kw=None):
    """Channel-summed K-weighted mean square per block."""
    y = k_weight(x) if kw is None else kw
    p = np.sum(y * y, axis=0) if y.ndim == 2 else y * y
    cs = np.concatenate([[0.0], np.cumsum(p)])
    b, h = int(block * SR), int(hop * SR)
    st = np.arange(0, p.size - b + 1, h)
    return (cs[st + b] - cs[st]) / b, st


def lufs(x):
    """Integrated loudness, ITU-R BS.1770 gating."""
    ms, _ = block_power(x)
    lk = -0.691 + 10 * np.log10(ms + 1e-20)
    g = ms[lk > -70]
    if g.size == 0:
        return -np.inf
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g = ms[(lk > -70) & (lk > rel)]
    return float(-0.691 + 10 * np.log10(g.mean()))


def true_peak_db(x):
    up = signal.resample_poly(x, 4, 1, axis=-1)
    return float(20 * np.log10(np.max(np.abs(up)) + 1e-12))


def write_wav(path, x):
    y = np.round(np.clip(x, -1.0, 32767 / 32768) * 32767.0).astype(np.int16)
    wavfile.write(path, SR, np.ascontiguousarray(y.T))
