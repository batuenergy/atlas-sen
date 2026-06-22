#!/usr/bin/env python3
"""Fetch Mexico high-voltage transmission lines from OpenStreetMap (Overpass) and write
data/derived/osm_lines.json — simplified geometry, tagged by voltage (kV).

Data: © OpenStreetMap contributors, ODbL. The raw Overpass response is cached at
data/sources/osm_raw.json (gitignored) so re-runs don't re-fetch.
"""
import json, re, os, urllib.request, urllib.parse
from shapely.geometry import LineString

RAW = 'data/sources/osm_raw.json'
OUT = 'data/derived/osm_lines.json'
QUERY = ('[out:json][timeout:240];area["ISO3166-1"="MX"][admin_level=2]->.mx;'
         'way["power"="line"]["voltage"](area.mx);out geom;')
TOL = 0.004  # ~330 m simplification

os.makedirs('data/sources', exist_ok=True)
os.makedirs('data/derived', exist_ok=True)

if not os.path.exists(RAW):
    print('fetching Overpass (1-3 min)...')
    req = urllib.request.Request('https://overpass-api.de/api/interpreter',
                                 data=urllib.parse.urlencode({'data': QUERY}).encode(),
                                 headers={'User-Agent': 'atlas-sen/fetch-osm-lines'})
    with urllib.request.urlopen(req, timeout=300) as r:
        open(RAW, 'wb').write(r.read())

def maxkv(v):
    nums = [int(x) for x in re.findall(r'\d+', v or '')]
    return max(nums) // 1000 if nums else 0

raw = json.load(open(RAW))['elements']
OL = []
for w in raw:
    g = w.get('geometry') or []
    if len(g) < 2:
        continue
    kv = maxkv(w.get('tags', {}).get('voltage'))
    if kv < 69:  # include 69-115 kV sub-transmission (connects distribution substations)
        continue
    coords = [(p['lon'], p['lat']) for p in g if p.get('lat') is not None]
    if len(coords) < 2:
        continue
    try:
        cc = list(LineString(coords).simplify(TOL, preserve_topology=False).coords)
    except Exception:
        cc = coords
    if len(cc) < 2:
        continue
    OL.append([kv, [[round(la, 4), round(lo, 4)] for lo, la in cc]])
OL.sort(key=lambda o: o[0])  # higher voltage drawn last (on top)
json.dump(OL, open(OUT, 'w'), separators=(',', ':'))
print(f'HV lines: {len(OL)} -> {OUT}')
