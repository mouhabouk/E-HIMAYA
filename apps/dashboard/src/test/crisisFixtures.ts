import { vi } from "vitest";
import type { crisisApi } from "../lib/crisis";
import { DIRECTIVES, first, JENDOUBA_AXIS, NABEUL_AXIS, NABEUL_DETAIL, overview, REQUEST, SITREPS, SOUSSE_AXIS, SUGGESTIONS } from "./crisisData";

export * from "./crisisData";

type CrisisApi = ReturnType<typeof crisisApi>;

export function fakeCrisisApi(): CrisisApi {
  return {
    crisisAxes: vi.fn((status: "open" | "closed") => Promise.resolve(status === "open" ? [NABEUL_AXIS, JENDOUBA_AXIS, SOUSSE_AXIS] : [])),
    crisisAxis: vi.fn(() => Promise.resolve(NABEUL_DETAIL)),
    disasterMap: vi.fn(() =>
      Promise.resolve({
        figures: NABEUL_AXIS.figures,
        areas: [{ id: NABEUL_AXIS.id, level: NABEUL_AXIS.level, area: NABEUL_AXIS.area }],
        incidents: NABEUL_DETAIL.incidents,
        shelters: NABEUL_DETAIL.shelters,
        evacuations: NABEUL_DETAIL.evacuations,
      }),
    ),
    openAxis: vi.fn(() => Promise.resolve(NABEUL_AXIS)),
    updateAxis: vi.fn(() => Promise.resolve(NABEUL_AXIS)),
    escalateAxis: vi.fn(() => Promise.resolve(NABEUL_AXIS)),
    closeAxis: vi.fn(() => Promise.resolve(NABEUL_AXIS)),
    axisSuggestions: vi.fn(() => Promise.resolve(SUGGESTIONS)),
    attachAxisIncident: vi.fn(() => Promise.resolve(undefined)),
    detachAxisIncident: vi.fn(() => Promise.resolve(undefined)),
    dismissAxisSuggestion: vi.fn(() => Promise.resolve(undefined)),
    addShelter: vi.fn(() => Promise.resolve(first(NABEUL_DETAIL.shelters))),
    updateShelter: vi.fn(() => Promise.resolve(first(NABEUL_DETAIL.shelters))),
    addEvacuation: vi.fn(() => Promise.resolve(first(NABEUL_DETAIL.evacuations))),
    updateEvacuation: vi.fn(() => Promise.resolve(first(NABEUL_DETAIL.evacuations))),
    raiseNeed: vi.fn(() => Promise.resolve(first(NABEUL_DETAIL.needs))),
    needMet: vi.fn(() => Promise.resolve(first(NABEUL_DETAIL.needs))),
    issueAxisDirective: vi.fn(() => Promise.resolve(first(DIRECTIVES))),
    axisDirectiveStatus: vi.fn(() => Promise.resolve(first(DIRECTIVES))),
    draftSitrep: vi.fn(() => Promise.resolve(first(SITREPS))),
    sendSitrep: vi.fn(() => Promise.resolve(first(SITREPS))),
    declarationRequests: vi.fn(() => Promise.resolve([REQUEST])),
    requestDeclaration: vi.fn(() => Promise.resolve(REQUEST)),
    decideRequest: vi.fn(() => Promise.resolve({ ...REQUEST, status: "accepted" as const, axis_id: "ax-nabeul" })),
    crisisCommand: vi.fn(() => Promise.resolve(overview("minister"))),
    crisisBoundaries: vi.fn(() => Promise.resolve({ type: "FeatureCollection" as const, features: [] })),
  };
}
