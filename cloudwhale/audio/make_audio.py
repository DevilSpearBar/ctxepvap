"""Entry point: `python -m audio.make_audio` -> build/audio.wav, stems, spectrogram, report."""
import os
import time

import numpy as np

import timeline as T

from . import analysis as AN
from . import music, sfx_amb, sfx_fx
from .dsp import (N, SR, Bus, compress, hp, limit, lufs, make_ir, reverb, rng, true_peak_db,
                  write_wav)

OUT = 'build'
# ---- stem gain knobs (linear) ----
MUSIC_GAIN = 1.0
SFX_GAIN = 1.0
SFX_G = dict(wind=0.05, cicadas=0.018, birds=0.05, chime=0.06, grass=0.05, higurashi=0.04, steps=0.5,
             gust=0.55, whoosh=0.2, shimmer=0.12, whale=0.4, blow=0.16, sparkle=0.06, catch=0.3, puton=0.14)
TARGET_LUFS = -16.0
CEIL_DBTP = -1.0


def render_sfx():
    bus, r = Bus(), rng(77)
    sfx_amb.render(bus, r, SFX_G)
    sfx_fx.render(bus, r, SFX_G)
    room = reverb(bus.verb, make_ir(1.2, seed=5, predelay=0.01, tilt=1.4))
    hall = reverb(bus.big, make_ir(5.0, seed=9, predelay=0.04, length=6.5))
    return bus.dry + room + hall


def fades():
    t = np.arange(N) / SR
    a0, a1 = T.EVENTS['fade_in']
    b0, b1 = T.EVENTS['fade_out']
    fin = np.clip((t - a0) / (a1 - a0), 0, 1)
    fout = np.clip((b1 - t) / (b1 - b0), 0, 1)
    g = (0.5 - 0.5 * np.cos(np.pi * fin)) * (0.5 - 0.5 * np.cos(np.pi * fout))
    g[t >= b1 - 0.01] = 0.0          # guaranteed digital silence at the end
    return g


def master(mus, sfx):
    pre = hp(MUSIC_GAIN * mus + SFX_GAIN * sfx, 30)
    pre *= 10 ** ((-20.0 - lufs(pre)) / 20)      # fixed reference so the bus compressor stays gentle
    comp, gr = compress(pre, thr_db=-20.0, ratio=1.6, att_ms=25, rel_ms=300, knee=10)
    fd = fades()
    gain = 1.0
    for _ in range(3):  # loudness target with limiter in the loop
        out, lim = limit(comp * gain, ceiling_db=CEIL_DBTP - 0.6)
        out = out * fd
        gain *= 10 ** ((TARGET_LUFS - lufs(out)) / 20)
    out, lim = limit(comp * gain, ceiling_db=CEIL_DBTP - 0.6)
    out *= fd
    tp = true_peak_db(out)
    if tp > CEIL_DBTP:
        out *= 10 ** ((CEIL_DBTP - 0.05 - tp) / 20)
    return out, gain, gr, lim


def main():
    t_start = time.time()
    os.makedirs(OUT, exist_ok=True)
    mus = music.render()
    print(f'music rendered   {time.time() - t_start:5.1f}s')
    sfx = render_sfx()
    print(f'sfx rendered     {time.time() - t_start:5.1f}s')
    out, gain, gr, lim = master(mus, sfx)
    for x in (mus, sfx, out):
        assert x.shape == (2, N) and np.all(np.isfinite(x))
    fd = fades()
    stems = {}
    for name, x, g in (('music', mus, MUSIC_GAIN), ('sfx', sfx, SFX_GAIN)):
        s = hp(x * g * gain, 25) * fd
        pk = np.max(np.abs(s))
        trim = min(1.0, 10 ** (-1.0 / 20) / pk)
        stems[name] = s * trim
        write_wav(f'{OUT}/audio_{name}.wav', stems[name])
        print(f'stem {name:5s} peak {20 * np.log10(pk):+5.1f} dBFS before trim (trim {20 * np.log10(trim):+.1f} dB)')
    write_wav(f'{OUT}/audio.wav', out)
    print(f'wrote {OUT}/audio.wav  {time.time() - t_start:5.1f}s')

    # ---------------------------------------------------------------- report
    print(f'\nMASTER: samples={out.shape[1]}  sr={SR}  peak={20 * np.log10(np.abs(out).max()):.2f} dBFS  '
          f'true-peak={true_peak_db(out):.2f} dBTP  LUFS={lufs(out):.2f}  gain={20 * np.log10(gain):+.1f} dB  '
          f'comp max GR={gr:.1f} dB  limiter max GR={-lim:.1f} dB')
    dc = out.mean(axis=1)
    cor = np.corrcoef(out[0], out[1])[0, 1]
    mono = out.mean(axis=0, keepdims=True).repeat(2, axis=0)
    print(f'DC L/R {dc[0]:+.1e}/{dc[1]:+.1e}  L/R corr {cor:.2f}  mono-sum loudness change '
          f'{lufs(mono) - lufs(out):+.1f} LU  last 10 ms max |x| = {np.abs(out[:, -480:]).max():.1e}')
    st = {'mix': out, 'music': stems['music'], 'sfx': stems['sfx']}
    print('\nshot        t0    t1    mix   music   sfx   (ungated K-weighted dB)')
    for nm, a, b, v in AN.section_table(st):
        print(f'{nm:8s} {a:5.1f} {b:5.1f}  ' + '  '.join(f'{x:6.1f}' for x in v))
    E = T.EVENTS
    for label, times in (('run_footfalls', E['run_footfalls']), ('stop_footfalls', E['stop_footfalls']),
                         ('stop_feet_together', [E['stop_feet_together']]), ('hat_catch', [E['hat_catch']]),
                         ('hat_put_on', [E['hat_put_on']]), ('whale_blow', [E['whale_blow']])):
        o, s = AN.onsets(stems['sfx'], times)
        print(f'onsets {label:18s} n={len(o):2d}  mean {o.mean():+5.1f} ms  max|off| {np.abs(o).max():4.1f} ms  '
              f'min strength {s.min():5.1f}x median')
    AN.spectrogram_png(out, st, f'{OUT}/audio_spectrogram.png')
    print(f'\ndone in {time.time() - t_start:.1f}s')


if __name__ == '__main__':
    main()
