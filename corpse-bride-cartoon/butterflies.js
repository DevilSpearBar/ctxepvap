'use strict';
/* Butterflies: the hero from the bouquet, the swarm the bride dissolves into, falling petals. */

const WING = 'M1 -1 C4 -12 14 -24 30 -26 C38 -27 40 -18 35 -9 C31 -2 18 1 1 1Z M1 2 C14 1 28 4 30 12 C31 20 20 26 12 22 C6 19 2 10 1 2Z';
const SHINE = WING.replace(/-?\d+(\.\d+)?/g, m => (parseFloat(m) * 0.55).toFixed(1));
const WING_DARK = [12, 20, 52], SHINE_DARK = [30, 46, 98];
const PALETTE = [
  { wing: [63, 160, 255], shine: [174, 232, 255] }, { wing: [91, 123, 255], shine: [185, 200, 255] },
  { wing: [56, 198, 255], shine: [200, 246, 255] }, { wing: [138, 108, 255], shine: [211, 195, 255] },
  { wing: [74, 216, 232], shine: [217, 253, 255] },
];
const HERO_COLORS = { wing: [79, 180, 255], shine: [228, 251, 255] };

const DIS = { t0: 6.3, t1: 8.9 };                                   // dissolve window
const dissolveFront = t => lerp(BASE.y + 170, BASE.y - BS * 650, easeIO(ramp(t, DIS.t0, DIS.t1)));   // world y
function bodyHalfWidth(ly) {
  if (ly > -215) return lerp(24, 125, ((ly + 215) / 215) ** 0.9);
  return ly > -300 ? 36 : 40;
}

function buildButterfly(parent) {
  const g = el('g', { opacity: 0 }, parent);
  const halo = el('circle', { r: 34, fill: 'url(#gHalo)' }, g);
  const wing = { stroke: '#0a1440', 'stroke-width': 1.3, 'stroke-linejoin': 'round' };
  const wR = el('path', { d: WING, ...wing }, g), wL = el('path', { d: WING, ...wing }, g);
  const sR = el('path', { d: SHINE }, g), sL = el('path', { d: SHINE }, g);
  el('path', { d: 'M0 -9 Q2.2 -2 0 10 Q-2.2 -2 0 -9Z', fill: '#0a1233' }, g);
  el('path', { d: 'M0 -9 Q-3 -15 -7 -17 M0 -9 Q3 -15 7 -17', fill: 'none', stroke: '#0a1233', 'stroke-width': 1, 'stroke-linecap': 'round' }, g);
  return { g, halo, wR, wL, sR, sL };
}

function poseButterfly(f, x, y, rot, scale, open, alpha, sil, colors) {
  set(f.g, { transform: `translate(${n1(x)} ${n1(y)}) rotate(${n1(rot)}) scale(${scale.toFixed(3)})`, opacity: alpha.toFixed(2) });
  const wing = rgb(mixc(colors.wing, WING_DARK, sil)), shine = rgb(mixc(colors.shine, SHINE_DARK, sil));
  set(f.wR, { transform: `scale(${open.toFixed(3)} 1)`, fill: wing });
  set(f.wL, { transform: `scale(${(-open).toFixed(3)} 1)`, fill: wing });
  set(f.sR, { transform: `scale(${open.toFixed(3)} 1)`, fill: shine, 'fill-opacity': 0.8 });
  set(f.sL, { transform: `scale(${(-open).toFixed(3)} 1)`, fill: shine, 'fill-opacity': 0.8 });
  set(f.halo, { opacity: ((1 - sil) * 0.85).toFixed(2) });
}
const silhouette = (x, y, moon, moonR) => 1 - smooth(ramp(Math.hypot(x - moon[0], y - moon[1]), moonR * 0.85, moonR * 1.3));
const flapOpen = (t, rate, amp, ph = 0) => 1 - amp * (0.5 - 0.5 * Math.cos(6.2832 * rate * t + ph));

// ---------------------------------------------------------------- hero
const HERO_REF = (() => {
  const s6 = brideState(6.0), s0 = brideState(3.95);
  return { land: upperToWorld(s6.fingertip, s6), start: upperToWorld(s0.bouquet, s0), petals: upperToWorld(brideState(4.5).bouquet, brideState(4.5)) };
})();

function heroState(t, s, moon) {
  const h = { vis: false };
  if (t < 3.95 || t > 9.95) return h;
  const F = HERO_REF.land, B = HERO_REF.start;
  const keys = [
    [3.95, B[0], B[1] - 8], [4.45, BASE.x - 90, BASE.y - 380], [4.95, BASE.x - 75, BASE.y - 560], [5.35, BASE.x + 50, BASE.y - 595],
    [5.7, BASE.x + 170, BASE.y - 500], [6.0, F[0], F[1] - 8], [6.75, F[0], F[1] - 8], [7.35, F[0] + 70, F[1] - 130],
    [8.2, moon[0] - 150, moon[1] + 120], [8.95, moon[0] - 10, moon[1] + 10], [9.7, moon[0] + 190, moon[1] - 130],
  ];
  let [x, y] = spline(keys, t);
  const hold = smooth(ramp(t, 5.55, 6.0)) * (1 - smooth(ramp(t, 6.75, 7.15)));
  const cur = upperToWorld(s.fingertip, s);
  const fly = 1 - hold;
  x = lerp(x + 7 * Math.sin(t * 11) * fly, cur[0], hold);
  y = lerp(y + 9 * Math.sin(t * 9 + 1) * fly, cur[1] - 8, hold);
  const a = spline(keys, t - 0.05), b = spline(keys, t + 0.05);
  const heading = Math.atan2(b[0] - a[0], -(b[1] - a[1])) * 180 / Math.PI;
  Object.assign(h, {
    vis: true, x, y,
    rot: hold > 0.5 ? Math.sin(t * 1.3) * 4 : clamp(heading, -55, 55) * 0.8,
    scale: 0.75 * (0.4 + 0.6 * easeOut(ramp(t, 3.95, 4.5))),
    open: flapOpen(t, 2.6, lerp(0.88, 0.45, hold)),
    alpha: ramp(t, 3.95, 4.3) * (1 - ramp(t, 9.5, 9.95)),
  });
  return h;
}

function buildHero(parent) { return buildButterfly(parent); }
function applyHero(f, h, moon, moonR) {
  if (!h.vis) { set(f.g, { opacity: 0 }); return; }
  poseButterfly(f, h.x, h.y, h.rot, h.scale, h.open, h.alpha, silhouette(h.x, h.y, moon, moonR), HERO_COLORS);
}

// ---------------------------------------------------------------- swarm
function buildSwarm(parent, n) {
  const r = rng(404);
  const list = [];
  for (let i = 0; i < n; i++) {
    const spawn = 6.45 + (i / n) ** 0.9 * 2.35 + (r() - 0.5) * 0.12;
    const ly = clamp((dissolveFront(spawn) - BASE.y) / BS + (r() - 0.5) * 70, -560, -10);
    const lx = (r() - 0.5) * 2 * bodyHalfWidth(ly) * 0.9 + (ly < -380 && r() < 0.35 ? 90 + r() * 110 : 0);
    const a = r() * 6.28;
    list.push({
      f: buildButterfly(parent), spawn,
      sx: BASE.x + BS * lx, sy: BASE.y + BS * ly,
      dur: clamp(2.6 + r() * 0.8 - (spawn - 6.45) * 0.55, 1.5, 3.6),
      ox: Math.cos(a) * r() * 70 + 150 + r() * 120, oy: Math.sin(a) * r() * 70 - 90 - r() * 100,
      amp: 28 + r() * 44, turns: 1 + r() * 1.4, ph: r() * 6.28, rate: 2 + r() * 1.3, fph: r() * 6.28,
      scale: 0.42 + r() * 0.4, colors: PALETTE[Math.floor(r() * PALETTE.length)],
    });
  }
  return list;
}

function applySwarm(list, t, moon, moonR) {
  for (const b of list) {
    const tau = t - b.spawn;
    if (tau < 0 || tau > b.dur + 0.05) { set(b.f.g, { opacity: 0 }); continue; }
    const u = Math.min(1, tau / b.dur);
    const tx = moon[0] + b.ox, ty = moon[1] + b.oy;
    const dx = tx - b.sx, dy = ty - b.sy, len = Math.hypot(dx, dy), nx = -dy / len, ny = dx / len;
    const at = uu => {
      const e = uu ** 1.4, w = b.amp * Math.sin(6.2832 * b.turns * uu + b.ph) * (1 - uu) ** 0.8;
      return [b.sx + dx * e + nx * w, b.sy + dy * e + ny * w];
    };
    const p = at(u), p0 = at(Math.max(0, u - 0.03)), p1 = at(Math.min(1, u + 0.03));
    const x = p[0] + 5 * Math.sin(tau * 10 + b.fph), y = p[1] + 7 * Math.sin(tau * 8 + b.fph * 2);
    const heading = Math.atan2(p1[0] - p0[0], -(p1[1] - p0[1])) * 180 / Math.PI;
    poseButterfly(b.f, x, y, clamp(heading, -60, 60) * 0.75 + 10 * Math.sin(tau * 4 + b.ph), b.scale * (0.35 + 0.65 * easeOut(ramp(tau, 0, 0.4))),
      flapOpen(tau, b.rate, 0.88, b.fph), ramp(tau, 0, 0.25) * (1 - ramp(u, 0.92, 1)), silhouette(x, y, moon, moonR), b.colors);
  }
}

// ---------------------------------------------------------------- petals
function buildPetals(parent, n) {
  return Array.from({ length: n }, (_, i) => {
    const r = rng(700 + i);
    return { e: el('ellipse', { rx: 5, ry: 2.6, fill: ['#b9b4ea', '#e5edf9', '#8da2e2'][i % 3], stroke: OUTLINE, 'stroke-width': 0.8 }, parent), off: r() * 3.6, ox: (r() - 0.5) * 60, oy: -(10 + r() * 30), ph: r() * 6.28, drift: 20 + r() * 30 };
  });
}
function applyPetals(list, t) {
  const cycle = 3.6, act = smooth(ramp(t, 3.4, 4.0)) * (1 - smooth(ramp(t, 7.6, 8.4)));
  for (const p of list) {
    const u = (((t + p.off) % cycle) + cycle) % cycle / cycle;
    const x = HERO_REF.petals[0] + p.ox + p.drift * u + 16 * Math.sin(6.28 * 1.4 * u + p.ph);
    const y = HERO_REF.petals[1] + p.oy + 190 * u * u + 60 * u;
    set(p.e, { transform: `translate(${n1(x)} ${n1(y)}) rotate(${n1(360 * u * 1.5 + p.ph * 20)}) scale(1 ${(0.4 + 0.6 * Math.abs(Math.cos(u * 9 + p.ph))).toFixed(2)})`, opacity: (act * Math.sin(Math.PI * u) ** 0.6 * 0.9).toFixed(2) });
  }
}
