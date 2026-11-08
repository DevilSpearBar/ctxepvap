#!/usr/bin/env node
// Synthesises the soundtrack (music-box waltz in A minor, wind, soil rumble, sparkles) -> out/music.wav
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SR = 44100, DUR = 10, N = SR * DUR;
const out = path.join(path.dirname(fileURLToPath(import.meta.url)), 'out');
const dryL = new Float32Array(N), dryR = new Float32Array(N);
const sendL = new Float32Array(N), sendR = new Float32Array(N);
const midi = m => 440 * 2 ** ((m - 69) / 12);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ramp = (t, a, b) => clamp((t - a) / (b - a));
const smooth = u => u * u * (3 - 2 * u);
let seed = 20051;
const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };

function add(i, l, r, send) {
  dryL[i] += l; dryR[i] += r;
  sendL[i] += l * send; sendR[i] += r * send;
}

// Tuned-bar / music-box tine: inharmonic partials [ratio, level, decay scale].
const TINE = [[1, 1, 1], [2.76, 0.28, 0.45], [5.4, 0.1, 0.22]];
const PLUCK = [[1, 1, 1], [2, 0.3, 0.5], [3, 0.1, 0.3]];
function voice(t0, note, amp, { pan = 0, decay = 1.2, send = 0.4, partials = TINE } = {}) {
  const f = midi(note), start = Math.floor(t0 * SR);
  if (start >= N) return;
  const len = Math.min(N - start, Math.floor(SR * decay * 3.5));
  const gl = Math.cos((pan + 1) * Math.PI / 4), gr = Math.sin((pan + 1) * Math.PI / 4);
  for (let i = 0; i < len; i++) {
    const t = i / SR;
    let s = 0;
    for (const [r, lv, dk] of partials) s += lv * Math.sin(2 * Math.PI * f * r * t) * Math.exp(-t / (decay * dk));
    s *= amp * Math.min(1, t / 0.003);
    add(start + i, s * gl, s * gr, send);
  }
}

// ---- the waltz: Am | Dm | E7 | Am, then a bright A major (Picardy third) as the swarm reaches the moon
const BEAT = 0.75;
const bars = [
  { t: 0, bass: 45, chord: [57, 60, 64], mel: [[0, 69, 1], [1, 72, 1], [2, 76, 1]] },
  { t: 2.25, bass: 50, chord: [57, 62, 65], mel: [[0, 77, 1.5], [1.5, 76, 0.5], [2, 74, 1]] },
  { t: 4.5, bass: 52, chord: [56, 59, 62], mel: [[0, 68, 1], [1, 71, 1], [2, 74, 1]] },
  { t: 6.75, bass: 45, chord: [57, 60, 64], mel: [[0, 72, 1], [1, 76, 1], [2, 81, 1]] },
];
bars.forEach((bar, bi) => {
  voice(bar.t, bar.bass, 0.26, { decay: 0.55, send: 0.2, partials: PLUCK, pan: -0.1 });
  for (const beat of [1, 2]) bar.chord.forEach((n, k) => voice(bar.t + beat * BEAT + k * 0.025, n, 0.1, { decay: 0.7, pan: (k - 1) * 0.35, send: 0.35 }));
  for (const [b, n, d] of bar.mel) voice(bar.t + b * BEAT, n, bi === 3 ? 0.3 : 0.27, { decay: 0.9 + d * 0.5, pan: 0.05, send: 0.55 });
});
voice(9.0, 45, 0.26, { decay: 1.6, send: 0.3, partials: PLUCK });
[57, 61, 64, 69, 73, 76, 81].forEach((n, k) => voice(9.0 + k * 0.07, n, 0.15, { decay: 2.4, pan: (k % 2 ? 1 : -1) * 0.4, send: 0.65 }));

// ---- story sparkles: eyes open, butterfly appears, butterfly lands, dissolve cascade
[[3.35, [76, 81, 88]], [4.0, [81, 84, 88, 93]], [6.0, [88, 93]]].forEach(([t, notes]) =>
  notes.forEach((n, k) => voice(t + k * 0.07, n, 0.085, { decay: 0.8, pan: (k % 2 ? 0.5 : -0.4), send: 0.7 })));
const PENTA = [81, 84, 86, 88, 91, 93];
for (let t = 6.7; t < 9.0;) {
  const u = (t - 6.7) / 2.3;
  voice(t, PENTA[Math.floor(rand() * PENTA.length)], 0.05 + 0.03 * u, { decay: 0.5, pan: rand() * 1.4 - 0.7, send: 0.65 });
  t += 0.42 - 0.34 * u + rand() * 0.06;
}

// ---- pad, wind, soil
{
  const pad = [[45, 0.9], [52, 0.6], [57, 0.5], [64, 0.3]];
  let lpL = 0, lpR = 0, lw1 = 0, lw2 = 0, lw3 = 0, lw4 = 0, rumble = 0;
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    const padEnv = smooth(ramp(t, 0.3, 3.5)) * (0.7 + 0.3 * smooth(ramp(t, 6.5, 9.0)));
    let sp = 0;
    for (const [m, a] of pad) { const f = midi(m); sp += a * (Math.sin(2 * Math.PI * f * t) + Math.sin(2 * Math.PI * f * 1.0032 * t + 1.3)) * 0.5; }
    sp += 0.3 * Math.sin(2 * Math.PI * midi(61) * t) * smooth(ramp(t, 8.4, 9.2));     // the major third arrives
    sp *= 0.03 * padEnv;

    const gust = (0.55 + 0.45 * Math.sin(2 * Math.PI * 0.13 * t + 1)) * (0.35 + 0.65 * smooth(ramp(t, 1, 3))) * (1 + 0.8 * smooth(ramp(t, 6.8, 8.6)));
    const nl = rand() * 2 - 1, nr = rand() * 2 - 1;                 // band-passed noise (~70-600 Hz) = wind
    lw1 += 0.09 * (nl - lw1); lw2 += 0.012 * (nl - lw2);
    lw3 += 0.09 * (nr - lw3); lw4 += 0.012 * (nr - lw4);
    const wl = (lw1 - lw2) * gust * 0.11, wr = (lw3 - lw4) * gust * 0.11;

    rumble += 0.012 * ((rand() * 2 - 1) - rumble);
    const rEnv = smooth(ramp(t, 0.25, 0.9)) * (1 - smooth(ramp(t, 2.2, 3.3)));
    const rm = rumble * 7 * rEnv * 0.12;

    const fade = smooth(ramp(t, 0, 0.8)) * (1 - smooth(ramp(t, 9.4, 10)));
    add(i, (sp + wl + rm) * fade, (sp * 0.97 + wr + rm) * fade, 0.25);
  }
}
for (let k = 0; k < 14; k++) {            // clods hitting the ground
  const t0 = 0.6 + rand() * 2.2, f = 55 + rand() * 40, a = 0.06 + rand() * 0.05, p = rand() * 1.2 - 0.6;
  const start = Math.floor(t0 * SR);
  let lp = 0;
  for (let i = 0; i < SR * 0.25; i++) {
    const t = i / SR, e = Math.exp(-t / 0.05);
    lp += 0.3 * ((rand() * 2 - 1) - lp);
    const s = (Math.sin(2 * Math.PI * f * t) * 0.8 + lp * 0.35) * e * a;
    add(start + i, s * Math.cos((p + 1) * Math.PI / 4), s * Math.sin((p + 1) * Math.PI / 4), 0.15);
  }
}

// ---- Schroeder reverb on the send bus
function reverb(input, combs, fb) {
  const y = new Float32Array(N);
  for (const d of combs) {
    const buf = new Float32Array(d);
    let idx = 0, lp = 0;
    for (let i = 0; i < N; i++) {
      const o = buf[idx];
      lp += 0.35 * (o - lp);
      buf[idx] = input[i] + lp * fb;
      y[i] += o * 0.25;
      idx = (idx + 1) % d;
    }
  }
  for (const d of [225, 556]) {
    const buf = new Float32Array(d);
    let idx = 0;
    for (let i = 0; i < N; i++) {
      const b = buf[idx], w = y[i] + 0.5 * b;
      y[i] = -0.5 * w + b;
      buf[idx] = w;
      idx = (idx + 1) % d;
    }
  }
  return y;
}
const wetL = reverb(sendL, [1557, 1617, 1491, 1422], 0.84);
const wetR = reverb(sendR, [1580, 1640, 1516, 1445], 0.84);

// ---- master: mix, fade, normalise, write 16-bit stereo WAV
const mixL = new Float32Array(N), mixR = new Float32Array(N);
let peak = 0;
for (let i = 0; i < N; i++) {
  const t = i / SR, fade = smooth(ramp(t, 0, 0.6)) * (1 - smooth(ramp(t, 9.45, 10)));
  mixL[i] = (dryL[i] + wetL[i] * 0.55) * fade;
  mixR[i] = (dryR[i] + wetR[i] * 0.55) * fade;
  peak = Math.max(peak, Math.abs(mixL[i]), Math.abs(mixR[i]));
}
const gain = 0.72 / peak;
const pcm = Buffer.alloc(N * 4);
for (let i = 0; i < N; i++) {
  pcm.writeInt16LE(Math.round(clamp(mixL[i] * gain, -1, 1) * 32767), i * 4);
  pcm.writeInt16LE(Math.round(clamp(mixR[i] * gain, -1, 1) * 32767), i * 4 + 2);
}
const head = Buffer.alloc(44);
head.write('RIFF', 0); head.writeUInt32LE(36 + pcm.length, 4); head.write('WAVEfmt ', 8);
head.writeUInt32LE(16, 16); head.writeUInt16LE(1, 20); head.writeUInt16LE(2, 22);
head.writeUInt32LE(SR, 24); head.writeUInt32LE(SR * 4, 28); head.writeUInt16LE(4, 32); head.writeUInt16LE(16, 34);
head.write('data', 36); head.writeUInt32LE(pcm.length, 40);
mkdirSync(out, { recursive: true });
writeFileSync(path.join(out, 'music.wav'), Buffer.concat([head, pcm]));
console.log(`music.wav written (${DUR}s, peak scaled by ${gain.toFixed(2)})`);
