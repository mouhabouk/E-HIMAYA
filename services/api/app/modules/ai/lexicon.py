"""Language heuristics and keyword signals (Arabic, Tunisian Derja, French, English).

Used for the immediate priority of a new report, before any model has run, and as the fallback when the
language model is unavailable. Transparent by design: the matched words are shown to the operator.
"""

import re
import unicodedata

_ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
# Tunisian written in Latin script uses digits for Arabic letters (3=ع, 7=ح, 9=ق, 5=خ ...).
_ARABIZI_WORD = re.compile(r"\b[a-z]*[a-z][23579][a-z]*\b|\b[23579][a-z]{2,}\b")
_ARABIZI_COMMON = {
    "barcha",
    "famma",
    "fama",
    "mta3",
    "karhba",
    "ya5i",
    "chnowa",
    "mouch",
    "behi",
    "ma3andich",
    "barsha",
}
_FRENCH = {
    "le",
    "la",
    "les",
    "des",
    "une",
    "est",
    "dans",
    "et",
    "il",
    "y",
    "a",
    "pour",
    "sur",
    "pas",
    "au",
    "aux",
    "du",
}
_ENGLISH = {"the", "is", "are", "a", "an", "in", "on", "and", "of", "there", "to", "near", "with", "people", "help"}


_AR_FORMS = str.maketrans("أإآىة", "ااايه")


def normalize_ar(text: str) -> str:
    """Lower-case, strip Arabic diacritics and unify alef, ya and ta marbuta forms."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[ً-ٰٟـ]", "", text)
    return text.translate(_AR_FORMS)


def detect_language(text: str) -> str:
    """``ar``, ``ar_latn`` (Tunisian in Latin script), ``fr``, ``en`` or ``other``."""
    arabic, latin = len(_ARABIC.findall(text)), len(_LATIN.findall(text))
    if arabic == 0 and latin == 0:
        return "other"
    if arabic >= latin:
        return "ar"
    words = re.findall(r"[a-zà-ÿ0-9']+", text.lower())
    arabizi = len(_ARABIZI_WORD.findall(text.lower())) + sum(w in _ARABIZI_COMMON for w in words)
    if arabizi >= 2:
        return "ar_latn"
    french = sum(w in _FRENCH for w in words) + 2 * len(re.findall(r"[éèêàçùôî]", text.lower()))
    english = sum(w in _ENGLISH for w in words)
    if french == english == 0:
        return "other"
    return "fr" if french >= english else "en"


def _terms(*groups: str) -> tuple[str, ...]:
    return tuple(normalize_ar(t) for group in groups for t in group.split("|"))


LIVES = _terms(
    "عالق|عالقين|محاصر|محاصرين|محتجز|يغرق|غريق|غرقى|اطفال|صغار|عجوز|شيخ|تحت الردم",
    "انقذو|انقاذ|نجدة|يستغيث|مازالو داخل|ناس داخل",
    "bloqué|bloqués|coincé|coincés|piégé|piégés|enfants|enfant|se noie|noyade|décombres|au secours|aidez|à l'intérieur",
    "trapped|stuck|children|kids|drowning|rubble|help us|inside|elderly",
    "m7asrin|3al9in|sghar",
)
INJURED = _terms(
    "جريح|جرحى|مجروح|مجروحين|مصاب|مصابين|اصابه|اصابات|ينزف|نزيف|فاقد الوعي|مغمى عليه|طايح",
    "blessé|blessés|blessure|blessures|saigne|inconscient|évanoui",
    "injured|wounded|bleeding|unconscious|hurt",
    "mjarh|mjar7in",
)
DEATHS = _terms("ميت|موتى|مات|ماتو|وفاه|توفي|قتيل|قتلى|جثه", "mort|morts|décédé|décès|cadavre", "dead|died|killed|body")
HAZARDS: dict[str, tuple[str, ...]] = {
    "gas": _terms("غاز|قاز|بوتقاز|gaz|gas|butane"),
    "chemical": _terms("كيميائي|كيميائيه|مواد سامه|سام|chimique|toxique|chemical|toxic"),
    "electricity": _terms("كهرباء|تيار كهربائي|ضو|سلك|électrique|électricité|câble|electric|power line"),
    "explosion": _terms("انفجار|تفجر|تفرقع|explosion|exploser|explosé|blast"),
    "fuel": _terms("بنزين|مازوط|وقود|essence|carburant|gasoil|fuel|petrol"),
    "building_collapse": _terms("انهيار|انهار|طاحت|طاح الحيط|effondrement|effondré|collapse|collapsed"),
    "spreading_fire": _terms("ينتشر|يتوسع|يكبر|se propage|propagation|s'étend|spreading"),
    "rising_water": _terms("الماء يطلع|يرتفع|طلع الماء|monte|montée des eaux|rising water"),
}


def _found(text: str, terms: tuple[str, ...]) -> list[str]:
    padded = f" {text} "
    return [t for t in terms if f" {t}" in padded or (len(t) > 4 and t in padded)]


def signals(text: str) -> dict[str, object]:
    """Keyword signals in a text: lives at risk, injuries, deaths, hazards and the words that matched."""
    norm = normalize_ar(re.sub(r"[^\w'\s]", " ", text))
    lives, injured, deaths = _found(norm, LIVES), _found(norm, INJURED), _found(norm, DEATHS)
    hazards = [name for name, terms in HAZARDS.items() if _found(norm, terms)]
    return {
        "lives_at_risk": bool(lives),
        "injured": bool(injured),
        "deaths": bool(deaths),
        "hazards": hazards,
        "matched": sorted(set(lives + injured + deaths))[:12],
    }
