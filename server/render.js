// Rendert eine Episode: Frames (Three.js im Headless-Browser) -> Tonspur -> fertiges MP4 (1080×1920, 30 FPS).
// Aufruf: node server/render.js <episode> [--draft] [--workers N]
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createApp, listen, ROOT, readState, writeState, getEpisode, episodeDir, loadVoiceover } from './app.js';
import { makeEpisode } from '../web/engine/director.js';
import { makeMusic, makeSfx, writeWav } from './audio.js';
import { pad3 } from '../web/engine/util.js';

const require = createRequire(import.meta.url);

function loadPlaywright() {
  try {
    return require('playwright');
  } catch {
    throw new Error('Playwright fehlt. Bitte einmalig ausführen: npm i -D playwright && npx playwright install chromium');
  }
}

function run(cmd, args) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let err = '';
    p.stderr.on('data', (d) => (err = (err + d).slice(-4000)));
    p.on('error', reject);
    p.on('close', (c) => (c === 0 ? resolve() : reject(new Error(`${cmd} fehlgeschlagen (${c}): ${err}`))));
  });
}

export async function renderEpisode({ number, draft = false, workers = null, range = null, onProgress = () => {} }) {
  const state = readState();
  const finalized = (state.episodesRendered || 0) >= number;
  const dir = episodeDir(number);
  fs.mkdirSync(dir, { recursive: true });
  fs.mkdirSync(path.join(ROOT, 'output'), { recursive: true });

  // Timeline: für bereits veröffentlichte Episoden die gespeicherte verwenden, sonst aus dem aktuellen Stand erzeugen
  // Die Timeline wird deterministisch aus dem gespeicherten Stadtzustand erzeugt (bereits gebaute Teile ändern sich nie)
  // und zusammen mit allen Kamerapositionen in episodes/NNN/episode.json abgelegt.
  const epFile = path.join(dir, 'episode.json');
  const rec = state.episodes.find((e) => e.number === number);
  const ep = makeEpisode(state, number, { followers: finalized && rec ? rec.followers : state.followers, ...loadVoiceover(number) });
  fs.writeFileSync(epFile, JSON.stringify(ep, null, 1));
  const W = draft ? 540 : ep.width, H = draft ? 960 : ep.height, fps = draft ? 15 : ep.fps;
  // range = [von, bis] in Sekunden: nur einen Ausschnitt rendern (Testzwecke, ändert den Stadtzustand nicht)
  const f0 = range ? Math.round(range[0] * fps) : 0, f1 = range ? Math.round(range[1] * fps) : Math.round(ep.duration * fps);
  const total = f1 - f0;
  const frames = fs.mkdtempSync(path.join(os.tmpdir(), `stadt_ep${pad3(number)}_`));
  const app = createApp();
  const port = await listen(app);
  const { chromium } = loadPlaywright();
  const N = workers || Math.max(1, Math.min(2, os.cpus().length - 1));
  let done = 0;
  const t0 = Date.now();
  onProgress({ stage: 'frames', done: 0, total });

  try {
    await Promise.all(Array.from({ length: N }, async (_, w) => {
      const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-dev-shm-usage'] });
      try {
        const page = await browser.newPage();
        page.on('pageerror', (e) => console.error('[Seite]', e.message));
        await page.goto(`http://127.0.0.1:${port}/render.html?episode=${number}&w=${W}&h=${H}`);
        await page.evaluate(() => window.ready);
        // zusammenhängender Block je Worker (Tageszeit ändert sich stetig -> weniger Neuberechnung)
        const from = f0 + Math.floor((total * w) / N), to = f0 + Math.floor((total * (w + 1)) / N);
        for (let i = from; i < to; i++) {
          const b64 = await page.evaluate(([t, q]) => window.frame(t, q), [i / fps, draft ? 0.85 : 0.95]);
          fs.writeFileSync(path.join(frames, `f_${String(i - f0).padStart(5, '0')}.jpg`), Buffer.from(b64, 'base64'));
          done++;
          if (done % 5 === 0 || done === total) onProgress({ stage: 'frames', done, total, fps: done / ((Date.now() - t0) / 1000) });
        }
      } finally {
        await browser.close();
      }
    }));
  } finally {
    app.close();
  }

  // ---- Ton ----
  onProgress({ stage: 'audio', done: total, total });
  const music = path.join(frames, 'music.wav'), sfx = path.join(frames, 'sfx.wav');
  writeWav(music, makeMusic(ep));
  writeWav(sfx, makeSfx(ep, state));
  const vo = ep.voiceover?.audio ? path.join(ROOT, ep.voiceover.audio) : null;
  const hasVo = vo && fs.existsSync(vo);

  // ---- Schnitt / Encoding ----
  onProgress({ stage: 'encode', done: total, total });
  const name = `episode_${pad3(number)}${draft ? '_draft' : ''}${range ? '_ausschnitt' : ''}`;
  const out = path.join(ROOT, 'output', name + '.mp4');
  const ss = ['-ss', String(f0 / fps)];
  const args = ['-y', '-framerate', String(fps), '-i', path.join(frames, 'f_%05d.jpg'), ...ss, '-i', music, ...ss, '-i', sfx];
  let filter;
  if (hasVo) {
    args.push(...ss, '-i', vo);
    const delay = Math.round((ep.voiceover.offset || 0) * 1000);
    // Musik weicht der Stimme aus (Ducking)
    filter = `[3:a]aresample=44100,adelay=${delay}|${delay},volume=1.6,asplit=2[vo][sc];[1:a]volume=0.5[m];[m][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[md];[2:a]volume=0.6[s];[md][s][vo]amix=inputs=3:normalize=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[a]`;
  } else {
    filter = `[1:a]volume=0.75[m];[2:a]volume=1.0[s];[m][s]amix=inputs=2:normalize=0,alimiter=limit=0.95,loudnorm=I=-15:TP=-1.5:LRA=11[a]`;
  }
  args.push('-filter_complex', filter, '-map', '0:v', '-map', '[a]', '-t', String(total / fps),
    '-c:v', 'libx264', '-preset', draft ? 'veryfast' : 'slow', '-crf', draft ? '24' : '19', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-r', String(fps), '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-movflags', '+faststart', out);
  await run('ffmpeg', args);

  // Titelbild (letzte Einstellung mit Endkarte)
  const cover = path.join(ROOT, 'output', name + '_cover.jpg');
  fs.copyFileSync(path.join(frames, `f_${String(Math.max(0, total - 1 - Math.round(2 * fps))).padStart(5, '0')}.jpg`), cover);
  fs.rmSync(frames, { recursive: true, force: true });

  // ---- Stadtzustand fortschreiben (nur bei finalem Render) ----
  if (!draft && !range) {
    const s = readState();
    const ids = [...s.roads, ...s.items].filter((o) => (o.episode ?? 1) === number).map((o) => o.id);
    const rec = { number, title: ep.title, followers: ep.followers, built: ids, video: `output/${name}.mp4`, cover: `output/${name}_cover.jpg`, renderedAt: new Date().toISOString() };
    s.episodes = s.episodes.filter((e) => e.number !== number).concat(rec).sort((a, b) => a.number - b.number);
    s.episodesRendered = Math.max(s.episodesRendered || 0, number);
    s.cameras = { ...s.cameras, final_aerial: ep.finalCamera };
    writeState(s);
    fs.mkdirSync(path.join(ROOT, 'city/history'), { recursive: true });
    fs.writeFileSync(path.join(ROOT, 'city/history', `state_after_ep_${pad3(number)}.json`), JSON.stringify(s, null, 1));
  }
  const seconds = Math.round((Date.now() - t0) / 1000);
  onProgress({ stage: 'done', done: total, total, file: `output/${name}.mp4`, seconds });
  return { file: out, seconds, voiceover: !!hasVo };
}

// Kommandozeile
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const number = Number(process.argv[2]);
  if (!number) {
    console.error('Aufruf: node server/render.js <episode> [--draft] [--workers N]');
    process.exit(1);
  }
  const wi = process.argv.indexOf('--workers'), ri = process.argv.indexOf('--range');
  renderEpisode({ number, draft: process.argv.includes('--draft'), workers: wi > 0 ? Number(process.argv[wi + 1]) : null, range: ri > 0 ? process.argv[ri + 1].split(':').map(Number) : null, onProgress: (p) => console.log(JSON.stringify(p)) })
    .then((r) => console.log(JSON.stringify({ stage: 'finished', ...r })))
    .catch((e) => {
      console.log(JSON.stringify({ stage: 'error', error: e.message }));
      process.exit(1);
    });
}
