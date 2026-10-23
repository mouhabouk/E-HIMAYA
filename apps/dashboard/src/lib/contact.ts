/**
 * Contact us inbox (phase B1, docs/phase-b/design.md §2ter): types and calls of `/api/v1/staff/contact`.
 */

import type { ApiClient } from "./api";

export const CONTACT_KINDS = ["access_info", "hazard", "question", "suggestion", "app_problem", "partnership"] as const;
export type ContactKind = (typeof CONTACT_KINDS)[number];
export const CONTACT_STATUSES = ["received", "in_progress", "answered", "closed", "rejected"] as const;
export type ContactStatus = (typeof CONTACT_STATUSES)[number];
export type StatusFilter = "open" | "all" | ContactStatus;
export type ContactAction = "take" | "answer" | "note" | "move" | "close" | "reject" | "reopen";

export interface ContactSummary {
  id: string;
  number: string;
  kind: ContactKind;
  status: ContactStatus;
  subject: string;
  gouvernorat_code: number | null;
  created_at: string;
  updated_at: string;
  due_at: string | null;
  overdue: boolean;
  assigned_name: string | null;
  anonymous: boolean;
  version: number;
}

export interface ContactEvent {
  id: string;
  action: "created" | "status" | "answer" | "note" | "move";
  status: ContactStatus | null;
  gouvernorat_code: number | null;
  at: string;
  note: string | null;
  visible: boolean;
  actor_name: string | null;
}

export interface ContactDetail extends ContactSummary {
  name: string | null;
  phone: string | null;
  email: string | null;
  message: string;
  answer: string | null;
  answered_at: string | null;
  closed_at: string | null;
  locale: string;
  platform: string | null;
  events: ContactEvent[];
}

export interface ContactInbox {
  items: ContactSummary[];
  truncated: boolean;
  open_by_kind: Record<ContactKind, number>;
  overdue: number;
}

export interface InboxFilters {
  kind: ContactKind | "";
  status: StatusFilter;
  /** "" all, "0" requests without a gouvernorat, else a code. */
  gouvernorat: string;
  overdue: boolean;
}

/** Statuses each action is allowed from; mirrors the API's transitions. */
export const ACTIONS_FROM: Record<ContactAction, readonly ContactStatus[]> = {
  take: ["received", "in_progress"],
  answer: ["received", "in_progress", "answered"],
  note: CONTACT_STATUSES,
  move: ["received", "in_progress"],
  close: ["received", "in_progress", "answered"],
  reject: ["received", "in_progress"],
  reopen: ["answered", "closed", "rejected"],
};

/** Actions that need a text (the answer, the note, or the reason given to the citizen). */
export const NEEDS_TEXT: readonly ContactAction[] = ["answer", "note", "reject"];
export const TEXT_MIN = 5;
export const TEXT_MAX = 3000;

export function allowedActions(status: ContactStatus): ContactAction[] {
  return (Object.keys(ACTIONS_FROM) as ContactAction[]).filter((a) => ACTIONS_FROM[a].includes(status));
}

const C = "/api/v1/staff/contact";

export const contactKeys = {
  inbox: (f: InboxFilters) => ["contact", "inbox", f] as const,
  detail: (id: string) => ["contact", "detail", id] as const,
};

export function contactApi(api: ApiClient) {
  return {
    contactInbox: (f: InboxFilters, signal?: AbortSignal) =>
      api.request<ContactInbox>(C, {
        query: {
          status: f.status,
          kind: f.kind || undefined,
          gouvernorat: f.gouvernorat || undefined,
          overdue: f.overdue ? "true" : undefined,
        },
        signal,
      }),
    contactRequest: (id: string, signal?: AbortSignal) =>
      api.request<ContactDetail>(`${C}/${encodeURIComponent(id)}`, { signal }),
    contactAct: (
      id: string,
      body: { version: number; action: ContactAction; text?: string; gouvernorat_code?: number | null },
    ) => api.request<ContactDetail>(`${C}/${encodeURIComponent(id)}/actions`, { method: "POST", body }),
  };
}
