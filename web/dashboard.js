// Dashboard-Logik: Live-3D-Vorschau + Steuerung der Stadt über die Server-API.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Player, loadFonts } from '/engine/player.js';
import { CATALOG, footprint, itemCost } from '/engine/catalog.js';
import { collisions } from '/engine/planner.js';
import { finalAerial } from '/engine/director.js';
import { formatEuro, formatInt, pad3 } from '/engine/util.js';

const $ = (id) => document.getElementById(id);
const api = async (url, body) => {
  const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || 'Fehler');
  return j;
};
let toastTimer;
function toast(msg, err = false) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast show' + (err ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = 'toast'), err ? 5000 : 2600);
}
const label = (o) => o.name || CATALOG[o.type]?.label || o.id;

let S = null; // letzte Zusammenfassung vom Server
let player, controls;
let mode = 'free';
let episode = null, playing = false, epTime = 0, lastTs = 0;
let placing = null, ghost = null;
let dirty = true;

// ------------------------------------------------------------------ 3D
async function initView() {
  await loadFonts();
  const state = await api('/api/state');
  player = new Player({ canvas: $('view'), width: 720, height: 1280, state });
  player.setCity(state, null);
  controls = new OrbitControls(player.camera, $('view'));
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.minDistance = 15;
  controls.maxDistance = 1200;
  controls.enableDamping = true;
  controls.addEventListener('change', () => (dirty = true));
  aerial(state);
  $('loading').remove();
  requestAnimationFrame(loop);
}

function aerial(state) {
  const fa = finalAerial(state, [...state.roads, ...state.items]);
  const a = THREE.MathUtils.degToRad(fa.a1);
  player.camera.position.set(fa.center[0] + Math.cos(a) * fa.r1, fa.h1, fa.center[2] + Math.sin(a) * fa.r1);
  controls.target.set(fa.center[0], 0, fa.center[2]);
  player.camera.fov = 46;
  player.camera.updateProjectionMatrix();
  controls.update();
  dirty = true;
}

function loop(ts) {
  requestAnimationFrame(loop);
  if (mode === 'free') {
    controls.update();
    if (dirty) {
      player.look.copy(controls.target);
      player.renderFree(+$('tod').value);
      dirty = false;
    }
  } else if (episode) {
    if (playing) {
      epTime += Math.min(0.1, (ts - lastTs) / 1000);
      if (epTime >= episode.duration) {
        epTime = episode.duration;
        setPlaying(false);
      }
      $('scrub').value = epTime;
      dirty = true;
    }
    if (dirty) {
      player.renderAt(epTime);
      $('time').textContent = epTime.toFixed(1).replace('.', ',') + ' s';
      dirty = false;
    }
  }
  lastTs = ts;
}

function setPlaying(p) {
  playing = p;
  $('play').textContent = p ? '❚❚ Pause' : '▶ Abspielen';
}

async function setMode(m) {
  if (placing) cancelPlacing();
  mode = m;
  $('mode-free').classList.toggle('on', m === 'free');
  $('mode-ep').classList.toggle('on', m === 'ep');
  $('free-ctl').classList.toggle('hidden', m !== 'free');
  $('ep-ctl').classList.toggle('hidden', m !== 'ep');
  controls.enabled = m === 'free';
  const state = await api('/api/state');
  if (m === 'free') {
    setPlaying(false);
    player.setCity(state, null);
    player.camera.up.set(0, 1, 0);
    aerial(state);
  } else {
    const n = S.pendingCount ? S.pendingEpisode : Math.max(1, S.state.episodesRendered);
    episode = await api(`/api/episode/${n}${S.pendingCount ? '?fresh=1' : ''}`);
    player.setCity(state, episode);
    $('scrub').max = episode.duration;
    epTime = 0;
    $('scrub').value = 0;
    setPlaying(true);
  }
  dirty = true;
}

async function rebuildView() {
  if (!player) return;
  if (mode === 'ep') return setMode('ep');
  player.setCity(S.state, null);
  dirty = true;
}

// ------------------------------------------------------------------ Platzieren eigener Gebäude
const ray = new THREE.Raycaster(), groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
function groundPoint(ev) {
  const r = $('view').getBoundingClientRect();
  const v = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(v, player.camera);
  const p = new THREE.Vector3();
  return ray.ray.intersectPlane(groundPlane, p) ? p : null;
}
function startPlacing() {
  if (mode !== 'free') return toast('Bitte zuerst zur freien Ansicht wechseln.', true);
  const type = $('c-type').value;
  placing = { type, rot: +$('c-rot').value, name: $('c-name').value.trim() };
  const f = footprint({ type, x: 0, z: 0, rot: placing.rot });
  const geo = new THREE.BoxGeometry(f[2] - f[0], 1.2, f[3] - f[1]);
  geo.translate((f[0] + f[2]) / 2, 0.6, (f[1] + f[3]) / 2);
  ghost = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x3ecf8e, transparent: true, opacity: 0.55, depthWrite: false }));
  ghost.visible = false;
  player.scene.add(ghost);
  $('hint').style.display = 'block';
  $('hint').textContent = `${CATALOG[type].label} platzieren: auf eine freie Stelle klicken (Esc bricht ab)`;
  $('c-place').textContent = 'Platzieren abbrechen';
}
function cancelPlacing() {
  if (ghost) player.scene.remove(ghost);
  ghost = placing = null;
  $('hint').style.display = 'none';
  $('c-place').textContent = 'Auf dem Grundstück platzieren';
  dirty = true;
}
function ghostState(p) {
  const it = { id: '_ghost', type: placing.type, x: Math.round(p.x), z: Math.round(p.z), rot: placing.rot };
  const free = placing.type === 'tree' || placing.type === 'lamp' || collisions(S.state, it).length === 0;
  return { it, free: free && Math.hypot(it.x, it.z) <= 300 };
}
let downAt = null;
$('view').addEventListener('pointerdown', (e) => (downAt = [e.clientX, e.clientY]));
$('view').addEventListener('pointermove', (e) => {
  if (!placing) return;
  const p = groundPoint(e);
  if (!p) return;
  const g = ghostState(p);
  ghost.visible = true;
  ghost.position.set(g.it.x, 0, g.it.z);
  ghost.material.color.set(g.free ? 0x3ecf8e : 0xff5252);
  dirty = true;
});
$('view').addEventListener('pointerup', async (e) => {
  if (!placing || !downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 6) return; // Ziehen = Kamera drehen
  const p = groundPoint(e);
  if (!p) return;
  const g = ghostState(p);
  try {
    const r = await api('/api/build/custom', { type: placing.type, x: g.it.x, z: g.it.z, rot: placing.rot, name: placing.name });
    toast(`${label(r.item)} eingeplant (${formatEuro(itemCost(r.item))}).`);
    cancelPlacing();
    update(r);
    rebuildView();
  } catch (err) {
    toast(err.message, true);
  }
});
addEventListener('keydown', (e) => e.key === 'Escape' && placing && cancelPlacing());

// ------------------------------------------------------------------ Oberfläche
function li(html, cls = '') {
  const e = document.createElement('li');
  e.className = cls;
  e.innerHTML = html;
  return e;
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

function update(sum) {
  S = sum;
  const st = S.state, b = S.budget;
  $('st-ep').textContent = pad3(S.pendingEpisode);
  $('st-followers').textContent = formatInt(st.followers);
  $('st-budget').textContent = formatEuro(b.total);
  $('st-avail').textContent = formatEuro(b.available);
  $('st-buildings').textContent = st.items.filter((i) => i.type !== 'tree' && i.type !== 'lamp').length;
  if (document.activeElement !== $('followers')) $('followers').value = st.followers;
  $('b-total').textContent = formatEuro(b.total);
  $('b-spent').textContent = formatEuro(b.spent);
  $('b-avail').textContent = formatEuro(b.available);
  $('b-avail').className = b.available >= 0 ? 'ok' : 'bad';

  // automatische Planung
  const plan = $('plan');
  plan.replaceChildren();
  if (!S.plan.queue.length) plan.append(li('Mit dem aktuellen Budget ist nichts Neues aus dem Masterplan möglich.', 'empty'));
  for (const e of S.plan.queue) plan.append(li(`<span>${esc(label(e))}</span><span class="c">${formatEuro(e.cost)}</span>`));
  $('plan-commit').disabled = !S.plan.queue.length;
  $('plan-commit').textContent = S.plan.queue.length ? `Alles einplanen (${formatEuro(S.plan.cost)})` : 'Alles einplanen';
  const nx = S.plan.next;
  $('plan-next').textContent = nx ? `Als Nächstes: ${label(nx)} (${formatEuro(nx.cost)}) – es fehlen ${formatEuro(nx.missing)} = ${formatInt(nx.followersNeeded)} Follower.` : S.remaining.length ? '' : 'Der komplette Masterplan ist gebaut.';

  // Meilensteine
  const ms = $('milestones');
  ms.replaceChildren();
  for (const m of S.milestones) {
    const done = m.built === m.total;
    const can = !done && m.restCost <= b.available;
    const e = li(`<div class="top"><b>${formatInt(m.followers)} Follower</b><span class="${done ? 'done' : 'c'}">${done ? '✔ gebaut' : `${m.built}/${m.total} · noch ${formatEuro(m.restCost)}`}</span></div><div>${esc(m.text)}</div><div class="prog"><i style="width:${(100 * m.built) / m.total}%"></i></div>`);
    if (!done) {
      const btn = document.createElement('button');
      btn.className = 'small';
      btn.textContent = can ? 'Stadtteil bauen' : 'Budget reicht noch nicht';
      btn.disabled = !can;
      btn.onclick = () => act('/api/plan/commit', { ids: S.remaining.filter((r) => r.milestone === m.followers).map((r) => r.id) }, 'Stadtteil eingeplant.');
      e.append(btn);
    }
    ms.append(e);
  }

  // geplante Bauten
  $('p-ep').textContent = `Episode ${pad3(S.pendingEpisode)}`;
  const pe = $('pending');
  pe.replaceChildren();
  if (!S.pending.length) pe.append(li('Noch nichts geplant.', 'empty'));
  for (const p of S.pending) {
    if (p.type === 'tree' || p.type === 'lamp') continue;
    const e = li(`<span>${esc(label(p))}</span><span class="c">${p.cost ? formatEuro(p.cost) : 'Startkapital'}</span>`);
    if (st.episodesRendered > 0 || p.cost > 0) {
      const btn = document.createElement('button');
      btn.className = 'small ghost';
      btn.textContent = '✕';
      btn.title = 'Aus der Planung entfernen';
      btn.onclick = () => act('/api/pending/remove', { id: p.id }, 'Entfernt.');
      e.append(btn);
    }
    pe.append(e);
  }
  const props = S.pendingCount - S.pending.filter((p) => p.type !== 'tree' && p.type !== 'lamp').length;
  if (props > 0) pe.append(li(`+ ${props} Bäume / Laternen`, 'empty'));

  $('r-final').disabled = $('r-draft').disabled = S.pendingCount === 0 && st.episodesRendered === 0;
  $('r-final').textContent = S.pendingCount ? `Episode ${pad3(S.pendingEpisode)} rendern (MP4)` : `Episode ${pad3(st.episodesRendered)} neu rendern`;

  // fertige Videos
  const out = $('outputs');
  out.replaceChildren();
  if (!S.outputs.length) out.append(li('Noch kein Video gerendert.', 'empty'));
  for (const o of S.outputs) {
    const e = li(`<span>${esc(o.file)} <span class="c">· ${(o.size / 1e6).toFixed(1)} MB</span></span>`);
    const play = document.createElement('button');
    play.className = 'small';
    play.textContent = 'Ansehen';
    play.onclick = () => {
      const v = $('player');
      v.classList.remove('hidden');
      v.src = o.url + '?t=' + Math.round(o.mtime);
      v.play();
    };
    const dl = document.createElement('a');
    dl.href = o.url;
    dl.download = o.file;
    dl.innerHTML = '<button class="small primary">MP4 exportieren</button>';
    e.append(play, dl);
    out.append(e);
  }
}

async function act(url, body, okMsg) {
  try {
    const r = await api(url, body);
    update(r);
    if (okMsg) toast(okMsg);
    await rebuildView();
  } catch (e) {
    toast(e.message, true);
  }
}

$('f-followers').addEventListener('submit', (e) => {
  e.preventDefault();
  act('/api/followers', { followers: $('followers').value }, 'Followerstand übernommen – Budget neu berechnet.');
});
$('plan-commit').onclick = () => act('/api/plan/commit', {}, 'Bauten für die nächste Episode eingeplant.');
$('restore').onclick = () => confirm('Alle geplanten, noch nicht gerenderten Bauten verwerfen und den letzten fertigen Stand laden?') && act('/api/restore', {}, 'Letzter Baufortschritt geladen.');
$('c-place').onclick = () => (placing ? cancelPlacing() : startPlacing());
$('mode-free').onclick = () => setMode('free');
$('mode-ep').onclick = () => setMode('ep');
$('tod').oninput = () => (dirty = true);
$('cam-aerial').onclick = () => aerial(S.state);
$('play').onclick = () => {
  if (!playing && epTime >= episode.duration - 0.05) epTime = 0;
  setPlaying(!playing);
};
$('scrub').oninput = () => {
  epTime = +$('scrub').value;
  setPlaying(false);
  dirty = true;
};

for (const [k, c] of Object.entries(CATALOG)) {
  if (k === 'road') continue;
  const o = document.createElement('option');
  o.value = k;
  o.textContent = `${c.label} – ${formatEuro(c.cost)}`;
  $('c-type').append(o);
}
$('c-type').onchange = () => {
  const c = CATALOG[$('c-type').value];
  $('c-info').textContent = `Grundfläche ca. ${c.lot[0]} × ${c.lot[1]} m · Kosten ${formatEuro(c.cost)}`;
};
$('c-type').onchange();

// ------------------------------------------------------------------ Rendern
const STAGE = { start: 'Renderer startet …', frames: 'Bilder werden gerendert', audio: 'Tonspur wird erzeugt', encode: 'Video wird geschnitten und kodiert', done: 'Fertig', finished: 'Fertig' };
let polling = false;
async function startRender(draft) {
  try {
    await api('/api/render', { draft });
    toast(draft ? 'Entwurf wird gerendert …' : 'Episode wird gerendert – das dauert einige Minuten.');
    poll();
  } catch (e) {
    toast(e.message, true);
  }
}
async function poll() {
  if (polling) return;
  polling = true;
  for (;;) {
    const j = await api('/api/render/status').catch(() => ({ status: 'idle' }));
    if (j.status === 'idle') break;
    const pct = j.total ? (100 * j.done) / j.total : 0;
    $('r-bar').style.width = (j.status === 'done' ? 100 : pct * 0.96) + '%';
    const eta = j.fps && j.stage === 'frames' ? ` · noch ca. ${Math.ceil((j.total - j.done) / j.fps / 60)} min` : '';
    $('r-status').textContent = j.status === 'error' ? 'Fehler: ' + j.error : j.status === 'done' ? `Episode ${pad3(j.number)}${j.draft ? ' (Entwurf)' : ''} fertig nach ${j.seconds} s.` : `${STAGE[j.stage] || j.stage}${j.total ? ` – ${j.done}/${j.total}` : ''}${eta}`;
    $('r-draft').disabled = $('r-final').disabled = j.status === 'running';
    if (j.status !== 'running') {
      update(await api('/api/summary'));
      if (j.status === 'done') toast('Video fertig – unten unter „Fertige Videos“.');
      break;
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
  polling = false;
}
$('r-draft').onclick = () => startRender(true);
$('r-final').onclick = () => startRender(false);

update(await api('/api/summary'));
poll();
initView().catch((e) => {
  $('loading').textContent = '3D-Vorschau konnte nicht starten: ' + e.message;
});
