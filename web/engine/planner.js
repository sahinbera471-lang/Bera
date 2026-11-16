// Stadtplanung: Budget aus Followern, automatische Bauplanung nach Masterplan, eigene Gebäude.
// Reine Logik – läuft im Dashboard (Vorschau) und auf dem Server (verbindlich).
import { CATALOG, EURO_PER_FOLLOWER, itemCost, footprint, rectsOverlap } from './catalog.js';

export const pendingEpisode = (state) => (state.episodesRendered || 0) + 1;

export function allObjects(state) {
  return [...state.roads, ...state.items];
}

export function budgetOf(state) {
  const total = (state.followers || 0) * EURO_PER_FOLLOWER;
  const spent = allObjects(state).reduce((s, o) => s + itemCost(o), 0);
  return { total, spent, available: total - spent };
}

export function remainingPlan(state, masterplan) {
  const have = new Set(allObjects(state).map((o) => o.id));
  return masterplan.entries.filter((e) => !have.has(e.id));
}

// Was kann mit dem verfügbaren Budget als Nächstes gebaut werden? (Reihenfolge des Masterplans)
export function autoPlan(state, masterplan) {
  let left = budgetOf(state).available;
  const queue = [];
  let next = null;
  for (const e of remainingPlan(state, masterplan)) {
    const c = itemCost(e);
    if (c <= left) {
      queue.push(e);
      left -= c;
    } else {
      next = { entry: e, missing: c - left, followersNeeded: Math.ceil((c - left) / EURO_PER_FOLLOWER) };
      break;
    }
  }
  return { queue, cost: queue.reduce((s, e) => s + itemCost(e), 0), left, next };
}

export function milestoneStatus(state, masterplan) {
  const have = new Set(allObjects(state).map((o) => o.id));
  return masterplan.milestones.map((m) => {
    const entries = masterplan.entries.filter((e) => e.milestone === m.followers);
    const built = entries.filter((e) => have.has(e.id));
    return { ...m, total: entries.length, built: built.length, cost: entries.reduce((s, e) => s + itemCost(e), 0), restCost: entries.filter((e) => !have.has(e.id)).reduce((s, e) => s + itemCost(e), 0), reached: (state.followers || 0) >= m.followers };
  });
}

// Laternen entlang einer neuen Straße (exakte Positionen werden im Stadtzustand gespeichert)
export function lampsForRoad(road, roads) {
  const ax = Math.abs(road.b[0] - road.a[0]) >= Math.abs(road.b[1] - road.a[1]) ? 0 : 1, px = 1 - ax;
  const L = Math.abs(road.b[ax] - road.a[ax]), sgn = Math.sign(road.b[ax] - road.a[ax]) || 1;
  const off = (road.width || 7) / 2 + (road.sidewalk ?? 2.5) - 0.6;
  const cross = roads.filter((q) => q.id !== road.id && (Math.abs(q.b[0] - q.a[0]) >= Math.abs(q.b[1] - q.a[1]) ? 0 : 1) !== ax);
  const out = [];
  let side = 1, i = 0;
  for (let t = 14; t < L - 6; t += 28) {
    const c = road.a[ax] + sgn * t;
    const blocked = cross.some((q) => Math.abs(q.a[ax] - c) < (q.width || 7) / 2 + 4 && Math.min(q.a[px], q.b[px]) <= road.a[px] + off + 1 && Math.max(q.a[px], q.b[px]) >= road.a[px] - off - 1);
    if (!blocked) {
      const p = [0, 0];
      p[ax] = c;
      p[px] = road.a[px] + side * off;
      const dir = [0, 0];
      dir[px] = -side;
      out.push({ id: `${road.id}_lamp_${++i}`, type: 'lamp', x: Math.round(p[0] * 10) / 10, z: Math.round(p[1] * 10) / 10, rot: Math.round((Math.atan2(dir[0], dir[1]) * 180) / Math.PI), cost: 0 });
    }
    side = -side;
  }
  return out;
}

// Einträge verbindlich in den Stadtzustand übernehmen (als Teil der nächsten Episode)
export function commitEntries(state, entries) {
  const ep = pendingEpisode(state);
  const added = [];
  for (const e of entries) {
    const o = { ...e, episode: ep };
    delete o.milestone;
    if (o.type === 'road') {
      state.roads.push(o);
      added.push(o.id);
      for (const l of lampsForRoad(o, state.roads)) {
        state.items.push({ ...l, episode: ep, auto: o.id });
        added.push(l.id);
      }
    } else {
      state.items.push(o);
      added.push(o.id);
    }
  }
  return added;
}

export function collisions(state, obj) {
  const f = footprint(obj);
  return allObjects(state).filter((o) => o.id !== obj.id && o.type !== 'tree' && o.type !== 'lamp' && rectsOverlap(f, footprint(o), 0.5));
}

// Eigenes Gebäude an freier Stelle hinzufügen
export function addCustom(state, { type, x, z, rot = 0, name, floors }) {
  const c = CATALOG[type];
  if (!c || type === 'road') return { ok: false, error: 'Unbekannter Gebäudetyp.' };
  const n = state.items.filter((i) => i.id.startsWith('custom_')).length + 1;
  const item = { id: `custom_${type}_${n}_${Date.now().toString(36)}`, type, x: Math.round(x * 10) / 10, z: Math.round(z * 10) / 10, rot: ((Math.round(rot / 90) * 90) % 360 + 360) % 360, custom: true };
  if (name) item.name = String(name).toUpperCase().replace(/[:|]/g, ' ').slice(0, 24);
  if (floors) item.floors = floors;
  const cost = itemCost(item);
  const b = budgetOf(state);
  if (cost > b.available) return { ok: false, error: `Budget reicht nicht: ${cost.toLocaleString('de-DE')} € nötig, ${b.available.toLocaleString('de-DE')} € verfügbar.` };
  if (Math.hypot(item.x, item.z) > 300) return { ok: false, error: 'Außerhalb des Baugebiets (max. 300 m vom Zentrum).' };
  if (type !== 'tree' && type !== 'lamp') {
    const hit = collisions(state, item);
    if (hit.length) return { ok: false, error: `Fläche belegt durch: ${hit.map((h) => h.name || CATALOG[h.type]?.label || h.id).join(', ')}` };
  }
  item.episode = pendingEpisode(state);
  state.items.push(item);
  return { ok: true, item, cost };
}

// Noch nicht gerenderte (geplante) Bauten wieder entfernen
export function removePending(state, id = null) {
  const ep = pendingEpisode(state);
  const keep = (o) => (o.episode ?? 1) !== ep || (id && o.id !== id && o.auto !== id);
  const before = state.roads.length + state.items.length;
  state.roads = state.roads.filter(keep);
  state.items = state.items.filter(keep);
  return before - state.roads.length - state.items.length;
}
