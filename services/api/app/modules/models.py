"""Import every module's models so they register on ``Base.metadata`` (used by Alembic)."""

from app.modules.ai.models import AiSettingsRow, Analysis
from app.modules.analytics.models import Notification, Scenario, Schedule
from app.modules.analytics.models import Report as AnalyticsReport
from app.modules.appinfo.models import AppRating
from app.modules.audit.models import AuditLog
from app.modules.contact.models import ContactEvent, ContactRequest
from app.modules.content.models import GuideItem, GuideTopic, Revision, SafetyTip
from app.modules.decision.models import ProcedureChunk
from app.modules.doctors.models import Doctor, DoctorReview
from app.modules.evidence.models import Anchor, Leaf
from app.modules.forecast.models import ForecastRun
from app.modules.geo.models import Delegation, Gouvernorat, Layer, LayerFeature, LayerImport
from app.modules.identity.models import Account, Consent, EmailCode, ErasureRequest, Profile
from app.modules.knowledge.models import IndexState, MemoryEntry, MemoryEntryVersion, SearchDoc
from app.modules.medical.models import FileKey, FileOpening, LockedFile
from app.modules.notify.models import Device, Dispatch, Message, OrgDigest, Outbox
from app.modules.ops.models import (
    Assignment,
    Callout,
    CalloutTarget,
    CasualtyCount,
    CasualtyTransport,
    CrewAlert,
    CrewEvent,
    CrewPosition,
    Directive,
    DirectiveAck,
    FieldAttachment,
    FieldReport,
    Incident,
    LevelState,
    ReportTemplate,
    Resource,
    Shift,
    StaffDevice,
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
from app.modules.rewards.models import (
    BadgeAward,
    ConsumerCursor,
    LedgerEntry,
    Nomination,
    PendingAward,
    RewardCertificate,
    RewardRule,
)
from app.modules.safety.models import Alert as SafetyAlert
from app.modules.safety.models import AlertRecipient as SafetyAlertRecipient
from app.modules.safety.models import Invitation as SafetyInvitation
from app.modules.safety.models import Link as SafetyLink
from app.modules.safety.models import LiveShare, LocationHistory, LocationPoint, SafetyCheck
from app.modules.streams.models import LiveStream, StreamDetection, StreamLocation, StreamSegment
from app.modules.telephony.models import Call, Conference, OperatorEndpoint, SmsInbound
from app.modules.volunteers.models import Volunteer, VolunteerReview
from app.modules.weather.models import AlertSuggestion, GridPoint, Observation, Rule

__all__ = [
    "Account",
    "AiSettingsRow",
    "AlertSuggestion",
    "Analysis",
    "AnalyticsReport",
    "Anchor",
    "AppRating",
    "Assignment",
    "AuditLog",
    "BadgeAward",
    "Call",
    "Callout",
    "CalloutTarget",
    "CasualtyCount",
    "CasualtyTransport",
    "Certificate",
    "Conference",
    "Consent",
    "ConsumerCursor",
    "ContactEvent",
    "ContactRequest",
    "CrewAlert",
    "CrewEvent",
    "CrewPosition",
    "Delegation",
    "Device",
    "Directive",
    "DirectiveAck",
    "Dispatch",
    "Doctor",
    "DoctorReview",
    "Document",
    "DocumentVersion",
    "EmailCode",
    "Equipment",
    "ErasureRequest",
    "FieldAttachment",
    "FieldReport",
    "FileKey",
    "FileOpening",
    "ForecastRun",
    "Gouvernorat",
    "GridPoint",
    "GuideItem",
    "GuideTopic",
    "Hazmat",
    "Incident",
    "IndexState",
    "Invitation",
    "Layer",
    "LayerFeature",
    "LayerImport",
    "Leaf",
    "LedgerEntry",
    "LevelState",
    "LiveShare",
    "LiveStream",
    "LocationHistory",
    "LocationPoint",
    "LockedFile",
    "MapFeature",
    "Media",
    "Member",
    "MemoryEntry",
    "MemoryEntryVersion",
    "Message",
    "Nomination",
    "Notification",
    "Observation",
    "OperatorEndpoint",
    "OrgDigest",
    "Organization",
    "Outbox",
    "PendingAward",
    "ProcedureChunk",
    "Profile",
    "Report",
    "ReportTemplate",
    "Resource",
    "Revision",
    "RewardCertificate",
    "RewardRule",
    "Rule",
    "SafetyAlert",
    "SafetyAlertRecipient",
    "SafetyCheck",
    "SafetyInvitation",
    "SafetyLink",
    "SafetyTip",
    "Scenario",
    "Schedule",
    "SearchDoc",
    "Shift",
    "SmsInbound",
    "StaffDevice",
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
