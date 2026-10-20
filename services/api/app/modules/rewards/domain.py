"""Rewards vocabulary (FR-A-070, FR-A-071, FR-A-072, FR-C-20): reasons, badges, distinctions, fixed notices.

Safety rule (R1 audit finding T25): rewards must never encourage repeated reporting or putting oneself in danger.
Points come only from verified usefulness (a report closed by the operations room, a rescue designated by staff, a
mission the operations room called a volunteer to); never from the number of reports, photos, videos, streams or
from being on scene. There are no cash rewards in this release: nothing here pays or promises money.
"""

import uuid
from enum import StrEnum
from typing import Literal

from app.core.crypto import get_cipher

Lang = Literal["ar", "fr", "en"]


class Reason(StrEnum):
    REPORT_VERIFIED = "report_verified"
    REPORT_HELPED_RESCUE = "report_helped_rescue"
    ACCURATE_CATEGORY = "accurate_category"
    VOLUNTEER_MISSION = "volunteer_mission"
    MANUAL = "manual"
    REVOCATION = "revocation"


# Reasons a rule configures (the others are staff decisions).
RULE_REASONS = (
    Reason.REPORT_VERIFIED,
    Reason.REPORT_HELPED_RESCUE,
    Reason.ACCURATE_CATEGORY,
    Reason.VOLUNTEER_MISSION,
)
# Automatic awards counted against the daily cap (REWARDS_DAILY_CAP); rescues designated by staff are not.
CAPPED_REASONS = frozenset({Reason.REPORT_VERIFIED, Reason.ACCURATE_CATEGORY, Reason.VOLUNTEER_MISSION})


class Level(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    AMBASSADOR = "ambassador"


LEVEL_ORDER = (Level.BRONZE, Level.SILVER, Level.GOLD, Level.AMBASSADOR)
# Bronze shows at once; the others wait for a staff confirmation (humans award).
AUTO_CONFIRMED = frozenset({Level.BRONZE})
# Badges that can produce a certificate.
CERTIFIED_LEVELS = frozenset({Level.GOLD, Level.AMBASSADOR})


class BadgeStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REVOKED = "revoked"


class NominationKind(StrEnum):
    VIGILANT_CITIZEN = "vigilant_citizen"
    BRAVE_VOLUNTEER = "brave_volunteer"
    LEADING_INSTITUTION = "leading_institution"


SubjectKind = Literal["citizen", "volunteer", "org"]
SUBJECT_OF: dict[NominationKind, SubjectKind] = {
    NominationKind.VIGILANT_CITIZEN: "citizen",
    NominationKind.BRAVE_VOLUNTEER: "volunteer",
    NominationKind.LEADING_INSTITUTION: "org",
}

Distinction = Literal["gold", "ambassador", "vigilant_citizen", "brave_volunteer", "leading_institution"]

DISTINCTION_LABELS: dict[str, dict[Lang, str]] = {
    "gold": {"ar": "الشارة الذهبية — مواطن يقظ", "fr": "Badge d'or — citoyen vigilant", "en": "Gold badge"},
    "ambassador": {
        "ar": "سفير الحماية المدنية",
        "fr": "Ambassadeur de la protection civile",
        "en": "Civil protection ambassador",
    },
    "vigilant_citizen": {"ar": "المواطن اليقظ", "fr": "Citoyen vigilant", "en": "Vigilant citizen"},
    "brave_volunteer": {"ar": "المتطوع الشجاع", "fr": "Bénévole courageux", "en": "Brave volunteer"},
    "leading_institution": {"ar": "المؤسسة الرائدة", "fr": "Institution exemplaire", "en": "Leading institution"},
}

# FR-A-072 mentions annual financial prizes: none exists in this release, and the app says so.
PRIZES_NOTICE: dict[Lang, str] = {
    "ar": "الجوائز السنوية تخضع لقرار السلطة المختصة؛ لا يمنح التطبيق أي مبلغ مالي.",
    "fr": "Les prix annuels relèvent d'une décision de l'autorité compétente ; l'application ne verse aucune somme.",
    "en": "Annual prizes are subject to a decision of the competent authority; the app pays no money.",
}
SAFETY_NOTICE: dict[Lang, str] = {
    "ar": "لا تعرّض نفسك للخطر من أجل التبليغ أبدا؛ اتصل بالرقم 198.",
    "fr": "Ne vous mettez jamais en danger pour signaler ; appelez le 198.",
    "en": "Never put yourself in danger to report; call 198.",
}

_PSEUDONYM_CONTEXT = "rewards.pseudonym"


def pseudonym(user_id: uuid.UUID) -> str:
    """Stable, non-reversible label of a citizen for staff lists and leaderboards (``C-1A2B3C4D``)."""
    return "C-" + get_cipher().blind_index(str(user_id), context=_PSEUDONYM_CONTEXT)[:4].hex().upper()


def initials(*names: str | None) -> str:
    """``"Amine", "Ben Salah"`` → ``"A. B."``: the only part of a name the public verification shows."""
    letters = [part.strip()[0].upper() for name in names if name for part in name.split()[:1] if part.strip()]
    return " ".join(f"{letter}." for letter in letters) or "—"
