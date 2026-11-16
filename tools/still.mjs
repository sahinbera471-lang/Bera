// Standbild(er) der Stadt rendern: node tools/still.mjs out.jpg [--episode N --t 12.5] [--pos x,y,z --look x,y,z --tod 0.2] [--w 540 --h 960]
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { createApp, listen } from '../server/app.js';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const arg = (k, d) => { const eq = process.argv.find((a) => a.startsWith('--' + k + '=')); if (eq) return eq.slice(k.length + 3); const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const out = process.argv[2] || 'still.jpg';
const app = createApp();
const port = await listen(app);
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage();
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[browser]', m.text()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
const ep = arg('episode');
const t0 = Date.now();
await page.goto(`http://127.0.0.1:${port}/render.html?w=${arg('w', 1080)}&h=${arg('h', 1920)}${ep ? '&episode=' + ep : ''}`);
await page.evaluate(() => window.ready);
console.log('Szene geladen in', Date.now() - t0, 'ms');
const times = ep ? String(arg('t', '0')).split(',').map(Number) : [null];
for (const t of times) {
  const t1 = Date.now();
  const b64 = ep
    ? await page.evaluate((t) => window.frame(t), t)
    : await page.evaluate(([p, l, f, tod]) => window.still(p, l, f, tod), [arg('pos', '120,90,170').split(',').map(Number), arg('look', '0,0,0').split(',').map(Number), +arg('fov', 42), +arg('tod', 0.15)]);
  const f = times.length > 1 ? out.replace(/(\.\w+)$/, `_${String(t).replace('.', '_')}$1`) : out;
  fs.writeFileSync(f, Buffer.from(b64, 'base64'));
  console.log(f, Date.now() - t1, 'ms');
}
await browser.close();
app.close();
