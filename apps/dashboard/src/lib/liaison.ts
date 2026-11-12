/**
 * Informing the partner bodies by phone (OS20, docs/phase-os20/design-os20.md): types and calls of
 * `/api/v1/staff/liaison`. The level of a report (1: handled in the room; 2: bodies informed), the contact system
 * (central and regional), the bodies informed of a report with their calls, the follow-ups and the history.
 * The link with the bodies is the phone only: the room calls from its softphone or dials by hand, then records.
 */
import type { ApiClient } from "./api";
import type { IconName, Tone } from "../components/Icon";

export type LiaisonCategory =
  | "civil"
  | "security"
  | "ministry"
  | "regional"
  | "public";
export const LIAISON_CATEGORIES: readonly LiaisonCategory[] = [
  "civil",
  "security",
  "ministry",
  "regional",
  "public",
];
export type CallResult = "answered" | "no_answer" | "busy" | "wrong_number";
export const CALL_RESULTS: readonly CallResult[] = [
  "answered",
  "no_answer",
  "busy",
  "wrong_number",
];
/** Minutes after which the room is reminded to call back (0: no reminder). */
export const FOLLOW_UP_MINUTES = [0, 5, 10, 15, 30] as const;

export interface LiaisonPoint {
  lat: number;
  lon: number;
}

export interface Official {
  id: string;
  body_id: string;
  name: string;
  role: string | null;
  phones: string[];
  email: string | null;
  duty: string | null;
  position: number;
  status: string;
  updated_at: string;
  updated_by_name: string | null;
}

export interface ContactBody {
  id: string;
  gouvernorat_code: number | null;
  category: LiaisonCategory;
  kind: "internal" | "external";
  agency: string | null;
  name: string;
  domain: string | null;
  address: string | null;
  location: LiaisonPoint | null;
  public_phone: string | null;
  status: "active" | "archived";
  created_by_name: string | null;
  updated_at: string;
  updated_by_name: string | null;
  version: number;
  editable: boolean;
  officials: Official[];
}

export interface OfficialBody {
  name: string;
  role?: string | null;
  phones: string[];
  email?: string | null;
  duty?: string | null;
  position?: number;
}

export interface ContactBodyIn {
  gouvernorat_code?: number | null;
  category: LiaisonCategory;
  kind?: "internal" | "external";
  name: string;
  domain?: string | null;
  address?: string | null;
  location?: LiaisonPoint | null;
  public_phone?: string | null;
  officials?: OfficialBody[];
  origin_incident_id?: string | null;
}

export interface ContactBodyPatch {
  category?: LiaisonCategory;
  name?: string;
  domain?: string | null;
  address?: string | null;
  public_phone?: string | null;
  version: number;
}

export interface LiaisonCall {
  id: string;
  incident_id: string;
  party_id: string;
  body_name: string;
  official_id: string | null;
  official_name: string | null;
  number: string;
  via: "softphone" | "manual";
  telephony_call_id: string | null;
  duration_s: number | null;
  result: CallResult;
  asked: string | null;
  promised: string | null;
  eta_min: number | null;
  note: string | null;
  follow_up_at: string | null;
  follow_up_done_at: string | null;
  follow_up_due: boolean;
  by_name: string | null;
  at: string;
  incident_title?: string | null;
  incident_category?: string | null;
}

export interface Party {
  id: string;
  body_id: string;
  official_id: string | null;
  body_name: string;
  official_name: string | null;
  official_role: string | null;
  phones: string[];
  public_phone: string | null;
  agency: string | null;
  category: LiaisonCategory | null;
  suggested: boolean;
  reason: string | null;
  added_by_name: string | null;
  added_at: string;
  removed_at: string | null;
  last_result: CallResult | null;
  calls: LiaisonCall[];
}

export interface Suggestion {
  agency: string;
  kind: "internal" | "external";
  body_id: string | null;
  name: string;
  public_phone: string | null;
  reason: { ar: string; fr: string };
  missing: boolean;
  in_report: boolean;
}

export interface IncidentLiaison {
  incident_id: string;
  gouvernorat_code: number | null;
  level: {
    level: 1 | 2;
    note: string | null;
    set_by_name: string | null;
    set_at: string;
  } | null;
  parties: Party[];
  suggestions: Suggestion[];
}

export interface UsedBefore {
  body_id: string;
  official_id: string | null;
  body_name: string;
  official_name: string | null;
  times: number;
  last_incident_id: string;
  last_at: string;
}

export interface HistoryParty {
  body_id: string;
  official_id: string | null;
  body_name: string;
  official_name: string | null;
  official_role: string | null;
  last_result: CallResult | null;
  calls: number;
}

export interface HistoryRow {
  incident_id: string;
  title: string | null;
  category: string;
  gouvernorat_code: number | null;
  status: string;
  opened_at: string;
  level: 1 | 2 | null;
  parties: HistoryParty[];
}

export interface PickerData {
  suggestions: Suggestion[];
  used_before: UsedBefore[];
  history: HistoryRow[];
}

export interface PartyPick {
  body_id: string;
  official_id?: string | null;
  suggested?: boolean;
  reason?: string | null;
}

export interface CallBody {
  official_id?: string | null;
  number: string;
  via: "softphone" | "manual";
  telephony_call_id?: string | null;
  result: CallResult;
  asked?: string | null;
  promised?: string | null;
  eta_min?: number | null;
  note?: string | null;
  follow_up_min?: number;
}

export interface BodyFilter {
  gouvernorat?: number | null;
  category?: LiaisonCategory | "";
  q?: string;
}

const CATEGORY_LOOK: Record<LiaisonCategory, { icon: IconName; tone: Tone }> = {
  civil: { icon: "localFireDepartment", tone: "red" },
  security: { icon: "policy", tone: "green" },
  ministry: { icon: "apartment", tone: "purple" },
  regional: { icon: "hub", tone: "teal" },
  public: { icon: "groups", tone: "amber" },
};

export function categoryLook(category: LiaisonCategory | null | undefined): {
  icon: IconName;
  tone: Tone;
} {
  return (
    (category && CATEGORY_LOOK[category]) || { icon: "call", tone: "slate" }
  );
}

export const RESULT_TONE: Record<CallResult, Tone> = {
  answered: "green",
  no_answer: "amber",
  busy: "orange",
  wrong_number: "red",
};

/** The number to call for a party: the official's first phone, else the body's public number. */
export function partyNumber(
  party: Pick<Party, "phones" | "public_phone">,
): string | null {
  return party.phones[0] ?? party.public_phone ?? null;
}

/** Bodies whose name, field, address or officials hold the words come first; the others keep their order. */
export function rankBodies(
  bodies: ContactBody[],
  query: string,
  first: ReadonlySet<string>,
): ContactBody[] {
  const q = query.trim().toLowerCase();
  const hit = (b: ContactBody) =>
    !q ||
    [
      b.name,
      b.domain,
      b.address,
      ...b.officials.flatMap((o) => [o.name, o.role, ...o.phones]),
    ]
      .filter(Boolean)
      .some((s) => String(s).toLowerCase().includes(q));
  const score = (b: ContactBody) =>
    (q && hit(b) ? 2 : 0) + (first.has(b.id) ? 1 : 0);
  return bodies
    .map((b, i) => ({ b, i, s: score(b) }))
    .filter(({ b }) => !q || hit(b))
    .sort((x, y) => y.s - x.s || x.i - y.i)
    .map(({ b }) => b);
}

export const liaisonKeys = {
  all: ["liaison"] as const,
  bodies: (filter: BodyFilter) => ["liaison", "bodies", filter] as const,
  body: (id: string) => ["liaison", "body", id] as const,
  incident: (id: string) => ["liaison", "incident", id] as const,
  picker: (id: string) => ["liaison", "picker", id] as const,
  followUps: (incidentId?: string) =>
    ["liaison", "follow-ups", incidentId ?? ""] as const,
  calls: (result: CallResult | "") => ["liaison", "calls", result] as const,
  history: (level: number | "") => ["liaison", "history", level] as const,
};

const L = "/api/v1/staff/liaison";
const enc = encodeURIComponent;

export function liaisonApi(api: ApiClient) {
  return {
    liaisonBodies: (filter: BodyFilter, signal?: AbortSignal) =>
      api.request<ContactBody[]>(`${L}/bodies`, {
        query: {
          gouvernorat: filter.gouvernorat ?? undefined,
          category: filter.category || undefined,
          q: filter.q?.trim() || undefined,
        },
        signal,
      }),
    liaisonBody: (id: string, signal?: AbortSignal) =>
      api.request<ContactBody>(`${L}/bodies/${enc(id)}`, { signal }),
    liaisonCreateBody: (body: ContactBodyIn) =>
      api.request<ContactBody>(`${L}/bodies`, { method: "POST", body }),
    liaisonPatchBody: (id: string, body: ContactBodyPatch) =>
      api.request<ContactBody>(`${L}/bodies/${enc(id)}`, {
        method: "PATCH",
        body,
      }),
    liaisonArchiveBody: (id: string) =>
      api.request<ContactBody>(`${L}/bodies/${enc(id)}/archive`, {
        method: "POST",
      }),
    liaisonAddOfficial: (bodyId: string, body: OfficialBody) =>
      api.request<Official>(`${L}/bodies/${enc(bodyId)}/officials`, {
        method: "POST",
        body,
      }),
    liaisonArchiveOfficial: (id: string) =>
      api.request<undefined>(`${L}/officials/${enc(id)}`, { method: "DELETE" }),
    liaisonIncident: (incidentId: string, signal?: AbortSignal) =>
      api.request<IncidentLiaison>(`${L}/incidents/${enc(incidentId)}`, {
        signal,
      }),
    liaisonSetLevel: (incidentId: string, level: 1 | 2) =>
      api.request<IncidentLiaison>(`${L}/incidents/${enc(incidentId)}/level`, {
        method: "PUT",
        body: { level },
      }),
    liaisonPicker: (incidentId: string, signal?: AbortSignal) =>
      api.request<PickerData>(`${L}/incidents/${enc(incidentId)}/picker`, {
        signal,
      }),
    liaisonAddParties: (incidentId: string, parties: PartyPick[]) =>
      api.request<IncidentLiaison>(
        `${L}/incidents/${enc(incidentId)}/parties`,
        {
          method: "POST",
          body: { parties },
        },
      ),
    liaisonRemoveParty: (incidentId: string, partyId: string) =>
      api.request<IncidentLiaison>(
        `${L}/incidents/${enc(incidentId)}/parties/${enc(partyId)}`,
        {
          method: "DELETE",
        },
      ),
    liaisonAddCall: (incidentId: string, partyId: string, body: CallBody) =>
      api.request<LiaisonCall>(
        `${L}/incidents/${enc(incidentId)}/parties/${enc(partyId)}/calls`,
        {
          method: "POST",
          body,
        },
      ),
    liaisonFollowUps: (incidentId?: string, signal?: AbortSignal) =>
      api.request<LiaisonCall[]>(`${L}/follow-ups`, {
        query: { incident_id: incidentId },
        signal,
      }),
    liaisonFollowUpDone: (callId: string) =>
      api.request<LiaisonCall>(`${L}/calls/${enc(callId)}/follow-up-done`, {
        method: "POST",
      }),
    liaisonCalls: (result: CallResult | "", signal?: AbortSignal) =>
      api.request<LiaisonCall[]>(`${L}/calls`, {
        query: { result: result || undefined },
        signal,
      }),
    liaisonHistory: (level: number | "", signal?: AbortSignal) =>
      api.request<HistoryRow[]>(`${L}/history`, {
        query: { level: level || undefined },
        signal,
      }),
  };
}
