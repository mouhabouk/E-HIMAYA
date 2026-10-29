import { vi } from "vitest";
import type {
  LearningLabelIn,
  LearningTask,
  learningApi,
  LearningLabel,
  LearningOverview,
  TaskOverview,
  TrainingJob,
} from "../lib/learning";

const OFF = { enabled: false, every_days: 7 };

export const CATEGORY_JOB: TrainingJob = {
  id: "job-1",
  task: "report_category",
  trigger: "manual",
  state: "done",
  requested_by_name: "Yamen Admin",
  requested_at: "2026-10-29T08:00:00Z",
  started_at: "2026-10-29T08:01:00Z",
  finished_at: "2026-10-29T08:02:00Z",
  result: {
    synced: 12,
    promoted: true,
    version: 2,
    primary: 0.87,
    train: 96,
    train_confirmed: 10,
    heldout: 24,
    heldout_confirmed: 4,
  },
  error: null,
};

export const WORDS_JOB: TrainingJob = {
  ...CATEGORY_JOB,
  id: "job-2",
  task: "derja_words",
  trigger: "schedule",
  requested_by_name: "system",
  result: {
    texts: 120,
    count: 1,
    candidates: [
      { word: "ta7rig", count: 7, script: "latn", category: "fire" },
    ],
  },
};

function task(
  key: TaskOverview["task"],
  extra: Partial<TaskOverview> = {},
): TaskOverview {
  return {
    task: key,
    runner: key === "fire_smoke" ? "trainer" : "worker",
    primary_metric: key === "fire_smoke" ? "map50" : "macro_f1",
    schedule: OFF,
    last_job: null,
    current: null,
    ...extra,
  };
}

export const OVERVIEW: LearningOverview = {
  samples: {
    total: 120,
    by_origin: { weak: 110, operator: 10 },
    by_split: { train: 96, heldout: 24 },
  },
  tasks: [
    task("report_category", {
      last_job: CATEGORY_JOB,
      current: {
        version: 2,
        algorithm: "char-ngram-logreg-v1",
        metrics: {
          model: { n: 24, accuracy: 0.9, macro_f1: 0.87, classes: {} },
          evaluated_on: "all",
        },
        primary_metric: "macro_f1",
        train_samples: 96,
        heldout_samples: 24,
        trained_by_name: "Yamen Admin",
        trained_at: "2026-10-29T08:02:00Z",
      },
    }),
    task("report_lives"),
    task("report_rejected"),
    task("derja_words", {
      last_job: WORDS_JOB,
      schedule: { enabled: true, every_days: 7 },
    }),
    task("fire_smoke"),
  ],
};

export const LABEL: LearningLabel = {
  category: "fire",
  lives_at_risk: null,
  rejected: true,
  confirmed: [],
};

export function fakeLearningApi(
  overview: LearningOverview = OVERVIEW,
): ReturnType<typeof learningApi> {
  return {
    learning: vi.fn(() => Promise.resolve(overview)),
    learningJobs: vi.fn(() => Promise.resolve([CATEGORY_JOB, WORDS_JOB])),
    launchTraining: vi.fn((t: LearningTask) =>
      Promise.resolve({ id: "job-9", task: t, state: "queued" as const }),
    ),
    learningDataset: vi.fn(() =>
      Promise.resolve({
        blob: new Blob(["id,text\n"]),
        filename: "e-himaya-report-texts.csv",
      }),
    ),
    learningLabel: vi.fn(() => Promise.resolve(LABEL)),
    saveLearningLabel: vi.fn((_id: string, body: LearningLabelIn) =>
      Promise.resolve({
        ...LABEL,
        ...body,
        confirmed: Object.keys(body).sort(),
      }),
    ),
  };
}
