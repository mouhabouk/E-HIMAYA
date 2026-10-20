"""Import every module's models so they register on ``Base.metadata`` (used by Alembic)."""

from app.modules.ai.models import AiSettingsRow, Analysis
from app.modules.audit.models import AuditLog
from app.modules.content.models import Revision, SafetyTip
from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.identity.models import Account, Consent, ErasureRequest, Profile
from app.modules.notify.models import Device, Dispatch, Message, OrgDigest, Outbox
from app.modules.ops.models import (
    Assignment,
    Callout,
    CalloutTarget,
    Directive,
    DirectiveAck,
    Incident,
    LevelState,
    Resource,
    TimelineEvent,
    Unit,
)
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
from app.modules.streams.models import LiveStream, StreamDetection, StreamLocation, StreamSegment
from app.modules.volunteers.models import Volunteer, VolunteerReview

__all__ = [
    "Account",
    "AiSettingsRow",
    "Analysis",
    "Assignment",
    "AuditLog",
    "Callout",
    "CalloutTarget",
    "Certificate",
    "Consent",
    "Delegation",
    "Device",
    "Directive",
    "DirectiveAck",
    "Dispatch",
    "Document",
    "DocumentVersion",
    "Equipment",
    "ErasureRequest",
    "Gouvernorat",
    "Hazmat",
    "Incident",
    "Invitation",
    "LevelState",
    "LiveStream",
    "MapFeature",
    "Media",
    "Member",
    "Message",
    "OrgDigest",
    "Organization",
    "Outbox",
    "Profile",
    "Report",
    "Resource",
    "Revision",
    "SafetyTip",
    "StatusHistory",
    "StreamDetection",
    "StreamLocation",
    "StreamSegment",
    "TeamMember",
    "TimelineEvent",
    "Unit",
    "Volunteer",
    "VolunteerReview",
]
