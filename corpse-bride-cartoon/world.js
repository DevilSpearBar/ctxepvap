'use strict';
/* Background planes: sky + moon, far hills + chapel, graveyard, ground + mound, foreground trees. */

function curlTip(g, x, y, ang, size, dir) {
  const pts = [[x, y]];
  let a = ang, step = size * 0.5, px = x, py = y;
  for (let i = 0; i < 13; i++) {
    a += dir * (0.3 + i * 0.05);
    step *= 0.88;
    px += Math.cos(a) * step; py += Math.sin(a) * step;
    pts.push([px, py]);
  }
  el('path', { d: curve(pts), fill: 'none', 'stroke-width': 1.7 }, g);
}

// Burton-style gnarled tree: S-shaped trunk, curling limbs, spiral tips.
function gnarlTree(parent, o) {
  const r = rng(o.seed);
  const g = el('g', { fill: o.fill, stroke: o.fill, 'stroke-width': 0.7, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, parent);
  const dirAt = (pts, i) => { const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)]; return Math.atan2(b[1] - a[1], b[0] - a[0]); };
  function grow(x, y, ang, len, w, depth, bend) {
    const n = Math.max(8, Math.round(len / 9));
    const pts = [[x, y]], ws = [w];
    let a = ang;
    for (let i = 1; i <= n; i++) {
      const u = i / n;
      const s = depth === 0 ? Math.sin(u * 5.2 + o.seed) * 0.55 : 0;
      a += (bend + s) / n * 1.8 + (r() - 0.5) * 0.2 + (depth >= 1 && u > 0.7 ? Math.sign(bend) * 0.5 * (u - 0.7) : 0);
      x += Math.cos(a) * len / n; y += Math.sin(a) * len / n;
      pts.push([x, y]); ws.push(Math.max(1.2, w * (1 - u) ** 0.85 + 1));
    }
    el('path', { d: ribbonPath(pts, ws) }, g);
    if (depth < o.depth) {
      const kids = depth === 0 ? 4 : 2 + (r() < 0.45 ? 1 : 0);
      for (let k = 0; k < kids; k++) {
        const i = Math.min(n - 1, Math.round(n * (0.28 + 0.66 * (k + r() * 0.6) / kids)));
        const side = (k + depth) % 2 ? 1 : -1;
        grow(pts[i][0], pts[i][1], dirAt(pts, i) + side * (0.5 + r() * 0.55), len * (0.5 + r() * 0.22), ws[i] * 0.72, depth + 1, (r() - 0.5) * 1.2);
      }
    }
    if (depth >= o.depth || r() < (o.curls ?? 0.35)) curlTip(g, x, y, a, len * 0.3, Math.sign(bend) || 1);
  }
  grow(o.x, o.y, o.ang ?? -Math.PI / 2, o.len, o.w, 0, o.bend ?? 0.5);
  return g;
}

function addFog(parent, { y, count, seed, rx, ry, op, speed, spread = 160 }) {
  const r = rng(seed);
  const items = [];
  for (let i = 0; i < count; i++) {
    const e = el('ellipse', { rx: n1(rx * (0.7 + r() * 0.8)), ry: n1(ry * (0.7 + r() * 0.8)), fill: 'url(#gFog)', opacity: (op * (0.6 + r() * 0.6)).toFixed(2) }, parent);
    items.push({ e, x0: r() * (W + 600), y: y + (r() - 0.5) * spread, sp: speed * (0.7 + r() * 0.6) });
  }
  return items;
}
function updateFog(items, t) {
  const span = W + 600;
  for (const f of items) set(f.e, { cx: n1((((f.x0 + f.sp * t) % span) + span) % span - 300), cy: n1(f.y) });
}

function grave(parent, x, y, w, h, tilt, kind) {
  const g = el('g', { transform: `translate(${x} ${y}) rotate(${tilt})` }, parent);
  let d;
  if (kind === 'cross') {
    const a = w * 0.16, b = w / 2;
    d = `M${-a} 0 L${-a} ${-h * 0.62} L${-b} ${-h * 0.62} L${-b} ${-h * 0.8} L${-a} ${-h * 0.8} L${-a} ${-h} L${a} ${-h} L${a} ${-h * 0.8} L${b} ${-h * 0.8} L${b} ${-h * 0.62} L${a} ${-h * 0.62} L${a} 0 Z`;
  } else {
    d = `M${-w / 2} 0 L${-w / 2} ${-h + w / 2} A${w / 2} ${w / 2} 0 0 1 ${w / 2} ${-h + w / 2} L${w / 2} 0 Z`;
  }
  el('path', { d, fill: 'url(#gStone)', stroke: '#050a18', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }, g);
  if (kind !== 'cross') {
    el('path', { d: `M${w / 2} 0 L${w / 2} ${-h + w / 2} A${w / 2} ${w / 2} 0 0 0 ${w * 0.25} ${-h + w / 2 - w * 0.433}`, fill: 'none', stroke: '#6a95d2', 'stroke-opacity': 0.55, 'stroke-width': 1.4 }, g);
    el('path', { d: `M0 ${-h * 0.66} v${h * 0.22} M${-w * 0.14} ${-h * 0.58} h${w * 0.28}`, fill: 'none', stroke: '#050a18', 'stroke-opacity': 0.6, 'stroke-width': 2 }, g);
  } else {
    el('path', { d: `M${w * 0.16} ${-h} L${w * 0.16} 0`, stroke: '#6a95d2', 'stroke-opacity': 0.5, 'stroke-width': 1.3 }, g);
  }
}

// ---------------------------------------------------------------- sky + moon
function buildSky(g) {
  const o = {};
  el('rect', { x: -80, y: -80, width: W + 160, height: H + 160, fill: 'url(#gSky)' }, g);
  const r = rng(11);
  o.stars = [];
  for (let i = 0; i < 90; i++) {
    const e = el('circle', { cx: n1(r() * W), cy: n1(r() * 420), r: n1(0.5 + r() * 1.1), fill: '#d3e5ff' }, g);
    o.stars.push({ e, ph: r() * 6.28, sp: 0.8 + r() * 2.2, base: 0.3 + r() * 0.5 });
  }
  o.swirl = el('g', null, g);
  for (let k = 0; k < 3; k++) {
    const pts = [], ws = [];
    for (let a = 0; a < 5.2; a += 0.26) {
      const rr = 135 + a * 62, th = a * 0.9 + k * 2.0944;
      pts.push([MOON.x + Math.cos(th) * rr, MOON.y + Math.sin(th) * rr * 0.9]);
      ws.push(26 * (1 - a / 5.2) ** 1.2 + 2);
    }
    el('path', { d: ribbonPath(pts, ws), fill: '#86b0e6', 'fill-opacity': 0.11, filter: 'url(#fBlur2)' }, o.swirl);
  }
  el('circle', { cx: MOON.x, cy: MOON.y, r: 560, fill: 'url(#gMoonGlow)' }, g);
  el('circle', { cx: MOON.x, cy: MOON.y, r: MOON.r + 12, fill: '#cfe6ff', 'fill-opacity': 0.28, filter: 'url(#fBlur10)' }, g);
  el('circle', { cx: MOON.x, cy: MOON.y, r: MOON.r, fill: 'url(#gMoon)' }, g);
  const cr = rng(5);
  for (let i = 0; i < 8; i++) {
    const a = cr() * 6.28, d = Math.sqrt(cr()) * MOON.r * 0.75, rr = 8 + cr() * 20;
    el('circle', { cx: n1(MOON.x + Math.cos(a) * d), cy: n1(MOON.y + Math.sin(a) * d), r: n1(rr), fill: '#9dbbd8', 'fill-opacity': (0.14 + cr() * 0.14).toFixed(2), filter: 'url(#fBlur2)' }, g);
  }
  o.clouds = [];
  for (const [x0, y, sc, sp] of [[760, 292, 1, -6], [1040, 322, 1.25, -4]]) {
    const e = el('g', { filter: 'url(#fBlur10)', opacity: 0.8 }, g);
    for (const [dx, dy, rx, ry] of [[0, 0, 120, 15], [-60, 6, 80, 11], [70, -4, 90, 12]]) el('ellipse', { cx: dx, cy: dy, rx, ry, fill: '#0d1a3d' }, e);
    o.clouds.push({ e, x0, y, sc, sp });
  }
  o.update = t => {
    for (const s of o.stars) set(s.e, { opacity: (s.base + 0.3 * Math.sin(t * s.sp + s.ph)).toFixed(2) });
    set(o.swirl, { transform: `rotate(${(t * 1.8).toFixed(2)} ${MOON.x} ${MOON.y})` });
    for (const c of o.clouds) set(c.e, { transform: `translate(${n1(c.x0 + c.sp * t)} ${c.y}) scale(${c.sc})` });
  };
  return o;
}

// ---------------------------------------------------------------- far hills + chapel + bats
function buildFar(g) {
  const o = {};
  const hillA = [[-30, 505], [100, 490], [250, 506], [420, 524], [600, 510], [790, 490], [960, 503], [1120, 488], [1310, 503]];
  el('path', { d: curve(hillA) + 'L1310 760L-30 760Z', fill: '#1a2c4b' }, g);

  for (const [x, y, len, w, seed, ang] of [[690, 506, 190, 20, 21, -1.3], [1010, 500, 160, 17, 22, -1.8], [340, 518, 170, 18, 23, -1.35]]) {
    gnarlTree(g, { x, y, len, w, seed, fill: '#17274a', depth: 3, ang });
  }

  const c = el('g', { fill: '#0d1832', stroke: '#2f4c7a', 'stroke-width': 1, 'stroke-linejoin': 'round' }, g);
  el('path', { d: 'M136 510 L136 476 L150 476 L192 450 L234 476 L250 476 L250 510 Z' }, c);
  el('path', { d: 'M160 482 L160 414 L152 412 L184 340 L204 410 L196 414 L196 482 Z' }, c);
  el('path', { d: 'M214 484 L214 442 L208 440 L226 412 L244 440 L238 442 L238 484 Z' }, c);
  o.windows = [];
  for (const [x, y] of [[146, 508], [206, 508], [226, 508], [170, 456], [219, 468]]) {
    const halo = el('circle', { cx: x + 4, cy: y - 8, r: 17, fill: 'url(#gWarm)', opacity: 0.55 }, g);
    const win = el('path', { d: `M${x} ${y} L${x} ${y - 11} Q${x + 4} ${y - 18} ${x + 8} ${y - 11} L${x + 8} ${y} Z`, fill: '#ffc27a' }, g);
    o.windows.push({ halo, win });
  }

  o.fog = addFog(g, { y: 538, count: 7, seed: 3, rx: 260, ry: 40, op: 0.55, speed: 6 });
  const hillB = [[-30, 548], [200, 556], [380, 540], [560, 560], [760, 548], [980, 564], [1180, 546], [1310, 556]];
  el('path', { d: curve(hillB) + 'L1310 760L-30 760Z', fill: '#121f3a' }, g);

  o.bats = [];
  const batShape = 'M0 0 Q-5 -7 -12 -4 Q-8 -1 -9 3 Q-4 1 0 5 Q4 1 9 3 Q8 -1 12 -4 Q5 -7 0 0Z';
  for (const [cx, cy, A, B, w, ph] of [[200, 350, 70, 34, 0.7, 0], [150, 300, 90, 40, 0.55, 2], [270, 330, 75, 28, 0.9, 4], [210, 270, 110, 36, 0.42, 1]]) {
    o.bats.push({ e: el('path', { d: batShape, fill: '#050914' }, g), cx, cy, A, B, w, ph });
  }
  o.update = (t, tp) => {
    o.windows.forEach((w, i) => {
      const f = 0.82 + 0.18 * Math.sin(tp * 9 + i * 2.3) * Math.sin(tp * 3.1 + i);
      set(w.halo, { opacity: (0.55 * f).toFixed(2) });
      set(w.win, { 'fill-opacity': f.toFixed(2) });
    });
    for (const b of o.bats) {
      const a = tp * b.w + b.ph;
      set(b.e, { transform: `translate(${n1(b.cx + Math.cos(a) * b.A)} ${n1(b.cy + Math.sin(a * 1.3) * b.B)}) rotate(${n1(Math.cos(a) * 14)}) scale(1 ${(0.45 + 0.55 * Math.abs(Math.cos(tp * 9 + b.ph))).toFixed(2)})` });
    }
    updateFog(o.fog, t);
  };
  return o;
}

// ---------------------------------------------------------------- graveyard
function buildMid(g) {
  const o = {};
  const hill = [[-30, 590], [150, 600], [330, 616], [520, 640], [700, 632], [900, 622], [1100, 628], [1310, 606]];
  el('path', { d: curve(hill) + 'L1310 780L-30 780Z', fill: '#0b1327' }, g);
  gnarlTree(g, { x: 1160, y: 640, len: 270, w: 34, seed: 31, fill: '#080f20', depth: 4, ang: -1.75, bend: 0.55 });
  gnarlTree(g, { x: 290, y: 622, len: 190, w: 22, seed: 33, fill: '#080f20', depth: 3, ang: -1.25, bend: -0.5 });
  for (const [x, y, w, h, tilt, kind] of [
    [90, 612, 46, 70, -6, 'round'], [195, 630, 34, 56, 8, 'cross'], [330, 640, 52, 80, -3, 'round'],
    [650, 640, 40, 62, 10, 'round'], [775, 636, 54, 76, -9, 'round'], [1010, 628, 44, 66, 5, 'cross'],
    [1120, 646, 60, 88, -5, 'round'], [1215, 634, 38, 56, 12, 'round'],
  ]) grave(g, x, y, w, h, tilt, kind);
  o.fog = addFog(g, { y: 636, count: 6, seed: 7, rx: 240, ry: 26, op: 0.5, speed: -8, spread: 40 });
  o.update = t => updateFog(o.fog, t);
  return o;
}

// ---------------------------------------------------------------- ground, mound, soil, wisps
const GROUND_Y = 664;                                          // ground height at the bride's x
function buildFront(g) {
  const o = {};
  const ground = [[-30, 668], [150, 660], [330, 668], [470, GROUND_Y], [650, 658], [850, 648], [1050, 658], [1170, 662], [1310, 650]];
  el('path', { d: curve(ground) + 'L1310 780L-30 780Z', fill: 'url(#gGround)' }, g);
  el('path', { d: curve(ground), fill: 'none', stroke: '#38568a', 'stroke-width': 1.8, 'stroke-opacity': 0.55 }, g);
  o.mound = el('path', { fill: 'url(#gGround)' }, g);
  o.moundEdge = el('path', { fill: 'none', stroke: '#38568a', 'stroke-width': 1.8, 'stroke-opacity': 0.55, 'stroke-linejoin': 'round' }, g);

  const groundAt = x => {
    for (let i = 0; i < ground.length - 1; i++) if (x <= ground[i + 1][0]) return lerp(ground[i][1], ground[i + 1][1], (x - ground[i][0]) / (ground[i + 1][0] - ground[i][0]));
    return ground[ground.length - 1][1];
  };
  const r = rng(77);
  let d = '';
  for (let x = -20; x < W + 20; x += 24 + r() * 30) {
    const base = groundAt(x) + 18 + r() * 12, blades = 4 + Math.floor(r() * 4);
    for (let k = 0; k < blades; k++) {
      const bx = x + (k - blades / 2) * 5 + r() * 4, h = 16 + r() * 34, lean = (r() - 0.5) * 26 + (k - blades / 2) * 3;
      d += `M${n1(bx - 2.2)} ${n1(base)} Q${n1(bx + lean * 0.3)} ${n1(base - h * 0.6)} ${n1(bx + lean)} ${n1(base - h)} Q${n1(bx + lean * 0.3 + 3)} ${n1(base - h * 0.55)} ${n1(bx + 2.2)} ${n1(base)}Z`;
    }
  }
  el('path', { d, fill: '#03050b' }, g);
  o.fog = addFog(g, { y: 705, count: 5, seed: 9, rx: 260, ry: 22, op: 0.3, speed: 10, spread: 30 });

  o.clods = Array.from({ length: 22 }, (_, i) => {
    const q = rng(100 + i);
    return { e: el('circle', { fill: '#1a2342', stroke: '#4a669e', 'stroke-width': 0.8, 'stroke-opacity': 0.6 }, g), t0: 0.95 + q() * 1.9, x0: BASE.x + (q() - 0.5) * 130, vx: (q() - 0.5) * 240, vy: -(160 + q() * 190), size: 2.2 + q() * 4.2 };
  });
  o.dust = Array.from({ length: 7 }, (_, i) => {
    const q = rng(200 + i);
    return { e: el('ellipse', { fill: 'url(#gFog)' }, g), t0: 0.8 + q() * 2.0, x0: BASE.x + (q() - 0.5) * 150, size: 38 + q() * 40 };
  });
  o.wisps = Array.from({ length: 26 }, (_, i) => {
    const q = rng(300 + i);
    return { halo: el('circle', { r: 10, fill: 'url(#gHalo)' }, g), dot: el('circle', { r: 1.8, fill: '#e2fbff' }, g), x0: q() * W, y0: 440 + q() * 250, ph: q() * 6.28, sp: 0.6 + q() };
  });

  o.update = (t, tp) => {
    const lift = 27 * smooth(ramp(tp, 0.5, 1.7)) * (1 - 0.55 * smooth(ramp(tp, 3.0, 4.6)));
    const pts = [[BASE.x - 200, GROUND_Y + 1]];
    for (let i = -5; i <= 5; i++) {
      const x = BASE.x + i * 34, h = lift * Math.exp(-(((i * 34) / 118) ** 2)) * (1 + 0.12 * Math.sin(i * 2.7 + tp * 5));
      pts.push([x, GROUND_Y - h]);
    }
    pts.push([BASE.x + 200, GROUND_Y + 1]);
    const top = curve(pts);
    set(o.mound, { d: top + `L${BASE.x + 200} 780L${BASE.x - 200} 780Z` });
    set(o.moundEdge, { d: top });

    for (const c of o.clods) {
      const tau = tp - c.t0;
      if (tau < 0 || tau > 0.8) { set(c.e, { opacity: 0 }); continue; }
      set(c.e, { cx: n1(c.x0 + c.vx * tau), cy: n1(GROUND_Y - lift * 0.8 + c.vy * tau + 450 * 2 * tau * tau), r: n1(c.size), opacity: n1(1 - ramp(tau, 0.6, 0.8)) });
    }
    for (const p of o.dust) {
      const tau = tp - p.t0;
      if (tau < 0 || tau > 1.6) { set(p.e, { opacity: 0 }); continue; }
      const u = tau / 1.6;
      set(p.e, { cx: n1(p.x0 + 20 * u), cy: n1(GROUND_Y - 6 - 30 * u), rx: n1(p.size * (0.5 + u)), ry: n1(p.size * 0.35 * (0.6 + u)), opacity: (0.7 * Math.sin(Math.PI * u) ** 0.7).toFixed(2) });
    }
    for (const w of o.wisps) {
      const x = w.x0 + 38 * Math.sin(t * 0.5 * w.sp + w.ph), y = 440 + (((w.y0 - 440 - t * 7 * w.sp) % 250) + 250) % 250 + 12 * Math.cos(t * 0.4 + w.ph);
      const a = clamp(0.35 + 0.55 * Math.sin(t * 1.7 * w.sp + w.ph * 3)) * clamp(ramp(t, 0.4, 2.0) * 0.8 + 0.2);
      set(w.halo, { cx: n1(x), cy: n1(y), opacity: a.toFixed(2) });
      set(w.dot, { cx: n1(x), cy: n1(y), opacity: a.toFixed(2) });
    }
    updateFog(o.fog, t);
  };
  return o;
}

// ---------------------------------------------------------------- foreground framing
function buildFg(g) {
  const o = {};
  gnarlTree(g, { x: -10, y: 820, len: 360, w: 84, seed: 41, fill: '#04070e', depth: 3, ang: -Math.PI / 2 + 0.2, bend: -0.5, curls: 0.12 });
  gnarlTree(g, { x: 1270, y: 820, len: 300, w: 62, seed: 52, fill: '#04070e', depth: 3, ang: -Math.PI / 2 - 0.3, bend: 0.5, curls: 0.12 });
  o.leaves = Array.from({ length: 7 }, (_, i) => {
    const q = rng(500 + i);
    const x0 = i % 2 ? 40 + q() * 260 : 980 + q() * 240;            // keep the middle of the frame clear
    return { e: el('path', { d: 'M0 -9 Q7 -2 0 10 Q-7 -2 0 -9Z', fill: '#05080f' }, g), x0, y0: q() * 800, ph: q() * 6.28, sp: 40 + q() * 40, sc: 0.8 + q() * 1.1 };
  });
  o.update = t => {
    for (const l of o.leaves) {
      const y = (((l.y0 + l.sp * t) % 820) + 820) % 820 - 50;
      set(l.e, { transform: `translate(${n1(l.x0 + 36 * Math.sin(t * 0.8 + l.ph) + 6 * t)} ${n1(y)}) rotate(${n1(60 * Math.sin(t * 1.3 + l.ph))}) scale(${l.sc.toFixed(2)} ${(l.sc * Math.abs(Math.cos(t * 1.7 + l.ph))).toFixed(2)})` });
    }
  };
  return o;
}
