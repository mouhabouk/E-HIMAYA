import { vi } from "vitest";
import type { OpsApi } from "../lib/opsApi";
import type {
  Assignment,
  Callout,
  Directive,
  LevelRow,
  Message,
  Performance,
  PerformanceRow,
  Resource,
  SafetyTip,
  StaffVolunteer,
  StaffVolunteerDetail,
  Unit,
} from "../lib/opsTypes";

const empty = { items: [], next_cursor: null };
const noFeatures = { type: "FeatureCollection" as const, features: [] };

/** Phase 5 calls of the fake API: empty lists by default, override per test. */
export function fakeOpsApi(): OpsApi {
  return {
    levels: vi.fn(() => Promise.resolve([makeLevel()])),
    setLevels: vi.fn(),
    incidentHospitals: vi.fn(() => Promise.resolve([])),
    chooseHospital: vi.fn(),
    directives: vi.fn(() => Promise.resolve(empty)),
    issueDirective: vi.fn(),
    acknowledgeDirective: vi.fn(),
    performance: vi.fn(() => Promise.resolve(makePerformance())),
    units: vi.fn(() => Promise.resolve([])),
    createUnit: vi.fn(),
    updateUnit: vi.fn(),
    deleteUnit: vi.fn(() => Promise.resolve(undefined)),
    resources: vi.fn(() => Promise.resolve(empty)),
    createResource: vi.fn(),
    updateResource: vi.fn(),
    deleteResource: vi.fn(() => Promise.resolve(undefined)),
    resourceSummary: vi.fn(() => Promise.resolve({ by_kind: {} })),
    resourcesMap: vi.fn(() => Promise.resolve(noFeatures)),
    updateIncidentCard: vi.fn(),
    addIncidentNote: vi.fn(),
    createAssignment: vi.fn(),
    updateAssignment: vi.fn(),
    saveMissionRecord: vi.fn(),
    suggestMissionTimes: vi.fn(() => Promise.resolve([])),
    closeIncident: vi.fn(),
    volunteerSuggestions: vi.fn(() => Promise.resolve([])),
    createCallout: vi.fn(),
    callout: vi.fn(),
    cancelCallout: vi.fn(),
    markArrived: vi.fn(),
    volunteers: vi.fn(() => Promise.resolve(empty)),
    volunteer: vi.fn(),
    reviewVolunteer: vi.fn(),
    volunteersMap: vi.fn(() => Promise.resolve(noFeatures)),
    messages: vi.fn(() => Promise.resolve(empty)),
    message: vi.fn(),
    createMessage: vi.fn(),
    updateMessage: vi.fn(),
    deleteMessage: vi.fn(() => Promise.resolve(undefined)),
    messageAudience: vi.fn(() => Promise.resolve({ push: 0, sms: 0, email: 0 })),
    messageAcks: vi.fn(() => Promise.resolve({ targeted: 0, acked: 0, items: [] })),
    publishMessage: vi.fn(),
    acknowledgeMessage: vi.fn(),
    cancelMessage: vi.fn(),
    activeAlerts: vi.fn(() => Promise.resolve([])),
    lookupUser: vi.fn(),
    tips: vi.fn(() => Promise.resolve([])),
    createTip: vi.fn(),
    updateTip: vi.fn(),
    deleteTip: vi.fn(() => Promise.resolve(undefined)),
    publishTip: vi.fn(),
    unpublishTip: vi.fn(),
  };
}

const NOW = "2026-10-19T08:00:00Z";

export function makeLevel(overrides: Partial<LevelRow> = {}): LevelRow {
  return { gouvernorat_code: 61, level: "normal", since: NOW, reason: null, set_by: null, ...overrides };
}

export function makePerformanceRow(overrides: Partial<PerformanceRow> = {}): PerformanceRow {
  return {
    gouvernorat_code: 61,
    level: "normal",
    reports: 12,
    closed: 8,
    rejected: 1,
    avg_first_response_s: 240,
    avg_resolution_s: 5400,
    open_incidents: 2,
    active_assignments: 3,
    volunteers_approved: 15,
    volunteers_ready: 4,
    alerts_active: 1,
    ...overrides,
  };
}

export function makePerformance(rows: PerformanceRow[] = [makePerformanceRow()]): Performance {
  return { since: "2026-09-19T08:00:00Z", rows, national: { ...makePerformanceRow(), gouvernorat_code: null, level: null } };
}

export function makeDirective(overrides: Partial<Directive> = {}): Directive {
  return {
    id: "d-1",
    title: "رفع الجاهزية",
    body: "رفع جاهزية الوحدات بسبب التقلبات الجوية",
    urgency: "urgent",
    from_level: "central",
    issued_by: "اللجنة المركزية",
    issued_at: NOW,
    gouvernorat_codes: [61],
    acks: [],
    pending_acks: [61],
    ...overrides,
  };
}

export function makeUnit(overrides: Partial<Unit> = {}): Unit {
  return {
    id: "u-1",
    name_ar: "وحدة صفاقس المدينة",
    name_fr: "Unité Sfax Ville",
    kind: "unit",
    gouvernorat_code: 61,
    location: { lat: 34.74, lon: 10.76 },
    phone: "74000000",
    resources: 2,
    version: 1,
    ...overrides,
  };
}

export function makeResource(overrides: Partial<Resource> = {}): Resource {
  return {
    id: "res-1",
    unit_id: "u-1",
    unit_name: "وحدة صفاقس المدينة",
    kind: "fire_engine",
    label: "FPT-12",
    status: "available",
    notes: null,
    location: null,
    gouvernorat_code: 61,
    assignment: null,
    version: 1,
    updated_at: NOW,
    ...overrides,
  };
}

export function makeAssignment(overrides: Partial<Assignment> = {}): Assignment {
  return {
    id: "a-1",
    incident_id: "i-1",
    kind: "resource",
    resource: { id: "res-1", label: "FPT-12", kind: "fire_engine", unit_name: "وحدة صفاقس المدينة" },
    volunteer: null,
    order: "التوجه فورا إلى المستودع",
    status: "ordered",
    created_by: "Sami Operator",
    created_at: NOW,
    en_route_at: null,
    on_scene_at: null,
    released_at: null,
    cancelled_at: null,
    ...overrides,
  };
}

export function makeCallout(overrides: Partial<Callout> = {}): Callout {
  return {
    id: "c-1",
    incident_id: "i-1",
    skill: "first_aid",
    requested: 2,
    radius_km: 30,
    message: "إسعافات أولية في موقع الحريق",
    status: "open",
    created_by: "Sami Operator",
    created_at: NOW,
    accepted: 1,
    targets: [
      {
        volunteer_id: "v-1",
        full_name: "Amel Jaziri",
        phone: "+21622333444",
        distance_m: 1800,
        status: "accepted",
        eta_minutes: 12,
        responded_at: NOW,
        arrived_at: null,
        position: { lat: 34.75, lon: 10.75, at: NOW },
      },
    ],
    ...overrides,
  };
}

export function makeVolunteer(overrides: Partial<StaffVolunteer> = {}): StaffVolunteer {
  return {
    id: "v-1",
    full_name: "Amel Jaziri",
    phone: "+21622333444",
    gouvernorat_code: 61,
    skills: ["first_aid", "search_rescue"],
    availability: "intermittent",
    period_from: "2026-10-01",
    period_to: "2027-10-01",
    status: "pending",
    ready: false,
    ready_until: null,
    submitted_at: NOW,
    ...overrides,
  };
}

export function makeVolunteerDetail(overrides: Partial<StaffVolunteerDetail> = {}): StaffVolunteerDetail {
  return {
    ...makeVolunteer(overrides),
    email: "amel@example.tn",
    other_skill: null,
    notes: "شهادة إسعاف من الهلال الأحمر",
    review_reason: null,
    reviews: [],
    calendar: { role: "volunteer", slots: [], planned_now: null },
    callouts: [],
    ...overrides,
  };
}

export function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "m-1",
    kind: "alert",
    status: "draft",
    title: { ar: "تنبيه أمطار غزيرة", fr: "Alerte pluies abondantes", en: "Heavy rain alert" },
    body: { ar: "تجنبوا الأودية", fr: "Évitez les oueds", en: "Keep away from wadis" },
    channels: ["push"],
    topic: null,
    audience: null,
    user_id: null,
    severity: "high",
    category: "weather",
    hazard: "heavy_rain",
    // Always in the future: a fixed date made the editor tests fail once it passed.
    expires_at: new Date(Date.now() + 24 * 3_600_000).toISOString(),
    area: { gouvernorat_codes: [61], polygon: null },
    created_by: "Rim Editor",
    created_at: NOW,
    published_by: null,
    published_at: null,
    cancelled_at: null,
    version: 1,
    stats: {},
    ...overrides,
  };
}

export function makeTip(overrides: Partial<SafetyTip> = {}): SafetyTip {
  return {
    id: "t-1",
    hazard: "fire",
    position: 10,
    status: "published",
    content: {
      ar: { title: "الحريق", do: ["اتصل بالرقم 198"], dont: ["لا تستعمل المصعد"] },
      fr: { title: "Incendie", do: ["Appelez le 198"], dont: ["N'utilisez pas l'ascenseur"] },
      en: { title: "Fire", do: ["Call 198"], dont: ["Do not use the lift"] },
    },
    version: 1,
    updated_at: NOW,
    published_at: NOW,
    ...overrides,
  };
}
