#!/usr/bin/env python3
"""
normalize_permisos_xlsx.py — turn the CNE monthly "Lista de permisos otorgados de
generación" workbook (sheet "Permisos Vigentes") into the normalized snapshot that
scripts/build_permisos.mjs and scripts/crawl_permit_titles.mjs read.

  Source page: https://www.gob.mx/cne/documentos/estadisticas-e-informacion-en-materia-de-permisos-de-electricidad
  python3 scripts/normalize_permisos_xlsx.py E4_Tabla_p_blica_Oct26.xlsx \
      --out data/sources/permisos-cne-oct26.json

Output: a JSON array, one object per permit in force —
  {num, titular, marco, mod, otorgamiento, mw, entidad, municipio, tecnologia, estado, operacion}
Dates are ISO (YYYY-MM-DD); the CNE's 1900-01-01 placeholder becomes null.
Needs openpyxl.
"""

import argparse
import datetime as dt
import json
import sys

import openpyxl

HEADERS = {
    "Permisionario": "titular",
    "Marco Legal Aplicable": "marco",
    "Modalidad": "mod",
    "Fecha de Otorgamiento": "otorgamiento",
    "Número de Permiso": "num",
    "Capacidad Autorizada (MW)": "mw",
    "Fecha de Entrada en Operación": "operacion",
    "Tecnología": "tecnologia",
    "Estado Actual": "estado",
    "Entidad Federativa": "entidad",
    "Municipio": "municipio",
}
ORDER = ["num", "titular", "marco", "mod", "otorgamiento", "mw", "entidad", "municipio", "tecnologia", "estado", "operacion"]


def iso(v):
    if isinstance(v, dt.datetime):
        return None if v.year <= 1900 else v.date().isoformat()
    return v or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ws = openpyxl.load_workbook(a.xlsx, read_only=True, data_only=True)["Permisos Vigentes"]
    rows = ws.iter_rows(values_only=True)
    stamp = None
    for r in rows:  # title block, then the header row
        if r and r[2] and str(r[2]).startswith("Actualización"):
            stamp = r[2]
        if r and r[0] == "Num":
            col = {HEADERS[h]: i for i, h in enumerate(r) if h in HEADERS}
            break
    else:
        sys.exit("header row not found")
    missing = set(HEADERS.values()) - set(col)
    if missing:
        sys.exit(f"columns missing: {sorted(missing)}")

    out = []
    for r in rows:
        if not isinstance(r[0], int) or not r[col["titular"]]:
            continue  # footer legend (modalidad glossary) has no running number
        p = {k: r[i] for k, i in col.items()}
        p["num"] = str(p["num"]).strip()
        p["mw"] = float(p["mw"]) if p["mw"] is not None else None
        if p["mw"] is not None and p["mw"].is_integer():
            p["mw"] = int(p["mw"])
        p["otorgamiento"] = iso(p["otorgamiento"])
        p["operacion"] = iso(p["operacion"])
        for k in ("titular", "marco", "mod", "entidad", "municipio", "tecnologia", "estado"):
            p[k] = (p[k] or "").strip()
        out.append({k: p[k] for k in ORDER})

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print(f"{stamp}: {len(out)} permits · {sum(p['mw'] or 0 for p in out):,.1f} MW → {a.out}")


if __name__ == "__main__":
    main()
