// Regie: erzeugt aus dem Stadtzustand automatisch die Timeline einer Episode
// (Bau-Reihenfolge, Kamerafahrten, Einblendungen). Reine Daten – läuft in Browser und Node.
import { CATALOG, BUILD_ORDER, itemClass, itemCost, footprint, EURO_PER_FOLLOWER } from './catalog.js';
import { pad3, formatEuro, formatInt } from './util.js';

function boundsOf(objs) {
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  for (const o of objs) {
    if (o.type === 'tree' || o.type === 'lamp') continue;
    const f = footprint(o);
    x0 = Math.min(x0, f[0]);
    z0 = Math.min(z0, f[1]);
    x1 = Math.max(x1, f[2]);
    z1 = Math.max(z1, f[3]);
  }
  if (!isFinite(x0)) return { cx: 0, cz: 0, hx: 40, hz: 40, r: 56 };
  return { cx: (x0 + x1) / 2, cz: (z0 + z1) / 2, hx: (x1 - x0) / 2, hz: (z1 - z0) / 2, r: Math.hypot(x1 - x0, z1 - z0) / 2 };
}
const r1 = (v) => Math.round(v * 10) / 10;
const V = (x, y, z) => [r1(x), r1(y), r1(z)];

const STEP_TEXT = {
  survey: 'GRUNDSTÜCK WIRD VORBEREITET',
  road: 'STRASSEN WERDEN GEBAUT',
  area: 'PLÄTZE ENTSTEHEN',
  building: 'GEBÄUDE WERDEN HOCHGEZOGEN',
  tree: 'BÄUME WERDEN GEPFLANZT',
  lamp: 'STRASSENBELEUCHTUNG WIRD INSTALLIERT',
};

// Finale Luftaufnahme: blickt entlang der längeren Stadtachse (passt ins Hochformat), möglichst Richtung Sonne
export function finalAerial(state, objs) {
  const B = boundsOf(objs);
  const alongX = B.hx >= B.hz;
  const La = Math.max(B.hx, B.hz), Ls = Math.min(B.hx, B.hz);
  const az = ((state.lighting?.sunAzimuth ?? -75) * Math.PI) / 180;
  const sun = [Math.sin(az), Math.cos(az)];
  const sign = alongX ? (sun[0] >= 0 ? 1 : -1) : sun[1] >= 0 ? 1 : -1; // Blickrichtung
  const D = Math.max((Ls / 0.21) * 1.05, La * 2.0, 150);
  const base = alongX ? (sign > 0 ? 180 : 0) : sign > 0 ? -90 : 90; // Winkel der Kameraposition um das Zentrum
  // Blickziel liegt hinter der Stadt: Stadt in der unteren Bildhälfte, Horizont und Himmel oben (Platz für Text)
  const fwd = alongX ? [sign, 0] : [0, sign];
  return {
    type: 'orbit', center: V(B.cx, 0, B.cz), look: V(B.cx + fwd[0] * D * 0.42, 0, B.cz + fwd[1] * D * 0.42),
    r0: r1(D * 0.5), r1: r1(D * 0.8), h0: r1(D * 0.2), h1: r1(D * 0.36),
    a0: base - 14, a1: base + 8, fov0: 46, fov1: 46, ease: 'out',
  };
}

export function makeEpisode(state, number, opts = {}) {
  const duration = opts.duration || 60;
  const fps = 30;
  const all = [...state.roads, ...state.items];
  const upTo = all.filter((o) => (o.episode ?? 1) <= number);
  const fresh = all.filter((o) => (o.episode ?? 1) === number);
  const old = all.filter((o) => (o.episode ?? 1) < number);
  const first = old.length === 0;
  const groups = {};
  for (const c of BUILD_ORDER) groups[c] = [];
  for (const o of fresh) groups[o.type === 'road' ? 'road' : itemClass(o)].push(o);
  const B = boundsOf(upTo), Bn = boundsOf(fresh.length ? fresh : upTo), Bo = boundsOf(old.length ? old : upTo);

  // ---- Zeitplan der Phasen ----
  const T = { intro: 0, survey: 5, build: 9, lamps: 46, final: 52, end: duration };
  const weights = { road: 9, area: 6, building: 17, tree: 5 };
  const present = ['road', 'area', 'building', 'tree'].filter((c) => groups[c].length);
  if (!groups.lamp.length) T.lamps = 48;
  const totalW = present.reduce((s, c) => s + weights[c], 0) || 1;
  const phase = {};
  let t = T.build;
  for (const c of present) {
    const d = ((T.lamps - T.build) * weights[c]) / totalW;
    phase[c] = [r1(t), r1(t + d)];
    t += d;
  }
  // optionale Überschreibung durch Voice-over-Sync: {survey, road, area, building, tree, lamps, final}
  const cues = opts.cues || {};
  if (cues.survey != null) T.survey = cues.survey;
  if (cues.lamps != null) T.lamps = cues.lamps;
  if (cues.final != null) T.final = cues.final;
  const order = ['survey', ...present, 'lamps'];
  const startOf = (k) => (k === 'survey' ? T.survey : k === 'lamps' ? T.lamps : phase[k][0]);
  for (const c of present) if (cues[c] != null) phase[c][0] = cues[c];
  for (let i = 0; i < present.length; i++) phase[present[i]][1] = i + 1 < present.length ? phase[present[i + 1]][0] : T.lamps;
  const surveyEnd = present.length ? phase[present[0]][0] : T.lamps;

  const builds = [], shots = [], captions = [], toasts = [];
  const shot = (s) => shots.push(s);

  // ---- Intro ----
  if (first) {
    shot({ type: 'move', start: 0, end: T.survey, ease: 'inOut', from: { pos: V(B.cx - 150, 12, B.cz + 210), look: V(B.cx - 20, 6, B.cz), fov: 46 }, to: { pos: V(B.cx - 70, 30, B.cz + 120), look: V(B.cx, 0, B.cz - 10), fov: 42 } });
  } else {
    const fa = finalAerial(state, old);
    shot({ ...fa, start: 0, end: T.survey, r0: fa.r1, r1: r1(fa.r1 * 0.8), h0: fa.h1, h1: r1(fa.h1 * 0.8), a0: fa.a1, a1: fa.a1 + 14, ease: 'inOut' });
  }
  // ---- Planung ----
  shot({ type: 'move', start: T.survey, end: surveyEnd, ease: 'inOut', in: 'flash',
    from: { pos: V(Bn.cx + Bn.r * 0.3, Bn.r * 1.0 + 24, Bn.cz + Bn.r * 1.55 + 30), look: V(Bn.cx, 0, Bn.cz), fov: 44 },
    to: { pos: V(Bn.cx - Bn.r * 0.15, Bn.r * 0.8 + 20, Bn.cz + Bn.r * 1.25 + 24), look: V(Bn.cx, 0, Bn.cz - 4), fov: 44 } });
  captions.push({ start: T.survey, end: surveyEnd, key: 'survey', text: STEP_TEXT.survey });

  // ---- Straßen ----
  if (groups.road.length) {
    const [g0, g1] = phase.road;
    const roads = [...groups.road].sort((a, b) => len(b) - len(a));
    const total = roads.reduce((s, r) => s + len(r), 0);
    let ts = g0;
    roads.forEach((r, i) => {
      const d = Math.max(2.5, ((g1 - g0) * len(r)) / total);
      const start = Math.min(ts, g1 - 2.5), end = Math.min(g1 + 1.5, start + d + 1.5);
      builds.push({ id: r.id, start: r1(start), end: r1(end) });
      ts += d;
      if (i < 2) {
        // Verfolgungsfahrt neben der Walze
        const L = len(r), dx = (r.b[0] - r.a[0]) / L, dz = (r.b[1] - r.a[1]) / L;
        let nx = -dz, nz = dx;
        if (nz < 0 || (nz === 0 && nx < 0)) { nx = -nx; nz = -nz; } // Kamera bevorzugt südlich/östlich
        const s0 = i === 0 ? g0 : Math.max(g0, start + 0.4), s1 = i === 0 && roads.length > 1 ? Math.min(g1, builds.at(-1).end - 2.2) : g1;
        if (s1 - s0 > 1.5) {
          // Kamera folgt exakt der Asphaltkante (Walze): q = Baufortschritt des Asphalts zur Zeit t
          const tA = start + 0.18 * (end - start), tB = start + 0.82 * (end - start);
          const q = (tt) => Math.min(1.04, (tt - tA) / (tB - tA));
          const P = (qq) => [r.a[0] + dx * L * qq, r.a[1] + dz * L * qq];
          const [pa, pb] = [P(q(s0)), P(q(s1))];
          shot({ type: 'move', start: r1(s0), end: r1(s1), ease: 'linear', in: i === 0 ? 'flash' : 'cut',
            from: { pos: V(pa[0] + nx * 27 - dx * 20, 14, pa[1] + nz * 27 - dz * 20), look: V(pa[0] + dx * 3, 1, pa[1] + dz * 3), fov: 42 },
            to: { pos: V(pb[0] + nx * 22 - dx * 15, 10, pb[1] + nz * 22 - dz * 15), look: V(pb[0] + dx * 3, 1, pb[1] + dz * 3), fov: 40 } });
        }
      }
    });
    captions.push({ start: g0, end: g1, key: 'road', text: STEP_TEXT.road });
  }

  // ---- Plätze / Flächen ----
  if (groups.area.length) {
    const [g0, g1] = phase.area;
    groups.area.forEach((it, i) => {
      const st = g0 + (i * (g1 - g0) * 0.4) / groups.area.length;
      builds.push({ id: it.id, start: r1(st), end: r1(g1 + 0.6) });
      toasts.push(toast(it, g1 + 0.2));
    });
    const it = groups.area[0], s = Math.max(...(CATALOG[it.type]?.lot || [20, 20]), it.w || 0, it.d || 0);
    shot({ type: 'orbit', start: g0, end: g1, in: 'flash', center: V(it.x, 0, it.z), r0: r1(s * 1.5 + 12), r1: r1(s * 1.15 + 10), h0: r1(s * 0.75 + 8), h1: r1(s * 0.5 + 5), a0: 62, a1: 112, fov0: 40, fov1: 38, lookY: 1, ease: 'inOut' });
    const names = [...new Set(groups.area.map((a) => CATALOG[a.type]?.label.toUpperCase()))];
    captions.push({ start: g0, end: g1, key: 'area', text: names.length === 1 ? `${names[0]} ENTSTEHT` : STEP_TEXT.area });
  }

  // ---- Gebäude ----
  if (groups.building.length) {
    const [g0, g1] = phase.building;
    const G = g1 - g0;
    const sorted = [...groups.building].sort((a, b) => itemCost(b) - itemCost(a) || 0);
    const heroes = groups.building.length <= 3 ? [...groups.building] : sorted.slice(0, 3);
    const k = heroes.length, slice = G / k;
    const heroWindows = [];
    heroes.forEach((it, i) => {
      const st = Math.max(g0 - 1.5, g0 + i * slice - slice * 0.26), en = g0 + (i + 1) * slice + 0.3;
      builds.push({ id: it.id, start: r1(st), end: r1(en) });
      heroWindows.push({ from: r1(g0 + i * slice), to: r1(g0 + (i + 1) * slice), start: r1(st), end: r1(en) });
      toasts.push(toast(it, en - 0.4));
      const c = CATALOG[it.type], s = Math.max(it.w || c.w, it.d || c.d), h = heightOf(it);
      const face = 90 - (it.rot || 0); // Winkel, aus dem man die Vorderseite sieht
      const dir = i % 2 ? -1 : 1;
      shot({ type: 'orbit', start: r1(g0 + i * slice), end: r1(g0 + (i + 1) * slice), in: i === 0 ? 'flash' : 'whip',
        center: V(it.x, 0, it.z), r0: r1(s * 2.3 + h * 1.1 + 14), r1: r1(s * 1.9 + h + 10), h0: r1(4 + h * 0.4), h1: r1(9 + h * 0.8),
        a0: face - 42 * dir, a1: face + 22 * dir, fov0: 42, fov1: 38, lookY: r1(h * 0.42), ease: 'inOut' });
    });
    const rest = groups.building.filter((b) => !heroes.includes(b));
    rest.forEach((it, i) => {
      const d = Math.max(5, G * 0.55);
      const st = g0 + ((G - d) * i) / Math.max(1, rest.length - 1 || 1);
      builds.push({ id: it.id, start: r1(st), end: r1(Math.min(g1 + 0.5, st + d)) });
      toasts.push(toast(it, Math.min(g1, st + d)));
    });
    const kinds = new Set(groups.building.map((b) => b.type));
    captions.push({ start: g0, end: g1, key: 'building', text: kinds.size === 1 && kinds.has('house') ? 'HÄUSER WERDEN HOCHGEZOGEN' : STEP_TEXT.building,
      sub: [{ at: 0.0, text: 'FUNDAMENTE ENTSTEHEN' }, { at: 0.2, text: 'WÄNDE WERDEN HOCHGEZOGEN' }, { at: 0.6, text: 'DÄCHER WERDEN FERTIGGESTELLT' }, { at: 0.8, text: 'FENSTER, TÜREN & GARTEN' }], heroes: heroWindows });
  }

  // ---- Bäume ----
  if (groups.tree.length) {
    const [g0, g1] = phase.tree;
    const n = groups.tree.length;
    const sorted = [...groups.tree].sort((a, b) => a.x - b.x);
    sorted.forEach((it, i) => {
      const st = g0 + 0.3 + ((g1 - g0 - 1.6) * i) / Math.max(1, n - 1);
      builds.push({ id: it.id, start: r1(st), end: r1(st + 1.1) });
    });
    shot({ type: 'move', start: g0, end: g1, ease: 'inOut', in: 'whip',
      from: { pos: V(B.cx - B.hx * 0.8, 30 + B.r * 0.14, B.cz + B.hz + 85), look: V(B.cx - B.hx * 0.3, 2, B.cz), fov: 44 },
      to: { pos: V(B.cx + B.hx * 0.5, 24 + B.r * 0.12, B.cz + B.hz + 70), look: V(B.cx + B.hx * 0.15, 2, B.cz - 5), fov: 44 } });
    captions.push({ start: g0, end: g1, key: 'tree', text: STEP_TEXT.tree });
  }

  // ---- Laternen + Dämmerung ----
  const lampsEnd = T.final;
  if (groups.lamp.length) {
    const n = groups.lamp.length;
    [...groups.lamp].sort((a, b) => b.x - a.x).forEach((it, i) => {
      const st = T.lamps + 0.2 + ((lampsEnd - T.lamps - 3.2) * i) / Math.max(1, n - 1);
      builds.push({ id: it.id, start: r1(st), end: r1(st + 0.9) });
    });
    captions.push({ start: T.lamps, end: lampsEnd, key: 'lamp', text: STEP_TEXT.lamp });
  } else captions.push({ start: T.lamps, end: lampsEnd, key: 'lamp', text: 'DIE LICHTER GEHEN AN' });
  // Fahrt entlang der Hauptachse Richtung Sonnenuntergang
  const main = state.roads.find((r) => r.kind === 'main') || state.roads[0];
  const mz = main ? main.a[1] : B.cz;
  shot({ type: 'move', start: T.lamps, end: lampsEnd, ease: 'inOut', in: 'flash',
    from: { pos: V(B.cx + B.hx * 0.98, 15, mz + 9), look: V(B.cx - B.hx, 3, mz - 2), fov: 44 },
    to: { pos: V(B.cx + B.hx * 0.5, 10, mz + 3), look: V(B.cx - B.hx, 5, mz - 1), fov: 40 } });

  // ---- Finale Luftaufnahme ----
  const fa = finalAerial(state, upTo);
  shot({ ...fa, start: T.final, end: duration, in: 'flash' });

  shots.sort((a, b) => a.start - b.start);
  // Überlappungen kappen; bei Lücken hält die Kamera ihre Endposition
  for (let i = 0; i < shots.length; i++) shots[i].end = i + 1 < shots.length ? Math.min(shots[i].end, shots[i + 1].start) : duration;

  const followers = opts.followers ?? state.followers ?? 0;
  const spent = fresh.reduce((s, o) => s + itemCost(o), 0);
  return {
    number, title: opts.title || (first ? 'Die erste Stadt' : `Die Stadt wächst`), duration, fps, width: 1080, height: 1920,
    followers, budget: followers * EURO_PER_FOLLOWER, spent,
    todKeys: [[0, 0.1], [Math.max(1, T.lamps - 4), 0.22], [T.lamps + 1.2, 0.62], [T.lamps + 4, 0.92], [T.final + 1, 1]],
    effects: [{ type: 'survey', start: T.survey + 0.3, end: surveyEnd }],
    phases: Object.fromEntries(order.map((k) => [k, startOf(k)]).concat([['final', T.final]])),
    builds, shots, captions, toasts: toasts.filter(Boolean),
    intro: {
      start: 0.3, end: T.survey - 0.3, kicker: `EPISODE ${pad3(number)}`, title: state.name || 'AUSLÄNDERSTADT',
      line: first ? ['0 FOLLOWER.', 'EIN LEERES GRUNDSTÜCK.'] : [`${formatInt(followers)} FOLLOWER`, `${formatEuro(followers * EURO_PER_FOLLOWER)} BAU-BUDGET`],
      rule: '1 FOLLOWER = 1.000 € BAU-BUDGET',
    },
    endCard: { start: T.final + 1.6, title: `WIE GROSS WIRD ${state.name || 'AUSLÄNDERSTADT'}?`, sub: 'FOLGE, UM DEINE STADT WACHSEN ZU LASSEN.' },
    voiceover: opts.voiceover || null,
    finalCamera: fa,
  };
}

function len(r) {
  return Math.hypot(r.b[0] - r.a[0], r.b[1] - r.a[1]);
}
function heightOf(it) {
  switch (it.type) {
    case 'highrise': return (it.floors || 20) * 3.2 + 10;
    case 'apartment': return (it.floors || 5) * 3.2;
    case 'mosque': return 30;
    case 'townhall': return 26;
    case 'statue': return 16;
    case 'mall': return 16;
    case 'house': return 9;
    default: return 9;
  }
}
function toast(it, at) {
  const c = CATALOG[it.type];
  if (!c) return null;
  const cost = itemCost(it);
  return { at: r1(at), text: (it.name || c.label).toUpperCase(), cost };
}
