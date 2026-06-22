#!/usr/bin/env python3
"""Dissolve INEGI/CONABIO 2020 municipio geometry into 32 state polygons.

Each upstream file (PhantomInsights/mexico-geojson · 2020/states/<State>.json) is one
state's municipios; we union + simplify each into a single state outline and key it by
the canonical state name used in data/public/dg_by_state.json so the DG choropleth joins
1:1. Output: public/data/state_polys.json  (same {name:[[[lat,lng],...]],...} shape as
region_polys / cfe_division_polys). Streams downloads (does not keep the ~150 MB on disk).

Source: github.com/PhantomInsights/mexico-geojson (INEGI/CONABIO 2020). Open gov data.
Usage: python scripts/dissolve_states.py
"""
import json, os, urllib.request, urllib.parse
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

TREE = 'https://api.github.com/repos/PhantomInsights/mexico-geojson/git/trees/main?recursive=1'
BASE = 'https://raw.githubusercontent.com/PhantomInsights/mexico-geojson/main/'
# INEGI filename (sans .json) -> canonical name used in dg_by_state.json
RENAME = {
    'Coahuila de Zaragoza': 'Coahuila',
    'Michoacán de Ocampo': 'Michoacán',
    'Veracruz de Ignacio de la Llave': 'Veracruz',
    'México': 'Estado de México',
}
SIMPLIFY = 0.02      # deg — national-zoom choropleth
MIN_AREA = 0.012     # deg^2 — drop tiny islands/slivers


def ring_ll(coords):
    return [[round(c[1], 4), round(c[0], 4)] for c in coords]


def shoe(r):
    a = 0.0
    for i in range(len(r) - 1):
        a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return abs(a) / 2


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'atlas-sen/dissolve-states'})
    return urllib.request.urlopen(req, timeout=120).read()


def main():
    tree = json.loads(get(TREE))['tree']
    paths = sorted(t['path'] for t in tree
                   if t['path'].startswith('2020/states/') and t['path'].endswith('.json'))
    out = {}
    for p in paths:
        fname = os.path.basename(p)[:-5]
        name = RENAME.get(fname, fname)
        gj = json.loads(get(BASE + urllib.parse.quote(p)))
        geoms = []
        for ft in gj.get('features', []):
            try:
                geoms.append(shape(ft['geometry']).buffer(0))
            except Exception:
                pass
        if not geoms:
            print('  ! no geometry for', name); continue
        u = unary_union(geoms).simplify(SIMPLIFY, preserve_topology=True)
        gj2 = mapping(u)
        raw = gj2['coordinates'] if gj2['type'] == 'MultiPolygon' else [gj2['coordinates']]
        raw = sorted(raw, key=lambda poly: -shoe(poly[0]))
        polys = []
        for i, poly in enumerate(raw):
            if i > 0 and shoe(poly[0]) < MIN_AREA:
                continue  # keep largest; drop tiny extras
            polys.append([ring_ll(r) for r in poly if r is poly[0] or shoe(r) >= MIN_AREA * 0.5])
        out[name] = polys
        print(f'  {name}: {len(polys)} poly(s)')

    os.makedirs('public/data', exist_ok=True)
    dst = 'public/data/state_polys.json'
    json.dump(out, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'states dissolved: {len(out)} -> {dst} ({round(os.path.getsize(dst)/1024)} KB)')


if __name__ == '__main__':
    main()
