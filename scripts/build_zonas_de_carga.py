#!/usr/bin/env python3
"""Build the Zonas de Carga (Nodos Distribuidos) georeferencing for the MDA price layer.

Maintainer-only. Consumes CENACE's public "Catálogo de NodosP" (xlsx) + INEGI/CONABIO 2020 municipio
geometry and emits two artifacts:

  --out-private  zonas_de_carga.json  per-zona reconstructed [lat,lng] (PROPRIETARY — committed only
                                       to the private batu-codebase repo at
                                       apps/web/public/atlas/data/pnd/, NEVER here; same policy as
                                       public/data/coordinates.json, see DATA-LICENSE.md / .gitignore)
  --out-index    zonas_index.json     per-zona {id,name,system} ONLY (no coords) — public-safe; read
                                       by fetch_pnd.py on the runner to know which zonas to query.

Placement: each Zona de Carga sits at the node-weighted centroid of its member NodosP' INEGI
municipios. The catálogo carries the Entidad+Municipio (INEGI) clave for every NodoP (100% coverage),
so this is reliable. The alternative NodoP-name→substation join is NOT used: substation names collide
across states and produce centroids hundreds of km off. Coordinates are reconstructed — the UI labels
them "ubicaciones aproximadas".

Validate the result against CENACE's weekly MEM report Fig. 7 (zonas colored by avg PND):
https://www.cenace.gob.mx/Docs/01_MECP/ReporteSemanal/

Public data — attribute "CENACE (Catálogo de NodosP) + INEGI/CONABIO".
"""
import argparse, datetime, json, os, re, urllib.parse, urllib.request
from collections import defaultdict
from shapely.geometry import shape

NODOSP_PAGE = "https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx"
CENACE_ROOT = "https://www.cenace.gob.mx"
MUNI_TREE = "https://api.github.com/repos/PhantomInsights/mexico-geojson/git/trees/main?recursive=1"
MUNI_BASE = "https://raw.githubusercontent.com/PhantomInsights/mexico-geojson/main/"
UA = {"User-Agent": "Mozilla/5.0 (atlas-sen build_zonas_de_carga)"}

# Column indices in the "Catalogo de NodosP" sheet (header is row 2; data starts row 3).
C_SISTEMA, C_CCR, C_ZONA, C_CLAVE, C_NOMBRE = 0, 1, 2, 3, 4
C_ENT_CVE, C_MUN_CVE, C_REGION = 14, 16, 18

# Manual coordinate overrides for any zona whose municipio centroid is wrong/missing (CVEGEO gap or
# catálogo errata). Keyed by zona name. Empty by default — fill after validating vs MEM Fig. 7.
# BCA/BCS load zones span enormous desert/peninsula municipios whose geometric centroid sits far from
# the populated city, so we pin them to the city. (Validated vs MEM Fig. 7.)
MANUAL_OVERRIDES: dict[str, list[float]] = {
    "ENSENADA": [31.866, -116.596],
    "MEXICALI": [32.624, -115.452],
    "SANLUIS": [32.464, -114.772],   # San Luis Río Colorado
    "TIJUANA": [32.514, -117.038],
    "CONSTITUCION": [25.031, -111.665],  # Ciudad Constitución
    "LA PAZ": [24.142, -110.311],
    "LOS CABOS": [23.063, -109.701],
}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=120).read()
    return data if binary else data.decode("utf-8", "replace")


def latest_catalog_url():
    """Newest 'Catálogo NodosP …xlsx' link from the NodosP page (the page lists newest first)."""
    html = get(NODOSP_PAGE)
    m = re.search(r'href="(/Docs/01_MECP/CatalogoNodosP/[^"]+?\.xlsx)"', html)
    if not m:
        raise SystemExit("could not find a catálogo .xlsx link on " + NODOSP_PAGE)
    return CENACE_ROOT + urllib.parse.quote(m.group(1))


def load_muni_centroids(cache):
    """CVEGEO (5-digit) -> [lat, lng], from INEGI/CONABIO 2020 municipio polygons (cached)."""
    if os.path.exists(cache):
        return json.load(open(cache))
    print("downloading municipio geometry (INEGI/CONABIO 2020)…")
    paths = [t["path"] for t in json.loads(get(MUNI_TREE))["tree"]
             if t["path"].startswith("2020/states/") and t["path"].endswith(".json")]
    muni = {}
    for p in paths:
        fc = json.loads(get(MUNI_BASE + urllib.parse.quote(p)))
        for f in fc["features"]:
            c = shape(f["geometry"]).centroid
            muni[f["properties"]["CVEGEO"]] = [round(c.y, 5), round(c.x, 5)]
    os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
    json.dump(muni, open(cache, "w"))
    print(f"  {len(muni)} municipio centroids -> {cache}")
    return muni


def parse_catalog(xlsx_bytes):
    """Return {(system, zona): {region, nodes:[clave], cvegeos:[CVEGEO per node]}} (excl. 'No Aplica')."""
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = next((s for s in wb.worksheets if s.title.lower().startswith("catalogo")), wb.worksheets[0])
    zonas = defaultdict(lambda: {"region": None, "nodes": [], "cvegeos": []})
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i < 2:  # header rows
            continue
        zona = r[C_ZONA]
        if not zona or zona == "No Aplica":
            continue
        z = zonas[(r[C_SISTEMA], zona)]
        z["region"] = r[C_CCR]
        z["nodes"].append(r[C_CLAVE])
        try:
            z["cvegeos"].append(f"{int(r[C_ENT_CVE]):02d}{int(r[C_MUN_CVE]):03d}")
        except (TypeError, ValueError):
            z["cvegeos"].append(None)
    return zonas


def build(xlsx_bytes, muni):
    zonas = parse_catalog(xlsx_bytes)
    out = []
    misplaced = []
    for (system, zona), z in sorted(zonas.items()):
        if zona in MANUAL_OVERRIDES:
            lat, lng = MANUAL_OVERRIDES[zona]
            tier = "manual"
        else:
            pts = [muni[c] for c in z["cvegeos"] if c in muni]
            if not pts:
                misplaced.append((system, zona))
                continue
            lat = round(sum(p[0] for p in pts) / len(pts), 4)
            lng = round(sum(p[1] for p in pts) / len(pts), 4)
            tier = "municipio"
        out.append({"id": zona, "name": zona.title(), "system": system,
                    "region": (z["region"] or "").title() or None,
                    "nodeCount": len(z["nodes"]), "lat": lat, "lng": lng, "geoTier": tier})
    if misplaced:
        print("WARNING: no municipio centroid for:", misplaced,
              "\n  -> add to MANUAL_OVERRIDES.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="", help="path or URL to the NodosP xlsx (default: latest from CENACE)")
    ap.add_argument("--muni-cache", default="data/sources/muni_centroids.json")
    ap.add_argument("--out-private", default="public/data/pnd/zonas_de_carga.json",
                    help="proprietary coords — copy to the PRIVATE repo; do NOT commit here")
    ap.add_argument("--out-index", default="public/data/pnd/zonas_index.json",
                    help="public names-only index read by fetch_pnd.py")
    args = ap.parse_args()

    src = args.catalog or latest_catalog_url()
    print("catálogo:", src)
    xlsx = open(src, "rb").read() if os.path.exists(src) else get(src, binary=True)
    muni = load_muni_centroids(args.muni_cache)
    zonas = build(xlsx, muni)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_sys = defaultdict(int)
    for z in zonas:
        by_sys[z["system"]] += 1
    print(f"zonas: {len(zonas)}  by system: {dict(by_sys)}  "
          f"tiers: {dict((t, sum(1 for z in zonas if z['geoTier'] == t)) for t in {z['geoTier'] for z in zonas})}")

    private = {"updatedAt": now, "source": "CENACE (Catálogo de NodosP) + INEGI/CONABIO",
               "method": "node-weighted municipio centroid", "count": len(zonas), "zonas": zonas}
    index = {"updatedAt": now, "source": "CENACE (Catálogo de NodosP)", "count": len(zonas),
             "zonas": [{"id": z["id"], "name": z["name"], "system": z["system"]} for z in zonas]}

    for path, obj in [(args.out_private, private), (args.out_index, index)]:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        json.dump(obj, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
        print("wrote", path)
    print("\nNOTE:", args.out_private, "carries proprietary coordinates — copy it into the PRIVATE repo",
          "(apps/web/public/atlas/data/pnd/) and do NOT commit it to atlas-sen.")


if __name__ == "__main__":
    main()
