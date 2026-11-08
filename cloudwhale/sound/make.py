"""Render, mix and master the soundtrack -> build/score.wav (+ stems, spectrogram).

    .venv/bin/python -m sound.make
"""

import os
import sys
import time
import wave

import numpy as np
from scipy import ndimage, signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import timeline as TL  # noqa: E402
from . import synth as S  # noqa: E402
from .music import render_music  # noqa: E402
from .sfx import render_sfx  # noqa: E402

BUILD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'build')
N = int(round(TL.DURATION * S.SR))
MUSIC_GAIN, SFX_GAIN = 1.0, 0.85


def k_weight(x):
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=-1), axis=-1)


def lufs(x):
    y = k_weight(x)
    blk, hop = int(0.4 * S.SR), int(0.1 * S.SR)
    ms = []
    for i in range(0, y.shape[1] - blk, hop):
        ms.append(np.sum(np.mean(y[:, i:i + blk] ** 2, axis=1)))
    ms = np.array(ms)
    L = -0.691 + 10 * np.log10(ms + 1e-12)
    g = ms[L > -70]
    rel = -0.691 + 10 * np.log10(np.mean(g)) - 10
    g = ms[(L > -70) & (L > rel)]
    return -0.691 + 10 * np.log10(np.mean(g))


def limiter(x, ceiling=0.89, look=0.004, rel=0.08):
    peak = np.max(np.abs(x), axis=0)
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-9))
    w = int(look * S.SR)
    g = ndimage.minimum_filter1d(need, size=2 * w + 1)
    # release smoothing (gain may fall instantly, recovers slowly)
    a = np.exp(-1.0 / (rel * S.SR))
    g = signal.lfilter([1 - a], [1, -a], g - 1.0) + 1.0
    g = np.minimum(g, ndimage.minimum_filter1d(need, size=2 * w + 1))
    g = ndimage.uniform_filter1d(g, size=w)
    return x * g


def write_wav(path, x):
    y = np.clip(x, -1, 1)
    pcm = (y.T * 32767.0).round().astype('<i2')
    with wave.open(path, 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(S.SR)
        f.writeframes(pcm.tobytes())


def spectrogram_png(x, path):
    from PIL import Image, ImageDraw
    mono = x.mean(axis=0)
    f, t, Z = signal.spectrogram(mono, S.SR, nperseg=2048, noverlap=1536)
    Z = 10 * np.log10(Z + 1e-12)
    Wp, Hp = 1440, 420
    fr = np.geomspace(30, 16000, Hp)[::-1]
    rows = np.interp(fr, f, np.arange(len(f)))
    img = ndimage.map_coordinates(Z, [np.repeat(rows[:, None], Wp, 1),
                                      np.repeat(np.linspace(0, Z.shape[1] - 1, Wp)[None, :], Hp, 0)], order=1)
    img = np.clip((img + 110) / 70, 0, 1)
    rgb = (np.stack([img ** 0.8, img ** 1.6, 0.4 + 0.6 * img ** 3], -1) * 255).astype(np.uint8)
    im = Image.fromarray(rgb)
    d = ImageDraw.Draw(im)
    for name, a, b, _ in TL.SHOTS:
        X = a / TL.N_FRAMES * Wp
        d.line([(X, 0), (X, Hp)], fill=(255, 255, 255), width=1)
    for k, v in TL.EVENTS.items():
        for tt in (v if isinstance(v, (list, tuple)) else [v])[:1] if not isinstance(v, list) else v:
            X = tt / TL.DURATION * Wp
            d.line([(X, Hp - 18), (X, Hp)], fill=(255, 220, 0), width=1)
    # loudness strip
    strip = Image.new('RGB', (Wp, 60), (20, 20, 20))
    ds = ImageDraw.Draw(strip)
    for s in range(60):
        seg = x[:, s * S.SR:(s + 1) * S.SR]
        r = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
        h = int(np.clip((r + 50) / 50 * 60, 0, 60))
        ds.rectangle([s * Wp / 60, 60 - h, (s + 1) * Wp / 60 - 2, 60], fill=(120, 200, 255))
    out = Image.new('RGB', (Wp, Hp + 60))
    out.paste(im, (0, 0))
    out.paste(strip, (0, Hp))
    out.save(path)


def main():
    t0 = time.time()
    music = render_music()[:, :N]
    t1 = time.time()
    sfx = render_sfx()[:, :N]
    t2 = time.time()
    hall = S.reverb_ir(2.6, seed=7, damp=6500)
    room = S.reverb_ir(1.8, seed=8, damp=5000)
    music = music * 0.78 + S.convolve_stereo(music, hall) * 0.42
    sfx = sfx * 0.85 + S.convolve_stereo(sfx, room) * 0.25
    mix = MUSIC_GAIN * music + SFX_GAIN * sfx
    mix = S.hp(mix, 28.0, 2)
    mix -= mix.mean(axis=1, keepdims=True)
    # fades per timeline
    t = np.arange(N) / S.SR
    a, b = TL.EVENTS['fade_in']
    c, d = TL.EVENTS['fade_out']
    env = np.clip((t - a) / (b - a), 0, 1) ** 1.5 * np.clip((d - t) / (d - c), 0, 1) ** 1.3
    env = np.maximum(env, np.clip((t - a) / 0.05, 0, 1) * 0.25 * (t < b))
    mix *= env
    # loudness target, then peak limit
    L0 = lufs(mix)
    mix *= 10 ** ((-16.0 - L0) / 20)
    mix = limiter(mix, ceiling=0.88)
    mix[:, -int(0.02 * S.SR):] *= np.linspace(1, 0, int(0.02 * S.SR))
    os.makedirs(BUILD, exist_ok=True)
    write_wav(os.path.join(BUILD, 'score.wav'), mix)
    write_wav(os.path.join(BUILD, 'score_music.wav'), np.clip(music * 0.5, -1, 1))
    write_wav(os.path.join(BUILD, 'score_sfx.wav'), np.clip(sfx * 0.5, -1, 1))
    spectrogram_png(mix, os.path.join(BUILD, 'score_spectrogram.png'))
    peak = 20 * np.log10(np.max(np.abs(mix)) + 1e-12)
    print(f'music {t1 - t0:.1f}s sfx {t2 - t1:.1f}s total {time.time() - t0:.1f}s')
    print(f'samples {mix.shape[1]}  peak {peak:.2f} dBFS  loudness {lufs(mix):.1f} LUFS  nan {np.isnan(mix).any()}')
    for name, a_, b_, _ in TL.SHOTS:
        seg = mix[:, int(a_ / 24 * S.SR):int(b_ / 24 * S.SR)]
        print(f'  {name:14s} rms {20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9):6.1f} dB')


if __name__ == '__main__':
    main()
