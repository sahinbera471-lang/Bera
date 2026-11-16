// Prozedurale Tonspur: leise Hintergrundmusik + zur Bauanimation synchrone Soundeffekte.
// Alles wird deterministisch synthetisiert (keine fremden Audiodateien, keine Lizenzfragen).
import fs from 'node:fs';
import { mulberry32 } from '../web/engine/util.js';

const SR = 44100;

class Bus {
  constructor(seconds) {
    this.n = Math.ceil(seconds * SR);
    this.L = new Float32Array(this.n);
    this.R = new Float32Array(this.n);
  }
  add(i, v, pan = 0) {
    if (i < 0 || i >= this.n) return;
    this.L[i] += v * Math.min(1, 1 - pan);
    this.R[i] += v * Math.min(1, 1 + pan);
  }
  mix(other, gain = 1) {
    for (let i = 0; i < this.n; i++) {
      this.L[i] += other.L[i] * gain;
      this.R[i] += other.R[i] * gain;
    }
  }
}

const midi = (m) => 440 * Math.pow(2, (m - 69) / 12);

// Gezupfte Saite (Karplus-Strong) – erinnert an Saz/Bağlama
function pluck(bus, rnd, t, freq, amp, dur = 1.6, pan = 0, bright = 0.5) {
  const N = Math.max(2, Math.round(SR / freq));
  const buf = new Float32Array(N);
  let prev = 0;
  for (let i = 0; i < N; i++) {
    const w = rnd() * 2 - 1;
    prev = prev + bright * (w - prev);
    buf[i] = prev;
  }
  const i0 = Math.round(t * SR), len = Math.round(dur * SR);
  let p = 0;
  const decay = 0.9965 - 0.0008 * (freq / 440);
  for (let i = 0; i < len; i++) {
    const nx = (p + 1) % N;
    const v = buf[p];
    buf[p] = (buf[p] + buf[nx]) * 0.5 * decay;
    p = nx;
    const env = Math.min(1, i / 40) * Math.min(1, (len - i) / 2000);
    bus.add(i0 + i, v * amp * env, pan);
  }
}

// weiche Fläche aus leicht verstimmten Obertönen
function pad(bus, t, dur, notes, amp) {
  const i0 = Math.round(t * SR), len = Math.round(dur * SR);
  const att = 1.2 * SR, rel = 1.6 * SR;
  notes.forEach((m, k) => {
    const f = midi(m);
    for (const [det, pan] of [[-0.35, -0.5], [0.3, 0.5], [0, 0]]) {
      const w = (2 * Math.PI * f * Math.pow(2, det / 120)) / SR;
      for (let i = 0; i < len + rel; i++) {
        const env = Math.min(1, i / att) * (i > len ? Math.max(0, 1 - (i - len) / rel) : 1);
        const trem = 0.85 + 0.15 * Math.sin((2 * Math.PI * (0.13 + k * 0.03) * i) / SR + k);
        const v = Math.sin(w * i) + 0.32 * Math.sin(2 * w * i + 0.4) + 0.12 * Math.sin(3 * w * i + 1.1);
        bus.add(i0 + i, v * amp * env * trem * 0.33, pan);
      }
    }
  });
}

function kick(bus, t, amp = 0.8) {
  const i0 = Math.round(t * SR), len = Math.round(0.4 * SR);
  let ph = 0;
  for (let i = 0; i < len; i++) {
    const x = i / SR;
    ph += (2 * Math.PI * (42 + 95 * Math.exp(-x * 26))) / SR;
    bus.add(i0 + i, Math.sin(ph) * Math.exp(-x * 8.5) * amp);
  }
}

// Darbuka-artige Schläge: "dum" (tief) und "tek" (hell)
function dum(bus, rnd, t, amp = 0.5, pan = 0) {
  const i0 = Math.round(t * SR), len = Math.round(0.3 * SR);
  let ph = 0;
  for (let i = 0; i < len; i++) {
    const x = i / SR;
    ph += (2 * Math.PI * (88 + 60 * Math.exp(-x * 40))) / SR;
    bus.add(i0 + i, (Math.sin(ph) * Math.exp(-x * 13) + (rnd() * 2 - 1) * 0.25 * Math.exp(-x * 90)) * amp, pan);
  }
}
function tek(bus, rnd, t, amp = 0.25, pan = 0.2, f = 950) {
  const i0 = Math.round(t * SR), len = Math.round(0.12 * SR);
  let y1 = 0, y2 = 0;
  const w = (2 * Math.PI * f) / SR, r = 0.985;
  for (let i = 0; i < len; i++) {
    const x = i / SR;
    const inp = (rnd() * 2 - 1) * Math.exp(-x * 120);
    const y = inp + 2 * r * Math.cos(w) * y1 - r * r * y2;
    y2 = y1;
    y1 = y;
    bus.add(i0 + i, y * 0.09 * Math.exp(-x * 30) * amp * 4, pan);
  }
}

// gefiltertes Rauschen mit wanderndem Bandpass (Whoosh, Riser, Walze)
function noiseSweep(bus, rnd, t, dur, f0, f1, amp, { q = 0.92, pan0 = 0, pan1 = 0, shape = 'bell' } = {}) {
  const i0 = Math.round(t * SR), len = Math.round(dur * SR);
  let y1 = 0, y2 = 0;
  for (let i = 0; i < len; i++) {
    const k = i / len;
    const f = f0 * Math.pow(f1 / f0, k);
    const w = (2 * Math.PI * f) / SR;
    const y = (rnd() * 2 - 1) * (1 - q) + 2 * q * Math.cos(w) * y1 - q * q * y2;
    y2 = y1;
    y1 = y;
    const env = shape === 'bell' ? Math.sin(Math.PI * k) ** 2 : shape === 'rise' ? k * k * Math.min(1, (1 - k) * 40) : Math.min(1, k * 20) * Math.min(1, (1 - k) * 6);
    bus.add(i0 + i, y * env * amp * 3, pan0 + (pan1 - pan0) * k);
  }
}

function tone(bus, t, freq, dur, amp, { pan = 0, decay = 6, harm = 0.3, glide = 0 } = {}) {
  const i0 = Math.round(t * SR), len = Math.round(dur * SR);
  let ph = 0;
  for (let i = 0; i < len; i++) {
    const x = i / SR;
    ph += (2 * Math.PI * freq * (1 + glide * x)) / SR;
    const env = Math.min(1, i / 60) * Math.exp(-x * decay);
    bus.add(i0 + i, (Math.sin(ph) + harm * Math.sin(2 * ph)) * env * amp, pan);
  }
}

function knock(bus, rnd, t, amp, pan) {
  // Hammerschlag: kurzer Klick + hölzerne Resonanz
  tek(bus, rnd, t, amp, pan, 420 + rnd() * 500);
  tone(bus, t, 160 + rnd() * 80, 0.09, amp * 0.5, { pan, decay: 45 });
}

// einfacher Hall (4 Kammfilter + 2 Allpässe)
function reverb(bus, mixAmt = 0.25) {
  for (const ch of [bus.L, bus.R]) {
    const dry = Float32Array.from(ch);
    const wet = new Float32Array(ch.length);
    const off = ch === bus.R ? 23 : 0;
    for (const [d, g] of [[1557, 0.82], [1617, 0.81], [1491, 0.83], [1422, 0.8]]) {
      const D = d + off, buf = new Float32Array(D);
      let p = 0, lp = 0;
      for (let i = 0; i < ch.length; i++) {
        const o = buf[p];
        lp = lp + 0.4 * (o - lp);
        buf[p] = dry[i] + lp * g;
        p = (p + 1) % D;
        wet[i] += o * 0.25;
      }
    }
    for (const d of [225 + off, 556 + off]) {
      const buf = new Float32Array(d);
      let p = 0;
      for (let i = 0; i < ch.length; i++) {
        const b = buf[p], x = wet[i];
        const y = -0.5 * x + b;
        buf[p] = x + 0.5 * y;
        wet[i] = y;
        p = (p + 1) % d;
      }
    }
    for (let i = 0; i < ch.length; i++) ch[i] = dry[i] * (1 - mixAmt * 0.3) + wet[i] * mixAmt;
  }
}

function normalize(bus, peak = 0.89) {
  let m = 0;
  for (let i = 0; i < bus.n; i++) m = Math.max(m, Math.abs(bus.L[i]), Math.abs(bus.R[i]));
  const g = m > 0 ? peak / m : 1;
  for (let i = 0; i < bus.n; i++) {
    bus.L[i] *= g;
    bus.R[i] *= g;
  }
}

// auf Ziel-Lautheit bringen und Spitzen weich begrenzen
function level(bus, targetRms = 0.12) {
  let sum = 0;
  for (let i = 0; i < bus.n; i++) sum += bus.L[i] * bus.L[i] + bus.R[i] * bus.R[i];
  const rms = Math.sqrt(sum / (2 * bus.n)) || 1;
  const g = targetRms / rms;
  for (let i = 0; i < bus.n; i++) {
    bus.L[i] = Math.tanh(bus.L[i] * g * 1.4) / 1.4;
    bus.R[i] = Math.tanh(bus.R[i] * g * 1.4) / 1.4;
  }
}

function fade(bus, dur, tIn = 0.4, tOut = 1.2) {
  for (let i = 0; i < bus.n; i++) {
    const t = i / SR;
    const g = Math.min(1, t / tIn) * Math.min(1, Math.max(0, (dur - t) / tOut));
    bus.L[i] *= g;
    bus.R[i] *= g;
  }
}

export function writeWav(file, bus) {
  const n = bus.n, buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0);
  buf.writeUInt32LE(36 + n * 4, 4);
  buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(2, 22);
  buf.writeUInt32LE(SR, 24);
  buf.writeUInt32LE(SR * 4, 28);
  buf.writeUInt16LE(4, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36);
  buf.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) {
    buf.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(bus.L[i] * 32767))), 44 + i * 4);
    buf.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(bus.R[i] * 32767))), 46 + i * 4);
  }
  fs.writeFileSync(file, buf);
}

// ---------------------------------------------------------------- Musik
export function makeMusic(ep) {
  const dur = ep.duration, bus = new Bus(dur + 2), rnd = mulberry32(1000 + ep.number);
  const bpm = 92, beat = 60 / bpm, bar = beat * 4;
  const P = ep.phases || {};
  const tBuild = P.road ?? P.area ?? P.building ?? 9, tLamps = P.lamps ?? dur - 14, tFinal = P.final ?? dur - 8;
  // d-Moll mit Hicaz-Färbung: i – VI – iv – V
  const chords = [[50, 57, 62, 65], [46, 53, 58, 62], [43, 50, 55, 58], [45, 52, 57, 61]];
  const scale = [62, 63, 66, 67, 69, 70, 72, 74, 75, 78, 79, 81]; // D Hicaz
  const bars = Math.ceil(dur / bar) + 1;
  let deg = 4;
  for (let b = 0; b < bars; b++) {
    const t0 = b * bar, ch = chords[b % 4];
    const final = t0 >= tFinal - 0.1, calm = t0 >= tLamps - 0.1 && !final;
    pad(bus, t0, bar, [ch[0] - 12, ch[1], ch[2], ch[3]], final ? 0.085 : 0.06);
    if (final) pad(bus, t0, bar, [ch[2] + 12, ch[3] + 12], 0.03);
    // Arpeggio (Achtel) ab dem Intro-Ende
    if (t0 >= (P.survey ?? 5) - 0.1)
      for (let s = 0; s < 8; s++) {
        if (calm && s % 2) continue;
        const note = ch[[0, 2, 1, 3, 2, 1, 3, 2][s]] + (s % 4 === 3 ? 12 : 0);
        pluck(bus, rnd, t0 + s * beat * 0.5 + (s % 2 ? 0.012 : 0), midi(note), (s % 4 === 0 ? 0.17 : 0.11) * (final ? 1.15 : 1), 1.4, s % 2 ? 0.35 : -0.35, 0.45);
      }
    // Melodie (ab Baubeginn), kleine zufällige Schritte auf der Hicaz-Leiter
    if (t0 >= tBuild - 0.1 && !calm) {
      const pattern = [[0, 1.5], [1.5, 0.5], [2, 1], [3, 0.5], [3.5, 0.5]];
      for (const [at, len] of pattern) {
        if (rnd() < 0.22) continue;
        deg = Math.max(0, Math.min(scale.length - 1, deg + [-2, -1, -1, 0, 1, 1, 2][(rnd() * 7) | 0]));
        if (at === 0) {
          // auf Akkordton landen
          const target = ch.map((n) => n + 12).concat(ch.map((n) => n + 24));
          deg = scale.reduce((best, n, i) => (target.some((x) => x % 12 === n % 12) && Math.abs(i - deg) < Math.abs(best - deg) ? i : best), deg + 9);
          deg = Math.max(0, Math.min(scale.length - 1, deg));
        }
        pluck(bus, rnd, t0 + at * beat, midi(scale[deg] + (final ? 12 : 0)), final ? 0.2 : 0.16, len * beat + 0.9, 0.1, 0.8);
      }
    }
    // Rhythmus (Maksum-artig: dum tek . tek dum . tek .)
    if (t0 >= tBuild - 0.1 && !calm) {
      const pat = ['d', 't', '', 't', 'd', '', 't', ''];
      pat.forEach((h, s) => {
        const t = t0 + s * beat * 0.5;
        if (h === 'd') {
          dum(bus, rnd, t, 0.34);
          if (final) kick(bus, t, 0.5);
        } else if (h === 't') tek(bus, rnd, t, 0.2, 0.25);
        else if (final || b % 2) tek(bus, rnd, t, 0.07, -0.3, 1500);
      });
    }
  }
  // Spannungsaufbau vor der Schlussaufnahme
  noiseSweep(bus, rnd, tFinal - 3.2, 3.2, 300, 5200, 0.12, { shape: 'rise' });
  kick(bus, tFinal, 1.0);
  tone(bus, tFinal, 36.7, 2.6, 0.5, { decay: 1.6, harm: 0.1 });
  reverb(bus, 0.3);
  level(bus, 0.13);
  fade(bus, dur);
  return bus;
}

// ---------------------------------------------------------------- Soundeffekte
export function makeSfx(ep, state) {
  const dur = ep.duration, bus = new Bus(dur + 2), rnd = mulberry32(2000 + ep.number);
  const byId = new Map([...state.roads, ...state.items].map((o) => [o.id, o]));
  const panOf = (o) => (o && o.x != null ? Math.max(-0.6, Math.min(0.6, o.x / 160)) : 0);
  // Szenenwechsel
  for (const s of ep.shots) {
    if (s.start < 0.5) continue;
    if (s.in === 'flash') {
      noiseSweep(bus, rnd, s.start - 0.45, 0.8, 500, 3600, 0.22, { pan0: -0.6, pan1: 0.6 });
      kick(bus, s.start, 0.35);
    } else if (s.in === 'whip') noiseSweep(bus, rnd, s.start - 0.25, 0.5, 1800, 500, 0.2, { pan0: 0.6, pan1: -0.6 });
  }
  // Intro: tiefer Einschlag + Wind über dem leeren Land
  kick(bus, ep.intro?.start ?? 0.3, 0.9);
  tone(bus, ep.intro?.start ?? 0.3, 55, 2.2, 0.35, { decay: 1.8 });
  noiseSweep(bus, rnd, 0, Math.min(6, ep.phases?.survey ?? 5) + 1, 260, 420, 0.07, { q: 0.97, shape: 'flat' });
  // Vermessung: kurze Signaltöne
  for (const fx of ep.effects || []) {
    const n = Math.max(3, Math.min(10, Math.round((fx.end - fx.start) * 2)));
    for (let i = 0; i < n; i++) tone(bus, fx.start + ((fx.end - fx.start) * i) / n, i % 2 ? 1320 : 990, 0.12, 0.09, { decay: 30, pan: (rnd() - 0.5) * 0.8 });
  }
  for (const b of ep.builds) {
    const o = byId.get(b.id), pan = panOf(o), d = b.end - b.start;
    if (!o) continue;
    if (o.type === 'road') {
      // Walze: tiefes Rumpeln + Schotter
      noiseSweep(bus, rnd, b.start + d * 0.1, d * 0.8, 70, 95, 0.5, { q: 0.985, shape: 'flat' });
      noiseSweep(bus, rnd, b.start, d * 0.6, 2200, 3200, 0.05, { q: 0.8, shape: 'flat' });
      tone(bus, b.end - 0.2, 660, 0.5, 0.1, { decay: 7 });
    } else if (o.type === 'tree') {
      tone(bus, b.start + 0.15, 300 + rnd() * 160, 0.22, 0.16, { pan, decay: 16, glide: 2.2 });
      noiseSweep(bus, rnd, b.start + 0.1, 0.3, 3000, 6000, 0.03, { q: 0.7, pan0: pan, pan1: pan });
    } else if (o.type === 'lamp') {
      tek(bus, rnd, b.start + 0.5, 0.35, pan, 2400);
      tone(bus, b.start + 0.55, 1760 + rnd() * 300, 0.5, 0.06, { pan, decay: 9 });
    } else {
      // Gebäude / Platz: Fundament-Schlag, Hammern beim Hochziehen, Abschluss-Akkord
      dum(bus, rnd, b.start + d * 0.14, 0.9, pan);
      noiseSweep(bus, rnd, b.start + d * 0.05, d * 0.2, 180, 420, 0.1, { q: 0.95, shape: 'flat', pan0: pan, pan1: pan });
      const t0 = b.start + d * 0.2, t1 = b.start + d * 0.8;
      for (let t = t0; t < t1; t += 0.16 + rnd() * 0.3) if (rnd() < 0.75) knock(bus, rnd, t, 0.2 + rnd() * 0.25, pan + (rnd() - 0.5) * 0.3);
      noiseSweep(bus, rnd, b.start + d * 0.6, d * 0.2, 900, 2600, 0.06, { q: 0.9, pan0: pan, pan1: pan });
      for (const [k, m] of [[0, 74], [0.07, 78], [0.14, 81]]) tone(bus, b.end - 0.35 + k, midi(m), 0.9, 0.11, { pan, decay: 5 });
    }
  }
  // Lichter gehen an: Summen + Schimmer
  if (ep.phases?.lamps != null) noiseSweep(bus, rnd, ep.phases.lamps + 1, 4, 5000, 9000, 0.02, { q: 0.9, shape: 'bell' });
  // Endkarte
  if (ep.endCard) {
    kick(bus, ep.endCard.start, 0.7);
    for (const [k, m] of [[0, 62], [0.1, 69], [0.2, 74], [0.3, 81]]) tone(bus, ep.endCard.start + k, midi(m), 2.2, 0.1, { decay: 2.2 });
  }
  reverb(bus, 0.16);
  level(bus, 0.09);
  fade(bus, dur, 0.05, 0.6);
  return bus;
}
