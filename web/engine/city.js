// CityView: baut die Stadt aus city/state.json auf und spielt die Bauanimation einer Episode ab.
import * as THREE from 'three';
import { MatLib, box, cyl } from './kit.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { buildItem } from './models.js';
import { buildRoad } from './roads.js';
import { Tex } from './textures.js';
import { CATALOG, footprint, itemClass } from './catalog.js';
import { clamp, lerp, seg, easeOut, easeOutBack, easeInOut, hashString, mulberry32 } from './util.js';

const TINY = 0.0001;

function scaffoldFor(root, mats) {
  const it = root.userData.item;
  const c = CATALOG[it.type] || {};
  const w = (it.w || c.w || 10) + 1.4, d = (it.d || c.d || 10) + 1.4;
  const H = root.userData.height + 0.8;
  const geoms = [];
  const push = (g, x, y, z) => {
    g.translate(x, y, z);
    geoms.push(g.toNonIndexed());
  };
  const stepX = w / Math.max(2, Math.round(w / 2.6)), stepZ = d / Math.max(2, Math.round(d / 2.6));
  for (let x = -w / 2; x <= w / 2 + 0.01; x += stepX) for (const z of [-d / 2, d / 2]) push(box(0.09, H, 0.09), x, H / 2, z);
  for (let z = -d / 2 + stepZ; z < d / 2 - 0.01; z += stepZ) for (const x of [-w / 2, w / 2]) push(box(0.09, H, 0.09), x, H / 2, z);
  const levels = Math.min(14, Math.max(2, Math.round(H / 2.2)));
  for (let i = 1; i <= levels; i++) {
    const y = (i / levels) * H - 0.2;
    for (const z of [-d / 2, d / 2]) {
      push(box(w, 0.07, 0.07), 0, y, z);
      push(box(w, 0.05, 0.5), 0, y - 0.95, z);
    }
    for (const x of [-w / 2, w / 2]) {
      push(box(0.07, 0.07, d), x, y, 0);
      push(box(0.5, 0.05, d), x, y - 0.95, 0);
    }
  }
  const mesh = new THREE.Mesh(mergeGeometries(geoms), mats.get('metal:#9aa0a6'));
  mesh.castShadow = true;
  return mesh;
}

function craneFor(root, mats) {
  const H = root.userData.height + 12;
  const g = new THREE.Group();
  const yellow = mats.get('color:#f2b01e:0.5');
  const tower = new THREE.Mesh(box(1.6, H, 1.6), yellow);
  tower.position.y = H / 2;
  const jib = new THREE.Group();
  jib.position.y = H;
  const arm = new THREE.Mesh(box(34, 1.1, 1.1), yellow);
  arm.position.x = 11;
  const cw = new THREE.Mesh(box(3, 2, 2), mats.get('concrete:#9a9a9a'));
  cw.position.x = -5;
  const cab = new THREE.Mesh(box(2, 2, 1.8), mats.get('color:#f4f4f4'));
  cab.position.set(1.4, -1.2, 1);
  const cable = new THREE.Mesh(box(0.08, H * 0.45, 0.08), mats.get('color:#222'));
  cable.position.set(20, -H * 0.225, 0);
  jib.add(arm, cw, cab, cable);
  g.add(tower, jib);
  g.traverse((o) => (o.castShadow = true));
  g.userData.jib = jib;
  const s = root.userData.size;
  g.position.set(-s[0] / 2 + 1, 0, -s[1] / 2 + 1);
  return g;
}

function makeRoller(mats) {
  const g = new THREE.Group();
  const y = mats.get('color:#f2b01e:0.5'), dk = mats.get('metal:#4a4d52');
  const body = new THREE.Mesh(box(3.2, 1.3, 2), y);
  body.position.set(-0.2, 1.6, 0);
  const cab = new THREE.Mesh(box(1.5, 1.4, 1.8), mats.get('color:#22272b:0.3'));
  cab.position.set(-0.6, 2.9, 0);
  const roof = new THREE.Mesh(box(1.9, 0.14, 2.1), y);
  roof.position.set(-0.6, 3.7, 0);
  const drum = new THREE.Mesh(cyl(0.85, 0.85, 2.2, 18), dk);
  drum.rotation.x = Math.PI / 2;
  drum.position.set(1.7, 0.95, 0);
  const drum2 = drum.clone();
  drum2.position.x = -1.7;
  g.add(body, cab, roof, drum, drum2);
  g.traverse((o) => (o.castShadow = true));
  g.scale.setScalar(1.25);
  return g;
}

export class CityView {
  // episode: null = aktueller Stand komplett gebaut; sonst wird alles mit item.episode === episode.number animiert
  constructor(scene, world, state, episode = null) {
    this.scene = scene;
    this.world = world;
    this.state = state;
    this.episode = episode;
    this.root = new THREE.Group();
    scene.add(this.root);
    this.shared = new MatLib(world);
    this.anim = []; // {kind, obj, start, end, ...}
    this.objects = new Map();
    const n = episode ? episode.number : Infinity;
    const sched = new Map((episode?.builds || []).map((b) => [b.id, b]));
    const roads = state.roads.filter((r) => (r.episode ?? 1) <= n);

    roads.forEach((r, i) => {
      const b = (r.episode ?? 1) === n ? sched.get(r.id) : null;
      let mats = this.shared, planes = null;
      if (b) {
        planes = { foundation: new THREE.Plane(), structure: new THREE.Plane(), details: new THREE.Plane() };
        mats = new MatLib(world, planes);
      }
      const obj = buildRoad(r, roads, mats, i);
      this.root.add(obj);
      this.objects.set(r.id, obj);
      if (b) {
        const roller = makeRoller(this.shared);
        roller.rotation.y = obj.rotation.y;
        this.root.add(roller);
        this.anim.push({ kind: 'road', obj, planes, roller, start: b.start, end: b.end });
      }
    });

    for (const it of state.items) {
      const ep = it.episode ?? 1;
      if (ep > n) continue;
      const b = ep === n ? sched.get(it.id) : null;
      let mats = this.shared, planes = null;
      if (b) {
        planes = { structure: new THREE.Plane(), roof: new THREE.Plane() };
        mats = new MatLib(world, planes);
      }
      const obj = buildItem(it, mats);
      this.root.add(obj);
      this.objects.set(it.id, obj);
      const parts = obj.userData.parts;
      if (!b) {
        parts.plot.visible = false;
        continue;
      }
      const a = { kind: obj.userData.anim, obj, planes, parts, start: b.start, end: b.end, seed: hashString(it.id) };
      obj.updateMatrixWorld(true);
      if (a.kind === 'staged') {
        a.scaffold = scaffoldFor(obj, this.shared);
        obj.add(a.scaffold);
        if (obj.userData.height > 14) {
          a.crane = craneFor(obj, this.shared);
          obj.add(a.crane);
        }
      }
      if (a.kind !== 'pop') {
        a.dust = [];
        const mat = new THREE.SpriteMaterial({ map: Tex.glow(), color: 0xd9c4a0, transparent: true, opacity: 0, depthWrite: false });
        a.dustMat = mat;
        const s = obj.userData.size;
        for (let i = 0; i < 7; i++) {
          const sp = new THREE.Sprite(mat);
          sp.userData.base = [((i * 0.37) % 1 - 0.5) * s[0] * 0.7, ((i * 0.61) % 1 - 0.5) * s[1] * 0.6];
          obj.add(sp);
          a.dust.push(sp);
        }
      }
      this.anim.push(a);
    }

    // Vermessungs-/Planungslinien für alles, was in dieser Episode entsteht
    this.survey = [];
    for (const fx of episode?.effects || []) {
      if (fx.type !== 'survey') continue;
      const targets = [...state.roads, ...state.items].filter((o) => (o.episode ?? 1) === n && sched.has(o.id) && itemClass(o) !== 'tree' && itemClass(o) !== 'lamp');
      targets.forEach((o, i) => {
        const [x0, z0, x1, z1] = footprint(o);
        const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false, fog: false });
        const g = new THREE.Group();
        const edges = [[x0, z0, x1, z0], [x1, z0, x1, z1], [x1, z1, x0, z1], [x0, z1, x0, z0]];
        const bars = edges.map(([ax, az, bx, bz]) => {
          const len = Math.hypot(bx - ax, bz - az);
          const geo = box(1, 0.2, 0.55);
          geo.translate(0.5, 0, 0);
          const m = new THREE.Mesh(geo, mat);
          m.position.set(ax, 0.32, az);
          m.rotation.y = Math.atan2(-(bz - az), bx - ax);
          m.userData.len = len;
          m.renderOrder = 10;
          g.add(m);
          return m;
        });
        const fillMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false, fog: false });
        const fill = new THREE.Mesh(box(x1 - x0, 0.02, z1 - z0), fillMat);
        fill.position.set((x0 + x1) / 2, 0.3, (z0 + z1) / 2);
        fill.renderOrder = 9;
        g.add(fill);
        const stakeMat = this.shared.get('color:#e53935');
        const stakes = [[x0, z0], [x1, z0], [x1, z1], [x0, z1]].map(([x, z]) => {
          const m = new THREE.Mesh(cyl(0.14, 0.14, 2.6, 6), stakeMat);
          m.position.set(x, 1.3, z);
          m.castShadow = true;
          g.add(m);
          return m;
        });
        this.root.add(g);
        const stagger = (i / Math.max(1, targets.length)) * (fx.end - fx.start) * 0.55;
        const b = sched.get(o.id);
        this.survey.push({ g, mat, fillMat, bars, stakes, start: fx.start + stagger, dur: (fx.end - fx.start) * 0.45, hideAt: b.start + (b.end - b.start) * 0.18 });
      });
    }
    this.scatterMeadow(n);
    this.setTime(episode ? 0 : Infinity);
  }

  // Grasbüschel und Wiesenblumen überall dort, wo (noch) nichts gebaut ist
  scatterMeadow(n) {
    const rnd = mulberry32(this.state.terrain.seed + 5);
    const rects = [...this.state.roads, ...this.state.items].filter((o) => (o.episode ?? 1) <= n && o.type !== 'tree' && o.type !== 'lamp').map((o) => footprint(o));
    const free = (x, z) => !rects.some((f) => x > f[0] - 1 && x < f[2] + 1 && z > f[1] - 1 && z < f[3] + 1);
    const tuft = mergeGeometries([0, 1, 2, 3].map((i) => {
      const h = 0.34 + i * 0.06;
      const g = new THREE.ConeGeometry(0.05, h, 3, 1, true).toNonIndexed();
      g.translate(0, h / 2, 0);
      const a = i * 1.6, tilt = i === 0 ? 0 : 0.3 + (i % 3) * 0.1;
      g.rotateZ(tilt);
      g.rotateY(a);
      g.translate(Math.cos(a) * 0.05, 0, Math.sin(a) * 0.05);
      return g;
    }));
    const make = (geo, mat, count, R, scale, colorFn) => {
      const mesh = new THREE.InstancedMesh(geo, mat, count);
      const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), sc = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), col = new THREE.Color();
      let i = 0, guard = 0;
      while (i < count && guard++ < count * 6) {
        const a = rnd() * 6.283, r = Math.sqrt(rnd()) * R, x = Math.cos(a) * r, z = Math.sin(a) * r;
        if (!free(x, z)) continue;
        const k = scale[0] + rnd() * (scale[1] - scale[0]);
        m.compose(p.set(x, this.world.height(x, z), z), q.setFromAxisAngle(up, rnd() * 6.283), sc.set(k, k * (0.8 + rnd() * 0.6), k));
        mesh.setMatrixAt(i, m);
        mesh.setColorAt(i, colorFn(col, rnd));
        i++;
      }
      mesh.count = i;
      mesh.receiveShadow = true;
      mesh.frustumCulled = false;
      this.root.add(mesh);
    };
    make(tuft, new THREE.MeshLambertMaterial(), 12000, 250, [0.8, 1.7], (c, r) => c.setHSL(0.21 + r() * 0.07, 0.36 + r() * 0.16, 0.25 + r() * 0.1));
    const fl = new THREE.IcosahedronGeometry(0.11, 0);
    fl.translate(0, 0.3, 0);
    const pal = [0xffffff, 0xffe066, 0xf7f3c8, 0xe8a0c8, 0xf4f4f4];
    make(fl, new THREE.MeshLambertMaterial(), 3500, 250, [0.8, 1.5], (c, r) => c.setHex(pal[(r() * pal.length) | 0]));
  }

  dispose() {
    this.scene.remove(this.root);
    this.root.traverse((o) => {
      if (o.geometry && !o.isSprite && !o.geometry.userData.shared) o.geometry.dispose?.();
    });
  }

  setTime(t) {
    for (const a of this.anim) {
      const p = seg(t, a.start, a.end);
      if (a.kind === 'road') this.animRoad(a, p);
      else if (a.kind === 'pop') {
        a.obj.visible = p > 0;
        a.obj.scale.setScalar(Math.max(TINY, easeOutBack(p)));
      } else this.animBuild(a, p, t);
    }
    for (const s of this.survey) {
      const p = seg(t, s.start, s.start + s.dur);
      const fade = 1 - seg(t, s.hideAt, s.hideAt + 0.8);
      s.g.visible = p > 0 && fade > 0;
      s.mat.opacity = 0.95 * fade;
      s.fillMat.opacity = 0.16 * fade * seg(p, 0.6, 1);
      s.bars.forEach((m, i) => m.scale.set(Math.max(TINY, m.userData.len * easeInOut(seg(p, i * 0.2, i * 0.2 + 0.4))), 1, 1));
      s.stakes.forEach((m, i) => m.scale.setScalar(Math.max(TINY, easeOutBack(seg(p, i * 0.2, i * 0.2 + 0.2)))));
    }
  }

  animRoad(a, p) {
    const f = a.obj.userData.frame;
    const d = new THREE.Vector3(f.dir[0], 0, f.dir[1]);
    const base = d.x * f.a[0] + d.z * f.a[1];
    const set = (plane, q) => plane.set(d.clone().negate(), base + f.L * q + (q >= 1 ? 1 : 0) - (q <= 0 ? 0.01 : 0));
    a.obj.visible = p > 0;
    const pa = seg(p, 0.18, 0.82);
    set(a.planes.foundation, seg(p, 0, 0.5));
    set(a.planes.structure, pa);
    set(a.planes.details, seg(p, 0.42, 1));
    a.roller.visible = pa > 0 && pa < 1;
    a.roller.position.set(f.a[0] + d.x * (f.L * pa + 1.5), 0, f.a[1] + d.z * (f.L * pa + 1.5));
  }

  animBuild(a, p, t) {
    const { parts, obj } = a;
    const U = obj.userData;
    obj.visible = p > 0;
    const sweep = a.kind === 'sweep';
    // Baugrund
    parts.plot.visible = p > 0 && p < 1;
    const dirt = parts.plot.children[0];
    if (dirt) dirt.material.opacity = seg(p, 0, 0.07) * (1 - seg(p, 0.88, 1));
    if (!sweep) {
      parts.foundation.visible = p > 0.07;
      parts.foundation.position.y = lerp(-0.75, 0, easeOut(seg(p, 0.07, 0.2)));
      const ps = seg(p, 0.2, 0.62);
      parts.structure.visible = ps > 0;
      a.planes.structure.set(new THREE.Vector3(0, -1, 0), 0.2 + (U.height - 0.15) * ps + (ps >= 1 ? 50 : 0));
      const pr = seg(p, 0.6, 0.8);
      parts.roof.visible = pr > 0;
      a.planes.roof.set(new THREE.Vector3(0, -1, 0), U.roofBase + (U.roofTop - U.roofBase) * pr + (pr >= 1 ? 50 : 0));
      const pd = seg(p, 0.78, 0.88);
      parts.details.visible = pd > 0;
      const sd = lerp(0.88, 1, easeOutBack(pd));
      parts.details.scale.set(sd, 1, sd);
      const pg = seg(p, 0.85, 1);
      parts.garden.visible = pg > 0;
      parts.garden.scale.setScalar(Math.max(TINY, easeOutBack(pg) ));
      if (a.scaffold) {
        const up = clamp(seg(p, 0.17, 0.6) + 0.06), down = 1 - seg(p, 0.8, 0.86);
        a.scaffold.visible = p > 0.17 && down > 0;
        a.scaffold.scale.set(1, Math.max(TINY, up * down), 1);
      }
      if (a.crane) {
        const up = easeOut(seg(p, 0.1, 0.2)) * (1 - seg(p, 0.86, 0.93));
        a.crane.visible = up > 0;
        a.crane.scale.set(1, Math.max(TINY, up), 1);
        a.crane.userData.jib.rotation.y = 0.8 + Math.sin(t * 0.5 + (a.seed % 7)) * 1.1;
      }
    } else {
      const dir = new THREE.Vector3(1, 0, 0).applyQuaternion(obj.quaternion);
      const base = dir.dot(obj.position), w = U.size[0];
      const ps = easeInOut(seg(p, 0.08, 0.62));
      parts.foundation.visible = parts.structure.visible = parts.roof.visible = ps > 0;
      const c = base - w / 2 - 1 + (w + 2) * ps + (ps >= 1 ? 50 : 0);
      a.planes.structure.set(dir.clone().negate(), c);
      a.planes.roof.set(dir.clone().negate(), c);
      const pd = seg(p, 0.6, 0.8);
      parts.details.visible = pd > 0;
      parts.details.scale.set(1, Math.max(TINY, easeOutBack(pd)), 1);
      const pg = seg(p, 0.75, 1);
      parts.garden.visible = pg > 0;
      parts.garden.scale.set(1, Math.max(TINY, easeOutBack(pg)), 1);
    }
    // Baustaub
    if (a.dust) {
      const k = seg(p, 0.03, 0.12) * (1 - seg(p, 0.66, 0.8));
      a.dustMat.opacity = 0.34 * k;
      a.dust.forEach((sp, i) => {
        sp.visible = k > 0;
        const ph = (t * 0.45 + i / a.dust.length + (a.seed % 10) / 10) % 1;
        const sc = (2.5 + ph * 5) * (sweep ? 0.8 : 1);
        sp.scale.set(sc, sc, 1);
        sp.position.set(sp.userData.base[0], 0.6 + ph * 3, sp.userData.base[1]);
      });
    }
  }

  // Umkreis aller gebauten Flächen (für automatische Kameras)
  bounds(filter = null) {
    let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
    for (const o of [...this.state.roads, ...this.state.items]) {
      if (filter && !filter(o)) continue;
      const f = footprint(o);
      x0 = Math.min(x0, f[0]);
      z0 = Math.min(z0, f[1]);
      x1 = Math.max(x1, f[2]);
      z1 = Math.max(z1, f[3]);
    }
    if (!isFinite(x0)) return { cx: 0, cz: 0, r: 60 };
    return { cx: (x0 + x1) / 2, cz: (z0 + z1) / 2, r: Math.hypot(x1 - x0, z1 - z0) / 2 };
  }
}
