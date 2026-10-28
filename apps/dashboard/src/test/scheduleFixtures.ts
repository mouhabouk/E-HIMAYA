import { vi } from "vitest";
import type { Approval, scheduleApi } from "../lib/schedule";
import { SCHEDULE_DETAIL, SCHEDULE_OPTIONS, SCHEDULE_PROGRESS, SCHEDULE_SETTINGS, SCHEDULE_SLOT } from "./scheduleData";

export * from "./scheduleData";

const SETTING = SCHEDULE_SETTINGS.find((s) => s.can_edit) ?? { gouvernorat_code: 21, gouvernorat_name: null, approval: "head" as const, updated_by_name: null, updated_at: null, can_edit: true };

export function fakeScheduleApi(): ReturnType<typeof scheduleApi> {
  return {
    scheduleSlot: vi.fn(() => Promise.resolve(SCHEDULE_SLOT)),
    schedulePeriod: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    createPeriod: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    periodNotes: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    deletePeriod: vi.fn(() => Promise.resolve(undefined)),
    periodStep: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    addScheduleItem: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    updateScheduleItem: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    deleteScheduleItem: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    scheduleItemStatus: vi.fn(() => Promise.resolve(SCHEDULE_DETAIL)),
    scheduleProgress: vi.fn(() => Promise.resolve(SCHEDULE_PROGRESS)),
    scheduleSettings: vi.fn(() => Promise.resolve(SCHEDULE_SETTINGS)),
    saveScheduleSetting: vi.fn((code: number, approval: Approval) => Promise.resolve({ ...SETTING, gouvernorat_code: code, approval })),
    scheduleOptions: vi.fn(() => Promise.resolve(SCHEDULE_OPTIONS)),
  };
}
