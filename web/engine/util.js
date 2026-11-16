// Kleine, abhängigkeitsfreie Helfer (laufen in Browser und Node).

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashString(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const invLerp = (a, b, x) => clamp((x - a) / (b - a));
export const smooth = (t) => t * t * (3 - 2 * t);
export const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const easeOut = (t) => 1 - Math.pow(1 - t, 3);
export const easeIn = (t) => t * t * t;
export function easeOutBack(t) {
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}
// Teilfortschritt: wie weit ist p innerhalb [a,b]?
export const seg = (p, a, b) => clamp((p - a) / (b - a));

// 2D Value-Noise (deterministisch)
export function makeNoise(seed) {
  const rnd = mulberry32(seed);
  const N = 256;
  const g = new Float32Array(N * N);
  for (let i = 0; i < g.length; i++) g[i] = rnd();
  const at = (x, y) => g[((y & 255) << 8) | (x & 255)];
  function n(x, y) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const u = smooth(xf), v = smooth(yf);
    return lerp(lerp(at(xi, yi), at(xi + 1, yi), u), lerp(at(xi, yi + 1), at(xi + 1, yi + 1), u), v);
  }
  return function fbm(x, y, oct = 4) {
    let s = 0, a = 0.5, f = 1, tot = 0;
    for (let o = 0; o < oct; o++) {
      s += a * n(x * f, y * f);
      tot += a;
      a *= 0.5;
      f *= 2.03;
    }
    return s / tot;
  };
}

export function formatEuro(n) {
  return new Intl.NumberFormat('de-DE').format(Math.round(n)) + ' €';
}
export function formatInt(n) {
  return new Intl.NumberFormat('de-DE').format(Math.round(n));
}
export const pad3 = (n) => String(n).padStart(3, '0');
