"""Render the arranged score to a stereo music stem: per-section buses, EQ, automation, hall."""
import numpy as np

from . import arrange as A
from . import instruments as I
from .dsp import N, SR, curve, hp, lp, make_ir, mix, peq, reson, reverb, rng

# Section gains (linear, pre-master) and hall-reverb send levels: the music mix knobs.
GAINS = dict(piano=0.62, strings=0.30, trem=0.26, violins=0.95, celli=0.55, flute=0.32, choir=0.55,
             horn=0.12, bass=0.30, pizz=0.65, harp=0.5, celesta=0.20, glock=0.13, timp=0.30, cymbal=0.05)
SENDS = dict(piano=0.24, strings=0.38, trem=0.5, violins=0.36, celli=0.3, flute=0.32, choir=0.55,
             horn=0.35, bass=0.1, pizz=0.22, harp=0.38, celesta=0.55, glock=0.5, timp=0.3, cymbal=0.4)
HALL_RT60 = 2.5
WET = 1.0


def _bal(x, b):
    """Stereo balance for an already-stereo note (b > 0 leans right)."""
    x[0] *= 1 - b
    x[1] *= 1 + b
    return x


def _piano(ev):
    g = np.zeros((2, N))
    need = {}
    for t, m, v, d in ev:
        k = (m, I.vbucket(v))
        need[k] = max(need.get(k, 0.0), d + 0.4)
    for (m, vb), length in need.items():
        I.piano_raw(m, vb, length)
    for t, m, v, d in ev:
        mix(g, I.piano(m, v, d), t, pan=float(np.clip((m - 62) / 40, -0.45, 0.45)))
    return peq(hp(g, 30), 250, 1.5, 0.8)


def _sustained(notes, fn, pre=0.1):
    g = np.zeros((2, N))
    for t0, t1, m in notes:
        mix(g, fn(m, t1 - t0 + pre), t0 - pre)
    return g


def _lines(phrases, fn, pan=0.0):
    g = np.zeros((2, N))
    for ph in phrases:
        x, t0 = fn(ph)
        mix(g, x, t0, pan=pan)
    return g


def _hits(ev, fn, panf):
    g = np.zeros((2, N))
    for i, (t, m, v) in enumerate(ev):
        mix(g, fn(m, v), t, pan=panf(i, m))
    return g


def render(verbose=True):
    ev, auto = A.build(), A.automation()
    r = rng(31)
    dry, send = np.zeros((2, N)), np.zeros((2, N))
    stats = {}

    def bus(name, g):
        if name in auto:
            g = g * curve(auto[name], smooth_hz=4.0)
        g *= GAINS[name]
        dry[:] += g
        send[:] += SENDS[name] * g
        act = np.abs(g).max(axis=0) > 1e-4
        stats[name] = (20 * np.log10(np.sqrt(np.mean(g[:, act] ** 2)) + 1e-12) if act.any() else -99,
                       20 * np.log10(np.abs(g).max() + 1e-12))

    bus('piano', _piano(ev['piano']))
    bus('strings', lp(hp(_sustained(ev['strings'], lambda m, d: _bal(
        I.bowed(m, d, r, att=0.45, rel=0.9, voices=3, spread=0.5), float(np.clip((60 - m) / 40, -0.3, 0.3)))),
        50), 3500))
    bus('trem', lp(_sustained(ev['trem'], lambda m, d: I.bowed(m, d, r, att=0.6, rel=1.0, voices=4,
                                                               trem=0.65, spread=0.7)), 5000))
    bus('violins', lp(hp(_lines(ev['violins'], lambda p: I.violin_line(p, r)), 150), 4200))
    bus('celli', lp(_lines(ev['celli'], lambda p: I.violin_line(p, r, voices=4)), 2500) * np.array([[0.75], [1.25]]))
    bus('flute', lp(hp(_lines(ev['flute'], lambda p: I.flute_line(p, r), pan=-0.2), 200), 9000))
    ch = _sustained(ev['choir'], lambda m, d: I.choir_note(m, d, r), pre=0.25)
    bus('choir', hp(reson(ch, 800, 6) + 0.7 * reson(ch, 1150, 7) + 0.25 * reson(ch, 2900, 10)
                    + 0.35 * lp(ch, 450), 120))
    bus('horn', lp(hp(_sustained(ev['horn'], lambda m, d: I.horn_note(m, d, r)), 60), 1100))
    bus('bass', lp(hp(_sustained(ev['bass'], lambda m, d: I.bass_note(m, d, r)), 28), 380))
    bus('pizz', hp(_hits(ev['pizz'], lambda m, v: I.pizz(m, v, r), lambda i, m: 0.25), 35))
    bus('harp', _hits(ev['harp'], lambda m, v: I.harp(m, v, r), lambda i, m: -0.35 + (m - 60) / 80))
    bus('celesta', _hits(ev['celesta'], lambda m, v: I.bell(m, v, 'celesta', 2.5), lambda i, m: 0.3))
    bus('glock', _hits(ev['glock'], lambda m, v: I.bell(m, v, 'glock', 2.5, r), lambda i, m: (-0.3, 0.3)[i % 2]))
    tp = _hits(ev['timp'], lambda m, v: I.timpani(m, v, r), lambda i, m: -0.1)
    for t0, d, m, v0, v1 in ev['timp_roll']:
        mix(tp, I.timp_roll(m, d, v0, v1, r), t0)
    bus('timp', tp)
    cy = np.zeros((2, N))
    for t0, tpk, tail in ev['cymbal']:
        mix(cy, I.cymbal_swell(tpk - t0 + 3 * tail, tpk - t0, r, tail), t0)
    bus('cymbal', cy)

    wet = reverb(send, make_ir(HALL_RT60, seed=11))
    out = dry + WET * wet
    if verbose:
        for k, (rm, pk) in stats.items():
            print(f'  music/{k:8s} rms {rm:6.1f} dB  peak {pk:6.1f} dB')
    return out
