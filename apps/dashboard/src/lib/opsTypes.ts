import type { OrgKind } from "./types";
import type { CrewRef } from "./crewTypes";

/**
 * Types mirroring docs/api/phase-5-contract.md: operational levels and committees (§1–2), units and resources
 * (§3), interventions and call-outs (§4–5), volunteers (§5), notifications and alerts (§7), safety tips (§8).
 */

// ---------- Levels and committees (§1, §2) ----------

export const OP_LEVELS = ["normal", "crisis", "disaster"] as const;
export type OpLevel = (typeof OP_LEVELS)[number];

export interface LevelRow {
  gouvernorat_code: number;
  level: OpLevel;
  since: string;
  reason: string | null;
  set_by: string | null;
}

export interface LevelBody {
  gouvernorat_codes: number[];
  level: OpLevel;
  reason: string;
}

export const URGENCIES = ["normal", "urgent"] as const;
export type Urgency = (typeof URGENCIES)[number];

export interface DirectiveAck {
  gouvernorat_code: number;
  acked_by: string | null;
  acked_at: string;
  note: string | null;
}

export interface Directive {
  id: string;
  title: string;
  body: string;
  urgency: Urgency;
  from_level: "central" | "local";
  issued_by: string | null;
  issued_at: string;
  /** Empty = all 24 gouvernorats. */
  gouvernorat_codes: number[];
  acks: DirectiveAck[];
  pending_acks: number[];
}

export interface DirectiveBody {
  title: string;
  body: string;
  urgency: Urgency;
  gouvernorat_codes: number[];
}

export interface PerformanceRow {
  gouvernorat_code: number | null;
  level: OpLevel | null;
  reports: number;
  closed: number;
  rejected: number;
  avg_first_response_s: number | null;
  avg_resolution_s: number | null;
  open_incidents: number;
  active_assignments: number;
  volunteers_approved: number;
  volunteers_ready: number;
  alerts_active: number;
}

export interface Performance {
  since: string;
  rows: PerformanceRow[];
  national: PerformanceRow;
}

// ---------- Units and resources (§3) ----------

export interface LatLon {
  lat: number;
  lon: number;
}

export const UNIT_KINDS = ["directorate", "unit", "advanced_post"] as const;
export type UnitKind = (typeof UNIT_KINDS)[number];

export interface Unit {
  id: string;
  name_ar: string;
  name_fr: string;
  kind: UnitKind;
  gouvernorat_code: number;
  location: LatLon;
  phone: string | null;
  /** Number of resources attached to the unit. */
  resources: number;
  version: number;
}

export interface UnitBody {
  name_ar: string;
  name_fr: string;
  kind: UnitKind;
  gouvernorat_code: number;
  location: LatLon;
  phone: string | null;
  version?: number;
}

export const RESOURCE_KINDS = [
  "fire_engine",
  "water_tanker",
  "ambulance",
  "rescue_vehicle",
  "heavy_equipment",
  "drone",
  "large_extinguisher",
  "boat",
  "command_vehicle",
  "other",
] as const;
export type ResourceKind = (typeof RESOURCE_KINDS)[number];

export const RESOURCE_STATUSES = ["available", "assigned", "out_of_service"] as const;
export type ResourceStatus = (typeof RESOURCE_STATUSES)[number];

export const ASSIGNMENT_STATUSES = ["ordered", "en_route", "on_scene", "released", "cancelled"] as const;
export type AssignmentStatus = (typeof ASSIGNMENT_STATUSES)[number];
export const ACTIVE_ASSIGNMENT_STATUSES: readonly AssignmentStatus[] = ["ordered", "en_route", "on_scene"];
/** Status flow of an assignment (§4): the server refuses anything else with `409 invalid_transition`. */
export const ASSIGNMENT_TRANSITIONS: Readonly<Record<AssignmentStatus, readonly AssignmentStatus[]>> = {
  ordered: ["en_route", "cancelled"],
  en_route: ["on_scene", "cancelled"],
  on_scene: ["released"],
  released: [],
  cancelled: [],
};

export interface Resource {
  id: string;
  unit_id: string;
  unit_name: string;
  kind: ResourceKind;
  label: string;
  status: ResourceStatus;
  notes: string | null;
  location: LatLon | null;
  gouvernorat_code: number;
  assignment: { id: string; incident_id: string; status: AssignmentStatus } | null;
  version: number;
  updated_at: string;
}

export interface ResourceBody {
  unit_id: string;
  kind: ResourceKind;
  label: string;
  status: "available" | "out_of_service";
  notes: string | null;
  location: LatLon | null;
  version?: number;
}

export interface ResourceFilters {
  status?: ResourceStatus | "";
  kind?: ResourceKind | "";
  unit_id?: string;
  gouvernorat_code?: number | null;
}

export interface ResourceSummary {
  by_kind: Partial<Record<ResourceKind, Partial<Record<ResourceStatus, number>>>>;
}

export interface PointFeature<P> {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: P;
}

export interface FeatureCollection<P> {
  type: "FeatureCollection";
  features: PointFeature<P>[];
}

export type ResourceMapProperties =
  | { layer: "unit"; id: string; name: string; name_fr: string; kind: UnitKind; phone: string | null }
  | {
      layer: "resource";
      id: string;
      label: string;
      kind: ResourceKind;
      status: ResourceStatus;
      unit_name: string;
      incident_id: string | null;
    };

// ---------- Interventions (§4) ----------

/** Classification vocabulary per category; `other` is accepted for every category. */
export const CLASSIFICATIONS: Readonly<Record<string, readonly string[]>> = {
  fire: ["forest_fire", "residential_fire", "industrial_fire", "vehicle_fire"],
  flood: ["river_flood", "urban_flood", "flash_flood"],
  traffic_accident: ["road_accident", "chemical_road_accident", "rail_accident"],
  drowning: ["beach", "dam_or_lake", "well"],
  landslide: ["landslide", "rockfall", "building_collapse"],
  chemical_leak: ["industrial_leak", "transport_leak", "gas_leak"],
  medical: ["cardiac", "trauma", "mass_casualty"],
};

export function classificationsFor(category: string): string[] {
  return [...(CLASSIFICATIONS[category] ?? []), "other"];
}

export interface Assignment {
  id: string;
  incident_id: string;
  kind: "resource" | "volunteer";
  resource: { id: string; label: string; kind: ResourceKind; unit_name: string } | null;
  volunteer: { id: string; full_name: string | null; phone: string | null; skills: Skill[] } | null;
  order: string | null;
  status: AssignmentStatus;
  created_by: string;
  created_at: string;
  en_route_at: string | null;
  on_scene_at: string | null;
  released_at: string | null;
  cancelled_at: string | null;
  /** Phase P4a: the team leader's shift when the vehicle is on the staff app. */
  crew?: CrewRef | null;
}

export const CALLOUT_STATUSES = ["open", "filled", "cancelled", "closed"] as const;
export type CalloutStatus = (typeof CALLOUT_STATUSES)[number];
export const TARGET_STATUSES = ["sent", "accepted", "declined", "expired", "arrived"] as const;
export type TargetStatus = (typeof TARGET_STATUSES)[number];

export interface CalloutTarget {
  volunteer_id: string;
  full_name: string | null;
  phone: string | null;
  distance_m: number | null;
  status: TargetStatus;
  eta_minutes: number | null;
  responded_at: string | null;
  arrived_at: string | null;
  position: { lat: number; lon: number; at: string } | null;
}

export interface Callout {
  id: string;
  incident_id: string;
  skill: Skill;
  requested: number;
  radius_km: number;
  message: string | null;
  status: CalloutStatus;
  created_by: string;
  created_at: string;
  accepted: number;
  targets: CalloutTarget[];
}

export interface CalloutBody {
  skill: Skill;
  requested: number;
  radius_km: number;
  message: string | null;
  volunteer_ids: string[] | null;
}

export interface VolunteerSuggestion {
  volunteer_id: string;
  full_name: string | null;
  phone: string | null;
  skills: Skill[];
  distance_m: number;
  busy: boolean;
}

export const OUTCOMES = ["resolved", "false_alarm", "transferred"] as const;
export type Outcome = (typeof OUTCOMES)[number];
export const CASUALTY_KINDS = ["rescued", "injured", "deceased", "evacuated"] as const;
export type CasualtyKind = (typeof CASUALTY_KINDS)[number];

export interface CloseBody {
  outcome: Outcome;
  summary: string;
  casualties: Record<CasualtyKind, number>;
  lessons: string | null;
}

export interface Evaluation extends CloseBody {
  closed_by: string | null;
  closed_at: string;
}

// ---------- Volunteers (§5) ----------

export const SKILLS = [
  "first_aid",
  "diving",
  "heavy_vehicles",
  "firefighting",
  "search_rescue",
  "logistics",
  "medical",
  "other",
] as const;
export type Skill = (typeof SKILLS)[number];

export const VOLUNTEER_STATUSES = ["pending", "approved", "rejected", "suspended", "withdrawn"] as const;
export type VolunteerStatus = (typeof VOLUNTEER_STATUSES)[number];
export const AVAILABILITIES = ["continuous", "intermittent"] as const;
export type Availability = (typeof AVAILABILITIES)[number];
export const VOLUNTEER_DECISIONS = ["approve", "reject", "suspend", "reinstate"] as const;
export type VolunteerDecision = (typeof VOLUNTEER_DECISIONS)[number];

/** Decisions offered for each status (§5: pending → approved | rejected; approved ↔ suspended). */
export const VOLUNTEER_DECISIONS_BY_STATUS: Readonly<Record<VolunteerStatus, readonly VolunteerDecision[]>> = {
  pending: ["approve", "reject"],
  approved: ["suspend"],
  suspended: ["reinstate"],
  rejected: [],
  withdrawn: [],
};

export interface StaffVolunteer {
  id: string;
  full_name: string | null;
  phone: string | null;
  gouvernorat_code: number;
  skills: Skill[];
  availability: Availability;
  period_from: string;
  period_to: string | null;
  status: VolunteerStatus;
  ready: boolean;
  ready_until: string | null;
  submitted_at: string;
}

export interface StaffVolunteerDetail extends StaffVolunteer {
  email: string | null;
  other_skill: string | null;
  notes: string | null;
  review_reason: string | null;
  reviews: { decision: string; reason: string | null; at: string }[];
  callouts: {
    callout_id: string;
    incident_id: string;
    skill: Skill;
    status: TargetStatus;
    sent_at: string;
    responded_at: string | null;
  }[];
}

export interface VolunteerFilters {
  status?: VolunteerStatus | "";
  skill?: Skill | "";
  gouvernorat_code?: number | null;
  ready?: boolean | null;
  q?: string;
}

export interface VolunteerMapProperties {
  id: string;
  full_name: string | null;
  phone: string | null;
  skills: Skill[];
  ready_until: string | null;
}

// ---------- Notifications and alerts (§7) ----------

export const MESSAGE_KINDS = ["info", "alert"] as const;
export type MessageKind = (typeof MESSAGE_KINDS)[number];
export const MESSAGE_STATUSES = ["draft", "published", "cancelled", "expired"] as const;
export type MessageStatus = (typeof MESSAGE_STATUSES)[number];
export const CHANNELS = ["push", "sms", "email"] as const;
export type Channel = (typeof CHANNELS)[number];
export const TOPICS = ["activity", "awareness", "training", "world_day", "other"] as const;
export type Topic = (typeof TOPICS)[number];
export const AUDIENCES = ["all", "volunteers", "organizations", "user"] as const;
export type Audience = (typeof AUDIENCES)[number];
export const SEVERITIES = ["high", "medium", "low"] as const;
export type Severity = (typeof SEVERITIES)[number];
export const ALERT_CATEGORIES = ["weather", "climate", "hazard"] as const;
export type AlertCategory = (typeof ALERT_CATEGORIES)[number];
export const HAZARDS = [
  "heavy_rain",
  "flood",
  "storm",
  "wind",
  "heat_wave",
  "cold_wave",
  "sea",
  "forest_fire",
  "chemical",
  "other",
] as const;
export type Hazard = (typeof HAZARDS)[number];
export const DISPATCH_STATUSES = ["pending", "running", "done", "skipped", "failed"] as const;

export interface Localized {
  ar: string;
  fr: string;
  en: string;
}

/** GeoJSON Polygon, one ring of [lon, lat] positions, closed. */
export interface Polygon {
  type: "Polygon";
  coordinates: [number, number][][];
}

export interface Area {
  gouvernorat_codes: number[];
  polygon: Polygon | null;
}

export interface Message {
  id: string;
  kind: MessageKind;
  status: MessageStatus;
  title: Localized;
  body: Localized;
  channels: Channel[];
  topic: Topic | null;
  audience: Audience | null;
  user_id: string | null;
  severity: Severity | null;
  category: AlertCategory | null;
  hazard: Hazard | null;
  expires_at: string | null;
  area: Area;
  created_by: string | null;
  created_at: string;
  published_by: string | null;
  published_at: string | null;
  cancelled_at: string | null;
  version: number;
  stats: Partial<Record<Channel, { status: string; sent: number; failed: number }>>;
  /** Four eyes (phase 10 §5.1): last editor, emergency override and the second look afterwards. */
  updated_by?: string | null;
  single_reviewer?: boolean;
  emergency_reason?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  /** Phase P2b: an "organizations" message for some kinds only (empty: every kind), with a read acknowledgement. */
  org_kinds?: OrgKind[];
  ack_required?: boolean;
}

/** `GET /api/v1/staff/notifications/{id}/acks` (phase P2b): institutions reached and their acknowledgements. */
export interface OrgAckRow {
  org_id: string;
  name: string;
  kind: OrgKind;
  gouvernorat_code: number | null;
  acked_at: string | null;
  acked_by: string | null;
}

export interface OrgAcks {
  targeted: number;
  acked: number;
  items: OrgAckRow[];
}

export interface MessageBody {
  kind: MessageKind;
  title: Localized;
  body: Localized;
  channels: Channel[];
  topic?: Topic | null;
  audience?: Audience | null;
  user_id?: string | null;
  severity?: Severity | null;
  category?: AlertCategory | null;
  hazard?: Hazard | null;
  expires_at?: string | null;
  area: { gouvernorat_codes: number[]; polygon?: Polygon | null };
  org_kinds?: OrgKind[];
  ack_required?: boolean;
  version?: number;
}

export interface AudienceEstimate {
  push: number;
  sms: number;
  email: number;
}

/** One citizen account found by its exact e-mail (§7, one-user target): masked, for confirmation only. */
export interface UserLookup {
  user_id: string;
  display_name: string | null;
  email: string;
  channels: Record<Channel, boolean>;
}

// ---------- Safety tips (§8) ----------

export const TIP_HAZARDS = [
  "fire",
  "flood",
  "traffic_accident",
  "medical",
  "drowning",
  "landslide",
  "chemical_leak",
  "heat_wave",
  "storm",
  "earthquake",
  "other",
] as const;
export type TipHazard = (typeof TIP_HAZARDS)[number];
export const TIP_LANGUAGES = ["ar", "fr", "en"] as const;
export type TipLanguage = (typeof TIP_LANGUAGES)[number];

export interface TipText {
  title: string;
  do: string[];
  dont: string[];
}

export interface SafetyTip {
  id: string;
  hazard: TipHazard;
  position: number;
  status: "draft" | "published";
  content: Record<TipLanguage, TipText>;
  /** Phase P2b: awareness for these institution kinds instead of a citizen tip. */
  org_kinds?: OrgKind[];
  version: number;
  updated_at: string;
  published_at: string | null;
}

export interface SafetyTipBody {
  hazard: TipHazard;
  position: number;
  content: Record<TipLanguage, TipText>;
  org_kinds?: OrgKind[];
  version?: number;
}

/** A language is complete when it has a title and at least one item (the publish rule, `translation_missing`). */
export function tipLanguageComplete(text: TipText | undefined): boolean {
  return Boolean(text && text.title.trim() && (text.do.length > 0 || text.dont.length > 0));
}
