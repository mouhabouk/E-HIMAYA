"""Quality check of the OSM POI export, one row per layer."""
import json, sys, csv, math, os, glob
from collections import Counter, defaultdict

root = sys.argv[1]
SENSITIVE = {"barracks", "oil_gas", "national_guard", "police", "ministries", "fire_hydrants", "factories", "companies"}
BBOX = (7.4, 30.1, 11.7, 37.6)  # lon_min, lat_min, lon_max, lat_max (Tunisia incl. coast, Galite, Djerba, Kerkennah)


def rep(geom):
    t = geom["type"]
    c = geom["coordinates"]
    if t == "Point":
        return c
    if t == "LineString":
        return c[len(c) // 2]
    if t == "MultiLineString":
        return c[0][len(c[0]) // 2]
    if t == "Polygon":
        r = c[0]
        return [sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)]
    if t == "MultiPolygon":
        r = c[0][0]
        return [sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)]
    return None


def dist(a, b):
    R = 6371000
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dl = la2 - la1
    dn = math.radians(b[0] - a[0])
    h = math.sin(dl / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dn / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


rows = []
for f in sorted(glob.glob(os.path.join(root, "geojson", "*.geojson"))):
    layer = os.path.basename(f)[:-8]
    if layer == "all_points":
        continue
    fc = json.load(open(f, encoding="utf-8"))
    feats = fc["features"]
    n = len(feats)
    gt = Counter(x["geometry"]["type"] for x in feats if x.get("geometry"))
    nogeom = sum(1 for x in feats if not x.get("geometry"))
    P = [x["properties"] for x in feats]
    named = sum(1 for p in P if p.get("name") and p["name"] != "(بدون اسم)")
    phone = sum(1 for p in P if p.get("phone"))
    deleg = sum(1 for p in P if p.get("delegation_ar"))
    gov = sum(1 for p in P if p.get("governorate_code"))
    osmid = Counter((p.get("osm_type"), p.get("osm_id")) for p in P)
    dup_id = sum(v - 1 for v in osmid.values() if v > 1)
    noid = sum(1 for p in P if not p.get("osm_id"))
    out = 0
    pts = []
    for x in feats:
        if not x.get("geometry"):
            continue
        r = rep(x["geometry"])
        if r is None:
            continue
        if not (BBOX[0] <= r[0] <= BBOX[2] and BBOX[1] <= r[1] <= BBOX[3]):
            out += 1
        pts.append((r, (x["properties"].get("name") or "").strip()))
    # near duplicates: same non-empty name within 50 m (grid bucketing)
    near = 0
    if gt.get("Point", 0) == n:
        grid = defaultdict(list)
        for i, (r, nm) in enumerate(pts):
            grid[(round(r[0] / 0.001), round(r[1] / 0.001))].append(i)
        seen = set()
        for i, (r, nm) in enumerate(pts):
            if not nm or nm == "(بدون اسم)":
                continue
            gx, gy = round(r[0] / 0.001), round(r[1] / 0.001)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy), []):
                        if j > i and pts[j][1] == nm and dist(r, pts[j][0]) < 50 and j not in seen:
                            near += 1
                            seen.add(j)
    # cross-format counts
    def cnt_csv(p):
        try:
            with open(p, encoding="utf-8-sig") as fh:
                return sum(1 for _ in csv.reader(fh)) - 1
        except FileNotFoundError:
            return None
    def cnt_json(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            return len(d) if isinstance(d, list) else len(d.get("features", d.get("items", [])))
        except FileNotFoundError:
            return None
    c_csv = cnt_csv(os.path.join(root, "csv", layer + ".csv"))
    c_json = cnt_json(os.path.join(root, "json", layer + ".json"))
    rows.append(dict(layer=layer, cat_ar=P[0].get("category_ar") if P else "", n=n, geom=dict(gt), nogeom=nogeom,
                     named=named, phone=phone, deleg=deleg, gov=gov, dup_id=dup_id, noid=noid, out=out, near=near,
                     csv=c_csv, json=c_json, sensitive=layer in SENSITIVE,
                     subtypes=Counter(p.get("subtype") for p in P).most_common(6)))

json.dump(rows, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in rows:
    print(f"{r['layer']:16} {r['cat_ar']:14} n={r['n']:6} geom={r['geom']} named={100*r['named']//max(r['n'],1):3}% "
          f"phone={100*r['phone']//max(r['n'],1):3}% deleg={100*r['deleg']//max(r['n'],1):3}% gov={100*r['gov']//max(r['n'],1):3}% "
          f"dupID={r['dup_id']} noID={r['noid']} out={r['out']} near50m={r['near']} csv={r['csv']} json={r['json']}")
