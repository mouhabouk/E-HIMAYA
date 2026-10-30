import { useQuery } from "@tanstack/react-query";
import { useServices } from "../context/services";
import type { ApiClient } from "./api";

/**
 * The strategies menu (phase S, docs/phase-s/design-s.md §2.2): beside the platform's own pages (SNACR, the plans, the
 * programmes, the dry runs, the lessons learned), the items the national system administrator adds, each with its own
 * page in three languages or a link, open to every staff member or to some roles.
 */

export interface StrategyItemIn {
  name: { ar: string; fr: string; en: string };
  summary: { ar?: string; fr?: string; en?: string };
  body: { ar?: string; fr?: string; en?: string };
  link: string | null;
  icon: string;
  tone: string;
  roles: string[];
  position: number;
  active: boolean;
}

export interface StrategyItem extends StrategyItemIn {
  key: string;
  updated_by_name: string | null;
  updated_at: string;
}

export interface StrategyItems {
  items: StrategyItem[];
  can_manage: boolean;
}

const S = "/api/v1/staff/strategies";
const enc = encodeURIComponent;

export const strategyKeys = {
  all: ["strategies"] as const,
  one: (key: string) => ["strategies", key] as const,
};

/** A page of the dashboard or an official site (the API refuses every other link). */
export const LINK_PATTERN = /^(\/[A-Za-z0-9/_-]*|https:\/\/\S{4,500})$/;
export const KEY_PATTERN = /^[a-z][a-z0-9_]{1,39}$/;

export function strategiesApi(api: ApiClient) {
  return {
    strategyItems: (signal?: AbortSignal) => api.request<StrategyItems>(S, { signal }),
    strategyItem: (key: string, signal?: AbortSignal) => api.request<StrategyItem>(`${S}/${enc(key)}`, { signal }),
    saveStrategyItem: (key: string, body: StrategyItemIn) =>
      api.request<StrategyItem>(`${S}/${enc(key)}`, { method: "PUT", body }),
    deleteStrategyItem: (key: string) => api.request<undefined>(`${S}/${enc(key)}`, { method: "DELETE" }),
  };
}

/** Where an item of the menu leads: a page of the dashboard as it is, everything else to the item's own page. */
export function itemPath(item: Pick<StrategyItem, "key" | "link">): string {
  return item.link?.startsWith("/") ? item.link : `/strategies/${enc(item.key)}`;
}

/** The items of the menu for the signed-in user (none until they are read; the menu works without them). */
export function useStrategyItems(enabled: boolean): StrategyItem[] {
  const { api } = useServices();
  const q = useQuery({
    queryKey: strategyKeys.all,
    queryFn: ({ signal }) => api.strategyItems(signal),
    enabled,
    staleTime: 5 * 60_000,
  });
  return (q.data?.items ?? []).filter((i) => i.active);
}
