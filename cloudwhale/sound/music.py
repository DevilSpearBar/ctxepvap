"""The score: a Hisaishi-flavoured waltz (3/4, 90 BPM, bar = 2 s), F major -> G major.

Shot cuts fall on bar lines (see timeline.SHOTS). Notes are rendered by the
instruments in synth.py and mixed onto a stereo music bus with hall reverb.
"""

import numpy as np

import timeline as TL
from . import synth as S

BEAT = 60.0 / TL.BPM


def T(bar, beat=1.0):
    return ((bar - 1) * 3 + (beat - 1)) * BEAT


# bar -> [(beat, beats, bass, chord tones)]
CH = {
    1: [(1, 3, 41, [53, 57, 60, 64, 67])],
    2: [(1, 3, 46, [50, 57, 62, 64, 69])],
    3: [(1, 3, 41, [53, 57, 60, 64, 67])],
    4: [(1, 2, 43, [55, 58, 62, 65]), (3, 1, 48, [55, 60, 65, 70])],
    5: [(1, 3, 41, [57, 60, 65])],
    6: [(1, 3, 45, [55, 60, 64])],
    7: [(1, 3, 46, [57, 62, 65])],
    8: [(1, 2, 48, [58, 65, 67]), (3, 1, 48, [58, 64, 67])],
    9: [(1, 3, 50, [60, 65, 69])],
    10: [(1, 3, 46, [62, 65, 69])],
    11: [(1, 1, 43, [65, 70, 74]), (2, 1, 45, [67, 74, 76]), (3, 1, 45, [67, 73, 76])],
    12: [(1, 3, 46, [62, 65, 69, 72])],
    13: [(1, 2, 43, [58, 65, 69, 74]), (3, 1, 48, [58, 62, 65, 67])],
    14: [(1, 3, 39, [55, 58, 62, 67])],
    15: [(1, 2, 38, [55, 60, 62, 67]), (3, 1, 38, [54, 60, 62, 66])],
    16: [(1, 3, 43, [55, 59, 62, 66])],
    17: [(1, 3, 47, [57, 62, 66])],
    18: [(1, 3, 48, [59, 64, 67])],
    19: [(1, 2, 48, [57, 62, 66]), (3, 1, 50, [57, 62, 66])],
    20: [(1, 2, 47, [57, 62, 66]), (3, 1, 40, [55, 59, 62])],
    21: [(1, 3, 45, [55, 60, 64])],
    22: [(1, 3, 48, [59, 64, 67])],
    23: [(1, 3, 50, [55, 60, 64])],
    24: [(1, 2, 50, [55, 57, 62]), (3, 1, 50, [54, 57, 62])],
    25: [(1, 3, 43, [59, 62, 66])],
    26: [(1, 3, 40, [55, 59, 62, 66])],
    27: [(1, 2, 48, [59, 64, 67]), (3, 1, 50, [57, 62, 66])],
    28: [(1, 2, 47, [57, 62, 66]), (3, 1, 40, [55, 59, 62])],
    29: [(1, 2, 45, [55, 59, 60, 64]), (3, 1, 50, [60, 64, 67, 69])],
    30: [(1, 3, 43, [59, 62, 66, 69])],
}

INTRO_MEL = [(3, 1, 81, 1), (3, 2, 79, 1), (3, 3, 77, 1), (4, 1, 79, 2), (4, 3, 77, 1)]
THEME_A = [(5, 1, 72, 2), (5, 3, 69, 1), (6, 1, 67, 1), (6, 2, 69, 1), (6, 3, 72, 1),
           (7, 1, 74, 2), (7, 3, 72, 1), (8, 1, 69, 1.5), (8, 2.5, 67, 0.5), (8, 3, 65, 1),
           (9, 1, 69, 1), (9, 2, 72, 1), (9, 3, 77, 1), (10, 1, 76, 2), (10, 3, 74, 1),
           (11, 1, 74, 1), (11, 2, 76, 1), (11, 3, 73, 1), (12, 1, 74, 3)]
HUSH_CEL = [(12, 1, 84, 1), (12, 2, 81, 1), (12, 3, 77, 1), (13, 1, 82, 1), (13, 2, 81, 1), (13, 3, 79, 1)]
THEME_B = [(16, 1, 71, 1), (16, 2, 74, 1), (16, 3, 78, 1), (17, 1, 81, 2), (17, 3, 78, 1),
           (18, 1, 79, 2), (18, 3, 76, 1), (19, 1, 78, 1.5), (19, 2.5, 76, 0.5), (19, 3, 74, 1),
           (20, 1, 74, 2), (20, 3, 71, 1), (21, 1, 72, 1), (21, 2, 76, 1), (21, 3, 81, 1),
           (22, 1, 79, 2), (22, 3, 76, 1), (23, 1, 74, 2), (23, 3, 72, 1), (24, 1, 69, 2), (24, 3, 66, 1)]
THEME_A_G = [(25, 1, 74, 2), (25, 3, 71, 1), (26, 1, 69, 1), (26, 2, 71, 1), (26, 3, 74, 1),
             (27, 1, 76, 2), (27, 3, 74, 1), (28, 1, 71, 1.5), (28, 2.5, 69, 0.5), (28, 3, 67, 1),
             (29, 1, 72, 1), (29, 2, 71, 1), (29, 3, 69, 1), (30, 1, 71, 3)]

# bar -> dynamic level
DYN = {1: .32, 2: .34, 3: .38, 4: .40, 5: .48, 6: .5, 7: .52, 8: .55, 9: .58, 10: .66, 11: .72,
       12: .34, 13: .34, 14: .5, 15: .66, 16: .92, 17: .9, 18: .88, 19: .86, 20: .8, 21: .74,
       22: .66, 23: .6, 24: .55, 25: .5, 26: .5, 27: .48, 28: .46, 29: .42, 30: .4}


class Bus:
    def __init__(self, seconds):
        self.n = int(seconds * S.SR)
        self.buf = np.zeros((2, self.n))

    def add(self, t, mono, p=0.0, gain=1.0):
        i = int(round(t * S.SR))
        if i >= self.n or i < -len(mono):
            return
        st = S.pan(mono * gain, p)
        a, b = max(0, i), min(self.n, i + st.shape[1])
        self.buf[:, a:b] += st[:, a - i:b - i]


def render_music():
    rng = np.random.default_rng(90)
    hum = lambda: rng.normal(0, 0.006)
    dry = Bus(TL.DURATION + 1.0)
    ppan = lambda m: float(np.clip((m - 64) / 40.0, -0.4, 0.4))

    def pno(t, m, beats, v, ring=None):
        dry.add(t + hum(), S.piano(m, beats * BEAT, v * (1 + rng.normal(0, 0.05)), rng,
                                   ring=ring), ppan(m))

    # ---------------- piano accompaniment
    for bar in range(1, 31):
        d = DYN[bar]
        segs = CH[bar]
        if bar <= 4 or bar == 30:
            # flowing broken chords (eighths), pedal through the bar
            bass, tones = segs[0][2], segs[0][3]
            fig = [bass - 12, bass - 5, tones[0], tones[1], tones[2], tones[1]] if bar < 30 else \
                [bass - 12, bass - 5, tones[0], tones[1], tones[2], tones[3] + 12]
            for i, m in enumerate(fig):
                b = i * 0.5 + 1
                seg = [s for s in segs if s[0] <= b < s[0] + s[1]][0]
                if seg is not segs[0] and i >= 2:
                    m = seg[3][min(i - 2, len(seg[3]) - 1)]
                ring = (3.0 - i * 0.5) * BEAT + (2.2 if bar == 30 else 0.3)
                pno(T(bar, b), m, 0.5, d * (0.9 if i == 0 else 0.7), ring=ring)
        elif 12 <= bar <= 15:
            if bar <= 13:
                pno(T(bar), segs[0][2] - 12, 3, d * 0.6, ring=3 * BEAT)
        elif 16 <= bar <= 24:
            for (b0, nb, bass, tones) in segs:
                pno(T(bar, b0), bass - 12, nb, d * 0.8, ring=nb * BEAT)
                arp = (tones + [t + 12 for t in tones])[:int(nb * 2)]
                for i, m in enumerate(arp):
                    pno(T(bar, b0 + 0.5 * (i + 1) - 0.5 + (0.5 if i == 0 else 0)), m, 0.5, d * 0.45,
                        ring=(nb - 0.5 * i) * BEAT)
        else:
            # waltz: bass on 1, chord on 2 and 3
            for (b0, nb, bass, tones) in segs:
                for b in np.arange(b0, b0 + nb):
                    if b == 1 or (b0 > 1 and b == b0):
                        pno(T(bar, b), bass - 12 if bar < 25 else bass, 1, d * 0.75, ring=1.2 * BEAT)
                    else:
                        for m in tones:
                            pno(T(bar, b), m, 0.8, d * 0.38)
    # ---------------- melodies
    for (bar, beat, m, nb) in INTRO_MEL + THEME_A + THEME_A_G:
        v = DYN[bar] * (1.15 if bar != 12 else 0.8)
        pno(T(bar, beat), m, nb, min(1.0, v), ring=nb * BEAT + 0.4)
    for (bar, beat, m, nb) in THEME_A[9:18]:
        dry.add(T(bar, beat) + hum(), S.flute(m + 12, nb * BEAT * 0.95, DYN[bar] * 0.7, rng), -0.2)
    for (bar, beat, m, nb) in THEME_B:
        v = DYN[bar]
        dur = nb * BEAT * 1.02
        dry.add(T(bar, beat), S.strings(m, dur, v, rng, attack=0.12, release=0.7, bright=4800), -0.3)
        dry.add(T(bar, beat), S.strings(m - 12, dur, v * 0.7, rng, attack=0.15, release=0.7, bright=3500), 0.25)
    for (bar, beat, m, nb) in HUSH_CEL:
        dry.add(T(bar, beat), S.celesta(m, 1, 0.5, rng), 0.3)
    # ---------------- strings pad / bass
    for bar in range(5, 31):
        d = DYN[bar]
        for (b0, nb, bass, tones) in CH[bar]:
            t0, dur = T(bar, b0), nb * BEAT
            trem = 9.0 if bar in (12, 13) else 0.0
            top = [m + 12 for m in tones[-2:]] if bar in (12, 13) else tones
            g = 0.35 if bar < 16 else (0.55 if bar < 25 else 0.4)
            for m in top:
                dry.add(t0, S.strings(m, dur, d * g, rng, voices=4, attack=0.4, release=0.9,
                                      tremolo=trem), 0.1 * ((m % 5) - 2))
            if bar not in (12, 13):
                dry.add(t0, S.strings(bass - 12, dur, d * 0.6, rng, voices=3, attack=0.2,
                                      release=0.6, bright=900), 0.05)
            if 5 <= bar <= 11 or 25 <= bar <= 29:
                if b0 == 1:
                    dry.add(T(bar, 1), S.pluck(bass - 12, 0.6, d * 0.9, rng, decay=0.993, bright=0.2), 0.15)
    # ---------------- reveal colours: horns + choir (bars 16-23)
    for bar in range(16, 24):
        d = DYN[bar]
        for (b0, nb, bass, tones) in CH[bar]:
            for m in tones[:3]:
                dry.add(T(bar, b0), S.horn(m - 12, nb * BEAT, d * 0.5, rng), 0.2)
            for m in tones[-2:]:
                for side in (-0.5, 0.5):
                    dry.add(T(bar, b0), S.choir(m, nb * BEAT, d * 0.35, rng), side)
    # ---------------- harp: rising (14-15), falling (21-24)
    for bar in (14, 15):
        for (b0, nb, bass, tones) in CH[bar]:
            ladder = sorted(set(tones + [t + 12 for t in tones] + [t + 24 for t in tones]))
            k = int(nb * 4)
            start = 0 if b0 == 1 else len(ladder) - k
            for i in range(k):
                m = ladder[min(len(ladder) - 1, start + i + (bar - 14) * 2)]
                dry.add(T(bar, b0 + i * 0.25), S.pluck(m, 0.5, 0.55 + 0.03 * i, rng, decay=0.997, bright=0.6,
                                                         ring=1.2), 0.45)
    for bar in range(21, 25):
        for (b0, nb, bass, tones) in CH[bar]:
            ladder = sorted(set([t + 12 for t in tones] + [t + 24 for t in tones]), reverse=True)
            for i in range(int(nb * 2)):
                m = ladder[i % len(ladder)]
                dry.add(T(bar, b0 + i * 0.5), S.pluck(m, 0.4, 0.45, rng, decay=0.997, bright=0.5, ring=1.0), 0.45)
                if i % 2 == 0:
                    dry.add(T(bar, b0 + i * 0.5), S.celesta(m + 12, 0.5, 0.25, rng), 0.25)
    # ---------------- percussion & sparkle
    for i in range(int(3 / 0.083)):
        tt = T(15) + i * 0.083
        dry.add(tt, S.timpani(38, 0.08, 0.15 + 0.5 * i / 36, rng), 0.0)
    dry.add(T(16), S.timpani(31, 0.5, 0.9, rng), 0.0)
    sh = TL.EVENTS['whale_shimmer']
    for i, m in enumerate([79, 83, 86, 90, 91, 95, 98]):
        dry.add(sh + i * 0.07, S.glock(m, 0.5, 0.35, rng), 0.3 - 0.1 * i)
    cat = TL.EVENTS['hat_catch']
    for i, m in enumerate([86, 91, 95]):
        dry.add(cat + i * 0.09, S.glock(m, 0.5, 0.3, rng), 0.25)
    # cymbal swells into the gust and the reveal
    for t_peak, dur, g in ((TL.EVENTS['gust'][1] + 0.4, 2.2, 0.10), (T(16), 2.6, 0.14)):
        n = int(dur * S.SR)
        env = np.linspace(0, 1, n) ** 3
        cy = S.hp(rng.standard_normal(n), 5000) * env * g
        dry.add(t_peak - dur, cy, 0.0)
    return dry.buf
