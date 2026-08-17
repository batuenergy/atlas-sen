/**
 * Join the atlas plant inventory to the CNE generation-permit registry and emit
 * /atlas/data/permisos.json — the permit modality ("tipo de permiso") and the
 * expiry date the map filter, the popup, and centrales.csv all read.
 *
 *   node scripts/build_permisos.mjs          (or: make permisos)
 *
 * ── Where the expiry comes from ──────────────────────────────────────────────
 * The CNE's public table publishes only the GRANT date for permits still in
 * force; its `Vigencia` / `Fecha de Terminación` columns exist solely on the
 * "Permisos No Vigentes" sheet, so the registry states a term only once the
 * permit is already dead. The term therefore comes from the PERMIT TITLE, read
 * document by document out of the CNE Registro Público
 * (scripts/crawl_permit_titles.mjs → data/sources/permisos-vigencia-titulos.json).
 *
 * `base` records which of these produced the date, and it must always travel
 * with it:
 *   verificado  read from the title — either an outright calendar date
 *               ("hasta el 1 de abril de 2028") or its stated term
 *   indefinida  the title says "duración indefinida" — there IS no expiry
 *   derivado /  no title read yet; falls back to otorgamiento + 30 años
 *   estimado    (`estimado` for LSPEE, whose original terms vary)
 *
 * Reading the titles overturned the 30-year default three ways, which is why the
 * fallback is a last resort and not the design:
 *   · 25 permits — almost all autoabastecimiento — are indefinite. Giving them
 *     an expiry was inventing a cliff that does not exist.
 *   · legacy PIE titles run 26y11m–28y, not 30, so their true dates land years
 *     EARLIER (Central Anáhuac E/128/PIE/98 lapsed 2026-07-16).
 *   · 16 titles name the date outright, no arithmetic at all.
 *
 * Why it matters: LSE transitorios quinto/noveno say permits granted under the
 * LSPEE and the LIE run to the end of their vigencia and "no deben ser
 * prorrogados". An expiry is a cliff, not a renewal formality.
 *
 * ── Inputs ───────────────────────────────────────────────────────────────────
 *   data/sources/permisos-cne-jul26.json  CNE snapshot, normalized (public, CC-BY)
 *   data/sources/atlas-ownership.json    plant → {spv, regimen, …}; Batu research
 *   public/data/atlas.json               plant inventory (name, MW, tech)
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA = join(__dirname, '..', 'public', 'data');
const SRC = join(__dirname, '..', 'data', 'sources');
const readJson = (p) => JSON.parse(readFileSync(p, 'utf8'));

const SNAPSHOT = 'permisos-cne-jul26.json';
const SOURCE = {
  label: 'CNE · Lista de permisos otorgados de generación de energía eléctrica (31-jul-2026)',
  url: 'https://www.gob.mx/cne/documentos/estadisticas-e-informacion-en-materia-de-permisos-de-electricidad',
};
/** LIE art. 17 / permit-title Condición TERCERA: up to 30 years from issuance. */
const TERM_YEARS = 30;

// ── Permit-modality vocabulary ────────────────────────────────────────────────
// Codes are the CNE's own `Modalidad` values; the glossary sheet in the same
// workbook defines MEM / ABA-I / ABA-NI / AUTC-A / AUTC-I verbatim.
const MODALIDAD = {
  MEM: 'Generador MEM',
  'AUT.': 'Autoabastecimiento',
  'ABA-I': 'Abasto aislado · interconectado',
  'ABA-NI': 'Abasto aislado · no interconectado',
  'COG.': 'Cogeneración',
  'P.I.E.': 'Producción independiente (PIE)',
  'U.P.C.': 'Usos propios continuos',
  'IMP.': 'Importación',
  'EXP.': 'Exportación',
  'P.P.': 'Pequeña producción',
  'AUTC-I': 'Autoconsumo interconectado',
  'AUTC-A': 'Autoconsumo aislado',
};
/** Fallback when no permit matched: Batu's researched régimen → same vocabulary. */
const REGIMEN_FALLBACK = {
  'PIE (legado)': 'P.I.E.',
  'Autoabastecimiento (legado)': 'AUT.',
  Cogeneración: 'COG.',
  'Pequeña producción': 'P.P.',
  'Generador MEM': 'MEM',
  'Subasta LP': 'MEM',
  'CFE (servicio público legado)': 'CFE',
};
// CFE's own legacy public-service fleet predates the permit regime; it is a real
// category on the map, not a missing match.
MODALIDAD.CFE = 'CFE · servicio público (legado)';

/** Atlas tech code → the CNE `Tecnología` strings that corroborate it. */
const TECH = {
  pv: ['fotovoltaica'],
  wind: ['eolica'],
  hydro: ['hidroelectrica'],
  geo: ['geotermica'],
  nuc: ['nucleoelectrica'],
  cc: ['ciclo combinado'],
  th: ['termoelectrica convencional', 'lecho fluidizado', 'vapor'],
  coal: ['carboelectrica'],
  tg: ['turbogas'],
  ci: ['combustion interna'],
  cog: ['cogeneracion', 'cogeneracion eficiente'],
  bat: ['almacenamiento', 'bateria'],
};

const strip = (s) =>
  (s || '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();

/** Normalize a company name: drop the corporate-form suffix and punctuation. */
const norm = (s) =>
  strip(s)
    .replace(/\b(s\.?\s?a\.?\s?p\.?\s?i\.?|s\.?\s?a\.?\s?b\.?|s\.?\s?a\.?|s\.?\s?de\s?r\.?\s?l\.?|de\s?c\.?\s?v\.?|c\.?\s?v\.?|e\s?p\s?e)\b/g, '')
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

/**
 * The atlas `spv` often carries a human annotation — "Energía Azteca VIII /
 * Saavi Energía (ex-InterGen Bajío)". Only the head is the legal name.
 */
const legalName = (spv) => norm(String(spv).split(/[(/]/)[0]);

/**
 * Multi-plant holders name the plant inside the `Permisionario` string:
 *   "Comisión Federal de Electricidad E P E, Central La Venta"
 *   "Petroleos Mexicanos E P E, Refinería Miguel Hidalgo"
 *   "Ternium México, S. A. de C. V., Planta Monterrey"
 * That trailing segment is the only thing tying an umbrella permit to a specific
 * plant — the CNE table has no plant-name column — so it is matched separately
 * from the legal name. Without it, CFE permits can only be matched on capacity,
 * which silently mis-assigns (Central La Venta is 84.2 MW, but a 30 MW CFE
 * permit outscored it on a plain MW join).
 */
const PLANT_WORD = /\b(central(?:es)?|planta|refineria|complejo|parque|proyecto|unidad|c\.?\s?[htcng]\.?)\b/gi;
function plantHint(titular) {
  const parts = String(titular).split(',');
  // Walk from the end for the first segment that names a plant rather than a
  // corporate form ("S. A. de C. V.", "S. de R. L.").
  for (let i = parts.length - 1; i >= 1; i--) {
    const seg = parts[i].trim();
    // norm() strips corporate forms entirely, so an empty result IS the test for
    // "this segment is just S. A. de C. V." — without it those suffixes were
    // being returned as if they named a plant.
    if (!norm(seg)) continue;
    return seg;
  }
  return '';
}

/** Strip plant-designation noise so "C.H. El Caracol" ≍ "Central El Caracol". */
const plantKeyOf = (s) =>
  strip(s)
    .split(/[(/]/)[0]
    .replace(PLANT_WORD, ' ')
    .replace(/\bu-?\s?\d+\b|\bfase\s+\w+\b|\bunidades?\s+\d+\b/g, ' ')
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const addYears = (iso, y) => {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCFullYear(d.getUTCFullYear() + y);
  return d.toISOString().slice(0, 10);
};

// ── Load ──────────────────────────────────────────────────────────────────────
const permisos = readJson(join(SRC, SNAPSHOT)).map((p) => ({
  ...p,
  key: norm(p.titular),
  plantKey: plantKeyOf(plantHint(p.titular)),
}));
/**
 * Terms read verbatim from the permit titles in the CNE Registro Público
 * (scripts/crawl_permit_titles.mjs). This is what turns a derived date into a
 * read one, and it overturned the 30-year default in three ways:
 *   · 16 titles state the calendar date outright ("hasta el 1 de abril de 2028")
 *   · 25 permits — almost all autoabastecimiento — are "de duración indefinida"
 *     and have NO expiry at all; deriving one for them was simply wrong
 *   · legacy PIE titles run 26y11m–28y, not 30, so their real dates land YEARS
 *     earlier than the default (Central Anáhuac expired 2026-07-16)
 */
const titulos = readJson(join(SRC, 'permisos-vigencia-titulos.json'));

const addMonths = (iso, y, m) => {
  const d = new Date(`${iso}T00:00:00Z`);
  const target = d.getUTCMonth() + m;
  d.setUTCFullYear(d.getUTCFullYear() + y + Math.floor(target / 12));
  d.setUTCMonth(((target % 12) + 12) % 12);
  return d.toISOString().slice(0, 10);
};

/** Expiry for a permit: read from its title when we have it, derived otherwise. */
function vigenciaDe(permit) {
  const t = titulos[permit.num];
  if (t?.indefinida) return { vencimiento: null, base: 'indefinida', clausula: t.clausula };
  if (t?.fecha) return { vencimiento: t.fecha, base: 'verificado', clausula: t.clausula };
  if (t?.anios) return { vencimiento: addMonths(permit.otorgamiento, t.anios, t.meses || 0), base: 'verificado', clausula: t.clausula };
  return {
    vencimiento: addYears(permit.otorgamiento, TERM_YEARS),
    base: permit.marco === 'LSPEE' ? 'estimado' : 'derivado',
  };
}
const regimen = readJson(join(SRC, 'atlas-ownership.json'));
const atlas = readJson(join(DATA, 'atlas.json'));

// ── Match ─────────────────────────────────────────────────────────────────────
/**
 * Tokens that carry no identifying power — they appear in hundreds of holder
 * names. A token match built only out of these is noise, and letting one through
 * is how "CFE Generación VI" matched "Compañía de Generación Valladolid".
 */
const STOP = new Set([
  'generacion', 'generadora', 'energia', 'energias', 'electricidad', 'electrica',
  'comision', 'federal', 'central', 'centrales', 'parque', 'parques', 'planta',
  'mexico', 'mexicana', 'mexicano', 'nacional', 'compania', 'grupo', 'servicios',
  'industrial', 'industrias', 'renovable', 'renovables', 'solar', 'eolica', 'eolico',
  'proyecto', 'desarrollos', 'sistemas',
]);

/** Name-similarity tier: 3 exact, 2 prefix, 1 every distinctive token present. */
function nameTier(plantName, permitKey) {
  if (!plantName || !permitKey) return 0;
  if (plantName === permitKey) return 3;
  if (permitKey.startsWith(plantName) || plantName.startsWith(permitKey)) return 2;
  // Tier 1 needs DISTINCTIVE tokens: one generic word in common ("generación")
  // is not evidence. Two ordinary tokens qualify — and so does a single long
  // one, because Mexican plants are named after rare toponyms that identify them
  // outright ("Tamazunchale" ties C.C. Tamazunchale to TMH Tamazunchale I).
  // Capacity still has to agree; this only decides whether to consider the pair.
  const toks = plantName.split(' ').filter((t) => t.length > 4 && !STOP.has(t));
  if (!toks.length || !toks.every((t) => permitKey.includes(t))) return 0;
  if (toks.length >= 2) return 1;
  return toks[0].length >= 8 ? 1 : 0;
}

/** MW agreement tier: capacity is the strongest corroborator we have. */
function mwTier(plantMw, permitMw) {
  if (!plantMw || !permitMw) return 0;
  const rel = Math.abs(plantMw - permitMw) / Math.max(plantMw, permitMw);
  if (rel <= 0.02) return 3;
  if (rel <= 0.1) return 2;
  if (rel <= 0.25) return 1;
  return 0;
}

const techOk = (code, tec) => (TECH[code] || []).some((t) => strip(tec).includes(t));

/**
 * Unit designators — "III y IV", "V", "2". Mexican sites stack same-named units,
 * so the toponym alone cannot tell them apart: "C.C. Altamira III y IV" (1,120 MW)
 * and ATV Altamira V (1,143 MW) agree on name AND on capacity to within 2%, and a
 * plain best-score join hands Altamira III y IV the wrong permit. When both sides
 * carry designators and they share none, it is a different unit — reject the pair.
 */
const ROMAN = /^(?:i{1,3}|iv|v|vi{1,3}|ix|x)$/;
// Read designators off the NORMALIZED name: "S. A. de C. V." otherwise donates a
// spurious roman "v", which made every "…V" plant look compatible with every
// other unit at the same site (C.C. Altamira V matched ATC Altamira III y IV).
const ordinals = (s) => new Set(norm(s).split(/\s+/).filter((t) => ROMAN.test(t) || /^\d{1,2}$/.test(t)));
function unitConflict(a, b) {
  const A = ordinals(a);
  const B = ordinals(b);
  if (!A.size || !B.size) return false;
  for (const x of A) if (B.has(x)) return false;
  return true;
}

const stats = { alta: 0, media: 0, sinDato: 0, fallback: 0, cfe: 0, descartado: 0, duplicado: 0, vencidoIncoherente: 0 };
const out0 = { today: new Date().toISOString().slice(0, 10) };

/** Best candidate permit for one plant, or null when nothing is corroborated. */
function matchPlant(name, mw, tech, own) {
  const legalKey = own.spv ? legalName(own.spv) : '';
  const nameKey = plantKeyOf(name);
  // Single-purpose plants are usually named after their own SPV ("Ventika",
  // "Techgen", "Parque Solar Villanueva"), so the plant name matches the holder
  // directly. Keep this key unstripped — removing "Parque" would break the
  // prefix test against "Parque Solar Villanueva, S.A.P.I. de C.V.".
  const rawKey = norm(String(name).split(/[(/]/)[0]);
  let best = null;

  for (const permit of permisos) {
    // Axis A — the operating company (SPV) matches the permit holder.
    const nt = legalKey ? nameTier(legalKey, permit.key) : 0;
    // Axis B — the plant name matches the plant named inside the holder string.
    const pt = permit.plantKey && nameKey ? nameTier(nameKey, permit.plantKey) : 0;
    // Axis C — the plant name matches the holder itself. Try it both raw and
    // with the plant designation stripped: "C.C. Tamazunchale" only reaches
    // "TMH Tamazunchale I" once the "C.C." prefix is out of the way.
    const ct = Math.max(rawKey ? nameTier(rawKey, permit.key) : 0, nameKey ? nameTier(nameKey, permit.key) : 0);
    if (!nt && !pt && !ct) continue;
    if (unitConflict(name, permit.titular)) continue;

    const mt = mwTier(mw, permit.mw);
    // Capacity is a hard gate, not a tie-breaker. Mexican toponyms repeat
    // ("La Angostura", "Santa Rosa", "Santa María"), so a name hit with no
    // capacity agreement is a coincidence: it paired a 900 MW CEGEN with a 7 MW
    // mine plant and a 148 MW solar farm with a 30 MW CFE permit. Skipping these
    // candidates outright also lets a weaker-but-corroborated permit win.
    if (mt === 0) continue;
    const tt = techOk(tech, permit.tecnologia) ? 1 : 0;
    const score = Math.max(nt, pt, ct) * 10 + pt * 6 + mt * 3 + tt;
    if (!best || score > best.score) best = { permit, score, nt, pt, ct, mt, tt };
  }
  if (!best) return null;

  // Naming the plant is the strongest evidence available: the CNE table has no
  // plant column, so a plant-name hit inside the holder string is a direct tie.
  if (best.pt >= 2) return { ...best, conf: 'alta' };
  if (best.pt === 1 && (best.mt >= 1 || best.tt)) return { ...best, conf: 'alta' };
  // Otherwise a name alone must be corroborated by capacity or technology.
  const nc = Math.max(best.nt, best.ct);
  if (nc >= 2 && best.mt >= 2) return { ...best, conf: 'alta' };
  if (nc === 3 && (best.mt >= 1 || best.tt)) return { ...best, conf: 'alta' };
  if (nc >= 2 && (best.mt >= 1 || best.tt)) return { ...best, conf: 'media' };
  // A single distinctive toponym is weak on its own, so it has to bring BOTH
  // capacity and technology agreement — and it has already survived the unit
  // guard above. This is what links "C.C. Tamazunchale" to TMH Tamazunchale I.
  if (nc === 1 && best.mt >= 1 && best.tt) return { ...best, conf: 'media' };
  return null;
}

const candidates = new Map();
for (const p of atlas.P) {
  const [name, , , mw, tech] = p;
  const m = matchPlant(name, mw, tech, regimen[name] || {});
  if (m) candidates.set(name, m);
  else if (regimen[name]?.spv || regimen[name]?.regimen) stats.descartado++;
}

// One permit authorises one central. When two plants claim the same permit the
// join is ambiguous for at least one of them — keep the better-evidenced plant
// and drop the permit (not the plant) from the other, rather than publishing the
// same expiry twice. Hit this on "Los Humeros III Fase A" vs "Humeros III U-11".
// Iterate a snapshot: deleting from `candidates` while walking it would skip entries.
const claim = new Map();
for (const [name, m] of [...candidates].sort((a, b) => b[1].score - a[1].score)) {
  const holder = claim.get(m.permit.num);
  if (holder === undefined) claim.set(m.permit.num, name);
  else {
    candidates.delete(name);
    stats.duplicado++;
  }
}

const byPlant = {};
for (const p of atlas.P) {
  const [name, , , , , , , owner] = p;
  const own = regimen[name] || {};
  const m = candidates.get(name);

  if (m) {
    const { permit } = m;
    const { vencimiento, base, clausula } = vigenciaDe(permit);
    // A DERIVED expiry already in the past contradicts the source (the CNE lists
    // the permit as in force), so the 30-year guess is wrong there — drop it. A
    // VERIFIED past date is not a contradiction, it is the finding: the permit
    // really has lapsed and the registry simply has not caught up.
    if (vencimiento && base !== 'verificado' && vencimiento < out0.today) {
      byPlant[name] = { mod: permit.mod, modLabel: MODALIDAD[permit.mod] || permit.mod, base: 'sin-permiso', conf: 'baja' };
      stats.vencidoIncoherente++;
      continue;
    }
    stats[base] = (stats[base] || 0) + 1;
    byPlant[name] = {
      clausula,
      mod: permit.mod,
      modLabel: MODALIDAD[permit.mod] || permit.mod,
      num: permit.num,
      marco: permit.marco,
      otorgamiento: permit.otorgamiento,
      vencimiento,
      base,
      titular: permit.titular,
      mw: permit.mw,
      conf: m.conf,
    };
    stats[m.conf]++;
    continue;
  }

  // No permit row. Fall back to a modality so the filter still has a value —
  // but never invent a date for it.
  const fb = REGIMEN_FALLBACK[own.regimen] || (owner === 'CFE' ? 'CFE' : null);
  if (fb) {
    byPlant[name] = { mod: fb, modLabel: MODALIDAD[fb] || fb, base: 'sin-permiso', conf: 'baja' };
    if (fb === 'CFE') stats.cfe++;
    else stats.fallback++;
  } else {
    stats.sinDato++;
  }
}

// ── Emit ──────────────────────────────────────────────────────────────────────
const out = {
  generatedAt: new Date().toISOString().slice(0, 10),
  source: SOURCE,
  termYears: TERM_YEARS,
  modalidades: MODALIDAD,
  notaVigencia:
    'La CNE no publica fecha de vencimiento para permisos vigentes; sólo la fecha de otorgamiento. ' +
    'El vencimiento se deriva del plazo legal de 30 años que fija el título de permiso (Condición TERCERA). ' +
    'base=derivado (LIE/LSE, plazo explícito) · estimado (LSPEE, plazo original variable) · sin-permiso (sin cruce).',
  byPlant,
};
writeFileSync(join(DATA, 'permisos.json'), JSON.stringify(out));

const covered = stats.alta + stats.media;
console.log(`permisos.json      ${Object.keys(byPlant).length}/${atlas.P.length} centrales con tipo de permiso`);
console.log(`  con permiso                ${covered}  (alta ${stats.alta} · media ${stats.media})`);
console.log(`  vigencia: verificada ${stats.verificado||0} · indefinida ${stats.indefinida||0} · derivada ${(stats.derivado||0)+(stats.estimado||0)}`);
console.log(`  sólo modalidad, sin fecha  ${stats.fallback} privadas + ${stats.cfe} CFE`);
console.log(`  sin dato                   ${stats.sinDato}`);
console.log(`  descartados sin corroborar ${stats.descartado} · duplicados ${stats.duplicado} · vencidos incoherentes ${stats.vencidoIncoherente}`);
