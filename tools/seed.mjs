// Erzeugt einmalig den Grundzustand der Stadt (Episode 001) und den Masterplan.
// ACHTUNG: überschreibt city/state.json – nur für einen kompletten Neustart benutzen (--force).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { footprint, rectsOverlap, itemCost } from '../web/engine/catalog.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const stateFile = path.join(root, 'city/state.json');
if (fs.existsSync(stateFile) && !process.argv.includes('--force')) {
  console.error('city/state.json existiert bereits. Mit --force überschreiben (setzt die Stadt zurück!).');
  process.exit(1);
}

const roads = [
  { id: 'road_main', type: 'road', name: 'Hauptstraße', kind: 'main', a: [-95, 0], b: [95, 0], width: 8, sidewalk: 2.5, crosswalks: [85], cost: 0, episode: 1 },
  { id: 'road_side', type: 'road', name: 'Nebenstraße', kind: 'side', a: [20, 0], b: [20, -72], width: 6, sidewalk: 2, cost: 0, episode: 1 },
];
const items = [
  { id: 'plaza_1', type: 'plaza', name: 'Dorfplatz', x: -10, z: 17.5, rot: 0 },
  { id: 'house_1', type: 'house', x: -52, z: -15.75, rot: 0, w: 10, d: 8.5, floors: 2, wall: '#f4ead7', roof: '#a8472f', shutters: '#3f6f4f', flowers: '#d6336c', garage: true, car: '#274c7a', tree: 'deciduous' },
  { id: 'house_2', type: 'house', x: -27, z: -15.75, rot: 0, w: 10, d: 8.5, floors: 2, wall: '#ecc58e', roof: '#6a4a40', balcony: true, flowers: '#e03131', pergola: true, door: '#5b3a22', tree: 'linden' },
  { id: 'house_3', type: 'house', x: 34.25, z: -36, rot: -90, w: 10, d: 8.5, floors: 2, wall: '#f7f3ec', roof: '#b6532f', shutters: '#2f4f7f', flowers: '#f08c00', tree: 'deciduous' },
];
const T = (id, x, z, species = 'deciduous', variant = 0, scale = 1) => ({ id: 'tree_' + id, type: 'tree', x, z, species, variant, scale });
items.push(
  T(1, -26.5, 10.5, 'linden', 0, 1.0), T(2, -26.5, 25, 'linden', 1, 0.95), T(3, 6.5, 10.5, 'linden', 2, 1.0), T(4, 6.5, 25, 'linden', 3, 0.9),
  T(5, -44, 11, 'deciduous', 1, 1.05), T(6, -36, 13, 'deciduous', 4, 0.85), T(7, 13, 11, 'deciduous', 2, 0.95), T(8, 28, 12, 'autumn', 0, 0.9),
  T(9, -39.5, -14, 'cypress', 1, 0.8), T(10, 30, -12, 'deciduous', 3, 1.0), T(11, 41, -14, 'cypress', 2, 0.85), T(12, 51, -11, 'deciduous', 0, 0.9),
  T(13, -70, -12, 'deciduous', 2, 1.05), T(14, -100, 12, 'conifer', 0, 1.0), T(15, -105, 28, 'deciduous', 1, 1.1), T(16, 74, 12, 'deciduous', 4, 1.0),
  T(17, -170, -60, 'deciduous', 0, 1.3), T(18, -185, 40, 'conifer', 1, 1.2), T(19, 120, -130, 'deciduous', 2, 1.25), T(20, 30, -140, 'conifer', 2, 1.15),
  T(21, -60, -140, 'deciduous', 3, 1.3), T(22, 215, 112, 'deciduous', 1, 1.2), T(23, -8, 152, 'deciduous', 4, 1.3), T(24, 128, 78, 'autumn', 1, 1.1)
);
const Lp = (id, x, z, rot) => ({ id: 'lamp_' + id, type: 'lamp', x, z, rot });
items.push(
  Lp(1, -81, -5.9, 0), Lp(2, -39.5, -5.9, 0), Lp(3, 27.5, -5.9, 0), Lp(4, 81, -5.9, 0),
  Lp(5, -54, 5.9, 180), Lp(6, 0, 5.9, 180), Lp(7, 54, 5.9, 180),
  Lp(8, 24.4, -24, -90), Lp(9, 15.6, -44, 90), Lp(10, 24.4, -62, -90),
  Lp(11, -23.4, 17.5, 90), Lp(12, 3.4, 17.5, -90)
);
for (const it of items) Object.assign(it, { cost: 0, episode: 1 });

const state = {
  name: 'AUSLÄNDERSTADT',
  version: 1,
  note: 'Dauerhafter Stadtzustand. Jede Episode baut auf diesem Stand auf – niemals neu erzeugen.',
  terrain: { seed: 4711, size: 2600, flatRadius: 330 },
  lighting: { sunAzimuth: -74, sunElevationDay: 38, sunElevationDusk: -2.5, timeOfDay: 0.15 },
  followers: 0,
  episodesRendered: 0,
  roads,
  items,
  cameras: {},
  episodes: [],
};

// ------------------------------------------------------------------ Masterplan
const H = (id, x, z, rot, o = {}) => ({ id, type: 'house', x, z, rot, w: 10, d: 8.5, floors: 2, ...o });
const entries = [
  // 1.000 Follower – erste Wohnstraße + weitere Wohnhäuser
  { milestone: 1000, id: 'road_garten', type: 'road', name: 'Gartenweg', kind: 'residential', a: [23, -72], b: [-90, -72], width: 6, sidewalk: 2 },
  { milestone: 1000, ...H('house_4', -22, -57.75, 180, { wall: '#f1dcc0', roof: '#8d3f2b', shutters: '#7a3b2e', garage: true, car: '#c9ccd1' }) },
  { milestone: 1000, ...H('house_5', 2, -57.75, 180, { wall: '#f6f1e7', roof: '#5c4a44', balcony: true, flowers: '#d6336c' }) },
  { milestone: 1000, ...H('house_6', -22, -86.25, 0, { wall: '#e8d1a6', roof: '#a8472f', pergola: true, flowers: '#e03131' }) },
  { milestone: 1000, ...H('house_7', 2, -86.25, 0, { wall: '#f4ead7', roof: '#b6532f', shutters: '#3f6f4f', garage: true, car: '#8a1f1f' }) },
  { milestone: 1000, ...H('house_8', -46, -86.25, 0, { wall: '#dfe7ea', roof: '#5c4a44', shutters: '#2f4f7f', tree: 'linden' }) },
  // 2.000 Follower – Supermarkt, Parkplatz, kleine Geschäfte
  { milestone: 2000, id: 'parking_1', type: 'parking', name: 'Parkplatz', x: 51, z: 16.5, rot: 0 },
  { milestone: 2000, id: 'supermarket_1', type: 'supermarket', name: 'AUSLÄNDER MARKT', x: 51, z: 42.5, rot: 180 },
  { milestone: 2000, id: 'shop_1', type: 'shop', name: 'DÖNER KEBAP', x: -8, z: -15.6, rot: 0, wall: '#f0dfc0' },
  { milestone: 2000, id: 'shop_2', type: 'shop', name: 'BÄCKEREI SIMIT', x: 4, z: -15.6, rot: 0, wall: '#e9d3ad', roof: '#6a4a40' },
  // 3.000 Follower – Schule + Fußballplatz
  { milestone: 3000, id: 'road_main_e', type: 'road', name: 'Hauptstraße Ost', kind: 'main', a: [95, 0], b: [155, 0], width: 8, sidewalk: 2.5 },
  { milestone: 3000, id: 'school_1', type: 'school', name: 'GRUNDSCHULE', x: 80, z: -30.5, rot: 0 },
  { milestone: 3000, id: 'pitch_1', type: 'pitch', name: 'Fußballplatz', x: 86, z: -72, rot: 0 },
  // 5.000 Follower – Rathaus, Statue, zentraler Marktplatz
  { milestone: 5000, id: 'market_1', type: 'market', name: 'Marktplatz', x: -10, z: 50.5, rot: 0 },
  { milestone: 5000, id: 'statue_1', type: 'statue', name: 'Denkmal', x: -10, z: 82, rot: 180 },
  { milestone: 5000, id: 'townhall_1', type: 'townhall', name: 'RATHAUS', x: -10, z: 112, rot: 180 },
  // 10.000 Follower – größere Wohngebiete, Moschee, Einkaufszentrum, neue Straßen
  { milestone: 10000, id: 'road_main_w', type: 'road', name: 'Hauptstraße West', kind: 'main', a: [-95, 0], b: [-150, 0], width: 8, sidewalk: 2.5 },
  { milestone: 10000, id: 'road_west', type: 'road', name: 'Weststraße', kind: 'side', a: [-120, 0], b: [-120, 95], width: 7, sidewalk: 2.5 },
  { milestone: 10000, id: 'mosque_1', type: 'mosque', name: 'Moschee', x: -70, z: 43.5, rot: 180 },
  { milestone: 10000, id: 'apartment_1', type: 'apartment', x: -139, z: 22, rot: 90, floors: 5, wall: '#f0e4cf', accent: '#c96f4a' },
  { milestone: 10000, id: 'apartment_2', type: 'apartment', x: -139, z: 54, rot: 90, floors: 6, wall: '#e6ecef', accent: '#3f6f8f' },
  { milestone: 10000, id: 'apartment_3', type: 'apartment', x: -139, z: 86, rot: 90, floors: 5, wall: '#f3e2b8', accent: '#7a9a4a' },
  { milestone: 10000, id: 'apartment_4', type: 'apartment', x: -126, z: -19.5, rot: 0, floors: 4, wall: '#f0e4cf', accent: '#b3564a' },
  { milestone: 10000, id: 'apartment_5', type: 'apartment', x: -94, z: -19.5, rot: 0, floors: 5, wall: '#ece6da', accent: '#c98a3a' },
  { milestone: 10000, id: 'mall_1', type: 'mall', name: 'CITY CENTER', x: 115, z: 35.5, rot: 180 },
  // 25.000 Follower – Hochhäuser, Gewerbegebiet, großer Stadtpark
  { milestone: 25000, id: 'road_west_2', type: 'road', name: 'Weststraße Süd', kind: 'side', a: [-120, 95], b: [-120, 140], width: 7, sidewalk: 2.5 },
  { milestone: 25000, id: 'road_south', type: 'road', name: 'Südring', kind: 'main', a: [-123.5, 140], b: [173.5, 140], width: 8, sidewalk: 2.5 },
  { milestone: 25000, id: 'road_main_e2', type: 'road', name: 'Hauptstraße Ost II', kind: 'main', a: [155, 0], b: [170, 0], width: 8, sidewalk: 2.5 },
  { milestone: 25000, id: 'road_east', type: 'road', name: 'Oststraße', kind: 'side', a: [170, 140], b: [170, -100], width: 7, sidewalk: 2.5 },
  { milestone: 25000, id: 'park_1', type: 'park', name: 'Stadtpark', x: -74, z: 104, rot: 0 },
  { milestone: 25000, id: 'highrise_1', type: 'highrise', x: 60, z: 116.5, rot: 0, floors: 18, wall: '#cfe0ee' },
  { milestone: 25000, id: 'highrise_2', type: 'highrise', x: 98, z: 116.5, rot: 0, floors: 26, wall: '#bcd3e6' },
  { milestone: 25000, id: 'highrise_3', type: 'highrise', x: 136, z: 116.5, rot: 0, floors: 21, wall: '#d9e3ea' },
  { milestone: 25000, id: 'highrise_4', type: 'highrise', x: 60, z: 163.5, rot: 180, floors: 30, wall: '#c4d6e2' },
  { milestone: 25000, id: 'warehouse_1', type: 'warehouse', name: 'LOGISTIK GMBH', x: 203, z: -70, rot: -90 },
  { milestone: 25000, id: 'warehouse_2', type: 'warehouse', name: 'BALKAN IMPORT', x: 203, z: -20, rot: -90, accent: '#1f5c3a' },
  { milestone: 25000, id: 'warehouse_3', type: 'warehouse', name: 'ANADOLU FOODS', x: 203, z: 40, rot: -90, accent: '#b3261e' },
];
const masterplan = {
  note: 'Geplante Stadtentwicklung. Reihenfolge = Baureihenfolge. Positionen sind fest, damit die Stadt in jeder Episode dieselbe bleibt.',
  milestones: [
    { followers: 1000, title: 'Erste Wohnstraße', text: 'Weitere Wohnhäuser, erste Wohnstraße' },
    { followers: 2000, title: 'Nahversorgung', text: 'Supermarkt, Parkplatz, kleine Geschäfte' },
    { followers: 3000, title: 'Bildung & Sport', text: 'Schule, Fußballplatz' },
    { followers: 5000, title: 'Stadtzentrum', text: 'Großes Rathaus, monumentale Statue, zentraler Marktplatz' },
    { followers: 10000, title: 'Großstadt', text: 'Größere Wohngebiete, Moschee, Einkaufszentrum, neue Straßen' },
    { followers: 25000, title: 'Skyline', text: 'Hochhäuser, Gewerbegebiet, großer Stadtpark' },
  ],
  entries,
};

// ---- Plausibilitätsprüfung: keine Überschneidungen, Budget je Meilenstein ----
const all = [...roads, ...items, ...entries];
let bad = 0;
for (let i = 0; i < all.length; i++)
  for (let j = i + 1; j < all.length; j++) {
    const a = all[i], b = all[j];
    if (a.type === 'lamp' || b.type === 'lamp') continue;
    if (a.type === 'road' && b.type === 'road') continue;
    if ((a.type === 'tree') !== (b.type === 'tree') || (a.type !== 'tree' && b.type !== 'tree')) {
      if (rectsOverlap(footprint(a), footprint(b), 0.3)) {
        console.log('ÜBERSCHNEIDUNG:', a.id, footprint(a).map(Math.round), b.id, footprint(b).map(Math.round));
        bad++;
      }
    }
  }
let cum = 0;
for (const m of masterplan.milestones) {
  const c = entries.filter((e) => e.milestone === m.followers).reduce((s, e) => s + itemCost(e), 0);
  cum += c;
  console.log(`${String(m.followers).padStart(6)} Follower: +${(c / 1e6).toFixed(3)} Mio € | kumuliert ${(cum / 1e6).toFixed(3)} Mio € | Budget ${(m.followers / 1000).toFixed(1)} Mio € ${cum <= m.followers * 1000 ? 'OK' : 'ZU TEUER'}`);
}
if (bad) process.exit(1);
fs.mkdirSync(path.join(root, 'city'), { recursive: true });
fs.writeFileSync(stateFile, JSON.stringify(state, null, 1));
fs.writeFileSync(path.join(root, 'city/masterplan.json'), JSON.stringify(masterplan, null, 1));
console.log('city/state.json und city/masterplan.json geschrieben.');
