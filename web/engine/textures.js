// Prozedurale Texturen (Canvas) – deterministisch, keine externen Bilddateien nötig.
import * as THREE from 'three';
import { mulberry32, makeNoise } from './util.js';

const cache = new Map();

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

function finish(c, { repeat = [1, 1], srgb = true, aniso = 8 } = {}) {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = aniso;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function speckle(ctx, w, h, rnd, count, colors, size = [1, 2], alpha = [0.1, 0.4]) {
  for (let i = 0; i < count; i++) {
    ctx.globalAlpha = alpha[0] + rnd() * (alpha[1] - alpha[0]);
    ctx.fillStyle = colors[(rnd() * colors.length) | 0];
    const s = size[0] + rnd() * (size[1] - size[0]);
    ctx.fillRect(rnd() * w, rnd() * h, s, s);
  }
  ctx.globalAlpha = 1;
}

function noiseFill(ctx, w, h, seed, scale, lo, hi, oct = 4) {
  const fbm = makeNoise(seed);
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      // kachelbar durch Überblenden
      const u = x / w, v = y / h;
      const n =
        fbm(u * scale, v * scale, oct) * (1 - u) * (1 - v) +
        fbm((u - 1) * scale, v * scale, oct) * u * (1 - v) +
        fbm(u * scale, (v - 1) * scale, oct) * (1 - u) * v +
        fbm((u - 1) * scale, (v - 1) * scale, oct) * u * v;
      const k = lo + (hi - lo) * n;
      const i = (y * w + x) * 4;
      d[i] *= k;
      d[i + 1] *= k;
      d[i + 2] *= k;
    }
  }
  ctx.putImageData(img, 0, 0);
}

function make(key, fn) {
  if (!cache.has(key)) cache.set(key, fn());
  return cache.get(key);
}

export const Tex = {
  grassDetail() {
    return make('grassDetail', () => {
      const c = canvas(512, 512), ctx = c.getContext('2d');
      ctx.fillStyle = '#8a8a8a';
      ctx.fillRect(0, 0, 512, 512);
      const rnd = mulberry32(11);
      // feine Halme
      for (let i = 0; i < 26000; i++) {
        const x = rnd() * 512, y = rnd() * 512, l = 2 + rnd() * 5;
        const g = 40 + rnd() * 200;
        ctx.strokeStyle = `rgba(${g},${g},${g},${0.35 + rnd() * 0.5})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + (rnd() - 0.5) * 2.5, y - l);
        ctx.stroke();
      }
      noiseFill(ctx, 512, 512, 5, 6, 0.7, 1.3);
      return finish(c, { srgb: false });
    });
  },
  asphalt() {
    return make('asphalt', () => {
      const c = canvas(512, 512), ctx = c.getContext('2d');
      ctx.fillStyle = '#3d3e41';
      ctx.fillRect(0, 0, 512, 512);
      const rnd = mulberry32(3);
      speckle(ctx, 512, 512, rnd, 30000, ['#5a5b5e', '#2a2b2d', '#6b6b6b', '#333'], [1, 2.2], [0.15, 0.55]);
      noiseFill(ctx, 512, 512, 9, 5, 0.82, 1.12);
      return finish(c);
    });
  },
  asphaltBump() {
    return make('asphaltBump', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#808080';
      ctx.fillRect(0, 0, 256, 256);
      speckle(ctx, 256, 256, mulberry32(4), 14000, ['#fff', '#000'], [1, 2], [0.1, 0.35]);
      return finish(c, { srgb: false });
    });
  },
  gravel() {
    return make('gravel', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#8b7a63';
      ctx.fillRect(0, 0, 256, 256);
      speckle(ctx, 256, 256, mulberry32(7), 9000, ['#a8977d', '#6f604c', '#b9ab95', '#5d5142'], [1.5, 4], [0.3, 0.8]);
      noiseFill(ctx, 256, 256, 2, 4, 0.8, 1.15);
      return finish(c);
    });
  },
  dirt() {
    return make('dirt', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#7a5f45';
      ctx.fillRect(0, 0, 256, 256);
      speckle(ctx, 256, 256, mulberry32(8), 7000, ['#8c7052', '#5e4732', '#9a8468'], [1.5, 5], [0.2, 0.6]);
      noiseFill(ctx, 256, 256, 3, 4, 0.75, 1.2);
      return finish(c);
    });
  },
  // Gehwegplatten
  pavers() {
    return make('pavers', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      const rnd = mulberry32(21);
      const n = 8, s = 256 / n;
      for (let y = 0; y < n; y++)
        for (let x = 0; x < n; x++) {
          const g = 168 + rnd() * 28;
          ctx.fillStyle = `rgb(${g},${g - 3},${g - 9})`;
          ctx.fillRect(x * s, y * s, s, s);
        }
      ctx.strokeStyle = 'rgba(70,66,60,0.75)';
      ctx.lineWidth = 2;
      for (let i = 0; i <= n; i++) {
        ctx.beginPath();
        ctx.moveTo(i * s, 0);
        ctx.lineTo(i * s, 256);
        ctx.moveTo(0, i * s);
        ctx.lineTo(256, i * s);
        ctx.stroke();
      }
      speckle(ctx, 256, 256, rnd, 5000, ['#fff', '#444'], [1, 2], [0.05, 0.2]);
      return finish(c);
    });
  },
  // Kopfsteinpflaster für Plätze
  cobble() {
    return make('cobble', () => {
      const c = canvas(512, 512), ctx = c.getContext('2d');
      ctx.fillStyle = '#4c4640';
      ctx.fillRect(0, 0, 512, 512);
      const rnd = mulberry32(31);
      const rows = 16, h = 512 / rows;
      for (let r = 0; r < rows; r++) {
        const cols = 16, w = 512 / cols, off = r % 2 ? w / 2 : 0;
        for (let q = -1; q < cols; q++) {
          const t = rnd();
          const base = t < 0.25 ? [176, 150, 122] : t < 0.6 ? [158, 148, 136] : [140, 128, 116];
          const k = 0.88 + rnd() * 0.24;
          ctx.fillStyle = `rgb(${base[0] * k},${base[1] * k},${base[2] * k})`;
          const x = q * w + off + 2, y = r * h + 2;
          ctx.beginPath();
          ctx.roundRect(x, y, w - 4, h - 4, 5);
          ctx.fill();
        }
      }
      speckle(ctx, 512, 512, rnd, 9000, ['#fff', '#222'], [1, 2], [0.04, 0.16]);
      return finish(c);
    });
  },
  plaster() {
    return make('plaster', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#f2f2f2';
      ctx.fillRect(0, 0, 256, 256);
      speckle(ctx, 256, 256, mulberry32(41), 16000, ['#fff', '#c9c9c9', '#dedede'], [1, 2], [0.2, 0.6]);
      noiseFill(ctx, 256, 256, 14, 3, 0.9, 1.06);
      return finish(c);
    });
  },
  brick() {
    return make('brick', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#b9b2a6';
      ctx.fillRect(0, 0, 256, 256);
      const rnd = mulberry32(51);
      const rows = 16, h = 16, w = 32;
      for (let r = 0; r < rows; r++)
        for (let q = -1; q < 9; q++) {
          const k = 0.8 + rnd() * 0.35;
          ctx.fillStyle = `rgb(${170 * k},${84 * k},${62 * k})`;
          ctx.fillRect(q * w + (r % 2 ? w / 2 : 0) + 1, r * h + 1, w - 2, h - 2);
        }
      speckle(ctx, 256, 256, rnd, 5000, ['#fff', '#222'], [1, 2], [0.05, 0.2]);
      return finish(c);
    });
  },
  concrete() {
    return make('concrete', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#b4b2ad';
      ctx.fillRect(0, 0, 256, 256);
      speckle(ctx, 256, 256, mulberry32(61), 9000, ['#d0cfca', '#8f8d88'], [1, 3], [0.1, 0.4]);
      noiseFill(ctx, 256, 256, 15, 3, 0.85, 1.1);
      return finish(c);
    });
  },
  roofTiles() {
    return make('roofTiles', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      const rnd = mulberry32(71);
      const rows = 8, h = 32, cols = 8, w = 32;
      for (let r = 0; r < rows; r++) {
        for (let q = -1; q <= cols; q++) {
          const k = 0.78 + rnd() * 0.36;
          const x = q * w + (r % 2 ? w / 2 : 0), y = r * h;
          const gr = ctx.createLinearGradient(0, y, 0, y + h);
          gr.addColorStop(0, `rgb(${235 * k},${235 * k},${235 * k})`);
          gr.addColorStop(0.8, `rgb(${185 * k},${185 * k},${185 * k})`);
          gr.addColorStop(1, `rgb(${70 * k},${70 * k},${70 * k})`);
          ctx.fillStyle = gr;
          ctx.beginPath();
          ctx.roundRect(x + 1, y, w - 2, h, [0, 0, 9, 9]);
          ctx.fill();
        }
      }
      return finish(c);
    });
  },
  wood() {
    return make('wood', () => {
      const c = canvas(128, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#8a5a34';
      ctx.fillRect(0, 0, 128, 256);
      const rnd = mulberry32(81);
      for (let i = 0; i < 90; i++) {
        ctx.strokeStyle = `rgba(${40 + rnd() * 60},${25 + rnd() * 30},10,${0.15 + rnd() * 0.3})`;
        ctx.lineWidth = 1 + rnd() * 2;
        const x = rnd() * 128;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.bezierCurveTo(x + rnd() * 8 - 4, 80, x + rnd() * 8 - 4, 170, x + rnd() * 6 - 3, 256);
        ctx.stroke();
      }
      return finish(c);
    });
  },
  // Fensterglas: Himmelsspiegelung als Verlauf
  glass() {
    return make('glass', () => {
      const c = canvas(64, 128), ctx = c.getContext('2d');
      const g = ctx.createLinearGradient(0, 0, 64, 128);
      g.addColorStop(0, '#9fc4e0');
      g.addColorStop(0.45, '#4a6a86');
      g.addColorStop(0.55, '#2c4257');
      g.addColorStop(1, '#1b2a39');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 64, 128);
      ctx.fillStyle = 'rgba(255,255,255,0.18)';
      ctx.beginPath();
      ctx.moveTo(0, 30);
      ctx.lineTo(64, 0);
      ctx.lineTo(64, 22);
      ctx.lineTo(0, 62);
      ctx.fill();
      const t = finish(c);
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      return t;
    });
  },
  // Fassadenraster für große Gebäude (Fensterbänder) – als Farb- und Emissive-Map
  facade(kind = 'office') {
    return make('facade_' + kind, () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      const e = canvas(256, 256), ectx = e.getContext('2d');
      const rnd = mulberry32(kind.length * 97 + 5);
      ctx.fillStyle = kind === 'office' ? '#d9dde2' : '#efe9de';
      ctx.fillRect(0, 0, 256, 256);
      ectx.fillStyle = '#000';
      ectx.fillRect(0, 0, 256, 256);
      const cols = 4, rows = 4, cw = 64, ch = 64;
      for (let r = 0; r < rows; r++)
        for (let q = 0; q < cols; q++) {
          const x = q * cw + (kind === 'office' ? 5 : 14), y = r * ch + (kind === 'office' ? 10 : 14);
          const w = kind === 'office' ? cw - 10 : cw - 28, h = kind === 'office' ? ch - 22 : ch - 26;
          const g = ctx.createLinearGradient(x, y, x + w, y + h);
          g.addColorStop(0, '#8fb4d1');
          g.addColorStop(0.5, '#3e5c78');
          g.addColorStop(1, '#22364a');
          ctx.fillStyle = g;
          ctx.fillRect(x, y, w, h);
          ctx.strokeStyle = kind === 'office' ? '#6f7780' : '#fbfbfb';
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, w, h);
          if (kind !== 'office') {
            ctx.beginPath();
            ctx.moveTo(x + w / 2, y);
            ctx.lineTo(x + w / 2, y + h);
            ctx.stroke();
          }
          if (rnd() < 0.55) {
            const warm = rnd() < 0.7;
            ectx.fillStyle = warm ? `rgba(255,${190 + rnd() * 40},${110 + rnd() * 40},1)` : 'rgba(200,225,255,1)';
            ectx.fillRect(x + 2, y + 2, w - 4, h - 4);
          }
        }
      return { map: finish(c), emissive: finish(e) };
    });
  },
  bark() {
    return make('bark', () => {
      const c = canvas(64, 128), ctx = c.getContext('2d');
      ctx.fillStyle = '#5b4634';
      ctx.fillRect(0, 0, 64, 128);
      const rnd = mulberry32(91);
      for (let i = 0; i < 80; i++) {
        ctx.strokeStyle = `rgba(30,20,12,${0.2 + rnd() * 0.4})`;
        ctx.lineWidth = 1 + rnd() * 2;
        const x = rnd() * 64;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x + rnd() * 6 - 3, 128);
        ctx.stroke();
      }
      return finish(c);
    });
  },
  leaves() {
    return make('leaves', () => {
      const c = canvas(256, 256), ctx = c.getContext('2d');
      ctx.fillStyle = '#7d7d7d';
      ctx.fillRect(0, 0, 256, 256);
      const rnd = mulberry32(101);
      for (let i = 0; i < 2600; i++) {
        const g = 60 + rnd() * 190;
        ctx.fillStyle = `rgba(${g},${g},${g},${0.5 + rnd() * 0.5})`;
        ctx.beginPath();
        ctx.ellipse(rnd() * 256, rnd() * 256, 3 + rnd() * 5, 2 + rnd() * 3, rnd() * 6.28, 0, 6.28);
        ctx.fill();
      }
      return finish(c);
    });
  },
  water() {
    return make('water', () => {
      const c = canvas(128, 128), ctx = c.getContext('2d');
      ctx.fillStyle = '#3f7fa6';
      ctx.fillRect(0, 0, 128, 128);
      noiseFill(ctx, 128, 128, 44, 5, 0.75, 1.3);
      return finish(c);
    });
  },
  pitch() {
    return make('pitch', () => {
      const c = canvas(512, 320), ctx = c.getContext('2d');
      for (let i = 0; i < 10; i++) {
        ctx.fillStyle = i % 2 ? '#3f8f3a' : '#4a9d43';
        ctx.fillRect(i * 51.2, 0, 51.2, 320);
      }
      ctx.strokeStyle = '#f4f4f4';
      ctx.lineWidth = 4;
      ctx.strokeRect(14, 14, 484, 292);
      ctx.beginPath();
      ctx.moveTo(256, 14);
      ctx.lineTo(256, 306);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(256, 160, 44, 0, 6.3);
      ctx.stroke();
      ctx.strokeRect(14, 80, 70, 160);
      ctx.strokeRect(428, 80, 70, 160);
      ctx.strokeRect(14, 122, 26, 76);
      ctx.strokeRect(472, 122, 26, 76);
      const t = finish(c);
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      return t;
    });
  },
  // Schild mit Text (Geschäfte, Supermarkt …)
  sign(text, bg = '#b3261e', fg = '#ffffff') {
    return make('sign_' + text + bg + fg, () => {
      const c = canvas(512, 96), ctx = c.getContext('2d');
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, 512, 96);
      ctx.fillStyle = fg;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      let size = 60;
      do {
        ctx.font = `${size}px Anton, Impact, sans-serif`;
        size -= 2;
      } while (ctx.measureText(text).width > 480 && size > 16);
      ctx.fillText(text, 256, 52);
      const t = finish(c);
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      return t;
    });
  },
  // weicher, radialer Lichtfleck (Glow-Sprites, Lichtkegel am Boden, Staub)
  glow() {
    return make('glow', () => {
      const c = canvas(128, 128), ctx = c.getContext('2d');
      const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
      g.addColorStop(0, 'rgba(255,255,255,1)');
      g.addColorStop(0.25, 'rgba(255,255,255,0.55)');
      g.addColorStop(0.6, 'rgba(255,255,255,0.14)');
      g.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 128, 128);
      const t = finish(c);
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      return t;
    });
  },
  // Markise mit Streifen
  awning(a = '#b3261e', b = '#f5f0e6') {
    return make('awning' + a + b, () => {
      const c = canvas(128, 32), ctx = c.getContext('2d');
      for (let i = 0; i < 8; i++) {
        ctx.fillStyle = i % 2 ? a : b;
        ctx.fillRect(i * 16, 0, 16, 32);
      }
      return finish(c);
    });
  },
};
