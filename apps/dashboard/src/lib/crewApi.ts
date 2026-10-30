import type { ApiClient } from "./api";
import type {
  CrewAlert,
  CrewDevice,
  FieldAgent,
  FieldAgentInput,
  ReportTemplate,
  ShiftRow,
  TemplateField,
} from "./crewTypes";
import type { Assignment } from "./opsTypes";
import type { Category } from "./types";

const S = "/api/v1/staff";

export const crewKeys = {
  shifts: ["crew", "shifts"] as const,
  devices: (revoked: boolean) => ["crew", "devices", revoked] as const,
  devicesAll: ["crew", "devices"] as const,
  templates: (retired: boolean) => ["crew", "templates", retired] as const,
  templatesAll: ["crew", "templates"] as const,
  fieldAgents: (gouvernorat: number | null) => ["crew", "field-agents", gouvernorat] as const,
  fieldAgentsAll: ["crew", "field-agents"] as const,
};

const A = `${S}/field-agents`;

/** The room's view of the staff app (phase P4a): teams on duty and the leaders' phones. */
export function crewApi(api: ApiClient) {
  return {
    shifts: (signal?: AbortSignal) => api.request<ShiftRow[]>(`${S}/shifts`, { signal }),
    crewDevices: (revoked: boolean, signal?: AbortSignal) =>
      api.request<CrewDevice[]>(`${S}/crew-devices`, { query: { revoked }, signal }),
    /** Remote wipe: the phone erases everything at its next call; an open shift on it ends. */
    revokeCrewDevice: (id: string) =>
      api.request<CrewDevice>(`${S}/crew-devices/${encodeURIComponent(id)}/revoke`, { method: "POST", body: {} }),
    /** The operator saw a backup or danger alert: the leader's phone shows "the room saw it at …" (P4b). */
    markAlertSeen: (id: string) =>
      api.request<CrewAlert>(`${S}/crew-alerts/${encodeURIComponent(id)}/seen`, { method: "POST", body: {} }),
    reportTemplates: (retired: boolean, signal?: AbortSignal) =>
      api.request<ReportTemplate[]>(`${S}/report-templates`, { query: { retired }, signal }),
    createTemplate: (category: Category, classification: string | null, fields: TemplateField[]) =>
      api.request<ReportTemplate>(`${S}/report-templates`, { method: "POST", body: { category, classification, fields } }),
    editTemplate: (id: string, fields: TemplateField[]) =>
      api.request<ReportTemplate>(`${S}/report-templates/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { fields },
      }),
    approveTemplate: (id: string) =>
      api.request<ReportTemplate>(`${S}/report-templates/${encodeURIComponent(id)}/approve`, {
        method: "POST",
        body: {},
      }),
    retireTemplate: (id: string) =>
      api.request<ReportTemplate>(`${S}/report-templates/${encodeURIComponent(id)}/retire`, {
        method: "POST",
        body: {},
      }),
    /** Phase F: the agents of the staff app, their one-time codes and their phones. */
    fieldAgents: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<FieldAgent[]>(A, { query: { gouvernorat_code: gouvernorat ?? undefined }, signal }),
    createFieldAgent: (body: FieldAgentInput) => api.request<FieldAgent>(A, { method: "POST", body }),
    updateFieldAgent: (id: string, body: Partial<FieldAgentInput> & { imei?: string | null }) =>
      api.request<FieldAgent>(`${A}/${encodeURIComponent(id)}`, { method: "PATCH", body }),
    renewFieldCode: (id: string) =>
      api.request<FieldAgent>(`${A}/${encodeURIComponent(id)}/code`, { method: "POST", body: {} }),
    disableFieldAgent: (id: string, reason: string | null, remove: boolean) =>
      api.request<FieldAgent>(`${A}/${encodeURIComponent(id)}/${remove ? "delete" : "disable"}`, {
        method: "POST",
        body: { reason },
      }),
    /** Phase F: the point the team must reach, picked on the map and sent to the leader's phone. */
    setAssignmentTarget: (id: string, lat: number, lon: number, note: string | null) =>
      api.request<Assignment>(`${S}/assignments/${encodeURIComponent(id)}/target`, {
        method: "PUT",
        body: { lat, lon, note },
      }),
    discardTemplate: (id: string) =>
      api.request<unknown>(`${S}/report-templates/${encodeURIComponent(id)}`, { method: "DELETE" }),
  };
}
