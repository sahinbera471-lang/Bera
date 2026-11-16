// 2D-Overlay im TikTok-Layout (1080×1920): Titel, Bauschritte, Untertitel, Preisschilder, Endkarte.
import { clamp, seg, easeOut, easeOutBack, lerp, formatEuro, formatInt, pad3 } from './util.js';

const YELLOW = '#FFE14A';
const TITLE = 'Anton, Impact, sans-serif';
const BODY = 'Inter, Arial, sans-serif';

function text(ctx, str, x, y, { size = 60, font = TITLE, color = '#fff', align = 'center', stroke = 10, alpha = 1, weight = '', shadow = true, spacing = 0 } = {}) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.font = `${weight} ${size}px ${font}`.trim();
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  if (spacing) ctx.letterSpacing = spacing + 'px';
  ctx.lineJoin = 'round';
  if (shadow) {
    ctx.shadowColor = 'rgba(0,0,0,0.55)';
    ctx.shadowBlur = size * 0.25;
    ctx.shadowOffsetY = size * 0.06;
  }
  if (stroke) {
    ctx.strokeStyle = 'rgba(8,10,14,0.92)';
    ctx.lineWidth = stroke;
    ctx.strokeText(str, x, y);
  }
  ctx.shadowColor = 'transparent';
  ctx.fillStyle = color;
  ctx.fillText(str, x, y);
  ctx.restore();
}

function chip(ctx, str, x, y, { size = 34, bg = 'rgba(10,12,16,0.72)', color = '#fff', padX = 26, h = 62, alpha = 1, accent = null } = {}) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.font = `700 ${size}px ${BODY}`;
  ctx.letterSpacing = '2px';
  const w = ctx.measureText(str).width + padX * 2 + (accent ? 22 : 0);
  ctx.fillStyle = bg;
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y - h / 2, w, h, h / 2);
  ctx.fill();
  if (accent) {
    ctx.fillStyle = accent;
    ctx.beginPath();
    ctx.arc(x - w / 2 + padX, y, 8, 0, 6.3);
    ctx.fill();
  }
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(str, x + (accent ? 11 : 0), y + 2);
  ctx.restore();
}

// Zeilenumbruch nach Breite
function wrap(ctx, str, maxW, font) {
  ctx.font = font;
  const words = str.split(' ');
  const lines = [];
  let cur = '';
  for (const w of words) {
    const t = cur ? cur + ' ' + w : w;
    if (ctx.measureText(t).width > maxW && cur) {
      lines.push(cur);
      cur = w;
    } else cur = t;
  }
  if (cur) lines.push(cur);
  return lines;
}

// Untertitel-Blöcke aus Wort-Zeitstempeln
export function subtitleChunks(words, maxChars = 16, maxWords = 3) {
  const chunks = [];
  let cur = [];
  const flush = () => {
    if (cur.length) chunks.push({ words: cur, start: cur[0].start, end: cur.at(-1).end });
    cur = [];
  };
  for (const w of words) {
    const len = cur.reduce((s, x) => s + x.text.length + 1, 0) + w.text.length;
    if (cur.length && (len > maxChars || cur.length >= maxWords)) flush();
    cur.push(w);
    if (/[.!?…:]$/.test(w.text) || (/,$/.test(w.text) && cur.length >= 2)) flush();
  }
  flush();
  for (let i = 0; i < chunks.length; i++) {
    const next = chunks[i + 1];
    chunks[i].end = next ? Math.min(next.start, chunks[i].end + 0.6) : chunks[i].end + 0.5;
  }
  return chunks;
}

export function isKeyword(word, highlights = []) {
  const w = word.replace(/[^\p{L}\p{N}€%]/gu, '');
  if (!w) return false;
  if (/\d|€/.test(w)) return true;
  const up = w.toUpperCase();
  return highlights.some((h) => up === h.toUpperCase() || (h.length > 4 && up.startsWith(h.toUpperCase())));
}

export class Overlay {
  constructor(ctx, W = 1080, H = 1920) {
    this.ctx = ctx;
    this.W = W;
    this.H = H;
    this.chunks = null;
  }

  draw(ep, t) {
    const ctx = this.ctx, W = 1080, H = 1920;
    ctx.save();
    ctx.scale(this.W / W, this.H / H);
    // Vignette + Lesbarkeitsverläufe
    let g = ctx.createRadialGradient(W / 2, H * 0.5, H * 0.3, W / 2, H * 0.5, H * 0.75);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(0,0,0,0.38)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    g = ctx.createLinearGradient(0, 0, 0, 420);
    g.addColorStop(0, 'rgba(0,0,0,0.42)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, 420);
    g = ctx.createLinearGradient(0, H - 620, 0, H);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(0,0,0,0.5)');
    ctx.fillStyle = g;
    ctx.fillRect(0, H - 620, W, 620);

    const vo = ep.voiceover && ep.voiceover.words && ep.voiceover.words.length ? ep.voiceover : null;
    const endStart = ep.endCard ? ep.endCard.start : Infinity;

    // ---- Kopfzeile ----
    const headA = seg(t, 0.2, 0.7) * (1 - seg(t, endStart - 0.4, endStart));
    if (headA > 0) {
      chip(ctx, `${ep.intro?.title || 'AUSLÄNDERSTADT'}  ·  EP ${pad3(ep.number)}`, W / 2, 262, { alpha: headA, size: 30, h: 58 });
    }

    // ---- Intro-Titel ----
    const I = ep.intro;
    if (I && t >= I.start && t <= I.end + 0.4) {
      const a = seg(t, I.start, I.start + 0.35) * (1 - seg(t, I.end, I.end + 0.4));
      const pop = lerp(1.25, 1, easeOut(seg(t, I.start, I.start + 0.45)));
      ctx.save();
      ctx.translate(W / 2, 620);
      ctx.scale(pop, pop);
      ctx.globalAlpha = a;
      text(ctx, I.kicker, 0, -178, { size: 46, font: BODY, weight: '800', color: YELLOW, stroke: 8, spacing: 8 });
      let size = 150;
      ctx.font = `${size}px ${TITLE}`;
      while (ctx.measureText(I.title).width > 940 && size > 60) ctx.font = `${(size -= 4)}px ${TITLE}`;
      text(ctx, I.title, 0, -30, { size, stroke: 16 });
      ctx.restore();
      I.line.forEach((l, i) => {
        const la = seg(t, I.start + 0.9 + i * 0.7, I.start + 1.2 + i * 0.7) * (1 - seg(t, I.end, I.end + 0.4));
        if (!vo) text(ctx, l, W / 2, 1290 + i * 92, { size: 74, alpha: la, color: i ? '#fff' : YELLOW, stroke: 12 });
      });
      const ra = seg(t, I.start + 2.4, I.start + 2.8) * (1 - seg(t, I.end, I.end + 0.4));
      if (ra > 0) chip(ctx, I.rule, W / 2, 760, { alpha: ra, size: 32, bg: YELLOW, color: '#14161a', h: 66 });
    }

    // ---- Bauschritte ----
    const caps = ep.captions || [];
    caps.forEach((c, idx) => {
      if (t < c.start - 0.05 || t > c.end + 0.25) return;
      const a = seg(t, c.start, c.start + 0.25) * (1 - seg(t, c.end - 0.1, c.end + 0.2));
      const stepLabel = `SCHRITT ${idx + 1}/${caps.length}`;
      if (vo) {
        chip(ctx, `${stepLabel} · ${c.text}`, W / 2, 344, { alpha: a, size: 28, h: 56, accent: YELLOW });
        return;
      }
      const pop = lerp(0.86, 1, easeOutBack(seg(t, c.start, c.start + 0.35)));
      ctx.save();
      ctx.translate(W / 2, 1300);
      ctx.scale(pop, pop);
      ctx.globalAlpha = a;
      chip(ctx, stepLabel, 0, -108, { size: 30, bg: YELLOW, color: '#14161a', h: 56 });
      const font = `72px ${TITLE}`;
      const lines = wrap(ctx, c.text, 900, font);
      lines.forEach((l, i) => text(ctx, l, 0, i * 84, { size: 72, stroke: 12 }));
      // Unterzeile (z. B. Fundamente / Wände / Dächer), läuft je Kamera-Abschnitt durch
      if (c.sub && c.heroes) {
        const h = c.heroes.find((x) => t >= x.from && t < x.to) || c.heroes.at(-1);
        const local = clamp((t - h.start) / (h.end - h.start));
        let cur = c.sub[0];
        for (const s of c.sub) if (local >= s.at) cur = s;
        text(ctx, cur.text, 0, lines.length * 84 + 14, { size: 40, font: BODY, weight: '800', color: YELLOW, stroke: 8, spacing: 2 });
      }
      ctx.restore();
    });

    // ---- Preisschilder beim Fertigstellen ----
    for (const to of ep.toasts || []) {
      if (t < to.at || t > to.at + 2.2) continue;
      const a = seg(t, to.at, to.at + 0.2) * (1 - seg(t, to.at + 1.8, to.at + 2.2));
      const y = lerp(520, 470, easeOut(seg(t, to.at, to.at + 0.5)));
      const label = to.cost > 0 ? `✔ ${to.text} · ${formatEuro(to.cost)}` : `✔ ${to.text} FERTIG`;
      chip(ctx, label, W / 2, y, { alpha: a, size: 34, h: 70, bg: 'rgba(22,130,70,0.92)' });
    }

    // ---- Budget-Anzeige (ab Episode 2 sinnvoll) ----
    if (ep.budget > 0 && t > 1 && t < endStart) {
      const done = (ep.toasts || []).filter((x) => t >= x.at).reduce((s, x) => s + x.cost, 0);
      chip(ctx, `FOLLOWER ${formatInt(ep.followers)}  ·  VERBAUT ${formatEuro(done)}`, W / 2, 190, { size: 26, h: 50, alpha: seg(t, 1, 1.4) });
    }

    // ---- Untertitel (Voice-over) ----
    if (vo && t < endStart + 30) {
      if (!this.chunks || this.chunksFor !== vo) {
        this.chunks = subtitleChunks(vo.words);
        this.chunksFor = vo;
      }
      const off = vo.offset || 0;
      const ch = this.chunks.find((c) => t - off >= c.start - 0.04 && t - off < c.end);
      if (ch) {
        const tt = t - off;
        const pop = lerp(0.9, 1, easeOutBack(seg(tt, ch.start - 0.04, ch.start + 0.14)));
        ctx.save();
        const yBase = t > endStart ? 1500 : 1330;
        ctx.translate(W / 2, yBase);
        ctx.scale(pop, pop);
        const size = 84;
        ctx.font = `${size}px ${TITLE}`;
        const parts = ch.words.map((w) => ({ w, str: w.text.toUpperCase(), width: ctx.measureText(w.text.toUpperCase()).width }));
        const space = size * 0.28;
        // ggf. zweizeilig
        const lines = [[]];
        let lw = 0;
        for (const p of parts) {
          if (lw + p.width > 900 && lines.at(-1).length) {
            lines.push([]);
            lw = 0;
          }
          lines.at(-1).push(p);
          lw += p.width + space;
        }
        lines.forEach((ln, li) => {
          const total = ln.reduce((s, p) => s + p.width, 0) + space * (ln.length - 1);
          let x = -total / 2;
          for (const p of ln) {
            const active = tt >= p.w.start - 0.03 && tt < p.w.end + 0.08;
            const key = isKeyword(p.w.text, vo.highlights);
            const sc = active ? 1.08 : 1;
            ctx.save();
            ctx.translate(x + p.width / 2, li * 100);
            ctx.scale(sc, sc);
            text(ctx, p.str, 0, 0, { size, color: key ? YELLOW : active ? '#ffffff' : 'rgba(255,255,255,0.86)', stroke: 14 });
            ctx.restore();
            x += p.width + space;
          }
        });
        ctx.restore();
      }
    }

    // ---- Endkarte ----
    const E = ep.endCard;
    if (E && t >= E.start) {
      const a = seg(t, E.start, E.start + 0.4);
      g = ctx.createLinearGradient(0, 250, 0, 1000);
      g.addColorStop(0, 'rgba(0,0,0,0)');
      g.addColorStop(0.5, `rgba(0,0,0,${0.38 * a})`);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 250, W, 750);
      const pop = lerp(1.18, 1, easeOut(seg(t, E.start, E.start + 0.5)));
      const Y0 = 470;
      ctx.save();
      ctx.translate(W / 2, Y0);
      ctx.scale(pop, pop);
      ctx.globalAlpha = a;
      const lines = wrap(ctx, E.title, 960, `118px ${TITLE}`);
      lines.forEach((l, i) => {
        const isName = /STADT\?$/.test(l) || lines.length === 1;
        text(ctx, l, 0, i * 132, { size: 118, stroke: 16, color: isName ? YELLOW : '#fff' });
      });
      ctx.restore();
      const a2 = seg(t, E.start + 0.9, E.start + 1.3);
      const sub = wrap(ctx, E.sub, 900, `800 46px ${BODY}`);
      const y0 = Y0 + lines.length * 132 + 30;
      sub.forEach((l, i) => text(ctx, l, W / 2, y0 + i * 62, { size: 46, font: BODY, weight: '800', alpha: a2, stroke: 9, spacing: 1 }));
      // pulsierender Folgen-Hinweis
      const a3 = seg(t, E.start + 1.8, E.start + 2.2);
      if (a3 > 0) {
        const pulse = 1 + 0.05 * Math.sin((t - E.start) * 6);
        ctx.save();
        ctx.translate(W / 2, y0 + sub.length * 62 + 86);
        ctx.scale(pulse, pulse);
        chip(ctx, '+ FOLGEN = + 1.000 € BAU-BUDGET', 0, 0, { alpha: a3, size: 34, h: 76, bg: '#e11d48' });
        ctx.restore();
      }
    }

    // ---- Übergänge ----
    for (const s of ep.shots || []) {
      if (!s.in || s.in === 'cut') continue;
      const dt = t - s.start;
      if (s.in === 'flash' && dt >= -0.1 && dt < 0.35) {
        const a = dt < 0 ? seg(dt, -0.1, 0) * 0.6 : (1 - seg(dt, 0, 0.35)) * 0.6;
        ctx.fillStyle = `rgba(255,255,255,${a})`;
        ctx.fillRect(0, 0, W, H);
      }
      if (s.in === 'whip' && dt >= -0.12 && dt < 0.2) {
        const a = dt < 0 ? seg(dt, -0.12, 0) * 0.45 : (1 - seg(dt, 0, 0.2)) * 0.45;
        ctx.fillStyle = `rgba(10,12,16,${a})`;
        ctx.fillRect(0, 0, W, H);
      }
    }
    // Auf-/Abblende
    const fade = Math.max(1 - seg(t, 0, 0.5), seg(t, ep.duration - 0.35, ep.duration));
    if (fade > 0) {
      ctx.fillStyle = `rgba(0,0,0,${fade})`;
      ctx.fillRect(0, 0, W, H);
    }
    ctx.restore();
  }
}
