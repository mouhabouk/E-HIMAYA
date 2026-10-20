"""Vocabulary and rule tables of decision support: what each kind of incident usually needs, in which words.

These tables are the transparent part of the recommendations (FR-C-11): an operator can read here why a fire engine
or a diver is proposed. They encode common civil-protection practice summarised in docs/procedures; units and
committees tune them through review of this file, not at run time.
"""

from typing import Literal

from app.modules.reports.domain import Category

Lang = Literal["ar", "fr", "en"]
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
    Category.SOS: {"ar": "نداء استغاثة", "fr": "SOS", "en": "SOS"},
    Category.FIRE: {"ar": "حريق", "fr": "incendie", "en": "fire"},
    Category.FLOOD: {"ar": "فيضان", "fr": "inondation", "en": "flood"},
    Category.TRAFFIC_ACCIDENT: {"ar": "حادث مرور", "fr": "accident de la circulation", "en": "road traffic accident"},
    Category.DROWNING: {"ar": "غرق", "fr": "noyade", "en": "drowning"},
    Category.LANDSLIDE: {"ar": "انزلاق أرضي", "fr": "glissement de terrain", "en": "landslide"},
    Category.CHEMICAL_LEAK: {"ar": "تسرب مادة كيميائية", "fr": "fuite de produit chimique", "en": "chemical leak"},
    Category.MEDICAL: {"ar": "حالة طبية", "fr": "urgence médicale", "en": "medical emergency"},
    Category.OTHER: {"ar": "حادثة أخرى", "fr": "autre incident", "en": "other incident"},
}

RESOURCE_LABELS: dict[str, Bilingual] = {
    "fire_engine": {"ar": "شاحنة إطفاء", "fr": "fourgon d'incendie", "en": "fire engine"},
    "water_tanker": {"ar": "شاحنة صهريج ماء", "fr": "camion-citerne d'eau", "en": "water tanker truck"},
    "ambulance": {"ar": "سيارة إسعاف", "fr": "ambulance", "en": "ambulance"},
    "rescue_vehicle": {"ar": "آلية نجدة وإنقاذ", "fr": "véhicule de secours et sauvetage", "en": "rescue vehicle"},
    "heavy_equipment": {"ar": "آلية ثقيلة", "fr": "engin lourd", "en": "heavy machinery"},
    "drone": {"ar": "طائرة مسيرة", "fr": "drone", "en": "drone"},
    "large_extinguisher": {"ar": "مطفأة كبيرة", "fr": "grand extincteur", "en": "large extinguisher"},
    "boat": {"ar": "قارب", "fr": "embarcation", "en": "boat"},
    "command_vehicle": {"ar": "سيارة قيادة", "fr": "véhicule de commandement", "en": "command vehicle"},
    "other": {"ar": "وسيلة أخرى", "fr": "autre moyen", "en": "other resource"},
}

SKILL_LABELS: dict[str, Bilingual] = {
    "first_aid": {"ar": "الإسعافات الأولية", "fr": "premiers secours", "en": "first aid"},
    "diving": {"ar": "الغوص", "fr": "plongée", "en": "diving"},
    "heavy_vehicles": {"ar": "الآليات الثقيلة", "fr": "engins lourds", "en": "heavy machinery"},
    "firefighting": {"ar": "مكافحة الحرائق", "fr": "lutte contre l'incendie", "en": "firefighting"},
    "search_rescue": {"ar": "البحث والإنقاذ", "fr": "recherche et sauvetage", "en": "search and rescue"},
    "logistics": {"ar": "الإمداد", "fr": "logistique", "en": "logistics"},
    "medical": {"ar": "طبي", "fr": "médical", "en": "medical"},
    "other": {"ar": "أخرى", "fr": "autre", "en": "other"},
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
    "samu": {"name": {"ar": "الإسعاف الطبي الاستعجالي", "fr": "SAMU", "en": "SAMU"}, "phone": "190"},
    "police": {"name": {"ar": "الأمن الوطني", "fr": "Police nationale", "en": "National Police"}, "phone": "197"},
    "garde_nationale": {
        "name": {"ar": "الحرس الوطني", "fr": "Garde nationale", "en": "National Guard"},
        "phone": "193",
    },
    "steg": {
        "name": {
            "ar": "الشركة التونسية للكهرباء والغاز",
            "fr": "STEG (électricité et gaz)",
            "en": "STEG (electricity and gas)",
        },
        "phone": None,
    },
    "sonede": {
        "name": {
            "ar": "الشركة الوطنية لاستغلال وتوزيع المياه",
            "fr": "SONEDE (eau potable)",
            "en": "SONEDE (drinking water)",
        },
        "phone": None,
    },
    "forests": {
        "name": {
            "ar": "الإدارة العامة للغابات",
            "fr": "Direction Générale des Forêts",
            "en": "General Directorate of Forests",
        },
        "phone": None,
    },
    "anpe": {
        "name": {
            "ar": "الوكالة الوطنية لحماية المحيط",
            "fr": "ANPE (protection de l'environnement)",
            "en": "ANPE (environmental protection)",
        },
        "phone": None,
    },
    "inm": {
        "name": {
            "ar": "المعهد الوطني للرصد الجوي",
            "fr": "Institut National de la Météorologie",
            "en": "National Institute of Meteorology",
        },
        "phone": None,
    },
    "poison_center": {
        "name": {
            "ar": "المركز الطبي للمساعدة الاستعجالية (مقاومة التسمم)",
            "fr": "CAMU — centre antipoison",
            "en": "CAMU — poison control centre",
        },
        "phone": None,
    },
    "municipality": {"name": {"ar": "البلدية", "fr": "Municipalité", "en": "Municipality"}, "phone": None},
    "equipment": {
        "name": {
            "ar": "الإدارة الجهوية للتجهيز",
            "fr": "Direction régionale de l'Équipement",
            "en": "Regional Directorate of Public Works",
        },
        "phone": None,
    },
}

# Why each service is involved, per category (an empty list: none by rule). Classification-specific additions below.
AGENCY_RULES: dict[str, list[tuple[str, Bilingual]]] = {
    Category.FIRE: [
        (
            "police",
            {"ar": "تأمين الطوق وتنظيم المرور", "fr": "périmètre et circulation", "en": "perimeter and traffic"},
        ),
        (
            "steg",
            {
                "ar": "قطع الغاز والكهرباء عن المباني المتضررة",
                "fr": "coupure du gaz et de l'électricité",
                "en": "gas and electricity shut-off",
            },
        ),
    ],
    Category.FLOOD: [
        (
            "garde_nationale",
            {
                "ar": "غلق المعابر والطرقات المغمورة",
                "fr": "fermeture des gués et routes submergées",
                "en": "closure of fords and flooded roads",
            },
        ),
        (
            "steg",
            {
                "ar": "قطع الكهرباء عن الأحياء المغمورة",
                "fr": "coupure de l'électricité des quartiers inondés",
                "en": "power cut in flooded neighbourhoods",
            },
        ),
        (
            "inm",
            {
                "ar": "تطور الأمطار والتحذيرات",
                "fr": "évolution de la pluie et vigilances",
                "en": "rainfall trend and weather warnings",
            },
        ),
        ("sonede", {"ar": "سلامة ماء الشرب", "fr": "sécurité de l'eau potable", "en": "drinking water safety"}),
        ("municipality", {"ar": "مراكز الإيواء المؤقت", "fr": "hébergement provisoire", "en": "temporary shelter"}),
    ],
    Category.TRAFFIC_ACCIDENT: [
        (
            "garde_nationale",
            {
                "ar": "تأمين الطريق والمعاينات",
                "fr": "sécurité de la route et constatations",
                "en": "road safety and on-scene findings",
            },
        ),
        (
            "police",
            {"ar": "تأمين الطريق داخل المدن", "fr": "sécurité de la route en ville", "en": "road safety in towns"},
        ),
    ],
    Category.DROWNING: [
        (
            "garde_nationale",
            {
                "ar": "الحرس البحري والبحث في الماء",
                "fr": "garde maritime et recherches en mer",
                "en": "coast guard and search at sea",
            },
        ),
    ],
    Category.LANDSLIDE: [
        (
            "garde_nationale",
            {"ar": "غلق الطرقات المهددة", "fr": "fermeture des routes menacées", "en": "closure of threatened roads"},
        ),
        (
            "equipment",
            {
                "ar": "الخبرة الجيوتقنية وحالة الطرقات",
                "fr": "expertise géotechnique et routes",
                "en": "geotechnical survey and roads",
            },
        ),
        (
            "steg",
            {
                "ar": "قطع الغاز والكهرباء",
                "fr": "coupure du gaz et de l'électricité",
                "en": "gas and electricity shut-off",
            },
        ),
        ("sonede", {"ar": "فحص قنوات الماء", "fr": "contrôle des conduites d'eau", "en": "inspection of water mains"}),
    ],
    Category.CHEMICAL_LEAK: [
        ("police", {"ar": "الأطواق والإخلاء", "fr": "périmètres et évacuation", "en": "perimeters and evacuation"}),
        ("anpe", {"ar": "التلوث البيئي", "fr": "pollution de l'environnement", "en": "environmental pollution"}),
        (
            "poison_center",
            {"ar": "التكفل بالمتسممين", "fr": "prise en charge des intoxications", "en": "care of poisoning victims"},
        ),
        (
            "samu",
            {
                "ar": "التكفل الطبي بعد إزالة التلوث",
                "fr": "prise en charge médicale après décontamination",
                "en": "medical care after decontamination",
            },
        ),
    ],
    Category.MEDICAL: [("samu", {"ar": "التكفل الطبي", "fr": "prise en charge médicale", "en": "medical care"})],
    Category.SOS: [
        (
            "police",
            {
                "ar": "تحديد الوضعية وتأمينها",
                "fr": "lever le doute et sécuriser",
                "en": "assess and secure the situation",
            },
        )
    ],
    Category.OTHER: [],
}

CLASSIFICATION_AGENCIES: dict[str, list[tuple[str, Bilingual]]] = {
    "forest_fire": [
        (
            "forests",
            {"ar": "مصالح الغابات وحراسها", "fr": "services et gardes forestiers", "en": "forest services and rangers"},
        ),
        (
            "garde_nationale",
            {
                "ar": "غلق الطرقات والإخلاء في الأرياف",
                "fr": "routes et évacuation en zone rurale",
                "en": "roads and evacuation in rural areas",
            },
        ),
    ],
    "gas_leak": [("steg", {"ar": "قطع غاز الشبكة", "fr": "coupure du gaz de réseau", "en": "mains gas shut-off"})],
    "building_collapse": [
        (
            "equipment",
            {
                "ar": "تقييم الهيكل والتدعيم",
                "fr": "évaluation de la structure et étaiement",
                "en": "structural assessment and shoring",
            },
        ),
        ("municipality", {"ar": "إيواء المتضررين", "fr": "relogement des sinistrés", "en": "rehousing of victims"}),
    ],
    "chemical_road_accident": [
        ("anpe", {"ar": "التلوث البيئي", "fr": "pollution de l'environnement", "en": "environmental pollution"})
    ],
}

SAMU_REASON: Bilingual = {
    "ar": "أرواح في خطر أو مصابون",
    "fr": "vies en danger ou blessés",
    "en": "lives at risk or injured",
}
