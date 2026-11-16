// HTTP-Server: liefert Dashboard + Engine aus und stellt die Stadt-API bereit.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { makeEpisode } from '../web/engine/director.js';
import { autoPlan, budgetOf, commitEntries, addCustom, removePending, pendingEpisode, milestoneStatus, remainingPlan } from '../web/engine/planner.js';
import { itemCost } from '../web/engine/catalog.js';
import { pad3 } from '../web/engine/util.js';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const P = (...a) => path.join(ROOT, ...a);
// CITY_STATE erlaubt Tests mit einer Kopie, ohne die echte Stadt anzufassen
const STATE = process.env.CITY_STATE || P('city/state.json');

export const readJSON = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));
export const readState = () => readJSON(STATE);
export function writeState(state) {
  fs.writeFileSync(STATE + '.tmp', JSON.stringify(state, null, 1));
  fs.renameSync(STATE + '.tmp', STATE);
}
export const readMasterplan = () => readJSON(P('city/masterplan.json'));
export const episodeDir = (n) => P('episodes', pad3(n));

// Episode laden (gespeicherte Timeline) oder aus dem aktuellen Stand erzeugen
export function getEpisode(n, { fresh = false } = {}) {
  const f = path.join(episodeDir(n), 'episode.json');
  const state = readState();
  if (!fresh && fs.existsSync(f)) return readJSON(f);
  const rec = state.episodes.find((e) => e.number === n);
  const ep = makeEpisode(state, n, { followers: rec ? rec.followers : state.followers, ...loadVoiceover(n) });
  return ep;
}

// Voice-over (falls vorhanden): episodes/NNN/voiceover.json = {audio, words:[{text,start,end}], highlights, cues}
export function loadVoiceover(n) {
  const f = path.join(episodeDir(n), 'voiceover.json');
  if (!fs.existsSync(f)) return {};
  const vo = readJSON(f);
  return { voiceover: { audio: vo.audio, words: vo.words, highlights: vo.highlights || [], offset: vo.offset || 0 }, cues: vo.cues || undefined, duration: vo.duration || undefined };
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.png': 'image/png', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.svg': 'image/svg+xml' };

const MOUNTS = [
  ['/vendor/three/', P('node_modules/three/')],
  ['/vendor/fonts/anton/', P('node_modules/@fontsource/anton/')],
  ['/vendor/fonts/inter/', P('node_modules/@fontsource/inter/')],
  ['/output/', P('output/')],
  ['/episodes/', P('episodes/')],
  ['/', P('web/')],
];

function serveFile(req, res, file) {
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) {
      res.writeHead(404).end('Nicht gefunden');
      return;
    }
    const type = MIME[path.extname(file)] || 'application/octet-stream';
    const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
    if (range) {
      const start = range[1] ? +range[1] : 0, end = range[2] ? +range[2] : st.size - 1;
      res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${st.size}`, 'Accept-Ranges': 'bytes', 'Content-Length': end - start + 1 });
      fs.createReadStream(file, { start, end }).pipe(res);
    } else {
      res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
      fs.createReadStream(file).pipe(res);
    }
  });
}

function body(req) {
  return new Promise((resolve, reject) => {
    let s = '';
    req.on('data', (c) => {
      s += c;
      if (s.length > 2e6) reject(new Error('Anfrage zu groß'));
    });
    req.on('end', () => {
      try {
        resolve(s ? JSON.parse(s) : {});
      } catch (e) {
        reject(new Error('Ungültiges JSON'));
      }
    });
  });
}

function summary(state) {
  const mp = readMasterplan();
  const plan = autoPlan(state, mp);
  const ep = pendingEpisode(state);
  const pending = [...state.roads, ...state.items].filter((o) => (o.episode ?? 1) === ep);
  return {
    state,
    budget: budgetOf(state),
    pendingEpisode: ep,
    pending: pending.filter((o) => !o.auto).map((o) => ({ id: o.id, type: o.type, name: o.name, cost: itemCost(o) })),
    pendingCount: pending.length,
    plan: { queue: plan.queue.map((e) => ({ id: e.id, type: e.type, name: e.name, cost: itemCost(e), milestone: e.milestone })), cost: plan.cost, left: plan.left, next: plan.next && { id: plan.next.entry.id, type: plan.next.entry.type, name: plan.next.entry.name, cost: itemCost(plan.next.entry), missing: plan.next.missing, followersNeeded: plan.next.followersNeeded } },
    milestones: milestoneStatus(state, mp),
    remaining: remainingPlan(state, mp).map((e) => ({ id: e.id, type: e.type, name: e.name, cost: itemCost(e), milestone: e.milestone })),
    outputs: listOutputs(),
  };
}

export function listOutputs() {
  const dir = P('output');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith('.mp4')).sort().map((f) => {
    const st = fs.statSync(path.join(dir, f));
    return { file: f, url: '/output/' + f, size: st.size, mtime: st.mtimeMs };
  });
}

// jobs: wird von server.js mit dem Renderer verbunden
export function createApp({ startRender = null, getJob = () => null } = {}) {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    const json = (o, code = 200) => {
      res.writeHead(code, { 'Content-Type': MIME['.json'], 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(o));
    };
    try {
      if (url.pathname.startsWith('/api/')) {
        const route = req.method + ' ' + url.pathname;
        if (route === 'GET /api/state') return json(readState());
        if (route === 'GET /api/summary') return json(summary(readState()));
        if (route === 'GET /api/masterplan') return json(readMasterplan());
        if (req.method === 'GET' && url.pathname.startsWith('/api/episode/')) return json(getEpisode(+url.pathname.split('/').pop(), { fresh: url.searchParams.has('fresh') }));
        if (route === 'GET /api/render/status') return json(getJob() || { status: 'idle' });
        if (req.method !== 'POST') return json({ error: 'Unbekannte Route' }, 404);
        const b = await body(req);
        const state = readState();
        if (route === 'POST /api/followers') {
          const f = Math.floor(Number(b.followers));
          if (!Number.isFinite(f) || f < 0 || f > 1e9) return json({ error: 'Bitte eine gültige Followerzahl eingeben.' }, 400);
          state.followers = f;
          writeState(state);
          return json(summary(state));
        }
        if (route === 'POST /api/plan/commit') {
          // ohne ids: alles, was das Budget laut Masterplan hergibt; mit ids: nur diese (z. B. ein Stadtteil)
          const mp = readMasterplan();
          let entries = autoPlan(state, mp).queue;
          if (Array.isArray(b.ids)) {
            const want = new Set(b.ids);
            entries = remainingPlan(state, mp).filter((e) => want.has(e.id));
            const cost = entries.reduce((s, e) => s + itemCost(e), 0);
            const avail = budgetOf(state).available;
            if (cost > avail) return json({ error: `Budget reicht nicht: ${cost.toLocaleString('de-DE')} € nötig, ${avail.toLocaleString('de-DE')} € verfügbar.` }, 400);
          }
          if (!entries.length) return json({ error: 'Mit dem aktuellen Budget kann nichts Neues gebaut werden.' }, 400);
          const added = commitEntries(state, entries);
          writeState(state);
          return json({ added, ...summary(state) });
        }
        if (route === 'POST /api/build/custom') {
          const r = addCustom(state, b);
          if (!r.ok) return json({ error: r.error }, 400);
          writeState(state);
          return json({ item: r.item, ...summary(state) });
        }
        if (route === 'POST /api/pending/remove') {
          const n = removePending(state, b.id || null);
          writeState(state);
          return json({ removed: n, ...summary(state) });
        }
        if (route === 'POST /api/restore') {
          // letzten fertig gerenderten Baufortschritt laden (verwirft geplante, noch nicht gerenderte Bauten)
          const snap = P('city/history', `state_after_ep_${pad3(state.episodesRendered || 0)}.json`);
          if (state.episodesRendered && fs.existsSync(snap)) {
            const s = readJSON(snap);
            s.followers = state.followers;
            writeState(s);
            return json({ restored: path.basename(snap), ...summary(s) });
          }
          // noch keine Episode gerendert: Gründungsdorf (Startkapital) behalten, nur zusätzlich Geplantes verwerfen
          const founding = (o) => itemCost(o) === 0 && !o.custom && !o.auto;
          const before = state.roads.length + state.items.length;
          if (state.episodesRendered) removePending(state, null);
          else {
            state.roads = state.roads.filter(founding);
            state.items = state.items.filter(founding);
          }
          writeState(state);
          return json({ restored: 'letzter fertiger Stand', removed: before - state.roads.length - state.items.length, ...summary(state) });
        }
        if (route === 'POST /api/render') {
          if (!startRender) return json({ error: 'Renderer nicht verfügbar.' }, 500);
          const job = getJob();
          if (job && job.status === 'running') return json({ error: 'Es läuft bereits ein Render-Vorgang.' }, 409);
          const n = Number(b.episode) || pendingEpisode(state);
          const has = [...state.roads, ...state.items].some((o) => (o.episode ?? 1) === n);
          if (!has) return json({ error: `Für Episode ${pad3(n)} ist noch nichts geplant. Erst Gebäude hinzufügen.` }, 400);
          return json(startRender({ number: n, draft: !!b.draft }));
        }
        return json({ error: 'Unbekannte Route' }, 404);
      }
      let pth = decodeURIComponent(url.pathname);
      if (pth === '/') pth = '/index.html';
      for (const [prefix, dir] of MOUNTS) {
        if (pth.startsWith(prefix)) {
          const file = path.join(dir, pth.slice(prefix.length));
          if (!file.startsWith(dir)) break;
          return serveFile(req, res, file);
        }
      }
      res.writeHead(404).end('Nicht gefunden');
    } catch (e) {
      json({ error: e.message }, 500);
    }
  });
}

export function listen(app, port = 0) {
  return new Promise((resolve) => app.listen(port, '0.0.0.0', () => resolve(app.address().port)));
}
