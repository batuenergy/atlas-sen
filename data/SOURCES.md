# Data sources & provenance

Every dataset shipped in this repo, where it comes from, its license, and the script
that produces it. Reproduce any of it with `make data`.

| File (in `public/data/`) | Description | Upstream source | License | Produced by |
|---|---|---|---|---|
| `plants.json` | Generation plants: name, source, MW, owner, market, COD | CENACE single‑line diagrams (extracted) + ownership research | CC‑BY 4.0 | `scripts/extract_grid.py` |
| `substations.json` | 400/230 kV substations: kV, transformer MVA, generation, saturation | CENACE single‑line diagrams (extracted) | CC‑BY 4.0 | `scripts/extract_grid.py` |
| `coordinates.json` | lat/lng for plants & substations | Geocoded via **Google Maps Platform** (proprietary) | © Google — **not** openly licensed; **not committed** here, served at runtime from a Batu endpoint | (internal) |
| `lines.json` | High‑voltage transmission line geometry (115–400 kV) | **OpenStreetMap** (`power=line`, Overpass) | **ODbL 1.0** | `scripts/fetch_osm_lines.py` |
| `edges.json` | Substation‑to‑substation topology (schematic) | CENACE single‑line diagrams (extracted) | CC‑BY 4.0 | `scripts/extract_grid.py` |
| `regions.json` | CENACE control‑region polygons (7 SIN + BCA/BCS/Mulegé) | INEGI/CONABIO municipio geometry + region assignment | CC‑BY 4.0 | `scripts/dissolve_regions.py` |
| `tariff_divisions.json` | CFE 17 tariff‑division polygons | DOF acuerdo (municipio→división) + INEGI geometry | CC‑BY 4.0 | `scripts/dissolve_divisions.py` |
| `timeseries.json` | Generation capacity by source by year (1960–2026) | Derived from `plants.json` COD | CC‑BY 4.0 | `scripts/build_timeseries.py` |
| `demand/today.json`, `demand/history/*.json` | Semi‑real‑time demand/generation/forecast per region | CENACE `GraficaDemanda.aspx` | Public (attribute CENACE) | `scripts/fetch_demand.py` (scheduled) |

## Raw inputs (`data/sources/`)

| File | Description | Source |
|---|---|---|
| `unifilares/` | Region extractions from the CENACE single‑line diagram PDFs | CENACE (public) |
| `cfe_muni_division.json` | Parsed DOF municipio→tariff‑division table | DOF acuerdo 5783862 |
| `ownership.json` | Plant → parent company / market / regime | Public registries + research |

## Notes on coordinates

`coordinates.json` is **not part of the open dataset and is not committed to this repo.**
The coordinates were geocoded with a proprietary service (Google Maps Platform), whose terms
restrict open redistribution. The live map loads them at runtime from a Batu‑hosted endpoint
(`PUBLIC_COORDS_URL`); the open pipeline runs against whatever coordinate file is provided.

To make the dataset **fully self‑contained / open**, re‑source coordinates from OpenStreetMap:
match substation names to OSM `power=substation` within the expected state, fall back to
Nominatim (`"<name>, <state>, México"`), and flag unmatched nodes for review. This is tracked
as a good first contribution.
