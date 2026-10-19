"""Import every module's models so they register on ``Base.metadata`` (used by Alembic)."""

from app.modules.ai.models import AiSettingsRow, Analysis
from app.modules.audit.models import AuditLog
from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.identity.models import Account, Consent, Profile
from app.modules.ops.models import Incident, TimelineEvent
from app.modules.orgs.models import (
    Certificate,
    Document,
    DocumentVersion,
    Equipment,
    Hazmat,
    Invitation,
    MapFeature,
    Member,
    Organization,
    TeamMember,
)
from app.modules.reports.models import Media, Report, StatusHistory

__all__ = [
    "Account",
    "AiSettingsRow",
    "Analysis",
    "AuditLog",
    "Certificate",
    "Consent",
    "Delegation",
    "Document",
    "DocumentVersion",
    "Equipment",
    "Gouvernorat",
    "Hazmat",
    "Incident",
    "Invitation",
    "MapFeature",
    "Media",
    "Member",
    "Organization",
    "Profile",
    "Report",
    "StatusHistory",
    "TeamMember",
    "TimelineEvent",
]
