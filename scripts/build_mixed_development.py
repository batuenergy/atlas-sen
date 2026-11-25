#!/usr/bin/env python3
"""
build_mixed_development.py — CFE "esquemas de desarrollo mixto" (1st call, fallo 2026-06-05)
→ public/data/mixed_development.json.

The only OFFICIAL location attribute of these awards is the CENACE gerencia de control
regional, so the layer is region-anchored: one record per gerencia, placed at the region's
label point from atlas.json (`R` rows: [name, …, lat, lng, …]), carrying its official project
count and the press-reconstructed project list. Never invent per-project coordinates here —
when CFE publishes them, add `lat`/`lng` per project in data/sources/desarrollo-mixto-2026.json.

  python3 scripts/build_mixed_development.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = json.loads((ROOT / "data/sources/desarrollo-mixto-2026.json").read_text())
atlas = json.loads((ROOT / "public/data/atlas.json").read_text())
anchor = {r[0]: (r[3], r[4]) for r in atlas["R"]}

regions = []
for reg, n in src["proyectos_por_gerencia"].items():
    lat, lng = anchor[reg]
    ps = [p for p in src["projects"] if p["reg"] == reg]
    regions.append({"reg": reg, "n": n, "named": len(ps), "mwKnown": round(sum(p.get("mw", 0) for p in ps), 1),
                    "lat": lat, "lng": lng, "projects": [{k: v for k, v in p.items() if k != "reg"} for p in ps]})
named = sum(r["named"] for r in regions)
assert named <= sum(src["proyectos_por_gerencia"].values())
out = {k: v for k, v in src.items() if k != "projects"} | {"regions": regions}
(ROOT / "public/data/mixed_development.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"mixed_development.json  {len(regions)} gerencias · {named}/37 proyectos con nombre")
