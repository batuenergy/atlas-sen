#!/usr/bin/env python3
"""Download INEGI/CONABIO 2020 municipio geometry (per state) into data/sources/muni/.

Source: github.com/PhantomInsights/mexico-geojson (CONABIO 2020 Marco Geoestadístico).
Open government data (INEGI). ~150 MB total; gitignored. Used by the dissolve_* scripts.
"""
import json, os, urllib.request, urllib.parse

OUT = 'data/sources/muni'
TREE = 'https://api.github.com/repos/PhantomInsights/mexico-geojson/git/trees/main?recursive=1'
BASE = 'https://raw.githubusercontent.com/PhantomInsights/mexico-geojson/main/'

os.makedirs(OUT, exist_ok=True)
tree = json.load(urllib.request.urlopen(TREE, timeout=60))['tree']
paths = [t['path'] for t in tree
         if t['path'].startswith('2020/states/') and t['path'].endswith('.json')]
n = 0
for p in paths:
    dst = os.path.join(OUT, os.path.basename(p))
    if os.path.exists(dst):
        n += 1
        continue
    urllib.request.urlretrieve(BASE + urllib.parse.quote(p), dst)
    n += 1
print(f'municipio state files: {n} -> {OUT}')
