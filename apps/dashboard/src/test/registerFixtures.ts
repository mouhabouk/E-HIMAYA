import { vi } from "vitest";
import type { registerApi } from "../lib/register";
import { first } from "./crisisData";
import type { HazardBody, plansApi } from "../lib/plans";
import { DIRECTIVE_ALL_DETAIL, DISPATCH_PAGE, HAZARD, HAZARDS, PLAN_DETAIL, PLANS, REVISIONS, SEARCH } from "./registerData";

export * from "./registerData";

type RegisterApi = ReturnType<typeof registerApi> & ReturnType<typeof plansApi>;

export function fakeRegisterApi(): RegisterApi {
  return {
    // Phase PL1: plans by hazard.
    hazards: vi.fn(() => Promise.resolve(HAZARDS)),
    saveHazard: vi.fn((key: string, body: HazardBody) => Promise.resolve({ ...HAZARD, ...body, key })),
    plans: vi.fn(() => Promise.resolve(PLANS)),
    documentFileBytes: vi.fn(() => Promise.resolve(new ArrayBuffer(8))),
    registerSearch: vi.fn(() => Promise.resolve(SEARCH)),
    registerDocument: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    createDocument: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    updateDocument: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    deleteDraft: vi.fn(() => Promise.resolve(undefined)),
    repealDocument: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    linkDocument: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    unlinkDocument: vi.fn(() => Promise.resolve(undefined)),
    uploadDocumentFile: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    documentFileUrl: vi.fn(() => Promise.resolve("http://s3.test/x")),
    addRecommendation: vi.fn(() => Promise.resolve(PLAN_DETAIL)),
    recommendationStatus: vi.fn(() => Promise.resolve(first(PLAN_DETAIL.recommendations))),
    documentRevisions: vi.fn(() => Promise.resolve(REVISIONS)),
    dispatches: vi.fn(() => Promise.resolve(DISPATCH_PAGE)),
    dispatch: vi.fn(() => Promise.resolve(DIRECTIVE_ALL_DETAIL)),
    sendDispatch: vi.fn(() => Promise.resolve(DIRECTIVE_ALL_DETAIL)),
    replyDispatch: vi.fn(() => Promise.resolve({ ...DIRECTIVE_ALL_DETAIL, reply_id: "rp-new" })),
    attachToDispatch: vi.fn(() => Promise.resolve(first(DIRECTIVE_ALL_DETAIL.attachments))),
    attachmentUrl: vi.fn(() => Promise.resolve("http://s3.test/y")),
    closeDispatch: vi.fn(() => Promise.resolve(DIRECTIVE_ALL_DETAIL)),
  };
}
