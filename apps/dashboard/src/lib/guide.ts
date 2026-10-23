/**
 * Emergency hub topics and items (phase B1, docs/phase-b/design.md §2bis): types and calls of
 * `/api/v1/staff/emergency-guide`, and the text ↔ lines helpers of the editor (one line per step).
 */

import type { ApiClient } from "./api";

export const GUIDE_LANGS = ["ar", "fr", "en"] as const;
export type GuideLang = (typeof GUIDE_LANGS)[number];

/** 24×24 topic icons (our own shapes). */
export const GUIDE_ICON_PATHS: Record<string, string> = {
  fire: "M12 2c1 4 6 6 6 12a6 6 0 0 1-12 0c0-3 2-5 3-6 0 2 1 3 2 3 0-4-1-6 1-9z",
  bone: "M7 3a3 3 0 0 0-2.8 4.1A3 3 0 1 0 7.9 11l5.1 5.1a3 3 0 1 0 3.9 3.7A3 3 0 1 0 20.9 16a3 3 0 0 0-3.9-3.9L11.9 7A3 3 0 0 0 7 3z",
  first_aid: "M9 2h6v7h7v6h-7v7H9v-7H2V9h7V2z",
  lungs: "M11 2h2v8l3 2V6c3 0 6 5 6 11 0 3-2 4-4 4s-5-1-5-4v-3l-1-1-1 1v3c0 3-3 4-5 4s-4-1-4-4C2 11 5 6 8 6v6l3-2V2z",
  burn: "M12 2c2 3 5 5 5 9a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3 0-5 1-8zM4 20h16v2H4z",
  drop: "M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z",
  heart: "M12 21 3.5 12.5A5 5 0 0 1 12 5.6a5 5 0 0 1 8.5 6.9L12 21z",
  water: "M2 15c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2v3c-2 0-2 2-4 2s-2-2-4-2-2 2-4 2-2-2-4-2-2 2-4 2v-3z",
  electric: "M13 2 4 14h6l-1 8 9-12h-6l1-8z",
  poison: "M9 2h6v4l4 6v8a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-8l4-6V2zm1 11a2 2 0 1 0 4 0 2 2 0 0 0-4 0z",
  pin: "M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 4.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z",
};

export interface ItemText {
  title: string;
  call: string[];
  steps: string[];
  dont: string[];
}

export type ItemContent = Record<GuideLang, ItemText>;
export type Titles = Record<GuideLang, string>;

export interface GuideItem {
  id: string;
  topic_id: string;
  position: number;
  content: ItemContent;
  call_198: boolean;
  hidden: boolean;
  validated: boolean;
  validated_by: string | null;
  validated_at: string | null;
  version: number;
  updated_at: string;
}

export interface GuideTopic {
  id: string;
  key: string;
  title: Titles;
  icon: string;
  colour: string;
  position: number;
  hidden: boolean;
  version: number;
  updated_at: string;
  items: GuideItem[];
}

export interface Guide {
  revision: number;
  topics: GuideTopic[];
  icons: string[];
  palette: string[];
}

export const LIMITS = { title: 120, line: 300, call: 5, steps: 15, dont: 10 } as const;

export const emptyText = (): ItemText => ({ title: "", call: [], steps: [], dont: [] });

/** Textarea → lines: one per line, trimmed, blank lines dropped. */
export function linesOf(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export type ItemError = "title" | "steps" | "tooMany" | "tooLong";

/** First problem of an item, in the order the editor shows the languages; mirrors the API. */
export function validateItem(content: ItemContent): { lang: GuideLang; error: ItemError } | null {
  for (const lang of GUIDE_LANGS) {
    const t = content[lang];
    if (!t.title.trim() || t.title.length > LIMITS.title) return { lang, error: "title" };
    if (t.steps.length === 0) return { lang, error: "steps" };
    if (t.steps.length > LIMITS.steps || t.call.length > LIMITS.call || t.dont.length > LIMITS.dont) {
      return { lang, error: "tooMany" };
    }
    if ([...t.call, ...t.steps, ...t.dont].some((l) => l.length > LIMITS.line)) return { lang, error: "tooLong" };
  }
  return null;
}

const G = "/api/v1/staff/emergency-guide";
const enc = encodeURIComponent;

export const guideKeys = { staff: ["emergency-guide", "staff"] as const };

export function guideApi(api: ApiClient) {
  return {
    guide: (signal?: AbortSignal) => api.request<Guide>(G, { signal }),
    createTopic: (body: { key: string; title: Titles; icon: string; colour: string; reason: string }) =>
      api.request<Guide>(`${G}/topics`, { method: "POST", body }),
    updateTopic: (
      id: string,
      body: { version: number; reason: string; title?: Titles; icon?: string; colour?: string; hidden?: boolean },
    ) => api.request<Guide>(`${G}/topics/${enc(id)}`, { method: "PATCH", body }),
    moveTopic: (id: string, direction: "up" | "down") =>
      api.request<Guide>(`${G}/topics/${enc(id)}/move`, { method: "POST", body: { direction } }),
    createItem: (topicId: string, body: { content: ItemContent; call_198: boolean; reason: string }) =>
      api.request<Guide>(`${G}/topics/${enc(topicId)}/items`, { method: "POST", body }),
    updateItem: (
      id: string,
      body: { version: number; reason: string; content?: ItemContent; call_198?: boolean; hidden?: boolean },
    ) => api.request<Guide>(`${G}/items/${enc(id)}`, { method: "PATCH", body }),
    validateItem: (id: string, version: number, reason: string) =>
      api.request<Guide>(`${G}/items/${enc(id)}/validate`, { method: "POST", body: { version, reason } }),
    moveItem: (id: string, direction: "up" | "down") =>
      api.request<Guide>(`${G}/items/${enc(id)}/move`, { method: "POST", body: { direction } }),
  };
}
