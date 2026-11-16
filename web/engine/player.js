// Player: verbindet Welt, Stadt, Kamera-Regie und Overlay. Wird vom Dashboard (Live-Vorschau)
// und vom Renderer (Frame für Frame, deterministisch) identisch benutzt.
import * as THREE from 'three';
import { World } from './world.js';
import { CityView } from './city.js';
import { Overlay } from './overlay.js';
import { clamp, lerp, easeInOut, easeOut, smooth } from './util.js';

const EASE = { inOut: easeInOut, out: easeOut, linear: (x) => x, smooth };

export async function loadFonts() {
  await Promise.all([
    document.fonts.load('60px Anton'),
    document.fonts.load('700 30px Inter'),
    document.fonts.load('800 30px Inter'),
  ]).catch(() => {});
}

export class Player {
  constructor({ canvas, width = 1080, height = 1920, state }) {
    this.out = canvas;
    this.width = width;
    this.height = height;
    canvas.width = width;
    canvas.height = height;
    this.ctx = canvas.getContext('2d');
    this.gl = document.createElement('canvas');
    this.renderer = new THREE.WebGLRenderer({ canvas: this.gl, antialias: true, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height, false);
    this.renderer.setPixelRatio(1);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.localClippingEnabled = true;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, width / height, 1, 9000);
    this.state = state;
    this.world = new World(this.scene, this.renderer, state);
    this.overlay = new Overlay(this.ctx, width, height);
    this.view = null;
    this.episode = null;
    this.look = new THREE.Vector3();
    this.showOverlay = true;
  }

  // episode = null: fertiger Stand; sonst Bauanimation dieser Episode
  setCity(state, episode = null) {
    if (this.view) this.view.dispose();
    this.state = state;
    this.episode = episode;
    this.view = new CityView(this.scene, this.world, state, episode);
  }

  shotAt(t) {
    const shots = this.episode.shots;
    let s = shots[0];
    for (const x of shots) if (t >= x.start) s = x;
    return s;
  }

  applyShot(s, t) {
    const k = EASE[s.ease || 'inOut'](clamp((t - s.start) / Math.max(0.001, s.end - s.start)));
    const cam = this.camera;
    if (s.type === 'orbit') {
      const a = THREE.MathUtils.degToRad(lerp(s.a0, s.a1, k)), r = lerp(s.r0, s.r1, k);
      cam.position.set(s.center[0] + Math.cos(a) * r, lerp(s.h0, s.h1, k), s.center[2] + Math.sin(a) * r);
      if (s.look) this.look.set(s.look[0], s.look[1], s.look[2]);
      else this.look.set(s.center[0], s.lookY ?? 0, s.center[2]);
      cam.fov = lerp(s.fov0 ?? 42, s.fov1 ?? 42, k);
    } else {
      cam.position.set(lerp(s.from.pos[0], s.to.pos[0], k), lerp(s.from.pos[1], s.to.pos[1], k), lerp(s.from.pos[2], s.to.pos[2], k));
      this.look.set(lerp(s.from.look[0], s.to.look[0], k), lerp(s.from.look[1], s.to.look[1], k), lerp(s.from.look[2], s.to.look[2], k));
      cam.fov = lerp(s.from.fov, s.to.fov, k);
    }
    cam.lookAt(this.look);
    cam.updateProjectionMatrix();
  }

  todAt(t) {
    const keys = this.episode.todKeys;
    if (!keys || !keys.length) return this.state.lighting.timeOfDay ?? 0.15;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++)
      if (t <= keys[i][0]) return lerp(keys[i - 1][1], keys[i][1], smooth((t - keys[i - 1][0]) / (keys[i][0] - keys[i - 1][0])));
    return keys.at(-1)[1];
  }

  // Episode zum Zeitpunkt t (Sekunden) zeichnen
  renderAt(t) {
    const ep = this.episode;
    this.view.setTime(t);
    this.world.setTimeOfDay(this.todAt(t));
    this.applyShot(this.shotAt(t), t);
    this.draw();
    if (this.showOverlay) this.overlay.draw(ep, t);
  }

  // freie Kamera (Dashboard-Vorschau)
  renderFree(tod = null) {
    if (tod != null) this.world.setTimeOfDay(tod);
    this.draw();
  }

  draw() {
    // Schatten dort scharf, wo die Kamera auf den Boden schaut
    const c = this.camera.position, dir = this.look.clone().sub(c).normalize();
    const tHit = dir.y < -0.02 ? Math.min(-c.y / dir.y, 1200) : 400;
    const focus = c.clone().addScaledVector(dir, tHit * 0.8);
    this.world.fitShadow(focus, Math.max(tHit * 0.75, c.y * 0.8));
    this.renderer.render(this.scene, this.camera);
    this.ctx.drawImage(this.gl, 0, 0, this.width, this.height);
  }
}
