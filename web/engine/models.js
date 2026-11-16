// Prozedurale 3D-Modelle aller Gebäudetypen. Jedes Modell legt seine Geometrie in Bauteile
// (plot, foundation, structure, roof, details, garden), die city.js nacheinander "baut".
import * as THREE from 'three';
import { Kit, box, plane, cyl, sphere, dome, cone, gable, addTree } from './kit.js';
import { Tex } from './textures.js';
import { mulberry32, hashString } from './util.js';
import { CATALOG } from './catalog.js';

const PI = Math.PI;
const F = 0.3; // Oberkante Fundament

function wallPos(w, d, side, u, off = 0) {
  switch (side) {
    case 'f': return { x: u, z: d / 2 + off, ry: 0 };
    case 'b': return { x: -u, z: -d / 2 - off, ry: PI };
    case 'r': return { x: w / 2 + off, z: -u, ry: PI / 2 };
    default: return { x: -w / 2 - off, z: u, ry: -PI / 2 };
  }
}
// Element an eine Wand hängen; ox/oz verschieben das Wandzentrum (für Anbauten)
function onWall(kit, part, mat, geom, w, d, side, u, y, off, ox = 0, oz = 0, rx = 0) {
  const p = wallPos(w, d, side, u, off);
  kit.add(part, mat, geom, p.x + ox, y, p.z + oz, p.ry, rx);
}

function windowAt(kit, w, d, side, u, y, ww, wh, o = {}) {
  const part = o.part || 'details', ox = o.ox || 0, oz = o.oz || 0;
  onWall(kit, part, o.frame || 'white', box(ww + 0.18, wh + 0.18, 0.08), w, d, side, u, y, 0.04, ox, oz);
  onWall(kit, part, o.lit ? 'glassLit' : 'glass', box(ww, wh, 0.04), w, d, side, u, y, 0.085, ox, oz);
  if (o.bars !== false) {
    onWall(kit, part, o.frame || 'white', box(0.05, wh, 0.03), w, d, side, u, y, 0.115, ox, oz);
    onWall(kit, part, o.frame || 'white', box(ww, 0.05, 0.03), w, d, side, u, y + wh * 0.18, 0.115, ox, oz);
  }
  if (o.sill !== false) onWall(kit, part, 'color:#d9d4c8', box(ww + 0.3, 0.07, 0.24), w, d, side, u, y - wh / 2 - 0.1, 0.12, ox, oz);
  if (o.shutters) {
    for (const s of [-1, 1])
      onWall(kit, part, 'color:' + o.shutters, box(ww * 0.46, wh + 0.1, 0.05), w, d, side, u + s * (ww * 0.74 + 0.08), y, 0.05, ox, oz);
  }
  if (o.flowers) {
    onWall(kit, part, 'wood', box(ww + 0.2, 0.2, 0.26), w, d, side, u, y - wh / 2 - 0.26, 0.2, ox, oz);
    onWall(kit, part, 'color:' + o.flowers, box(ww + 0.1, 0.14, 0.22), w, d, side, u, y - wh / 2 - 0.1, 0.2, ox, oz);
  }
}

function doorAt(kit, w, d, side, u, o = {}) {
  const ox = o.ox || 0, oz = o.oz || 0, dw = o.w || 1.05, dh = o.h || 2.15;
  onWall(kit, 'details', 'white', box(dw + 0.2, dh + 0.12, 0.1), w, d, side, u, F + dh / 2 + 0.05, 0.04, ox, oz);
  onWall(kit, 'details', o.mat || 'wood:#a86f44', box(dw, dh, 0.08), w, d, side, u, F + dh / 2, 0.09, ox, oz);
  onWall(kit, 'details', 'concrete', box(dw + 0.7, 0.3, 0.9, 2), w, d, side, u, 0.15, 0.45, ox, oz);
  if (o.canopy !== false) onWall(kit, 'details', o.canopyMat || 'color:#5a5450', box(dw + 0.9, 0.1, 1.0), w, d, side, u, F + dh + 0.35, 0.5, ox, oz);
}

// Satteldach (First entlang x) inkl. Giebelwänden
function gableRoof(kit, w, d, yBase, rh, roofMat, wallMat, ov = 0.55, cx = 0, cz = 0) {
  const a = Math.atan2(rh, d / 2), hd = d / 2 + ov, sl = hd / Math.cos(a);
  if (wallMat) {
    kit.add('structure', wallMat, gable(d, rh), cx + w / 2 - 0.01, yBase, cz);
    kit.add('structure', wallMat, gable(d, rh), cx - w / 2 + 0.01, yBase, cz);
  }
  for (const s of [1, -1]) {
    kit.add('roof', roofMat, box(w + ov * 2, 0.16, sl, 1.7), cx, yBase + rh - (hd / 2) * Math.tan(a) + 0.1, cz + (s * hd) / 2, 0, s * a);
    kit.add('roof', 'metal:#6b6f73', box(w + ov * 2, 0.1, 0.14), cx, yBase - ov * Math.tan(a) + 0.08, cz + s * (hd + 0.04));
  }
  kit.add('roof', 'color:#5c2f24', box(w + ov * 2, 0.14, 0.34), cx, yBase + rh + 0.2, cz);
}

function flatRoof(kit, w, d, y, o = {}) {
  const cx = o.cx || 0, cz = o.cz || 0;
  kit.add('roof', o.mat || 'color:#4a4c50', box(w - 0.3, 0.12, d - 0.3), cx, y + 0.08, cz);
  const pm = o.parapet || 'color:#d8d3c8';
  for (const s of [-1, 1]) {
    kit.add('roof', pm, box(w + 0.2, 0.7, 0.3), cx, y + 0.3, cz + s * (d / 2 - 0.1));
    kit.add('roof', pm, box(0.3, 0.7, d + 0.2), cx + s * (w / 2 - 0.1), y + 0.3, cz);
  }
}

function bench(kit, part, x, z, ry) {
  const c = Math.cos(ry), s = Math.sin(ry);
  kit.add(part, 'wood:#b98654', box(1.8, 0.08, 0.5), x, 0.6, z, ry);
  kit.add(part, 'wood:#b98654', box(1.8, 0.5, 0.07), x - s * 0.24, 0.95, z - c * 0.24, ry);
  for (const e of [-0.75, 0.75]) kit.add(part, 'metal:#333', box(0.07, 0.5, 0.45), x + c * e, 0.35, z - s * e, ry);
}

function car(kit, part, x, z, ry, color) {
  kit.add(part, 'color:' + color + ':0.35', box(1.8, 0.7, 4.3), x, 0.72, z, ry);
  kit.add(part, 'color:#1c2733:0.15', box(1.62, 0.58, 2.2), x - Math.sin(ry) * 0.2, 1.33, z - Math.cos(ry) * 0.2, ry);
  for (const [a, b] of [[-0.9, 1.35], [0.9, 1.35], [-0.9, -1.35], [0.9, -1.35]]) {
    const wx = x + Math.cos(ry) * a + Math.sin(ry) * b, wz = z - Math.sin(ry) * a + Math.cos(ry) * b;
    kit.add(part, 'color:#16171a', cyl(0.34, 0.34, 0.24, 10), wx, 0.36, wz, ry, 0, PI / 2);
  }
}
const CAR_COLORS = ['#c9ccd1', '#2b2d31', '#f1f1ee', '#8a1f1f', '#274c7a', '#5c6166', '#d8d2c2'];

function fountain(kit, part, x, z, r = 2.2) {
  kit.add(part, 'concrete:#e6dfd2', cyl(r, r + 0.15, 0.7, 20), x, 0.45, z);
  kit.add(part, 'water', cyl(r - 0.25, r - 0.25, 0.1, 20), x, 0.78, z);
  kit.add(part, 'concrete:#e6dfd2', cyl(0.22, 0.32, 1.9, 10), x, 1.2, z);
  kit.add(part, 'concrete:#e6dfd2', cyl(r * 0.45, 0.2, 0.3, 14), x, 2.1, z);
  kit.add(part, 'water', cyl(r * 0.4, r * 0.4, 0.06, 14), x, 2.27, z);
}

function planter(kit, part, x, z, variant = 0) {
  kit.add(part, 'concrete:#cfc8bb', box(1.3, 0.6, 1.3, 2), x, 0.42, z);
  addTree(kit, part, 'bush', variant, x, z, 1.0);
  kit.bins.get(part + '|foliage').at(-1).translate(0, 0.6, 0);
}

// ------------------------------------------------------------------ Wohnhaus
function house(kit, it, rnd) {
  const w = it.w || 10, d = it.d || 8.5, floors = it.floors || 2;
  const H = floors * 2.9 + 0.2, rh = it.roofH || 3.2;
  const lw = w + 12, ld = d + 14;
  kit.height = F + H;
  kit.roofBase = F + H - 0.6;
  kit.roofTop = F + H + rh + 1.6;
  kit.size = [lw, ld];
  const wall = 'plaster:' + (it.wall || '#f3ead8'), roof = 'roof:' + (it.roof || '#a8472f');
  kit.add('plot', 'dirt', plane(lw - 2, ld - 2, 5), 0, 0.03, -2);
  kit.add('foundation', 'concrete', box(w + 0.5, 0.6, d + 0.5, 3), 0, 0, 0);
  kit.add('structure', wall, box(w, H, d, 2.5), 0, F + H / 2, 0);
  kit.add('structure', 'color:#8f877b', box(w + 0.08, 0.55, d + 0.08), 0, F + 0.27, 0);
  gableRoof(kit, w, d, F + H, rh, roof, wall);
  // Schornstein
  kit.add('roof', 'brick', box(0.75, 1.9, 0.75, 1.2), w * 0.24, F + H + rh - 0.2, -d * 0.16);
  kit.add('roof', 'color:#3c3c3c', box(0.95, 0.12, 0.95), w * 0.24, F + H + rh + 0.8, -d * 0.16);

  const sh = it.shutters || null, fl = it.flowers || null;
  const y1 = F + 1.55, y2 = F + 2.9 + 1.5;
  const doorU = -w * 0.22;
  doorAt(kit, w, d, 'f', doorU, { mat: 'wood:' + (it.door || '#a86f44'), canopy: !it.balcony });
  windowAt(kit, w, d, 'f', w * 0.2, y1, 1.7, 1.35, { lit: rnd() < 0.7, shutters: sh, flowers: fl });
  if (floors > 1) {
    if (it.balcony) {
      windowAt(kit, w, d, 'f', doorU, F + 2.9 + 1.15, 1.1, 2.1, { lit: true, sill: false });
      kit.add('details', 'concrete', box(2.9, 0.14, 1.3), doorU, F + 2.95, d / 2 + 0.65);
      kit.add('details', 'metal:#2f3133', box(2.9, 0.06, 0.06), doorU, F + 3.95, d / 2 + 1.27);
      for (const e of [-1.42, 1.42]) kit.add('details', 'metal:#2f3133', box(0.06, 0.06, 1.3), doorU + e, F + 3.95, d / 2 + 0.65);
      for (let i = 0; i <= 8; i++) kit.add('details', 'metal:#2f3133', box(0.04, 0.95, 0.04), doorU - 1.42 + i * 0.355, F + 3.47, d / 2 + 1.27);
      for (const e of [-1.42, 1.42]) for (let i = 0; i < 3; i++) kit.add('details', 'metal:#2f3133', box(0.04, 0.95, 0.04), doorU + e, F + 3.47, d / 2 + 0.2 + i * 0.4);
      if (fl) kit.add('details', 'color:' + fl, box(2.6, 0.2, 0.2), doorU, F + 3.85, d / 2 + 1.4);
    } else windowAt(kit, w, d, 'f', doorU, y2, 1.2, 1.3, { lit: rnd() < 0.5, shutters: sh });
    windowAt(kit, w, d, 'f', w * 0.2, y2, 1.2, 1.3, { lit: rnd() < 0.5, shutters: sh });
  }
  for (let f = 0; f < floors; f++) {
    const y = f ? y2 : y1;
    windowAt(kit, w, d, 'b', -w * 0.24, y, 1.2, 1.3, { lit: rnd() < 0.5 });
    windowAt(kit, w, d, 'b', w * 0.24, y, 1.2, 1.3, { lit: rnd() < 0.5 });
    windowAt(kit, w, d, 'l', 0, y, 1.1, 1.3, { lit: rnd() < 0.5, shutters: sh });
    if (!(it.garage && f === 0)) windowAt(kit, w, d, 'r', 0, y, 1.1, 1.3, { lit: rnd() < 0.5, shutters: sh });
  }
  for (const s of ['l', 'r']) windowAt(kit, w, d, s, 0, F + H + rh * 0.36, 0.8, 0.8, { lit: rnd() < 0.4, sill: false });
  // Satellitenschüssel
  if (it.dish !== false) {
    kit.add('details', 'white', cyl(0.42, 0.42, 0.05, 14), -w / 2 - 0.3, F + H - 0.5, -d * 0.25, -PI / 2 + 0.5, PI / 2 - 0.4);
    kit.add('details', 'metal:#888', box(0.05, 0.05, 0.4), -w / 2 - 0.15, F + H - 0.6, -d * 0.25, PI / 2);
  }
  // Garage
  if (it.garage) {
    const gw = 3.6, gd = 6, gx = w / 2 + gw / 2, gz = d / 2 - gd / 2 - 0.6;
    kit.add('foundation', 'concrete', box(gw + 0.3, 0.6, gd + 0.3, 3), gx, 0, gz);
    kit.add('structure', wall, box(gw, 2.7, gd, 2.5), gx, F + 1.35, gz);
    kit.add('details', 'color:#4a4c50', box(gw + 0.3, 0.14, gd + 0.3), gx, F + 2.78, gz);
    kit.add('details', 'color:#e8e6e1:0.5', box(2.7, 2.15, 0.08), gx, F + 1.08, gz + gd / 2 + 0.05);
    for (let i = 1; i < 5; i++) kit.add('details', 'color:#bdbab3', box(2.7, 0.03, 0.03), gx, F + i * 0.43, gz + gd / 2 + 0.1);
    kit.add('garden', 'pavers:#d9d2c4', plane(3.2, d / 2 + 5 - (gz + gd / 2), 1.6), gx, 0.07, (gz + gd / 2 + d / 2 + 5) / 2);
    if (it.car) car(kit, 'garden', gx, gz + gd / 2 + 3.2, 0, it.car);
  }
  // Garten
  kit.add('garden', 'lawn:' + (it.lawn || '#8fcb5c'), plane(lw, ld, 6), 0, 0.05, -2);
  const zb = -(d / 2 + 9);
  kit.add('garden', 'hedge', box(lw, 1.15, 0.8, 2), 0, 0.58, zb + 0.4);
  for (const s of [-1, 1]) kit.add('garden', 'hedge', box(0.8, 1.15, ld - 3, 2), s * (lw / 2 - 0.4), 0.58, -3.5);
  kit.add('garden', 'pavers:#d9d2c4', plane(1.5, 4.2, 1.5), doorU, 0.07, d / 2 + 2.9);
  // Holzzaun vorne
  const zf = d / 2 + 4.9;
  for (let x = -lw / 2 + 0.4; x <= lw / 2 - 0.3; x += 0.9) {
    if (Math.abs(x - doorU) < 1.1 || (it.garage && x > w / 2 - 0.4 && x < w / 2 + 4)) continue;
    kit.add('garden', 'wood:#d8c9ad', box(0.12, 0.85, 0.06), x, 0.45, zf);
  }
  for (const [x0, x1] of [[-lw / 2 + 0.3, doorU - 1.1], [doorU + 1.1, it.garage ? w / 2 - 0.4 : lw / 2 - 0.3]])
    if (x1 > x0) kit.add('garden', 'wood:#d8c9ad', box(x1 - x0, 0.08, 0.05), (x0 + x1) / 2, 0.62, zf);
  addTree(kit, 'garden', it.tree || 'deciduous', (rnd() * 5) | 0, -lw / 2 + 3.6, zb + 4, 0.72 + rnd() * 0.2, rnd() * 6);
  if (!it.pergola) addTree(kit, 'garden', 'cypress', (rnd() * 5) | 0, lw / 2 - 3, zb + 3.4, 0.6, rnd() * 6);
  for (let i = 0; i < 4; i++) addTree(kit, 'garden', 'bush', i, w * 0.05 + i * 1.3, d / 2 + 0.9 + (i % 2) * 0.3, 0.8);
  if (it.pergola) {
    // Laube mit Weinranken und Teetisch
    const px = lw / 2 - 4.2, pz = zb + 4.4;
    for (const [a, b] of [[-1.6, -1.4], [1.6, -1.4], [-1.6, 1.4], [1.6, 1.4]]) kit.add('garden', 'wood:#8c6239', box(0.14, 2.4, 0.14), px + a, 1.2, pz + b);
    for (let i = -2; i <= 2; i++) kit.add('garden', 'wood:#8c6239', box(0.1, 0.1, 3.4), px + i * 0.8, 2.45, pz);
    kit.add('garden', 'hedge:#6aa13f', box(3.7, 0.25, 3.2, 2), px, 2.62, pz);
    kit.add('garden', 'wood:#b98654', cyl(0.6, 0.6, 0.06, 12), px, 0.78, pz);
    kit.add('garden', 'metal:#333', cyl(0.05, 0.05, 0.75, 6), px, 0.4, pz);
    for (const a of [0, 2.1, 4.2]) kit.add('garden', 'color:#c0392b', box(0.4, 0.45, 0.4), px + Math.cos(a) * 1.0, 0.27, pz + Math.sin(a) * 1.0);
    kit.add('garden', 'pavers:#d9d2c4', plane(4.2, 3.8, 1.6), px, 0.07, pz);
  }
}

// ------------------------------------------------------------------ Kleiner Platz (Episode 1)
function plaza(kit, it) {
  const w = it.w || 24, d = it.d || 20;
  kit.anim = 'sweep';
  kit.size = [w, d];
  kit.add('plot', 'dirt', plane(w + 2, d + 2, 5), 0, 0.03, 0);
  kit.add('structure', 'cobble', box(w, 0.16, d, 6), 0, 0.08, 0);
  for (const s of [-1, 1]) {
    kit.add('structure', 'concrete:#d8d2c6', box(w + 0.5, 0.2, 0.3, 2), 0, 0.1, s * (d / 2 + 0.1));
    kit.add('structure', 'concrete:#d8d2c6', box(0.3, 0.2, d + 0.5, 2), s * (w / 2 + 0.1), 0.1, 0);
  }
  kit.add('structure', 'pavers:#e9dcc3', cyl(4.6, 4.6, 0.04, 28), 0, 0.17, 0);
  fountain(kit, 'details', 0, 0, 2.3);
  bench(kit, 'details', -5.6, 0, PI / 2);
  bench(kit, 'details', 5.6, 0, -PI / 2);
  bench(kit, 'details', 0, 5.4, PI);
  bench(kit, 'details', 0, -5.4, 0);
  let i = 0;
  for (const [x, z] of [[-w / 2 + 1.6, -d / 2 + 1.6], [w / 2 - 1.6, -d / 2 + 1.6], [-w / 2 + 1.6, d / 2 - 1.6], [w / 2 - 1.6, d / 2 - 1.6]]) planter(kit, 'garden', x, z, i++);
}

// ------------------------------------------------------------------ Baum / Laterne
function tree(kit, it) {
  kit.anim = 'pop';
  kit.size = [4, 4];
  addTree(kit, 'structure', it.species || 'deciduous', it.variant || 0, 0, 0, it.scale || 1, ((it.variant || 0) * 1.7) % 6.28);
}

let lampShared = null;
function lamp(kit, it) {
  kit.anim = 'pop';
  kit.size = [1, 1];
  kit.add('structure', 'metal:#2e3033', cyl(0.07, 0.11, 6.2, 8), 0, 3.1, 0);
  kit.add('structure', 'metal:#2e3033', cyl(0.16, 0.2, 0.5, 8), 0, 0.25, 0);
  kit.add('structure', 'metal:#2e3033', box(0.08, 0.08, 1.7), 0, 6.2, 0.8);
  kit.add('structure', 'metal:#2e3033', box(0.34, 0.12, 0.8), 0, 6.2, 1.55);
  kit.add('structure', 'lampOn', box(0.26, 0.05, 0.62), 0, 6.12, 1.55);
  const w = kit.mats.world;
  if (!lampShared || lampShared.world !== w) {
    const glow = new THREE.SpriteMaterial({ map: Tex.glow(), color: 0xffd79a, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
    const pool = new THREE.MeshBasicMaterial({ map: Tex.glow(), color: 0xffb86b, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, polygonOffset: true, polygonOffsetFactor: -6, polygonOffsetUnits: -6 });
    w.registerNightOpacity(glow, 0.95);
    w.registerNightOpacity(pool, 0.5);
    const pg = new THREE.PlaneGeometry(1, 1);
    pg.rotateX(-PI / 2);
    lampShared = { world: w, glow, pool, pg };
  }
  const s = new THREE.Sprite(lampShared.glow);
  s.scale.setScalar(3.2);
  s.position.set(0, 6.05, 1.55);
  const p = new THREE.Mesh(lampShared.pg, lampShared.pool);
  p.scale.set(17, 1, 17);
  p.position.set(0, 0.22, 2.2);
  p.renderOrder = 5;
  const th = 0.25 + ((hashString(it.id || 'x') % 100) / 100) * 0.45;
  for (const o of [s, p]) {
    o.userData.nightThreshold = th;
    o.visible = false;
    w.nightObjs.push(o);
    kit.extras.push({ part: 'details', obj: o });
  }
}

// ------------------------------------------------------------------ Kleines Geschäft
const SHOP_STYLES = [
  ['DÖNER KEBAP', '#b3261e', '#ffffff', '#b3261e', '#f5f0e6'],
  ['BÄCKEREI SIMIT', '#8a5a2b', '#fff3d6', '#c98a3a', '#fff3d6'],
  ['BARBER SHOP', '#1d1d1f', '#f1c40f', '#1d1d1f', '#f5f0e6'],
  ['BALKAN GRILL', '#1f5c3a', '#ffffff', '#1f5c3a', '#f5f0e6'],
  ['ÇAY EVI', '#7a1f2b', '#ffe9b0', '#7a1f2b', '#ffe9b0'],
  ['BAKLAVA & CAFÉ', '#0f5a66', '#ffffff', '#0f5a66', '#f5f0e6'],
  ['KIOSK 24', '#1f3f8a', '#ffffff', '#1f3f8a', '#f5f0e6'],
  ['OBST & GEMÜSE', '#2e7d32', '#fffde7', '#2e7d32', '#fffde7'],
];
function shop(kit, it, rnd) {
  const w = it.w || 10, d = it.d || 10, H = 6.6, rh = 2.6;
  const st = SHOP_STYLES.find((s) => s[0] === it.name) || SHOP_STYLES[hashString(it.id || 'shop') % SHOP_STYLES.length];
  const wall = 'plaster:' + (it.wall || '#efe2c8');
  kit.height = F + H;
  kit.roofBase = F + H - 0.6;
  kit.roofTop = F + H + rh + 0.6;
  kit.size = [w + 1, d + 4];
  kit.add('plot', 'dirt', plane(w + 3, d + 5, 5), 0, 0.03, 1);
  kit.add('foundation', 'concrete', box(w + 0.4, 0.6, d + 0.4, 3), 0, 0, 0);
  kit.add('structure', wall, box(w, H, d, 2.5), 0, F + H / 2, 0);
  kit.add('structure', 'color:#6f675c', box(w + 0.06, 0.4, d + 0.06), 0, F + 0.2, 0);
  gableRoof(kit, w, d, F + H, rh, 'roof:' + (it.roof || '#8d3f2b'), wall, 0.4);
  // Schaufenster
  kit.add('details', 'color:#2b2b2b', box(w - 1.2, 2.7, 0.1), 0, F + 1.55, d / 2 + 0.04);
  kit.add('details', 'glassLit', box(w - 4.2, 2.3, 0.06), -1.3, F + 1.55, d / 2 + 0.1);
  kit.add('details', 'glassLit', box(1.3, 2.3, 0.06), w / 2 - 2.0, F + 1.45, d / 2 + 0.1);
  kit.add('details', 'concrete', box(w, 0.2, 1.4, 2), 0, 0.1, d / 2 + 0.7);
  // Schild + Markise
  const sg = new THREE.PlaneGeometry(w - 0.8, 0.95);
  kit.add('details', 'color:#222', box(w - 0.6, 1.1, 0.12), 0, F + 3.65, d / 2 + 0.06);
  kit.add('details', `sign:${st[0]}:${st[1]}:${st[2]}`, sg, 0, F + 3.65, d / 2 + 0.13);
  kit.add('details', `awning:${st[3]}:${st[4]}`, box(w - 1, 0.05, 1.7), 0, F + 2.85, d / 2 + 0.85, 0, 0.32);
  for (const u of [-w * 0.25, w * 0.25]) windowAt(kit, w, d, 'f', u, F + 5.2, 1.3, 1.4, { lit: rnd() < 0.6, shutters: it.shutters });
  for (const u of [-w * 0.25, w * 0.25]) windowAt(kit, w, d, 'b', u, F + 5.2, 1.2, 1.3, { lit: rnd() < 0.5 });
  // Tische draußen
  for (const x of [-w * 0.3, w * 0.05]) {
    kit.add('garden', 'white', cyl(0.4, 0.4, 0.05, 10), x, 0.95, d / 2 + 2.4);
    kit.add('garden', 'metal:#444', cyl(0.04, 0.04, 0.75, 6), x, 0.58, d / 2 + 2.4);
    for (const s of [-0.65, 0.65]) kit.add('garden', 'color:' + st[1], box(0.36, 0.45, 0.36), x + s, 0.43, d / 2 + 2.4);
  }
  kit.add('garden', 'pavers', plane(w + 0.6, 3.4, 2), 0, 0.06, d / 2 + 2);
}

// ------------------------------------------------------------------ Supermarkt
function supermarket(kit, it) {
  const w = it.w || 34, d = it.d || 22, H = 6.4;
  kit.height = F + H;
  kit.roofBase = F + H - 0.2;
  kit.roofTop = F + H + 2.2;
  kit.size = [w + 2, d + 4];
  kit.add('plot', 'dirt', plane(w + 4, d + 6, 5), 0, 0.03, 0);
  kit.add('foundation', 'concrete', box(w + 0.6, 0.6, d + 0.6, 3), 0, 0, 0);
  kit.add('structure', 'plaster:#ece6da', box(w, H, d, 2.5), 0, F + H / 2, 0);
  kit.add('structure', 'color:#b3261e', box(w + 0.1, 1.1, d + 0.1), 0, F + H - 0.55, 0);
  flatRoof(kit, w, d, F + H);
  for (const [x, z] of [[-8, -4], [5, 3], [10, -5]]) kit.add('roof', 'metal:#a5a9ad', box(2.6, 1.3, 1.8), x, F + H + 0.8, z);
  kit.add('details', 'color:#2b2b2b', box(w * 0.62, 3.3, 0.1), 0, F + 1.75, d / 2 + 0.04);
  kit.add('details', 'glassLit', box(w * 0.6, 3.0, 0.06), 0, F + 1.7, d / 2 + 0.1);
  for (let i = -3; i <= 3; i++) kit.add('details', 'color:#2b2b2b', box(0.1, 3.0, 0.1), (i * w * 0.6) / 7, F + 1.7, d / 2 + 0.12);
  kit.add('details', 'color:#b3261e', box(9, 0.3, 3.2), 0, F + 3.7, d / 2 + 1.6);
  for (const s of [-4.2, 4.2]) kit.add('details', 'metal:#888', cyl(0.1, 0.1, 3.7, 8), s, F + 1.85, d / 2 + 3);
  const sg = new THREE.PlaneGeometry(15, 1.9);
  kit.add('details', `sign:${it.name || 'AUSLÄNDER MARKT'}:#b3261e:#ffffff`, sg, 0, F + H - 0.55, d / 2 + 0.07);
  // Einkaufswagen-Unterstand
  kit.add('garden', 'metal:#9aa0a6', box(4, 0.08, 2.2), w / 2 - 4, 2.2, d / 2 + 2);
  for (const [a, b] of [[-1.9, -1], [1.9, -1], [-1.9, 1], [1.9, 1]]) kit.add('garden', 'metal:#9aa0a6', box(0.07, 2.2, 0.07), w / 2 - 4 + a, 1.1, d / 2 + 2 + b);
  kit.add('garden', 'metal:#c9ccd1', box(3.2, 0.9, 1.2), w / 2 - 4, 0.6, d / 2 + 2);
  kit.add('garden', 'pavers', plane(w + 1, 4, 2), 0, 0.06, d / 2 + 2);
}

// ------------------------------------------------------------------ Parkplatz
function parking(kit, it, rnd) {
  const w = it.w || 34, d = it.d || 18;
  kit.anim = 'sweep';
  kit.size = [w, d];
  kit.add('plot', 'dirt', plane(w + 2, d + 2, 5), 0, 0.03, 0);
  kit.add('structure', 'asphalt', box(w, 0.12, d, 6), 0, 0.06, 0);
  for (const s of [-1, 1]) kit.add('structure', 'concrete:#d8d2c6', box(w + 0.4, 0.2, 0.25, 2), 0, 0.1, s * (d / 2 + 0.1));
  const n = Math.floor((w - 2) / 2.7);
  for (const row of [-1, 1]) {
    const zc = row * (d / 2 - 2.7);
    for (let i = 0; i <= n; i++) kit.add('details', 'line', box(0.12, 0.02, 5), -w / 2 + 1 + i * 2.7, 0.135, zc);
    for (let i = 0; i < n; i++)
      if (rnd() < 0.45) car(kit, 'garden', -w / 2 + 1 + (i + 0.5) * 2.7, zc, row > 0 ? 0 : PI, CAR_COLORS[(rnd() * CAR_COLORS.length) | 0]);
  }
}

// ------------------------------------------------------------------ Schule
function school(kit, it) {
  const w = it.w || 44, d = it.d || 16, H = 9.6;
  const fac = 'facade:res:' + (it.wall || '#f3e2b8');
  kit.height = F + H;
  kit.roofBase = F + H - 0.2;
  kit.roofTop = F + H + 1.6;
  kit.size = [w + 4, d + 18];
  kit.add('plot', 'dirt', plane(w + 6, d + 20, 5), 0, 0.03, 6);
  kit.add('foundation', 'concrete', box(w + 0.6, 0.6, d + 0.6, 3), 0, 0, 0);
  kit.add('foundation', 'concrete', box(14.6, 0.6, 12.6, 3), -w / 2 + 7, 0, d / 2 + 6);
  kit.add('structure', fac, box(w, H, d, 12.8), 0, F + H / 2, 0);
  kit.add('structure', fac, box(14, 6.4, 12, 12.8), -w / 2 + 7, F + 3.2, d / 2 + 6);
  flatRoof(kit, w, d, F + H);
  kit.add('details', 'color:#4a4c50', box(14.3, 0.3, 12.3), -w / 2 + 7, F + 6.5, d / 2 + 6);
  // Eingang
  kit.add('details', 'color:#c0392b', box(8, 0.3, 3), 6, F + 3.4, d / 2 + 1.5);
  for (const s of [-3.6, 3.6]) kit.add('details', 'color:#c0392b', cyl(0.14, 0.14, 3.4, 8), 6 + s, F + 1.7, d / 2 + 2.8);
  kit.add('details', 'glassLit', box(5, 2.8, 0.08), 6, F + 1.5, d / 2 + 0.06);
  kit.add('details', `sign:${it.name || 'GRUNDSCHULE'}:#f3e2b8:#333333`, new THREE.PlaneGeometry(9, 1.1), 6, F + 4.5, d / 2 + 0.07);
  // Uhr
  kit.add('details', 'white', cyl(0.9, 0.9, 0.08, 20), w / 2 - 6, F + H - 1.6, d / 2 + 0.06, 0, PI / 2);
  kit.add('details', 'color:#222', box(0.06, 0.7, 0.03), w / 2 - 6, F + H - 1.35, d / 2 + 0.12);
  // Schulhof
  kit.add('garden', 'pavers:#d9cdb8', plane(w - 15, 15, 2), 7.5, 0.06, d / 2 + 8);
  for (let i = 0; i < 4; i++) addTree(kit, 'garden', 'linden', i, -4 + i * 9, d / 2 + 13.5, 0.7);
  bench(kit, 'garden', 2, d / 2 + 9, 0);
  bench(kit, 'garden', 12, d / 2 + 9, 0);
}

// ------------------------------------------------------------------ Fußballplatz
function pitch(kit, it) {
  const w = it.w || 56, d = it.d || 36;
  kit.anim = 'sweep';
  kit.size = [w, d];
  kit.add('plot', 'dirt', plane(w + 2, d + 2, 5), 0, 0.03, 0);
  kit.add('structure', 'color:#a8523c:1', box(w, 0.08, d), 0, 0.04, 0);
  kit.add('structure', 'pitch', box(w - 7, 0.05, d - 7), 0, 0.085, 0);
  for (const s of [-1, 1]) {
    const gx = s * (w / 2 - 4.2);
    kit.add('details', 'white', box(0.12, 2.44, 0.12), gx, 1.3, -3.66);
    kit.add('details', 'white', box(0.12, 2.44, 0.12), gx, 1.3, 3.66);
    kit.add('details', 'white', box(0.12, 0.12, 7.44), gx, 2.5, 0);
    kit.add('details', 'color:#dddddd:1', box(1.4, 0.04, 7.3), gx + s * 0.7, 2.3, 0, 0, 0, s * -0.5);
    for (const z of [-d / 2 + 1.5, d / 2 - 1.5]) {
      kit.add('details', 'metal:#8a8f94', cyl(0.14, 0.2, 13, 8), s * (w / 2 - 1.5), 6.5, z);
      kit.add('details', 'lampOn', box(1.8, 0.9, 0.3), s * (w / 2 - 1.5), 13, z, s * (z > 0 ? -2.3 : -0.8));
    }
  }
  for (let i = 0; i < 3; i++) kit.add('details', 'concrete:#cfc8bb', box(22, 0.45, 0.9, 2), 0, 0.25 + i * 0.45, -d / 2 + 2.6 - i * 0.9);
}

// ------------------------------------------------------------------ Rathaus
function townhall(kit, it) {
  const w = it.w || 40, d = it.d || 22, H = 12.8, rh = 4.2;
  const fac = 'facade:res:' + (it.wall || '#eadbbd');
  kit.height = F + H + 1.2;
  kit.roofBase = F + H - 0.4;
  kit.roofTop = F + H + 23;
  kit.size = [w + 6, d + 12];
  kit.add('plot', 'dirt', plane(w + 8, d + 14, 5), 0, 0.03, 2);
  kit.add('foundation', 'concrete:#d8cfbd', box(w + 2, 1.4, d + 2, 3), 0, 0.1, 0);
  for (let i = 0; i < 4; i++) kit.add('foundation', 'concrete:#d8cfbd', box(18 - i * 0.2, 0.25, 1.2, 3), 0, 0.12 + (3 - i) * 0.22, d / 2 + 2.2 + i * 0.9);
  const B = 0.8;
  kit.add('structure', fac, box(w, H, d, 12.8), 0, B + H / 2, 0);
  kit.add('structure', 'plaster:#efe3c9', box(15, H + 1.2, 4, 2.5), 0, B + (H + 1.2) / 2, d / 2 + 1);
  for (let i = 0; i < 6; i++) kit.add('structure', 'concrete:#f1ead9', cyl(0.5, 0.58, 9.6, 14), -6 + i * 2.4, B + 4.8, d / 2 + 3.6);
  kit.add('structure', 'plaster:#efe3c9', box(15.6, 1.3, 2.2, 2.5), 0, B + 10.3, d / 2 + 3.6);
  kit.add('roof', 'plaster:#efe3c9', gable(15.6, 3), 0, B + 10.95, d / 2 + 4.6, PI / 2);
  kit.add('roof', 'roof:#5f6d76', box(16.2, 0.2, 5.2, 1.7), 0, B + H + 1.3, d / 2 + 2);
  gableRoof(kit, w, d, B + H, rh, 'roof:#5f6d76', 'plaster:#efe3c9', 0.7);
  // Uhrturm
  const ty = B + H + 2;
  kit.add('roof', 'plaster:#efe3c9', box(6, 10, 6, 2.5), 0, ty + 5, 0);
  kit.add('roof', 'concrete:#f1ead9', box(6.8, 0.5, 6.8), 0, ty + 10.2, 0);
  kit.add('roof', 'color:#5f9b8a:0.5', cone(4.6, 7, 4), 0, ty + 13.9, 0, PI / 4);
  kit.add('roof', 'gold', sphere(0.5, 10), 0, ty + 17.7, 0);
  kit.add('roof', 'gold', cyl(0.06, 0.06, 2, 6), 0, ty + 18.5, 0);
  for (const [x, z, ry] of [[0, 3.05, 0], [0, -3.05, PI], [3.05, 0, PI / 2], [-3.05, 0, -PI / 2]]) {
    kit.add('roof', 'white', cyl(1.6, 1.6, 0.08, 24), x, ty + 7.2, z, ry, PI / 2);
    kit.add('roof', 'color:#222', box(0.1, 1.2, 0.05), x + Math.sin(ry) * 0.06, ty + 7.6, z + Math.cos(ry) * 0.06, ry);
    kit.add('roof', 'color:#222', box(0.9, 0.1, 0.05), x + Math.sin(ry) * 0.06 + Math.cos(ry) * 0.4, ty + 7.2, z + Math.cos(ry) * 0.06 - Math.sin(ry) * 0.4, ry);
  }
  kit.add('details', 'wood:#6b4423', box(2.6, 4, 0.12), 0, B + 2, d / 2 + 3.06);
  kit.add('details', `sign:${it.name || 'RATHAUS'}:#efe3c9:#3a2e1c`, new THREE.PlaneGeometry(9, 1.1), 0, B + 10.3, d / 2 + 4.72);
  for (const s of [-1, 1]) {
    addTree(kit, 'garden', 'cypress', 1, s * 12, d / 2 + 4, 0.8);
    addTree(kit, 'garden', 'cypress', 2, s * 17, d / 2 + 4, 0.8);
    planter(kit, 'garden', s * 10.5, d / 2 + 7, 2);
  }
  kit.add('garden', 'pavers:#e2d6c0', plane(w + 4, 7, 2), 0, 0.06, d / 2 + 6.5);
}

// ------------------------------------------------------------------ Statue
function statue(kit, it) {
  kit.height = 10.2;
  kit.roofBase = 10;
  kit.roofTop = 16.5;
  kit.size = [14, 14];
  kit.add('plot', 'dirt', plane(15, 15, 5), 0, 0.03, 0);
  kit.add('foundation', 'cobble', cyl(7, 7, 0.24, 32), 0, 0.12, 0);
  kit.add('structure', 'concrete:#e3dccd', box(5.4, 0.7, 5.4, 3), 0, 0.55, 0);
  kit.add('structure', 'concrete:#e3dccd', box(4.2, 0.7, 4.2, 3), 0, 1.25, 0);
  kit.add('structure', 'concrete:#efe8d9', box(3, 3.4, 3, 3), 0, 3.3, 0);
  kit.add('structure', 'concrete:#e3dccd', box(3.5, 0.4, 3.5, 3), 0, 5.2, 0);
  kit.add('structure', 'concrete:#efe8d9', cyl(0.95, 1.1, 4.4, 18), 0, 7.6, 0);
  kit.add('structure', 'concrete:#e3dccd', cyl(1.5, 1.0, 0.5, 18), 0, 9.95, 0);
  kit.add('details', 'bronze', box(1.8, 1.1, 0.06), 0, 3.4, 1.53);
  // Figur aus Bronze: Mensch mit erhobener Fackel
  const y = 10.2;
  kit.add('roof', 'bronze', cyl(0.42, 0.75, 2.5, 12), 0, y + 1.25, 0);
  kit.add('roof', 'bronze', cyl(0.5, 0.42, 1.3, 12), 0, y + 3.1, 0);
  kit.add('roof', 'bronze', sphere(0.42, 14), 0, y + 4.2, 0);
  kit.add('roof', 'bronze', cyl(0.14, 0.17, 1.9, 8), 0.72, y + 4.25, 0, 0, 0, -0.42);
  kit.add('roof', 'bronze', cyl(0.14, 0.17, 1.6, 8), -0.62, y + 2.9, 0.1, 0, 0.2, 0.3);
  kit.add('roof', 'bronze', cone(0.2, 0.5, 8), 1.12, y + 5.3, 0, 0, 0, PI);
  kit.add('roof', 'gold', sphere(0.3, 10), 1.12, y + 5.75, 0);
  for (let i = 0; i < 4; i++) {
    const a = PI / 4 + (i * PI) / 2;
    planter(kit, 'garden', Math.cos(a) * 5.2, Math.sin(a) * 5.2, i);
  }
}

// ------------------------------------------------------------------ Marktplatz
function market(kit, it, rnd) {
  const w = it.w || 70, d = it.d || 44;
  kit.anim = 'sweep';
  kit.size = [w, d];
  kit.add('plot', 'dirt', plane(w + 2, d + 2, 5), 0, 0.03, 0);
  kit.add('structure', 'cobble', box(w, 0.16, d, 6), 0, 0.08, 0);
  kit.add('structure', 'pavers:#e9dcc3', box(w - 8, 0.03, 3, 2), 0, 0.175, 0);
  kit.add('structure', 'pavers:#e9dcc3', box(3, 0.03, d - 6, 2), 0, 0.176, 0);
  const cols = [['#b3261e', '#f5f0e6'], ['#1f5c3a', '#f5f0e6'], ['#1f3f8a', '#f5f0e6'], ['#c98a3a', '#fff3d6']];
  const goods = ['#e67e22', '#c0392b', '#f1c40f', '#27ae60', '#8e44ad'];
  let k = 0;
  for (const z of [-d / 2 + 7, -d / 2 + 15, d / 2 - 15, d / 2 - 7])
    for (let x = -w / 2 + 9; x <= w / 2 - 8; x += 9) {
      if (Math.abs(x) < 5) continue;
      const c = cols[k++ % cols.length];
      for (const [a, b] of [[-1.9, -1.2], [1.9, -1.2], [-1.9, 1.2], [1.9, 1.2]]) kit.add('details', 'wood:#8c6239', box(0.1, 2.5, 0.1), x + a, 1.4, z + b);
      kit.add('details', `awning:${c[0]}:${c[1]}`, box(4.6, 0.06, 3.2), x, 2.75, z, 0, 0.14);
      kit.add('details', 'wood:#b98654', box(3.8, 0.9, 1.4), x, 0.6, z);
      for (let i = 0; i < 4; i++) kit.add('details', 'color:' + goods[(rnd() * goods.length) | 0], box(0.8, 0.25, 1.1), x - 1.35 + i * 0.9, 1.17, z);
    }
  for (const s of [-1, 1]) {
    for (const t of [-1, 1]) {
      addTree(kit, 'garden', 'linden', (s + t + 3) % 5, s * (w / 2 - 3), t * (d / 2 - 3), 0.75);
      bench(kit, 'details', s * 9, t * 3.2, t > 0 ? PI : 0);
    }
  }
}

// ------------------------------------------------------------------ Mehrfamilienhaus
function apartment(kit, it, rnd) {
  const w = it.w || 22, d = it.d || 13, floors = it.floors || 5, H = floors * 3.2;
  const fac = 'facade:res:' + (it.wall || '#f0e4cf');
  kit.height = F + H;
  kit.roofBase = F + H - 0.2;
  kit.roofTop = F + H + 3;
  kit.size = [w + 8, d + 13];
  kit.add('plot', 'dirt', plane(w + 8, d + 13, 5), 0, 0.03, 0);
  kit.add('foundation', 'concrete', box(w + 0.6, 0.6, d + 0.6, 3), 0, 0, 0);
  kit.add('structure', fac, box(w, H, d, 12.8), 0, F + H / 2, 0);
  kit.add('structure', 'plaster:' + (it.accent || '#c96f4a'), box(3.4, H + 0.6, d + 0.6, 2.5), 0, F + (H + 0.6) / 2, 0);
  flatRoof(kit, w, d, F + H);
  kit.add('roof', 'plaster:#d8d3c8', box(3.6, 2.4, 4, 2.5), 0, F + H + 1.6, -1);
  kit.add('roof', 'white', cyl(0.5, 0.5, 0.05, 12), w / 2 - 3, F + H + 1.2, 0, 0.6, PI / 2 - 0.5);
  for (let f = 1; f < floors; f++)
    for (const s of [-1, 1]) {
      const x = s * (w / 2 - 4.4), y = F + f * 3.2;
      kit.add('details', 'concrete:#eeeeee', box(5.6, 0.14, 1.5), x, y + 0.05, d / 2 + 0.75);
      kit.add('details', 'color:' + (it.accent || '#c96f4a'), box(5.6, 1.0, 0.06), x, y + 0.6, d / 2 + 1.48);
      for (const e of [-2.8, 2.8]) kit.add('details', 'color:#f2f2f2', box(0.06, 1.0, 1.5), x + e, y + 0.6, d / 2 + 0.75);
    }
  kit.add('details', 'glassLit', box(2.2, 2.6, 0.08), 0, F + 1.3, d / 2 + 0.36);
  kit.add('details', 'color:#4a4c50', box(4.6, 0.16, 2), 0, F + 2.9, d / 2 + 1.2);
  kit.add('garden', 'lawn:#8fcb5c', plane(w + 8, d + 13, 6), 0, 0.05, 0);
  kit.add('garden', 'pavers:#d9d2c4', plane(2.6, 5.5, 1.6), 0, 0.07, d / 2 + 3.4);
  kit.add('garden', 'hedge', box(w + 7, 1, 0.8, 2), 0, 0.5, -d / 2 - 5.6);
  for (const s of [-1, 1]) addTree(kit, 'garden', s > 0 ? 'linden' : 'deciduous', (rnd() * 5) | 0, s * (w / 2 + 1), d / 2 + 4, 0.85);
  addTree(kit, 'garden', 'deciduous', (rnd() * 5) | 0, -w / 4, -d / 2 - 3, 0.8);
}

// ------------------------------------------------------------------ Moschee
function mosque(kit, it) {
  const w = it.w || 30, d = it.d || 30, H = 10, mh = 27;
  const wall = 'plaster:' + (it.wall || '#f2ecdf'), lead = 'color:#6f8fa3:0.4';
  kit.height = F + mh;
  kit.roofBase = F + H - 0.2;
  kit.roofTop = F + mh + 9;
  kit.size = [w + 14, d + 22];
  kit.add('plot', 'dirt', plane(w + 14, d + 22, 5), 0, 0.03, 4);
  kit.add('foundation', 'concrete:#ded6c6', box(w + 3, 0.9, d + 3, 3), 0, 0, 0);
  kit.add('foundation', 'concrete:#ded6c6', box(w + 3, 0.9, 7, 3), 0, 0, d / 2 + 4.5);
  kit.add('structure', wall, box(w, H, d, 2.5), 0, F + H / 2, 0);
  kit.add('structure', 'concrete:#e6dccb', box(w + 0.3, 0.5, d + 0.3), 0, F + H - 0.25, 0);
  // Vorhalle mit Säulen
  for (let i = 0; i < 6; i++) kit.add('structure', 'concrete:#f1ead9', cyl(0.4, 0.46, 4.6, 12), -w / 2 + 2 + (i * (w - 4)) / 5, F + 2.3, d / 2 + 6.4);
  kit.add('structure', wall, box(w, 1, 6.6, 2.5), 0, F + 5.1, d / 2 + 3.4);
  for (let i = 0; i < 5; i++) kit.add('roof', lead, dome(2.3, 16), -w / 2 + 5 + (i * (w - 10)) / 4, F + 5.6, d / 2 + 3.4);
  // Tambour + Hauptkuppel
  kit.add('roof', wall, cyl(9.2, 9.2, 3, 28), 0, F + H + 1.5, 0);
  kit.add('roof', lead, dome(9.4, 32), 0, F + H + 3, 0);
  kit.add('roof', 'gold', cyl(0.12, 0.12, 2.6, 6), 0, F + H + 13.5, 0);
  kit.add('roof', 'gold', sphere(0.45, 10), 0, F + H + 12.7, 0);
  kit.add('roof', 'gold', new THREE.TorusGeometry(0.62, 0.1, 6, 18, PI * 1.45), 0, F + H + 15.3, 0, 0, 0, PI * 0.78);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) kit.add('roof', lead, dome(3.2, 16), sx * (w / 2 - 3.6), F + H, sz * (d / 2 - 3.6));
  // Minarette
  for (const s of [-1, 1]) {
    const x = s * (w / 2 + 1.2), z = d / 2 + 0.6;
    kit.add('structure', wall, box(3, 6, 3, 2.5), x, F + 3, z);
    kit.add('structure', wall, cyl(1.05, 1.25, mh - 6, 14), x, F + 6 + (mh - 6) / 2, z);
    kit.add('structure', 'concrete:#e6dccb', cyl(1.75, 1.3, 0.6, 14), x, F + 18.5, z);
    kit.add('structure', 'concrete:#e6dccb', cyl(1.75, 1.75, 0.5, 14), x, F + 19.3, z);
    kit.add('roof', wall, cyl(0.8, 0.8, 3, 12), x, F + mh + 1.5, z);
    kit.add('roof', lead, cone(1.25, 5, 14), x, F + mh + 5.4, z);
    kit.add('roof', 'gold', sphere(0.25, 8), x, F + mh + 8.1, z);
  }
  // Fenster
  for (const side of ['l', 'r', 'b'])
    for (let i = -2; i <= 2; i++) {
      windowAt(kit, w, d, side, i * 5, F + 3.4, 1.3, 3, { lit: true, bars: false, frame: 'concrete:#e6dccb' });
      windowAt(kit, w, d, side, i * 5, F + 7.6, 1.1, 1.4, { lit: i % 2 === 0, bars: false, sill: false, frame: 'concrete:#e6dccb' });
    }
  kit.add('details', 'wood:#6b4423', box(2.8, 4, 0.12), 0, F + 2, d / 2 + 0.07);
  // Hof
  kit.add('garden', 'pavers:#e6dccb', plane(w + 10, 12, 2), 0, 0.06, d / 2 + 13);
  fountain(kit, 'garden', 0, d / 2 + 14, 1.8);
  for (const s of [-1, 1]) {
    addTree(kit, 'garden', 'cypress', 1, s * (w / 2 + 4), d / 2 + 10, 0.9);
    addTree(kit, 'garden', 'cypress', 3, s * (w / 2 + 4), d / 2 + 16, 0.9);
    addTree(kit, 'garden', 'cypress', 2, s * (w / 2 + 5), -d / 2 + 2, 0.9);
  }
  kit.add('garden', 'lawn:#8fcb5c', plane(w + 14, d + 4, 6), 0, 0.045, -2);
}

// ------------------------------------------------------------------ Einkaufszentrum
function mall(kit, it) {
  const w = it.w || 64, d = it.d || 42, H = 12.8;
  kit.height = F + H + 3.2;
  kit.roofBase = F + H - 0.2;
  kit.roofTop = F + H + 9;
  kit.size = [w + 6, d + 8];
  kit.add('plot', 'dirt', plane(w + 6, d + 8, 5), 0, 0.03, 0);
  kit.add('foundation', 'concrete', box(w + 0.8, 0.6, d + 0.8, 3), 0, 0, 0);
  kit.add('structure', 'plaster:#e9e5dc', box(w, H, d, 2.5), 0, F + H / 2, 0);
  kit.add('structure', 'color:#1f3f8a:0.5', box(w + 0.2, 1.2, d + 0.2), 0, F + H - 0.6, 0);
  kit.add('structure', 'facade:office:#dfe9f2', box(22.4, H + 3.2, 6, 12.8), 0, F + (H + 3.2) / 2, d / 2 + 2);
  for (const s of [-1, 1]) kit.add('structure', 'facade:office:#dfe9f2', box(12.8, 6.4, 0.4, 12.8), s * 21.5, F + 3.2, d / 2 + 0.1);
  flatRoof(kit, w, d, F + H);
  kit.add('roof', 'glass', cone(9, 6, 4), 0, F + H + 3.2, -4, PI / 4);
  kit.add('roof', 'color:#3a3d42', box(22.8, 0.3, 6.4), 0, F + H + 3.35, d / 2 + 2);
  for (const [x, z] of [[-22, -8], [-14, 6], [20, -10], [22, 4]]) kit.add('roof', 'metal:#a5a9ad', box(3.2, 1.5, 2.2), x, F + H + 0.9, z);
  kit.add('details', `sign:${it.name || 'CITY CENTER'}:#1f3f8a:#ffffff`, new THREE.PlaneGeometry(18, 2.4), 0, F + H + 1.6, d / 2 + 5.06);
  kit.add('details', 'color:#1f3f8a:0.5', box(14, 0.3, 4), 0, F + 4, d / 2 + 6.8);
  for (const s of [-6.5, 6.5]) kit.add('details', 'metal:#999', cyl(0.14, 0.14, 4, 8), s, F + 2, d / 2 + 8.4);
  kit.add('garden', 'pavers:#d9d2c4', plane(w + 4, 8, 2), 0, 0.06, d / 2 + 5);
  for (let i = -3; i <= 3; i++) if (Math.abs(i) > 0) planter(kit, 'garden', i * 8.5, d / 2 + 8, i + 3);
}

// ------------------------------------------------------------------ Hochhaus
function highrise(kit, it) {
  const w = it.w || 22, d = it.d || 22, floors = it.floors || 20, H = floors * 3.2;
  const fac = 'facade:office:' + (it.wall || '#cfe0ee');
  kit.height = F + 6.4 + H;
  kit.roofBase = F + 6.4 + H - 0.2;
  kit.roofTop = F + 6.4 + H + 14;
  kit.size = [w + 12, d + 12];
  kit.add('plot', 'dirt', plane(w + 12, d + 12, 5), 0, 0.03, 0);
  kit.add('foundation', 'concrete', box(w + 8.6, 0.6, d + 8.6, 3), 0, 0, 0);
  kit.add('structure', 'facade:office:#e3e8ec', box(w + 8, 6.4, d + 8, 12.8), 0, F + 3.2, 0);
  kit.add('structure', fac, box(w, H, d, 12.8), 0, F + 6.4 + H / 2, 0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) kit.add('structure', 'color:#f2f4f6:0.4', box(1, H + 1.5, 1), sx * w / 2, F + 6.4 + (H + 1.5) / 2, sz * d / 2);
  kit.add('details', 'color:#3a3d42', box(w + 8.4, 0.4, d + 8.4), 0, F + 6.6, 0);
  kit.add('roof', 'color:#3a3d42', box(w - 0.5, 0.4, d - 0.5), 0, F + 6.4 + H + 0.2, 0);
  kit.add('roof', 'color:#dfe4e8:0.4', box(w - 6, 3.4, d - 6), 0, F + 6.4 + H + 1.9, 0);
  kit.add('roof', 'metal:#b0b5ba', cyl(0.18, 0.3, 10, 8), w / 5, F + 6.4 + H + 8.5, 0);
  kit.add('roof', 'lampOn', sphere(0.3, 8), w / 5, F + 6.4 + H + 13.6, 0);
  kit.add('details', 'glassLit', box(6, 3.6, 0.1), 0, F + 1.9, d / 2 + 4.06);
  kit.add('garden', 'pavers:#d9d2c4', plane(w + 12, d + 12, 2), 0, 0.055, 0);
  for (const s of [-1, 1]) addTree(kit, 'garden', 'linden', s + 2, s * (w / 2 + 2), d / 2 + 5.2, 0.7);
}

// ------------------------------------------------------------------ Gewerbehalle
function warehouse(kit, it, rnd) {
  const w = it.w || 40, d = it.d || 26, H = 8.5, rh = 2;
  kit.height = F + H;
  kit.roofBase = F + H - 0.5;
  kit.roofTop = F + H + rh + 0.6;
  kit.size = [w + 8, d + 14];
  kit.add('plot', 'dirt', plane(w + 8, d + 14, 5), 0, 0.03, 4);
  kit.add('foundation', 'concrete', box(w + 0.6, 0.6, d + 0.6, 3), 0, 0, 0);
  const col = it.wall || '#c7cdd3';
  kit.add('structure', 'concrete:' + col, box(w, H, d, 3), 0, F + H / 2, 0);
  kit.add('structure', 'color:' + (it.accent || '#e67e22'), box(w + 0.1, 0.9, d + 0.1), 0, F + H - 1.2, 0);
  gableRoof(kit, w, d, F + H, rh, 'color:#7d8790:0.5', 'concrete:' + col, 0.3);
  for (let i = 0; i < 4; i++) {
    const x = -w / 2 + 6 + i * 6.5;
    kit.add('details', 'color:#eef0f2:0.5', box(4.2, 4.4, 0.1), x, F + 2.2, d / 2 + 0.05);
    for (let j = 1; j < 6; j++) kit.add('details', 'color:#b7bcc2', box(4.2, 0.04, 0.03), x, F + j * 0.72, d / 2 + 0.11);
  }
  kit.add('structure', 'facade:office:#e3e8ec', box(9.6, 6.4, 6.4, 12.8), w / 2 - 4.8, F + 3.2, d / 2 + 3.2);
  kit.add('details', 'color:#4a4c50', box(9.9, 0.3, 6.7), w / 2 - 4.8, F + 6.5, d / 2 + 3.2);
  kit.add('details', `sign:${it.name || 'LOGISTIK GMBH'}:#ffffff:#333333`, new THREE.PlaneGeometry(11, 1.3), -w / 2 + 14, F + H - 1.2, d / 2 + 0.12);
  kit.add('garden', 'asphalt', box(w + 6, 0.1, 12, 6), 0, 0.05, d / 2 + 6.4);
  for (let i = 0; i < 2; i++)
    if (rnd() < 0.8) {
      const x = -w / 2 + 6 + i * 13;
      kit.add('garden', 'color:#f2f2f2:0.5', box(2.5, 2.8, 8), x, 2.5, d / 2 + 5.6);
      kit.add('garden', 'color:' + CAR_COLORS[3 + i] + ':0.4', box(2.4, 2.3, 2.2), x, 1.75, d / 2 + 11);
      for (const b of [3, 7, 11.2]) for (const a of [-1.1, 1.1]) kit.add('garden', 'color:#16171a', cyl(0.5, 0.5, 0.3, 10), x + a, 0.55, d / 2 + b, 0, 0, PI / 2);
    }
}

// ------------------------------------------------------------------ Stadtpark
function park(kit, it, rnd) {
  const w = it.w || 80, d = it.d || 90;
  kit.anim = 'sweep';
  kit.size = [w, d];
  kit.add('plot', 'dirt', plane(w, d, 5), 0, 0.03, 0);
  kit.add('structure', 'lawn:#93d15e', plane(w, d, 6), 0, 0.06, 0);
  kit.add('structure', 'pavers:#e2d3b4', box(3, 0.06, d - 4, 2), -w * 0.2, 0.08, 0);
  kit.add('structure', 'pavers:#e2d3b4', box(w - 4, 0.06, 3, 2), 0, 0.085, d * 0.18);
  kit.add('structure', 'pavers:#e2d3b4', box(w * 0.62, 0.06, 2.4, 2), w * 0.12, 0.09, -d * 0.22, 0.5);
  const px = w * 0.16, pz = -d * 0.05;
  kit.add('structure', 'gravel', cyl(15, 15, 0.1, 36), px, 0.07, pz, 0, 0, 0, [1, 1, 0.75]);
  kit.add('structure', 'water', cyl(13.6, 13.6, 0.1, 36), px, 0.1, pz, 0, 0, 0, [1, 1, 0.75]);
  // Pavillon
  const gx = -w * 0.2, gz = d * 0.18;
  kit.add('details', 'concrete:#e3dccd', cyl(4.2, 4.4, 0.4, 8), gx, 0.26, gz);
  for (let i = 0; i < 8; i++) kit.add('details', 'white', cyl(0.12, 0.12, 3, 8), gx + Math.cos((i * PI) / 4) * 3.7, 1.9, gz + Math.sin((i * PI) / 4) * 3.7);
  kit.add('details', 'roof:#5f6d76', cone(5, 2.6, 8), gx, 4.7, gz);
  // Spielplatz
  const sx = w * 0.22, sz = d * 0.32;
  kit.add('details', 'color:#e2c98f:1', cyl(7, 7, 0.1, 20), sx, 0.1, sz);
  for (const s of [-1.6, 1.6]) {
    kit.add('details', 'color:#c0392b', box(0.12, 2.6, 0.12), sx + s, 1.3, sz - 2, 0, 0, s > 0 ? -0.12 : 0.12);
  }
  kit.add('details', 'color:#c0392b', box(3.4, 0.12, 0.12), sx, 2.55, sz - 2);
  kit.add('details', 'color:#f1c40f', box(1.2, 2, 1.2), sx - 2, 1.05, sz + 2);
  kit.add('details', 'color:#2980b9', box(0.9, 0.08, 3.4), sx - 2, 1.1, sz + 4.1, 0, 0.55);
  for (let i = 0; i < 6; i++) bench(kit, 'details', -w * 0.2 + 2.2, -d / 2 + 10 + i * 12, -PI / 2);
  for (let i = 0; i < 34; i++) {
    const x = (rnd() - 0.5) * (w - 6), z = (rnd() - 0.5) * (d - 6);
    if (Math.hypot((x - px) / 1, (z - pz) / 0.75) < 18 || Math.abs(x + w * 0.2) < 3 || Math.abs(z - d * 0.18) < 3 || Math.hypot(x - sx, z - sz) < 9 || Math.hypot(x - gx, z - gz) < 7) continue;
    addTree(kit, 'garden', ['deciduous', 'linden', 'deciduous', 'conifer', 'autumn'][(rnd() * 5) | 0], (rnd() * 5) | 0, x, z, 0.75 + rnd() * 0.45, rnd() * 6);
  }
}

const BUILDERS = { house, plaza, tree, lamp, shop, supermarket, parking, school, pitch, townhall, statue, market, apartment, mosque, mall, highrise, warehouse, park };

// Erzeugt das Modell für ein Stadt-Objekt aus city/state.json
export function buildItem(it, mats) {
  const kit = new Kit(mats);
  const c = CATALOG[it.type] || {};
  kit.size = [c.w || 10, c.d || 10];
  const fn = BUILDERS[it.type];
  if (!fn) throw new Error('Unbekannter Gebäudetyp: ' + it.type);
  fn(kit, it, mulberry32(hashString(it.id || it.type) + 7));
  const root = kit.finalize();
  root.userData.roofBase = kit.roofBase ?? kit.height;
  root.userData.roofTop = kit.roofTop ?? kit.height;
  root.userData.item = it;
  root.position.set(it.x, 0, it.z);
  root.rotation.y = THREE.MathUtils.degToRad(it.rot || 0);
  return root;
}
