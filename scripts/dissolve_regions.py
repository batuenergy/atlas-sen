import json, glob, collections
from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree

# region-tagged substation points from per-gerencia region files
# NOTE: needs coordinates (data/sources/atlas-sen-geocoded.json), which are gitignored —
# this regeneration step is maintainer-only. The output (data/derived/region_polys.json) is committed.
geo={s['name']:s for s in json.load(open('data/sources/atlas-sen-geocoded.json'))['substations'] if isinstance(s.get('lat'),(int,float))}
pts=[]  # (lng,lat,region)
for f in glob.glob('data/sources/regions/atlas-region-*.json'):
    if 'geo' in f or 'snapshot' in f: continue
    d=json.load(open(f)); g=d.get('gerencia')
    if not g: continue
    for z in d.get('zones',[]):
        for s in z.get('substations',[]):
            gc=geo.get(s['name'])
            if gc: pts.append((gc['lng'],gc['lat'],g))
print('region-tagged points:',len(pts))

# municipio polygons
geoms=[]; 
for f in glob.glob('data/sources/muni/*.json'):
    try: gj=json.load(open(f))
    except: continue
    for ft in gj.get('features',[]):
        try: geoms.append(shape(ft['geometry']).buffer(0))
        except: pass
print('municipios:',len(geoms))
tree=STRtree(geoms)

# assign each point to containing municipio; tally region votes per municipio
votes=[collections.Counter() for _ in geoms]
for lng,lat,reg in pts:
    p=Point(lng,lat)
    for i in tree.query(p):
        if geoms[i].covers(p): votes[i][reg]+=1; break
assigned=[ (v.most_common(1)[0][0] if v else None) for v in votes ]
n0=sum(1 for a in assigned if a)
print('municipios with points:',n0,'/',len(geoms))

# fill empty municipios by nearest assigned-municipio centroid
cent=[g.centroid for g in geoms]
aidx=[i for i,a in enumerate(assigned) if a]
atree=STRtree([cent[i] for i in aidx])
for i in range(len(geoms)):
    if assigned[i]: continue
    j=atree.nearest(cent[i])
    assigned[i]=assigned[aidx[j]]

# dissolve by region
def ring_ll(c): return [[round(p[1],4),round(p[0],4)] for p in c]
def shoe(r):
    a=0.0
    for i in range(len(r)-1): a+=r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1]
    return abs(a)/2
MIN_AREA=0.01
byreg=collections.defaultdict(list)
for i,r in enumerate(assigned): byreg[r].append(geoms[i])
out={}
for reg,gs in byreg.items():
    u=unary_union(gs).simplify(0.012, preserve_topology=True)
    gj=mapping(u)
    raw=gj['coordinates'] if gj['type']=='MultiPolygon' else [gj['coordinates']]
    raw=sorted(raw,key=lambda poly:-shoe(poly[0]))
    polys=[]
    for k,poly in enumerate(raw):
        if k>0 and shoe(poly[0])<MIN_AREA: continue
        polys.append([ring_ll(r) for r in poly if r is poly[0] or shoe(r)>=MIN_AREA*0.5])
    out[reg]=polys
import os
os.makedirs('data/derived',exist_ok=True)
json.dump(out, open('data/derived/region_polys.json','w'), separators=(',',':'))
print('regions dissolved:',len(out),'| KB:',round(os.path.getsize('data/derived/region_polys.json')/1024))
for r in sorted(out): print('  ',r, len(out[r]),'polys')
