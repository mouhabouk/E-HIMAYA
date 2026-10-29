"""Import every module's models so they register on ``Base.metadata`` (used by Alembic)."""

from app.modules.ai.models import AiSettingsRow, Analysis, Anomaly, ModelDecision
from app.modules.analytics.models import Notification, Scenario, Schedule
from app.modules.analytics.models import Report as AnalyticsReport
from app.modules.appinfo.models import AppRating
from app.modules.audit.models import AuditLog
from app.modules.basemap.models import Basemap
from app.modules.checklist.models import Checklist, ChecklistTask
from app.modules.coastal.models import Beach, BeachDay, CoastalAlert, CoastalSettings, MarineHour, Presence, RiskModel
from app.modules.contact.models import ContactEvent, ContactRequest
from app.modules.content.models import GuideItem, GuideTopic, Revision, SafetyTip
from app.modules.crisis.models import (
    Axis,
    AxisEvent,
    AxisIncident,
    Counter,
    DeclarationRequest,
    DirectiveEvent,
    Dismissal,
    Evacuation,
    Need,
    Shelter,
    Sitrep,
)
from app.modules.crisis.models import (
    Directive as CrisisDirective,
)
from app.modules.decision.models import ProcedureChunk
from app.modules.doctors.models import Doctor, DoctorReview
from app.modules.drill.models import Booking as DrillBooking
from app.modules.drill.models import Evaluation as DrillEvaluation
from app.modules.drill.models import Exercise as DrillExercise
from app.modules.drill.models import Inject as DrillInject
from app.modules.drill.models import Participant as DrillParticipant
from app.modules.drill.models import Response as DrillResponse
from app.modules.drill.models import StressRun as DrillStressRun
from app.modules.drones.models import DroneAlert, DroneTelemetry, DroneZone
from app.modules.evidence.models import Anchor, Leaf
from app.modules.features.models import FeatureRule
from app.modules.forecast.models import ForecastRun
from app.modules.geo.models import Delegation, Gouvernorat, Layer, LayerFeature, LayerImport, LayerRevision
from app.modules.identity.models import Account, Consent, EmailCode, ErasureRequest, Profile
from app.modules.inventory.models import Agent, AgentSkill, Category, InventoryRevision, Stock, UnitCheck
from app.modules.knowledge.models import IndexState, MemoryEntry, MemoryEntryVersion, SearchDoc
from app.modules.learning.models import LearnedModel, TrainingJob
from app.modules.learning.models import Sample as LearningSample
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
from app.modules.programmes.models import Programme, ProgrammePoint, ProgrammeRevision
from app.modules.register.models import Attachment as RegisterAttachment
from app.modules.register.models import Counter as RegisterCounter
from app.modules.register.models import Dispatch as RegisterDispatch
from app.modules.register.models import DispatchTarget as RegisterDispatchTarget
from app.modules.register.models import Document as RegisterDocument
from app.modules.register.models import Hazard as RegisterHazard
from app.modules.register.models import Link as RegisterLink
from app.modules.register.models import Recommendation as RegisterRecommendation
from app.modules.register.models import Reply as RegisterReply
from app.modules.register.models import Revision as RegisterRevision
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
from app.modules.schedule.models import Item as ScheduleItem
from app.modules.schedule.models import Period as SchedulePeriod
from app.modules.schedule.models import Setting as ScheduleSetting
from app.modules.schedule.models import SuggestionDismissal
from app.modules.schedule.models import Template as ScheduleTemplate
from app.modules.sensors.models import SensorDevice, SensorReading
from app.modules.streams.models import LiveStream, StreamDetection, StreamLocation, StreamSegment
from app.modules.telephony.models import Call, Conference, OperatorEndpoint, SmsInbound
from app.modules.towers.models import CameraTower, TowerEvent
from app.modules.volunteers.models import Volunteer, VolunteerReview
from app.modules.weather.models import AlertSuggestion, GridPoint, Observation, Rule
from app.modules.window.models import SavedSearch as WindowSavedSearch
from app.modules.window.models import Synonym as WindowSynonym
from app.modules.window.models import WindowDelegation, WindowEvent

__all__ = [
    "Account",
    "Agent",
    "AgentSkill",
    "AiSettingsRow",
    "AlertSuggestion",
    "Analysis",
    "AnalyticsReport",
    "Anchor",
    "Anomaly",
    "AppRating",
    "Assignment",
    "AuditLog",
    "Axis",
    "AxisEvent",
    "AxisIncident",
    "BadgeAward",
    "Basemap",
    "Beach",
    "BeachDay",
    "Call",
    "Callout",
    "CalloutTarget",
    "CameraTower",
    "CasualtyCount",
    "CasualtyTransport",
    "Category",
    "Certificate",
    "Checklist",
    "ChecklistTask",
    "CoastalAlert",
    "CoastalSettings",
    "Conference",
    "Consent",
    "ConsumerCursor",
    "ContactEvent",
    "ContactRequest",
    "Counter",
    "CrewAlert",
    "CrewEvent",
    "CrewPosition",
    "CrisisDirective",
    "DeclarationRequest",
    "Delegation",
    "Device",
    "Directive",
    "DirectiveAck",
    "DirectiveEvent",
    "Dismissal",
    "Dispatch",
    "Doctor",
    "DoctorReview",
    "Document",
    "DocumentVersion",
    "DrillBooking",
    "DrillEvaluation",
    "DrillExercise",
    "DrillInject",
    "DrillParticipant",
    "DrillResponse",
    "DrillStressRun",
    "DroneAlert",
    "DroneTelemetry",
    "DroneZone",
    "EmailCode",
    "Equipment",
    "ErasureRequest",
    "Evacuation",
    "FeatureRule",
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
    "InventoryRevision",
    "Invitation",
    "Layer",
    "LayerFeature",
    "LayerImport",
    "LayerRevision",
    "Leaf",
    "LearnedModel",
    "LearningSample",
    "LedgerEntry",
    "LevelState",
    "LiveShare",
    "LiveStream",
    "LocationHistory",
    "LocationPoint",
    "LockedFile",
    "MapFeature",
    "MarineHour",
    "Media",
    "Member",
    "MemoryEntry",
    "MemoryEntryVersion",
    "Message",
    "ModelDecision",
    "Need",
    "Nomination",
    "Notification",
    "Observation",
    "OperatorEndpoint",
    "OrgDigest",
    "Organization",
    "Outbox",
    "PendingAward",
    "Presence",
    "ProcedureChunk",
    "Profile",
    "Programme",
    "ProgrammePoint",
    "ProgrammeRevision",
    "RegisterAttachment",
    "RegisterCounter",
    "RegisterDispatch",
    "RegisterDispatchTarget",
    "RegisterDocument",
    "RegisterHazard",
    "RegisterLink",
    "RegisterRecommendation",
    "RegisterReply",
    "RegisterRevision",
    "Report",
    "ReportTemplate",
    "Resource",
    "Revision",
    "RewardCertificate",
    "RewardRule",
    "RiskModel",
    "Rule",
    "SafetyAlert",
    "SafetyAlertRecipient",
    "SafetyCheck",
    "SafetyInvitation",
    "SafetyLink",
    "SafetyTip",
    "Scenario",
    "Schedule",
    "ScheduleItem",
    "SchedulePeriod",
    "ScheduleSetting",
    "ScheduleTemplate",
    "SearchDoc",
    "SensorDevice",
    "SensorReading",
    "Shelter",
    "Shift",
    "Sitrep",
    "SmsInbound",
    "StaffDevice",
    "StatusHistory",
    "Stock",
    "StreamDetection",
    "StreamLocation",
    "StreamSegment",
    "SuggestionDismissal",
    "TeamMember",
    "TimelineEvent",
    "TowerEvent",
    "TrainingJob",
    "Unit",
    "UnitCheck",
    "Volunteer",
    "VolunteerReview",
    "WindowDelegation",
    "WindowEvent",
    "WindowSavedSearch",
    "WindowSynonym",
]
