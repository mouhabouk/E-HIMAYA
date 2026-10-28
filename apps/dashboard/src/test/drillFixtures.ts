import { vi } from "vitest";
import type { drillApi } from "../lib/drill";
import type { DrillResponse } from "../lib/drill";
import { DRILL, FEED, INJECTS, REPORT } from "./drillData";

const [INJECT] = INJECTS as [(typeof INJECTS)[number], ...typeof INJECTS];
const ANSWER = FEED.items.flatMap((i) => i.responses)[0] as DrillResponse;

export function fakeDrillApi(): ReturnType<typeof drillApi> {
  return {
    drills: vi.fn(() => Promise.resolve([])),
    drill: vi.fn(() => Promise.resolve(DRILL)),
    createDrill: vi.fn(() => Promise.resolve(DRILL)),
    editDrill: vi.fn(() => Promise.resolve(DRILL)),
    injects: vi.fn(() => Promise.resolve(INJECTS)),
    addInject: vi.fn(() => Promise.resolve(INJECT)),
    deleteInject: vi.fn(() => Promise.resolve(undefined)),
    generateInjects: vi.fn(() => Promise.resolve(INJECTS)),
    submitDrill: vi.fn(() => Promise.resolve({ ...DRILL, status: "submitted" as const })),
    decideDrill: vi.fn(() => Promise.resolve(DRILL)),
    startDrill: vi.fn(() => Promise.resolve(DRILL)),
    stopDrill: vi.fn(() => Promise.resolve(DRILL)),
    drillFeed: vi.fn(() => Promise.resolve(FEED)),
    respondInject: vi.fn(() => Promise.resolve(ANSWER)),
    releaseResponse: vi.fn(() => Promise.resolve(undefined)),
    evaluateInject: vi.fn(() =>
      Promise.resolve({ plan_followed: "yes" as const, score: 4, notes: "", evaluated_by_name: null, evaluated_at: "2026-11-04T10:00:00Z" }),
    ),
    closeDrill: vi.fn(() => Promise.resolve(DRILL)),
    drillReport: vi.fn(() => Promise.resolve(REPORT)),
  };
}
