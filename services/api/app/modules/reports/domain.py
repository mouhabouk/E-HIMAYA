"""Report vocabulary: categories (FR-A-040), statuses and allowed transitions (FR-A-032), labels."""

from enum import StrEnum
from typing import Literal

Lang = Literal["ar", "fr", "en"]


class Category(StrEnum):
    SOS = "sos"
    FIRE = "fire"
    FLOOD = "flood"
    TRAFFIC_ACCIDENT = "traffic_accident"
    DROWNING = "drowning"
    LANDSLIDE = "landslide"
    CHEMICAL_LEAK = "chemical_leak"
    MEDICAL = "medical"
    OTHER = "other"


class Status(StrEnum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    INTERVENED = "intervened"
    ONGOING = "ongoing"
    CLOSED = "closed"
    REJECTED = "rejected"


TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.RECEIVED: frozenset({Status.IN_PROGRESS, Status.REJECTED}),
    Status.IN_PROGRESS: frozenset({Status.INTERVENED, Status.ONGOING, Status.CLOSED, Status.REJECTED}),
    Status.INTERVENED: frozenset({Status.ONGOING, Status.CLOSED}),
    Status.ONGOING: frozenset({Status.INTERVENED, Status.CLOSED}),
    Status.CLOSED: frozenset(),
    Status.REJECTED: frozenset(),
}


def can_transition(current: Status, target: Status) -> bool:
    return target in TRANSITIONS[current]


CATEGORY_LABELS: dict[Category, dict[Lang, str]] = {
    Category.SOS: {"ar": "نجدة عاجلة", "fr": "SOS", "en": "SOS"},
    Category.FIRE: {"ar": "حريق", "fr": "Incendie", "en": "Fire"},
    Category.FLOOD: {"ar": "فيضان", "fr": "Inondation", "en": "Flood"},
    Category.TRAFFIC_ACCIDENT: {"ar": "حادث مرور", "fr": "Accident de la route", "en": "Traffic accident"},
    Category.DROWNING: {"ar": "غرق", "fr": "Noyade", "en": "Drowning"},
    Category.LANDSLIDE: {"ar": "انزلاق تربة", "fr": "Glissement de terrain", "en": "Landslide"},
    Category.CHEMICAL_LEAK: {"ar": "تسرب كيميائي", "fr": "Fuite chimique", "en": "Chemical leak"},
    Category.MEDICAL: {"ar": "حالة صحية", "fr": "Urgence médicale", "en": "Medical emergency"},
    Category.OTHER: {"ar": "غيرها", "fr": "Autre", "en": "Other"},
}

# Bounding box around Tunisia including territorial waters (drownings, boats).
LAT_MIN, LAT_MAX = 30.0, 37.6
LON_MIN, LON_MAX = 7.4, 11.7

# Reports whose point falls just outside the simplified boundaries (coast, sea) take the nearest gouvernorat.
NEAREST_GOUVERNORAT_MAX_M = 25_000

# Media limits (FR-A-041, FR-A-043).
MEDIA_MAX_BYTES: dict[str, int] = {"image": 20 * 1024 * 1024, "video": 300 * 1024 * 1024, "audio": 30 * 1024 * 1024}
MEDIA_TYPES: dict[str, frozenset[str]] = {
    "image": frozenset({"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}),
    "video": frozenset({"video/mp4", "video/quicktime", "video/3gpp", "video/webm"}),
    "audio": frozenset({"audio/mp4", "audio/aac", "audio/mpeg", "audio/ogg", "audio/wav", "audio/x-wav", "audio/webm"}),
}
MEDIA_PER_REPORT = 10
MEDIA_UPLOAD_WINDOW_H = 24
