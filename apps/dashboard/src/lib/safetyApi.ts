import type { ApiClient } from "./api";

const enc = encodeURIComponent;

/** The 7b medical file a reporter attached to one report (phase B2); every field is optional. */
export interface MedicalFile {
  sex?: "female" | "male" | null;
  birth_date?: string | null;
  blood_group?: string | null;
  treatment_card?: string | null;
  allergies?: string | null;
  conditions?: string | null;
  medications?: string | null;
  other?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
}

export interface MedicalOut {
  data: MedicalFile;
  attached_at: string;
}

/** The order the fields are shown in, and their translation keys under `safety.medical.fields`. */
export const MEDICAL_FIELDS = [
  "blood_group",
  "allergies",
  "conditions",
  "medications",
  "treatment_card",
  "other",
  "sex",
  "birth_date",
  "contact_name",
  "contact_phone",
] as const satisfies readonly (keyof MedicalFile)[];

export interface HistorySearchBody {
  phone: string;
  report_id: string;
  reason: string;
}

export interface HistoryPoint {
  lat: number;
  lon: number;
  accuracy_m: number | null;
  at: string;
}

export interface HistorySearchOut {
  found: boolean;
  enabled: boolean;
  points: HistoryPoint[];
}

/** Same bounds as the API (`settings/domain.py`). */
export const LIVE_MAX_MINUTES_RANGE = { min: 15, max: 1440 } as const;
export const CHECK_MAX_HOURS_RANGE = { min: 1, max: 72 } as const;

/** Setting that turns the 72-hour location history on (off by default; the search is hidden while off). */
export const LOCATION_HISTORY_SETTING = "safety.location_history";
export const HISTORY_REASON_RANGE = { min: 10, max: 500 } as const;
/** Same rule as the API (`SearchIn.phone`): 8 to 20 characters, read as a Tunisian number. */
export const HISTORY_PHONE = /^[+0-9 ]{8,20}$/;

/** Personal safety, staff side (phase B2): the attached medical file and the missing-person history search. */
export function safetyApi(api: ApiClient) {
  return {
    /** Audited on the server; only for the room handling the report or a break-glass grant. */
    reportMedical: (reportId: string) => api.request<MedicalOut>(`/api/v1/staff/reports/${enc(reportId)}/medical`),

    searchLocationHistory: (body: HistorySearchBody) =>
      api.request<HistorySearchOut>("/api/v1/staff/safety/history/search", { method: "POST", body }),
  };
}
