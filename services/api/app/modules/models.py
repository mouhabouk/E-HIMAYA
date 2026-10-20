"""Import every module's models so they register on ``Base.metadata`` (used by Alembic)."""

from app.modules.ai.models import AiSettingsRow, Analysis
from app.modules.audit.models import AuditLog
from app.modules.content.models import Revision, SafetyTip
from app.modules.decision.models import ProcedureChunk
from app.modules.forecast.models import ForecastRun
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
from app.modules.telephony.models import Call, Conference, OperatorEndpoint, SmsInbound
from app.modules.volunteers.models import Volunteer, VolunteerReview
from app.modules.weather.models import AlertSuggestion, GridPoint, Observation, Rule

__all__ = [
    "Account",
    "AiSettingsRow",
    "AlertSuggestion",
    "Analysis",
    "Assignment",
    "AuditLog",
    "Call",
    "Callout",
    "CalloutTarget",
    "Certificate",
    "Conference",
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
    "ForecastRun",
    "Gouvernorat",
    "GridPoint",
    "Hazmat",
    "Incident",
    "Invitation",
    "LevelState",
    "LiveStream",
    "MapFeature",
    "Media",
    "Member",
    "Message",
    "Observation",
    "OperatorEndpoint",
    "OrgDigest",
    "Organization",
    "Outbox",
    "ProcedureChunk",
    "Profile",
    "Report",
    "Resource",
    "Revision",
    "Rule",
    "SafetyTip",
    "SmsInbound",
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
