// Baukasten: Material-Bibliothek + Geometrie-Sammler, der pro Bauteil und Material zu einem Mesh verschmilzt.
import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { Tex } from './textures.js';
import { mulberry32, makeNoise, clamp } from './util.js';

// Bauteile in Bau-Reihenfolge
export const PARTS = ['plot', 'foundation', 'structure', 'roof', 'details', 'garden'];

export class MatLib {
  // world: für Nacht-Emission; planes: optionale Clipping-Ebenen je Bauteil (z. B. {structure, roof}) für die Bauanimation
  constructor(world, planes = null) {
    this.world = world;
    this.planes = planes;
    this.cache = new Map();
  }
  get(key, part = '') {
    const clipPart = this.planes && this.planes[part] ? part : '';
    const k = key + '|' + clipPart;
    let m = this.cache.get(k);
    if (!m) {
      m = this.create(key);
      if (/^(glass|glassLit|metal|gold|bronze|water|facade)/.test(key)) this.world.registerEnv(m);
      if (clipPart) {
        m.clippingPlanes = [this.planes[clipPart]];
        m.clipShadows = true;
      }
      this.cache.set(k, m);
    }
    return m;
  }
  create(key) {
    const [kind, a, b, c] = key.split(':');
    const S = (o) => new THREE.MeshStandardMaterial({ roughness: 0.9, metalness: 0, ...o });
    switch (kind) {
      case 'plaster': return S({ map: Tex.plaster(), color: a, roughness: 0.95 });
      case 'brick': return S({ map: Tex.brick(), color: a || '#ffffff' });
      case 'concrete': return S({ map: Tex.concrete(), color: a || '#ffffff' });
      case 'roof': return S({ map: Tex.roofTiles(), color: a, roughness: 0.8 });
      case 'wood': return S({ map: Tex.wood(), color: a || '#ffffff', roughness: 0.8 });
      case 'color': return S({ color: a, roughness: b ? +b : 0.8 });
      case 'metal': return S({ color: a || '#555', roughness: 0.45, metalness: 0.7 });
      case 'gold': return S({ color: '#e7b548', roughness: 0.3, metalness: 0.9 });
      case 'bronze': return S({ color: '#7a5a34', roughness: 0.42, metalness: 0.85 });
      case 'white': return S({ color: '#f4f2ee', roughness: 0.7 });
      case 'glass': return S({ map: Tex.glass(), roughness: 0.12, metalness: 0.3, envMapIntensity: 1.6 });
      case 'glassLit': {
        const m = S({ map: Tex.glass(), roughness: 0.15, metalness: 0.2, emissive: '#ffbf73', emissiveIntensity: 0 });
        this.world.registerNight(m, 2.4);
        return m;
      }
      case 'facade': {
        const f = Tex.facade(a);
        const m = S({ map: f.map, color: b || '#ffffff', roughness: 0.55, metalness: 0.1, emissive: '#ffffff', emissiveMap: f.emissive, emissiveIntensity: 0 });
        this.world.registerNight(m, 1.8);
        return m;
      }
      case 'cobble': return S({ map: Tex.cobble(), roughness: 0.85 });
      case 'pavers': return S({ map: Tex.pavers(), color: a || '#ffffff' });
      case 'asphalt': return S({ map: Tex.asphalt(), bumpMap: Tex.asphaltBump(), bumpScale: 0.6, roughness: 0.92 });
      case 'gravel': return S({ map: Tex.gravel(), roughness: 1 });
      case 'dirt': return S({ map: Tex.dirt(), roughness: 1, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      case 'lawn': return S({ map: Tex.grassDetail(), color: a || '#86c257', roughness: 1, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3 });
      case 'hedge': return S({ map: Tex.leaves(), color: a || '#4f8a3a', roughness: 1 });
      case 'foliage': return S({ vertexColors: true, color: a || '#ffffff', roughness: 0.95 });
      case 'bark': return S({ map: Tex.bark(), roughness: 1 });
      case 'water': return S({ map: Tex.water(), color: '#9fd3ee', roughness: 0.08, metalness: 0.4 });
      case 'pitch': return S({ map: Tex.pitch(), roughness: 1 });
      case 'sign': {
        const m = S({ map: Tex.sign(a, b, c), roughness: 0.6, emissive: '#ffffff', emissiveMap: Tex.sign(a, b, c), emissiveIntensity: 0 });
        this.world.registerNight(m, 1.1);
        return m;
      }
      case 'awning': return S({ map: Tex.awning(a, b), roughness: 0.9, side: THREE.DoubleSide });
      case 'lampOn': {
        const m = S({ color: '#fff4dc', emissive: '#ffd9a0', emissiveIntensity: 0 });
        this.world.registerNight(m, 6);
        return m;
      }
      case 'line': return new THREE.MeshBasicMaterial({ color: a || '#f2f2f2', polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });
      default: return S({ color: '#ff00ff' });
    }
  }
}

// Box mit UVs im Weltmaßstab (Textur wiederholt sich alle `ts` Meter)
export function box(w, h, d, ts = 0) {
  const g = new THREE.BoxGeometry(w, h, d);
  if (ts) {
    const uv = g.attributes.uv;
    const dims = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
    for (let f = 0; f < 6; f++)
      for (let k = 0; k < 4; k++) {
        const i = f * 4 + k;
        uv.setXY(i, (uv.getX(i) * dims[f][0]) / ts, (uv.getY(i) * dims[f][1]) / ts);
      }
  }
  return g;
}
export function plane(w, d, ts = 0) {
  const g = new THREE.PlaneGeometry(w, d);
  g.rotateX(-Math.PI / 2);
  if (ts) {
    const uv = g.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * w) / ts, (uv.getY(i) * d) / ts);
  }
  return g;
}
export const cyl = (rt, rb, h, n = 12) => new THREE.CylinderGeometry(rt, rb, h, n);
export const sphere = (r, n = 16) => new THREE.SphereGeometry(r, n, Math.max(6, n >> 1));
export const dome = (r, n = 24) => new THREE.SphereGeometry(r, n, 12, 0, Math.PI * 2, 0, Math.PI / 2);
export const cone = (r, h, n = 12) => new THREE.ConeGeometry(r, h, n);

// Giebeldreieck in der YZ-Ebene (beidseitig), Basisbreite d, Höhe rh
export function gable(d, rh, ts = 2.5) {
  const g = new THREE.BufferGeometry();
  const h = d / 2;
  // Vorderseite (+x): A(z=+h) -> B(z=-h) -> C(Spitze); Rückseite umgekehrt
  const pos = [0, 0, h, 0, 0, -h, 0, rh, 0, 0, 0, -h, 0, 0, h, 0, rh, 0];
  const n = [1, 0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, -1, 0, 0, -1, 0, 0];
  const uv = [0, 0, d / ts, 0, d / 2 / ts, rh / ts, d / ts, 0, 0, 0, d / 2 / ts, rh / ts];
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(n, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  return g;
}

const _o = new THREE.Object3D();

export class Kit {
  constructor(mats) {
    this.mats = mats;
    this.bins = new Map(); // "part|matKey" -> [geoms]
    this.height = 3; // Höhe der Wände (structure)
    this.roofHeight = 0; // zusätzliche Dachhöhe
    this.anim = 'staged'; // staged | sweep | pop
    this.size = [10, 10];
    this.extras = []; // fertige Object3D (z. B. Glow-Sprites), {part, obj}
  }
  // t: {p:[x,y,z], ry, rx, rz, s:[x,y,z]|number}
  add(part, matKey, geom, x = 0, y = 0, z = 0, ry = 0, rx = 0, rz = 0, s = 1) {
    let g = geom.index ? geom.toNonIndexed() : geom.clone();
    if (matKey.startsWith('foliage')) g.deleteAttribute('uv');
    else if (g.attributes.color) g.deleteAttribute('color');
    if (!matKey.startsWith('foliage') && !g.attributes.uv) {
      g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    }
    _o.position.set(x, y, z);
    _o.rotation.set(rx, ry, rz, 'YXZ');
    if (typeof s === 'number') _o.scale.setScalar(s);
    else _o.scale.set(s[0], s[1], s[2]);
    _o.updateMatrix();
    g.applyMatrix4(_o.matrix);
    const k = part + '|' + matKey;
    if (!this.bins.has(k)) this.bins.set(k, []);
    this.bins.get(k).push(g);
    return this;
  }
  finalize() {
    const root = new THREE.Group();
    const parts = {};
    for (const p of PARTS) {
      parts[p] = new THREE.Group();
      parts[p].name = p;
      root.add(parts[p]);
    }
    for (const [k, geoms] of this.bins) {
      const [part, matKey] = k.split('|');
      const g = geoms.length > 1 ? mergeGeometries(geoms, false) : geoms[0];
      const mesh = new THREE.Mesh(g, this.mats.get(matKey, part));
      const flat = matKey.startsWith('dirt') || matKey.startsWith('lawn') || matKey.startsWith('line');
      mesh.castShadow = !flat;
      mesh.receiveShadow = !matKey.startsWith('line');
      if (matKey.startsWith('dirt')) mesh.renderOrder = 1;
      if (matKey.startsWith('lawn')) mesh.renderOrder = 2;
      if (matKey.startsWith('line')) mesh.renderOrder = 3;
      parts[part].add(mesh);
    }
    for (const e of this.extras) parts[e.part].add(e.obj);
    root.userData = { parts, height: this.height, roofHeight: this.roofHeight, anim: this.anim, size: this.size };
    return root;
  }
}

// ---------- Bäume ----------
const treeCache = new Map();
function blob(r, seed, squash = 1, detail = 2) {
  let g = new THREE.IcosahedronGeometry(r, detail);
  g.deleteAttribute('uv');
  g.deleteAttribute('normal');
  g = mergeVertices(g);
  const fbm = makeNoise(seed);
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i) / r, y = pos.getY(i) / r, z = pos.getZ(i) / r;
    const n = fbm(x * 1.1 + 9 + y * 0.7, z * 1.1 + 5 - y * 0.6, 2), n2 = fbm(x * 4.2 + 3 + y * 2.3, z * 4.2 + y * 3.1 + 1, 2);
    const k = 0.62 + n * 0.62 + (n2 - 0.5) * 0.3;
    pos.setXYZ(i, x * k * r, y * k * squash * r, z * k * r);
  }
  g.computeVertexNormals();
  return g;
}
function colorize(g, base, yMin, yMax, seed) {
  const fbm = makeNoise(seed + 3);
  const pos = g.attributes.position;
  const col = new Float32Array(pos.count * 3);
  const c = new THREE.Color(base), warm = new THREE.Color('#b9c46a');
  const t = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const hgt = clamp((y - yMin) / (yMax - yMin));
    const n = fbm(x * 3.1 + y * 1.7, z * 3.1 - y * 1.3, 2);
    const k = 0.34 + 0.72 * hgt + (n - 0.5) * 0.5;
    t.copy(c).lerp(warm, clamp((n - 0.55) * 1.6) * hgt);
    col[i * 3] = t.r * k;
    col[i * 3 + 1] = t.g * k;
    col[i * 3 + 2] = t.b * k;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return g;
}
// liefert {foliage, trunk} in lokalen Koordinaten (Stammfuß bei y=0, Höhe ~1 Einheit = 1 m)
export function treeGeoms(species, variant) {
  const key = species + variant;
  if (treeCache.has(key)) return treeCache.get(key);
  const rnd = mulberry32(variant * 131 + species.length * 17 + 1);
  const parts = [];
  let trunk, top;
  if (species === 'cypress') {
    const b = blob(1, variant + 20, 1);
    b.scale(0.95, 4.2, 0.95);
    b.translate(0, 4.9, 0);
    parts.push(b);
    trunk = cyl(0.14, 0.2, 1.2, 6);
    trunk.translate(0, 0.6, 0);
    top = 9;
    parts.forEach((g) => colorize(g, '#3d6140', 0.8, top, variant));
  } else if (species === 'conifer') {
    for (let i = 0; i < 4; i++) {
      const c = new THREE.ConeGeometry(2.3 - i * 0.48, 2.8, 9);
      c.deleteAttribute('uv');
      c.translate(0, 2.6 + i * 1.7, 0);
      parts.push(c.toNonIndexed());
    }
    trunk = cyl(0.18, 0.26, 1.6, 6);
    trunk.translate(0, 0.8, 0);
    top = 9.5;
    parts.forEach((g) => colorize(g, '#3c6a41', 1.2, top, variant));
  } else if (species === 'bush') {
    for (let i = 0; i < 3; i++) {
      const b = blob(0.55 + rnd() * 0.25, variant * 7 + i, 0.85, 1);
      b.translate((rnd() - 0.5) * 0.9, 0.45 + rnd() * 0.2, (rnd() - 0.5) * 0.9);
      parts.push(b);
    }
    trunk = cyl(0.04, 0.05, 0.2, 4);
    trunk.translate(0, 0.1, 0);
    top = 1.3;
    parts.forEach((g) => colorize(g, '#5a8440', 0, top, variant));
  } else {
    const th = 2.6 + rnd() * 0.8;
    const n = 7 + ((rnd() * 3) | 0);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 6.28 + rnd(), rr = i === 0 ? 0 : 1.1 + rnd() * 0.7;
      const b = blob(1.35 + rnd() * 0.75, variant * 13 + i, 0.9);
      b.translate(Math.cos(a) * rr, th + 1.5 + (i === 0 ? 1.3 : rnd() * 1.2), Math.sin(a) * rr);
      parts.push(b);
    }
    trunk = cyl(0.16, 0.28, th + 1.2, 7);
    trunk.translate(0, (th + 1.2) / 2, 0);
    top = th + 4.8;
    const tint = species === 'linden' ? '#6f9648' : species === 'autumn' ? '#b58534' : '#587f3c';
    parts.forEach((g) => colorize(g, tint, th, top, variant));
  }
  const foliage = mergeGeometries(parts.map((g) => (g.index ? g.toNonIndexed() : g)));
  const out = { foliage, trunk };
  treeCache.set(key, out);
  return out;
}
export function addTree(kit, part, species, variant, x, z, scale = 1, ry = 0) {
  const t = treeGeoms(species, variant % 5);
  kit.add(part, 'foliage', t.foliage, x, 0, z, ry, 0, 0, scale);
  kit.add(part, 'bark', t.trunk, x, 0, z, ry, 0, 0, scale);
}
