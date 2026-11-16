// Startet das Dashboard: npm start  ->  http://localhost:5173
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createApp, listen, ROOT } from './app.js';

let job = null;

function startRender({ number, draft }) {
  job = { status: 'running', number, draft, stage: 'start', done: 0, total: 0, startedAt: Date.now(), log: [] };
  const args = [path.join(ROOT, 'server/render.js'), String(number)];
  if (draft) args.push('--draft');
  const child = spawn(process.execPath, args, { cwd: ROOT });
  let buf = '';
  const current = job;
  child.stdout.on('data', (d) => {
    buf += d;
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i);
      buf = buf.slice(i + 1);
      try {
        const p = JSON.parse(line);
        Object.assign(current, p);
        if (p.stage === 'finished') current.status = 'done';
        if (p.stage === 'error') current.status = 'error';
      } catch {
        /* keine JSON-Zeile */
      }
    }
  });
  child.stderr.on('data', (d) => current.log.push(String(d).slice(0, 500)) && current.log.splice(0, current.log.length - 20));
  child.on('close', (code) => {
    if (current.status === 'running') {
      current.status = code === 0 ? 'done' : 'error';
      if (code !== 0 && !current.error) current.error = 'Render-Prozess beendet (Code ' + code + '). ' + current.log.slice(-3).join(' ');
    }
    current.finishedAt = Date.now();
  });
  return job;
}

const app = createApp({ startRender, getJob: () => job });
const port = await listen(app, Number(process.env.PORT) || 5173);
console.log(`AUSLÄNDERSTADT Dashboard läuft: http://localhost:${port}`);
