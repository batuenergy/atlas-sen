# Data sources & provenance

Every dataset shipped in this repo, where it comes from, its license, and the script
that produces it. Reproduce any of it with `make data`.

| File (in `public/data/`) | Description | Upstream source | License | Produced by |
|---|---|---|---|---|
| `plants.json` | Generation plants: name, source, MW, owner, market, COD | CENACE single‑line diagrams (extracted) + ownership research | CC‑BY 4.0 | `scripts/extract_grid.py` |
| `substations.json` | 400/230 kV substations: kV, transformer MVA, generation, saturation | CENACE single‑line diagrams (extracted) | CC‑BY 4.0 | `scripts/extract_grid.py` |
| `coordinates.json` | lat/lng for plants & substations | Geocoded via **Google Maps Platform** (proprietary) | © Google — **not** openly licensed; **not committed** here, served at runtime from a Batu endpoint | (internal) |
| `lines.json` | Transmission & sub‑transmission line geometry (69–400 kV) | **OpenStreetMap** (`power=line`, Overpass) | **ODbL 1.0** | `scripts/fetch_osm_lines.py` |
| `osm_substations.json` | Distribution & sub‑transmission substations (≤161 kV) with real coordinates | **OpenStreetMap** (`power=substation`, Overpass) | **ODbL 1.0** | `scripts/fetch_osm_substations.py` |
| `cfe_rgd_by_division.json` | Per‑division distribution‑substation count + transformer MVA | CFE Distribución — *Valores de Corto Circuito de las RGD* (extracted) | CC‑BY 4.0 | `scripts/fetch_rgd_substations.py` |
| `edges.json` | Substation‑to‑substation topology (schematic) | CENACE single‑line diagrams (extracted) | CC‑BY 4.0 | `scripts/extract_grid.py` |
| `regions.json` | CENACE control‑region polygons (7 SIN + BCA/BCS/Mulegé) | INEGI/CONABIO municipio geometry + region assignment | CC‑BY 4.0 | `scripts/dissolve_regions.py` |
| `tariff_divisions.json` | CFE 17 tariff‑division polygons | DOF acuerdo (municipio→división) + INEGI geometry | CC‑BY 4.0 | `scripts/dissolve_divisions.py` |
| `state_polys.json` | 32 state (entidad federativa) polygons | INEGI/CONABIO 2020 municipio geometry (dissolved) | CC‑BY 4.0 | `scripts/dissolve_states.py` |
| `osm_plants.json` | OSM `power=plant` cache, used to re‑source plant coordinates from open data | **OpenStreetMap** (`power=plant`, Overpass) | **ODbL 1.0** | `scripts/regeocode_plants_osm.mjs` |
| `projects.json` | CFE generation projects under construction / planning (name, MW, tech, status, COD) | CFE *Plan de Fortalecimiento y Expansión del SEN 2025–2030* | CC‑BY 4.0 (public sector) | curated |
| `transmission.json` | Planned transmission lines & substations (kV, km, status) | CFE *Plan SEN 2025–2030* + *Proyectos México* per‑project catalog; coordinates via SEMARNAT MIA / municipio geocode | CC‑BY 4.0 (public sector) | curated |
| `international_ties.json` | International interconnections (MX↔US/Guatemala/Belize): cross‑border tie geometry with voltage, transfer capacity, sync/async technology & flow direction | **OpenStreetMap** (`power=line`, Overpass — 4 of 6 crossings mapped MX‑side) + attributes from CENACE/WECC/EOR + OAS/CFE (Duque 2007) | **ODbL 1.0** (geometry) + CC‑BY (attributes) | curated |
| `private_generation.json` | Private renewable projects approved in CNE/SENER *Atención Prioritaria / Planeación Vinculante* (1st call, Dec 2025) — the private‑developer pipeline | CNE results doc (count/status/zone, anonymized folios) + press (name/developer/MW) + SEMARNAT MIA (coordinates) | CC‑BY 4.0 (public sector) + press attribution | curated |
| `dg_by_size.json`, `dg_by_state.json` | Distributed‑generation installed capacity (MW) + contracts, by size bucket × year and by state × semester | CNE/CRE *Estadísticas de GD / generación exenta* (RES/142/2017) + datos.gob.mx | CC‑BY 4.0 | `scripts/fetch_dg.py` |
| `cfe_users_ts.json`, `cfe_energy_ts.json` | Estimated users & energy sales (MWh) by tarifa × división × year | CNE *Memorias de cálculo de las tarifas de operación / finales del Suministro Básico* | CC‑BY 4.0 | `scripts/fetch_cfe_tarifa_ts.py` |
| `permisos.json` | Plant → permit modality, number, grant date and expiry (`base` records whether the date was read from the título, is indefinite, or fell back to the 30-year term) | **CNE** *Lista de permisos otorgados de generación* (monthly XLSX) + each permit's **título** from the CNE Registro Público | CC‑BY 4.0 (public sector) | `scripts/build_permisos.mjs` (titles via `scripts/crawl_permit_titles.mjs`) |
| `timeseries.json` | Generation capacity by source by year (1960–2026) | Derived from `plants.json` COD | CC‑BY 4.0 | `scripts/build_timeseries.py` |
| `demand/today.json`, `demand/history/*.json` | Semi‑real‑time demand/generation/forecast per region | CENACE `GraficaDemanda.aspx` | Public (attribute CENACE) | `scripts/fetch_demand.py` (scheduled) |

## Raw inputs (`data/sources/`)

| File | Description | Source |
|---|---|---|
| `unifilares/` | Region extractions from the CENACE single‑line diagram PDFs | CENACE (public) |
| `cfe_muni_division.json` | Parsed DOF municipio→tariff‑division table | DOF acuerdo 5783862 |
| `ownership.json` | Plant → parent company / market / regime | Public registries + research |
| `permisos-cne-jul26.json` | Normalized snapshot of the CNE's granted‑generation‑permit table (1,038 permits in force, 122.9 GW) | CNE (public, CC‑BY) |
| `permisos-vigencia-titulos.json` | Term clause read out of each permit's **título**, verbatim, plus how it was resolved (`fecha-explicita` / `plazo` / `indefinida`) | CNE Registro Público (`drive.cne.gob.mx`) |

## Notes on coordinates

`coordinates.json` is **not part of the open dataset and is not committed to this repo.**
The coordinates were geocoded with a proprietary service (Google Maps Platform), whose terms
restrict open redistribution. The live map loads them at runtime from a Batu‑hosted endpoint
(`PUBLIC_COORDS_URL`); the open pipeline runs against whatever coordinate file is provided.

To make the dataset **fully self‑contained / open**, re‑source coordinates from OpenStreetMap:
match substation names to OSM `power=substation` within the expected state, fall back to
Nominatim (`"<name>, <state>, México"`), and flag unmatched nodes for review. This is tracked
as a good first contribution.

**Plants: partially done.** `scripts/regeocode_plants_osm.mjs` re‑sources plant coordinates
from OSM `power=plant` (fuel‑type‑constrained, name‑similarity + distance‑gated match against
the `osm_plants.json` cache), snapping matched plants to community‑verified footprints and
flagging still‑stacked, unmatched plants as approximate. Substations are the remaining
open‑coordinate gap.

**Regenerating `public/data/osm_plants.json`** (the committed Overpass cache): run
`OSM_REFETCH=1 node scripts/regeocode_plants_osm.mjs`, which re‑queries Overpass with

```
[out:json][timeout:180];
( node["power"="plant"](14.0,-118.6,33.0,-86.0);
  way["power"="plant"](14.0,-118.6,33.0,-86.0);
  relation["power"="plant"](14.0,-118.6,33.0,-86.0); );
out center tags;
```

(Mexico bbox; ODbL, © OpenStreetMap contributors). It's a large raw export, so refresh it
deliberately — only when re‑geocoding — and expect a big diff. Without `OSM_REFETCH` the script
reuses the committed cache.
