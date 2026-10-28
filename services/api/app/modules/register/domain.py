"""Register of plans, decisions and instructions, the rules without the database (phase L3b,
docs/phase-l/design-l3b.md).

Who records what (§3), who reads a document at each access level, the status a document has on a given day, the
folded text the search runs on, and what an attached file may be.
"""

from collections.abc import Iterable
from datetime import date

from app.core.security import Principal, Role
from app.modules.knowledge import text as kt

KINDS = (
    "plan",
    "decision",
    "memo",
    "circular",
    "standing_instruction",
    "temporary_instruction",
    "recommendation",
    "minutes",
    "other",
)
LEVELS = ("central", "regional")
STATUSES = ("draft", "in_force", "expired", "repealed")
ACCESS = ("all", "gouvernorat", "command", "restricted")
RELATIONS = ("repeals", "amends", "complements")
RECOMMENDATION_STATUSES = ("proposed", "in_progress", "done", "dropped")
# Topics the search filters on (the free list of a document may hold others).
TOPICS = (
    "floods",
    "forest_fires",
    "beaches",
    "hazardous_materials",
    "establishments",
    "health",
    "transport",
    "earthquakes",
    "storms",
    "civil_protection",
    "public_information",
    "other",
)
# Axis directive category → topics of the document recorded for it.
AXIS_KIND_TOPICS = {
    "flood": "floods",
    "forest_fire": "forest_fires",
    "storm": "storms",
    "earthquake": "earthquakes",
    "technological": "hazardous_materials",
    "health": "health",
}

MAX_FILE_BYTES = 20 * 1024 * 1024
# Content types accepted for the attached file, recognised by their first bytes.
FILE_TYPES = {
    "application/pdf": (b"%PDF-",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}
FILE_SUFFIX = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

_COMMAND = frozenset({Role.GOVERNOR, Role.MINISTER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE, Role.OPS_MANAGER})
_READERS = frozenset(
    {
        Role.OPERATOR,
        Role.OPS_MANAGER,
        Role.FIELD_COMMANDER,
        Role.LOCAL_COMMITTEE,
        Role.CENTRAL_COMMITTEE,
        Role.CONTENT_EDITOR,
        Role.SYSADMIN,
        Role.GOVERNOR,
        Role.MINISTER,
    }
)
_WRITERS = frozenset({Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE, Role.SYSADMIN})


def reads(p: Principal) -> bool:
    return p.is_staff and bool(p.roles & _READERS)


def writes(p: Principal) -> bool:
    return bool(p.roles & _WRITERS)


def can_write(p: Principal, level: str, gouvernorat_code: int | None) -> bool:
    """Central documents: national writers; regional ones: national writers and those of the gouvernorat."""
    if not writes(p):
        return False
    if p.is_national:
        return True
    return level == "regional" and gouvernorat_code is not None and gouvernorat_code == p.gouvernorat_code


def in_scope(p: Principal, gouvernorat_code: int | None) -> bool:
    return p.is_national or gouvernorat_code is None or gouvernorat_code == p.gouvernorat_code


def can_read(
    p: Principal, *, access: str, gouvernorat_code: int | None, status: str, created_by: str, actor: str
) -> bool:
    """The access level of a document on top of the row-level security (which already keeps a regional account to
    the central documents and those of its gouvernorat). Drafts are for those who may write them."""
    if not reads(p) or not in_scope(p, gouvernorat_code):
        return False
    if status == "draft" and not (
        created_by == actor or can_write(p, "regional" if gouvernorat_code else "central", gouvernorat_code)
    ):
        return False
    if access == "all":
        return True
    if access == "gouvernorat":
        return p.is_national or gouvernorat_code is None or gouvernorat_code == p.gouvernorat_code
    if access == "command":
        return bool(p.roles & _COMMAND)
    # restricted: the minister, and whoever recorded it.
    return (Role.MINISTER in p.roles and p.is_national) or created_by == actor


def readable_access(p: Principal) -> list[str]:
    """Access levels a staff member may ever read ("restricted" also covers their own documents, checked apart)."""
    out = ["all", "gouvernorat"]
    if p.roles & _COMMAND:
        out.append("command")
    if Role.MINISTER in p.roles and p.is_national:
        out.append("restricted")
    return out


def status_on(status: str, effective_to: date | None, day: date) -> str:
    """What the status of a document in force is on ``day`` (the worker writes it; drafts and repealed stay)."""
    if status not in ("in_force", "expired"):
        return status
    if effective_to is not None and day > effective_to:
        return "expired"
    return "in_force"


def in_force_on(effective_from: date | None, effective_to: date | None, issued_on: date, day: date) -> bool:
    start = effective_from or issued_on
    return start <= day and (effective_to is None or day <= effective_to)


def norm_text(parts: Iterable[str | None]) -> str:
    return kt.normalise("\n".join(p for p in parts if p))


def file_type(data: bytes, declared: str | None) -> str | None:
    """The content type of an attached file from its first bytes (the declared type only picks among matches)."""
    matches = [t for t, heads in FILE_TYPES.items() if any(data.startswith(h) for h in heads)]
    if not matches:
        return None
    if declared in matches:
        return declared
    return matches[0]


# --- Directives and notices between the centre and the gouvernorats (design §8) -----------------------------------

DISPATCH_KINDS = ("directive", "notice")
AUDIENCES = ("all", "targeted", "centre")
URGENCIES = ("normal", "urgent", "flash")
MAX_ATTACHMENTS = 10
_CENTRE = frozenset({Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE, Role.MINISTER})
_ROOM = frozenset({Role.OPS_MANAGER, Role.OPERATOR, Role.LOCAL_COMMITTEE})


def centre_writes(p: Principal) -> bool:
    """Issues directives, answers notices and writes in the thread of any gouvernorat."""
    return p.is_national and bool(p.roles & _CENTRE)


def room_writes(p: Principal) -> bool:
    """A regional room: raises notices and replies in the thread of its gouvernorat (not the governor)."""
    return not p.is_national and p.gouvernorat_code is not None and bool(p.roles & _ROOM)


def receiving_side(kind: str) -> str:
    """Who is expected to read and answer: the gouvernorats for a directive, the centre for a notice."""
    return "regional" if kind == "directive" else "centre"


_PDF = "application/pdf"
_ZIP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
}
_OLE = {".doc": "application/msword", ".xls": "application/vnd.ms-excel", ".ppt": "application/vnd.ms-powerpoint"}
_TEXT = {".txt": "text/plain", ".csv": "text/csv"}
_IMAGES = {b"\x89PNG\r\n\x1a\n": ("image/png", ".png"), b"\xff\xd8\xff": ("image/jpeg", ".jpg")}


def suffix(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot >= 0 else ""


def attachment_type(data: bytes, name: str) -> tuple[str, str] | None:
    """Content type and stored suffix of a file attached to a directive, notice or reply: PDF, Office (Word, Excel,
    PowerPoint, old and new), OpenDocument, PNG or JPEG recognised by their first bytes and name, or UTF-8 text/CSV.
    Anything else (programs, archives, scripts) is refused."""
    ext = suffix(name)
    if data.startswith(b"%PDF-"):
        return _PDF, ".pdf"
    for head, found in _IMAGES.items():
        if data.startswith(head):
            return found
    if data.startswith(b"PK\x03\x04") and ext in _ZIP:
        return _ZIP[ext], ext
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") and ext in _OLE:
        return _OLE[ext], ext
    if ext in _TEXT and b"\x00" not in data:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return _TEXT[ext], ext
    return None
