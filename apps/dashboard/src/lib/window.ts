import { useQuery } from "@tanstack/react-query";
import { useServices } from "../context/services";
import type { ApiClient } from "./api";
import { canOpenWindowFull } from "./roles";
import type { Download } from "./layersApi";
import type {
  CompareQuery,
  CompareResult,
  Delegate,
  Delegation,
  DelegationIn,
  EventRef,
  ExportIn,
  SavedSearch,
  SearchResult,
  Synonym,
  WindowAccess,
  WindowFilters,
  WindowNow,
} from "./windowTypes";

export type * from "./windowTypes";

/** The decision window (L4, design-l4.md §3) and its delegations (§5). */

const W = "/api/v1/staff/window";
const enc = encodeURIComponent;

function filenameOf(response: Response, fallback: string): string {
  const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "");
  return match?.[1] ?? fallback;
}

/** The criteria as the query string carries them (lists joined by commas by the client). */
export function filterQuery(f: WindowFilters) {
  return {
    q: f.q?.trim() || undefined,
    from: f.from,
    to: f.to,
    gouvernorats: f.gouvernorats,
    delegation: f.delegation ?? undefined,
    category: f.category,
    classification: f.classification,
    severity: f.severity,
    status: f.status,
    source: f.source,
    unit: f.unit ?? undefined,
    org: f.org ?? undefined,
  };
}

export function windowApi(api: ApiClient) {
  return {
    windowAccess: (signal?: AbortSignal) => api.request<WindowAccess>(`${W}/access`, { signal }),
    windowNow: (signal?: AbortSignal) => api.request<WindowNow>(`${W}/now`, { signal }),
    windowSearch: (f: WindowFilters, signal?: AbortSignal) =>
      api.request<SearchResult>(`${W}/search`, { signal, query: filterQuery(f) }),
    windowCompare: (f: WindowFilters, c: CompareQuery, signal?: AbortSignal) =>
      api.request<CompareResult>(`${W}/compare`, {
        signal,
        query: {
          ...filterQuery(f),
          mode: c.mode,
          a_from: c.a_from,
          a_to: c.a_to,
          b_from: c.b_from,
          b_to: c.b_to,
          a_gouvernorat: c.a_gouvernorat ?? undefined,
          b_gouvernorat: c.b_gouvernorat ?? undefined,
        },
      }),
    windowExport: async (body: ExportIn): Promise<Download> => {
      const response = await api.requestRaw(`${W}/export`, { method: "POST", body, accept: "*/*" });
      return { blob: await response.blob(), filename: filenameOf(response, `e-himaya-window.${body.format}`) };
    },
    savedSearches: (signal?: AbortSignal) => api.request<SavedSearch[]>(`${W}/searches`, { signal }),
    saveSearch: (body: Omit<SavedSearch, "id" | "created_at">) =>
      api.request<SavedSearch>(`${W}/searches`, { method: "POST", body }),
    deleteSearch: (id: string) => api.request<undefined>(`${W}/searches/${enc(id)}`, { method: "DELETE" }),
    synonyms: (signal?: AbortSignal) => api.request<Synonym[]>(`${W}/synonyms`, { signal }),
    putSynonym: (meaning: string, words: string[]) =>
      api.request<Synonym>(`${W}/synonyms`, { method: "POST", body: { meaning, words } }),
    deleteSynonym: (id: string) => api.request<undefined>(`${W}/synonyms/${enc(id)}`, { method: "DELETE" }),
    delegates: (q: string, signal?: AbortSignal) => api.request<Delegate[]>(`${W}/delegates`, { signal, query: { q } }),
    delegations: (includeEnded: boolean, signal?: AbortSignal) =>
      api.request<Delegation[]>(`${W}/delegations`, { signal, query: { include_ended: includeEnded } }),
    grantDelegation: (body: DelegationIn) => api.request<Delegation>(`${W}/delegations`, { method: "POST", body }),
    addDelegationEvents: (id: string, events: EventRef[]) =>
      api.request<Delegation>(`${W}/delegations/${enc(id)}/events`, { method: "POST", body: { events } }),
    revokeDelegation: (id: string, reason: string) =>
      api.request<Delegation>(`${W}/delegations/${enc(id)}/revoke`, { method: "POST", body: { reason } }),
  };
}

/** Whether the caller opens the window: in full by their roles, otherwise through a delegation in force. */
export function useWindowOpen(identity: { roles: readonly string[]; national: boolean; subject: string } | null): boolean {
  const { api } = useServices();
  const full = identity ? canOpenWindowFull(identity) : false;
  const q = useQuery({
    queryKey: ["window", "access", identity?.subject ?? ""],
    queryFn: ({ signal }) => api.windowAccess(signal),
    enabled: identity !== null && !full,
    staleTime: 60_000,
  });
  return full || Boolean(q.data?.delegated);
}
