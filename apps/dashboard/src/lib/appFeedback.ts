import type { ApiClient } from "./api";

/** Ratings of the mobile app (phase P5b, F-APP-143): GET /api/v1/staff/app-feedback. */
export interface AppFeedbackSummary {
  days: number;
  count: number;
  /** null while nobody rated in the period. */
  average: number | null;
  /** Ratings per star, "1" to "5". */
  by_stars: Record<string, number>;
  by_build: { build: number | null; version: string | null; count: number; average: number }[];
  remarks: {
    stars: number;
    remark: string;
    platform: string | null;
    version: string | null;
    locale: string;
    created_at: string;
  }[];
}

export const APP_FEEDBACK_ROLES = ["sysadmin", "content_editor"] as const;
export const APP_FEEDBACK_PERIODS = [30, 90, 365] as const;

export function canReadAppFeedback(roles: readonly string[]): boolean {
  return APP_FEEDBACK_ROLES.some((r) => roles.includes(r));
}

/** Share of each star in the period, 0 to 100, rounded; 0 everywhere when nobody rated. */
export function starShares(summary: Pick<AppFeedbackSummary, "count" | "by_stars">): Record<number, number> {
  const out: Record<number, number> = {};
  for (let s = 1; s <= 5; s++) {
    out[s] = summary.count ? Math.round(((summary.by_stars[String(s)] ?? 0) * 100) / summary.count) : 0;
  }
  return out;
}

export const appFeedbackKeys = {
  summary: (days: number) => ["app-feedback", days] as const,
};

export function appFeedbackApi(api: ApiClient) {
  return {
    appFeedback: (days: number, signal?: AbortSignal) =>
      api.request<AppFeedbackSummary>(`/api/v1/staff/app-feedback?days=${days}`, { signal }),
  };
}
