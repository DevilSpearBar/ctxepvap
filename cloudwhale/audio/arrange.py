"""Orchestration: turns the score into humanized, timed events per instrument + bus automation."""
import numpy as np

import timeline as T

from . import score as S
from .dsp import bar_t, rng

BEAT = S.BEAT
EIGHTH = BEAT / 2
_r = rng(2024)

PATTERN = {b: 'arp' for b in range(1, 31)}
PATTERN.update({b: 'waltz' for b in (5, 6, 7, 8, 25, 26, 27)})
PATTERN.update({12: 'roll', 13: 'roll', 30: 'final'})
ACC_VEL = dict(zip(range(1, 31), (
    .24, .26, .28, .30, .32, .33, .34, .35, .40, .46, .48, .24, .26, .36, .50,
    .54, .54, .55, .56, .54, .50, .42, .38, .34, .32, .32, .32, .30, .29, .30)))


def hum(t):
    return t + float(np.clip(_r.normal(0, 0.004), -0.008, 0.008))


def hv(v):
    return float(np.clip(v * _r.uniform(0.92, 1.08), 0.05, 1.0))


def x5(seg):
    b = seg['bass']
    return b + 7 if (b + 7) % 12 in S.pcs(seg) else b + 12


def piano_events(segs):
    ev = []
    for seg in segs:
        b, v = seg['bar'], ACC_VEL[seg['bar']]
        t0, t1, U, bass = seg['t0'], seg['t1'], seg['up'], seg['bass']
        k = int(round(seg['beats'] * 2))
        pat = PATTERN[b]
        if pat == 'arp':
            notes = {6: [bass, x5(seg), U[0], U[2], U[3], U[2]], 4: [bass, x5(seg), U[1], U[3]]}.get(k, [bass, U[2]])
            for i, m in enumerate(notes):
                t = t0 + i * EIGHTH
                ev.append((hum(t), m, hv(v * (1.12, .85, .92, .97, 1.0, .9)[i]), t1 - t + 0.25))
        elif pat == 'waltz':
            nb = int(round(seg['beats']))
            ev.append((hum(t0), bass, hv(v * 1.1), t1 - t0 + 0.1))
            for j in (range(1, nb) if nb > 1 else [0]):
                for m in U[:3]:
                    ev.append((hum(t0 + j * BEAT), m, hv(v * 0.75), 0.5))
        elif pat == 'roll':
            for i, m in enumerate([bass] + U):
                t = t0 + i * 0.05
                ev.append((hum(t), m, hv(v * (1.15 if i == 0 else 0.85)), t1 - t + 0.6))
        else:  # final rolled Gmaj9 arpeggio, rings into the fade
            for i, m in enumerate(S.ns('G1 D2 B2 F#3 A3 D4 F#4 A4')):
                ev.append((t0 + i * 0.07, m, hv(v * (1.2 if i == 0 else 0.9)), T.DURATION + 0.5 - t0))
    for lst, vel in ((S.FRAG, .40), (S.THEME_A, .48), (S.BUILD, .55), (S.THEME_A2, .44), (S.CODA, .40)):
        for t, d, m, v in S.mel(lst, vel):
            ev.append((hum(t), m, hv(v), d + 0.08))
            if lst is S.BUILD and t >= bar_t(10):
                ev.append((hum(t), m - 12, hv(v * 0.6), d + 0.08))
    return ev


def merged(segs, bars, voicer):
    """Sustained notes from chord segments; common tones are tied, not re-attacked."""
    notes, active, prev = [], {}, None
    for seg in (s for s in segs if s['bar'] in bars):
        want = set(voicer(seg))
        if prev is not None and abs(seg['t0'] - prev) > 1e-6:
            notes += [(ts, prev, m) for m, ts in active.items()]
            active = {}
        for m in [m for m in active if m not in want]:
            notes.append((active.pop(m), seg['t0'], m))
        for m in want:
            active.setdefault(m, seg['t0'])
        prev = seg['t1']
    return notes + [(ts, prev, m) for m, ts in active.items()]


def _low(m):
    return m + 12 if m < 36 else m


def shaped(lst, v0, v1):
    ev = S.mel(lst, 1.0)
    k = max(len(ev) - 1, 1)
    return [(t, d, m, v * (v0 + (v1 - v0) * i / k)) for i, (t, d, m, v) in enumerate(ev)]


def build():
    segs = S.segments()
    gust0, gust_pk, gust1 = T.EVENTS['gust']
    ev = dict(piano=piano_events(segs))
    ev['strings'] = merged(segs, set(range(5, 12)) | set(range(14, 31)), lambda s: [_low(s['bass'] + 12)] + s['up'])
    ev['trem'] = merged(segs, {12, 13}, lambda s: [m + 12 for m in s['up']])
    ev['choir'] = merged(segs, set(range(16, 22)), lambda s: s['up'])
    ev['horn'] = merged(segs, set(range(16, 22)), lambda s: [_low(s['bass'] + 12), s['up'][0], s['up'][1]])
    ev['bass'] = merged(segs, set(range(14, 25)) | {28, 29, 30}, lambda s: [s['bass']])
    themeb = shaped(S.THEME_B, 0.72, 0.85)
    ev['violins'] = [shaped(S.BUILD, 0.32, 0.72), themeb, shaped(S.THEME_A2, 0.28, 0.32)]
    ev['celli'] = [[(t, d, m - 12, v * 0.6) for t, d, m, v in themeb]]
    ev['flute'] = [S.mel(S.THEME_A, 0.42), shaped(S.BUILD, 0.42, 0.55), shaped(S.DRIFT, 0.62, 0.5)]
    pz = []
    for seg in segs:
        b = seg['bar']
        if b in range(5, 12) or b in range(25, 30):
            v = 0.62 if b >= 9 and b < 12 else 0.55 if b < 9 else 0.45
            pz.append((hum(seg['t0']), _low(seg['bass']), hv(v)))
            if 9 <= b <= 11 and seg['beat'] == 0 and seg['beats'] == 3:
                pz.append((hum(seg['t0'] + 2 * BEAT), _low(seg['bass']) + 12, hv(0.4)))
    ev['pizz'] = pz
    hp_ev = []
    for seg in segs:  # rising 16ths (bars 14-15), falling 8ths (bars 22-24)
        b, pc, k = seg['bar'], S.pcs(seg), int(round(seg['beats']))
        if b in (14, 15):
            lo = {14: S.nm('Eb3'), 15: S.nm('D4')}[b] if seg['beat'] == 0 else hp_ev[-1][1] + 1
            for i, m in enumerate(S.arp_up(pc, lo, 4 * k)):
                v = 0.3 + 0.35 * (seg['t0'] + i * BEAT / 4 - bar_t(14)) / (2 * T.BAR_SEC)
                hp_ev.append((hum(seg['t0'] + i * BEAT / 4), m, hv(v)))
        if b in (22, 23, 24):
            for i, m in enumerate(S.arp_down(pc, S.nm('D6'), 2 * k)):
                hp_ev.append((hum(seg['t0'] + i * EIGHTH), m, hv(0.42 - 0.03 * (b - 22))))
    gl = [m for m in range(S.nm('G3'), S.nm('G6') + 1) if m % 12 in (7, 9, 11, 0, 2, 4, 6)]
    hp_ev += [(bar_t(20) - 0.55 + 0.55 * i / len(gl), m, 0.3 + 0.2 * i / len(gl)) for i, m in enumerate(gl)]
    ev['harp'] = hp_ev
    ce = [(hum(bar_t(b, bt)), S.nm(p), hv(0.5)) for b, bt, p in S.CELESTA_SUSP]
    for seg in (s for s in segs if s['bar'] in (22, 23, 24)):
        for i, m in enumerate(S.arp_down(S.pcs(seg), S.nm('A6'), int(round(seg['beats'])))):
            ce.append((hum(seg['t0'] + i * BEAT + EIGHTH / 2), m, hv(0.32)))
    ev['celesta'] = ce + [(T.EVENTS['hat_catch'] + 0.01, S.nm('B5'), 0.3)]
    sh = T.EVENTS['whale_shimmer']
    ev['glock'] = [(sh + 0.07 * i, S.nm(p), 0.42 - 0.02 * i) for i, p in enumerate(S.SPARKLE)]
    ev['glock'] += [(T.EVENTS['hat_catch'], S.nm('B6'), 0.5), (bar_t(16), S.nm('B6'), 0.25)]
    ev['timp_roll'] = [(bar_t(15), bar_t(16) - bar_t(15) - 0.04, S.nm('D2'), 0.1, 0.5)]
    ev['timp'] = [(bar_t(16), S.nm('G2'), 0.7), (bar_t(20), S.nm('D2'), 0.32)]
    ev['cymbal'] = [(gust0 - 2.2, gust_pk, 2.0), (bar_t(15) + 0.4, bar_t(16), 1.6), (bar_t(19) + 0.6, bar_t(20), 1.5)]
    return ev


def automation():
    """Bus gain breakpoints (seconds -> linear gain)."""
    pk = T.EVENTS['gust'][1]
    return dict(
        strings=[(0, 0), (bar_t(5), 0.0), (bar_t(5) + 0.6, 0.30), (bar_t(9), 0.34), (pk - 0.1, 0.85),
                 (bar_t(11), 0.62), (bar_t(12), 0.45), (bar_t(14), 0.22), (bar_t(16) - 0.15, 0.78),
                 (bar_t(16), 0.85), (bar_t(20), 0.92), (bar_t(22), 0.7), (bar_t(25) - 0.1, 0.38),
                 (bar_t(28), 0.36), (bar_t(30), 0.46), (T.DURATION, 0.46)],
        choir=[(bar_t(16), 0.6), (bar_t(18), 0.8), (bar_t(20), 0.9), (bar_t(22), 0.6), (T.DURATION, 0.6)],
        horn=[(bar_t(16), 0.7), (bar_t(20), 0.85), (bar_t(22), 0.6), (T.DURATION, 0.6)],
        bass=[(bar_t(14), 0.3), (bar_t(16) - 0.1, 0.6), (bar_t(16), 0.9), (bar_t(22), 0.75),
              (bar_t(25), 0.5), (T.DURATION, 0.5)],
    )
