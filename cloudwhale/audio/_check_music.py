"""Smoke test: render the music stem alone and report timing/levels."""
import time

import numpy as np

from . import music
from .dsp import lufs, write_wav

t0 = time.time()
x = music.render()
print(f'music render {time.time() - t0:.1f}s  shape={x.shape}  finite={np.all(np.isfinite(x))}  '
      f'peak={20 * np.log10(np.abs(x).max()):.1f} dB  lufs={lufs(x):.1f}')
write_wav('build/audio_music_test.wav', x / np.abs(x).max() * 0.7)
