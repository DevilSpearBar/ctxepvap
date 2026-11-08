'use strict';
/* The bride puppet. Local units: origin at her feet, negative y is up.
   brideState() is a pure function of time, buildBride()/applyBride() own the DOM. */

const BS = 1.1;                                    // puppet scale
const WAIST = [0, -215], NECK = [0, -306], HEAD = [0, -392];
const SH_L = [-34, -290], SH_R = [34, -290];
const L1 = 60, L2 = 58;                            // arm segment lengths
const SKIN = '#a9c6dc', SKIN_LIGHT = '#cfe3f0', BONE = '#ece5cf';
const hemRand = (() => { const r = rng(9); return Array.from({ length: 24 }, () => r()); })();
const bump = (t, c, w) => Math.max(0, 1 - Math.abs(t - c) / w);

const HEM = Array.from({ length: 13 }, (_, i) => ({ u: (i + 1 + (hemRand[i] - 0.5) * 0.7) / 14, d: i % 2 ? 4 + hemRand[(i + 3) % 24] * 8 : -(16 + hemRand[(i + 6) % 24] * 26) }));
const STRIPS = Array.from({ length: 7 }, (_, i) => ({ x0: (i - 3) * 8, x1: (i - 3) * 40 + (hemRand[i] - 0.5) * 20, tip: -14 - hemRand[i + 8] * 56, w: 22 + hemRand[i + 2] * 8, ph: i * 1.3 }));
const RINGLETS = [
  { side: -1, x0: 47, len: 84, wind: 4, curlR: 8, ph: 1.9, w: 10 }, { side: -1, x0: 41, len: 112, wind: 3, curlR: 11, ph: 0.4, w: 13 },
  { side: 1, x0: 47, len: 84, wind: 13, curlR: 8, ph: 0.8, w: 10 }, { side: 1, x0: 41, len: 112, wind: 11, curlR: 11, ph: 2.2, w: 13 },
];

function armPoints(sh, a1, a2) {
  const e = [sh[0] + L1 * Math.cos(rad(a1)), sh[1] + L1 * Math.sin(rad(a1))];
  const h = [e[0] + L2 * Math.cos(rad(a2)), e[1] + L2 * Math.sin(rad(a2))];
  return { a1, a2, e, h };
}

function upperToWorld(p, s) {
  const a = rad(s.sway), c = Math.cos(a), sn = Math.sin(a);
  const dx = p[0] - WAIST[0], dy = p[1] - WAIST[1];
  return [BASE.x + BS * (WAIST[0] + dx * c - dy * sn), BASE.y + BS * (WAIST[1] + dx * sn + dy * c + s.riseY)];
}
function headToUpper(p, rot) {
  const a = rad(rot), c = Math.cos(a), sn = Math.sin(a);
  const dx = HEAD[0] + p[0] - NECK[0], dy = HEAD[1] + p[1] - NECK[1];
  return [NECK[0] + dx * c - dy * sn, NECK[1] + dx * sn + dy * c];
}

// Everything except the head follow-through (needs the gaze target, see finishHead).
function brideState(t) {
  const s = { t };
  s.rise = easeIO(ramp(t, 1.0, 3.6));
  s.riseY = (1 - s.rise) * 480;
  s.sway = 1.5 * Math.sin(t * 1.4) + 1.5 + 2.6 * Math.sin(t * 7.3) * smooth(ramp(t, 0.9, 1.6)) * (1 - smooth(ramp(t, 3.0, 3.9)));

  const raise = smooth(ramp(t, 4.4, 5.4)) * (1 - smooth(ramp(t, 7.0, 8.3)));
  s.raise = raise;
  s.armR = armPoints(SH_R, lerp(84, 45, raise) + Math.sin(t * 1.3) * 1.5, lerp(100, -58, raise) + Math.sin(t * 1.7 + 1) * 1.5);
  s.armL = armPoints(SH_L, 112 + Math.sin(t * 1.4 + 1) * 1.5, 8 - 12 * bump(t, 4.1, 0.45) + Math.sin(t * 1.4) * 1.5);
  const tipDir = rad(s.armR.a2 + 6);
  s.fingertip = [s.armR.h[0] + 26 * Math.cos(tipDir), s.armR.h[1] + 26 * Math.sin(tipDir)];
  s.bouquet = [s.armL.h[0] + 2, s.armL.h[1] - 2];

  let open = 0.92 * smooth(ramp(t, 3.15, 3.8));
  for (const b of [4.5, 5.9, 7.4]) open *= 1 - 0.96 * bump(t, b, 0.11);
  open *= 1 - smooth(ramp(t, 8.2, 8.7));
  s.smile = -0.25 + 0.35 * smooth(ramp(t, 3.6, 4.4)) + 0.95 * smooth(ramp(t, 5.5, 6.2));
  s.open = open * (1 - 0.12 * clamp(s.smile));
  s.glow = smooth(ramp(t, 1.4, 3.6)) * 0.7 + 0.5 * bump(t, 7.6, 1.2) - 0.7 * smooth(ramp(t, 8.8, 9.6));
  return s;
}

// Head roll and pupils follow the gaze target (world coordinates).
function finishHead(s, target) {
  const head = upperToWorld(HEAD, s);
  const vx = target[0] - head[0], vy = target[1] - head[1];
  const aware = smooth(ramp(s.t, 3.5, 4.3));
  s.gaze = [clamp(vx / 170, -1, 1) * 4.6 * aware, clamp(vy / 170, -1, 1) * 4 * aware];
  s.headRot = lerp(-10, 3, easeIO(ramp(s.t, 2.8, 4.4))) + Math.sin(s.t * 1.1 + 0.5) * 1.4 + clamp(vx / 420, -1, 1) * 6 * aware;
  return s;
}

// ------------------------------------------------------------------ parts
function limb(parent, w) {
  const o = el('path', { fill: 'none', stroke: OUTLINE, 'stroke-width': w + 3.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, parent);
  const f = el('path', { fill: 'none', stroke: SKIN, 'stroke-width': w, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, parent);
  return (a, b) => { const d = `M${n1(a[0])} ${n1(a[1])} L${n1(b[0])} ${n1(b[1])}`; set(o, { d }); set(f, { d }); };
}
// exposed forearm bone with knobbed ends
function boneLimb(parent) {
  const o = el('path', { fill: 'none', stroke: OUTLINE, 'stroke-width': 8.4, 'stroke-linecap': 'round' }, parent);
  const f = el('path', { fill: 'none', stroke: BONE, 'stroke-width': 4.6, 'stroke-linecap': 'round' }, parent);
  const k = [5.2, 4.4].map(r => el('circle', { r, fill: BONE, stroke: OUTLINE, 'stroke-width': 1.6 }, parent));
  return (a, b) => {
    const d = `M${n1(a[0])} ${n1(a[1])} L${n1(b[0])} ${n1(b[1])}`;
    set(o, { d }); set(f, { d });
    set(k[0], { cx: n1(a[0]), cy: n1(a[1]) }); set(k[1], { cx: n1(b[0]), cy: n1(b[1]) });
  };
}

const FINGERS = [{ y: -4, a: -14, len: 19 }, { y: -1.5, a: -3, len: 20 }, { y: 1.2, a: 8, len: 18 }, { y: 3.6, a: 19, len: 14 }];
function buildHand(parent) {
  const g = el('g', null, parent);
  const fingers = FINGERS.map(() => ({
    o: el('path', { fill: 'none', stroke: OUTLINE, 'stroke-width': 4.4, 'stroke-linecap': 'round' }, g),
    f: el('path', { fill: 'none', stroke: SKIN_LIGHT, 'stroke-width': 2.4, 'stroke-linecap': 'round' }, g),
  }));
  el('path', { d: 'M3 -5 Q9 -11 14 -9', fill: 'none', stroke: OUTLINE, 'stroke-width': 4.4, 'stroke-linecap': 'round' }, g);
  el('path', { d: 'M3 -5 Q9 -11 14 -9', fill: 'none', stroke: SKIN_LIGHT, 'stroke-width': 2.4, 'stroke-linecap': 'round' }, g);
  el('ellipse', { cx: 3, cy: 0, rx: 8, ry: 6.5, fill: SKIN, stroke: OUTLINE, 'stroke-width': 1.8 }, g);
  return { g, fingers };
}
function poseHand(h, p, ang, curl) {
  set(h.g, { transform: `translate(${n1(p[0])} ${n1(p[1])}) rotate(${n1(ang)})` });
  FINGERS.forEach((f, i) => {
    const c = curl[i], a = rad(f.a + c * 40), L = f.len * (1 - 0.3 * c), bx = 8, by = f.y;
    const d = `M${bx} ${by} Q${n1(bx + Math.cos(a - 0.35 * c) * L * 0.55)} ${n1(by + Math.sin(a - 0.35 * c) * L * 0.55)} ${n1(bx + Math.cos(a) * L)} ${n1(by + Math.sin(a) * L)}`;
    set(h.fingers[i].o, { d }); set(h.fingers[i].f, { d });
  });
}

function flower(parent, x, y, r, col, rot) {
  const g = el('g', { transform: `translate(${n1(x)} ${n1(y)}) rotate(${n1(rot)})` }, parent);
  for (let i = 0; i < 5; i++) el('ellipse', { cx: r * 0.7, cy: 0, rx: r * 0.78, ry: r * 0.44, fill: col, stroke: OUTLINE, 'stroke-width': 1, transform: `rotate(${i * 72})` }, g);
  el('circle', { r: r * 0.3, fill: '#2a2f5c' }, g);
  return g;
}

function buildBouquet(parent) {
  const g = el('g', null, parent);
  const q = rng(61);
  const heads = [[-38, -40], [-14, -58], [14, -52], [-54, -14], [32, -26], [-26, -24]];
  const cols = ['#b9b4ea', '#8da2e2', '#e5edf9', '#a78fd8', '#c8d7f3', '#98aee8'];
  for (const [x, y, rot, sc] of [[-30, -22, -140, 1], [18, -26, -40, 0.9], [-6, -30, -100, 0.8]]) {
    el('path', { d: 'M0 0 Q10 -6 26 0 Q10 6 0 0Z', fill: '#1f3b4f', stroke: OUTLINE, 'stroke-width': 1, transform: `translate(${x} ${y}) rotate(${rot}) scale(${sc})` }, g);
  }
  heads.forEach(([x, y]) => el('path', { d: `M0 4 Q${x * 0.35} ${y * 0.9} ${x} ${y + 6}`, fill: 'none', stroke: '#1d3a46', 'stroke-width': 2.2, 'stroke-linecap': 'round' }, g));
  heads.forEach(([x, y], i) => flower(g, x, y + 4, 7 + (i % 3) * 1.6, cols[i], q() * 360));
  el('path', { d: 'M0 8 Q-9 18 -13 30 M0 8 Q8 18 10 32', fill: 'none', stroke: '#352a68', 'stroke-width': 2.6, 'stroke-linecap': 'round' }, g);
  el('path', { d: 'M-6 2 L6 2 L7 9 L-7 9 Z', fill: '#352a68', stroke: OUTLINE, 'stroke-width': 1.2 }, g);
  return g;
}

function buildEye(parent, cx, cy, rx, ry, id) {
  const g = el('g', { transform: `translate(${cx} ${cy})` }, parent);
  el('ellipse', { cx: 0, cy: 3, rx: rx + 7, ry: ry + 6, fill: '#323872', 'fill-opacity': 0.5, filter: 'url(#fBlur3)' }, g);
  const glow = el('circle', { r: ry * 1.7, fill: 'url(#gHalo)', opacity: 0 }, g);
  const ball = el('g', null, g);
  const clip = el('clipPath', { id: `eyeclip${id}` }, defs);
  el('ellipse', { cx: 0, cy: 0, rx: rx - 0.5, ry: ry - 0.5 }, clip);
  el('ellipse', { cx: 0, cy: 0, rx, ry, fill: '#eaf3fa', stroke: OUTLINE, 'stroke-width': 1.9 }, ball);
  const inner = el('g', { 'clip-path': `url(#eyeclip${id})` }, ball);
  const iris = el('circle', { r: ry * 0.78, fill: '#3153a0', 'fill-opacity': 0.75 }, inner);
  const pupil = el('circle', { r: ry * 0.5, fill: '#0b0f2c' }, inner);
  const glint = el('circle', { r: 2.3, fill: '#ffffff' }, inner);
  const lid = el('path', { fill: 'none', stroke: OUTLINE, 'stroke-width': 2.8, 'stroke-linecap': 'round' }, g);
  const bag = el('path', { fill: 'none', stroke: '#3f4f86', 'stroke-opacity': 0.55, 'stroke-width': 2, 'stroke-linecap': 'round' }, g);
  return { g, glow, ball, iris, pupil, glint, lid, bag, rx, ry };
}
function poseEye(e, open, gx, gy) {
  const sy = Math.max(0.03, open);
  set(e.ball, { transform: `scale(1 ${sy.toFixed(3)})`, opacity: open < 0.05 ? 0 : 1 });
  for (const k of ['iris', 'pupil']) set(e[k], { cx: n1(gx), cy: n1(gy) });
  set(e.glint, { cx: n1(gx - 2.8), cy: n1(gy - 3.2) });
  set(e.lid, { d: `M${n1(-e.rx - 1.5)} 0 Q0 ${n1(6 + (-2 * e.ry - 6) * sy)} ${n1(e.rx + 1.5)} 0` });
  set(e.bag, { d: `M${n1(-e.rx * 0.8)} ${n1(e.ry * 0.95 + 3)} Q0 ${n1(e.ry * 1.25 + 4)} ${n1(e.rx * 0.8)} ${n1(e.ry * 0.95 + 3)}` });
  set(e.glow, { opacity: (0.3 * clamp(open * 1.2)).toFixed(2) });
}

function buildBride(parent) {
  const b = {};
  const root = b.root = el('g', null, parent);
  const line = (extra) => ({ stroke: OUTLINE, 'stroke-width': 2.2, 'stroke-linejoin': 'round', ...extra });

  // ----- skirt (stays planted, the torso sways above it): base layer + torn strips
  b.skirt = el('path', line({ fill: 'url(#gDressH)' }), root);
  b.skirtShade = el('path', { fill: 'url(#gDressV)' }, root);
  b.pleats = el('path', { fill: 'none', stroke: '#47617f', 'stroke-opacity': 0.32, 'stroke-width': 1.5, 'stroke-linecap': 'round' }, root);
  b.strips = STRIPS.map(() => el('path', { fill: '#e6f1fa', 'fill-opacity': 0.5, stroke: OUTLINE, 'stroke-opacity': 0.45, 'stroke-width': 1.3, 'stroke-linejoin': 'round' }, root));

  const up = b.upper = el('g', null, root);
  const veil = { stroke: 'url(#gVeilEdge)', 'stroke-width': 1.2, 'stroke-linejoin': 'round' };
  b.veils = [0.7, 0.85, 1].map(op => el('path', { fill: 'url(#gVeil)', opacity: op, ...veil }, up));
  b.strands = [0, 1].map(() => el('path', { fill: '#0f1329', stroke: '#0f1329', 'stroke-width': 0.8, 'stroke-linejoin': 'round' }, up));
  b.headBack = el('g', null, up);
  el('path', line({ d: 'M-46 -4 C-54 -58 -22 -74 0 -74 C22 -74 54 -58 46 -4 L50 44 C48 74 30 90 0 92 C-30 90 -48 74 -50 44 Z', fill: '#0e1228', 'stroke-width': 2 }), b.headBack);
  el('ellipse', line({ cx: 3, cy: -76, rx: 25, ry: 19, fill: '#0e1228', 'stroke-width': 2 }), b.headBack);       // bun
  el('path', { d: 'M-12 -84 Q4 -92 20 -82', fill: 'none', stroke: '#3a4c88', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-opacity': 0.8 }, b.headBack);

  // neck, shoulders, bodice
  el('path', line({ d: 'M-6 -344 L-6.5 -304 Q0 -298 6.5 -304 L6 -344 Z', fill: 'url(#gSkin)' }), up);
  el('ellipse', { cx: 0, cy: -334, rx: 10, ry: 8, fill: '#324c70', 'fill-opacity': 0.5, filter: 'url(#fBlur3)' }, up);
  el('path', line({ d: 'M-9 -309 C-20 -301 -34 -299 -45 -293 C-48 -289 -46 -283 -40 -283 L40 -283 C46 -283 48 -289 45 -293 C34 -299 20 -301 9 -309 Z', fill: 'url(#gSkin)' }), up);
  el('path', { d: 'M-8 -300 Q-20 -296 -33 -296 M8 -300 Q20 -296 33 -296', fill: 'none', stroke: '#6f90b0', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-opacity': 0.8 }, up);
  el('path', line({ d: 'M-42 -288 Q-30 -270 -15 -275 Q-7 -278 0 -266 Q7 -278 15 -275 Q30 -270 42 -288 L30 -250 L27 -214 Q0 -205 -27 -214 L-30 -250 Z', fill: 'url(#gDressH)' }), up);
  el('path', { d: 'M-42 -288 Q-30 -270 -15 -275 Q-7 -278 0 -266 Q7 -278 15 -275 Q30 -270 42 -288', fill: 'none', stroke: '#f4faff', 'stroke-width': 2.6, 'stroke-dasharray': '2.2 2.6' }, up);
  let lacing = 'M0 -262 L0 -222';
  for (let y = -258; y < -224; y += 8) lacing += `M-5 ${y} L5 ${y + 6} M5 ${y} L-5 ${y + 6}`;
  el('path', { d: lacing, fill: 'none', stroke: '#47617f', 'stroke-width': 1.3, 'stroke-linecap': 'round' }, up);
  flower(up, -19, -251, 6.5, '#b2a6e0', 20);

  // arms: bouquet arm (screen-left) then the free arm (screen-right, bare forearm bone)
  b.armLU = limb(up, 8.4); b.armLF = limb(up, 6.6);
  b.bouquet = buildBouquet(up);
  b.handL = buildHand(up);
  b.armRU = limb(up, 8.4); b.armRF = boneLimb(up);
  b.handR = buildHand(up);

  // head
  b.headFront = el('g', null, up);
  const hd = b.headFront;
  el('path', line({ d: 'M0 -52 C26 -52 42 -34 43 -8 C44 12 31 36 12 50 C6 54 -6 54 -12 50 C-31 36 -44 12 -43 -8 C-42 -34 -26 -52 0 -52Z', fill: 'url(#gSkin)', 'stroke-width': 2.4 }), hd);
  for (const [x, rot] of [[-27, 8], [28, -8]]) el('ellipse', { cx: x, cy: 22, rx: 8, ry: 17, fill: '#4f7192', 'fill-opacity': 0.33, filter: 'url(#fBlur3)', transform: `rotate(${rot} ${x} 22)` }, hd);
  el('ellipse', { cx: 6, cy: -34, rx: 20, ry: 9, fill: '#eef7fd', 'fill-opacity': 0.32, filter: 'url(#fBlur3)' }, hd);
  b.eyeL = buildEye(hd, -18, -4, 13, 14.5, 'L');
  b.eyeR = buildEye(hd, 19, -5.5, 15, 16.5, 'R');
  for (const d of ['M-34 -23 Q-22 -34 -8 -26', 'M8 -30 Q22 -41 36 -29']) el('path', { d, fill: 'none', stroke: '#171c3b', 'stroke-width': 2.4, 'stroke-linecap': 'round' }, hd);
  el('path', { d: 'M-3.6 15 Q0 20 3.6 15', fill: 'none', stroke: '#4d6d8f', 'stroke-width': 1.8, 'stroke-linecap': 'round' }, hd);
  el('path', { d: 'M1 3 Q-1 10 -2 14', fill: 'none', stroke: '#d6e7f3', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-opacity': 0.7 }, hd);
  b.lowerLip = el('path', { fill: '#6a78b3', 'fill-opacity': 0.8 }, hd);
  b.mouth = el('path', { fill: 'none', stroke: '#1b2147', 'stroke-width': 2.1, 'stroke-linecap': 'round' }, hd);
  el('path', { d: 'M23 20 L28 27 M21 24 L26 22 M25 25 L30 24', fill: 'none', stroke: '#3c4f7a', 'stroke-width': 1.3, 'stroke-linecap': 'round', 'stroke-opacity': 0.75 }, hd);
  el('path', line({ d: 'M-45 -3 C-50 -44 -27 -63 0 -63 C27 -63 50 -44 45 -3 C44 -22 32 -38 8 -38 L0 -33 L-8 -38 C-32 -38 -44 -22 -45 -3Z', fill: '#0e1228', 'stroke-width': 1.8 }), hd);
  el('path', { d: 'M-30 -52 Q-8 -62 16 -56', fill: 'none', stroke: '#3a4c88', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-opacity': 0.8 }, hd);
  b.locks = RINGLETS.map(() => el('path', line({ fill: '#0e1228', 'stroke-width': 1.8 }), hd));
  [[-24, -56, 6, '#c3c6f2', 10], [-8, -64, 6.5, '#e8effa', 80], [12, -63, 6, '#a995dc', 140], [28, -54, 5.2, '#c3c6f2', 30]].forEach(([x, y, r, c, rot]) => flower(hd, x, y, r, c, rot));
  return b;
}

// ------------------------------------------------------------------ per-frame pose
function skirtPaths(t) {
  const sw = (i, a) => Math.sin(t * 1.9 + i * 0.8) * a;
  const left = [[-26, -216], [-46, -172], [-84, -118], [-120, -58], [-140, -12]].map((p, i) => [p[0] + sw(i, 1.1 * i), p[1]]);
  const right = [[26, -216], [46, -168], [86, -114], [122, -56], [140, -10]].map((p, i) => [p[0] + sw(i + 3, 1.1 * i), p[1]]);
  let main = curve(left);
  HEM.forEach((h, i) => { main += `L${n1(lerp(left[4][0], right[4][0], h.u) + sw(i, 2.5))} ${n1(-6 + h.d + sw(i * 2, 2))}`; });
  main += `L${n1(right[4][0])} ${n1(right[4][1])}` + curve(right.slice().reverse(), false, true) + `Q0 -205 ${n1(left[0][0])} ${n1(left[0][1])}Z`;

  const strips = STRIPS.map(st => {
    const sway = Math.sin(t * 1.9 + st.ph) * 3.5;
    const pts = [[st.x0, -212], [lerp(st.x0, st.x1, 0.35) + sway * 0.3, lerp(-212, st.tip, 0.35)], [lerp(st.x0, st.x1, 0.7) + sway * 0.7, lerp(-212, st.tip, 0.7)], [st.x1 + sway, st.tip]];
    return ribbonPath(pts, [12, st.w, st.w * 0.9, 2.5]);
  });
  let pleats = '';
  for (let i = -4; i <= 4; i += 2) pleats += `M${i * 6} -206 Q${n1(i * 14 + sw(i, 1.5))} -120 ${i * 24} -24`;
  return { main, strips, pleats };
}

// Silky veil streamer: a wavy ribbon that fades out (the gradient hides its end).
function veilRibbon(anchor, t, o) {
  const N = 12, pts = [], ws = [];
  for (let i = 0; i <= N; i++) {
    const s = i / N, wave = Math.sin(t * o.sp - s * o.k + o.ph);
    pts.push([anchor[0] + s * o.len * (1 - 0.08 * Math.abs(wave) * s), anchor[1] + s * o.rise + s * s * o.droop + wave * o.amp * s ** 0.9]);
    ws.push(5 + o.wid * Math.sin(Math.min(1, s * 1.15) * Math.PI * 0.62) ** 1.1 * (1 - 0.2 * s));
  }
  return ribbonPath(pts, ws);
}

function strandPath(anchor, t, o) {
  const pts = [], ws = [];
  for (let i = 0; i <= 9; i++) {
    const s = i / 9;
    pts.push([anchor[0] + s * o.len, anchor[1] + s * o.rise + s * s * o.droop + Math.sin(t * o.sp - s * 5 + o.ph) * o.amp * s]);
    ws.push(6 * (1 - s) ** 0.8 + 1);
  }
  return ribbonPath(pts, ws);
}

// Hanging ringlet that ends in a curl.
function ringletPath(o, t) {
  const side = o.side, n = 7, pts = [], ws = [];
  for (let k = 0; k <= n; k++) {
    const s = k / n;
    pts.push([side * (o.x0 + 8 * Math.sin(s * 3 + o.ph)) + (Math.sin(t * 1.7 + o.ph + s * 2.2) * 3.5 + o.wind) * s ** 1.3, -6 + s * o.len]);
    ws.push(o.w * (1 - 0.35 * s));
  }
  const end = pts[n], cx = end[0] - side * o.curlR * 0.9, cy = end[1] + o.curlR * 0.3;
  const a0 = Math.atan2(end[1] - cy, end[0] - cx), r0 = Math.hypot(end[0] - cx, end[1] - cy);
  for (let k = 1; k <= 8; k++) {
    const a = a0 + side * k * 0.75, r = r0 * (1 - 0.68 * k / 8);
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    ws.push(Math.max(1.6, o.w * 0.5 * (1 - k / 9)));
  }
  return ribbonPath(pts, ws);
}

function applyBride(b, s) {
  const t = s.t;
  set(b.root, { transform: `translate(${BASE.x} ${n1(BASE.y + BS * s.riseY)}) scale(${BS})` });
  const sk = skirtPaths(t);
  set(b.skirt, { d: sk.main }); set(b.skirtShade, { d: sk.main }); set(b.pleats, { d: sk.pleats });
  b.strips.forEach((p, i) => set(p, { d: sk.strips[i] }));
  set(b.upper, { transform: `rotate(${n1(s.sway)} ${WAIST[0]} ${WAIST[1]})` });

  const ht = `translate(${HEAD[0]} ${HEAD[1]}) rotate(${n1(s.headRot)} 0 ${NECK[1] - HEAD[1]})`;
  set(b.headBack, { transform: ht }); set(b.headFront, { transform: ht });
  const crown = headToUpper([6, -74], s.headRot), bun = headToUpper([18, -78], s.headRot);
  const wind = 0.75 + 0.25 * Math.sin(t * 0.9);
  [{ len: 330, rise: -24, droop: 60, wid: 120, amp: 38, sp: 2.0, k: 4.0, ph: 0 }, { len: 270, rise: -8, droop: 90, wid: 90, amp: 30, sp: 2.3, k: 4.8, ph: 1.3 }, { len: 200, rise: 6, droop: 105, wid: 62, amp: 22, sp: 2.6, k: 5.6, ph: 2.4 }]
    .forEach((o, i) => set(b.veils[i], { d: veilRibbon(crown, t, { ...o, len: o.len * wind }) }));
  [{ len: 110, rise: -14, droop: 24, amp: 20, sp: 2.5, ph: 0.4 }, { len: 140, rise: 4, droop: 40, amp: 22, sp: 2.2, ph: 2.3 }]
    .forEach((o, i) => set(b.strands[i], { d: strandPath([bun[0], bun[1] + 4 + i * 8], t, o) }));
  RINGLETS.forEach((o, i) => set(b.locks[i], { d: ringletPath(o, t) }));

  poseEye(b.eyeL, s.open, s.gaze[0], s.gaze[1]);
  poseEye(b.eyeR, s.open, s.gaze[0], s.gaze[1]);
  const sm = s.smile, cy = lerp(34, 30, clamp(sm)) + (sm < 0 ? -sm * 0.6 : 0), k = lerp(-1.6, 10, clamp(sm)) + (sm < 0 ? sm * 4 : 0);
  set(b.mouth, { d: `M-13.5 ${n1(cy)} Q0 ${n1(cy + k)} 13.5 ${n1(cy)}` });
  const mid = cy + k / 2;
  set(b.lowerLip, { d: `M-8 ${n1(mid + 0.6)} Q0 ${n1(mid + 8)} 8 ${n1(mid + 0.6)}Z` });

  // arms + hands
  const { armL, armR } = s;
  b.armLU(SH_L, armL.e); b.armLF(armL.e, armL.h);
  b.armRU(SH_R, armR.e); b.armRF(armR.e, armR.h);
  set(b.bouquet, { transform: `translate(${n1(s.bouquet[0])} ${n1(s.bouquet[1])}) rotate(${n1(Math.sin(t * 1.5) * 2.5 - 4 * bump(t, 4.1, 0.45))})` });
  poseHand(b.handL, armL.h, armL.a2 + 6, [0.85, 0.9, 0.95, 1]);
  const r = s.raise;
  poseHand(b.handR, armR.h, armR.a2 + 6, [0.04 + 0.4 * (1 - r), 0.55 + 0.35 * (1 - r), 0.7 + 0.2 * (1 - r), 0.75 + 0.2 * (1 - r)]);
}
