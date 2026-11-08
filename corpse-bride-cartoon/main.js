'use strict';
/* Scene assembly and the per-frame entry point used by render.mjs. */

const L = {};
for (const n of ['sky', 'far', 'mid', 'bride', 'front', 'fg']) L[n] = el('g', null, svg);

const sky = buildSky(L.sky), far = buildFar(L.far), mid = buildMid(L.mid), front = buildFront(L.front), fg = buildFg(L.fg);

// bride plane: glow behind her, the puppet (boil + dissolve mask), dissolve glow, butterflies
const brideGlow = el('ellipse', { cx: BASE.x, rx: 230, ry: 340, fill: 'url(#gBrideGlow)', opacity: 0 }, L.bride);
const brideWrap = el('g', { filter: 'url(#fBoil)' }, L.bride);
const bride = buildBride(brideWrap);
const edgeGlow = el('ellipse', { fill: '#a8ecff', opacity: 0, filter: 'url(#fBlur10)' }, L.bride);
const petals = buildPetals(L.bride, 10);
const flock = el('g', { filter: 'url(#fGlow)' }, L.bride);
const swarm = buildSwarm(flock, 64);
const hero = buildHero(flock);
const dissolveGradient = document.getElementById('gDissolve');

// overlays (screen space)
el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#gVignette)' }, svg);
el('rect', { x: 0, y: 0, width: W, height: H, filter: 'url(#fGrain)' }, svg);
const title = el('g', { opacity: 0 }, svg);
const caption = 'Пока смерть не разлучит нас…';
for (const [fill, filter] of [['#8fc6ff', 'url(#fBlur10)'], ['#e6f3ff', null]]) {
  const txt = el('text', { x: 640, y: 650, 'text-anchor': 'middle', 'font-family': 'FreeSerif, "DejaVu Serif", serif', 'font-style': 'italic', 'font-size': 46, 'letter-spacing': 1.5, fill }, title);
  if (filter) set(txt, { filter });
  txt.textContent = caption;
}
const fade = el('rect', { x: 0, y: 0, width: W, height: H, fill: '#000' }, svg);

function renderFrame(t) {
  t = clamp(t, 0, DURATION - 1e-4);
  const tp = Math.floor(t / STEP + 1e-6) * STEP;            // puppet clock: one pose per two video frames
  for (const n in L) set(L[n], { transform: planeTransform(n, t) });
  const moon = toPlane([MOON.x, MOON.y], 'sky', 'bride', t);
  const moonR = MOON.r * planeScale('sky', t) / planeScale('bride', t);

  sky.update(t); far.update(t, tp); mid.update(t); front.update(t, tp); fg.update(t);

  const s = brideState(tp);
  const h = heroState(tp, s, moon);
  const attention = smooth(ramp(tp, 3.9, 4.3)) * (1 - smooth(ramp(tp, 8.0, 8.6)));
  finishHead(s, h.vis ? [lerp(moon[0], h.x, attention), lerp(moon[1], h.y, attention)] : moon);
  applyBride(bride, s);
  boilTurbulence.setAttribute('seed', 1 + Math.round(tp / STEP) % 97);

  // dissolve into butterflies
  const front_ = dissolveFront(tp);
  const dissolving = tp > DIS.t0 - 0.2;
  const gone = front_ < BASE.y - BS * 640;
  set(brideWrap, { display: gone ? 'none' : 'inline', mask: dissolving ? 'url(#mDissolve)' : 'none' });
  set(dissolveGradient, { y1: n1(front_ - 90), y2: n1(front_ + 90) });
  const localY = (front_ - BASE.y) / BS;
  set(edgeGlow, { cx: BASE.x, cy: n1(front_), rx: n1((bodyHalfWidth(clamp(localY, -560, 0)) + 14) * BS), ry: 22, opacity: (gone || !dissolving ? 0 : 0.55 * Math.sin(Math.PI * ramp(tp, DIS.t0, DIS.t1)) ** 0.5).toFixed(2) });
  set(brideGlow, { cy: n1(BASE.y - 250 * BS + BS * s.riseY * 0.6), opacity: clamp(s.glow).toFixed(2) });

  applyPetals(petals, tp);
  applySwarm(swarm, tp, moon, moonR);
  applyHero(hero, h, moon, moonR);

  grainTurbulence.setAttribute('seed', Math.round(t * 24) + 1);
  set(title, { opacity: (smooth(ramp(t, 8.3, 9.0)) * (1 - smooth(ramp(t, 9.5, 9.96)))).toFixed(3) });
  set(fade, { opacity: Math.max(1 - ramp(t, 0, 0.8), ramp(t, 9.4, 9.96)).toFixed(3) });
  return true;
}
