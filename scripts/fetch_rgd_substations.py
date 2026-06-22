#!/usr/bin/env python3
"""Parse CFE's "Valores de Corto Circuito de las RGD" into a distribution-substation
registry + a per-division rollup.

The PDF lists every RGD (distribution) substation by division, zona (municipio),
acronym, name, HV/MV voltage and transformer MVA — but no coordinates. We extract
the public attributes only:
  - data/derived/rgd_substations.json   full registry (committable; names/MVA/voltage)
  - public/data/cfe_rgd_by_division.json per-division {subs, mva} rollup for the map

Requires `pdftotext` (poppler-utils). Source PDF (CFE Distribución, annual):
  https://www.cfe.gob.mx/distribucion/cumplimiento/Documents/

Usage: python scripts/fetch_rgd_substations.py [--pdf <path-or-url>]
"""
import argparse, json, os, re, subprocess, tempfile, urllib.request
from collections import defaultdict

DEFAULT_URL = ("https://www.cfe.gob.mx/distribucion/cumplimiento/Documents/"
               "Valores%20de%20Corto%20Circuito%20en%20las%20RGD%202024.pdf")
DIVISIONS = ["Baja California", "Noroeste", "Norte", "Golfo Norte", "Golfo Centro",
             "Bajío", "Jalisco", "Centro Occidente", "Centro Sur", "Centro Oriente",
             "Oriente", "Sureste", "Peninsular", "Valle de México Norte",
             "Valle de México Centro", "Valle de México Sur"]
DIVS_SORTED = sorted(DIVISIONS, key=len, reverse=True)
ROW = re.compile(r'^\s*(\d+)\s+(.+?)\s+(\d{2}-[A-Z0-9]+-\d+-[A-Z0-9]+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+')


def to_text(pdf):
    if pdf.startswith("http"):
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
        req = urllib.request.Request(pdf, headers={"User-Agent": "atlas-sen/rgd"})
        # CFE serves an incomplete TLS chain; relax verification for this host only.
        import ssl
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=120) as r, open(tmp, "wb") as f:
            f.write(r.read())
        pdf = tmp
    txt = pdf + ".txt"
    subprocess.run(["pdftotext", "-layout", pdf, txt], check=True)
    return open(txt, encoding="utf-8").read()


def parse(text):
    subs, banks, mva = {}, defaultdict(int), defaultdict(float)
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        _, prefix, banco, at, mt, mvav = m.groups()
        acr = banco.rsplit("-", 1)[0]
        parts = prefix.split(acr)
        if len(parts) < 2:
            continue
        div_zona = re.sub(r"\s+", " ", parts[0]).strip()
        name = re.sub(r"\s+", " ", parts[1]).strip()
        div = next((d for d in DIVS_SORTED if div_zona.startswith(d)), None)
        if not div:
            continue
        zona = div_zona[len(div):].strip()
        banks[acr] += 1
        try:
            mva[acr] += float(mvav)
        except ValueError:
            pass
        if acr not in subs:
            subs[acr] = {"code": acr, "name": name, "division": div, "zona": zona,
                         "atKV": float(at), "mtKV": set()}
        subs[acr]["mtKV"].add(float(mt))
    out = []
    for acr, r in subs.items():
        r["mtKV"] = sorted(r["mtKV"]); r["banks"] = banks[acr]; r["mva"] = round(mva[acr], 2)
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=DEFAULT_URL)
    args = ap.parse_args()
    registry = parse(to_text(args.pdf))
    os.makedirs("data/derived", exist_ok=True)
    json.dump(registry, open("data/derived/rgd_substations.json", "w"), ensure_ascii=False)

    agg = defaultdict(lambda: {"subs": 0, "mva": 0.0})
    for r in registry:
        a = agg[r["division"]]; a["subs"] += 1; a["mva"] += r.get("mva", 0) or 0
    rollup = {k: {"subs": v["subs"], "mva": round(v["mva"])} for k, v in agg.items()}
    json.dump({"meta": {"source": "CFE Distribución — Valores de Corto Circuito de las RGD",
                        "count": len(registry)}, "byDivision": rollup},
              open("public/data/cfe_rgd_by_division.json", "w"), ensure_ascii=False)
    print(f"registry: {len(registry)} substations · rollup: {len(rollup)} divisions")


if __name__ == "__main__":
    main()
