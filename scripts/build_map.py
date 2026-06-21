#!/usr/bin/env python3
"""Assemble the atlas into public/.

Reads the open source/derived data + (local, gitignored) coordinate files, emits:
  public/data/atlas.json        open data bundle (NO point coordinates)
  public/data/coordinates.json  plant/substation coordinates (gitignored; served from Batu)
  public/index.html, atlas.css, atlas.js   the static site (from src/)

The map fetches atlas.json + coordinates.json at runtime and splices coords in, so the
committed artifact never contains the proprietary-geocoded coordinates. See DATA-LICENSE.md.
"""
import json, collections, os, glob, re, shutil

SRC='data/sources'; REG='data/sources/regions'; DER='data/derived'; TPL='src'; PUB='public'

d=json.load(open(f'{SRC}/atlas-map-data.json'))
links=json.load(open(f'{SRC}/plant_links.json'))
own=json.load(open(f'{SRC}/atlas-ownership.json'))
geo={s['name']:s for s in json.load(open(f'{SRC}/atlas-sen-geocoded.json'))['substations'] if isinstance(s.get('lat'),(int,float))}
REGIONS=['Central','Oriental','Occidental','Noroeste','Norte','Noreste','Baja California','Baja California Sur','Mulegé','Peninsular']
RIDX={r:i for i,r in enumerate(REGIONS)}

SUBZ={}; PLZ={}; zacc={}
for f in glob.glob(f'{REG}/atlas-region-*.json'):
    dd=json.load(open(f)); g=dd.get('gerencia','?')
    for z in dd.get('zones',[]):
        zn=re.sub(r'\s*20\d\d-20\d\d$','',(z.get('zona') or '').strip())
        if not zn: continue
        acc=zacc.setdefault((g,zn),[])
        for s in z.get('substations',[]):
            SUBZ[s['name']]=zn
            gc=geo.get(s['name'])
            if gc: acc.append((round(gc['lng'],4),round(gc['lat'],4)))
        for pl in z.get('generation',[]):
            if pl.get('plant'): PLZ[pl['plant']]=zn

def yr(s):
    s=str(s or '')
    for tok in s.replace('-',' ').replace('/',' ').split():
        if tok.isdigit() and len(tok)==4: return int(tok)
    return 0
def clean(v):
    return v if (v or 'desconocido').lower()!='desconocido' else ''

hubGen=collections.defaultdict(float)
for p in d['plants']:
    l=links.get(p['n'])
    if l: hubGen[l['sub']]+=p['mw']

P=[]
for p in d['plants']:
    o=own.get(p['n'],{}); l=links.get(p['n'],{})
    P.append([p['n'],round(p['lat'],4),round(p['lng'],4),int(round(p['mw'])),p['t'],
              (p.get('c') or 'l').lower(),RIDX.get(p['g'],-1),clean(o.get('grupo')),
              clean(o.get('mercado')),yr(o.get('cod')),l.get('sub',''),l.get('km'),
              l.get('slat'),l.get('slng'),PLZ.get(p['n'],'')])
H=[]
for h in d['hubs']:
    cap=(h.get('mva') or 0)*0.9; conn=round(hubGen.get(h['n'],0))
    sat=round(conn/cap,2) if cap>0 else None
    H.append([h['n'],round(h['lat'],4),round(h['lng'],4),h['kv'],int(h.get('mva') or 0),conn,sat,RIDX.get(h.get('g'),-1),SUBZ.get(h['n'],'')])
R=[[r['g'],r['gen'],r['mva'],round(r['lat'],3),round(r['lng'],3),r.get('satMW'),r.get('mwCap')] for r in d['regions']]

# operational zones: convex-hull footprint per (gerencia, zona)
def hull(pts):
    pts=sorted(set(pts))
    if len(pts)<3: return pts
    def cr(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[]
    for p in pts:
        while len(lo)>=2 and cr(lo[-2],lo[-1],p)<=0: lo.pop()
        lo.append(p)
    up=[]
    for p in reversed(pts):
        while len(up)>=2 and cr(up[-2],up[-1],p)<=0: up.pop()
        up.append(p)
    return lo[:-1]+up[:-1]
Z=[]
for (g,zn),pts in zacc.items():
    h=hull(pts)
    if len(h)<3: continue
    cx=round(sum(p[0] for p in pts)/len(pts),4); cy=round(sum(p[1] for p in pts)/len(pts),4)
    Z.append([zn,g,[[round(la,4),round(lo,4)] for (lo,la) in h],cy,cx,len(set(pts))])

TYPE_META={'pv':['Fotovoltaica','#F5B301'],'wind':['Eolica','#1D9E75'],'hydro':['Hidroelectrica','#378ADD'],'geo':['Geotermica','#D85A30'],'nuc':['Nuclear','#7F77DD'],'cc':['Ciclo combinado','#A98B63'],'th':['Termoelectrica','#7C5C3E'],'coal':['Carboelectrica','#3C332C'],'tg':['Turbogas','#C9A227'],'ci':['Combustion interna','#8A6240'],'cog':['Cogeneracion','#97C459'],'cegen':['CEGEN (s/ubicar)','#B9B6AE'],'bat':['Baterias','#534AB7']}

# CFE tariff divisions: dissolved polygons + point-in-polygon node tagging (needs coords)
TZ=json.load(open(f'{DER}/cfe_division_polys.json'))
try:
    from shapely.geometry import Point, Polygon, MultiPolygon
    from shapely.prepared import prep
    dgeom={}
    for dv,polys in TZ.items():
        sp=[]
        for poly in polys:
            ext=[(c[1],c[0]) for c in poly[0]]
            holes=[[(c[1],c[0]) for c in r] for r in poly[1:]]
            try: sp.append(Polygon(ext,holes).buffer(0))
            except: pass
        dgeom[dv]=prep(MultiPolygon([g for g in sp]) if len(sp)!=1 else sp[0])
    def tdiv(lat,lng):
        pt=Point(lng,lat)
        for dv,g in dgeom.items():
            if g.contains(pt): return dv
        return ''
    for rec in P: rec.append(tdiv(rec[1],rec[2]))
    for rec in H: rec.append(tdiv(rec[1],rec[2]))
except Exception as e:
    print('shapely tagging skipped:',e)
    for rec in P: rec.append('')
    for rec in H: rec.append('')

OL=json.load(open(f'{DER}/osm_lines.json')) if os.path.exists(f'{DER}/osm_lines.json') else []
RP=json.load(open(f'{DER}/region_polys.json')) if os.path.exists(f'{DER}/region_polys.json') else {}

# ---- split coordinates out of the open bundle ----
coords={
 'plants':[[p[1],p[2]] for p in P],
 'conns':[([p[12],p[13]] if p[12] is not None else None) for p in P],
 'hubs':[[h[1],h[2]] for h in H],
}
for p in P: p[1]=None; p[2]=None; p[12]=None; p[13]=None
for h in H: h[1]=None; h[2]=None

atlas={'P':P,'H':H,'R':R,'T':TYPE_META,'REG':REGIONS,'Z':Z,'TZ':TZ,'OL':OL,'RP':RP}
os.makedirs(f'{PUB}/data',exist_ok=True)
json.dump(atlas, open(f'{PUB}/data/atlas.json','w'), ensure_ascii=False, separators=(',',':'))
json.dump(coords, open(f'{PUB}/data/coordinates.json','w'), separators=(',',':'))

# ---- assemble the static site from src/ ----
totMW=round(sum(p[3] for p in P)); nOwn=sum(1 for p in P if p[7])
shutil.copy(f'{TPL}/atlas.css', f'{PUB}/atlas.css')
shutil.copy(f'{TPL}/atlas.js',  f'{PUB}/atlas.js')
html=open(f'{TPL}/atlas.html',encoding='utf-8').read()
html=(html.replace('__TOT__',str(round(totMW/1000,1))).replace('__NP__',str(len(P)))
          .replace('__NH__',str(len(H))).replace('__NOWN__',str(nOwn)).replace('__NL__',str(len(OL))))
open(f'{PUB}/index.html','w',encoding='utf-8').write(html)

print(f'built public/ — plants {len(P)} hubs {len(H)} lines {len(OL)} regions {len(RP)} | '
      f'atlas.json {round(os.path.getsize(f"{PUB}/data/atlas.json")/1024)}KB '
      f'coordinates.json {round(os.path.getsize(f"{PUB}/data/coordinates.json")/1024)}KB (gitignored)')
