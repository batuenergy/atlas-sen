/**
 * Read permit terms out of the CNE Registro Público, one título de permiso at a
 * time, and write scripts/data/permisos-vigencia-titulos.json — the input that
 * lets build-atlas-permisos.mjs publish a READ expiry instead of a derived one.
 *
 *   node scripts/crawl_permit_titles.mjs        (~10 min, ~180 PDFs)
 *
 * Why crawl at all: there is no queryable public dataset of expiry dates. The
 * CNE's monthly table omits the term for permits in force, the Registro
 * Público's own search box is broken (it returns all 29,897 records whatever you
 * type, so you cannot look a permit up by number), and cre.gob.mx — where the
 * legacy electricity titles used to live — no longer resolves. The titles are
 * reachable only by paging the whole registry to learn each permit's internal
 * PermisoId and then constructing the drive.cne.gob.mx URL from it.
 *
 * What the titles say, and why the 30-year default was not good enough:
 *   · 16 name the date outright — "hasta el 1 de abril de 2028"
 *   · 25 say "duración indefinida": those permits never expire
 *   · legacy PIE titles run 26y11m–28y, so real dates land YEARS earlier
 *
 * Nothing here guesses. A clause that does not parse is left unresolved and the
 * verbatim text is kept so a human can adjudicate it.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = join(__dirname, '..', 'data', 'sources');
const CACHE = join(__dirname, '..', 'data', '.permit-titles');
const API = 'https://api-creweb.cne.gob.mx/api/Permisos/ObtenerPermisosPaginados';
const PAGE = 500;

// ── 1. Index the registry: permit number → internal PermisoId ─────────────────
async function buildIndex() {
  const idx = {};
  let total = Infinity;
  for (let start = 0; start < total; start += PAGE) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const r = await fetch(API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json; charset=utf-8', Origin: 'https://www.cne.gob.mx', 'User-Agent': 'Mozilla/5.0' },
          body: JSON.stringify({ parameters: { draw: 1, start, length: PAGE, search: { value: '', regex: false }, order: [], columns: [] } }),
        });
        const d = await r.json();
        total = d.recordsTotal;
        for (const row of d.data) if (row.Numero) idx[row.Numero.trim()] = row.PermisoId;
        break;
      } catch {
        await new Promise((res) => setTimeout(res, 1500));
      }
    }
  }
  console.log(`índice del registro: ${Object.keys(idx).length} permisos`);
  return idx;
}

// ── 2. Parse the term clause ─────────────────────────────────────────────────
const MES = { enero: 1, febrero: 2, marzo: 3, abril: 4, mayo: 5, junio: 6, julio: 7, agosto: 8, septiembre: 9, setiembre: 9, octubre: 10, noviembre: 11, diciembre: 12 };
const WORDS = { uno: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10, once: 11, doce: 12, trece: 13, catorce: 14, quince: 15, dieciseis: 16, diecisiete: 17, dieciocho: 18, diecinueve: 19, veinte: 20, veintiuno: 21, veintidos: 22, veintitres: 23, veinticuatro: 24, veinticinco: 25, veintiseis: 26, veintisiete: 27, veintiocho: 28, veintinueve: 29, treinta: 30, 'treinta y cinco': 35 };
const deaccent = (s) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '');
const numOf = (t) => {
  const s = deaccent(String(t).trim().toLowerCase());
  return /^\d+$/.test(s) ? Number(s) : (WORDS[s] ?? null);
};

export function readTerm(txt) {
  const flat = deaccent(txt).replace(/\s+/g, ' ');
  const m = flat.match(/(?:plazo del permiso|vigencia del permiso|vigencia)\.?\s*(.{0,420})/i);
  if (!m) return null;
  const clausula = m[1].slice(0, 220).trim();

  const ex = clausula.match(/hasta el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})/i);
  if (ex && MES[ex[2].toLowerCase()]) {
    const mm = String(MES[ex[2].toLowerCase()]).padStart(2, '0');
    return { fecha: `${ex[3]}-${mm}-${String(ex[1]).padStart(2, '0')}`, via: 'fecha-explicita', clausula };
  }
  // `duracion | indefinida` — the pipe is an OCR artifact from the scan's rule line.
  if (/duracion\s*\|?\s*indefinida|vigencia indefinida/i.test(clausula)) return { indefinida: true, via: 'indefinida', clausula };
  // A handful tie the permit to the interconnection contract rather than to a
  // term, so there is no date to publish either.
  if (/misma duracion que el Contrato/i.test(clausula)) return { indefinida: true, via: 'ligada-a-contrato-interconexion', clausula };

  const y = clausula.match(/(?:duracion|vigencia|plazo)\s+(?:sera\s+)?(?:de|es)?\s*(?:hasta\s+)?(?:por\s+)?([a-z]+(?:\s+y\s+[a-z]+)?|\d+)\s*(?:\([^)]*\)\s*)?anos/i)
    || clausula.match(/([a-z]+(?:\s+y\s+[a-z]+)?|\d+)\s*(?:\([^)]*\)\s*)?anos/i);
  const anios = y ? numOf(y[1]) : null;
  if (!anios) return { via: 'no-resuelto', clausula };
  const mo = clausula.match(/y\s+([a-z]+|\d+)\s+mes(?:es)?/i);
  return { anios, meses: mo ? (numOf(mo[1]) ?? 0) : 0, via: 'plazo', clausula };
}

// ── 3. Fetch + read each title ───────────────────────────────────────────────
const hex = () => Math.floor(Math.random() * 16).toString(16);
// The registry links a title by base64 of a synthetic UUID carrying PermisoId in
// its fourth group — mirrors how the page's own DataTable builds the href.
const titleUrl = (id) =>
  'https://drive.cne.gob.mx/Drive/ObtenerPermiso/?id=' +
  encodeURIComponent(Buffer.from(('xxxxxxxx-xxxx-4xxx-' + id + '-xxxxxxxxxxxx').replace(/x/g, hex)).toString('base64'));

/**
 * OCR a scanned title (needs `brew install tesseract tesseract-lang`). Returns
 * '' when the toolchain is missing so the crawl degrades to "unresolved" rather
 * than dying — a missing date is recoverable, a wrong one is not.
 */
function ocr(pdf, base) {
  try {
    execFileSync('pdftoppm', ['-r', '300', '-gray', '-f', '1', '-l', '12', '-png', pdf, join(CACHE, base)], { stdio: 'ignore' });
  } catch { return ''; }
  let txt = '';
  for (let p = 1; p <= 12; p++) {
    for (const pad of [String(p), String(p).padStart(2, '0')]) {
      const img = join(CACHE, `${base}-${pad}.png`);
      if (!existsSync(img)) continue;
      try {
        txt += execFileSync('tesseract', [img, 'stdout', '-l', 'spa', '--psm', '6'], { stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 40e6 }).toString();
      } catch { /* tesseract not installed → leave unresolved */ }
      try { execFileSync('rm', ['-f', img]); } catch { /* best effort */ }
    }
  }
  return txt;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (!existsSync(CACHE)) mkdirSync(CACHE, { recursive: true });
  const idx = await buildIndex();

  // Target the permits the atlas actually shows, plus every PIE permit — the
  // legacy independent-power fleet is where the terms deviate most from 30 years.
  const snapshot = JSON.parse(readFileSync(join(SRC, 'permisos-cne-jul26.json'), 'utf8'));
  const dataset = new Set(Object.values(JSON.parse(readFileSync(join(__dirname, '..', 'public', 'data', 'permisos.json'), 'utf8')).byPlant).map((v) => v.num).filter(Boolean));
  for (const p of snapshot) if (p.mod === 'P.I.E.') dataset.add(p.num);
  const targets = [...dataset].filter((n) => idx[n]).sort();

  const out = {};
  const skipped = [];
  let n = 0;
  for (const num of targets) {
    const base = num.replace(/\//g, '_');
    const pdf = join(CACHE, `${base}.pdf`);
    try {
      if (!existsSync(pdf)) {
        const res = await fetch(titleUrl(idx[num]), { headers: { 'User-Agent': 'Mozilla/5.0' } });
        if (!res.ok) { skipped.push([num, 'HTTP ' + res.status]); continue; }
        const buf = Buffer.from(await res.arrayBuffer());
        if (buf.subarray(0, 4).toString() !== '%PDF') { skipped.push([num, 'no es PDF']); continue; }
        writeFileSync(pdf, buf);
      }
      let txt = execFileSync('pdftotext', ['-layout', pdf, '-'], { maxBuffer: 40e6 }).toString();
      // Scanned titles have no text layer — OCR them. The term clause sits deep
      // in the CONDICIONES block (page 4+ on the autoabastecimiento templates),
      // so a first-pages-only pass misses it and reports a false "no clause".
      if (txt.replace(/\s/g, '').length < 400) txt = ocr(pdf, base);
      if (!txt || txt.replace(/\s/g, '').length < 400) { skipped.push([num, 'escaneado y OCR sin texto']); continue; }
      const t = readTerm(txt);
      if (t && t.via !== 'no-resuelto') out[num] = t;
      else skipped.push([num, 'cláusula no parseada']);
    } catch (e) {
      skipped.push([num, String(e.message).slice(0, 60)]);
    }
    if (++n % 25 === 0) console.log(`  ${n}/${targets.length}`);
  }

  writeFileSync(join(SRC, 'permisos-vigencia-titulos.json'), JSON.stringify(out, null, 0));
  const by = (v) => Object.values(out).filter((x) => x.via === v).length;
  console.log(`\ntítulos resueltos: ${Object.keys(out).length}/${targets.length}`);
  console.log(`  fecha explícita ${by('fecha-explicita')} · plazo ${by('plazo')} · indefinida ${by('indefinida')}`);
  console.log(`  sin resolver ${skipped.length} (${[...new Set(skipped.map((s) => s[1]))].join(', ')})`);
}
