/**
 * Notification and alert composer (contract §7): form state, client-side validation and the request body.
 * The server validates again; these rules only spare a round trip.
 */
import type {
  AlertCategory,
  Audience,
  Channel,
  Hazard,
  Localized,
  Message,
  MessageBody,
  MessageKind,
  Severity,
  Topic,
} from "./opsTypes";
import { CHANNELS } from "./opsTypes";
import type { OrgKind } from "./types";
import { fromPolygon, toPolygon, validateVertices, type PolygonError, type Vertex } from "./polygon";

export const TITLE_MAX = 120;
export const BODY_MAX = 1000;
export const MAX_ALERT_DAYS = 7;
export const SMS_CHARS = 300;

/** Phase M adds "delegations": some délégations of a gouvernorat, picked from the Map Tunisia list. */
export type AreaMode = "gouvernorats" | "delegations" | "polygon";

export interface MessageForm {
  kind: MessageKind;
  title: Localized;
  body: Localized;
  channels: Channel[];
  topic: Topic | "";
  audience: Audience | "";
  userId: string;
  gouvernorats: number[];
  severity: Severity | "";
  category: AlertCategory | "";
  hazard: Hazard | "";
  /** `datetime-local` value (local time, minutes). */
  expiresAt: string;
  areaMode: AreaMode;
  vertices: Vertex[];
  delegations: number[];
  /** Phase P2b, audience "organizations": some kinds only (none: every kind) and a read acknowledgement. */
  orgKinds: OrgKind[];
  ackRequired: boolean;
}

export type FormErrors = Partial<
  Record<
    | "titleAr"
    | "bodyAr"
    | "channels"
    | "topic"
    | "audience"
    | "userId"
    | "severity"
    | "category"
    | "expiresAt"
    | "polygon"
    | "delegations",
    string
  >
>;

const pad = (n: number) => String(n).padStart(2, "0");

/** `datetime-local` value of a date, in the browser's time zone. */
export function toLocalInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function emptyForm(kind: MessageKind, now: Date = new Date()): MessageForm {
  return {
    kind,
    title: { ar: "", fr: "", en: "" },
    body: { ar: "", fr: "", en: "" },
    channels: ["push"],
    topic: "",
    audience: kind === "info" ? "all" : "",
    userId: "",
    gouvernorats: [],
    severity: "",
    category: "",
    hazard: "",
    // Alerts expire within 7 days; 24 hours is the usual weather bulletin.
    expiresAt: toLocalInput(new Date(now.getTime() + 24 * 3_600_000)),
    areaMode: "gouvernorats",
    vertices: [],
    delegations: [],
    orgKinds: [],
    ackRequired: false,
  };
}

export function formFromMessage(m: Message): MessageForm {
  return {
    kind: m.kind,
    title: { ...m.title },
    body: { ...m.body },
    channels: [...m.channels],
    topic: m.topic ?? "",
    audience: m.audience ?? "",
    userId: m.user_id ?? "",
    gouvernorats: [...m.area.gouvernorat_codes],
    severity: m.severity ?? "",
    category: m.category ?? "",
    hazard: m.hazard ?? "",
    expiresAt: m.expires_at ? toLocalInput(new Date(m.expires_at)) : toLocalInput(new Date(Date.now() + 86_400_000)),
    areaMode: m.area.delegation_ids?.length ? "delegations" : m.area.polygon ? "polygon" : "gouvernorats",
    vertices: m.area.polygon?.type === "Polygon" && !m.area.delegation_ids?.length ? fromPolygon(m.area.polygon) : [],
    delegations: [...(m.area.delegation_ids ?? [])],
    orgKinds: [...(m.org_kinds ?? [])],
    ackRequired: m.ack_required ?? false,
  };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Error keys (under `notify.validation`) by field; empty when the form can be sent. */
export function validateForm(form: MessageForm, now: Date = new Date()): FormErrors {
  const errors: FormErrors = {};
  if (!form.title.ar.trim()) errors.titleAr = "titleRequired";
  if (!form.body.ar.trim()) errors.bodyAr = "bodyRequired";
  if (form.channels.length === 0) errors.channels = "channelsRequired";
  if (form.kind === "info") {
    if (!form.topic) errors.topic = "topicRequired";
    if (!form.audience) errors.audience = "audienceRequired";
    if (form.audience === "user" && !UUID.test(form.userId.trim())) errors.userId = "userIdInvalid";
  } else {
    if (!form.severity) errors.severity = "severityRequired";
    if (!form.category) errors.category = "categoryRequired";
    const expires = new Date(form.expiresAt);
    if (!form.expiresAt || Number.isNaN(expires.getTime())) errors.expiresAt = "expiryRequired";
    else if (expires.getTime() <= now.getTime() || expires.getTime() > now.getTime() + MAX_ALERT_DAYS * 86_400_000) {
      errors.expiresAt = "expiryRange";
    }
    if (form.areaMode === "polygon") {
      const err: PolygonError | null = validateVertices(form.vertices);
      if (err) errors.polygon = `polygon.${err}`;
    }
    if (form.areaMode === "delegations" && form.delegations.length === 0) errors.delegations = "delegationsRequired";
  }
  return errors;
}

export function toMessageBody(form: MessageForm, version?: number): MessageBody {
  const trim = (l: Localized): Localized => ({ ar: l.ar.trim(), fr: l.fr.trim(), en: l.en.trim() });
  const channels = CHANNELS.filter((c) => form.channels.includes(c));
  const base = { kind: form.kind, title: trim(form.title), body: trim(form.body), channels, ...(version ? { version } : {}) };
  if (form.kind === "info") {
    const toUser = form.audience === "user";
    const toOrgs = form.audience === "organizations";
    return {
      ...base,
      topic: form.topic || null,
      audience: form.audience || null,
      user_id: toUser ? form.userId.trim() : null,
      area: { gouvernorat_codes: toUser ? [] : [...form.gouvernorats] },
      org_kinds: toOrgs ? [...form.orgKinds].sort() : [],
      ack_required: toOrgs && form.ackRequired,
    };
  }
  return {
    ...base,
    severity: form.severity || null,
    category: form.category || null,
    hazard: form.hazard || null,
    expires_at: new Date(form.expiresAt).toISOString(),
    area:
      form.areaMode === "polygon"
        ? { gouvernorat_codes: [], polygon: toPolygon(form.vertices) }
        : form.areaMode === "delegations"
          ? { gouvernorat_codes: [], delegation_ids: [...form.delegations] }
          : { gouvernorat_codes: [...form.gouvernorats] },
  };
}

/** The SMS text as the delivery worker builds it (title, colon, body, cut at 300 characters). */
export function smsPreview(title: string, body: string): string {
  return `${title.trim()}: ${body.trim()}`.slice(0, SMS_CHARS);
}
