import { useQuery } from "@tanstack/react-query";
import type { ApiClient } from "./api";
import { useServices } from "../context/services";
import { useAuth } from "../context/auth";
import type { Feature, FeatureRule, FeatureRuleIn, MyFeatures, PreviewRow } from "./featureTypes";

export type * from "./featureTypes";

/**
 * What the system administrator grants and hides (L4, docs/phase-l/design-l4.md §8). The API enforces it on every
 * request; the dashboard follows it so a hidden page or button is not shown and a granted one is.
 */

const F = "/api/v1/staff/features";
const enc = encodeURIComponent;

export function featuresApi(api: ApiClient) {
  return {
    myFeatures: (signal?: AbortSignal) => api.request<MyFeatures>(`${F}/mine`, { signal }),
    featureCatalogue: (signal?: AbortSignal) => api.request<Feature[]>(`${F}/catalogue`, { signal }),
    featureRules: (includeEnded: boolean, signal?: AbortSignal) =>
      api.request<FeatureRule[]>(`${F}/rules`, { signal, query: { include_ended: includeEnded } }),
    createFeatureRule: (body: FeatureRuleIn) => api.request<FeatureRule>(`${F}/rules`, { method: "POST", body }),
    revokeFeatureRule: (id: string, reason: string) =>
      api.request<FeatureRule>(`${F}/rules/${enc(id)}/revoke`, { method: "POST", body: { reason } }),
    featurePreview: (roles: string[], gouvernorat: number | null, subject: string | null, signal?: AbortSignal) =>
      api.request<PreviewRow[]>(`${F}/preview`, { signal, query: { roles, gouvernorat, subject } }),
  };
}

/** The dashboard path of each page and tab of the catalogue (the API's catalogue names the same paths). */
export const PAGE_PATHS: readonly (readonly [string, string])[] = [
  ["/", "home"],
  ["/reports/late", "reports.late"],
  ["/reports/geo-queue", "reports.geo_queue"],
  ["/reports", "reports"],
  ["/incidents", "incidents"],
  ["/map", "map"],
  ["/streams", "streams"],
  ["/calls", "calls"],
  ["/resource-requests", "resource_requests"],
  ["/resources", "resources"],
  ["/inventory", "inventory"],
  ["/crew", "crew"],
  ["/schedule", "schedule"],
  ["/command", "command"],
  ["/axes", "axes"],
  ["/plans", "plans"],
  ["/register/dispatches", "dispatches"],
  ["/register", "register"],
  ["/committee", "committee"],
  ["/programmes", "programmes"],
  ["/coastal", "coastal"],
  ["/notifications", "notifications"],
  ["/weather/suggestions", "weather"],
  ["/safety-tips", "safety_tips"],
  ["/emergency-guide", "emergency_guide"],
  ["/contact", "contact"],
  ["/volunteers", "volunteers"],
  ["/doctors", "doctors"],
  ["/medical-committee", "medical_committee"],
  ["/rewards", "rewards"],
  ["/orgs/certificates/counter", "counter"],
  ["/orgs/certificates", "certificates"],
  ["/orgs/prevention", "prevention"],
  ["/orgs", "orgs"],
  ["/analytics", "analytics"],
  ["/reports-library", "reports_library"],
  ["/report-templates", "report_templates"],
  ["/memory", "memory"],
  ["/library", "library"],
  ["/layers", "layers"],
  ["/settings/ai", "ai_settings"],
  ["/settings", "settings"],
  ["/accounts", "accounts"],
  ["/audit", "audit"],
  ["/break-glass", "break_glass"],
  ["/permissions", "permissions"],
  ["/window", "window"],
];

/** The page (or tab) a dashboard path belongs to: the longest path that contains it. */
export function featureOfPath(pathname: string): string | null {
  for (const [path, key] of PAGE_PATHS) {
    if (path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(`${path}/`)) return key;
  }
  return null;
}

/** The page of a feature key (`schedule.approve` → `schedule`). */
export const pageOf = (key: string): string => key.split(".")[0] ?? key;

export interface FeatureAccess {
  granted: ReadonlySet<string>;
  hidden: ReadonlySet<string>;
  lent: Readonly<Record<string, string>>;
}

const NONE: FeatureAccess = { granted: new Set(), hidden: new Set(), lent: {} };

/** The caller's grants and hidings; none while loading or on error (the API enforces them anyway). */
export function useMyFeatures(): FeatureAccess {
  const { api } = useServices();
  const { user } = useAuth();
  const q = useQuery({
    queryKey: ["features", "mine", user?.identity.subject ?? ""],
    queryFn: ({ signal }) => api.myFeatures(signal),
    enabled: user !== null,
    staleTime: 60_000,
  });
  if (!q.data) return NONE;
  return { granted: new Set(q.data.granted), hidden: new Set(q.data.hidden), lent: q.data.lent ?? {} };
}

/** Open to the caller: held through their roles or granted, and not hidden. */
export function allowed(access: FeatureAccess, key: string | null, byRole: boolean): boolean {
  if (key === null) return byRole;
  if (access.hidden.has(key) || access.hidden.has(pageOf(key))) return false;
  return byRole || access.granted.has(key);
}

/** The roles granted features lend on one page (its own grant and those of its tabs and buttons). */
export function lentRoles(access: FeatureAccess, page: string): string[] {
  return Object.entries(access.lent)
    .filter(([key]) => pageOf(key) === page)
    .map(([, role]) => role);
}

/** One feature for a button: shown when the roles allow it or it was granted, never when hidden. */
export function useCan(key: string, byRole: boolean): boolean {
  return allowed(useMyFeatures(), key, byRole);
}
