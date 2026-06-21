# Methodology & limitations

This atlas is an independent reconstruction from public data. It favors being useful and
transparent over claiming authority. Here's how each layer is built and where it's soft.

## Grid data (plants, substations, topology)
Extracted from CENACE's single‑line diagrams (*diagramas unifilares*) of the SEN. These
are schematic, not geographic. We extracted, per region: substation names, voltages,
transformer MVA, connected generation, planned works, and substation‑to‑substation
edges. Attributes are as good as the diagrams; expect occasional gaps in small/rural nodes.

## Coordinates
Substation/plant coordinates were geocoded from the extracted names with a proprietary
service (Google Maps Platform). Under Google's terms they are **not** openly redistributable,
so they are **not committed** to this repository — the live map loads them at runtime from a
Batu‑hosted endpoint, and the open pipeline runs against whatever coordinate file is supplied.
A future contribution can re‑source these from OpenStreetMap (`power=substation` + Nominatim
fallback) to make the dataset fully self‑contained and openly licensed.

## Transmission lines
Two flavors:
- **Real geometry** (`lines.json`) — actual routed high‑voltage lines (115–400 kV) from
  OpenStreetMap via Overpass, simplified and tagged by voltage. Coverage of the 230/400 kV
  backbone is strong; 115–161 kV has occasional gaps.
- **Schematic topology** (`edges.json`) — straight connectors between substations derived
  from the diagrams, showing *what connects to what*. Edges longer than 300 km are dropped
  (almost always name‑collision artifacts, not real lines).

## Saturation
`saturación = connected generation (MW) ÷ (transformer capacity MVA × 0.9)`, where 0.9 is a
typical power factor converting MVA→MW. **>1×** means a node/region hosts more generation
than its transformers can step down — a signal of congestion or need for reinforcement.
It is an indicator, not an operational limit.

## Control‑region polygons
CENACE's control regions are defined administratively. We approximate each region's
territory by assigning every INEGI municipio to the region whose substations dominate it
(majority of contained nodes; nearest‑region fallback for empty municipios), then dissolving.
Borders follow real municipal lines but the **assignment is reconstructed**, not the official
DOF circumscription.

## Tariff divisions
CFE's 17 tariff divisions are mapped from the DOF acuerdo's municipio→división table, joined
to INEGI municipio geometry and dissolved. This is authoritative at municipio granularity.

## Live demand
Pulled from CENACE's public `GraficaDemanda.aspx` endpoint per control region: net demand,
net generation, and forecast, hourly, for the current operating day. Measured values exist
only up to the current hour (marked "ahora"); beyond it is forecast. History is accumulated
by snapshotting over time — it cannot be back‑filled from the endpoint. Attribute "Fuente: CENACE".
