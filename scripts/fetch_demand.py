#!/usr/bin/env python3
"""Fetch CENACE semi-real-time demand/generation/forecast per control region.
Public data — attribute "Fuente: CENACE". Writes <out>/today.json and, with --history,
<out>/history/<operatingDate>.json (used by the scheduled job)."""
import json, urllib.request, datetime, argparse, os

GER={10:"Sistema Interconectado Nacional",1:"Baja California",2:"Baja California Sur",
     3:"Central",4:"Noreste",5:"Noroeste",6:"Norte",7:"Occidental",8:"Oriental",9:"Peninsular"}
URL="https://www.cenace.gob.mx/GraficaDemanda.aspx/obtieneValoresTotal"

def fetch(gid):
    req=urllib.request.Request(URL, data=json.dumps({"gerencia":str(gid)}).encode(),
        headers={"Content-Type":"application/json; charset=utf-8","User-Agent":"Mozilla/5.0"})
    raw=urllib.request.urlopen(req, timeout=30).read().decode()
    rows=json.loads(json.loads(raw)["d"])  # 'd' is a JSON-encoded string
    out=[]
    for r in rows:
        def num(v):
            try: return int(float(str(v).replace(',','')))
            except: return None
        out.append({"hora":int(r["hora"]),"demandaMW":num(r.get("valorDemanda")),
                    "generacionMW":num(r.get("valorGeneracion")),"pronosticoMW":num(r.get("valorPronostico"))})
    return [x for x in out if x["demandaMW"] is not None or x["pronosticoMW"] is not None]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out', default='public/data/demand', help='output directory')
    ap.add_argument('--history', action='store_true', help='also append history/<date>.json')
    args=ap.parse_args()

    regions={}
    for gid,name in GER.items():
        try:
            h=fetch(gid)
            latest=[x for x in h if x["demandaMW"] is not None]
            regions[name]={"gerencia":gid,"hourly":h,"latest":(latest[-1] if latest else None)}
            print("%-34s rows:%2d  latest demanda:%s MW"%(name,len(h),(latest[-1]["demandaMW"] if latest else 'n/d')))
        except Exception as e:
            print("FAIL",name,e)

    now=datetime.datetime.now(datetime.timezone.utc)
    out={"updatedAt":now.strftime('%Y-%m-%dT%H:%M:%SZ'),"operatingDate":now.strftime('%Y-%m-%d'),
         "source":"CENACE","regions":regions}
    os.makedirs(args.out, exist_ok=True)
    json.dump(out, open(os.path.join(args.out,'today.json'),'w'), ensure_ascii=False, separators=(',',':'))
    if args.history:
        hd=os.path.join(args.out,'history'); os.makedirs(hd, exist_ok=True)
        json.dump(out, open(os.path.join(hd, out['operatingDate']+'.json'),'w'), ensure_ascii=False, separators=(',',':'))
    print("wrote", args.out, "@", out["updatedAt"])

if __name__=='__main__':
    main()
