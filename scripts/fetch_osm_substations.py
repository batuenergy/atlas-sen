#!/usr/bin/env python3
"""Fetch distribution / sub-transmission substations from OpenStreetMap (ODbL).

Complements the CENACE 400/230 kV transmission substations ("hubs") with the
lower-voltage network: distribution (<=34.5 kV) and sub-transmission (69-161 kV).
Transmission-voltage substations (>=230 kV) are excluded — those are already in
the CENACE hubs layer. Output coordinates are OSM-derived (ODbL), so unlike the
Google-geocoded plant/hub coords they CAN be committed to the public repo.

Usage: python scripts/fetch_osm_substations.py --out data/derived/osm_substations.json
"""
import argparse, json, re, urllib.request, urllib.parse

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="MX"][admin_level=2]->.mx;
(
  node["power"="substation"](area.mx);
  way["power"="substation"](area.mx);
);
out tags center;
"""


def max_voltage(vtag: str) -> int:
    """Largest voltage (in volts) in a tag like '115000;13800'."""
    nums = [int(n) for n in re.findall(r"\d+", vtag or "")]
    return max(nums) if nums else 0


def band(maxv: int):
    """0 = MV/distribution (<=34.5 kV), 1 = sub-transmission (69-161 kV), None = drop."""
    if 0 < maxv <= 34_500:
        return 0
    if 34_500 < maxv <= 161_000:
        return 1
    return None  # no voltage, or >=230 kV (handled by the transmission hubs layer)


def fetch():
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "atlas-sen/osm-substations"})
    return json.load(urllib.request.urlopen(req, timeout=240))["elements"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/derived/osm_substations.json")
    args = ap.parse_args()

    els = fetch()
    seen, subs = set(), []
    for e in els:
        t = e.get("tags") or {}
        maxv = max_voltage(t.get("voltage", ""))
        b = band(maxv)
        if b is None:
            continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lng = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        name = (t.get("name") or "").strip()
        operator = (t.get("operator") or "").strip()
        # dedup co-located duplicates (node + way for the same site)
        key = (round(lat, 4), round(lng, 4), name)
        if key in seen:
            continue
        seen.add(key)
        subs.append([round(lat, 5), round(lng, 5), b, name, operator, t.get("voltage", "")])

    subs.sort(key=lambda s: (-s[2], s[0]))  # sub-transmission first, then by lat (stable)
    n_mv = sum(1 for s in subs if s[2] == 0)
    out = {
        "meta": {
            "source": "OpenStreetMap contributors (ODbL)",
            "license": "https://opendatacommons.org/licenses/odbl/",
            "scope": "power=substation in Mexico, <=161 kV (distribution + sub-transmission)",
            "count": len(subs),
        },
        "fields": ["lat", "lng", "band", "name", "operator", "voltage"],
        "bandLabels": {"0": "Distribución (≤34.5 kV)", "1": "Subtransmisión (69–161 kV)"},
        "subs": subs,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"wrote {args.out}: {len(subs)} substations ({n_mv} distribution, {len(subs)-n_mv} sub-transmission)")


if __name__ == "__main__":
    main()
