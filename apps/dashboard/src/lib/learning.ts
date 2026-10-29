import type { ApiClient } from "./api";
import type { Download } from "./layersApi";
import type { Category } from "./types";

/**
 * The training centre (docs/learning.md): the system administrator chooses which trainings run, launches them or
 * schedules them (setting `learning.schedule`), and reads their results. The report texts, anonymised, are the data
 * set; the operator confirms the reading of a closed or rejected report, which weighs more than the system's own.
 */

export const LEARNING_TASKS = [
  "report_category",
  "report_lives",
  "report_rejected",
  "derja_words",
  "fire_smoke",
  "command_ranker",
] as const;
export type LearningTask = (typeof LEARNING_TASKS)[number];
export type JobState =
  | "queued"
  | "running"
  | "done"
  | "skipped"
  | "failed"
  | "waiting_trainer";
export const LEARNING_SCHEDULE = "learning.schedule";

export interface ScheduleEntry {
  enabled: boolean;
  every_days: number;
}

export type LearningSchedule = Record<LearningTask, ScheduleEntry>;

export interface ClassScores {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface Scores {
  n: number;
  accuracy: number;
  macro_f1: number;
  classes: Record<string, ClassScores>;
}

export interface WordCandidate {
  word: string;
  count: number;
  script: "ar" | "latn";
  category: string;
}

/** What a job says it did; the keys depend on the task. */
export interface JobResult {
  synced?: number;
  skipped?: string;
  promoted?: boolean;
  version?: number;
  primary?: number;
  train?: number;
  heldout?: number;
  train_confirmed?: number;
  heldout_confirmed?: number;
  evaluated_on?: "confirmed" | "all";
  texts?: number;
  count?: number;
  candidates?: WordCandidate[];
  images?: number;
  confirmed?: number;
  boxes?: Record<string, number>;
  trainer?: { model: string; metrics: Record<string, number>; by: string };
  /** The commander's ranking (AI5c): decisions linked to their outcome, and the rules' first proposal adopted. */
  outcomes_linked?: number;
  ranked_incidents?: number;
  rules_top1?: number;
}

/** The learned ranking against the rules' order on the held-out incidents (AI5c). */
export interface Ranking {
  incidents: number;
  top1: number;
  rules_top1: number;
  current_top1: number | null;
}

export interface TrainingJob {
  id: string;
  task: LearningTask;
  trigger: "manual" | "schedule";
  state: JobState;
  requested_by_name: string;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  result: JobResult;
  error: string | null;
}

export interface TrainedModel {
  version: number;
  algorithm: string;
  metrics: {
    model?: Scores;
    current?: Scores | null;
    baseline?: Scores | null;
    evaluated_on?: "confirmed" | "all";
    ranking?: Ranking;
  };
  primary_metric: string;
  train_samples: number;
  heldout_samples: number;
  trained_by_name: string;
  trained_at: string;
}

export interface TaskOverview {
  task: LearningTask;
  runner: "worker" | "trainer";
  primary_metric: string;
  schedule: ScheduleEntry;
  last_job: TrainingJob | null;
  current: TrainedModel | null;
}

export interface LearningOverview {
  samples: {
    total: number;
    by_origin: Record<string, number>;
    by_split: Record<string, number>;
  };
  tasks: TaskOverview[];
}

export interface LearningLabel {
  category: Category | null;
  lives_at_risk: boolean | null;
  rejected: boolean | null;
  confirmed: string[];
}

export type LearningLabelIn = Partial<
  Pick<LearningLabel, "category" | "lives_at_risk" | "rejected">
>;

export const learningKeys = {
  overview: ["learning"] as const,
  jobs: ["learning", "jobs"] as const,
  label: (reportId: string) => ["learning", "label", reportId] as const,
};

const L = "/api/v1/staff/learning";
const enc = encodeURIComponent;

export function learningApi(api: ApiClient) {
  return {
    learning: (signal?: AbortSignal) =>
      api.request<LearningOverview>(L, { signal }),
    learningJobs: (signal?: AbortSignal) =>
      api.request<TrainingJob[]>(`${L}/jobs`, { signal }),
    launchTraining: (task: LearningTask) =>
      api.request<{ id: string; task: LearningTask; state: JobState }>(
        `${L}/jobs`,
        { method: "POST", body: { task } },
      ),
    learningDataset: async (
      set: "reports" | "fire_smoke",
    ): Promise<Download> => {
      const csv = set === "reports";
      const response = await api.requestRaw(`${L}/datasets/${set}`, {
        accept: csv ? "text/csv" : "application/json",
      });
      return {
        blob: await response.blob(),
        filename: csv
          ? "e-himaya-report-texts.csv"
          : "fire-smoke-manifest.json",
      };
    },
    learningLabel: (reportId: string, signal?: AbortSignal) =>
      api.request<LearningLabel>(
        `/api/v1/staff/reports/${enc(reportId)}/learning-label`,
        { signal },
      ),
    saveLearningLabel: (reportId: string, body: LearningLabelIn) =>
      api.request<LearningLabel>(
        `/api/v1/staff/reports/${enc(reportId)}/learning-label`,
        { method: "PUT", body },
      ),
  };
}
