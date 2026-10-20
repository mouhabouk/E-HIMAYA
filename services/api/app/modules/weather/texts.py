"""Prefilled texts (ar, fr, en) of suggested weather alerts and labels of the derived levels."""

from datetime import UTC, datetime, timedelta

from app.modules.weather.fwi import FireDanger

DANGER_LABELS: dict[str, dict[str, str]] = {
    FireDanger.LOW: {"ar": "منخفض", "fr": "faible", "en": "low"},
    FireDanger.MODERATE: {"ar": "معتدل", "fr": "modéré", "en": "moderate"},
    FireDanger.HIGH: {"ar": "مرتفع", "fr": "élevé", "en": "high"},
    FireDanger.VERY_HIGH: {"ar": "مرتفع جدًا", "fr": "très élevé", "en": "very high"},
    FireDanger.EXTREME: {"ar": "أقصى", "fr": "extrême", "en": "extreme"},
}

HAZARDS = {"fire_danger": "forest_fire", "wind_gust": "wind", "rain_24h": "heavy_rain", "rain_1h": "heavy_rain"}


def _when(at: datetime) -> str:
    """Local time (Africa/Tunis, UTC+1) as dd/mm HH:MM."""
    return (at.astimezone(UTC) + timedelta(hours=1)).strftime("%d/%m %H:%M")


def suggestion_texts(
    metric: str,
    value: float,
    names_ar: list[str],
    names_fr: list[str],
    valid_from: datetime,
    valid_until: datetime,
) -> tuple[dict[str, str], dict[str, str]]:
    """Title and body of a suggested alert. The editor reviews and edits them before anything is sent."""
    where_ar, where_fr = "، ".join(names_ar), ", ".join(names_fr)
    start, end = _when(valid_from), _when(valid_until)
    if metric == "fire_danger":
        level = DANGER_LABELS[_danger(value)]
        title = {
            "ar": f"خطر حرائق {level['ar']}",
            "fr": f"Danger d'incendie {level['fr']}",
            "en": f"{level['en'].capitalize()} fire danger",
        }
        body = {
            "ar": f"يبلغ مؤشر خطر الحرائق مستوى {level['ar']} في {where_ar} من {start} إلى {end}. "
            "تجنّبوا إشعال النار في الغابات والحقول وقربها، وأبلغوا فورًا عن أي دخان على الرقم 198.",
            "fr": f"Le danger d'incendie atteint le niveau {level['fr']} ({where_fr}) du {start} au {end}. "
            "Évitez tout feu en forêt, dans les champs et à proximité ; signalez immédiatement toute fumée au 198.",
            "en": f"Fire danger reaches the {level['en']} level ({where_fr}) from {start} to {end}. "
            "Do not light any fire in or near forests and fields; report any smoke to 198 at once.",
        }
    elif metric == "wind_gust":
        kmh = round(value)
        title = {"ar": "رياح قوية", "fr": "Vents violents", "en": "Strong winds"}
        body = {
            "ar": f"هبوب رياح قوية تصل سرعتها إلى {kmh} كم/س في {where_ar} من {start} إلى {end}. "
            "ثبّتوا الأشياء القابلة للتطاير وابتعدوا عن الأشجار واللافتات، وتوخّوا الحذر على الطرقات.",
            "fr": f"Rafales jusqu'à {kmh} km/h ({where_fr}) du {start} au {end}. Fixez les objets exposés, "
            "éloignez-vous des arbres et panneaux, prudence sur la route.",
            "en": f"Gusts up to {kmh} km/h ({where_fr}) from {start} to {end}. Secure loose objects, keep away "
            "from trees and signs, drive carefully.",
        }
    else:
        mm = round(value)
        per = {"ar": "في الساعة", "fr": "en une heure", "en": "in one hour"}
        if metric == "rain_24h":
            per = {"ar": "خلال 24 ساعة", "fr": "en 24 heures", "en": "in 24 hours"}
        title = {"ar": "أمطار غزيرة", "fr": "Fortes pluies", "en": "Heavy rain"}
        body = {
            "ar": f"أمطار غزيرة قد تبلغ {mm} مم {per['ar']} في {where_ar} من {start} إلى {end}. "
            "لا تعبروا الأودية ومجاري المياه، وابتعدوا عن المناطق المنخفضة.",
            "fr": f"Fortes pluies jusqu'à {mm} mm {per['fr']} ({where_fr}) du {start} au {end}. Ne traversez pas "
            "les oueds ni les routes inondées, éloignez-vous des zones basses.",
            "en": f"Heavy rain up to {mm} mm {per['en']} ({where_fr}) from {start} to {end}. Do not cross wadis or "
            "flooded roads, keep away from low-lying areas.",
        }
    return title, body


def _danger(rank: float) -> FireDanger:
    levels = list(FireDanger)
    return levels[min(max(round(rank), 0), len(levels) - 1)]
