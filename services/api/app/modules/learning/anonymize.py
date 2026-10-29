"""Anonymisation of a report text before it enters the training data (law 2004-63).

What identifies someone is replaced by a tag the model can still learn from: ``<PHONE>``, ``<EMAIL>``, ``<URL>``,
``<PLATE>``, ``<NUMBER>`` (six digits or more: national identity card, account, address number), ``<NAME>`` (the
reporter's own first and last name wherever they appear, and the word after "my name is" / "اسمي" / "je
m'appelle"). Small numbers stay: "زوز عالقين", "3 blessés", "الطابق 2" are what the model must learn.

It is a strong first pass, not a guarantee: a stranger's name written in the text may stay. The samples are therefore
kept encrypted, read by the AI administrator only, and deleted with the report's anonymisation (privacy/retention).
"""

import re
from collections.abc import Iterable

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Tunisian numbers: +216 / 00216 then 8 digits, or 8 digits starting 2-9; spaces, dots and dashes allowed inside.
_PHONE = re.compile(r"(?<!\d)(?:(?:\+|00)\s?216[\s.-]?)?[2-9]\d(?:[\s.-]?\d){6}(?!\d)")
# Tunisian plates: "123 تونس 4567", "123 TU 4567", "123 TN 4567", "RS 12345".
_PLATE = re.compile(r"(?<!\d)\d{1,3}\s*(?:تونس|TU|TN|ت\s*و\s*ن\s*س)\s*\d{1,4}(?!\d)|\bRS\s*\d{3,6}\b", re.IGNORECASE)
_LONG_NUMBER = re.compile(r"(?<!\d)\d(?:[\s.-]?\d){5,}(?!\d)")
_INTRO = re.compile(
    r"(?P<intro>اسمي|انا اسمي|أنا اسمي|ismi|esmi|je m'appelle|je m’appelle|mon nom est|my name is)"
    r"\s+(?P<name>[^\s,.،!?؟]+)",
    re.IGNORECASE,
)


def anonymize(text: str, names: Iterable[str | None] = ()) -> str:
    """``text`` with phones, e-mails, links, plates, long numbers and the given names replaced by tags."""
    out = _URL.sub("<URL>", text)
    out = _EMAIL.sub("<EMAIL>", out)
    out = _PLATE.sub("<PLATE>", out)
    out = _PHONE.sub("<PHONE>", out)
    out = _LONG_NUMBER.sub("<NUMBER>", out)
    out = _INTRO.sub(lambda m: f"{m.group('intro')} <NAME>", out)
    for name in names:
        for part in (name or "").split():
            if len(part) >= 3:
                out = re.sub(rf"(?<!\w){re.escape(part)}(?!\w)", "<NAME>", out, flags=re.IGNORECASE)
    return out
