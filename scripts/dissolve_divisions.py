import json, glob, re, unicodedata, collections
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower()
    s=re.sub(r'[^a-z0-9 ]',' ',s); s=re.sub(r'\s+',' ',s).strip()
    return s
def nstate(s):
    s=norm(s)
    s=s.replace(' de zaragoza','').replace(' de ocampo','').replace(' de ignacio de la llave','')
    s=s.replace('distrito federal','ciudad de mexico').replace('estado de mexico','mexico')
    if s=='veracruz llave': s='veracruz'
    return s

mp=json.load(open('data/sources/cfe_muni_division.json'))['flat']  # [div, estado, muni]
# build per-state: norm muni -> division
byst=collections.defaultdict(dict)
for div,est,mu in mp:
    byst[nstate(est)][norm(mu)]=div

def lookup(state,muni):
    d=byst.get(state)
    if not d: return None
    nm=norm(muni)
    if nm in d: return d[nm]
    # prefix / contains fallback within state
    for k,v in d.items():
        if k.startswith(nm) or nm.startswith(k): return v
    for k,v in d.items():
        if nm in k or k in nm: return v
    return None

geoms=collections.defaultdict(list)
seen=set(); matched=0; unmatched=[]
for f in glob.glob('data/sources/muni/*.json'):
    try: gj=json.load(open(f))
    except: continue
    for ft in gj.get('features',[]):
        pr=ft.get('properties',{})
        st=pr.get('NOM_ENT'); mu=pr.get('NOM_MUN')
        if not st or not mu: continue
        key=(nstate(st),norm(mu))
        if key in seen: continue
        seen.add(key)
        div=lookup(nstate(st),mu)
        if div:
            try: geoms[div].append(shape(ft['geometry']).buffer(0))
            except: pass
            matched+=1
        else:
            unmatched.append((st,mu))
print('matched municipios:',matched,'| unmatched:',len(unmatched))
print('unmatched sample:',unmatched[:15])

def ring_ll(coords): return [[round(c[1],4),round(c[0],4)] for c in coords]
def shoe(r):
    a=0.0
    for i in range(len(r)-1): a+=r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1]
    return abs(a)/2
MIN_AREA=0.01  # deg^2 ~ drop tiny islands/slivers
out={}
for div,gs in geoms.items():
    u=unary_union(gs).simplify(0.013, preserve_topology=True)
    gj=mapping(u)
    raw = gj['coordinates'] if gj['type']=='MultiPolygon' else [gj['coordinates']]
    raw=sorted(raw,key=lambda poly:-shoe(poly[0]))
    polys=[]
    for i,poly in enumerate(raw):
        if i>0 and shoe(poly[0])<MIN_AREA: continue   # always keep largest; drop tiny extras
        polys.append([ring_ll(r) for r in poly if r is poly[0] or shoe(r)>=MIN_AREA*0.5])
    out[div]=polys
import os
os.makedirs('data/derived',exist_ok=True)
json.dump(out,open('data/derived/cfe_division_polys.json','w'),separators=(',',':'))
print('divisions dissolved:',len(out),'| file KB:',round(os.path.getsize('data/derived/cfe_division_polys.json')/1024))
for d in sorted(out): print('  ',d, len(out[d]),'rings')
