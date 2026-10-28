import type { ApiClient } from "./api";
import type {
  Drill,
  DrillIn,
  DrillReport,
  DrillResponse,
  Evaluation,
  EvaluationIn,
  Feed,
  GenerateIn,
  Inject,
  InjectIn,
  ResponseIn,
} from "./drillTypes";

export type * from "./drillTypes";
export { INJECT_KINDS, PLAN_FOLLOWED, RESOURCE_KINDS, RESPONSE_ACTIONS } from "./drillTypes";

/**
 * The digital dry run (L5a, docs/phase-l/design-l5.md §2): dormant until the system administrator grants its page and
 * buttons; a written scenario played to the rooms that approved it, answered with the real resources (booked inside
 * the dry run only), evaluated by an independent evaluator.
 */

const D = "/api/v1/staff/drills";
const enc = encodeURIComponent;

export const drillKeys = {
  all: ["drills"] as const,
  list: ["drills", "list"] as const,
  one: (id: string) => ["drills", id] as const,
  injects: (id: string) => ["drills", id, "injects"] as const,
  feed: (id: string) => ["drills", id, "feed"] as const,
  report: (id: string) => ["drills", id, "report"] as const,
};

/** The statuses in which the run has started (its feed exists). */
export const STARTED = new Set(["running", "stopped", "ended", "closed"]);

export function drillApi(api: ApiClient) {
  return {
    drills: (signal?: AbortSignal) => api.request<Drill[]>(D, { signal }),
    drill: (id: string, signal?: AbortSignal) => api.request<Drill>(`${D}/${enc(id)}`, { signal }),
    createDrill: (body: DrillIn) => api.request<Drill>(D, { method: "POST", body }),
    editDrill: (id: string, body: DrillIn) => api.request<Drill>(`${D}/${enc(id)}`, { method: "PUT", body }),
    injects: (id: string, signal?: AbortSignal) => api.request<Inject[]>(`${D}/${enc(id)}/injects`, { signal }),
    addInject: (id: string, body: InjectIn) => api.request<Inject>(`${D}/${enc(id)}/injects`, { method: "POST", body }),
    deleteInject: (id: string, injectId: string) =>
      api.request<undefined>(`${D}/${enc(id)}/injects/${enc(injectId)}`, { method: "DELETE" }),
    generateInjects: (id: string, body: GenerateIn) =>
      api.request<Inject[]>(`${D}/${enc(id)}/generate`, { method: "POST", body }),
    submitDrill: (id: string) => api.request<Drill>(`${D}/${enc(id)}/submit`, { method: "POST" }),
    decideDrill: (id: string, decision: "approved" | "refused" | "withdrawn", reason?: string) =>
      api.request<Drill>(`${D}/${enc(id)}/approvals`, { method: "POST", body: { decision, reason: reason || null } }),
    startDrill: (id: string) => api.request<Drill>(`${D}/${enc(id)}/start`, { method: "POST" }),
    stopDrill: (id: string, reason: string) =>
      api.request<Drill>(`${D}/${enc(id)}/stop`, { method: "POST", body: { reason } }),
    drillFeed: (id: string, signal?: AbortSignal) => api.request<Feed>(`${D}/${enc(id)}/feed`, { signal }),
    respondInject: (id: string, injectId: string, body: ResponseIn) =>
      api.request<DrillResponse>(`${D}/${enc(id)}/injects/${enc(injectId)}/responses`, { method: "POST", body }),
    releaseResponse: (id: string, responseId: string) =>
      api.request<undefined>(`${D}/${enc(id)}/responses/${enc(responseId)}/release`, { method: "POST" }),
    evaluateInject: (id: string, injectId: string, body: EvaluationIn) =>
      api.request<Evaluation>(`${D}/${enc(id)}/injects/${enc(injectId)}/evaluation`, { method: "PUT", body }),
    closeDrill: (id: string, conclusion: string) =>
      api.request<Drill>(`${D}/${enc(id)}/close`, { method: "POST", body: { conclusion } }),
    drillReport: (id: string, signal?: AbortSignal) => api.request<DrillReport>(`${D}/${enc(id)}/report`, { signal }),
  };
}
