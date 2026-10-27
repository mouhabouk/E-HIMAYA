"""Suggest names + confidence for unnamed OSM features in all layers (beaches done separately).
Inputs: geojson dir, places file (Overpass place nodes, 27-10-2026). Output: enriched geojson per layer + review rows json."""
import json, math, re, sys, os, collections

gdir, places_f, out_dir = sys.argv[1:4]
os.makedirs(out_dir, exist_ok=True)
UNNAMED = (None, "", "(بدون اسم)")
ar = lambda s: bool(re.search(r"[؀-ۿ]", s or ""))
PT = {"c": "مدينة", "t": "بلدة", "v": "قرية", "s": "حي", "q": "حي", "n": "حي", "h": "تجمّع ريفي", "l": "موقع مسمّى", "d": "مسكن معزول"}

# ---------- places grid ----------
PL = []
for r in open(places_f, encoding="utf-8").read().strip().split(";"):
    lat, lon, t, n = r.split(",", 3)
    PL.append((float(lat), float(lon), t, n.strip()))
G = collections.defaultdict(list)
for i, (la, lo, t, n) in enumerate(PL):
    G[(int(la * 10), int(lo * 10))].append(i)


def km(a, b, c, d):
    x = math.radians(d - b) * math.cos(math.radians((a + c) / 2)); y = math.radians(c - a)
    return 6371 * math.hypot(x, y)


def nearest_place(lat, lon):
    best = None
    for rad in (1, 2, 4, 8, 20):
        ci, cj = int(lat * 10), int(lon * 10)
        for i in range(ci - rad, ci + rad + 1):
            for j in range(cj - rad, cj + rad + 1):
                for k in G.get((i, j), ()):
                    p = PL[k]
                    # prefer populated places: penalise "locality"/"isolated" slightly
                    d = km(lat, lon, p[0], p[1]) * (1.3 if p[2] in "ld" else 1)
                    if best is None or d < best[0]:
                        best = (d, k)
        if best and best[0] < rad * 8:
            break
    d, k = best
    return PL[k], round(km(lat, lon, PL[k][0], PL[k][1]), 2)


def where(p, d):
    """Locative phrase: 'ب<قرية>' / 'قرب <قرية>'."""
    n = p[3]
    if d <= 1.0:
        return (" ب" + n) if ar(n) and not n.startswith(("حي", "مركز", "دوار", "باب")) else (" " + n if ar(n) else " – " + n)
    return " قرب " + n


def conf_by_dist(d):
    return "متوسطة" if d <= 1 else ("منخفضة" if d <= 3 else "للمراجعة")


# ---------- generic class names ----------
COMP = {"estate_agent": "وكالة عقارية", "lawyer": "مكتب محاماة", "company": "شركة", "notary": "مكتب عدل إشهاد", "yes": "مكتب",
        "educational_institution": "مؤسسة تعليمية", "insurance": "وكالة تأمين", "research": "مركز بحث", "association": "جمعية",
        "it": "شركة إعلامية", "diplomatic": "مقر دبلوماسي", "telecommunication": "مكتب اتصالات", "security": "شركة حراسة",
        "architect": "مكتب مهندس معماري", "graphic_design": "مكتب تصميم", "accountant": "مكتب محاسبة", "political_party": "مقر حزب",
        "water_utility": "مكتب الماء", "ngo": "منظمة", "travel_agent": "وكالة أسفار", "forestry": "مكتب الغابات", "physician": "عيادة طبيب"}
FACT = {"depot": "مستودع", "scrap_yard": "ساحة خردة", "port": "منشأة مينائية", "mine": "منجم", "chemical": "مصنع كيميائي",
        "factory": "مصنع", "manufacturing": "وحدة تصنيع"}
SPORT = {"soccer": "ملعب كرة قدم", "football": "ملعب كرة قدم", "swimming": "مسبح", "basketball": "ملعب كرة سلة", "shooting": "ميدان رماية"}
SUPER = {"supermarket": "مغازة عامة", "mall": "مركز تجاري", "wholesale": "مغازة بيع بالجملة", "department_store": "مغازة كبرى"}


def generic(layer, p):
    st, act = p.get("subtype") or "", p.get("activity") or ""
    if layer == "airports": return "مهبط طائرات"
    if layer == "barracks": return "منشأة عسكرية"
    if layer == "bus_stations":
        return "محطة لواج" if "louage" in (p.get("name_en") or "").lower() else "محطة نقل بري"
    if layer == "bus_stops": return "موقف حافلات"
    if layer == "civil_protection": return "مركز الحماية المدنية"
    if layer == "clinics": return "مصحة"
    if layer == "companies": return COMP.get(st, "مؤسسة")
    if layer == "elderly_homes": return "دار رعاية المسنين"
    if layer == "factories": return FACT.get(st, "مصنع")
    if layer == "fire_hydrants": return "حنفية إطفاء"
    if layer == "forests": return "غابة"
    if layer == "fuel_stations": return "محطة وقود" + (" " + p["brand"] if p.get("brand") else "")
    if layer == "hospitals": return "مؤسسة استشفائية"
    if layer == "hotels": return "نُزُل"
    if layer == "institutes": return "معهد"
    if layer == "lakes": return {"بحيرة": "بحيرة", "بحيرة شاطئية": "بحيرة شاطئية"}.get(st, "بحيرة جبلية / خزان مائي")
    if layer == "oil_gas": return "بئر نفط" if act == "oil" or st == "oil" else ("مصفاة" if st == "refinery" else "منشأة محروقات")
    if layer == "pharmacies": return "صيدلية"
    if layer == "police": return "مركز أمن"
    if layer == "railways": return "خط حديدي" + (" صناعي" if "industrial" in st else (" فرعي" if "branch" in st else ""))
    if layer == "rivers": return "قناة" if st == "قناة" else ("وادٍ موسمي" if "موسمي" in st else "وادٍ")
    if layer == "schools": return "مدرسة" if st != "إعدادي" else "مدرسة إعدادية"
    if layer == "sports": return SPORT.get(act, "ملعب" if st == "stadium" else "مركب رياضي")
    if layer == "supermarkets": return SUPER.get(st, "مغازة")
    if layer == "train_stations": return {"موقف قطار": "موقف قطار", "محطة": "محطة قطار", "مترو خفيف": "محطة مترو خفيف"}.get(st, "محطة قطار")
    if layer == "worship":
        return {"muslim": "مسجد", "jewish": "كنيس", "christian": "كنيسة"}.get(p.get("religion"), "معلم ديني")
    return p.get("category_ar") or layer


def centroid(g):
    t, c = g["type"], g["coordinates"]
    if t == "Point": return c[1], c[0]
    if t == "LineString": pts = c
    elif t == "Polygon": pts = c[0]
    elif t == "MultiPolygon": pts = max((pp[0] for pp in c), key=len)
    elif t == "MultiLineString": pts = max(c, key=len)
    else: pts = [c]
    if t == "LineString" or t == "MultiLineString":
        m = pts[len(pts) // 2]; return m[1], m[0]
    return sum(x[1] for x in pts) / len(pts), sum(x[0] for x in pts) / len(pts)


GENERIC_EN = re.compile(r"^(bus|louage|taxi|local)?\s*(station|stop|louage)?\s*(station|louage)?$", re.I)
DUP_R = {"hospitals": .3, "clinics": .1, "universities": .3, "hotels": .1}  # km
CONF_ORDER = {"مؤكد": 0, "مرتفعة": 1, "متوسطة": 2, "منخفضة": 3, "للمراجعة": 4}

# ---------- line networks: propagate names via shared endpoints ----------
def line_propagation(F, tributary=False):
    key = lambda c: (round(c[0], 5), round(c[1], 5))
    ends = collections.defaultdict(set)
    for i, f in enumerate(F):
        c = f["geometry"]["coordinates"]
        if f["geometry"]["type"] != "LineString": continue
        ends[key(c[0])].add(i); ends[key(c[-1])].add(i)
    name = {i: f["properties"]["name"] for i, f in enumerate(F) if f["properties"]["name"] not in UNNAMED}
    got = {}
    for rnd in (1, 2, 3, 4, 5, 6):
        new = {}
        for i, f in enumerate(F):
            if i in name or i in got or f["geometry"]["type"] != "LineString": continue
            c = f["geometry"]["coordinates"]
            a = {name.get(j) or got.get(j, (None,))[0] for j in ends[key(c[0])] if j != i} - {None}
            b = {name.get(j) or got.get(j, (None,))[0] for j in ends[key(c[-1])] if j != i} - {None}
            both = a & b
            if len(both) == 1:
                new[i] = (both.pop(), "مرتفعة" if rnd <= 2 else "متوسطة", f"OSM: يتصل من الطرفين بمقطع مسمّى (جولة {rnd})")
            elif len(a | b) == 1 and rnd <= 3:
                nm1 = (a | b).pop()
                if tributary:
                    if rnd == 1:
                        new[i] = ("رافد " + nm1, "متوسطة", "OSM: يصبّ في مجرى مسمّى (اتصال من طرف واحد)")
                else:
                    new[i] = (nm1, "متوسطة", f"OSM: يتصل من طرف واحد بمقطع مسمّى (جولة {rnd})")
            elif len(a | b) > 1:
                pass  # junction of different names: leave descriptive
        if not new: break
        got.update(new)
    return got


rows, summary = [], []
for fn in sorted(os.listdir(gdir)):
    layer = fn[:-8]
    if not fn.endswith(".geojson") or layer in ("all_points", "beaches"): continue
    FC = json.load(open(os.path.join(gdir, fn), encoding="utf-8"))
    F = FC["features"]
    named_pts = [(centroid(f["geometry"]), f["properties"]["name"]) for f in F if f["properties"].get("name") not in UNNAMED]
    prop = line_propagation(F, layer == "rivers") if layer in ("railways", "rivers") else {}
    cnt = collections.Counter()
    for i, f in enumerate(F):
        p = f["properties"]
        nm = p.get("name")
        if nm not in UNNAMED:
            p.update(name_suggested=nm, name_source="OSM: الاسم نفسه", name_confidence="مؤكد", needs_review=False)
            continue
        lat, lon = centroid(f["geometry"])
        pl, d = nearest_place(lat, lon)
        gen = generic(layer, p)
        en = (p.get("name_en") or "").strip()
        city, addr = (p.get("city") or "").strip(), (p.get("address") or "").strip()
        dup = None
        if layer in DUP_R or layer in ("pharmacies", "schools", "worship", "police", "civil_protection", "fuel_stations", "supermarkets", "sports", "bus_stations"):
            r = DUP_R.get(layer, .05)
            cand = [(km(lat, lon, a, b), n) for (a, b), n in named_pts if abs(a - lat) < .01 and abs(b - lon) < .01]
            cand = [c for c in cand if c[0] <= r]
            if cand: dup = min(cand)
        if i in prop:
            s, conf, src = prop[i][0], prop[i][1], prop[i][2]
        elif en and not GENERIC_EN.match(en):
            s, conf, src = f"{gen} – {en}", "مرتفعة", "OSM: الاسم بالإنجليزية (name:en)"
        elif dup and dup[0] <= .03:
            s, conf, src = dup[1], "مرتفعة", f"OSM: عنصر مسمّى من نفس الطبقة على {int(dup[0]*1000)} م (تكرار محتمل)"
        elif dup:
            s, conf, src = f"{gen} قرب {dup[1]}" if layer not in ("hospitals", "universities") else f"{dup[1]} (مبنى أو مدخل تابع محتمل)", "متوسطة", f"OSM: عنصر مسمّى من نفس الطبقة على {int(dup[0]*1000)} م"
        elif addr:
            s = f"{gen} – {addr}" + (f"، {city}" if city else "")
            conf, src = ("متوسطة" if d <= 3 else "منخفضة"), "OSM: العنوان (addr) + أقرب تجمّع"
        else:
            s = gen + where(pl, d)
            conf = conf_by_dist(d)
            src = f"أقرب تجمّع ({PT[pl[2]]}) على {d} كم"
            if city and d > 1:
                s, src = f"{gen} – {city}", f"OSM: المدينة (addr:city)؛ أقرب تجمّع على {d} كم"
                conf = "منخفضة" if d <= 5 else "للمراجعة"
        sens = layer in ("barracks", "oil_gas")
        p.update(name_suggested=s, name_source=src, name_confidence=conf, nearest_place=pl[3],
                 nearest_place_type=PT[pl[2]], nearest_place_km=d, possible_duplicate=bool(dup and dup[0] <= .03 and i not in prop),
                 needs_review=conf in ("منخفضة", "للمراجعة") or bool(dup and dup[0] <= .03), verified_by_admin=False, osm_snapshot="2026-10-27")
        cnt[conf] += 1
        rows.append([layer, p.get("category_ar"), p.get("osm_id"), p.get("osm_type"), p.get("governorate_ar"), round(lat, 5), round(lon, 5),
                     gen, s, src, conf, pl[3], d, "نعم" if p["possible_duplicate"] else "", "حساسة" if sens else "", p.get("osm_url")])
    FC["name"] = f"{layer}_enriched_2026-10-27"
    FC["attribution"] = "© OpenStreetMap contributors (ODbL)"
    json.dump(FC, open(os.path.join(out_dir, f"{layer}_enriched.geojson"), "w", encoding="utf-8"), ensure_ascii=False)
    summary.append([layer, F[0]["properties"].get("category_ar") if F else "", len(F), sum(cnt.values())] + [cnt[k] for k in CONF_ORDER])

rows.sort(key=lambda r: (r[0], r[4] or "", CONF_ORDER[r[10]]))
json.dump({"rows": rows, "summary": summary}, open(os.path.join(out_dir, "_review.json"), "w", encoding="utf-8"), ensure_ascii=False)
tot = collections.Counter()
for s in summary:
    print(s)
    for k, v in zip(CONF_ORDER, s[4:]): tot[k] += v
print("TOTAL unnamed", len(rows), dict(tot))
