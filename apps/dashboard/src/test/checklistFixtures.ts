import { vi } from "vitest";
import type { Checklist, checklistApi, PlanTask } from "../lib/checklist";

/** A plan read by the local model [SIM]: two tasks traced to their page, one whose passage was not found. */
const task = (n: number, over: Partial<PlanTask> = {}): PlanTask => ({
  id: `t-${n}`,
  position: n,
  action: `مهمة ${n}`,
  owner: "",
  resource: "",
  page: n,
  quote: `مقطع ${n}`,
  quote_found: true,
  origin: "ai",
  review: "suggested",
  suggested: null,
  status: "todo",
  note: "",
  status_by_name: null,
  status_at: null,
  ...over,
});

export const PLAN = { id: "doc-1", number: "REG-2026-001", title: "المخطط الأزرق للفيضانات [SIM]" };

export const REVIEW: Checklist = {
  id: "c-1",
  state: "review",
  error: null,
  plan: PLAN,
  plans: [PLAN],
  model: "qwen3:4b",
  pages: 12,
  pages_read: 12,
  requested_by_name: "رئيس القاعة",
  requested_at: "2026-10-29T08:00:00Z",
  read_at: "2026-10-29T08:03:00Z",
  approved_by_name: null,
  approved_at: null,
  version: 2,
  tasks: [
    task(1, { action: "فتح خلية الأزمة", owner: "قاعة العمليات الجهوية", quote: "تفتح القاعة خلية الأزمة" }),
    task(2, { action: "استدعاء فرق الإنقاذ", resource: "زوارق", quote_found: false }),
    task(3, { action: "إخلاء الأحياء المنخفضة", owner: "المعتمد", page: 7 }),
  ],
  counts: { suggested: 3, kept: 0, deleted: 0, todo: 0, doing: 0, done: 0, not_applicable: 0 },
  reading_available: true,
  can_review: true,
  can_follow: false,
};

export const EMPTY: Checklist = {
  ...REVIEW,
  id: null,
  state: null,
  plan: null,
  model: null,
  pages: null,
  pages_read: null,
  requested_by_name: null,
  requested_at: null,
  read_at: null,
  version: 0,
  tasks: [],
  counts: { suggested: 0, kept: 0, deleted: 0, todo: 0, doing: 0, done: 0, not_applicable: 0 },
  can_review: false,
};

export const APPROVED: Checklist = {
  ...REVIEW,
  state: "approved",
  approved_by_name: "رئيس القاعة",
  approved_at: "2026-10-29T08:10:00Z",
  version: 6,
  tasks: [
    task(1, { action: "فتح خلية الأزمة", review: "accepted", status: "done", status_by_name: "عون", status_at: "2026-10-29T08:20:00Z" }),
    task(2, { action: "استدعاء فرق الإنقاذ بالزوارق", review: "edited", suggested: { action: "استدعاء فرق الإنقاذ" } }),
    task(3, { action: "إخلاء الأحياء المنخفضة", review: "deleted" }),
  ],
  counts: { suggested: 0, kept: 2, deleted: 1, todo: 1, doing: 0, done: 1, not_applicable: 0 },
  reading_available: true,
  can_review: false,
  can_follow: true,
};

export function fakeChecklistApi(list: Checklist = EMPTY): ReturnType<typeof checklistApi> {
  return {
    checklist: vi.fn(() => Promise.resolve(list)),
    readPlan: vi.fn(() => Promise.resolve({ ...list, id: "c-1", state: "queued" as const })),
    reviewTask: vi.fn(() => Promise.resolve(list)),
    addTask: vi.fn(() => Promise.resolve(list)),
    approveChecklist: vi.fn(() => Promise.resolve(list)),
    followTask: vi.fn(() => Promise.resolve(list)),
  };
}
