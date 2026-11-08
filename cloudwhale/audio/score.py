"""Musical material: 3/4 waltz chord chart with voicings (F major -> G major), themes, motifs."""
import timeline as T

from .dsp import bar_t

BEAT = T.BAR_SEC / T.BEATS_PER_BAR
_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def nm(s):
    """'F#4' / 'Bb1' -> MIDI number (C4 = 60)."""
    acc = s[1:-1]
    return 12 * (int(s[-1]) + 1) + _PC[s[0]] + acc.count('#') - acc.count('b')


def ns(s):
    return [nm(x) for x in s.split()]


# bar -> [(beat, symbol, bass, upper voicing)]; second chords fall on beat 3 (or 2 and 3).
CHART = {
    1: [(0, 'Fmaj9', 'F2', 'A3 C4 E4 G4')],
    2: [(0, 'Bbmaj7#11', 'Bb1', 'F3 A3 D4 E4')],
    3: [(0, 'Fmaj9', 'F2', 'A3 C4 E4 G4')],
    4: [(0, 'Gm7', 'G2', 'Bb3 D4 F4 A4'), (2, 'C7sus4', 'C2', 'Bb3 D4 F4 G4')],
    5: [(0, 'F', 'F2', 'F3 A3 C4 F4')],
    6: [(0, 'Am7', 'A2', 'G3 A3 C4 E4')],
    7: [(0, 'Bbmaj7', 'Bb1', 'F3 A3 D4 F4')],
    8: [(0, 'C7sus4', 'C2', 'Bb3 D4 F4 G4'), (2, 'C7', 'C2', 'Bb3 C4 E4 G4')],
    9: [(0, 'Dm7', 'D2', 'F3 A3 C4 E4')],
    10: [(0, 'Bbmaj7', 'Bb1', 'A3 D4 F4 A4')],
    11: [(0, 'Gm7', 'G2', 'Bb3 D4 F4 A4'), (1, 'A7sus4', 'A2', 'A3 D4 E4 G4'),
         (2, 'A7', 'A2', 'A3 C#4 E4 G4')],
    12: [(0, 'Bbmaj9', 'Bb1', 'D4 F4 A4 C5')],
    13: [(0, 'Gm9', 'G1', 'Bb3 D4 F4 A4'), (2, 'C9sus4', 'C2', 'Bb3 D4 F4 G4')],
    14: [(0, 'Ebmaj7', 'Eb2', 'G3 Bb3 D4 F4')],
    15: [(0, 'D7sus4', 'D2', 'A3 C4 D4 G4'), (2, 'D7', 'D2', 'A3 C4 D4 F#4')],
    16: [(0, 'Gmaj7', 'G1', 'B3 D4 F#4 A4')],
    17: [(0, 'Bm7', 'B1', 'B3 D4 F#4 A4')],
    18: [(0, 'Cmaj7', 'C2', 'B3 D4 E4 G4')],
    19: [(0, 'D/C', 'C2', 'A3 D4 F#4 A4'), (2, 'D', 'D2', 'A3 D4 F#4 A4')],
    20: [(0, 'Bm7', 'B1', 'A3 D4 F#4 B4'), (2, 'Em7', 'E2', 'G3 B3 D4 F#4')],
    21: [(0, 'Am7', 'A1', 'G3 C4 E4 A4')],
    22: [(0, 'Cmaj7', 'C2', 'G3 B3 D4 E4')],
    23: [(0, 'Am7/D', 'D2', 'G3 C4 E4 A4')],
    24: [(0, 'Dsus4', 'D2', 'A3 D4 G4 A4'), (2, 'D', 'D2', 'A3 D4 F#4 A4')],
    25: [(0, 'Gmaj7', 'G2', 'G3 B3 D4 F#4')],
    26: [(0, 'Em9', 'E2', 'G3 B3 D4 F#4')],
    27: [(0, 'Cmaj7', 'C2', 'G3 B3 D4 E4'), (2, 'D', 'D2', 'A3 D4 F#4 A4')],
    28: [(0, 'Bm7', 'B1', 'A3 B3 D4 F#4'), (2, 'Em7', 'E2', 'G3 B3 D4 F#4')],
    29: [(0, 'Am9', 'A1', 'G3 B3 C4 E4'), (2, 'D9sus4', 'D2', 'G3 A3 C4 E4')],
    30: [(0, 'Gmaj9', 'G1', 'F#3 A3 B3 D4')],
}


def segments():
    """Flat list of chord segments with absolute times."""
    out = []
    for b in range(1, 31):
        ch = CHART[b]
        for i, (beat, sym, bass, up) in enumerate(ch):
            end = ch[i + 1][0] if i + 1 < len(ch) else T.BEATS_PER_BAR
            out.append(dict(bar=b, beat=beat, beats=end - beat, t0=bar_t(b, beat), t1=bar_t(b, end),
                            sym=sym, bass=nm(bass), up=ns(up)))
    return out


def pcs(seg):
    return {m % 12 for m in [seg['bass']] + seg['up']}


def arp_up(pc, lo, count):
    out, m = [], lo
    while len(out) < count:
        if m % 12 in pc:
            out.append(m)
        m += 1
    return out


def arp_down(pc, hi, count):
    out, m = [], hi
    while len(out) < count:
        if m % 12 in pc:
            out.append(m)
        m -= 1
    return out


# ------------------------------------------------------------------ melodies: (bar, beat, beats, note)
FRAG = [(3, 0, 1.5, 'A4'), (3, 1.5, .5, 'Bb4'), (3, 2, 1, 'C5'), (4, 0, 2, 'D5'), (4, 2, 1, 'C5')]
THEME_A = [(5, 0, 1.5, 'A4'), (5, 1.5, .5, 'Bb4'), (5, 2, 1, 'C5'),
           (6, 0, 2, 'E5'), (6, 2, .5, 'D5'), (6, 2.5, .5, 'C5'),
           (7, 0, 1.5, 'D5'), (7, 1.5, .5, 'C5'), (7, 2, .5, 'Bb4'), (7, 2.5, .5, 'A4'),
           (8, 0, 2, 'G4'), (8, 2, 1, 'C5')]
BUILD = [(9, 0, 1.5, 'F5'), (9, 1.5, .5, 'E5'), (9, 2, 1, 'D5'),
         (10, 0, 1, 'F5'), (10, 1, 1, 'G5'), (10, 2, 1, 'A5'),
         (11, 0, 1, 'Bb5'), (11, 1, 1, 'A5'), (11, 2, 1, 'G5')]
THEME_B = [(16, 0, 1, 'D5'), (16, 1, 2, 'B5'),
           (17, 0, 1.5, 'A5'), (17, 1.5, .5, 'G5'), (17, 2, 1, 'F#5'),
           (18, 0, 1, 'E5'), (18, 1, 2, 'C6'),
           (19, 0, 1, 'B5'), (19, 1, 2, 'A5'),
           (20, 0, 2, 'D6'), (20, 2, 1, 'B5'),
           (21, 0, 1.5, 'C6'), (21, 1.5, .5, 'B5'), (21, 2, 1, 'A5')]
DRIFT = [(22, 0, 2, 'G5'), (22, 2, 1, 'E5'),
         (23, 0, 1.5, 'A5'), (23, 1.5, .5, 'G5'), (23, 2, 1, 'E5'),
         (24, 0, 3, 'D5')]
THEME_A2 = [(25, 0, 1.5, 'B4'), (25, 1.5, .5, 'C5'), (25, 2, 1, 'D5'),
            (26, 0, 2, 'F#5'), (26, 2, .5, 'E5'), (26, 2.5, .5, 'D5'),
            (27, 0, 1.5, 'E5'), (27, 1.5, .5, 'D5'), (27, 2, .5, 'C5'), (27, 2.5, .5, 'B4')]
CODA = [(28, 0, 1.5, 'A4'), (28, 1.5, .5, 'B4'), (28, 2, 1, 'G4'),
        (29, 0, 2, 'E5'), (29, 2, 1, 'D5'), (30, 0, 3, 'B4')]
CELESTA_SUSP = [(12, 0, 'F5'), (12, 1, 'A5'), (12, 2, 'C6'), (13, 0, 'D6'), (13, 1, 'A5'), (13, 2, 'F6')]
SPARKLE = ['D6', 'E6', 'G6', 'A6', 'B6', 'D7', 'E7', 'G7']   # G pentatonic run (whale shimmer)


def mel(lst, vel=0.6, accent=0.06):
    """Melody list -> [(t, dur, midi, vel)] (downbeats slightly accented)."""
    return [(bar_t(b, bt), d * BEAT, nm(p), vel + (accent if bt == 0 else 0.0)) for b, bt, d, p in lst]
