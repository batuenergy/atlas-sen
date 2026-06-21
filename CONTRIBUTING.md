# Contributing

Thanks for helping improve the Atlas de Red SEN.

## Ground rules
- The runtime stays **dependency‑free** (vanilla JS + Leaflet). Don't add a framework or a
  required build step to view the map.
- **Never commit data from proprietary sources** (e.g. Google Maps geocoding). Coordinates
  must come from OpenStreetMap / Nominatim or another openly‑licensed source. See `DATA-LICENSE.md`.
- Keep data and code changes in separate PRs where possible.

## Dev setup
```bash
make setup
make data      # or grab prebuilt data/derived if you only touch the UI
make build && make serve
make test
```

## Good first issues
- Improve substation ↔ OSM `power=substation` matching (raise the geocode match rate).
- Backfill missing 115–161 kV transmission edges from the schematic topology.
- New layers (see open issues) — clean‑energy zones, gas pipelines, load zones.

## PR checklist
- [ ] `make lint` and `make test` pass
- [ ] If you added/changed data, updated `data/SOURCES.md` (source + license + script)
- [ ] If it's user‑visible, added/updated a Playwright regression test
- [ ] No proprietary‑sourced data committed

By contributing you agree your code is MIT‑licensed and any data you add is compatible with
`DATA-LICENSE.md`.
