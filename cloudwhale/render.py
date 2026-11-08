"""Render «Облачный кит»: previews, the full picture, the final mux.

    python render.py preview 10 200 400      # stills + contact sheet in build/preview/
    python render.py video [--workers 4]     # build/picture.mp4 (no audio)
    python render.py mux                     # build/cloudwhale.mp4 (picture + build/audio.wav)
"""

import argparse
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np
import skia

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import timeline as TL  # noqa: E402
from film import shots  # noqa: E402
from film.core import H, W, fbm, surface  # noqa: E402

BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
_POST = {}


def _post_tables():
    if not _POST:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        nx = (xx - W / 2) / (W / 2)
        ny = (yy - H / 2) / (H / 2)
        r = np.sqrt(nx * nx * 0.85 + ny * ny * 1.1)
        vig = 1.0 - 0.20 * np.clip(r - 0.35, 0, None) ** 1.8
        rng = np.random.default_rng(2024)
        paper = 1.0 + 0.010 * fbm(H, W, 3, rng, octaves=2) + 0.006 * fbm(H, W, 40, rng, octaves=2)
        _POST['mul'] = (vig * paper)[..., None].astype(np.float32)
    return _POST['mul']


def fade_at(f):
    T = f / TL.FPS
    a, b = TL.EVENTS['fade_in']
    c, d = TL.EVENTS['fade_out']
    k = 1.0
    if T < b:
        k *= np.clip((T - a) / (b - a), 0, 1) ** 1.5
    if T > c:
        k *= np.clip((d - T) / (d - c), 0, 1) ** 1.2
    return float(k)


def render_frame(f):
    s = surface(W, H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 1))
    shots.draw_frame(c, f)
    a = s.makeImageSnapshot().toarray()
    rgb = a[..., :3].astype(np.float32)
    rgb *= _post_tables()
    k = fade_at(f)
    if k < 1.0:
        rgb *= k
    return np.clip(rgb + 0.5, 0, 255).astype(np.uint8)


def _work(f):
    return f, render_frame(f).tobytes()


def preview(frames, scale=0.25, cols=4):
    from PIL import Image
    out = os.path.join(BUILD, 'preview')
    os.makedirs(out, exist_ok=True)
    thumbs = []
    for f in frames:
        t0 = time.time()
        img = Image.fromarray(render_frame(f))
        img.save(os.path.join(out, f'f{f:04d}.jpg'), quality=92)
        thumbs.append(img.resize((int(W * scale), int(H * scale)), Image.LANCZOS))
        print(f'frame {f} ({shots.shot_of(f)[0]}) {time.time() - t0:.2f}s', flush=True)
    rows = (len(thumbs) + cols - 1) // cols
    tw, th = thumbs[0].size
    sheet = Image.new('RGB', (cols * tw, rows * th), (0, 0, 0))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(os.path.join(out, 'sheet.jpg'), quality=90)


def video(start, end, workers, out_path, crf):
    os.makedirs(BUILD, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{W}x{H}', '-r', str(TL.FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'slow', '-tune', 'animation', '-crf', str(crf),
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    frames = list(range(start, end))
    ctx = mp.get_context('fork')
    with ctx.Pool(workers) as pool:
        for i, (f, buf) in enumerate(pool.imap(_work, frames, chunksize=4)):
            proc.stdin.write(buf)
            if i % 48 == 0:
                el = time.time() - t0
                print(f'{f}/{end}  {el:.0f}s elapsed, {el / (i + 1):.2f}s/frame', flush=True)
    proc.stdin.close()
    proc.wait()
    print(f'done {out_path} in {time.time() - t0:.0f}s', flush=True)


def mux(picture, audio, out_path):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', picture, '-i', audio,
           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
           '-shortest', '-movflags', '+faststart', out_path]
    subprocess.run(cmd, check=True)
    print('muxed', out_path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['preview', 'video', 'mux'])
    ap.add_argument('frames', nargs='*', type=int)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=TL.N_FRAMES)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--crf', type=int, default=18)
    ap.add_argument('--out', default=os.path.join(BUILD, 'picture.mp4'))
    a = ap.parse_args()
    if a.cmd == 'preview':
        preview(a.frames)
    elif a.cmd == 'video':
        video(a.start, a.end, a.workers, a.out, a.crf)
    else:
        mux(os.path.join(BUILD, 'picture.mp4'), os.path.join(BUILD, 'audio.wav'),
            os.path.join(BUILD, 'cloudwhale.mp4'))
