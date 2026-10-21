import type { ApiClient } from "./api";
import { bboxParam, type BBox } from "./filters";
import type {
  Assignment,
  AssignmentStatus,
  AudienceEstimate,
  Callout,
  CalloutBody,
  CloseBody,
  Directive,
  DirectiveBody,
  FeatureCollection,
  LevelBody,
  LevelRow,
  Message,
  MessageBody,
  MessageKind,
  MessageStatus,
  Performance,
  Resource,
  ResourceBody,
  ResourceFilters,
  ResourceMapProperties,
  ResourceSummary,
  SafetyTip,
  SafetyTipBody,
  Skill,
  StaffVolunteer,
  StaffVolunteerDetail,
  Unit,
  UnitBody,
  UserLookup,
  VolunteerDecision,
  VolunteerFilters,
  VolunteerMapProperties,
  VolunteerSuggestion,
} from "./opsTypes";
import type { IncidentDetail, Page, TimelineEntry } from "./types";

const enc = encodeURIComponent;
const incidentPath = (id: string) => `/api/v1/staff/incidents/${enc(id)}`;
const unitPath = (id: string) => `/api/v1/staff/units/${enc(id)}`;
const resourcePath = (id: string) => `/api/v1/staff/resources/${enc(id)}`;
const volunteerPath = (id: string) => `/api/v1/staff/volunteers/${enc(id)}`;
const messagePath = (id: string) => `/api/v1/staff/notifications/${enc(id)}`;
const tipPath = (id: string) => `/api/v1/staff/safety-tips/${enc(id)}`;
const callPath = (id: string) => `/api/v1/staff/callouts/${enc(id)}`;

interface PageOpts {
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
}

/** Typed calls for docs/api/phase-5-contract.md (§1–8). */
export function opsApi(api: ApiClient) {
  return {
    // ---------- Levels and committees (§1, §2) ----------
    levels: (signal?: AbortSignal) => api.request<LevelRow[]>("/api/v1/staff/levels", { signal }),

    setLevels: (body: LevelBody) => api.request<LevelRow[]>("/api/v1/staff/levels", { method: "POST", body }),

    directives: (opts: PageOpts & { pending?: boolean } = {}) =>
      api.request<Page<Directive>>("/api/v1/staff/directives", {
        query: { pending: opts.pending ? true : undefined, limit: opts.limit ?? 30, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    issueDirective: (body: DirectiveBody) =>
      api.request<Directive>("/api/v1/staff/directives", { method: "POST", body }),

    acknowledgeDirective: (id: string, note: string | null) =>
      api.request<Directive>(`/api/v1/staff/directives/${enc(id)}/ack`, {
        method: "POST",
        body: { note: note?.trim() ? note.trim() : null },
      }),

    performance: (since: string, signal?: AbortSignal) =>
      api.request<Performance>("/api/v1/staff/committee/performance", { query: { since }, signal }),

    // ---------- Units and resources (§3) ----------
    units: (signal?: AbortSignal) => api.request<Unit[]>("/api/v1/staff/units", { signal }),
    createUnit: (body: UnitBody) => api.request<Unit>("/api/v1/staff/units", { method: "POST", body }),
    updateUnit: (id: string, body: UnitBody) => api.request<Unit>(unitPath(id), { method: "PUT", body }),
    deleteUnit: (id: string) => api.request<undefined>(unitPath(id), { method: "DELETE" }),

    resources: (filters: ResourceFilters, opts: PageOpts = {}) =>
      api.request<Page<Resource>>("/api/v1/staff/resources", {
        query: {
          status: filters.status || undefined,
          kind: filters.kind || undefined,
          unit_id: filters.unit_id || undefined,
          gouvernorat_code: filters.gouvernorat_code ?? undefined,
          limit: opts.limit ?? 100,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),
    createResource: (body: ResourceBody) =>
      api.request<Resource>("/api/v1/staff/resources", { method: "POST", body }),
    updateResource: (id: string, body: ResourceBody) =>
      api.request<Resource>(resourcePath(id), { method: "PUT", body }),
    deleteResource: (id: string) => api.request<undefined>(resourcePath(id), { method: "DELETE" }),
    resourceSummary: (signal?: AbortSignal) =>
      api.request<ResourceSummary>("/api/v1/staff/resources/summary", { signal }),
    resourcesMap: (bbox: BBox, signal?: AbortSignal) =>
      api.request<FeatureCollection<ResourceMapProperties>>("/api/v1/staff/resources/map", {
        query: { bbox: bboxParam(bbox) },
        signal,
      }),

    // ---------- Interventions (§4, §5) ----------
    updateIncidentCard: (id: string, body: { title: string | null; classification: string | null }) =>
      api.request<IncidentDetail>(incidentPath(id), { method: "PATCH", body }),
    addIncidentNote: (id: string, text: string) =>
      api.request<TimelineEntry>(`${incidentPath(id)}/notes`, { method: "POST", body: { text } }),
    createAssignment: (incidentId: string, resourceId: string, order: string | null) =>
      api.request<Assignment>(`${incidentPath(incidentId)}/assignments`, {
        method: "POST",
        body: { resource_id: resourceId, order: order?.trim() ? order.trim() : null },
      }),
    updateAssignment: (id: string, status: AssignmentStatus, note?: string | null) =>
      api.request<Assignment>(`/api/v1/staff/assignments/${enc(id)}/status`, {
        method: "POST",
        body: note?.trim() ? { status, note: note.trim() } : { status },
      }),
    closeIncident: (id: string, body: CloseBody) =>
      api.request<IncidentDetail>(`${incidentPath(id)}/close`, { method: "POST", body }),
    volunteerSuggestions: (
      incidentId: string,
      opts: { skill?: Skill | ""; radiusKm?: number; limit?: number; signal?: AbortSignal } = {},
    ) =>
      api.request<VolunteerSuggestion[]>(`${incidentPath(incidentId)}/volunteer-suggestions`, {
        query: { skill: opts.skill || undefined, radius_km: opts.radiusKm ?? 30, limit: opts.limit ?? 20 },
        signal: opts.signal,
      }),
    createCallout: (incidentId: string, body: CalloutBody) =>
      api.request<Callout>(`${incidentPath(incidentId)}/callouts`, { method: "POST", body }),
    callout: (id: string, signal?: AbortSignal) => api.request<Callout>(callPath(id), { signal }),
    cancelCallout: (id: string) => api.request<Callout>(`${callPath(id)}/cancel`, { method: "POST" }),
    markArrived: (calloutId: string, volunteerId: string) =>
      api.request<Callout>(`${callPath(calloutId)}/targets/${enc(volunteerId)}/arrived`, { method: "POST" }),

    // ---------- Volunteers (§5) ----------
    volunteers: (filters: VolunteerFilters, opts: PageOpts = {}) =>
      api.request<Page<StaffVolunteer>>("/api/v1/staff/volunteers", {
        query: {
          status: filters.status || undefined,
          skill: filters.skill || undefined,
          gouvernorat_code: filters.gouvernorat_code ?? undefined,
          ready: filters.ready ?? undefined,
          q: filters.q?.trim() || undefined,
          limit: opts.limit ?? 50,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),
    /** Opening a volunteer is written to the audit log (`volunteer.view`): fetch it only when shown. */
    volunteer: (id: string, signal?: AbortSignal) => api.request<StaffVolunteerDetail>(volunteerPath(id), { signal }),
    reviewVolunteer: (id: string, decision: VolunteerDecision, reason?: string) =>
      api.request<StaffVolunteerDetail>(`${volunteerPath(id)}/review`, {
        method: "POST",
        body: reason?.trim() ? { decision, reason: reason.trim() } : { decision },
      }),
    volunteersMap: (bbox: BBox, skill?: Skill | "", signal?: AbortSignal) =>
      api.request<FeatureCollection<VolunteerMapProperties>>("/api/v1/staff/volunteers/map", {
        query: { bbox: bboxParam(bbox), skill: skill || undefined },
        signal,
      }),

    // ---------- Notifications and alerts (§7) ----------
    messages: (filters: { kind?: MessageKind | ""; status?: MessageStatus | "" }, opts: PageOpts = {}) =>
      api.request<Page<Message>>("/api/v1/staff/notifications", {
        query: {
          kind: filters.kind || undefined,
          status: filters.status || undefined,
          limit: opts.limit ?? 30,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),
    message: (id: string, signal?: AbortSignal) => api.request<Message>(messagePath(id), { signal }),
    createMessage: (body: MessageBody) =>
      api.request<Message>("/api/v1/staff/notifications", { method: "POST", body }),
    updateMessage: (id: string, body: MessageBody) => api.request<Message>(messagePath(id), { method: "PUT", body }),
    deleteMessage: (id: string) => api.request<undefined>(messagePath(id), { method: "DELETE" }),
    messageAudience: (id: string, signal?: AbortSignal) =>
      api.request<AudienceEstimate>(`${messagePath(id)}/audience`, { signal }),
    /** Phase 10 §5.1: the author of an alert publishes it alone only with an emergency reason. */
    publishMessage: (id: string, emergencyReason?: string) =>
      api.request<Message>(`${messagePath(id)}/publish`, {
        method: "POST",
        ...(emergencyReason ? { body: { emergency_reason: emergencyReason } } : {}),
      }),
    /** Second look at an alert published alone in an emergency (another publisher). */
    acknowledgeMessage: (id: string) => api.request<Message>(`${messagePath(id)}/acknowledge`, { method: "POST" }),
    cancelMessage: (id: string) => api.request<Message>(`${messagePath(id)}/cancel`, { method: "POST" }),
    activeAlerts: (signal?: AbortSignal) => api.request<Message[]>("/api/v1/staff/alerts/active", { signal }),
    /** Exact e-mail match only; the address goes in the body so it stays out of URLs and logs. */
    lookupUser: (email: string) =>
      api.request<UserLookup>("/api/v1/staff/users/lookup", { method: "POST", body: { email: email.trim() } }),

    // ---------- Safety tips (§8) ----------
    tips: (signal?: AbortSignal) => api.request<SafetyTip[]>("/api/v1/staff/safety-tips", { signal }),
    createTip: (body: SafetyTipBody) => api.request<SafetyTip>("/api/v1/staff/safety-tips", { method: "POST", body }),
    updateTip: (id: string, body: SafetyTipBody) => api.request<SafetyTip>(tipPath(id), { method: "PUT", body }),
    deleteTip: (id: string) => api.request<undefined>(tipPath(id), { method: "DELETE" }),
    publishTip: (id: string) => api.request<SafetyTip>(`${tipPath(id)}/publish`, { method: "POST" }),
    unpublishTip: (id: string) => api.request<SafetyTip>(`${tipPath(id)}/unpublish`, { method: "POST" }),
  };
}

export type OpsApi = ReturnType<typeof opsApi>;

export const opsKeys = {
  levels: ["levels"] as const,
  directivesAll: ["directives"] as const,
  directives: (pending: boolean) => ["directives", pending] as const,
  performance: (since: string) => ["performance", since] as const,
  units: ["units"] as const,
  resourcesAll: ["resources"] as const,
  resources: (filters: ResourceFilters) => ["resources", filters] as const,
  resourceSummary: ["resource-summary"] as const,
  resourcesMapAll: ["resources-map"] as const,
  resourcesMap: (bbox: BBox) => ["resources-map", bbox.map((n) => Number(n.toFixed(3)))] as const,
  volunteerSuggestions: (incidentId: string, skill: string, radiusKm: number) =>
    ["volunteer-suggestions", incidentId, skill, radiusKm] as const,
  volunteersAll: ["volunteers"] as const,
  volunteers: (filters: VolunteerFilters) => ["volunteers", filters] as const,
  volunteerAll: ["volunteer"] as const,
  volunteer: (id: string) => ["volunteer", id] as const,
  volunteersMapAll: ["volunteers-map"] as const,
  volunteersMap: (bbox: BBox, skill: string) => ["volunteers-map", bbox.map((n) => Number(n.toFixed(3))), skill] as const,
  messagesAll: ["messages"] as const,
  messages: (kind: string, status: string) => ["messages", kind, status] as const,
  messageAll: ["message"] as const,
  message: (id: string) => ["message", id] as const,
  audience: (id: string, version: number) => ["message-audience", id, version] as const,
  activeAlerts: ["active-alerts"] as const,
  tips: ["safety-tips"] as const,
};
