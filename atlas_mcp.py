#!/usr/bin/env python3
"""Atlas de Red — MCP server.

Lets an LLM (Claude, etc.) query Mexico's Sistema Eléctrico Nacional in natural
language: generation, live demand, distributed generation, CFE tariff users &
energy, and substations. Reads the same open JSON the map serves (public/data/),
so no database or API key is needed. Proprietary-geocoded plant/substation
coordinates are NOT exposed — only public attributes and aggregates.

Run (stdio):  python atlas_mcp.py
Add to an MCP client (e.g. Claude Desktop / Claude Code .mcp.json):
  { "mcpServers": { "atlas-sen": { "command": "python", "args": ["/abs/path/atlas_mcp.py"] } } }

Live demand is read from ATLAS_DEMAND_URL (defaults to the public data branch).
Data sources & licenses: see data/SOURCES.md.
"""
import json, os, urllib.request

from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "public", "data")
DEMAND_URL = os.environ.get(
    "ATLAS_DEMAND_URL",
    "https://raw.githubusercontent.com/batuenergy/atlas-sen/data/public/data/demand/today.json",
)


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


ATLAS = _load("atlas.json")
DG_SIZE = _load("dg_by_size.json")
DG_STATE = _load("dg_by_state.json")
USERS = _load("cfe_users_ts.json")
ENERGY = _load("cfe_energy_ts.json")
RGD = _load("cfe_rgd_by_division.json")
OSM_SUBS = _load("osm_substations.json")
TYPES = {k: v[0] for k, v in ATLAS["T"].items()}   # source key -> Spanish label
REG = ATLAS["REG"]                                   # CENACE region names (by index)
TARIFAS = ["DB1", "DB2", "PDBT", "GDBT", "GDMTH", "GDMTO", "DIST", "DIT", "RABT", "RAMT", "APBT", "APMT"]

SRC = {
    "generation": "CENACE diagramas unifilares + ownership research (CC-BY)",
    "demand": "CENACE GraficaDemanda — semi-real-time (attribute CENACE)",
    "dg": "CNE/CRE Estadísticas de Generación Distribuida / generación exenta (RES/142/2017)",
    "tarifa": "CNE Memorias de cálculo de las tarifas del Suministro Básico — gob.mx/cne",
    "substations_transmission": "CENACE diagramas unifilares",
    "substations_distribution": "OpenStreetMap contributors (ODbL)",
    "rgd": "CFE Distribución — Valores de Corto Circuito de las RGD",
}

mcp = FastMCP(
    "atlas-sen",
    instructions=(
        "Query Mexico's national electricity system (Sistema Eléctrico Nacional). "
        "Call list_dimensions first to discover valid filter values (sources, CENACE "
        "regions, CFE tariff divisions, tariff codes, year ranges). Every tool returns "
        "a 'source' field — cite it. Plant/substation coordinates are intentionally not "
        "exposed; use aggregates and attributes."
    ),
)


def _ci(a, b):
    return a and b and a.lower() in b.lower()


SOURCE_SYN = {"solar": "pv", "fotovoltaica": "pv", "pv": "pv", "wind": "wind", "eolica": "wind",
              "eolico": "wind", "viento": "wind", "hydro": "hydro", "hidro": "hydro",
              "hidroelectrica": "hydro", "nuclear": "nuc", "nuc": "nuc", "geo": "geo",
              "geotermica": "geo", "gas": "cc", "ciclo": "cc", "ciclo combinado": "cc",
              "carbon": "coal", "coal": "coal", "termo": "th", "termoelectrica": "th",
              "cogeneracion": "cog", "turbogas": "tg", "bateria": "bat", "battery": "bat", "baterias": "bat"}


def _match_source(q, t):
    if not q:
        return True
    ql = q.lower().strip()
    return ql in (t.lower(), TYPES.get(t, "").lower()) or SOURCE_SYN.get(ql) == t or ql in TYPES.get(t, "").lower()


@mcp.tool()
def list_dimensions() -> dict:
    """Valid filter values across the datasets: generation source types, CENACE control
    regions, CFE tariff divisions, tariff codes, and the year/period coverage of each series."""
    return {
        "generation_sources": TYPES,
        "cenace_regions": REG,
        "tariff_divisions": sorted(ATLAS["TZ"].keys()),
        "states": sorted(DG_STATE["byState"].keys()),
        "tariff_codes": TARIFAS,
        "coverage": {
            "dg_by_state_periods": DG_STATE["periods"],
            "dg_by_size_years": DG_SIZE["years"],
            "users_years": USERS["years"],
            "energy_years": ENERGY["years"],
        },
        "counts": {"plants": len(ATLAS["P"]), "transmission_substations": len(ATLAS["H"]),
                   "distribution_substations": len(OSM_SUBS["subs"]), "lines": len(ATLAS["OL"])},
    }


@mcp.tool()
def query_generation(source: str = "", owner: str = "", region: str = "", state: str = "",
                     min_mw: float = 0, commissioned_from: int = 0, commissioned_to: int = 0,
                     limit: int = 50) -> dict:
    """Generation plants filtered by source (key or Spanish label, e.g. 'pv'/'solar'/'Fotovoltaica'),
    owner, CENACE region, state (entidad), minimum MW, and commissioning-year range. Returns matching
    plants (no coordinates) plus an aggregate summary (count, total MW, breakdown by source)."""
    out, total, by_src = [], 0.0, {}
    for p in ATLAS["P"]:
        t = p[4]
        reg = REG[p[6]] if isinstance(p[6], int) and 0 <= p[6] < len(REG) else ""
        rec = {"name": p[0], "mw": p[3], "source": TYPES.get(t, t), "owner": p[7] or "",
               "market": p[8] or "", "cod": p[9] or None, "region": reg,
               "estado": p[14] or "", "municipio": p[10] or "", "tariff_division": p[15] or ""}
        if not _match_source(source, t):
            continue
        if owner and not _ci(owner, rec["owner"]):
            continue
        if region and not _ci(region, reg):
            continue
        if state and not _ci(state, rec["estado"]):
            continue
        if min_mw and (p[3] or 0) < min_mw:
            continue
        if commissioned_from and (not p[9] or p[9] < commissioned_from):
            continue
        if commissioned_to and (not p[9] or p[9] > commissioned_to):
            continue
        out.append(rec)
        total += p[3] or 0
        by_src[rec["source"]] = round(by_src.get(rec["source"], 0) + (p[3] or 0), 1)
    out.sort(key=lambda r: -(r["mw"] or 0))
    return {"summary": {"count": len(out), "total_mw": round(total, 1),
                        "total_gw": round(total / 1000, 2), "by_source_mw": by_src},
            "plants": out[:limit], "truncated": len(out) > limit, "source": SRC["generation"]}


@mcp.tool()
def query_demand(region: str = "Sistema Interconectado Nacional") -> dict:
    """Live semi-real-time CENACE demand / generation / forecast for a region or the whole
    national system (default). Returns the latest measured hour, the surplus, and the hourly curve."""
    try:
        req = urllib.request.Request(DEMAND_URL, headers={"User-Agent": "atlas-mcp"})
        dem = json.load(urllib.request.urlopen(req, timeout=20))
    except Exception as e:
        return {"error": f"could not fetch live demand: {e}", "source": SRC["demand"]}
    regions = dem.get("regions", {})
    name = next((k for k in regions if k.lower() == region.lower()), None) \
        or next((k for k in regions if _ci(region, k)), None)
    if not name:
        return {"error": "region not found", "available": list(regions.keys()), "source": SRC["demand"]}
    r = regions[name]
    hourly = r.get("hourly", [])
    measured = [h for h in hourly if h.get("demandaMW") is not None]
    latest = measured[-1] if measured else None
    return {"region": name, "updatedAt": dem.get("updatedAt"), "operatingDate": dem.get("operatingDate"),
            "latest": latest, "hourly": hourly, "source": SRC["demand"],
            "note": "Hours are Mexico-Central time; measured data lags ~1h, the rest is forecast."}


@mcp.tool()
def query_distributed_generation(by: str = "state", name: str = "", period: str = "",
                                 metric: str = "mw") -> dict:
    """Distributed-generation installed capacity over time. by='state' (per entidad federativa,
    semesters 2019-H2..2025-H2, cumulative MW + contracts) or by='size' (per system-size bucket,
    annual 2018-2024, MWp). Optional name (a state or size bucket) and period/year; metric='mw'|'contratos'."""
    if by == "size":
        cap = DG_SIZE["capacityMWp"]
        if name:
            series = cap.get(name) or {}
            return {"by": "size", "size": name, "capacityMWp": series, "source": SRC["dg"]}
        if period:
            return {"by": "size", "year": period,
                    "capacityMWp": {s: cap[s].get(period) for s in cap}, "source": SRC["dg"]}
        return {"by": "size", "years": DG_SIZE["years"], "capacityMWp": cap,
                "total": DG_SIZE.get("capacityMWp_total"), "source": SRC["dg"]}
    # by state
    bs = DG_STATE["byState"]
    periods = DG_STATE["periods"]
    if name:
        st = next((k for k in bs if k.lower() == name.lower()), None) or next((k for k in bs if _ci(name, k)), None)
        if not st:
            return {"error": "state not found", "available": sorted(bs.keys()), "source": SRC["dg"]}
        return {"by": "state", "state": st, "macroRegion": DG_STATE.get("macroRegion", {}).get(st),
                "series": bs[st], "source": SRC["dg"]}
    per = period or periods[-1]
    key = "contratos" if metric == "contratos" else "mw"
    rows = sorted(((s, (bs[s].get(per) or {}).get(key)) for s in bs),
                  key=lambda x: -(x[1] or 0))
    return {"by": "state", "period": per, "metric": key,
            "ranking": [{"state": s, key: v} for s, v in rows if v is not None],
            "national_total": round(sum((v or 0) for _, v in rows), 1), "source": SRC["dg"]}


@mcp.tool()
def query_tarifa(metric: str = "users", division: str = "", tarifa: str = "", year: str = "") -> dict:
    """CFE basic-supply estimated USERS or ENERGY by tariff x division x year.
    metric='users' (2016-18, 2022-26) or 'energy' (MWh, 2019-2026). Optional division (CFE tariff
    division), tarifa code (e.g. DB1, GDMTH; omit for all/sum), and year (omit for the full series)."""
    ds = USERS if metric == "users" else ENERGY
    unit = "usuarios" if metric == "users" else "MWh"
    byd = ds["byDivision"]
    divs = [d for d in byd if (not division or _ci(division, d) or d.lower() == division.lower())]
    if division and not divs:
        return {"error": "division not found", "available": sorted(byd.keys()), "source": SRC["tarifa"]}

    def val(d, yr):
        node = byd[d]
        if tarifa:
            return (node.get(tarifa) or {}).get(yr)
        tot = sum((node[tf] or {}).get(yr, 0) or 0 for tf in node)
        return tot or None

    years = [year] if year else ds["years"]
    result = {}
    for d in divs:
        result[d] = {yr: val(d, yr) for yr in years}
    # national rollup per year
    national = {yr: round(sum((result[d].get(yr) or 0) for d in result), 1) for yr in years}
    return {"metric": metric, "unit": unit, "tarifa": tarifa or "ALL",
            "years": years, "byDivision": result, "national": national, "source": SRC["tarifa"]}


@mcp.tool()
def query_substations(kind: str = "transmission", division: str = "", min_kv: float = 0,
                      limit: int = 50) -> dict:
    """Substations. kind='transmission' (CENACE 400/230 kV, with transformer MVA + saturation),
    'distribution' (OpenStreetMap, <=161 kV, with real coordinates), or 'rgd_summary' (CFE per-division
    distribution-substation count + transformer MVA)."""
    if kind == "rgd_summary":
        return {"kind": "rgd_summary", "byDivision": RGD["byDivision"], "source": SRC["rgd"]}
    if kind == "distribution":
        rows = []
        for s in OSM_SUBS["subs"]:
            if min_kv:
                v = max([int(x) for x in str(s[5]).replace(";", " ").split() if x.isdigit()] or [0]) / 1000
                if v < min_kv:
                    continue
            rows.append({"name": s[3] or "Subestación", "operator": s[4] or "",
                         "voltage": s[5], "band": "MV" if s[2] == 0 else "sub-transmisión",
                         "lat": s[0], "lng": s[1]})
        return {"kind": "distribution", "count": len(rows), "substations": rows[:limit],
                "truncated": len(rows) > limit, "source": SRC["substations_distribution"]}
    # transmission
    rows = []
    for h in ATLAS["H"]:
        rec = {"name": h[0], "kv": h[3], "mva": h[4], "saturation": h[6],
               "municipio": h[8] or "", "division": h[9] or ""}
        if division and not _ci(division, rec["division"]):
            continue
        if min_kv and (h[3] or 0) < min_kv:
            continue
        rows.append(rec)
    rows.sort(key=lambda r: -(r["mva"] or 0))
    return {"kind": "transmission", "count": len(rows), "substations": rows[:limit],
            "truncated": len(rows) > limit, "source": SRC["substations_transmission"]}


if __name__ == "__main__":
    mcp.run()
