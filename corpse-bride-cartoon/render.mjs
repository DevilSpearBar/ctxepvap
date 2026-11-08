#!/usr/bin/env node
// Renders scene.html through headless Chrome (DevTools protocol) and encodes the mp4 with ffmpeg.
//   node render.mjs                     full render -> out/corpse-bride.mp4 (muxes out/music.wav if present)
//   node render.mjs --still 2.5 6 9     PNG stills at the given times -> out/stills/
//   node render.mjs --jobs 3            parallel Chrome instances (default 3)
//   node render.mjs --sheet             contact sheet of the finished video -> out/sheet.png
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, 'out');
const W = 1280, H = 720, FPS = 24, DURATION = 10, FRAMES = FPS * DURATION;
const argv = process.argv.slice(2);
const opt = (name, fallback) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : fallback; };

async function openPage() {
  const profile = mkdtempSync(path.join(tmpdir(), 'cb-chrome-'));
  const chrome = spawn('google-chrome', [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--mute-audio',
    '--force-color-profile=srgb', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    `--window-size=${W},${H}`, 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((resolve, reject) => {
    let log = '';
    chrome.stderr.on('data', d => { log += d; const m = log.match(/DevTools listening on (ws:\/\/\S+)/); if (m) resolve(m[1]); });
    chrome.on('exit', code => reject(new Error(`chrome exited early (${code})`)));
    setTimeout(() => reject(new Error('chrome start timeout')), 30000);
  });
  const port = new URL(wsUrl).port;
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));

  let id = 0;
  const pending = new Map();
  const listeners = [];
  ws.addEventListener('message', ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) p.reject(new Error(`${p.method}: ${msg.error.message}`)); else p.resolve(msg.result);
    } else listeners.forEach(fn => fn(msg));
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const i = ++id;
    pending.set(i, { resolve, reject, method });
    ws.send(JSON.stringify({ id: i, method, params }));
  });

  listeners.push(msg => {
    if (msg.method === 'Runtime.exceptionThrown') console.error('page error:', msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') console.error('console.error:', msg.params.args.map(a => a.value ?? a.description).join(' '));
  });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  const loaded = new Promise(resolve => listeners.push(msg => msg.method === 'Page.loadEventFired' && resolve()));
  await send('Page.navigate', { url: pathToFileURL(path.join(here, 'scene.html')).href });
  await loaded;
  await send('Runtime.evaluate', { expression: 'document.fonts.ready.then(() => true)', awaitPromise: true });

  return {
    async frame(t) {
      const r = await send('Runtime.evaluate', { expression: `renderFrame(${t})`, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      return Buffer.from(shot.data, 'base64');
    },
    close() { ws.close(); chrome.kill('SIGKILL'); rmSync(profile, { recursive: true, force: true }); },
  };
}

async function renderJobs(items, jobs) {
  let next = 0, done = 0;
  const started = Date.now();
  await Promise.all(Array.from({ length: Math.min(jobs, items.length) }, async () => {
    const page = await openPage();
    try {
      while (next < items.length) {
        const item = items[next++];
        writeFileSync(item.file, await page.frame(item.t));
        if (++done % 20 === 0 || done === items.length) console.log(`  ${done}/${items.length} frames, ${((Date.now() - started) / 1000).toFixed(0)}s`);
      }
    } finally { page.close(); }
  }));
}

function ffmpeg(args) {
  const r = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args], { stdio: 'inherit' });
  if (r.status !== 0) throw new Error('ffmpeg failed');
}

const jobs = Number(opt('--jobs', 3));
if (argv.includes('--sheet')) {
  ffmpeg(['-i', path.join(OUT, 'corpse-bride.mp4'), '-vf', 'fps=2,scale=384:-1,tile=5x4', '-frames:v', '1', path.join(OUT, 'sheet.png')]);
} else if (argv.includes('--still')) {
  const times = argv.slice(argv.indexOf('--still') + 1).filter(a => !a.startsWith('--')).map(Number);
  const dir = path.join(OUT, 'stills');
  mkdirSync(dir, { recursive: true });
  await renderJobs(times.map(t => ({ t, file: path.join(dir, `s_${t.toFixed(2)}.png`) })), jobs);
} else {
  const dir = path.join(OUT, 'frames');
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  await renderJobs(Array.from({ length: FRAMES }, (_, i) => ({ t: i / FPS, file: path.join(dir, `f${String(i).padStart(4, '0')}.png`) })), jobs);
  const music = path.join(OUT, 'music.wav');
  const withAudio = existsSync(music);
  ffmpeg([
    '-framerate', String(FPS), '-i', path.join(dir, 'f%04d.png'), ...(withAudio ? ['-i', music] : []),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    ...(withAudio ? ['-c:a', 'aac', '-b:a', '192k'] : []), '-t', String(DURATION), path.join(OUT, 'corpse-bride.mp4'),
  ]);
  console.log('done:', path.join(OUT, 'corpse-bride.mp4'));
}
