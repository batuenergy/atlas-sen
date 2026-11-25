#!/usr/bin/env python3
"""
add_dg_semester.py — append one new CNE distributed-generation semester report to the
committed dg_by_state.json / dg_by_size.json, without re-running the full historical
extraction in fetch_dg.py (which needs a maintainer-only Excel workbook).

Every CNE "Estadísticas de Solicitudes de Interconexión ... menor a 0.7 MW" PDF since
2S-2025 has the same layout:
  * a "SOLICITUDES ATENDIDAS: NACIONAL" per-state table (solicitudes, %, MW, %) — parsed
    with fetch_dg.parse_state_table (it reproduces the committed 2025-H2 values exactly);
  * three per-régimen size tables (Medición Neta / Facturación Neta / Venta Total), with
    rows "0 a 50", "50 a 100", "100 a 250", "250 a 500" kW — summed here across régimenes.

The CNE no longer publishes sub-ranges below 50 kW, so the four atlas buckets
0-5 / 5-10 / 10-30 / 30-50 kW are estimated by splitting the published "0 a 50" total
with the bucket shares of the latest year that has them (same rule used for 2025).
The ≥50 kW buckets and all totals are exact.

Usage:
  python3 scripts/add_dg_semester.py --pdf 2026_S1.pdf --period 2026-H1 --url <pdf url>
  python3 scripts/add_dg_semester.py --text 2026_S1.txt --period 2026-H1 --url <pdf url> [--check]

A mid-year period ("YYYY-H1") is stored in dg_by_size under the key "YYYY-H1"; the map
annualizes the "new" view for it (see `dgSizeSpan` in the Batu atlas renderer).
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_dg  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "public" / "data"
SMALL = ["0-5 kW", "5-10 kW", "10-30 kW", "30-50 kW"]
LARGE = {"50 a 100": "50-100 kW", "100 a 250": "100-250 kW", "250 a 500": "250-500 kW"}
ROW = re.compile(r"^\s*(0 a 50|50 a 100|100 a 250|250 a 500)\s+([\d,]+)\s+[\d.]+\s+([\d,]+\.\d+)\s+[\d.]+\s*$")


def num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_size_tables(text: str) -> dict:
    """Sum the per-régimen size tables → {range: {"n": solicitudes, "mw": MW}}."""
    out: dict = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        r = out.setdefault(m.group(1), {"n": 0, "mw": 0.0})
        r["n"] += int(num(m.group(2)))
        r["mw"] += num(m.group(3))
    for r in out.values():
        r["mw"] = round(r["mw"], 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf")
    src.add_argument("--text", help="pre-extracted `pdftotext -layout` output")
    ap.add_argument("--period", required=True, help="e.g. 2026-H1 or 2026-H2")
    ap.add_argument("--url", required=True, help="public URL of the CNE PDF")
    ap.add_argument("--check", action="store_true", help="parse and print, write nothing")
    a = ap.parse_args()

    text = Path(a.text).read_text() if a.text else fetch_dg.pdf_to_text(a.pdf)
    year, half = a.period.split("-H")

    # ── per state ────────────────────────────────────────────────────────────
    states = fetch_dg.parse_state_table(text, a.period, "state_solicitudes_mw")
    if len(states) != 32:
        sys.exit(f"expected 32 states, parsed {len(states)}")
    st_mw = round(sum(v["mw"] for v in states.values()), 2)
    st_n = sum(v["contratos"] for v in states.values())

    # ── per size ─────────────────────────────────────────────────────────────
    sizes = parse_size_tables(text)
    if set(sizes) != {"0 a 50", *LARGE}:
        sys.exit(f"size tables incomplete: {sorted(sizes)}")
    sz_mw = round(sum(v["mw"] for v in sizes.values()), 2)
    sz_n = sum(v["n"] for v in sizes.values())
    # the two tables are independent views of the same universe — they must agree
    if abs(sz_mw - st_mw) > 0.05 or sz_n != st_n:
        sys.exit(f"state total {st_mw} MW/{st_n} ≠ size total {sz_mw} MW/{sz_n}")
    print(f"{a.period}: 32 states · {st_n:,} solicitudes · {st_mw:,.2f} MW (state and size tables agree)")
    for k, v in sizes.items():
        print(f"  {k:>10} kW  {v['n']:>8,}  {v['mw']:>9,.2f} MW")
    if a.check:
        return

    # ── dg_by_state.json ─────────────────────────────────────────────────────
    ps = json.loads((OUT / "dg_by_state.json").read_text())
    for s, v in states.items():
        ps["byState"][s][a.period] = v
    if a.period not in ps["periods"]:
        ps["periods"].append(a.period)
    ps["periods"].sort(key=lambda p: (int(p[:4]), p[5:]))
    ps["meta"][f"{a.period.replace('-', '_')}_url"] = a.url
    ps["meta"]["latest_period"] = ps["periods"][-1]
    ps["verificationLog"] = [x for x in ps.get("verificationLog", []) if x.get("period") != a.period]
    ps["verificationLog"].append({"period": a.period, "status": "parsed", "sum_mw": st_mw,
                                  "sum_contratos": st_n, "source": a.url,
                                  "check": "per-state sum == per-size sum (3 régimenes)"})
    (OUT / "dg_by_state.json").write_text(json.dumps(ps, ensure_ascii=False, separators=(",", ":")))

    # ── dg_by_size.json ──────────────────────────────────────────────────────
    pz = json.loads((OUT / "dg_by_size.json").read_text())
    key = year if half == "2" else a.period
    ref = next(y for y in reversed(pz["years"]) if y != key)  # latest other year — share basis
    for metric, field in (("capacityMWp", "mw"), ("contracts", "n")):
        tbl = pz[metric]
        small_ref = sum(tbl[b][ref] for b in SMALL)
        tot = sizes["0 a 50"][field]
        parts = [tot * tbl[b][ref] / small_ref for b in SMALL]
        if field == "n":  # integer split that still sums exactly to the published total
            parts = [int(round(p)) for p in parts]
            parts[0] += tot - sum(parts)
        else:
            parts = [round(p, 2) for p in parts]
        for b, p in zip(SMALL, parts):
            tbl[b][key] = p
        for rng, b in LARGE.items():
            tbl[b][key] = sizes[rng][field]
    pz["capacityMWp_total"][key] = sz_mw
    pz["contracts_total"][key] = sz_n
    if key not in pz["years"]:
        pz["years"].append(key)
    pz["meta"]["coverage"] = f"2018–{pz['years'][-1]}"
    pz["meta"][f"note_{key}"] = (
        f"{key} = CNE, Estadísticas GD {half}S-{year} ({'acumulado a jun' if half == '1' else 'acumulado a dic'}-{year}). "
        f"Totales y bandas ≥50 kW exactos (suma de los 3 regímenes); el desglose <50 kW se estima "
        f"con la proporción de {ref}. Solicitudes atendidas (la CNE ya no distingue contratos)."
    )
    pz["meta"][f"{key}_url"] = a.url
    (OUT / "dg_by_size.json").write_text(json.dumps(pz, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote dg_by_state.json ({a.period}) and dg_by_size.json ({key}, <50 kW split by {ref})")


if __name__ == "__main__":
    main()
