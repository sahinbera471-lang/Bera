// Straßenbau: achsenparallele Straßen mit Schotterbett, Asphalt, Gehwegen, Bordsteinen und Markierungen.
import { Kit, box } from './kit.js';

const AXIS = (r) => (Math.abs(r.b[0] - r.a[0]) >= Math.abs(r.b[1] - r.a[1]) ? 0 : 1);

// Geometrische Daten einer Straße (gekürzt an Einmündungen)
export function roadFrame(road, all) {
  const ax = AXIS(road), px = 1 - ax;
  const sgn = Math.sign(road.b[ax] - road.a[ax]) || 1;
  const w = road.width || 7, sw = road.sidewalk ?? 2.5;
  let a = [...road.a], b = [...road.b];
  let trimA = 0, trimB = 0;
  const joins = []; // Querstraßen: {t (Position entlang), w, lo, hi (Ausdehnung quer)}
  for (const q of all) {
    if (q.id === road.id || AXIS(q) === ax) continue;
    const qw = q.width || 7, qsw = q.sidewalk ?? 2.5;
    const qc = q.a[ax]; // Position der Querstraße entlang unserer Achse
    const qlo = Math.min(q.a[px], q.b[px]), qhi = Math.max(q.a[px], q.b[px]);
    // liegt unser Endpunkt in der Fahrbahn der Querstraße? -> kürzen
    for (const end of ['a', 'b']) {
      const P = end === 'a' ? a : b;
      if (P[px] >= qlo - 0.1 && P[px] <= qhi + 0.1 && Math.abs(P[ax] - qc) < qw / 2 - 0.01) {
        const dirIn = end === 'a' ? sgn : -sgn;
        P[ax] = qc + dirIn * (qw / 2);
        if (end === 'a') trimA = qsw;
        else trimB = qsw;
      }
    }
    joins.push({ c: qc, w: qw, lo: qlo, hi: qhi });
  }
  const L = Math.abs(b[ax] - a[ax]);
  const lo = Math.min(road.a[ax], road.b[ax]), hi = Math.max(road.a[ax], road.b[ax]);
  const cuts = { 1: [], '-1': [], mark: [] };
  for (const j of joins) {
    const t = (j.c - a[ax]) * sgn;
    if (j.c < lo - j.w || j.c > hi + j.w) continue;
    for (const s of [1, -1]) {
      // Gehwegstreifen auf Seite s (lokal +z / -z) in Weltkoordinate quer
      const side = road.a[px] + s * sgn * (ax === 0 ? 1 : -1) * (w / 2 + sw / 2);
      if (j.lo < side + 0.3 && j.hi > side - 0.3) {
        cuts[s].push([t - j.w / 2, t + j.w / 2]);
        cuts.mark.push([t - j.w / 2 - 1.2, t + j.w / 2 + 1.2]);
      }
    }
  }
  const theta = ax === 0 ? (sgn > 0 ? 0 : Math.PI) : sgn > 0 ? -Math.PI / 2 : Math.PI / 2;
  return { ax, sgn, w, sw, a, b, L, trimA, trimB, cuts, theta, dir: ax === 0 ? [sgn, 0] : [0, sgn] };
}

function subtract(from, to, cuts) {
  let segs = [[from, to]];
  for (const [c0, c1] of cuts) {
    const next = [];
    for (const [s0, s1] of segs) {
      if (c1 <= s0 || c0 >= s1) next.push([s0, s1]);
      else {
        if (c0 > s0) next.push([s0, c0]);
        if (c1 < s1) next.push([c1, s1]);
      }
    }
    segs = next;
  }
  return segs.filter(([s0, s1]) => s1 - s0 > 0.2);
}

// mats: MatLib; wenn die Straße animiert wird, enthält mats.planes {foundation, structure, details}
export function buildRoad(road, all, mats, index = 0) {
  const f = roadFrame(road, all);
  const kit = new Kit(mats);
  const { w, sw, L } = f;
  const yOff = (index % 7) * 0.004;
  // Schotterbett
  kit.add('foundation', 'gravel', box(L, 0.06, w + 2 * sw + 0.8, 3), L / 2, 0.02, 0);
  // Asphalt
  kit.add('structure', 'asphalt', box(L, 0.08, w, 6), L / 2, 0.075 + yOff, 0);
  // Gehwege + Bordstein
  if (sw > 0)
    for (const s of [1, -1]) {
      const segs = subtract(f.trimA, L - f.trimB, f.cuts[s]);
      for (const [s0, s1] of segs) {
        const len = s1 - s0, cx = (s0 + s1) / 2;
        kit.add('details', 'pavers', box(len, 0.2, sw - 0.2, 2), cx, 0.1, s * (w / 2 + 0.2 + (sw - 0.2) / 2));
        kit.add('details', 'concrete:#c9c5bc', box(len, 0.22, 0.2, 2), cx, 0.11, s * (w / 2 + 0.1));
      }
    }
  // Markierungen
  const ym = 0.118 + yOff;
  if (road.kind === 'main' || road.centerLine) {
    for (const [s0, s1] of subtract(1, L - 1, f.cuts.mark)) for (let x = s0 + 0.5; x + 3 <= s1; x += 7.5) kit.add('details', 'line', box(3, 0.01, 0.15), x + 1.5, ym, 0);
  }
  for (const t of road.crosswalks || []) {
    const x = (t - (f.a[f.ax] - road.a[f.ax]) * f.sgn);
    for (let z = -w / 2 + 0.5; z < w / 2 - 0.3; z += 1) kit.add('details', 'line', box(3.2, 0.01, 0.5), x, ym, z + 0.25);
  }
  const root = kit.finalize();
  root.position.set(f.a[0], 0, f.a[1]);
  root.rotation.y = f.theta;
  root.userData.frame = f;
  root.userData.item = road;
  for (const m of root.userData.parts.structure.children) m.castShadow = false;
  for (const m of root.userData.parts.foundation.children) m.castShadow = false;
  return root;
}
