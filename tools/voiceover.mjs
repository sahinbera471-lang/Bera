// Voice-over in eine Episode einbinden.
//   node tools/voiceover.mjs <episode> --audio datei.mp3 --words timing.json [--highlights "WORT1,WORT2"] [--offset 0.3]
// timing.json: Wort-Zeitstempel aus ElevenLabs (Transkript {words:[{text,start,end}]}, Alignment
// {characters, character_start_times_seconds, character_end_times_seconds}) oder ein Array [{text,start,end}].
// Der gesprochene Text wird NICHT verändert – es werden nur Zeitpunkte übernommen.
// Szenenwechsel werden automatisch auf die nächstgelegenen Satzanfänge gelegt.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, readState, episodeDir } from '../server/app.js';
import { makeEpisode } from '../web/engine/director.js';
import { pad3 } from '../web/engine/util.js';

const arg = (k, d = null) => {
  const i = process.argv.indexOf('--' + k);
  return i > 0 ? process.argv[i + 1] : d;
};
const n = Number(process.argv[2]);
const audio = arg('audio'), wordsFile = arg('words');
if (!n || !audio || !wordsFile) {
  console.error('Aufruf: node tools/voiceover.mjs <episode> --audio datei.mp3 --words timing.json [--highlights "A,B"] [--offset 0.3]');
  process.exit(1);
}

export function toWords(raw) {
  if (Array.isArray(raw)) return raw.map((w) => ({ text: w.text ?? w.word, start: +w.start, end: +w.end }));
  if (raw.words) return raw.words.filter((w) => (w.type ?? 'word') === 'word').map((w) => ({ text: w.text ?? w.word, start: +w.start, end: +w.end }));
  const al = raw.alignment || raw.normalized_alignment || raw;
  if (al.characters) {
    const out = [];
    let cur = null;
    al.characters.forEach((ch, i) => {
      const s = al.character_start_times_seconds[i], e = al.character_end_times_seconds[i];
      if (/\s/.test(ch)) {
        if (cur) out.push(cur);
        cur = null;
      } else if (!cur) cur = { text: ch, start: s, end: e };
      else {
        cur.text += ch;
        cur.end = e;
      }
    });
    if (cur) out.push(cur);
    return out;
  }
  throw new Error('Unbekanntes Timing-Format.');
}

const words = toWords(JSON.parse(fs.readFileSync(wordsFile, 'utf8'))).filter((w) => w.text && w.text.trim());
const offset = Number(arg('offset', 0.3));
const dir = episodeDir(n);
fs.mkdirSync(dir, { recursive: true });
const ext = path.extname(audio) || '.mp3';
const dest = path.join(dir, 'voiceover' + ext);
if (path.resolve(audio) !== dest) fs.copyFileSync(audio, dest);

// Satzanfänge
const sentences = [];
let startNew = true;
for (const w of words) {
  if (startNew) sentences.push(w.start + offset);
  startNew = /[.!?…]["»”]?$/.test(w.text);
}
// Standard-Timeline holen und Phasenwechsel auf Satzanfänge einrasten (max. ±3,5 s)
const state = readState();
const base = makeEpisode(state, n, {});
const cues = {};
const used = new Set();
for (const [k, t] of Object.entries(base.phases)) {
  let best = null;
  for (const s of sentences) if (!used.has(s) && Math.abs(s - t) <= 3.5 && (best == null || Math.abs(s - t) < Math.abs(best - t))) best = s;
  if (best != null) {
    used.add(best);
    cues[k] = Math.round(best * 10) / 10;
  }
}
const last = words.at(-1).end + offset;
if (last > base.duration) console.warn(`Achtung: Das Voice-over endet bei ${last.toFixed(1)} s und ist länger als die Episode (${base.duration} s).`);
const highlights = (arg('highlights', '') || '').split(',').map((s) => s.trim()).filter(Boolean);
if (!highlights.length) highlights.push(state.name, 'Follower', 'Stadt', 'Budget', 'Euro');
const vo = { audio: path.relative(ROOT, dest), offset, words, highlights, cues };
fs.writeFileSync(path.join(dir, 'voiceover.json'), JSON.stringify(vo, null, 1));
console.log(`Voice-over für Episode ${pad3(n)} eingebunden: ${words.length} Wörter, ${sentences.length} Sätze, Ende bei ${last.toFixed(1)} s.`);
console.log('Szenenwechsel (Sekunden):', cues);
