// Re-geocode plant coordinates against OpenStreetMap `power=plant`.
//
// WHY: the plant coordinates in public/data/coordinates.json were originally
// produced by name-based geocoding, which landed ~40% of plants on generic
// city/substation centroids (many plants stacked on one point). OSM has real,
// community-verified plant footprints, so we snap to those where we can match.
//
// METHOD (per plant in atlas.json D.P):
//   candidate OSM plant must be
//     • within 0.7° of the current coord (disambiguate + avoid wild jumps), and
//     • fuel-type compatible (a `pv` plant never snaps to a same-named wind farm), and
//     • name-similar: |shared significant tokens| / |our tokens| ≥ threshold,
//       with ≥1 shared token of length ≥4. Threshold is 0.5 for moves <15 km,
//       0.7 for moves ≥15 km (a weak name match can't drag a plant far).
//   Best-scoring candidate wins. Matched plants get the OSM coord (4 dp).
//   A plant that stays unmatched AND still shares a point with another is
//   flagged approximate → coordinates.json `approx[i] = 1` (the map dims it and
//   labels the popup "ubicación aproximada").
//
// USAGE:
//   node scripts/regeocode_plants_osm.mjs                # uses cached OSM file if present
//   OSM_REFETCH=1 node scripts/regeocode_plants_osm.mjs  # re-query Overpass
//
// Overpass query used to build the cache (public/data/osm_plants.json):
//   [out:json][timeout:180];
//   ( node["power"="plant"](14.0,-118.6,33.0,-86.0);
//     way["power"="plant"](14.0,-118.6,33.0,-86.0);
//     relation["power"="plant"](14.0,-118.6,33.0,-86.0); );
//   out center tags;

import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const DATA = 'public/data';
const OSM_CACHE = `${DATA}/osm_plants.json`;
const OVERPASS = 'https://overpass-api.de/api/interpreter';
const QUERY = `[out:json][timeout:180];(node["power"="plant"](14.0,-118.6,33.0,-86.0);way["power"="plant"](14.0,-118.6,33.0,-86.0);relation["power"="plant"](14.0,-118.6,33.0,-86.0););out center tags;`;

async function loadOsm() {
  if (!process.env.OSM_REFETCH && existsSync(OSM_CACHE)) return JSON.parse(readFileSync(OSM_CACHE, 'utf8'));
  const r = await fetch(OVERPASS, { method: 'POST', body: 'data=' + encodeURIComponent(QUERY) });
  const j = await r.json();
  writeFileSync(OSM_CACHE, JSON.stringify(j));
  return j;
}

const STOP = new Set('central de la el los las planta parque ciclo combinado turbogas turbo gas termoelectrica termica geotermica geotermoelectrica hidroelectrica fotovoltaica solar eolico eolica eoloelectrica nucleoelectrica carboelectrica cc tg ct ci cogeneracion energia generacion power plant y del san santa unidad fase'.split(' '));
const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const toks = s => norm(s).split(' ').filter(t => t.length >= 3 && !STOP.has(t));
const FOSSIL = new Set(['gas', 'natural_gas', 'oil', 'fuel_oil', 'diesel', 'coal', 'biomass', 'biogas', 'waste', 'combustion', '']);
function compat(t, src) {
  if (!src) return true;
  if (t === 'pv') return src === 'solar';
  if (t === 'wind') return src === 'wind';
  if (t === 'hydro') return src === 'hydro';
  if (t === 'geo') return src === 'geothermal';
  if (t === 'nuc') return src === 'nuclear';
  if (t === 'coal') return src === 'coal' || src === '';
  if (t === 'bat') return src === 'battery';
  if (['cc', 'th', 'tg', 'ci', 'cog'].includes(t)) return FOSSIL.has(src);
  return true; // cegen / unknown
}

const D = JSON.parse(readFileSync(`${DATA}/atlas.json`, 'utf8'));
const C = JSON.parse(readFileSync(`${DATA}/coordinates.json`, 'utf8'));
const osm = (await loadOsm()).elements.filter(e => e.tags && e.tags.name)
  .map(e => { const c = e.center || { lat: e.lat, lon: e.lon }; return { t: new Set(toks(e.tags.name)), lat: c.lat, lon: c.lon, src: (e.tags['plant:source'] || e.tags['generator:source'] || '').toLowerCase() }; })
  .filter(o => o.lat != null);

let applied = 0;
D.P.forEach((p, i) => {
  const k = C.plants[i]; if (!k || k[0] == null) return;
  const ot = new Set(toks(p[0])); if (!ot.size) return;
  let best = null, bs = 0;
  for (const o of osm) {
    const d = Math.hypot(o.lat - k[0], o.lon - k[1]); if (d > 0.7) continue;
    if (!compat(p[4], o.src)) continue;
    let inter = 0, distinct = false;
    ot.forEach(x => { if (o.t.has(x)) { inter++; if (x.length >= 4) distinct = true; } });
    if (!distinct) continue;
    const score = inter / ot.size, need = d * 111 < 15 ? 0.5 : 0.7;
    if (score >= need && score > bs) { bs = score; best = o; }
  }
  if (best) { C.plants[i] = [+best.lat.toFixed(4), +best.lon.toFixed(4)]; applied++; }
});

// flag approximate = unmatched AND still sharing a generic point with another plant
const osmSet = new Set(osm.map(o => (+o.lat.toFixed(4)) + ',' + (+o.lon.toFixed(4))));
const cnt = {};
D.P.forEach((p, i) => { const k = C.plants[i]; if (k && k[0] != null) { const key = k[0] + ',' + k[1]; cnt[key] = (cnt[key] || 0) + 1; } });
const approx = D.P.map((p, i) => { const k = C.plants[i]; if (!k || k[0] == null) return 0; const key = k[0] + ',' + k[1]; return (!osmSet.has(key) && cnt[key] > 1) ? 1 : 0; });
C.approx = approx;

writeFileSync(`${DATA}/coordinates.json`, JSON.stringify(C));
console.log(`OSM-matched: ${applied} · flagged approximate: ${approx.reduce((a, b) => a + b, 0)} · total: ${D.P.length}`);
