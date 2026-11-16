// Gebäudekatalog: Typen, Standardmaße (Grundfläche inkl. Garten/Hof in Metern), virtuelle Baukosten.
// Reine Daten – wird von Browser (Dashboard, Renderer) und Node (Server) gemeinsam genutzt.

export const EURO_PER_FOLLOWER = 1000;

export const CATALOG = {
  house:       { label: 'Wohnhaus',            cost: 150000,  w: 10, d: 8.5, lot: [22, 23], off: -2, cls: 'building' },
  shop:        { label: 'Kleines Geschäft',    cost: 120000,  w: 10, d: 10,  lot: [11, 14], off: 2, cls: 'building' },
  supermarket: { label: 'Supermarkt',          cost: 600000,  w: 34, d: 22,  lot: [36, 26], off: 2, cls: 'building' },
  parking:     { label: 'Parkplatz',           cost: 100000,  w: 34, d: 18,  lot: [34, 18], cls: 'area' },
  school:      { label: 'Schule',              cost: 600000,  w: 44, d: 16,  lot: [48, 34], off: 7, cls: 'building' },
  pitch:       { label: 'Fußballplatz',        cost: 250000,  w: 56, d: 36,  lot: [56, 36], cls: 'area' },
  townhall:    { label: 'Rathaus',             cost: 1200000, w: 40, d: 22,  lot: [46, 32], off: 4, cls: 'building' },
  statue:      { label: 'Monumentale Statue',  cost: 300000,  w: 14, d: 14,  lot: [14, 14], cls: 'building' },
  market:      { label: 'Marktplatz',          cost: 400000,  w: 70, d: 44,  lot: [70, 44], cls: 'area' },
  apartment:   { label: 'Mehrfamilienhaus',    cost: 400000,  w: 22, d: 13,  lot: [30, 26], cls: 'building' },
  mosque:      { label: 'Moschee',             cost: 1200000, w: 30, d: 30,  lot: [44, 52], off: 10, cls: 'building' },
  mall:        { label: 'Einkaufszentrum',     cost: 1500000, w: 64, d: 42,  lot: [70, 50], off: 4, cls: 'building' },
  highrise:    { label: 'Hochhaus',            cost: 2500000, w: 22, d: 22,  lot: [34, 34], cls: 'building' },
  warehouse:   { label: 'Gewerbehalle',        cost: 800000,  w: 40, d: 26,  lot: [48, 40], off: 6, cls: 'building' },
  park:        { label: 'Stadtpark',           cost: 1400000, w: 76, d: 58,  lot: [76, 58], cls: 'area' },
  plaza:       { label: 'Kleiner Platz',       cost: 80000,   w: 24, d: 20,  lot: [24, 20], cls: 'area' },
  tree:        { label: 'Baum',                cost: 1000,    w: 4,  d: 4,   lot: [3, 3],   cls: 'prop' },
  lamp:        { label: 'Straßenlaterne',      cost: 3000,    w: 1,  d: 1,   lot: [1, 1],   cls: 'prop' },
  road:        { label: 'Straße',              costPerMeter: 2000, cls: 'road' },
};

// Reihenfolge, in der Bauteile innerhalb einer Episode entstehen
export const BUILD_ORDER = ['road', 'area', 'building', 'tree', 'lamp'];

export function itemClass(it) {
  if (it.type === 'tree' || it.type === 'lamp') return it.type;
  return CATALOG[it.type]?.cls || 'building';
}

export function itemCost(it) {
  if (typeof it.cost === 'number') return it.cost;
  const c = CATALOG[it.type];
  if (!c) return 0;
  if (it.type === 'road') return Math.round(roadLength(it) * c.costPerMeter);
  return c.cost;
}

export function roadLength(r) {
  return Math.hypot(r.b[0] - r.a[0], r.b[1] - r.a[1]);
}

// Achsenparalleles Rechteck der Grundfläche (inkl. Garten/Hof) in Weltkoordinaten: [minX, minZ, maxX, maxZ]
export function footprint(it) {
  if (it.type === 'road') {
    const hw = (it.width || 7) / 2 + (it.sidewalk ?? 2.5);
    const alongX = Math.abs(it.b[0] - it.a[0]) >= Math.abs(it.b[1] - it.a[1]);
    const x0 = Math.min(it.a[0], it.b[0]), x1 = Math.max(it.a[0], it.b[0]);
    const z0 = Math.min(it.a[1], it.b[1]), z1 = Math.max(it.a[1], it.b[1]);
    return alongX ? [x0, z0 - hw, x1, z1 + hw] : [x0 - hw, z0, x1 + hw, z1];
  }
  const c = CATALOG[it.type] || { lot: [10, 10] };
  let [w, d] = it.lot || [it.w ? it.w + (c.lot[0] - c.w) : c.lot[0], it.d ? it.d + (c.lot[1] - c.d) : c.lot[1]];
  const q = ((Math.round((it.rot || 0) / 90) % 4) + 4) % 4;
  // Grundstück ist gegenüber dem Gebäude nach vorn/hinten versetzt (lokale z-Achse)
  const off = c.off || 0;
  const ox = [0, 1, 0, -1][q] * off, oz = [1, 0, -1, 0][q] * off;
  if (q % 2) [w, d] = [d, w];
  return [it.x + ox - w / 2, it.z + oz - d / 2, it.x + ox + w / 2, it.z + oz + d / 2];
}

export function rectsOverlap(a, b, margin = 0) {
  return a[0] < b[2] - margin && a[2] > b[0] + margin && a[1] < b[3] - margin && a[3] > b[1] + margin;
}
