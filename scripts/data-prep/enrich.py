"""Enrich the OSM beach layer with suggested names (Overpass, 27 Oct 2026) and add named beach points."""
import csv, json, math, re, sys
from collections import Counter

base, match, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
F = json.load(open(base, encoding="utf-8"))["features"]
txt = open(match, encoding="utf-8").read().strip()
main, extra = txt.split("\nEXTRA\n")
M = {}
for r in main.split(";"):
    i, node, place, ptype, pd = r.split("|")
    M[int(i)] = (node, place, ptype, float(pd))
X = []
for r in extra.strip().split(";"):
    i, name, lat, lon = r.rsplit(",", 3)
    X.append((int(i), name.replace("_", " "), float(lat), float(lon)))

ISLANDS = [  # bounding boxes, named from geography
    ("جزيرة جالطة", 37.45, 37.58, 8.80, 9.00),
    ("جزيرة زمبرة", 37.08, 37.16, 10.76, 10.86),
    ("جزر قوريا", 35.74, 35.82, 10.97, 11.05),
]
PTYPE = {"c": "مدينة", "t": "بلدة", "v": "قرية", "s": "حي", "n": "حي", "h": "تجمّع", "l": "موقع"}
ar = lambda s: bool(re.search(r"[؀-ۿ]", s))


def suggest(name, node, place, pd, lat, lon):
    if name:
        return name, "OSM: اسم الشاطئ نفسه", "مؤكد"
    for nm, a1, a2, o1, o2 in ISLANDS:
        if a1 <= lat <= a2 and o1 <= lon <= o2:
            return "شاطئ " + nm, "الموقع الجغرافي (جزيرة)", "مرتفعة"
    if node:
        return node, "OSM: نقطة شاطئ مسماة على أقل من 1.5 كم", "مرتفعة"
    nm = place if place.startswith("شاطئ") else (("شاطئ " if ar(place) else "Plage ") + place)
    if pd <= 1:
        return nm, f"أقرب تجمّع سكني على {pd} كم", "متوسطة"
    if pd <= 3:
        return nm, f"أقرب تجمّع سكني على {pd} كم", "منخفضة"
    return nm, f"أقرب تجمّع سكني على {pd} كم", "للمراجعة"


feats, rows = [], []
GOV = {}
for f in F:
    p = f["properties"]
    g = f["geometry"]
    ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
    lat = sum(x[1] for x in ring) / len(ring)
    lon = sum(x[0] for x in ring) / len(ring)
    name = p["name"] if p["name"] != "(بدون اسم)" else ""
    node, place, ptype, pd = M[p["osm_id"]]
    s, src, conf = suggest(name, node, place, pd, lat, lon)
    GOV[(round(lat, 3), round(lon, 3))] = (p["governorate_code"], p["governorate_ar"])
    props = {"osm_id": p["osm_id"], "osm_type": p["osm_type"], "osm_url": p["osm_url"], "geometry_kind": "مساحة",
             "governorate_code": p["governorate_code"], "governorate_ar": p["governorate_ar"],
             "name_osm": name or None, "name_suggested": s, "name_source": src, "name_confidence": conf,
             "nearest_place": place, "nearest_place_type": PTYPE[ptype], "nearest_place_km": pd,
             "verified_by_admin": False, "data_source": "OpenStreetMap (ODbL)", "osm_snapshot": "2026-10-27"}
    feats.append({"type": "Feature", "geometry": g, "properties": props})
    rows.append([p["osm_id"], "مساحة", p["governorate_ar"], round(lat, 5), round(lon, 5), name, s, src, conf, p["osm_url"]])

pts = list(GOV.items())
for i, name, lat, lon in X:
    (code, gov) = min(pts, key=lambda kv: math.hypot(kv[0][0] - lat, kv[0][1] - lon))[1]
    props = {"osm_id": i, "osm_type": "node", "osm_url": f"https://www.openstreetmap.org/node/{i}", "geometry_kind": "نقطة",
             "governorate_code": code, "governorate_ar": gov, "name_osm": name, "name_suggested": name,
             "name_source": "OSM: نقطة شاطئ مسماة، غير موجودة في الاستخراج الأول", "name_confidence": "مؤكد",
             "verified_by_admin": False, "data_source": "OpenStreetMap (ODbL)", "osm_snapshot": "2026-10-27",
             "governorate_note": "مقدّرة من أقرب شاطئ؛ تُعاد بالحدود الإدارية عند الاستيراد"}
    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props})
    rows.append([i, "نقطة", gov, lat, lon, name, name, props["name_source"], "مؤكد", props["osm_url"]])

json.dump({"type": "FeatureCollection", "name": "beaches_enriched_2026-10-27",
           "attribution": "© OpenStreetMap contributors (ODbL)", "features": feats},
          open(f"{out_dir}/beaches_enriched.geojson", "w", encoding="utf-8"), ensure_ascii=False)
with open(f"{out_dir}/beaches_enriched_review.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["osm_id", "الهندسة", "الولاية", "lat", "lon", "الاسم في OSM", "الاسم المقترح", "مصدر الاسم", "درجة الثقة", "رابط OSM"])
    order = {"مؤكد": 0, "مرتفعة": 1, "متوسطة": 2, "منخفضة": 3, "للمراجعة": 4}
    w.writerows(sorted(rows, key=lambda r: (r[2], order[r[8]])))

c = Counter(r[8] for r in rows)
print("total", len(rows), dict(c))
print("by gov", Counter(r[2] for r in rows).most_common())
print("distinct suggested names", len({r[6] for r in rows}))
REAL = ["عين مريم", "رفراف", "أنجيلا", "غار الملح", "الحمامات", "المنصورة", "الهوارية", "القنطاوي", "بوجعفر", "سكانس", "سقانس", "المهدية",
        "هيبون", "الشفار", "قرقنة", "شط السلام", "سيدي محرز", "رأس الرمل", "أغير", "جرجيس"]
LAT = {"عين مريم": "Ain Mariem", "رفراف": "Rafraf", "أنجيلا": "Angela", "القنطاوي": "Kantaoui", "سيدي محرز": "Mahrez", "رأس الرمل": "Ras Rmel",
       "أغير": "Aghir", "سكانس": "Skanes", "هيبون": "Hiboun"}
for n in REAL:
    hits = [r for r in rows if n in (r[6] + " " + r[5]) or (n in LAT and LAT[n] in (r[6] + " " + r[5]))]
    print(f"{n}: {len(hits)}")
