#!/usr/bin/env python3
"""Fetch CENACE MDA (Mercado del Día en Adelante) zone prices — the PND (Precio de Nodos Distribuidos,
the load-zone price) per Zona de Carga. Public data — attribute "Fuente: CENACE".

MDA clears the EVENING BEFORE the operating day, so this fetches the latest available operating day:
tomorrow if already published, otherwise today (the morning run is a retry safety net). Reads the
public names-only zonas_index.json (no coordinates); the map joins these prices to the proprietary
coordinates (zonas_de_carga.json, private repo) by zona id at runtime.

Writes <out>/today.json and, with --history, <out>/history/<operatingDate>.json. Stdlib only (runs on a
GitHub runner because CENACE serves those IPs but rejects datacenter IPs)."""
import argparse, datetime, json, os, ssl, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

WS = "https://ws01.cenace.gob.mx:8082/SWPEND/SIM/{sis}/MDA/{zona}/{d}/{d}/JSON"
CT = ZoneInfo("America/Mexico_City")
CTX = ssl.create_default_context()  # verify ws01's TLS cert (it presents a valid chain)


def fetch_zona(system, zona_id, day):
    """day = 'YYYY/MM/DD'. Returns (hourly, avgPND) or (None, None). Zona names: spaces -> hyphens."""
    url = WS.format(sis=system, zona=urllib.parse.quote(zona_id.replace(" ", "-")), d=day)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=45, context=CTX).read().decode("utf-8", "replace")
    j = json.loads(raw)
    if j.get("status") != "OK" or not j.get("Resultados"):
        return None, None
    vals = j["Resultados"][0].get("Valores", [])
    hourly = []
    for v in vals:
        def num(x):
            try: return round(float(x), 2)
            except (TypeError, ValueError): return None
        hourly.append({"hora": int(v["hora"]), "pnd": num(v.get("pz")), "energia": num(v.get("pz_ene")),
                       "perdidas": num(v.get("pz_per")), "congestion": num(v.get("pz_cng"))})
    pnds = [h["pnd"] for h in hourly if h["pnd"] is not None]
    avg = round(sum(pnds) / len(pnds), 2) if pnds else None
    return (hourly, avg) if hourly else (None, None)


def fetch_with_retry(args):
    """Worker: (system, zona_id, day) -> (zona_id, system, result). Retries transient errors 3x."""
    system, zona_id, day = args
    for attempt in range(3):
        try:
            return zona_id, system, fetch_zona(system, zona_id, day)
        except Exception as e:
            if attempt == 2:
                return zona_id, system, ("ERR", str(e))
            time.sleep(0.5 * (attempt + 1))  # brief backoff so transient hiccups aren't hammered
    return zona_id, system, (None, None)


def pick_operating_day(zonas):
    """Latest published MDA day: tomorrow if available, else today (CT)."""
    if not zonas:
        raise SystemExit("zonas index is empty — nothing to fetch")
    today = datetime.datetime.now(CT).date()
    probe = zonas[0]
    for d in (today + datetime.timedelta(days=1), today):
        day = d.strftime("%Y/%m/%d")
        try:
            hourly, _ = fetch_zona(probe["system"], probe["id"], day)
            if hourly:
                return d.strftime("%Y-%m-%d"), day
        except Exception:
            pass
    # Default to tomorrow even if the probe failed; the per-zona fetch will report failures.
    d = today + datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d"), d.strftime("%Y/%m/%d")


def main():
    """Fetch all zonas for the latest MDA operating day and write today.json (+ optional history)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="public/data/pnd/zonas_index.json")
    ap.add_argument("--out", default="public/data/pnd")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--day", default="", help="force operating day YYYY-MM-DD (default: latest published)")
    args = ap.parse_args()

    with open(args.index) as f:
        zonas = json.load(f).get("zonas")
    if not zonas:
        raise SystemExit(f"index {args.index} is empty or missing 'zonas'")
    if args.day:
        op_date, day = args.day, args.day.replace("-", "/")
    else:
        op_date, day = pick_operating_day(zonas)
    print(f"operating day: {op_date}  ({len(zonas)} zonas)")

    out = {}
    fails = []
    jobs = [(z["system"], z["id"], day) for z in zonas]
    with ThreadPoolExecutor(max_workers=6) as ex:
        for zona_id, system, res in ex.map(fetch_with_retry, jobs):
            if res[0] == "ERR" or res[0] is None:
                fails.append((zona_id, res[1] if res[0] == "ERR" else "ZERO_RESULTS"))
                continue
            hourly, avg = res
            out[zona_id] = {"system": system, "avgPND": avg, "hourly": hourly}
    print(f"fetched {len(out)}/{len(zonas)} zonas; failed {len(fails)}")
    for f in fails:
        print("  FAIL", f)

    # Don't publish a partial snapshot as canonical data — abort on broad failure (keeps the last
    # good today.json in place; the next scheduled run retries).
    ratio = len(out) / len(zonas) if zonas else 0
    if ratio < 0.9:
        raise SystemExit(f"aborting write: only {ratio:.0%} of zonas fetched (need >=90%)")

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"updatedAt": now, "operatingDate": op_date, "source": "CENACE", "market": "MDA",
               "count": len(out), "zonas": out}
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "today.json"), "w") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    if args.history:
        hd = os.path.join(args.out, "history")
        os.makedirs(hd, exist_ok=True)
        with open(os.path.join(hd, op_date + ".json"), "w") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", args.out, "@", now)


if __name__ == "__main__":
    main()
