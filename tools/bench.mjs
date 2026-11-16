// Misst die Renderzeit pro Frame: node tools/bench.mjs [w h]
import { createRequire } from 'node:module';
import { createApp, listen } from '../server/app.js';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const [w, h] = [process.argv[2] || 1080, process.argv[3] || 1920];
const app = createApp();
const port = await listen(app);
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${port}/render.html?episode=1&w=${w}&h=${h}`);
await page.evaluate(() => window.ready);
const res = await page.evaluate(() => {
  const out = {};
  const info = window.player.renderer.info;
  for (const t of [3, 12, 30, 44, 57]) {
    window.frame(t);
    const a = performance.now();
    for (let i = 1; i <= 3; i++) window.player.renderAt(t + i / 30);
    const b = performance.now();
    for (let i = 4; i <= 6; i++) window.frame(t + i / 30);
    const c = performance.now();
    out[t] = { render_ms: Math.round((b - a) / 3), with_jpeg_ms: Math.round((c - b) / 3), tris: info.render.triangles, calls: info.render.calls };
  }
  return out;
});
console.table(res);
await browser.close();
app.close();
