import csv,sys,collections,json
src,out=sys.argv[1],sys.argv[2]
W,H=880,600; L0,L1,A0,A1=8.25,11.3,35.72,37.42
import math
def P(lon,lat):
    return round((lon-L0)/(L1-L0)*W,1), round((A1-lat)/(A1-A0)*H,1)
coast=[(8.25,36.94),(8.75,36.96),(9.0,37.1),(9.22,37.23),(9.55,37.20),(9.85,37.33),(9.87,37.27),(10.05,37.25),(10.19,37.17),(10.23,36.95),(10.33,36.88),(10.30,36.82),(10.28,36.77),(10.34,36.72),(10.49,36.70),(10.57,36.82),(10.70,36.93),(10.86,37.02),(11.01,37.05),(11.06,37.08),(11.12,36.85),(11.00,36.78),(10.87,36.58),(10.74,36.45),(10.60,36.39),(10.53,36.25),(10.50,36.03),(10.60,35.90),(10.68,35.80),(10.78,35.72)]
land=coast+[(8.25,35.72)]
poly=" ".join("%s,%s"%P(*p) for p in land)
lake=[(9.78,37.20),(9.92,37.20),(9.95,37.15),(9.82,37.13)]
lakep=" ".join("%s,%s"%P(*p) for p in lake)
r=list(csv.DictReader(open(src,encoding='utf-8-sig')))
g=[]
beach=collections.defaultdict(lambda:[0,0,0,''])
for x in r:
    if not x['latitude']: continue
    lat,lon=float(x['latitude']),float(x['longitude'])
    if not(L0<lon<L1 and A0<lat<A1): continue
    if x['program_id']=='BEACH-2026':
        k=(round(lat,3),round(lon,3)); b=beach[k]; b[0]+=1; b[1]+=int(x['lifeguards_planned'] or 0); b[2]+=int(x['lifeguards_deployed'] or 0); b[3]=x['place_name']
for (lat,lon),(n,pl,dp,name) in beach.items():
    x,y=P(lon,lat); rad=min(4+pl**0.5*1.3,14); low=dp<pl*0.5
    g.append(f'<circle cx="{x}" cy="{y}" r="{rad:.1f}" fill="#2bb3e6" fill-opacity="0.55" stroke="{"#ff9d2e" if low else "#bfeeff"}" stroke-width="{2.2 if low else 1.2}"></circle>')
for x0 in r:
    if not x0['latitude']: continue
    lat,lon=float(x0['latitude']),float(x0['longitude'])
    if not(L0<lon<L1 and A0<lat<A1): continue
    x,y=P(lon,lat)
    if x0['program_id']=='SEAS-2026':
        g.append(f'<path d="M{x},{y-9} L{x+8},{y+6} L{x-8},{y+6} Z" fill="#5cc26b" stroke="#0e1a33" stroke-width="1.5"></path>')
    elif x0['program_id']=='ROAD-2026':
        g.append(f'<rect x="{x-7}" y="{y-7}" width="14" height="14" rx="3" fill="#e5484d" stroke="#fff" stroke-width="1.5"></rect><path d="M{x-4},{y} H{x+4} M{x},{y-4} V{y+4}" stroke="#fff" stroke-width="2"></path>')
# selected Hammamet
hx,hy=P(10.61768,36.39415)
sel=f'<circle cx="{hx}" cy="{hy}" r="20" fill="none" stroke="#e08600" stroke-width="2.5" stroke-dasharray="4 3"></circle>'
labels=[("بنزرت",9.86,37.29),("تونس",10.18,36.80),("نابل",10.74,36.45),("قليبية",11.11,36.85),("جندوبة",8.78,36.50),("باجة",9.18,36.73),("الكاف",8.71,36.18),("زغوان",10.14,36.40),("سوسة",10.62,35.83),("طبرقة",8.76,36.95)]
lab="".join(f'<text x="{P(lo,la)[0]+ (8 if n not in ("قليبية",) else -50)}" y="{P(lo,la)[1]+4}" font-size="12" fill="#9fb0d6">{n}</text>' for n,lo,la in labels)
grid="".join(f'<line x1="{i}" y1="0" x2="{i}" y2="{H}" stroke="#1d2c52" stroke-width="1"></line>' for i in range(0,W,80))+"".join(f'<line x1="0" y1="{j}" x2="{W}" y2="{j}" stroke="#1d2c52" stroke-width="1"></line>' for j in range(0,H,80))
svg=f'''<svg viewBox="0 0 {W} {H}" style="display: block; width: 100%; height: auto" xmlns="http://www.w3.org/2000/svg"><rect width="{W}" height="{H}" fill="#0b1630"></rect>{grid}<polygon points="{poly}" fill="#16264a" stroke="#3a5592" stroke-width="1.5"></polygon><polygon points="{lakep}" fill="#0b1630" stroke="#3a5592"></polygon>{lab}{"".join(g)}{sel}</svg>'''
open(out,'w').write(svg)
print(len(beach),len(g), hx,hy)
