"""Quick smoke test for instruments: timings, levels, NaN check, and a short demo wav."""
import time

import numpy as np

from . import instruments as I
from .dsp import SR, mix, rng, write_wav

r = rng(1)
buf = np.zeros((2, 14 * SR))
tests = [
    ('piano C4 v.5', lambda: I.piano(60, 0.5, 1.5)),
    ('piano F2 v.9', lambda: I.piano(41, 0.9, 2.0)),
    ('piano C7 v.3', lambda: I.piano(96, 0.3, 1.0)),
    ('bowed A4 trem', lambda: I.bowed(69, 2.0, r, trem=0.6)),
    ('bowed F3', lambda: I.bowed(53, 2.0, r)),
    ('violin line', lambda: I.violin_line([(0, .6, 74, .8), (.6, 1.3, 83, .9), (1.9, .7, 81, .8)], r)[0]),
    ('flute line', lambda: I.flute_line([(0, .6, 69, .8), (.6, .4, 70, .8), (1.0, .8, 72, .8)], r)[0]),
    ('choir', lambda: I.choir_note(62, 2.0, r)),
    ('horn', lambda: I.horn_note(55, 2.0, r)),
    ('bass', lambda: I.bass_note(31, 2.0, r)),
    ('pizz F2', lambda: I.pizz(41, 0.8, r)),
    ('harp A4', lambda: I.harp(69, 0.7, r)),
    ('glock B6', lambda: I.bell(95, 0.7, 'glock', r=r)),
    ('celesta C6', lambda: I.bell(84, 0.7, 'celesta')),
    ('timpani D2', lambda: I.timpani(38, 0.8, r)),
    ('timp roll', lambda: I.timp_roll(38, 1.5, 0.2, 0.8, r)),
    ('cymbal', lambda: I.cymbal_swell(3.0, 2.0, r)),
]
pos = 0.0
for name, fn in tests:
    t0 = time.time()
    x = fn()
    dt = time.time() - t0
    ok = np.all(np.isfinite(x))
    print(f'{name:16s} {dt * 1000:7.1f} ms  len={x.shape[-1] / SR:5.2f}s  peak={np.max(np.abs(x)):.3f}'
          f'  rms={np.sqrt(np.mean(x ** 2)):.4f}  dc={np.mean(x):+.4f}  finite={ok}')
    mix(buf, x / (np.max(np.abs(x)) + 1e-9) * 0.5, pos)
    pos += 0.8
write_wav('build/audio_test_instruments.wav', buf)
