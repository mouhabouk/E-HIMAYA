import type { ApiClient } from "./api";

/** Register of plans, decisions and instructions, central and regional (phase L3b, docs/phase-l/design-l3b.md). */

export const DOCUMENT_KINDS = [
  "plan",
  "decision",
  "memo",
  "circular",
  "standing_instruction",
  "temporary_instruction",
  "recommendation",
  "minutes",
  "other",
] as const;
export type DocumentKind = (typeof DOCUMENT_KINDS)[number];
export const DOCUMENT_LEVELS = ["central", "regional"] as const;
export type DocumentLevel = (typeof DOCUMENT_LEVELS)[number];
export const DOCUMENT_STATUSES = ["in_force", "draft", "expired", "repealed"] as const;
export type DocumentStatus = (typeof DOCUMENT_STATUSES)[number];
export const DOCUMENT_ACCESS = ["all", "gouvernorat", "command", "restricted"] as const;
export type DocumentAccess = (typeof DOCUMENT_ACCESS)[number];
export const RELATIONS = ["repeals", "amends", "complements"] as const;
export type Relation = (typeof RELATIONS)[number];
export const RECOMMENDATION_STATUSES = ["proposed", "in_progress", "done", "dropped"] as const;
export type RecommendationStatus = (typeof RECOMMENDATION_STATUSES)[number];
/** Topics the search filters on (the server's list; a document may hold others). */
export const TOPICS = [
  "floods",
  "forest_fires",
  "beaches",
  "hazardous_materials",
  "establishments",
  "health",
  "transport",
  "earthquakes",
  "storms",
  "civil_protection",
  "public_information",
  "other",
] as const;

/** Status colours (design system tones). */
export const STATUS_TONE: Readonly<Record<DocumentStatus, string>> = {
  in_force: "green",
  draft: "slate",
  expired: "amber",
  repealed: "red",
};

export interface RegisterDocument {
  id: string;
  number: string;
  reference: string;
  kind: DocumentKind;
  /** The hazard of a plan (phase PL1). */
  hazard_key: string | null;
  level: DocumentLevel;
  gouvernorat_code: number | null;
  gouvernorat_name: string | null;
  issuer: string;
  signatory: string;
  title: string;
  summary: string;
  topics: string[];
  issued_on: string;
  effective_from: string | null;
  effective_to: string | null;
  status: DocumentStatus;
  repeal_reason: string | null;
  repealed_by: string | null;
  access: DocumentAccess;
  source: "manual" | "axis";
  signed: boolean;
  file_name: string | null;
  file_type: string | null;
  file_size: number | null;
  file_sha256: string | null;
  recommendations_open: number;
  recommendations: number;
  updated_by_name: string | null;
  updated_at: string;
  version: number;
  excerpt?: string | null;
  can_edit: boolean;
}

export interface Recommendation {
  id: string;
  number: number;
  body: string;
  responsible: string;
  due_on: string | null;
  status: RecommendationStatus;
  status_reason: string | null;
  updated_by_name: string | null;
  updated_at: string;
  overdue: boolean;
}

export interface DocumentLink {
  id: string;
  number: string;
  title: string;
  kind: DocumentKind;
  status: DocumentStatus;
  relation: Relation;
  direction: "out" | "in";
}

export interface DocumentDetail {
  document: RegisterDocument;
  body: string;
  axes: { id: string; number: string; name: string; status: string }[];
  links: DocumentLink[];
  recommendations: Recommendation[];
  created_by_name: string | null;
  created_at: string;
}

export interface RegisterSearch {
  items: RegisterDocument[];
  total: number;
  facets: Record<"kind" | "level" | "status", { key: string; count: number }[]>;
  can_create: boolean;
  can_create_central: boolean;
}

export interface Revision {
  version: number;
  change: string;
  reason: string | null;
  created_by_name: string | null;
  created_at: string;
  snapshot: Record<string, unknown>;
}

export interface RegisterQuery {
  q: string;
  kinds: DocumentKind[];
  levels: DocumentLevel[];
  statuses: DocumentStatus[];
  gouvernorat: number | null;
  topic: string | null;
  issuer: string;
  from: string | null;
  to: string | null;
  dateField: "issued" | "effective";
  inForceOn: string | null;
  hasFile: boolean | null;
  axis: string | null;
  sort: "relevance" | "newest" | "oldest";
  limit: number;
}

export const DEFAULT_QUERY: RegisterQuery = {
  q: "",
  kinds: [],
  levels: [],
  statuses: ["in_force"],
  gouvernorat: null,
  topic: null,
  issuer: "",
  from: null,
  to: null,
  dateField: "issued",
  inForceOn: null,
  hasFile: null,
  axis: null,
  sort: "relevance",
  limit: 30,
};

export interface DocumentBody {
  reference: string;
  kind: DocumentKind;
  hazard_key: string | null;
  level: DocumentLevel;
  gouvernorat_code: number | null;
  issuer: string;
  signatory: string;
  title: string;
  summary: string;
  body: string;
  topics: string[];
  issued_on: string;
  effective_from: string | null;
  effective_to: string | null;
  access: DocumentAccess;
  axis_ids: string[];
  publish: boolean;
}

export const registerKeys = {
  all: ["register"] as const,
  search: (q: RegisterQuery) => ["register", "search", q] as const,
  document: (id: string) => ["register", "document", id] as const,
  revisions: (id: string) => ["register", "revisions", id] as const,
  plans: (gouvernorat: number | null) => ["register", "plans", gouvernorat] as const,
  latest: ["register", "latest"] as const,
};

/** The search parameters the API reads (repeated keys for lists). */
export function searchParams(q: RegisterQuery): Record<string, string | number | boolean | readonly string[] | null> {
  return {
    q: q.q.trim() || null,
    kind: q.kinds,
    level: q.levels,
    status: q.statuses,
    gouvernorat: q.gouvernorat,
    topic: q.topic ? [q.topic] : [],
    issuer: q.issuer.trim() || null,
    from: q.from,
    to: q.to,
    date_field: q.from || q.to ? q.dateField : null,
    in_force_on: q.inForceOn,
    has_file: q.hasFile,
    axis: q.axis,
    sort: q.sort,
    limit: q.limit,
  };
}

/** Bytes as "1.2 MB" / "640 KB". */
export function fileSize(n: number | null): string {
  if (n === null) return "";
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}

// --- Directives and notices between the centre and the gouvernorats (design §8) ---

export const URGENCIES = ["normal", "urgent", "flash"] as const;
export type Urgency = (typeof URGENCIES)[number];
export const URGENCY_TONE: Readonly<Record<Urgency, string>> = { normal: "slate", urgent: "amber", flash: "red" };
/** What an attachment may be (the API checks the first bytes too). */
export const ATTACHMENT_ACCEPT =
  ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.odp,.png,.jpg,.jpeg,.txt,.csv";
export const MAX_ATTACHMENTS = 10;

export interface Attachment {
  id: string;
  file_name: string;
  content_type: string;
  size: number;
  sha256: string;
  created_at: string;
}

export interface Dispatch {
  id: string;
  number: string;
  kind: "directive" | "notice";
  audience: "all" | "targeted" | "centre";
  origin_gouvernorat: number | null;
  origin_name: string | null;
  urgency: Urgency;
  subject: string;
  body: string;
  topics: string[];
  incident_id: string | null;
  axis_id: string | null;
  reply_required: boolean;
  reply_due_at: string | null;
  status: "open" | "closed";
  closed_at: string | null;
  created_by_name: string | null;
  created_at: string;
  targets: number;
  seen: number;
  replied: number;
  unread: boolean;
  overdue: boolean;
  attachments: number;
  excerpt?: string | null;
}

export interface DispatchTarget {
  gouvernorat_code: number;
  gouvernorat_name: string | null;
  seen_at: string | null;
  seen_by_name: string | null;
  replied_at: string | null;
  replies: number;
  overdue: boolean;
}

export interface Reply {
  id: string;
  gouvernorat_code: number;
  side: "centre" | "regional";
  body: string;
  created_by_name: string | null;
  created_at: string;
  attachments: Attachment[];
  mine: boolean;
}

export interface DispatchDetail {
  dispatch: Dispatch;
  attachments: Attachment[];
  targets: DispatchTarget[];
  threads: { gouvernorat_code: number; gouvernorat_name: string | null; replies: Reply[] }[];
  can_reply: boolean;
  can_close: boolean;
  can_attach: boolean;
  viewer_side: "centre" | "regional";
  reply_id?: string | null;
}

export interface DispatchPage {
  items: Dispatch[];
  total: number;
  unread: number;
  can_direct: boolean;
  can_notify: boolean;
}

export interface DispatchQuery {
  box: "inbox" | "sent" | "all";
  q: string;
  urgency: Urgency | null;
  state: "open" | "closed" | null;
  gouvernorat: number | null;
  from: string | null;
  to: string | null;
  unread: boolean;
}

export const DEFAULT_DISPATCH_QUERY: DispatchQuery = {
  box: "inbox",
  q: "",
  urgency: null,
  state: null,
  gouvernorat: null,
  from: null,
  to: null,
  unread: false,
};

export interface DispatchBody {
  kind: "directive" | "notice";
  audience: "all" | "targeted";
  gouvernorats: number[];
  urgency: Urgency;
  subject: string;
  body: string;
  topics: string[];
  incident_id?: string | null;
  axis_id?: string | null;
  reply_required: boolean;
  reply_due_at: string | null;
}

export const dispatchKeys = {
  all: ["register", "dispatches"] as const,
  list: (q: DispatchQuery) => ["register", "dispatches", "list", q] as const,
  one: (id: string) => ["register", "dispatches", "one", id] as const,
};

const R = "/api/v1/staff/register";
const enc = encodeURIComponent;

export function registerApi(api: ApiClient) {
  const doc = (id: string) => `${R}/documents/${enc(id)}`;
  return {
    registerSearch: (q: RegisterQuery, signal?: AbortSignal) =>
      api.request<RegisterSearch>(`${R}/documents`, { query: searchParams(q), signal }),
    registerDocument: (id: string, signal?: AbortSignal) => api.request<DocumentDetail>(doc(id), { signal }),
    createDocument: (body: DocumentBody) => api.request<DocumentDetail>(`${R}/documents`, { method: "POST", body }),
    updateDocument: (id: string, body: DocumentBody & { version: number; reason: string }) =>
      api.request<DocumentDetail>(doc(id), { method: "PATCH", body }),
    deleteDraft: (id: string) => api.request<undefined>(doc(id), { method: "DELETE" }),
    repealDocument: (id: string, reason: string, byDocumentId: string | null) =>
      api.request<DocumentDetail>(`${doc(id)}/repeal`, { method: "POST", body: { reason, by_document_id: byDocumentId } }),
    linkDocument: (id: string, toId: string, relation: Relation) =>
      api.request<DocumentDetail>(`${doc(id)}/links`, { method: "POST", body: { to_id: toId, relation } }),
    unlinkDocument: (id: string, otherId: string) =>
      api.request<undefined>(`${doc(id)}/links/${enc(otherId)}`, { method: "DELETE" }),
    uploadDocumentFile: (id: string, file: Blob, name: string) =>
      api.request<DocumentDetail>(`${doc(id)}/file`, { method: "PUT", query: { file_name: name }, rawBody: file }),
    documentFileUrl: (id: string) => api.request<{ url: string }>(`${doc(id)}/file`).then((b) => b.url),
    addRecommendation: (id: string, body: { body: string; responsible: string; due_on: string | null }) =>
      api.request<DocumentDetail>(`${doc(id)}/recommendations`, { method: "POST", body }),
    recommendationStatus: (recommendationId: string, status: RecommendationStatus, reason: string) =>
      api.request<Recommendation>(`${R}/recommendations/${enc(recommendationId)}/status`, {
        method: "POST",
        body: { status, reason },
      }),
    documentRevisions: (id: string, signal?: AbortSignal) => api.request<Revision[]>(`${doc(id)}/revisions`, { signal }),
    dispatches: (q: DispatchQuery, signal?: AbortSignal) =>
      api.request<DispatchPage>(`${R}/dispatches`, {
        query: {
          box: q.box,
          q: q.q.trim() || null,
          urgency: q.urgency,
          state: q.state,
          gouvernorat: q.gouvernorat,
          from: q.from,
          to: q.to,
          unread: q.unread || null,
        },
        signal,
      }),
    dispatch: (id: string, signal?: AbortSignal) => api.request<DispatchDetail>(`${R}/dispatches/${enc(id)}`, { signal }),
    sendDispatch: (body: DispatchBody) => api.request<DispatchDetail>(`${R}/dispatches`, { method: "POST", body }),
    replyDispatch: (id: string, body: string, gouvernoratCode: number | null) =>
      api.request<DispatchDetail>(`${R}/dispatches/${enc(id)}/replies`, {
        method: "POST",
        body: { body, gouvernorat_code: gouvernoratCode },
      }),
    attachToDispatch: (id: string, file: Blob, name: string, replyId: string | null) =>
      api.request<Attachment>(`${R}/dispatches/${enc(id)}/attachments`, {
        method: "PUT",
        query: { file_name: name, reply_id: replyId },
        rawBody: file,
      }),
    attachmentUrl: (attachmentId: string) =>
      api.request<{ url: string }>(`${R}/attachments/${enc(attachmentId)}`).then((b) => b.url),
    closeDispatch: (id: string) => api.request<DispatchDetail>(`${R}/dispatches/${enc(id)}/close`, { method: "POST", body: {} }),
  };
}
