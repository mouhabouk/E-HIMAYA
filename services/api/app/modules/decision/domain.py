"""Vocabulary and rule tables of decision support: what each kind of incident usually needs, in which words.

These tables are the transparent part of the recommendations (FR-C-11): an operator can read here why a fire engine
or a diver is proposed. They encode common civil-protection practice summarised in docs/procedures; units and
committees tune them through review of this file, not at run time.
"""

from typing import Literal

from app.modules.reports.domain import Category

Lang = Literal["ar", "fr"]
Bilingual = dict[str, str]
Confidence = Literal["low", "medium", "high"]
RecommendationKind = Literal["resources", "volunteers", "route", "escalation", "alert", "responders"]

FIRE_DANGER_CLASSES = ("low", "moderate", "high", "very_high", "extreme")
RAIN_LEVELS = ("none", "watch", "warning")


def danger_at_least(value: str | None, threshold: str) -> bool:
    return value in FIRE_DANGER_CLASSES and FIRE_DANGER_CLASSES.index(value) >= FIRE_DANGER_CLASSES.index(threshold)


def rain_at_least(value: str | None, threshold: str) -> bool:
    return value in RAIN_LEVELS and RAIN_LEVELS.index(value) >= RAIN_LEVELS.index(threshold)


CATEGORY_LABELS: dict[str, Bilingual] = {
    Category.SOS: {"ar": "نداء استغاثة", "fr": "SOS"},
    Category.FIRE: {"ar": "حريق", "fr": "incendie"},
    Category.FLOOD: {"ar": "فيضان", "fr": "inondation"},
    Category.TRAFFIC_ACCIDENT: {"ar": "حادث مرور", "fr": "accident de la circulation"},
    Category.DROWNING: {"ar": "غرق", "fr": "noyade"},
    Category.LANDSLIDE: {"ar": "انزلاق أرضي", "fr": "glissement de terrain"},
    Category.CHEMICAL_LEAK: {"ar": "تسرب مادة كيميائية", "fr": "fuite de produit chimique"},
    Category.MEDICAL: {"ar": "حالة طبية", "fr": "urgence médicale"},
    Category.OTHER: {"ar": "حادثة أخرى", "fr": "autre incident"},
}

RESOURCE_LABELS: dict[str, Bilingual] = {
    "fire_engine": {"ar": "شاحنة إطفاء", "fr": "fourgon d'incendie"},
    "water_tanker": {"ar": "شاحنة صهريج ماء", "fr": "camion-citerne d'eau"},
    "ambulance": {"ar": "سيارة إسعاف", "fr": "ambulance"},
    "rescue_vehicle": {"ar": "آلية نجدة وإنقاذ", "fr": "véhicule de secours et sauvetage"},
    "heavy_equipment": {"ar": "آلية ثقيلة", "fr": "engin lourd"},
    "drone": {"ar": "طائرة مسيرة", "fr": "drone"},
    "large_extinguisher": {"ar": "مطفأة كبيرة", "fr": "grand extincteur"},
    "boat": {"ar": "قارب", "fr": "embarcation"},
    "command_vehicle": {"ar": "سيارة قيادة", "fr": "véhicule de commandement"},
    "other": {"ar": "وسيلة أخرى", "fr": "autre moyen"},
}

SKILL_LABELS: dict[str, Bilingual] = {
    "first_aid": {"ar": "الإسعافات الأولية", "fr": "premiers secours"},
    "diving": {"ar": "الغوص", "fr": "plongée"},
    "heavy_vehicles": {"ar": "الآليات الثقيلة", "fr": "engins lourds"},
    "firefighting": {"ar": "مكافحة الحرائق", "fr": "lutte contre l'incendie"},
    "search_rescue": {"ar": "البحث والإنقاذ", "fr": "recherche et sauvetage"},
    "logistics": {"ar": "الإمداد", "fr": "logistique"},
    "medical": {"ar": "طبي", "fr": "médical"},
    "other": {"ar": "أخرى", "fr": "autre"},
}

# Vehicles routed with the truck profile (weight, height, width restrictions of the road network).
TRUCK_KINDS = frozenset({"fire_engine", "water_tanker", "heavy_equipment", "boat", "large_extinguisher"})

# First response by category: resource kind → count (before the aggravating factors of recommendations.py).
BASE_NEEDS: dict[str, dict[str, int]] = {
    Category.FIRE: {"fire_engine": 1, "water_tanker": 1},
    Category.FLOOD: {"rescue_vehicle": 1, "boat": 1},
    Category.TRAFFIC_ACCIDENT: {"rescue_vehicle": 1, "ambulance": 1},
    Category.DROWNING: {"boat": 1, "ambulance": 1},
    Category.LANDSLIDE: {"heavy_equipment": 1, "rescue_vehicle": 1},
    Category.CHEMICAL_LEAK: {"fire_engine": 1, "rescue_vehicle": 1, "command_vehicle": 1},
    Category.MEDICAL: {"ambulance": 1},
    Category.SOS: {"rescue_vehicle": 1, "ambulance": 1},
    Category.OTHER: {"rescue_vehicle": 1},
}

# Volunteer skills worth calling out per category (none for chemical leaks: volunteers stay out of contaminated
# zones, docs/procedures/chemical-leak.*).
VOLUNTEER_SKILLS: dict[str, tuple[str, ...]] = {
    Category.FIRE: ("firefighting", "first_aid"),
    Category.FLOOD: ("search_rescue", "logistics"),
    Category.TRAFFIC_ACCIDENT: ("first_aid",),
    Category.DROWNING: ("diving", "first_aid"),
    Category.LANDSLIDE: ("search_rescue", "heavy_vehicles"),
    Category.CHEMICAL_LEAK: (),
    Category.MEDICAL: ("medical", "first_aid"),
    Category.SOS: ("first_aid", "search_rescue"),
    Category.OTHER: (),
}

# Hazard of the public alert form (phase 5 notify schemas) proposed per category; None: no public alert by rule.
ALERT_HAZARD: dict[str, str | None] = {
    Category.FIRE: "forest_fire",
    Category.FLOOD: "flood",
    Category.CHEMICAL_LEAK: "chemical",
    Category.LANDSLIDE: "other",
    Category.TRAFFIC_ACCIDENT: None,
    Category.DROWNING: None,
    Category.MEDICAL: None,
    Category.SOS: None,
    Category.OTHER: None,
}

# Prefilled texts of a suggested public alert; {place} is the gouvernorat name. Reviewed and edited by a human before
# anything is sent (the alert endpoint of phase 5).
ALERT_TEXTS: dict[str, dict[str, dict[str, str]]] = {
    "forest_fire": {
        "title": {
            "ar": "حريق غابات في {place_ar}",
            "fr": "Feu de forêt — {place_fr}",
            "en": "Forest fire — {place_fr}",
        },
        "body": {
            "ar": "حريق غابات يتطور في {place_ar}. ابتعدوا عن المنطقة واتبعوا تعليمات الحماية المدنية. "
            "لا تستعملوا الطرقات المحاذية للحريق. النجدة: 198.",
            "fr": "Un feu de forêt se développe — {place_fr}. Éloignez-vous de la zone et suivez les consignes de la "
            "protection civile. N'empruntez pas les routes proches du feu. Urgence : 198.",
            "en": "A forest fire is spreading — {place_fr}. Keep away from the area and follow civil protection "
            "instructions. Avoid roads near the fire. Emergency: 198.",
        },
    },
    "flood": {
        "title": {
            "ar": "خطر فيضان في {place_ar}",
            "fr": "Risque d'inondation — {place_fr}",
            "en": "Flood risk — {place_fr}",
        },
        "body": {
            "ar": "أمطار غزيرة وخطر فيضان في {place_ar}. ابتعدوا عن الأودية والمناطق المنخفضة، ولا تعبروا المياه "
            "الجارية لا مشيا ولا بالسيارة. النجدة: 198.",
            "fr": "Fortes pluies et risque d'inondation — {place_fr}. Éloignez-vous des oueds et des zones basses, ne "
            "traversez pas l'eau en mouvement, ni à pied ni en voiture. Urgence : 198.",
            "en": "Heavy rain and flood risk — {place_fr}. Keep away from wadis and low areas; do not cross moving "
            "water on foot or by car. Emergency: 198.",
        },
    },
    "chemical": {
        "title": {
            "ar": "تسرب مادة خطرة في {place_ar}",
            "fr": "Fuite de produit dangereux — {place_fr}",
            "en": "Hazardous material leak — {place_fr}",
        },
        "body": {
            "ar": "تسرب مادة خطرة في {place_ar}. ابقوا داخل المباني وأغلقوا الأبواب والنوافذ وأوقفوا التهوئة إلى "
            "حين رفع التعليمات. النجدة: 198.",
            "fr": "Fuite de produit dangereux — {place_fr}. Restez à l'intérieur, fermez portes et fenêtres, arrêtez "
            "la ventilation jusqu'à la levée des consignes. Urgence : 198.",
            "en": "Hazardous material leak — {place_fr}. Stay indoors, close doors and windows and turn off "
            "ventilation until further notice. Emergency: 198.",
        },
    },
    "other": {
        "title": {
            "ar": "خطر انزلاق أرضي في {place_ar}",
            "fr": "Risque de glissement de terrain — {place_fr}",
            "en": "Landslide risk — {place_fr}",
        },
        "body": {
            "ar": "خطر انزلاق أرضي في {place_ar}. ابتعدوا عن المنحدرات والبنايات المتضررة واتبعوا تعليمات الحماية "
            "المدنية. النجدة: 198.",
            "fr": "Risque de glissement de terrain — {place_fr}. Éloignez-vous des pentes et des constructions "
            "endommagées et suivez les consignes de la protection civile. Urgence : 198.",
            "en": "Landslide risk — {place_fr}. Keep away from slopes and damaged buildings and follow civil "
            "protection instructions. Emergency: 198.",
        },
    },
}

# ---------------------------------------------------------------- responders (FR-C-13)

AgencyKey = Literal[
    "samu",
    "police",
    "garde_nationale",
    "steg",
    "sonede",
    "forests",
    "anpe",
    "inm",
    "poison_center",
    "municipality",
    "equipment",
]

# National services involved by incident type, with their public emergency number when one exists nationally.
AGENCIES: dict[str, dict[str, object]] = {
    "samu": {"name": {"ar": "الإسعاف الطبي الاستعجالي", "fr": "SAMU"}, "phone": "190"},
    "police": {"name": {"ar": "الأمن الوطني", "fr": "Police nationale"}, "phone": "197"},
    "garde_nationale": {"name": {"ar": "الحرس الوطني", "fr": "Garde nationale"}, "phone": "193"},
    "steg": {"name": {"ar": "الشركة التونسية للكهرباء والغاز", "fr": "STEG (électricité et gaz)"}, "phone": None},
    "sonede": {
        "name": {"ar": "الشركة الوطنية لاستغلال وتوزيع المياه", "fr": "SONEDE (eau potable)"},
        "phone": None,
    },
    "forests": {"name": {"ar": "الإدارة العامة للغابات", "fr": "Direction Générale des Forêts"}, "phone": None},
    "anpe": {
        "name": {"ar": "الوكالة الوطنية لحماية المحيط", "fr": "ANPE (protection de l'environnement)"},
        "phone": None,
    },
    "inm": {"name": {"ar": "المعهد الوطني للرصد الجوي", "fr": "Institut National de la Météorologie"}, "phone": None},
    "poison_center": {
        "name": {"ar": "المركز الطبي للمساعدة الاستعجالية (مقاومة التسمم)", "fr": "CAMU — centre antipoison"},
        "phone": None,
    },
    "municipality": {"name": {"ar": "البلدية", "fr": "Municipalité"}, "phone": None},
    "equipment": {
        "name": {"ar": "الإدارة الجهوية للتجهيز", "fr": "Direction régionale de l'Équipement"},
        "phone": None,
    },
}

# Why each service is involved, per category (an empty list: none by rule). Classification-specific additions below.
AGENCY_RULES: dict[str, list[tuple[str, Bilingual]]] = {
    Category.FIRE: [
        ("police", {"ar": "تأمين الطوق وتنظيم المرور", "fr": "périmètre et circulation"}),
        ("steg", {"ar": "قطع الغاز والكهرباء عن المباني المتضررة", "fr": "coupure du gaz et de l'électricité"}),
    ],
    Category.FLOOD: [
        ("garde_nationale", {"ar": "غلق المعابر والطرقات المغمورة", "fr": "fermeture des gués et routes submergées"}),
        ("steg", {"ar": "قطع الكهرباء عن الأحياء المغمورة", "fr": "coupure de l'électricité des quartiers inondés"}),
        ("inm", {"ar": "تطور الأمطار والتحذيرات", "fr": "évolution de la pluie et vigilances"}),
        ("sonede", {"ar": "سلامة ماء الشرب", "fr": "sécurité de l'eau potable"}),
        ("municipality", {"ar": "مراكز الإيواء المؤقت", "fr": "hébergement provisoire"}),
    ],
    Category.TRAFFIC_ACCIDENT: [
        ("garde_nationale", {"ar": "تأمين الطريق والمعاينات", "fr": "sécurité de la route et constatations"}),
        ("police", {"ar": "تأمين الطريق داخل المدن", "fr": "sécurité de la route en ville"}),
    ],
    Category.DROWNING: [
        ("garde_nationale", {"ar": "الحرس البحري والبحث في الماء", "fr": "garde maritime et recherches en mer"}),
    ],
    Category.LANDSLIDE: [
        ("garde_nationale", {"ar": "غلق الطرقات المهددة", "fr": "fermeture des routes menacées"}),
        ("equipment", {"ar": "الخبرة الجيوتقنية وحالة الطرقات", "fr": "expertise géotechnique et routes"}),
        ("steg", {"ar": "قطع الغاز والكهرباء", "fr": "coupure du gaz et de l'électricité"}),
        ("sonede", {"ar": "فحص قنوات الماء", "fr": "contrôle des conduites d'eau"}),
    ],
    Category.CHEMICAL_LEAK: [
        ("police", {"ar": "الأطواق والإخلاء", "fr": "périmètres et évacuation"}),
        ("anpe", {"ar": "التلوث البيئي", "fr": "pollution de l'environnement"}),
        ("poison_center", {"ar": "التكفل بالمتسممين", "fr": "prise en charge des intoxications"}),
        ("samu", {"ar": "التكفل الطبي بعد إزالة التلوث", "fr": "prise en charge médicale après décontamination"}),
    ],
    Category.MEDICAL: [("samu", {"ar": "التكفل الطبي", "fr": "prise en charge médicale"})],
    Category.SOS: [("police", {"ar": "تحديد الوضعية وتأمينها", "fr": "lever le doute et sécuriser"})],
    Category.OTHER: [],
}

CLASSIFICATION_AGENCIES: dict[str, list[tuple[str, Bilingual]]] = {
    "forest_fire": [
        ("forests", {"ar": "مصالح الغابات وحراسها", "fr": "services et gardes forestiers"}),
        ("garde_nationale", {"ar": "غلق الطرقات والإخلاء في الأرياف", "fr": "routes et évacuation en zone rurale"}),
    ],
    "gas_leak": [("steg", {"ar": "قطع غاز الشبكة", "fr": "coupure du gaz de réseau"})],
    "building_collapse": [
        ("equipment", {"ar": "تقييم الهيكل والتدعيم", "fr": "évaluation de la structure et étaiement"}),
        ("municipality", {"ar": "إيواء المتضررين", "fr": "relogement des sinistrés"}),
    ],
    "chemical_road_accident": [("anpe", {"ar": "التلوث البيئي", "fr": "pollution de l'environnement"})],
}

SAMU_REASON: Bilingual = {"ar": "أرواح في خطر أو مصابون", "fr": "vies en danger ou blessés"}
