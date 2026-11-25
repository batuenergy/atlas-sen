#!/usr/bin/env python3
"""
dg_basis.py — make the distributed-generation series comparable across the CNE's
change of basis, without rewriting any published per-state value.

Two facts from the CNE 1S-2026 report (data/sources: see --report-url):

1. BASIS CHANGE. Through 2S-2024 the CRE/CNE tables were GD + SIPyME (the 2007–Q1-2017
   small/medium-scale contracts, frozen at 247.59 MW / 29,556 since 2017). From 2S-2025
   on the per-state and per-size tables are GD only. Subtracting the two published
   cumulative values across that boundary under-states that year's additions by ~248 MW.
   The CNE does not publish SIPyME by state or by size band, so:
     * the national total is exact (247.59 MW / 29,556);
     * per state it is ESTIMATED with each state's share of the 2019-H2 fleet (the oldest
       per-state cut we have, when SIPyME was still ~25% of all DG);
     * per size band it is ESTIMATED with the 2018 band shares.
   The renderer and the facts use `meta.sipyme` ONLY to convert the pre-boundary value
   when computing a delta across the boundary; cumulative values stay as published.

2. RESTATEMENT. The 1S-2026 report restates the national GD totals with late CFE data:
   2024 = 4,202.73 MW / 488,573 and 2025 = 5,228.00 MW / 602,330 (were 4,200.33 and
   5,189.71 / 600,651). Only national totals are restated — not states, not bands — so
   the 2025 size bands are rescaled proportionally to the restated total and the
   per-state 2025-H2 values are left as published.

Also records the CNE 1S-2025 national figures (the PDF is no longer listed by the CNE;
figures as reported by the press), so the map can show a year-on-year comparison.

  python3 scripts/dg_basis.py
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "public" / "data"
SIP_MW, SIP_N = 247.59, 29556
BOUNDARY = {"through": "2024", "from": "2025"}  # last GD+SIPyME year-end / first GD-only
RESTATED_2025 = {"mw": 5228.00, "n": 602330}
REPORT_URL = "https://www.gob.mx/cms/uploads/attachment/file/1114039/2026_Semestre_1_Generaci_n_Distribuida.pdf"
H1_2025 = {
    "mw": 4504.23, "solicitudes": 528499,
    "nota": "GD atendida al 30-jun-2025 (medición neta 4,429.90 + facturación neta 71.11 + venta total 3.22 MW), "
            "según el reporte CNE 1S-2025 citado por la prensa; cifra NO reexpresada (el PDF ya no está en el portal de la CNE).",
    "src": "https://energiaestrategica.com/energiaestrategica/es/notes/la-cne-acumula-47-gw-en-solicitudes-y-consolida-el-avance-de-la-generacion-distribuida-en-mexico",
}
# National GD cumulative at 30-jun of each year, so the map can compare ene–jun against
# ene–jun. Only national totals exist for mid-year cuts (no size bands before 2026).
# basis: "gd+sipyme" through 2024, "gd" from 2025 (see BASIS CHANGE above).
# n = None where the source gives MW only. 2026 comes from the size tables themselves.
H1_NATIONAL = {
    "2020": {"mw": 1196.52, "n": 165528, "basis": "gd+sipyme",
             "src": "CRE, Estadísticas GD 1S-2020 (tabla por estado; public/data/dg_by_state.json 2020-H1)"},
    "2021": {"mw": 1817.09, "n": None, "basis": "gd+sipyme",
             "nota": "2S-2020 (1,571.09 MW) + 246 MW instalados en ene–jun 2021 según la CRE citada por la prensa.",
             "src": "https://energiaestrategica.com/energiaestrategica/es/notes/la-generacion-distribuida-en-mexico-crecio-246-mw-durante-primer-semestre-de-2021"},
    "2022": {"mw": 2307.44, "n": 300624, "basis": "gd+sipyme",
             "src": "CRE, Estadísticas GD 1S-2022 (tabla por estado; public/data/dg_by_state.json 2022-H1)"},
    "2023": {"mw": 2954.65, "n": None, "basis": "gd+sipyme",
             "nota": "1S-2024 (3,891.22 MW) − 936.57 MW de crecimiento anual reportado por la CRE.",
             "src": "https://energiaadebate.com/aumenta-31-capacidad-instalada-en-generacion-distribuida"},
    "2024": {"mw": 3891.22, "n": 460896, "basis": "gd+sipyme",
             "src": "https://factorenergetico.mx/generacion-distribuida-suma-inversiones-de-5200-mdd-y-una-capacidad-instalada-de-3891-mw-al-primer-semestre-de-2024"},
    "2025": {"mw": H1_2025["mw"], "n": H1_2025["solicitudes"], "basis": "gd", "nota": H1_2025["nota"], "src": H1_2025["src"]},
}


def split(total, weights, integer=False):
    s = sum(weights.values())
    parts = {k: total * w / s for k, w in weights.items()}
    if not integer:
        return {k: round(v, 2) for k, v in parts.items()}
    r = {k: int(round(v)) for k, v in parts.items()}
    r[max(r, key=r.get)] += total - sum(r.values())
    return r


def main():
    # ── state ────────────────────────────────────────────────────────────────
    ps = json.loads((OUT / "dg_by_state.json").read_text())
    base = "2019-H2"
    mw = split(SIP_MW, {s: v[base]["mw"] for s, v in ps["byState"].items()})
    n = split(SIP_N, {s: v[base]["contratos"] for s, v in ps["byState"].items()}, integer=True)
    ps["meta"]["basis"] = {
        "gd_mas_sipyme_hasta": "2024-H2", "solo_gd_desde": "2025-H2",
        "nota": "Hasta 2S-2024 las tablas por estado suman GD + SIPyME; desde 2S-2025 sólo GD. "
                "Para calcular altas a través del cambio, se resta SIPyME del periodo anterior (estimado por estado).",
    }
    ps["meta"]["sipyme"] = {"mw": SIP_MW, "n": SIP_N, "estimado_por": f"participación de cada estado en {base}",
                            "byState": {s: {"mw": mw[s], "n": n[s]} for s in mw}}
    ps["meta"]["restatement_2025"] = ("El reporte 1S-2026 reexpresa sólo el total nacional de 2025 (5,228.00 MW); "
                                      "los valores por estado de 2025-H2 se conservan como se publicaron (suma 5,189.71 MW).")
    (OUT / "dg_by_state.json").write_text(json.dumps(ps, ensure_ascii=False, separators=(",", ":")))

    # ── size ─────────────────────────────────────────────────────────────────
    pz = json.loads((OUT / "dg_by_size.json").read_text())
    bands = list(pz["capacityMWp"])
    for metric, key, tot in (("capacityMWp", "mw", "capacityMWp_total"), ("contracts", "n", "contracts_total")):
        cur = {b: pz[metric][b]["2025"] for b in bands}
        new = split(RESTATED_2025[key], cur, integer=(key == "n"))
        for b in bands:
            pz[metric][b]["2025"] = new[b]
        pz[tot]["2025"] = RESTATED_2025[key]
    sip_mw = split(SIP_MW, {b: pz["capacityMWp"][b]["2018"] for b in bands})
    sip_n = split(SIP_N, {b: pz["contracts"][b]["2018"] for b in bands}, integer=True)
    pz["meta"]["basis"] = {
        "gd_mas_sipyme_hasta": BOUNDARY["through"], "solo_gd_desde": BOUNDARY["from"],
        "nota": "2018–2024 = GD + SIPyME; desde 2025 sólo GD (CNE). Las altas a través del cambio restan SIPyME del año anterior.",
    }
    pz["meta"]["sipyme"] = {"mw": SIP_MW, "n": SIP_N, "estimado_por": "proporción por banda de 2018",
                            "byBand": {b: {"mw": sip_mw[b], "n": sip_n[b]} for b in bands}}
    pz["meta"]["note_2025"] = ("2025 = total nacional reexpresado por la CNE en el reporte 1S-2026 (5,228.00 MW · 602,330 solicitudes, "
                               "sólo GD); bandas reescaladas proporcionalmente desde el 2S-2025 (el CNE no reexpresa por banda; <50 kW "
                               "estimado con la proporción de 2024).")
    pz["meta"]["2025_restated_url"] = REPORT_URL
    pz["meta"]["prevYearH1"] = {"2025-H1": H1_2025}
    pz["meta"]["h1National"] = {
        "nota": "Acumulado nacional al 30-jun de cada año (sólo total: no hay desglose por tamaño de cortes de mitad de año "
                "antes de 2026). Las altas ene–jun se miden contra el cierre del año anterior; a través del cambio de base "
                "se resta SIPyME. 2026 = reporte CNE 1S-2026 contra el 2025 reexpresado (5,228.00 MW); con el 2025 sin "
                "reexpresar (5,189.71 MW) serían 485.8 MW.",
        "years": {**H1_NATIONAL, "2026": {"from": "2026-H1", "basis": "gd", "src": REPORT_URL}},
    }
    tag = " Periodo parcial (ene–jun): no se anualiza."
    pz["meta"]["note_2026-H1"] = pz["meta"].get("note_2026-H1", "").replace(tag, "") + tag  # idempotent
    (OUT / "dg_by_size.json").write_text(json.dumps(pz, ensure_ascii=False, separators=(",", ":")))

    gd25 = RESTATED_2025["mw"]
    print(f"2025 additions (GD basis): {gd25 - (pz['capacityMWp_total']['2024'] - SIP_MW):,.1f} MW")
    print(f"2026 ene–jun: {pz['capacityMWp_total']['2026-H1'] - gd25:,.2f} MW · "
          f"2025 ene–jun: {H1_2025['mw'] - (pz['capacityMWp_total']['2024'] - SIP_MW):,.1f} MW")
    T = pz["capacityMWp_total"]
    for y, v in H1_NATIONAL.items():
        prev = T[str(int(y) - 1)] - (SIP_MW if v["basis"] == "gd" and int(y) - 1 <= int(BOUNDARY["through"]) else 0)
        print(f"  ene–jun {y}: {v['mw'] - prev:,.1f} MW")


if __name__ == "__main__":
    main()
