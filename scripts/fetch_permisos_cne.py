"""Fetch the CNE's monthly generation-permit table and normalize it into
data/sources/permisos-cne.json — the snapshot build_permisos.mjs reads.

    python scripts/fetch_permisos_cne.py            (or: make permisos-fetch)
    python scripts/fetch_permisos_cne.py --xlsx E4_Tabla_p_blica_Sep26.xlsx

The CNE publishes the table once a month on its statistics page as
"E4_Tabla_p_blica_<Mes><AA>.xlsx". The cut date is read from the sheet's own
"Actualización: …" header, not from the filename, and travels in
permisos-cne.meta.json so the map can cite it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import json
import re
import sys
from pathlib import Path

import openpyxl
import requests

PAGE = "https://www.gob.mx/cne/documentos/estadisticas-e-informacion-en-materia-de-permisos-de-electricidad"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sources" / "permisos-cne.json"
META = ROOT / "data" / "sources" / "permisos-cne.meta.json"
SHEET = "Permisos Vigentes"
UA = {"User-Agent": "Mozilla/5.0 (atlas-sen; +https://github.com/batuenergy/atlas-sen)"}

MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
     "agosto", "septiembre", "octubre", "noviembre", "diciembre"], 1)}

# Header text in the CNE sheet → snapshot field. Matched on the header, not the
# position, because the CNE has added columns before (Entidad Federativa).
COLUMNS = {
    "Número de Permiso": "num",
    "Permisionario": "titular",
    "Marco Legal Aplicable": "marco",
    "Modalidad": "mod",
    "Fecha de Otorgamiento": "otorgamiento",
    "Capacidad Autorizada (MW)": "mw",
    "Entidad Federativa": "entidad",
    "Municipio": "municipio",
    "Tecnología": "tecnologia",
    "Estado Actual": "estado",
    "Fecha de Entrada en Operación": "operacion",
}
REQUIRED = {"num", "titular", "mod", "otorgamiento", "mw"}


def find_xlsx_url() -> str:
    page = requests.get(PAGE, headers=UA, timeout=60)
    page.raise_for_status()
    urls = re.findall(r'href="([^"]*E4_Tabla[^"]*\.xlsx)"', page.text)
    if not urls:
        sys.exit(f"no E4_Tabla*.xlsx link on {PAGE} — did the CNE rename it?")
    url = urls[0]
    return url if url.startswith("http") else "https://www.gob.mx" + url


def text(v) -> str:
    # Inner spacing is kept as published: build_permisos.mjs keys plants off the
    # holder string, and collapsing it moves matches.
    return html.unescape(str(v)).strip() if v is not None else ""


def iso(v) -> str | None:
    # The CNE fills unknown operation dates with 1900-01-01.
    if isinstance(v, dt.datetime) and v.year > 1900:
        return v.date().isoformat()
    return None


def cut_date(ws) -> str:
    for row in ws.iter_rows(max_row=5, values_only=True):
        for cell in row:
            m = re.search(r"Actualizaci[oó]n:\s*(\d{1,2}) de (\w+) de (\d{4})", str(cell or ""))
            if m:
                return dt.date(int(m[3]), MESES[m[2].lower()], int(m[1])).isoformat()
    sys.exit("no 'Actualización: …' header in the sheet")


def normalize(ws) -> list[dict]:
    rows = ws.iter_rows(values_only=True)
    for header in rows:
        if "Número de Permiso" in [text(c) for c in header]:
            break
    else:
        sys.exit("header row not found")
    idx = {COLUMNS[h]: i for i, h in enumerate(text(c) for c in header) if h in COLUMNS}
    if missing := REQUIRED - idx.keys():
        sys.exit(f"columns missing from the CNE sheet: {sorted(missing)}")

    out = []
    for r in rows:
        get = lambda f: r[idx[f]] if f in idx and idx[f] < len(r) else None  # noqa: E731
        # The sheet ends with a modality glossary that has no permit number.
        if not text(get("num")) or not isinstance(get("otorgamiento"), dt.datetime):
            continue
        mw = get("mw")
        out.append({
            "num": text(get("num")),
            "titular": text(get("titular")),
            "marco": text(get("marco")),
            "mod": text(get("mod")),
            "otorgamiento": iso(get("otorgamiento")),
            "mw": mw if isinstance(mw, (int, float)) else None,
            "entidad": text(get("entidad")),
            "municipio": text(get("municipio")),
            "tecnologia": text(get("tecnologia")),
            "estado": text(get("estado")),
            "operacion": iso(get("operacion")),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xlsx", help="local copy of E4_Tabla_p_blica_*.xlsx (skips the download)")
    args = ap.parse_args()

    if args.xlsx:
        url, data = None, Path(args.xlsx).read_bytes()
    else:
        url = find_xlsx_url()
        resp = requests.get(url, headers=UA, timeout=120)
        resp.raise_for_status()
        data = resp.content

    ws = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)[SHEET]
    corte = cut_date(ws)
    permisos = normalize(ws)

    previous = {p["num"] for p in json.loads(OUT.read_text())} if OUT.exists() else set()
    current = {p["num"] for p in permisos}
    OUT.write_text(json.dumps(permisos, ensure_ascii=False, indent=0) + "\n")
    META.write_text(json.dumps({"actualizacion": corte, "url": url or PAGE}, ensure_ascii=False, indent=1) + "\n")

    print(f"permisos-cne.json  {len(permisos)} permisos vigentes · corte {corte}")
    if previous:
        print(f"  altas {len(current - previous)} · bajas {len(previous - current)}")


if __name__ == "__main__":
    main()
