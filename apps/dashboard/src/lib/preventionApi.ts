import type { ApiClient } from "./api";
import type { Certificate, CertificateChange, DownloadLink, Page } from "./types";

/** Phase P3b: prevention visits (docs/phase-p3/design-prevention.md). */
export const VISIT_STATUSES = ["requested", "scheduled", "inspected", "decided", "cancelled"] as const;
export type VisitStatus = (typeof VISIT_STATUSES)[number];
export const VISIT_DECISIONS = ["approved", "approved_with_reservations", "refused"] as const;
export type VisitDecision = (typeof VISIT_DECISIONS)[number];
export const INSPECTION_RESULTS = ["conform", "nonconform", "not_checked"] as const;
export type InspectionResult = (typeof INSPECTION_RESULTS)[number];
export const INSPECTION_SECTIONS = [
  "building",
  "classification",
  "hazmat",
  "equipment",
  "evacuation",
  "safety_team",
  "documents",
  "site",
] as const;
export type InspectionSection = (typeof INSPECTION_SECTIONS)[number];
export const RESERVATION_STATES = ["open", "responded", "overdue", "lifted"] as const;
export type ReservationState = (typeof RESERVATION_STATES)[number];
/** Same limits as the API: the validity is a working value [SIM], reservations run 12 months at most. */
export const PREVENTION_DEFAULT_MONTHS = 12;
export const RESERVATION_MAX_MONTHS = 12;

export interface ChecklistItem {
  key: string;
  section: InspectionSection;
  declared: unknown;
}

export interface InspectionItem extends ChecklistItem {
  result: InspectionResult;
  observed: string | null;
  note: string | null;
}

export interface ComparisonReport {
  items: InspectionItem[];
  conform: number;
  nonconform: number;
  not_checked: number;
  missing: string[];
  changes: CertificateChange[];
  suggested: "approved" | "approved_with_reservations";
}

export interface Reservation {
  id: string;
  visit_id: string;
  item_key: string | null;
  text: string;
  due_on: string;
  state: ReservationState;
  response_note: string | null;
  responded_by_name: string | null;
  responded_at: string | null;
  lifted_by_name: string | null;
  lift_note: string | null;
  lifted_at: string | null;
}

export interface Visit {
  id: string;
  org_id: string;
  origin: "request" | "scheduled";
  status: VisitStatus;
  request_note: string | null;
  requested_by_name: string | null;
  requested_at: string | null;
  scheduled_on: string | null;
  inspector_name: string | null;
  inspected_on: string | null;
  attendees: string | null;
  comparison: ComparisonReport | null;
  decision: VisitDecision | null;
  decision_reason: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  certificate: Certificate | null;
  reservations: Reservation[];
  has_report: boolean;
  cancel_reason: string | null;
  cancelled_at: string | null;
  created_at: string;
}

/** A photo taken on site with the inspector's phone (phase P4c); ``url`` is a short-lived link. */
export interface VisitPhoto {
  id: string;
  item_key: string | null;
  content_type: string;
  bytes: number;
  created_by_name: string | null;
  device_at: string | null;
  created_at: string;
  url: string | null;
}

/** Both signatures of an inspection made on a phone (phase P4c). */
export interface VisitSignatures {
  inspector_name: string | null;
  inspector_url: string | null;
  representative_name: string | null;
  representative_role: string | null;
  representative_url: string | null;
}

export interface StaffVisit extends Visit {
  org_name: string;
  org_kind: string;
  org_status: string;
  gouvernorat_code: number | null;
  checklist: ChecklistItem[];
  inspector_on_phone?: boolean;
  photos?: VisitPhoto[];
  signatures?: VisitSignatures | null;
}

export interface ScheduleBody {
  scheduled_on: string;
  inspector_name?: string | null;
}

export interface InspectionBody {
  inspected_on: string;
  attendees?: string | null;
  items: { key: string; result: InspectionResult; observed?: string | null; note?: string | null }[];
}

export interface DecisionBody {
  decision: VisitDecision;
  reason?: string | null;
  valid_until?: string | null;
  reservations: { text: string; due_on: string; item_key?: string | null }[];
}

const enc = encodeURIComponent;
const S = "/api/v1/staff";
const visitPath = (id: string) => `${S}/prevention/visits/${enc(id)}`;

export function preventionApi(api: ApiClient) {
  return {
    /** Visits in scope, newest first; `status` filters on one or more states. */
    preventionVisits: (
      opts: { status?: readonly VisitStatus[]; cursor?: string | null; limit?: number; signal?: AbortSignal } = {},
    ) =>
      api.request<Page<StaffVisit>>(`${S}/prevention/visits`, {
        query: {
          status: opts.status?.length ? opts.status.join(",") : undefined,
          limit: opts.limit ?? 50,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),
    preventionVisit: (id: string, signal?: AbortSignal) => api.request<StaffVisit>(visitPath(id), { signal }),
    orgPreventionVisits: (orgId: string, signal?: AbortSignal) =>
      api.request<Visit[]>(`${S}/orgs/${enc(orgId)}/prevention/visits`, { signal }),
    /** The Office schedules a visit without a request (`org_auditor`). */
    scheduleNewVisit: (orgId: string, body: ScheduleBody) =>
      api.request<StaffVisit>(`${S}/orgs/${enc(orgId)}/prevention/visits`, { method: "POST", body }),
    scheduleVisit: (id: string, body: ScheduleBody) =>
      api.request<StaffVisit>(`${visitPath(id)}/schedule`, { method: "POST", body }),
    recordInspection: (id: string, body: InspectionBody) =>
      api.request<StaffVisit>(`${visitPath(id)}/inspection`, { method: "POST", body }),
    decideVisit: (id: string, body: DecisionBody) =>
      api.request<StaffVisit>(`${visitPath(id)}/decision`, { method: "POST", body }),
    cancelVisit: (id: string, reason: string) =>
      api.request<StaffVisit>(`${visitPath(id)}/cancel`, { method: "POST", body: { reason } }),
    visitReport: (id: string) => api.request<DownloadLink>(`${visitPath(id)}/report`),
    liftReservation: (id: string, note: string | null) =>
      api.request<Reservation>(`${S}/prevention/reservations/${enc(id)}/lift`, { method: "POST", body: { note } }),
  };
}
