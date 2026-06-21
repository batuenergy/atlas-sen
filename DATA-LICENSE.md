# Data licensing

The **code** in this repository is MIT (see `LICENSE`). The **data** is not — each
dataset keeps the license of the source it derives from. This file explains the
overall picture; `data/SOURCES.md` has the per‑file table.

## Summary

| Data | License | Requirement |
|------|---------|-------------|
| Transmission lines (OpenStreetMap‑derived) | **ODbL 1.0** | Attribute "© OpenStreetMap contributors"; share‑alike applies if you redistribute the **data** |
| Plant/substation coordinates | © Google (proprietary geocoder) | **Not** openly licensed; **not committed** to this repo — loaded at runtime from a Batu‑hosted endpoint. Redistribution restricted by Google Maps Platform Terms |
| Municipio / region / tariff‑division geometry (INEGI / CONABIO) | Public sector ("Libre Uso MX") → published here as **CC‑BY 4.0** | Attribution |
| Grid attributes extracted from CENACE single‑line diagrams (names, kV, MVA, generation, COD) | Public sector → **CC‑BY 4.0** | Attribution to CENACE |
| Tariff‑division ↔ municipio mapping (DOF acuerdo) | Public (DOF) → **CC‑BY 4.0** | Attribution |
| Live demand snapshots (CENACE) | Public sector | Attribute "Fuente: CENACE"; not an official feed |

## Important notes

- **Plant/substation coordinates were produced with a proprietary geocoder (Google Maps
  Platform).** Under Google's terms they may not be openly redistributed, so they are
  **not committed to this repository**; the live map loads them at runtime from a
  Batu‑hosted endpoint. Everything else in `public/data/` is openly licensed. Re‑sourcing
  the coordinates from OpenStreetMap would make the dataset fully self‑contained.
- **ODbL share‑alike** is triggered by redistributing the *data* (e.g. the JSON in
  `public/data/`). A rendered map is a "Produced Work" and only requires attribution.
- This project is **not affiliated with or endorsed by** CENACE, CFE, SENER, or INEGI.
  It is an independent reconstruction from public information and carries no warranty of
  accuracy. See `METHODOLOGY.md` for known limitations.
