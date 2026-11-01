import type { ApiClient } from "./api";
import type { Download } from "./layersApi";

/**
 * SNACR (phase S, docs/phase-s/design-s.md): the national risk analysis and coverage plan drawn from the Office's
 * yearly archive of interventions (three years by default), with the [SIM] years until the real files arrive.
 */

export const FAMILIES = ["medical", "road", "fire", "rescue"] as const;
export type Family = (typeof FAMILIES)[number];
export const ZONES = ["urban", "periurban", "rural"] as const;
export type Zone = (typeof ZONES)[number];
export const HAZARDS = [
  "flood",
  "forest_fire",
  "industrial",
  "hazmat_transport",
  "coastal",
  "earthquake",
  "storm",
  "drought",
  "epidemic",
] as const;
export type Hazard = (typeof HAZARDS)[number];
export type Priority = "high" | "medium" | "low";

export interface SnacrDataset {
  id: string;
  year: number;
  source: "office" | "simulated" | "live";
  simulated: boolean;
  file_name: string | null;
  rows: number;
  quality: {
    read?: number;
    kept?: number;
    skipped?: number;
    flags?: Record<string, number>;
    unmatched?: number;
    [key: string]: unknown;
  };
  imported_by_name: string | null;
  imported_at: string;
}

export interface SnacrMethod {
  goal: number;
  urban: number;
  periurban: number;
  targets: Record<Family, Record<Zone, number>>;
  review_months: number;
  validity_years: number;
}

export interface Figures {
  rows: number;
  completeness_pct: number | null;
  recorded_pct: number | null;
  compliance_pct: number | null;
}

export interface FamilyFigures extends Figures {
  arrival_median?: number | null;
  arrival_p90?: number | null;
  departure_median?: number | null;
  departure_p90?: number | null;
  target?: number | null;
}

export interface DelegationAnalysis extends Figures {
  id: number;
  gouvernorat_code: number;
  name_ar: string;
  name_fr: string;
  population: number | null;
  area_km2: number | null;
  zone: Zone;
  annual: number;
  rate_per_1000: number | null;
  frequency_level: number | null;
  coverage_level: number | null;
  priority: Priority | null;
  families: Partial<Record<Family, FamilyFigures>>;
}

export interface GouvernoratAnalysis extends Figures {
  code: number;
  unmatched: number;
  annual: number;
  rate_per_1000: number | null;
  families: Partial<Record<Family, FamilyFigures>>;
}

export interface SnacrAnalysis {
  years: number[];
  codes: number[];
  simulated: boolean;
  datasets: { year: number; simulated: boolean; rows: number; source?: "office" | "simulated" | "live" }[];
  method: SnacrMethod;
  breaks: number[];
  totals: Figures & { unmatched: number; annual: number; population: number | null; rate_per_1000: number | null };
  by_year: { year: number; families: Partial<Record<Family, number>> }[];
  gouvernorats: GouvernoratAnalysis[];
  delegations: DelegationAnalysis[];
  /** Délégations by frequency level (rows 1-5) and coverage level (columns 1-5). */
  matrix: number[][];
  month: Partial<Record<Family, number[]>>;
  /** Monday first (ISO), 24 hours, local time. */
  weekday_hour: Partial<Record<Family, number[][]>>;
  subtypes: Partial<Record<Family, { subtype: string; rows: number }[]>>;
  /** Phase S2: the parts of a mission in minutes, from the records of the operations rooms. */
  mission?: Partial<Record<Family, MissionFamily>>;
}

export const MISSION_PARTS = ["turnout", "travel", "on_scene", "transport", "length"] as const;
export type MissionPart = (typeof MISSION_PARTS)[number];

export type MissionFamily = {
  rows: number;
  returned_pct: number | null;
  hospital_rows: number;
  crew_mean: number | null;
} & { [K in `${MissionPart}_${"median" | "p90"}`]: number | null };

export interface UnmatchedName {
  gouvernorat_code: number;
  raw: string;
  rows: number;
}

export interface SnacrAlias {
  id: string;
  gouvernorat_code: number;
  raw: string;
  delegation_id: number;
  created_by_name: string | null;
  created_at: string;
}

export interface SpecialRiskIn {
  gouvernorat_code: number;
  hazard: Hazard;
  probability: number;
  gravity: number;
  note?: string | null;
}

export interface SpecialRisk extends SpecialRiskIn {
  id: string;
  level: Priority;
  note: string | null;
  simulated: boolean;
  updated_by_name: string | null;
  updated_at: string | null;
}

export interface SnacrReference {
  code: string;
  title: string;
  use: string;
  url: string | null;
}

export interface SnacrOverview {
  datasets: SnacrDataset[];
  default_years: number[];
  method: SnacrMethod;
  references: SnacrReference[];
  can_import: boolean;
  can_edit_national: boolean;
}

export interface Objective {
  kind: "coverage" | "data" | "names" | "special";
  gouvernorat_code: number;
  delegation_id: number | null;
  delegation: string | null;
  family: Family | null;
  hazard: Hazard | null;
  target_min: number | null;
  from_pct: number | null;
  to_pct: number | null;
  rows: number | null;
}

export interface SnacrPlanSummary {
  id: string;
  gouvernorat_code: number | null;
  version: number;
  years: number[];
  status: "draft" | "approved" | "superseded";
  simulated: boolean;
  created_by_name: string | null;
  created_at: string;
  approved_by_name: string | null;
  approved_at: string | null;
  review_due: string | null;
  valid_until: string | null;
  objectives: number;
  can_approve: boolean;
}

export interface SnacrPlan extends SnacrPlanSummary {
  objective_list: Objective[];
  special_risks: SpecialRisk[];
  references: SnacrReference[];
}

// ── Studies in the Office's format (SEC_GLOB, SAP, SR, LCI, SB, DIV): the methodology note of 2026-11-01. ──

export const STUDY_TABLES = ["SEC_GLOB", "SAP", "SR", "LCI", "SB", "DIV"] as const;
export type StudyTableKey = (typeof STUDY_TABLES)[number];
export type StudyPeriod = "J" | "S" | "T";

/** Counts per year (null: the délégation was under another unit that year, "*"), yearly mean, travel minutes. */
export interface StudyFigures {
  counts: Record<string, Partial<Record<StudyPeriod, number>> | null>;
  mean: Partial<Record<StudyPeriod, number | null>>;
  travel: Partial<Record<StudyPeriod, number | null>>;
  total: number;
}

export interface StudyRow extends StudyFigures {
  delegation_id: number | null;
  delegation: string;
  area_km2: number | null;
  population: number | null;
  density: number | null;
}

export interface StudyUnit {
  unit: string;
  rows: StudyRow[];
  subtotal: StudyFigures & { delegations: number; area_km2: number | null };
}

export interface StudyTable {
  key: StudyTableKey;
  label_ar: string;
  gouvernorats: { gouvernorat_code: number; gouvernorat: string; units: StudyUnit[]; total: StudyFigures }[];
  total: StudyFigures;
}

export interface SnacrStudySummary {
  id: string;
  number: number;
  gouvernorat_code: number | null;
  years: number[];
  split: boolean;
  travel_max: number;
  status: "current" | "archived";
  simulated: boolean;
  quality: Record<string, unknown>;
  created_by_name: string | null;
  created_at: string;
  archived_at: string | null;
}

/** One table of the study read as a class: by year, its share of all outings, its change, its night share. */
export interface StudyClassFinding {
  key: StudyTableKey;
  label_ar: string;
  per_year: Record<string, number | null>;
  total: number;
  share_pct: number;
  change_pct: number | null;
  steps: { from: number; to: number; change_pct: number | null }[];
  night_pct: number | null;
  travel: Partial<Record<StudyPeriod, number | null>>;
}

export interface StudyDelegationFinding {
  gouvernorat: string;
  delegation: string;
  units: string[];
  per_year: Record<string, number | null>;
  mean: number;
  population: number | null;
  rate_per_1000: number | null;
  change_pct: number | null;
  travel: number | null;
}

export type StudyNoteTone = "up" | "down" | "warn" | "info";

export interface StudyFindings {
  classes: StudyClassFinding[];
  delegations: StudyDelegationFinding[];
  notes: { tone: StudyNoteTone; text_ar: string }[];
  /** Absent from the studies read before the damages were joined. */
  damages?: StudyDamages;
}

/** The damages of the study's interventions (joined by NUM_SEQUENTIEL), per year. */
export interface StudyDamageLine {
  code: string | null;
  label: string;
  unit: "ha" | "bale" | "bag";
  per_year: Record<string, number>;
  outings: number;
  total: number;
}

export interface StudyDamages {
  forest: StudyDamageLine[];
  agri: StudyDamageLine[];
  forest_ha: Record<string, number>;
}

export interface DamageStatus {
  kind: "forest" | "agri";
  lines: number;
  matched: number;
  file_name: string | null;
  imported_at: string | null;
  years: number[];
}

export interface DamageImport {
  kind: "forest" | "agri";
  read: number;
  kept: number;
  rejected: Record<string, number>;
  status: DamageStatus[];
}

export interface SnacrStudy extends SnacrStudySummary {
  tables: { years: number[]; periods: StudyPeriod[]; tables: StudyTable[] };
  findings: StudyFindings;
}

export interface StudyIn {
  gouvernorat_code: number | null;
  years: readonly number[];
  split: boolean;
  travel_max: number;
}

const S = "/api/v1/staff/snacr";
const enc = encodeURIComponent;

export const snacrKeys = {
  all: ["snacr"] as const,
  overview: ["snacr", "overview"] as const,
  analysis: (years: readonly number[], gouvernorat: number | null) => ["snacr", "analysis", years, gouvernorat] as const,
  unmatched: ["snacr", "unmatched"] as const,
  aliases: ["snacr", "aliases"] as const,
  special: (gouvernorat: number | null) => ["snacr", "special", gouvernorat] as const,
  plans: (gouvernorat: number | null) => ["snacr", "plans", gouvernorat] as const,
  plan: (id: string) => ["snacr", "plan", id] as const,
  studies: (gouvernorat: number | null) => ["snacr", "studies", gouvernorat] as const,
  study: (id: string) => ["snacr", "study", id] as const,
  damages: ["snacr", "damages"] as const,
};

export function snacrApi(api: ApiClient) {
  return {
    snacr: (signal?: AbortSignal) => api.request<SnacrOverview>(S, { signal }),
    snacrAnalysis: (years: readonly number[], gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<SnacrAnalysis>(`${S}/analysis`, { query: { years, gouvernorat }, signal }),
    /** ``year`` null: every year the file covers; ``merge``: only the file's gouvernorats are replaced. */
    importSnacr: (year: number | null, file: File, merge = false) =>
      api.request<{ dataset: SnacrDataset; datasets: SnacrDataset[] }>(`${S}/datasets`, {
        method: "POST",
        query: { year: year ?? undefined, file_name: file.name, merge: merge || undefined },
        rawBody: file,
      }),
    /** A damage table of the Office (degat_forestieres or degat_Agriculteur), recognised by its headings. */
    importSnacrDamages: (file: File) =>
      api.request<DamageImport>(`${S}/damages`, { method: "POST", query: { file_name: file.name }, rawBody: file }),
    snacrDamages: (signal?: AbortSignal) => api.request<DamageStatus[]>(`${S}/damages`, { signal }),
    simulateSnacr: (year: number) =>
      api.request<{ dataset: SnacrDataset }>(`${S}/datasets/simulate`, { method: "POST", query: { year } }),
    liveSnacr: (year: number) =>
      api.request<{ dataset: SnacrDataset }>(`${S}/datasets/live`, { method: "POST", query: { year } }),
    deleteSnacrYear: (year: number) => api.request<undefined>(`${S}/datasets/${year}`, { method: "DELETE" }),
    snacrUnmatched: (signal?: AbortSignal) => api.request<UnmatchedName[]>(`${S}/unmatched`, { signal }),
    snacrAliases: (signal?: AbortSignal) => api.request<SnacrAlias[]>(`${S}/aliases`, { signal }),
    addSnacrAlias: (body: { gouvernorat_code: number; raw: string; delegation_id: number }) =>
      api.request<{ alias: SnacrAlias; rows_fixed: number }>(`${S}/aliases`, { method: "POST", body }),
    specialRisks: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<SpecialRisk[]>(`${S}/special-risks`, { query: { gouvernorat }, signal }),
    saveSpecialRisk: (body: SpecialRiskIn) => api.request<SpecialRisk>(`${S}/special-risks`, { method: "POST", body }),
    deleteSpecialRisk: (id: string) => api.request<undefined>(`${S}/special-risks/${enc(id)}`, { method: "DELETE" }),
    snacrPlans: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<SnacrPlanSummary[]>(`${S}/plans`, { query: { gouvernorat }, signal }),
    snacrPlan: (id: string, signal?: AbortSignal) => api.request<SnacrPlan>(`${S}/plans/${enc(id)}`, { signal }),
    createSnacrPlan: (gouvernorat: number | null, years: readonly number[]) =>
      api.request<SnacrPlan>(`${S}/plans`, { method: "POST", body: { gouvernorat_code: gouvernorat, years } }),
    approveSnacrPlan: (id: string) => api.request<SnacrPlan>(`${S}/plans/${enc(id)}/approve`, { method: "POST" }),
    snacrStudies: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<SnacrStudySummary[]>(`${S}/studies`, { query: { gouvernorat }, signal }),
    snacrStudy: (id: string, signal?: AbortSignal) => api.request<SnacrStudy>(`${S}/studies/${enc(id)}`, { signal }),
    launchSnacrStudy: (body: StudyIn) => api.request<SnacrStudy>(`${S}/studies`, { method: "POST", body }),
    snacrStudyExport: async (
      study: Pick<SnacrStudySummary, "id" | "number" | "gouvernorat_code">,
      format: "pdf" | "xlsx",
    ): Promise<Download> => {
      const accept =
        format === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const response = await api.requestRaw(`${S}/studies/${enc(study.id)}/export`, { query: { format }, accept });
      const scope = study.gouvernorat_code === null ? "national" : `g${study.gouvernorat_code}`;
      return { blob: await response.blob(), filename: `snacr-study-${scope}-${study.number}.${format}` };
    },
    snacrPlanPdf: async (plan: Pick<SnacrPlanSummary, "id" | "version" | "gouvernorat_code">): Promise<Download> => {
      const response = await api.requestRaw(`${S}/plans/${enc(plan.id)}/document`, {
        query: { format: "pdf" },
        accept: "application/pdf",
      });
      const scope = plan.gouvernorat_code === null ? "national" : `g${plan.gouvernorat_code}`;
      return { blob: await response.blob(), filename: `snacr-${scope}-v${plan.version}.pdf` };
    },
  };
}

/** Colours of the priority classes (the same in both themes: drawn on the map and in the matrix). */
export const PRIORITY_COLOURS: Record<Priority | "none", string> = {
  high: "#C81E1E",
  medium: "#F59E0B",
  low: "#16A34A",
  none: "#E3E7EF",
};

/** Frequency × coverage, the class of the matrix cell (the thresholds of domain.priority_of). */
export function priorityOf(frequency: number, coverage: number): Priority {
  const score = frequency * coverage;
  return score >= 15 ? "high" : score >= 8 ? "medium" : "low";
}

/** Probability × gravity of a special risk, read on the same scale. */
export const specialLevel = priorityOf;
