"""Rules of the knowledge module: who reads and writes the national memory, the review workflow, and who may see
which item of the events library (docs/api/phase-8-contract.md §2, golden rule "search respects scope")."""

from collections.abc import Iterable
from enum import StrEnum

from app.core.security import Principal, Role
from app.modules.reports.staff_router import READ_ROLES

# Library search and published memory entries: every staff role that reads incidents, plus content editors.
LIBRARY_ROLES = (*READ_ROLES, Role.CONTENT_EDITOR)
# Writing memory entries (after-action reviews) and starting one from an incident.
AUTHOR_ROLES = (
    Role.OPS_MANAGER,
    Role.FIELD_COMMANDER,
    Role.LOCAL_COMMITTEE,
    Role.CENTRAL_COMMITTEE,
    Role.CONTENT_EDITOR,
)
# Publishing (as the second staff member), requesting changes, archiving and restoring.
REVIEW_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
COMMITTEE_ROLES = frozenset({Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE})


class Kind(StrEnum):
    MEMORY = "memory"
    REPORT_DOC = "report_doc"
    INCIDENT = "incident"
    REPORT = "report"
    TRANSCRIPT = "transcript"
    PROCEDURE = "procedure"


# Kinds whose text is encrypted at its source: kept encrypted in knowledge.search_doc (blind-index word search).
SENSITIVE_KINDS = frozenset({Kind.REPORT, Kind.TRANSCRIPT})

KIND_LABELS: dict[str, dict[str, str]] = {
    Kind.MEMORY: {"ar": "الذاكرة الوطنية", "fr": "Mémoire nationale"},
    Kind.REPORT_DOC: {"ar": "تقارير", "fr": "Rapports"},
    Kind.INCIDENT: {"ar": "تدخلات", "fr": "Interventions"},
    Kind.REPORT: {"ar": "بلاغات", "fr": "Signalements"},
    Kind.TRANSCRIPT: {"ar": "تفريغ المكالمات والفيديو", "fr": "Transcriptions"},
    Kind.PROCEDURE: {"ar": "إجراءات", "fr": "Procédures"},
}


class Access(StrEnum):
    """Visibility of a library item (``knowledge.search_doc.access``)."""

    # Every staff member who may use the library (procedures, national memory entries).
    ALL = "all"
    # National staff, and staff of one of the item's gouvernorats (no gouvernorat: national staff only).
    GOUVERNORAT = "gouvernorat"
    # The central committee, and local committees of one of the item's gouvernorats.
    COMMITTEE = "committee"


MEMORY_ACCESS = {"national": Access.ALL, "gouvernorat": Access.GOUVERNORAT, "committee": Access.COMMITTEE}


def can_see(principal: Principal, access: str, gouvernorats: Iterable[int]) -> bool:
    """The scope rule applied to every library hit and item before it is returned."""
    if not principal.is_staff:
        return False
    codes = set(gouvernorats)
    if access == Access.ALL:
        return True
    if access == Access.GOUVERNORAT:
        return principal.is_national or (principal.gouvernorat_code is not None and principal.gouvernorat_code in codes)
    if access == Access.COMMITTEE:
        if Role.CENTRAL_COMMITTEE in principal.roles and principal.is_national:
            return True
        return (
            bool(principal.roles & COMMITTEE_ROLES)
            and principal.gouvernorat_code is not None
            and principal.gouvernorat_code in codes
        )
    return False


def covers(principal: Principal, gouvernorats: Iterable[int]) -> bool:
    """A staff member may write an entry only when every gouvernorat it names is in their scope (national: any)."""
    if principal.is_national:
        return True
    codes = set(gouvernorats)
    return bool(codes) and codes <= {principal.gouvernorat_code}


# ---------------------------------------------------------------- memory workflow


class Status(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# (from, to) → (roles allowed, note required, version change label)
TRANSITIONS: dict[tuple[str, str], tuple[tuple[Role, ...], bool, str]] = {
    (Status.DRAFT, Status.IN_REVIEW): (AUTHOR_ROLES, False, "in_review"),
    (Status.IN_REVIEW, Status.PUBLISHED): (REVIEW_ROLES, False, "published"),
    (Status.IN_REVIEW, Status.DRAFT): (REVIEW_ROLES, True, "changes_requested"),
    (Status.DRAFT, Status.ARCHIVED): (REVIEW_ROLES, True, "archived"),
    (Status.PUBLISHED, Status.ARCHIVED): (REVIEW_ROLES, True, "archived"),
    (Status.ARCHIVED, Status.DRAFT): (REVIEW_ROLES, False, "restored"),
}
