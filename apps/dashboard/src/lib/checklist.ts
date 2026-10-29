import type { ApiClient } from "./api";

/**
 * The task list read from an intervention plan (L5, docs/phase-l/design-l5.md §2.3, AI2): the local model suggests the
 * tasks of the plan (action, who, with what, page, and the passage it rests on), the room manager accepts, edits or
 * deletes each one and approves the list, then the rooms follow it task by task. The same list belongs to a crisis
 * axis or to a dry run, where it is the expected answer.
 */

export type ChecklistState = "queued" | "reading" | "review" | "approved" | "failed";
export type TaskReview = "suggested" | "accepted" | "edited" | "deleted" | "added";
export type TaskStatus = "todo" | "doing" | "done" | "not_applicable";

export const TASK_STATUSES: readonly TaskStatus[] = ["todo", "doing", "done", "not_applicable"];

export interface PlanRef {
  id: string;
  number: string;
  title: string;
}

export interface PlanTask {
  id: string;
  position: number;
  action: string;
  owner: string;
  resource: string;
  page: number | null;
  quote: string;
  quote_found: boolean | null;
  origin: "ai" | "manual";
  review: TaskReview;
  suggested: Record<string, string | number | null> | null;
  status: TaskStatus;
  note: string;
  status_by_name: string | null;
  status_at: string | null;
}

export interface ChecklistCounts {
  suggested: number;
  kept: number;
  deleted: number;
  todo: number;
  doing: number;
  done: number;
  not_applicable: number;
}

export interface Checklist {
  id: string | null;
  state: ChecklistState | null;
  error: string | null;
  plan: PlanRef | null;
  plans: PlanRef[];
  model: string | null;
  pages: number | null;
  pages_read: number | null;
  requested_by_name: string | null;
  requested_at: string | null;
  read_at: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  version: number;
  tasks: PlanTask[];
  counts: ChecklistCounts;
  reading_available: boolean;
  can_review: boolean;
  can_follow: boolean;
}

export interface TaskIn {
  action: string;
  owner: string;
  resource: string;
  page: number | null;
}

/** Where a list lives: a crisis axis or a dry run. */
export type ChecklistOwner = { kind: "axis"; id: string } | { kind: "drill"; id: string };

const enc = encodeURIComponent;

function base(owner: ChecklistOwner): string {
  return owner.kind === "axis"
    ? `/api/v1/staff/crisis/axes/${enc(owner.id)}/checklist`
    : `/api/v1/staff/drills/${enc(owner.id)}/checklist`;
}

export const checklistKeys = {
  one: (owner: ChecklistOwner) => ["checklist", owner.kind, owner.id] as const,
};

/** While the model reads, the list is asked again at this pace. */
export const READING_POLL_MS = 5000;
export const MAX_ACTION = 400;
export const MAX_SHORT = 160;
export const MAX_NOTE = 500;

export function isReading(list: Checklist | undefined): boolean {
  return list?.state === "queued" || list?.state === "reading";
}

/** The tasks kept after review, as followed. */
export function kept(list: Checklist): PlanTask[] {
  return list.tasks.filter((x) => x.review !== "suggested" && x.review !== "deleted");
}

export function checklistApi(api: ApiClient) {
  return {
    checklist: (owner: ChecklistOwner, signal?: AbortSignal) => api.request<Checklist>(base(owner), { signal }),
    readPlan: (owner: ChecklistOwner, documentId: string, version: number | null) =>
      api.request<Checklist>(`${base(owner)}/read`, { method: "POST", body: { document_id: documentId, version } }),
    reviewTask: (owner: ChecklistOwner, taskId: string, decision: "accept" | "edit" | "delete", task?: TaskIn) =>
      api.request<Checklist>(`${base(owner)}/tasks/${enc(taskId)}/review`, {
        method: "POST",
        body: task ? { decision, task } : { decision },
      }),
    addTask: (owner: ChecklistOwner, task: TaskIn) =>
      api.request<Checklist>(`${base(owner)}/tasks`, { method: "POST", body: task }),
    approveChecklist: (owner: ChecklistOwner, version: number) =>
      api.request<Checklist>(`${base(owner)}/approve`, { method: "POST", body: { version } }),
    followTask: (owner: ChecklistOwner, taskId: string, status: TaskStatus, note: string) =>
      api.request<Checklist>(`${base(owner)}/tasks/${enc(taskId)}/status`, { method: "POST", body: { status, note } }),
  };
}
