// covers: phase L2 (docs/phase-l/design-l2.md §2): seasonal programmes, their points, versions and imports.
import type { ApiClient } from "./api";

export const PROGRAMME_KINDS = ["road", "seasonal", "beach", "other"] as const;
export type ProgrammeKind = (typeof PROGRAMME_KINDS)[number];
export const PROGRAMME_STATUSES = ["draft", "approved", "updated", "ended", "cancelled"] as const;
export type ProgrammeStatus = (typeof PROGRAMME_STATUSES)[number];
export const POINT_STATUSES = ["open", "closed", "postponed"] as const;
export type PointStatus = (typeof POINT_STATUSES)[number];
export const CONFIDENCES = ["confirmed", "high", "medium", "approximate", "review", "unknown"] as const;
export type Confidence = (typeof CONFIDENCES)[number];
/** The programme code of the template: `ROAD-2026`, `BEACH-2026-NORTH`. */
export const PROGRAMME_CODE = /^[A-Z]+-[0-9]{4}(-[A-Z0-9]+)?$/;
/** Below this share of lifeguards deployed to planned, a point is flagged (design-l2 §2.7). */
export const LOW_COVERAGE = 0.5;

export interface ProgrammeFigures {
  points: number;
  unlocated: number;
  open: number;
  gouvernorats: number;
  staff: number;
  lifeguards_planned: number;
  lifeguards_deployed: number;
}

export interface Programme {
  id: string;
  code: string;
  kind: ProgrammeKind;
  title: string;
  season: string;
  valid_from: string;
  valid_to: string;
  status: ProgrammeStatus;
  version: number;
  source_document: string;
  declared: Record<string, number>;
  approved_by_name: string | null;
  approved_at: string | null;
  cancel_reason: string | null;
  layer_key: string | null;
  /** On the maps today: approved or updated, and today within the validity dates. */
  live: boolean;
  updated_by_name: string | null;
  updated_at: string;
  figures: ProgrammeFigures;
  can_edit: boolean;
  can_follow_up: boolean;
}

export interface ProgrammePoint {
  id: string;
  ref: string;
  gouvernorat_code: number | null;
  place_name: string;
  sub_points: string | null;
  lat: number | null;
  lon: number | null;
  geo_confidence: Confidence;
  geo_note: string | null;
  staff_count: number | null;
  staff_composition: string | null;
  supervisors: number | null;
  lifeguards_planned: number | null;
  lifeguards_deployed: number | null;
  equipment: string | null;
  hours: string | null;
  opening_date: string | null;
  closing_date: string | null;
  status: PointStatus;
  /** The operations rooms only: null for everyone else. */
  supervisor_name: string | null;
  supervisor_phone: string | null;
  notes: string | null;
  updated_at: string;
  can_follow_up: boolean;
}

export interface ProgrammeDetail {
  programme: Programme;
  points: ProgrammePoint[];
  computed: Record<string, number>;
}

export interface ProgrammeBody {
  code: string;
  kind: ProgrammeKind;
  title: string;
  season?: string;
  valid_from: string;
  valid_to: string;
  source_document?: string;
}

export interface ProgrammePatch {
  title?: string;
  season?: string;
  valid_from?: string;
  valid_to?: string;
  source_document?: string;
  reason: string;
}

export interface CopyBody {
  code: string;
  valid_from: string;
  valid_to: string;
  season?: string;
  title?: string;
}

export type PointFields = Partial<Omit<ProgrammePoint, "id" | "ref" | "geo_note" | "updated_at" | "can_follow_up">>;
export type PointBody = PointFields & {
  ref: string;
  place_name: string;
  reason: string;
};
export type PointPatch = PointFields & { reason: string };

export interface Revision {
  number: number;
  action: string;
  reason: string | null;
  created_by_name: string | null;
  created_at: string;
  points: number;
}

/** What changed between two versions: programme fields, points added or removed, point fields `[before, after]`. */
export interface ProgrammeDiff {
  number: number;
  against: number | null;
  programme: Record<string, [unknown, unknown]>;
  added: string[];
  removed: string[];
  changed: Record<string, Record<string, [unknown, unknown]>>;
}

export interface Problem {
  code: string;
  programme?: string | null;
  ref?: string | null;
  line?: number | null;
  value?: string | null;
}

export interface ImportedProgramme {
  code: string;
  title: string | null;
  kind: ProgrammeKind | null;
  exists: boolean;
  status: ProgrammeStatus | null;
  points: number;
  unlocated: number;
  computed: Record<string, number>;
  declared: Record<string, number>;
  diff: ProgrammeDiff | null;
}

export interface ProgrammeImport {
  format: string;
  applied: boolean;
  programmes: ImportedProgramme[];
  errors: Problem[];
  warnings: Problem[];
}

/** Lifeguards deployed to planned, or null when nothing is planned. */
export function coverage(planned: number | null | undefined, deployed: number | null | undefined): number | null {
  if (!planned) return null;
  return (deployed ?? 0) / planned;
}

export function isLowCoverage(p: Pick<ProgrammePoint, "lifeguards_planned" | "lifeguards_deployed">): boolean {
  const c = coverage(p.lifeguards_planned, p.lifeguards_deployed);
  return c !== null && c < LOW_COVERAGE;
}

export interface PointFilters {
  gouvernorat?: number;
  status?: PointStatus;
  confidence?: Confidence | "unlocated";
  lowCoverage?: boolean;
  text?: string;
}

export function filterPoints(points: readonly ProgrammePoint[], f: PointFilters): ProgrammePoint[] {
  const text = f.text?.trim().toLowerCase();
  return points.filter(
    (p) =>
      (f.gouvernorat === undefined || p.gouvernorat_code === f.gouvernorat) &&
      (f.status === undefined || p.status === f.status) &&
      (f.confidence === undefined ||
        (f.confidence === "unlocated" ? p.lat === null : p.geo_confidence === f.confidence)) &&
      (!f.lowCoverage || isLowCoverage(p)) &&
      (!text || `${p.ref} ${p.place_name} ${p.sub_points ?? ""}`.toLowerCase().includes(text)),
  );
}

/** Declared totals of the file that differ from the totals computed from its points (shown, never blocking). */
export function totalGaps(
  declared: Record<string, number>,
  computed: Record<string, number>,
): [string, number, number][] {
  return Object.entries(declared)
    .filter(([k, v]) => k in computed && computed[k] !== v)
    .map(([k, v]) => [k, v, computed[k] ?? 0]);
}

/** Tunis day (UTC+1, no daylight saving) as YYYY-MM-DD. */
export function tunisToday(now = new Date()): string {
  return new Date(now.getTime() + 3_600_000).toISOString().slice(0, 10);
}

const P = "/api/v1/staff/programmes";
const enc = encodeURIComponent;

export const programmeKeys = {
  all: ["programmes"] as const,
  list: ["programmes", "list"] as const,
  detail: (id: string) => ["programmes", "detail", id] as const,
  revisions: (id: string) => ["programmes", "revisions", id] as const,
  diff: (id: string, n: number) => ["programmes", "diff", id, n] as const,
};

/** Seasonal programmes (phase L2): list, detail, life cycle, points, versions and the file import. */
export function programmesApi(api: ApiClient) {
  const one = (id: string) => `${P}/${enc(id)}`;
  return {
    programmes: (signal?: AbortSignal) => api.request<{ items: Programme[]; can_create: boolean }>(P, { signal }),
    programme: (id: string, signal?: AbortSignal) => api.request<ProgrammeDetail>(one(id), { signal }),
    createProgramme: (body: ProgrammeBody) => api.request<ProgrammeDetail>(P, { method: "POST", body }),
    updateProgramme: (id: string, body: ProgrammePatch) =>
      api.request<ProgrammeDetail>(one(id), { method: "PATCH", body }),
    deleteProgramme: (id: string) => api.requestRaw(one(id), { method: "DELETE" }).then(() => undefined),
    approveProgramme: (id: string, reason: string) =>
      api.request<ProgrammeDetail>(`${one(id)}/approve`, {
        method: "POST",
        body: { reason },
      }),
    cancelProgramme: (id: string, reason: string) =>
      api.request<ProgrammeDetail>(`${one(id)}/cancel`, {
        method: "POST",
        body: { reason },
      }),
    copyProgramme: (id: string, body: CopyBody) =>
      api.request<ProgrammeDetail>(`${one(id)}/copy`, { method: "POST", body }),
    addProgrammePoint: (id: string, body: PointBody) =>
      api.request<ProgrammeDetail>(`${one(id)}/points`, {
        method: "POST",
        body,
      }),
    updateProgrammePoint: (id: string, pointId: string, body: PointPatch) =>
      api.request<ProgrammeDetail>(`${one(id)}/points/${enc(pointId)}`, {
        method: "PATCH",
        body,
      }),
    deleteProgrammePoint: (id: string, pointId: string) =>
      api.request<ProgrammeDetail>(`${one(id)}/points/${enc(pointId)}`, {
        method: "DELETE",
      }),
    programmeRevisions: (id: string, signal?: AbortSignal) =>
      api.request<{ items: Revision[] }>(`${one(id)}/revisions`, { signal }).then((b) => b.items),
    programmeDiff: (id: string, n: number, signal?: AbortSignal) =>
      api.request<ProgrammeDiff>(`${one(id)}/revisions/${n}/diff`, { signal }),
    restoreProgramme: (id: string, n: number, reason: string) =>
      api.request<ProgrammeDetail>(`${one(id)}/revisions/${n}/restore`, {
        method: "POST",
        body: { reason },
      }),
    importProgrammes: (file: File, apply: boolean, reason = "") =>
      api.request<ProgrammeImport>(`${P}/imports`, {
        method: "POST",
        query: {
          file_name: file.name,
          apply,
          reason: apply ? reason : undefined,
        },
        rawBody: file,
      }),
  };
}
