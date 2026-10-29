import type { ApiClient } from "./api";

/** An indicator out of its habit (AI4, design-l5.md §4.4): figures only, with its sentence in the reader's
 * language ("arrival time in the delegation of X over the last seven days: 24 min, usually 14 ± 3"). */
export interface Anomaly {
  id: string;
  indicator: "reports" | "arrival" | "completion";
  gouvernorat_code: number;
  gouvernorat_name: string | null;
  delegation_id: number | null;
  delegation_name: string | null;
  day: string;
  value: number;
  mean: number;
  std: number;
  z: number;
  baseline: "season" | "recent";
  points: number;
  n: number;
  higher: boolean;
  text: string;
  raised_at: string;
}

export interface Anomalies {
  /** False when the AI settings switched the detection off (AI-01). */
  enabled: boolean;
  items: Anomaly[];
}

export const anomalyKeys = {
  all: (lang: string) => ["anomalies", lang] as const,
};

export function anomalyApi(api: ApiClient) {
  return {
    anomalies: (lang: string, signal?: AbortSignal) =>
      api.request<Anomalies>("/api/v1/staff/anomalies", { signal, query: { lang } }),
  };
}
