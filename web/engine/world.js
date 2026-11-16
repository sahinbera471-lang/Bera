// Landschaft, Himmel und Beleuchtung. Alles deterministisch aus city/state.json (terrain + lighting).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { Tex } from './textures.js';
import { mulberry32, makeNoise, lerp, clamp, smooth } from './util.js';

const SIZE = 2600; // Kantenlänge der Landschaft in Metern
const FLAT_R = 330; // innerhalb dieses Radius ist das Baugebiet eben

export function makeTerrainFn(seed) {
  const fbm = makeNoise(seed);
  return function height(x, z) {
    const r = Math.hypot(x, z);
    const k = smooth(clamp((r - FLAT_R) / 520));
    if (k <= 0) return 0;
    const n = fbm(x / 420 + 7.3, z / 420 + 2.1, 4);
    return k * (n * 95 - 18) + k * k * 14;
  };
}

function macroTexture(seed) {
  const W = 2048;
  const c = document.createElement('canvas');
  c.width = c.height = W;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(W, W);
  const d = img.data;
  const fbm = makeNoise(seed + 1);
  const fbm2 = makeNoise(seed + 2);
  const cos = Math.cos(0.42), sin = Math.sin(0.42);
  const hash = (a, b) => {
    let h = (a * 374761393 + b * 668265263) ^ (seed * 1274126177);
    h = (h ^ (h >>> 13)) * 1274126177;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };
  const crops = [
    [196, 178, 96], [158, 172, 82], [112, 150, 66], [176, 152, 104], [134, 164, 74], [206, 190, 118], [98, 138, 62],
  ];
  for (let py = 0; py < W; py++) {
    for (let px = 0; px < W; px++) {
      const x = (px / W - 0.5) * SIZE, z = (py / W - 0.5) * SIZE;
      const r = Math.hypot(x, z);
      const n = fbm(x / 160, z / 160, 4);
      const n2 = fbm2(x / 28, z / 28, 3);
      // Wiese: mehrere Maßstäbe (große Flecken, trockene Stellen, feines Rauschen)
      const n3 = fbm(x / 9 + 50, z / 9 + 50, 2);
      const dry = smooth(clamp((fbm2(x / 75 + 13, z / 75 + 4, 3) - 0.5) / 0.22));
      const grain = (hash(px, py) - 0.5) * 12;
      let R = lerp(74, 104, n) + n2 * 20 + n3 * 12 + dry * 30 + grain;
      let G = lerp(108, 134, n) + n2 * 22 + n3 * 14 + dry * 12 + grain;
      let B = lerp(44, 58, n) + n2 * 8 + n3 * 4 - dry * 4 + grain * 0.5;
      // Felder außerhalb des Baugebiets
      const fieldK = smooth(clamp((r - (FLAT_R + 60) - n * 120) / 30));
      if (fieldK > 0) {
        const u = x * cos + z * sin, v = -x * sin + z * cos;
        const cu = Math.floor(u / 170), cv = Math.floor(v / 110);
        const h = hash(cu, cv);
        const fu = u / 170 - cu, fv = v / 110 - cv;
        const edge = Math.min(fu, 1 - fu) * 170 < 3 || Math.min(fv, 1 - fv) * 110 < 3;
        if (h > 0.3 && !edge) {
          const cr = crops[(h * 977) % crops.length | 0];
          const rows = 0.93 + 0.07 * Math.sin(v * 1.6);
          const k = fieldK * 0.9;
          R = lerp(R, cr[0] * rows * (0.9 + n2 * 0.2), k);
          G = lerp(G, cr[1] * rows * (0.9 + n2 * 0.2), k);
          B = lerp(B, cr[2] * rows * (0.9 + n2 * 0.2), k);
        }
      }
      // Wald (dunkler Boden unter den Bäumen)
      const f = forestDensity(fbm2, x, z, r);
      if (f > 0) {
        R = lerp(R, 44, f * 0.8);
        G = lerp(G, 66, f * 0.8);
        B = lerp(B, 34, f * 0.8);
      }
      const i = (py * W + px) * 4;
      d[i] = R;
      d[i + 1] = G;
      d[i + 2] = B;
      d[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function forestDensity(fbm2, x, z, r) {
  if (r < FLAT_R + 30) return 0;
  const n = fbm2(x / 230 + 31.7, z / 230 + 11.9, 3);
  return smooth(clamp((n - 0.56) / 0.08)) * smooth(clamp((r - FLAT_R - 30) / 60));
}

function buildForest(seed, height) {
  const rnd = mulberry32(seed + 77);
  const fbm2 = makeNoise(seed + 2);
  // einfacher Baum aus Stamm + zwei Kronen, als InstancedMesh
  const crown = new THREE.IcosahedronGeometry(1, 0).toNonIndexed();
  crown.scale(1, 1.25, 1);
  crown.translate(0, 1.9, 0);
  const crown2 = new THREE.IcosahedronGeometry(0.72, 0).toNonIndexed();
  crown2.translate(0.45, 2.7, 0.2);
  const trunk = new THREE.CylinderGeometry(0.12, 0.18, 1.2, 3, 1, true).toNonIndexed();
  trunk.translate(0, 0.6, 0);
  const paint = (g, r, gg, b) => {
    const n = g.attributes.position.count;
    const col = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const y = g.attributes.position.getY(i);
      const k = 0.45 + 0.55 * clamp(y / 3.2);
      col[i * 3] = r * k;
      col[i * 3 + 1] = gg * k;
      col[i * 3 + 2] = b * k;
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  };
  paint(crown, 0.9, 0.95, 0.85);
  paint(crown2, 1.0, 1.0, 0.9);
  paint(trunk, 0.5, 0.36, 0.26);
  const geo = mergeGeometries([crown, crown2, trunk]);
  const mat = new THREE.MeshLambertMaterial({ vertexColors: true });
  const pts = [];
  let guard = 0;
  while (pts.length < 4200 && guard++ < 400000) {
    const x = (rnd() - 0.5) * SIZE * 0.96, z = (rnd() - 0.5) * SIZE * 0.96;
    const r = Math.hypot(x, z);
    const f = forestDensity(fbm2, x, z, r);
    // im Wald dicht, sonst vereinzelte Baumgruppen
    if (rnd() < f * 0.9 || (r > FLAT_R + 20 && rnd() < 0.0035)) pts.push([x, z]);
  }
  const mesh = new THREE.InstancedMesh(geo, mat, pts.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  const col = new THREE.Color();
  pts.forEach(([x, z], i) => {
    const sc = 2.6 + rnd() * 2.0;
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * 6.28);
    s.set(sc, sc * (0.9 + rnd() * 0.35), sc);
    p.set(x, height(x, z) - 0.3, z);
    m.compose(p, q, s);
    mesh.setMatrixAt(i, m);
    col.setHSL(0.24 + rnd() * 0.08, 0.32 + rnd() * 0.16, 0.2 + rnd() * 0.1);
    mesh.setColorAt(i, col);
  });
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  mesh.frustumCulled = false;
  return mesh;
}

// Himmelskuppel mit Farbverlauf, Sonnenglühen und prozeduralen Wolken
function cloudNoise(seed) {
  const W = 512;
  const c = document.createElement('canvas');
  c.width = c.height = W;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(W, W);
  const fbm = makeNoise(seed + 909);
  for (let y = 0; y < W; y++)
    for (let x = 0; x < W; x++) {
      const u = x / W, v = y / W, S = 5;
      const n = fbm(u * S, v * S, 5) * (1 - u) * (1 - v) + fbm((u - 1) * S, v * S, 5) * u * (1 - v) + fbm(u * S, (v - 1) * S, 5) * (1 - u) * v + fbm((u - 1) * S, (v - 1) * S, 5) * u * v;
      const i = (y * W + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = clamp(n * 255, 0, 255);
      img.data[i + 3] = 255;
    }
  ctx.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

function makeSky(seed) {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      zenith: { value: new THREE.Color() }, horizon: { value: new THREE.Color() }, away: { value: new THREE.Color() },
      sunColor: { value: new THREE.Color() }, cloudLit: { value: new THREE.Color() }, cloudDark: { value: new THREE.Color() },
      sunDir: { value: new THREE.Vector3(0, 1, 0) }, glow: { value: 1 }, cover: { value: 0.5 }, noise: { value: cloudNoise(seed) },
    },
    vertexShader: `varying vec3 vDir; void main(){ vDir = position; vec4 p = modelViewMatrix * vec4(position,1.0); gl_Position = projectionMatrix * p; gl_Position.z = gl_Position.w; }`,
    fragmentShader: `
      varying vec3 vDir;
      uniform vec3 zenith, horizon, away, sunColor, cloudLit, cloudDark, sunDir;
      uniform float glow, cover;
      uniform sampler2D noise;
      void main(){
        vec3 d = normalize(vDir);
        float h = max(d.y, 0.0);
        vec2 dh = normalize(d.xz + 1e-5), sh = normalize(sunDir.xz + 1e-5);
        float toSun = dot(dh, sh) * 0.5 + 0.5;
        vec3 hor = mix(away, horizon, pow(toSun, 1.6));
        vec3 col = mix(hor, zenith, pow(h, 0.42));
        float s = max(dot(d, normalize(sunDir)), 0.0);
        col += sunColor * (pow(s, 5.0) * 0.22 + pow(s, 48.0) * 0.55) * glow;
        if (d.y > 0.015) {
          vec2 uv = d.xz / (d.y + 0.12) * 0.11;
          float n = texture2D(noise, uv).r * 0.62 + texture2D(noise, uv * 2.7 + 0.31).r * 0.38;
          float c = smoothstep(cover, cover + 0.2, n);
          float n2 = texture2D(noise, uv + sh * 0.012).r * 0.62 + texture2D(noise, (uv + sh * 0.012) * 2.7 + 0.31).r * 0.38;
          float lit = clamp(0.55 + (n - n2) * 6.0, 0.0, 1.0);
          vec3 cc = mix(cloudDark, cloudLit, lit) + sunColor * pow(s, 6.0) * 0.35 * glow;
          col = mix(col, cc, c * smoothstep(0.015, 0.2, d.y) * 0.92);
        }
        col += sunColor * pow(s, 1400.0) * 6.0;
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(7000, 48, 24), mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -10;
  return mesh;
}

export class World {
  constructor(scene, renderer, state) {
    this.scene = scene;
    this.renderer = renderer;
    const seed = state.terrain.seed;
    this.height = makeTerrainFn(seed);
    this.lighting = state.lighting;

    // --- Gelände ---
    const segs = 220;
    const geo = new THREE.PlaneGeometry(SIZE, SIZE, segs, segs);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setY(i, this.height(pos.getX(i), pos.getZ(i)));
    geo.computeVertexNormals();
    const detail = Tex.grassDetail();
    const mat = new THREE.MeshLambertMaterial({ map: macroTexture(seed) });
    mat.onBeforeCompile = (s) => {
      s.uniforms.detailMap = { value: detail };
      s.fragmentShader = s.fragmentShader
        .replace('void main() {', 'uniform sampler2D detailMap;\nvoid main() {')
        .replace(
          '#include <map_fragment>',
          `#include <map_fragment>
           float dA = texture2D(detailMap, vMapUv * 520.0).r;
           float dB = texture2D(detailMap, vMapUv * 61.0 + 0.37).r;
           float dC = texture2D(detailMap, vMapUv * 9.0 + 0.11).r;
           diffuseColor.rgb *= (0.55 + dA * 0.9) * (0.75 + dB * 0.5) * (0.85 + dC * 0.3);`
        );
    };
    const ground = new THREE.Mesh(geo, mat);
    ground.receiveShadow = true;
    ground.name = 'ground';
    scene.add(ground);
    this.ground = ground;

    this.forest = buildForest(seed, this.height);
    scene.add(this.forest);
    // --- Himmel ---
    this.sky = makeSky(seed);
    scene.add(this.sky);

    // --- Licht ---
    this.sun = new THREE.DirectionalLight(0xffffff, 3);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(4096, 4096);
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.06;
    scene.add(this.sun);
    scene.add(this.sun.target);
    this.hemi = new THREE.HemisphereLight(0xbfd8ff, 0x5c6b3a, 1);
    scene.add(this.hemi);
    scene.fog = new THREE.Fog(0xcfe0ee, 260, 3000);

    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.envMats = []; // Materialien mit Himmelsreflexion
    this.nightMats = []; // Materialien, deren Emission mit der Dämmerung steigt
    this.nightOpacity = []; // Materialien, deren Deckkraft mit der Dämmerung steigt (Lichtkegel)
    this.nightObjs = []; // Objekte (Glows), die ab einer Schwelle eingeschaltet werden
    this._envTod = -1;
    this.tod = -1;
    this.setTimeOfDay(this.lighting.timeOfDay ?? 0.15);
  }

  registerEnv(mat) {
    mat.envMap = this.envRT ? this.envRT.texture : null;
    this.envMats.push(mat);
  }

  registerNightOpacity(mat, maxOpacity) {
    mat.userData.nightMax = maxOpacity;
    mat.opacity = maxOpacity * (this.night || 0);
    this.nightOpacity.push(mat);
  }

  registerNight(mat, maxIntensity) {
    mat.emissiveIntensity = maxIntensity * (this.night || 0);
    mat.userData.nightMax = maxIntensity;
    this.nightMats.push(mat);
  }

  // tod: 0 = Nachmittag, ~0.5 goldene Stunde, 1 = Sonnenuntergang (Lichter an)
  setTimeOfDay(tod) {
    tod = clamp(tod);
    if (Math.abs(tod - this.tod) < 1e-4) return;
    this.tod = tod;
    const L = this.lighting;
    const C = (h) => new THREE.Color(h);
    const elev = lerp(L.sunElevationDay, L.sunElevationDusk, smooth(tod));
    const az = L.sunAzimuth + tod * 10;
    const theta = THREE.MathUtils.degToRad(az);
    const dir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - elev), theta);
    // Schattenlicht nie zu flach, sonst werden die Schatten endlos
    this.sunDir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - Math.max(elev, 9)), theta);

    const warm = smooth(clamp((tod - 0.15) / 0.55));
    const dusk = smooth(clamp((tod - 0.55) / 0.45));
    this.sun.color.copy(C(0xfff1dd).lerp(C(0xffb066), warm).lerp(C(0xff7a3c), dusk));
    this.sun.intensity = lerp(3.4, 3.1, warm) * lerp(1, 0.75, dusk);
    this.hemi.color.copy(C(0xbcd6ff).lerp(C(0xcfc0ea), warm).lerp(C(0xa9a6e8), dusk));
    this.hemi.groundColor.copy(C(0x6f7a48).lerp(C(0x6e6478), dusk));
    this.hemi.intensity = lerp(1.6, 1.9, warm) * lerp(1, 1.5, dusk);

    const u = this.sky.material.uniforms;
    u.sunDir.value.copy(dir);
    u.zenith.value.copy(C(0x2f6fd0).lerp(C(0x3a62b8), warm).lerp(C(0x27397e), dusk));
    u.horizon.value.copy(C(0xbfdcf5).lerp(C(0xffd29a), warm).lerp(C(0xff8a3d), dusk));
    u.away.value.copy(C(0xb4d3f2).lerp(C(0xe3c4d6), warm).lerp(C(0x9a7fb0), dusk));
    u.sunColor.value.copy(C(0xfff3d6).lerp(C(0xffc27a), warm).lerp(C(0xff8a4a), dusk));
    u.cloudLit.value.copy(C(0xffffff).lerp(C(0xffe2c2), warm).lerp(C(0xffa878), dusk));
    u.cloudDark.value.copy(C(0xc9d6e6).lerp(C(0xb9a9c2), warm).lerp(C(0x5d5a8c), dusk));
    u.glow.value = lerp(0.7, 1.6, dusk);
    u.cover.value = 0.52;
    this.scene.fog.color.copy(C(0xc3daf0).lerp(C(0xf0cfae), warm).lerp(C(0xc98f7a), dusk));
    this.scene.fog.far = lerp(3600, 2600, dusk);
    this.renderer.toneMappingExposure = lerp(0.6, 0.7, warm) * lerp(1, 1.3, dusk);

    // Lichter gehen in der Dämmerung an
    const night = smooth(clamp((tod - 0.62) / 0.3));
    this.night = night;
    for (const m of this.nightMats) m.emissiveIntensity = m.userData.nightMax * night;
    for (const m of this.nightOpacity) m.opacity = m.userData.nightMax * night;
    for (const o of this.nightObjs) o.visible = night > (o.userData.nightThreshold ?? 0.02);
    // Umgebungslicht-Map nur bei spürbarer Änderung neu erzeugen (teuer)
    if (Math.abs(tod - this._envTod) > 0.1) {
      this._envTod = tod;
      const envScene = new THREE.Scene();
      envScene.add(new THREE.Mesh(this.sky.geometry, this.sky.material));
      const old = this.envRT;
      this.envRT = this.pmrem.fromScene(envScene, 0, 1, 12000);
      // Reflexionen nur auf Glas/Metall/Wasser (spart im Software-Renderer viel Zeit)
      for (const m of this.envMats) m.envMap = this.envRT.texture;
      if (old) old.dispose();
    }
  }

  // Schattenkamera folgt dem Bildausschnitt
  fitShadow(center, radius) {
    const r = clamp(radius, 60, 520);
    const cam = this.sun.shadow.camera;
    // an Texel-Raster einrasten, damit Schatten nicht flimmern
    const texel = (2 * r) / 4096;
    const cx = Math.round(center.x / texel) * texel, cz = Math.round(center.z / texel) * texel;
    this.sun.target.position.set(cx, 0, cz);
    this.sun.position.set(cx, 0, cz).addScaledVector(this.sunDir, 900);
    if (cam.right !== r) {
      cam.left = -r;
      cam.right = r;
      cam.top = r;
      cam.bottom = -r;
      cam.near = 100;
      cam.far = 1900;
      cam.updateProjectionMatrix();
    }
    this.sun.target.updateMatrixWorld();
  }
}
