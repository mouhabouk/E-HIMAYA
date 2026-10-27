import type { ApiClient } from "./api";
import type { CrewAlert, CrewDevice, ReportTemplate, ShiftRow, TemplateField } from "./crewTypes";
import type { Category } from "./types";

const S = "/api/v1/staff";

export const crewKeys = {
  shifts: ["crew", "shifts"] as const,
  devices: (revoked: boolean) => ["crew", "devices", revoked] as const,
  devicesAll: ["crew", "devices"] as const,
  templates: (retired: boolean) => ["crew", "templates", retired] as const,
  templatesAll: ["crew", "templates"] as const,
};

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
    discardTemplate: (id: string) =>
      api.request<unknown>(`${S}/report-templates/${encodeURIComponent(id)}`, { method: "DELETE" }),
  };
}
