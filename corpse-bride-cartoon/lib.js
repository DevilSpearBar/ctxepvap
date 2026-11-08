'use strict';
/* Shared helpers, gradients and filters. Classic scripts share one global scope. */

const W = 1280, H = 720, DURATION = 10, STEP = 1 / 12;      // the puppet is animated "on twos"
const NS = 'http://www.w3.org/2000/svg';
const svg = document.getElementById('stage');
const MOON = { x: 905, y: 215, r: 122 };
const BASE = { x: 470, y: 690 };                             // where the bride rises from
const OUTLINE = '#10162f';

const set = (e, a) => { for (const k in a) e.setAttribute(k, a[k]); return e; };
const el = (tag, a, parent) => { const e = document.createElementNS(NS, tag); if (a) set(e, a); if (parent) parent.appendChild(e); return e; };
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;
const ramp = (t, a, b) => clamp((t - a) / (b - a));
const smooth = u => u * u * (3 - 2 * u);
const easeOut = u => 1 - (1 - u) ** 3;
const easeIO = u => (u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2);
const mixc = (a, b, u) => a.map((v, i) => lerp(v, b[i], u));
const rgb = c => `rgb(${c.map(v => Math.round(v)).join(',')})`;
const n1 = v => (Math.round(v * 10) / 10).toString();
const rad = d => d * Math.PI / 180;

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Catmull-Rom spline through points -> cubic bezier path. cont=true omits the leading "M".
function curve(p, closed = false, cont = false) {
  const n = p.length;
  const at = i => (closed ? p[((i % n) + n) % n] : p[clamp(i, 0, n - 1)]);
  let d = cont ? '' : `M${n1(p[0][0])} ${n1(p[0][1])}`;
  const segs = closed ? n : n - 1;
  for (let i = 0; i < segs; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    d += `C${n1(p1[0] + (p2[0] - p0[0]) / 6)} ${n1(p1[1] + (p2[1] - p0[1]) / 6)} ${n1(p2[0] - (p3[0] - p1[0]) / 6)} ${n1(p2[1] - (p3[1] - p1[1]) / 6)} ${n1(p2[0])} ${n1(p2[1])}`;
  }
  return d + (closed ? 'Z' : '');
}

// Tapered ribbon around a centre line: pts [[x,y]...], ws widths per point.
function ribbonPath(pts, ws) {
  const L = [], R = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    let dx = b[0] - a[0], dy = b[1] - a[1];
    const d = Math.hypot(dx, dy) || 1;
    dx /= d; dy /= d;
    L.push([pts[i][0] - dy * ws[i] / 2, pts[i][1] + dx * ws[i] / 2]);
    R.push([pts[i][0] + dy * ws[i] / 2, pts[i][1] - dx * ws[i] / 2]);
  }
  return curve(L.concat(R.reverse()), true);
}

// Hermite spline through timed keys [[t, x, y], ...].
function spline(keys, t) {
  const n = keys.length;
  if (t <= keys[0][0]) return [keys[0][1], keys[0][2]];
  if (t >= keys[n - 1][0]) return [keys[n - 1][1], keys[n - 1][2]];
  let i = 0;
  while (t > keys[i + 1][0]) i++;
  const k0 = keys[i], k1 = keys[i + 1];
  const km = keys[Math.max(0, i - 1)], kp = keys[Math.min(n - 1, i + 2)];
  const dt = k1[0] - k0[0], u = (t - k0[0]) / dt;
  const out = [];
  for (let c = 1; c <= 2; c++) {
    const m0 = (k1[c] - km[c]) / (k1[0] - km[0]) * dt;
    const m1 = (kp[c] - k0[c]) / (kp[0] - k0[0]) * dt;
    out.push((2 * u ** 3 - 3 * u ** 2 + 1) * k0[c] + (u ** 3 - 2 * u ** 2 + u) * m0 + (-2 * u ** 3 + 3 * u ** 2) * k1[c] + (u ** 3 - u ** 2) * m1);
  }
  return out;
}

// ---- camera: every plane zooms by a different amount (multiplane parallax) ----
const CX = 640, CY = 420;
const PLANE_ZOOM = { sky: 0.01, far: 0.025, mid: 0.05, bride: 0.07, front: 0.11, fg: 0.17 };
const planeScale = (name, t) => 1 + PLANE_ZOOM[name] * easeIO(clamp(t / DURATION));
const planeTransform = (name, t) => `translate(${CX} ${CY}) scale(${planeScale(name, t).toFixed(5)}) translate(${-CX} ${-CY})`;
function toPlane(p, from, to, t) {
  const k = planeScale(from, t) / planeScale(to, t);
  return [CX + (p[0] - CX) * k, CY + (p[1] - CY) * k];
}

// ---- gradients ----
const defs = el('defs', null, svg);
function gradient(id, type, attrs, stops) {
  const g = el(type === 'r' ? 'radialGradient' : 'linearGradient', { id, ...attrs }, defs);
  for (const [o, c, a = 1] of stops) el('stop', { offset: o, 'stop-color': c, 'stop-opacity': a }, g);
  return g;
}
const vert = { x1: 0, y1: 0, x2: 0, y2: 1 };
gradient('gSky', 'l', { gradientUnits: 'userSpaceOnUse', x1: 0, y1: 0, x2: 0, y2: 720 }, [[0, '#03040c'], [0.36, '#0a1334'], [0.64, '#17305a'], [0.86, '#2b4a78'], [1, '#1d3354']]);
gradient('gMoonGlow', 'r', { gradientUnits: 'userSpaceOnUse', cx: MOON.x, cy: MOON.y, r: 560 }, [[0, '#dcefff', 0.6], [0.2, '#a2cdf8', 0.32], [0.48, '#5f8fd6', 0.12], [1, '#2a4a8a', 0]]);
gradient('gMoon', 'r', { cx: 0.38, cy: 0.34, r: 0.75 }, [[0, '#ffffff'], [0.55, '#e4f1fb'], [1, '#a9c6e2']]);
gradient('gFog', 'r', {}, [[0, '#a6c8ee', 0.5], [0.55, '#86aadb', 0.2], [1, '#6e94c8', 0]]);
gradient('gBrideGlow', 'r', {}, [[0, '#86d8ff', 0.34], [0.5, '#5aa8f0', 0.13], [1, '#3c78d0', 0]]);
gradient('gHalo', 'r', {}, [[0, '#bff4ff', 0.75], [0.4, '#58b8ff', 0.28], [1, '#2a6af0', 0]]);
gradient('gWarm', 'r', {}, [[0, '#ffc477', 0.7], [1, '#ff9a3c', 0]]);
gradient('gDressH', 'l', { gradientUnits: 'userSpaceOnUse', x1: -135, y1: 0, x2: 135, y2: 0 }, [[0, '#6c87a6'], [0.4, '#b4cadf'], [0.78, '#e0edf8'], [1, '#c9deee']]);
gradient('gDressV', 'l', { gradientUnits: 'userSpaceOnUse', x1: 0, y1: -216, x2: 0, y2: 0 }, [[0, '#1d3350', 0], [0.55, '#1d3350', 0.12], [1, '#17404a', 0.6]]);
gradient('gSkin', 'l', vert, [[0, '#cfe2ef'], [0.6, '#a9c6dc'], [1, '#86a9c6']]);
gradient('gVeil', 'l', { x1: 0, y1: 0, x2: 1, y2: 0 }, [[0, '#e6f3fd', 0.8], [0.5, '#cde3f5', 0.42], [1, '#bcd8f0', 0]]);
gradient('gStone', 'l', vert, [[0, '#2b4068'], [1, '#0d1630']]);
gradient('gGround', 'l', vert, [[0, '#0b1124'], [1, '#04060d']]);
gradient('gVignette', 'r', { gradientUnits: 'userSpaceOnUse', cx: 640, cy: 360, r: 780, gradientTransform: 'translate(640 360) scale(1 0.64) translate(-640 -360)' }, [[0, '#000008', 0], [0.55, '#000008', 0.05], [1, '#000008', 0.8]]);
gradient('gDissolve', 'l', { gradientUnits: 'userSpaceOnUse', x1: 0, y1: 0, x2: 0, y2: 100 }, [[0, '#fff', 1], [1, '#fff', 0]]);

// ---- filters ----
function mkFilter(id, build, attrs) {
  const f = el('filter', { id, 'color-interpolation-filters': 'sRGB', ...attrs }, defs);
  build(f);
  return f;
}
const margin = { x: '-60%', y: '-60%', width: '220%', height: '220%' };
for (const [id, sd] of [['fBlur2', 2], ['fBlur3', 3.5], ['fBlur10', 10], ['fBlur24', 24]]) {
  mkFilter(id, f => el('feGaussianBlur', { stdDeviation: sd }, f), margin);
}
mkFilter('fGlow', f => {
  el('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: 5, result: 'b' }, f);
  const m = el('feMerge', null, f);
  el('feMergeNode', { in: 'b' }, m);
  el('feMergeNode', { in: 'SourceGraphic' }, m);
}, { filterUnits: 'userSpaceOnUse', x: -100, y: -100, width: W + 200, height: H + 200 });

// stop-motion "boil": a different wobble pattern every puppet frame
const boilTurbulence = el('feTurbulence', { type: 'turbulence', baseFrequency: '0.018 0.022', numOctaves: 2, seed: 1, result: 'n' });
mkFilter('fBoil', f => {
  f.appendChild(boilTurbulence);
  el('feDisplacementMap', { in: 'SourceGraphic', in2: 'n', scale: 3.4, xChannelSelector: 'R', yChannelSelector: 'G' }, f);
}, { filterUnits: 'userSpaceOnUse', x: -60, y: -60, width: W + 120, height: H + 120 });

// dissolve: vertical gradient + noise, thresholded into a ragged alpha edge
mkFilter('fDissolve', f => {
  el('feTurbulence', { type: 'fractalNoise', baseFrequency: '0.013 0.032', numOctaves: 3, seed: 5, result: 'n' }, f);
  el('feColorMatrix', { in: 'n', type: 'matrix', values: '0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  1 0 0 0 0', result: 'na' }, f);
  el('feComposite', { in: 'SourceGraphic', in2: 'na', operator: 'arithmetic', k1: 0, k2: 1, k3: 0.8, k4: -0.4, result: 'sum' }, f);
  const ct = el('feComponentTransfer', null, f);
  el('feFuncA', { type: 'linear', slope: 14, intercept: -6.4 }, ct);
}, { filterUnits: 'userSpaceOnUse', x: 0, y: 0, width: W, height: H });
const dissolveMask = el('mask', { id: 'mDissolve', maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: W, height: H, 'mask-type': 'alpha' }, defs);
el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#gDissolve)', filter: 'url(#fDissolve)' }, dissolveMask);

const grainTurbulence = el('feTurbulence', { type: 'fractalNoise', baseFrequency: 0.8, numOctaves: 1, seed: 1, result: 'n' });
mkFilter('fGrain', f => {
  f.appendChild(grainTurbulence);
  el('feColorMatrix', { in: 'n', type: 'matrix', values: '0.4 0.4 0.4 0 -0.1  0.4 0.4 0.4 0 -0.1  0.4 0.4 0.4 0 -0.1  0 0 0 0 0.09' }, f);
}, { filterUnits: 'userSpaceOnUse', x: 0, y: 0, width: W, height: H });
