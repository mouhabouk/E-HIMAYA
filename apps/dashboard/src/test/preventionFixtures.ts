import { vi } from "vitest";
import type { preventionApi, Reservation, StaffVisit } from "../lib/preventionApi";
import { makeCertificate } from "./fixtures";

type PreventionApi = ReturnType<typeof preventionApi>;

export function makeVisit(overrides: Partial<StaffVisit> = {}): StaffVisit {
  return {
    id: "v-1",
    org_id: "o-1",
    origin: "request",
    status: "requested",
    request_note: "Avant la saison estivale",
    requested_by_name: "Sami Ben Ali",
    requested_at: "2026-10-20T08:00:00Z",
    scheduled_on: null,
    inspector_name: null,
    inspected_on: null,
    attendees: null,
    comparison: null,
    decision: null,
    decision_reason: null,
    decided_by_name: null,
    decided_at: null,
    certificate: null,
    reservations: [],
    has_report: false,
    cancel_reason: null,
    cancelled_at: null,
    created_at: "2026-10-20T08:00:00Z",
    org_name: "Société Chimique du Sud",
    org_kind: "industrial",
    org_status: "active",
    gouvernorat_code: 61,
    checklist: [
      { key: "building.capacity", section: "building", declared: 300 },
      { key: "hazmat.0", section: "hazmat", declared: "Chlore (UN 1017): 200 kg" },
      { key: "equipment.extinguisher", section: "equipment", declared: 12 },
      { key: "site.exits", section: "site", declared: null },
    ],
    ...overrides,
  };
}

export function makeReservation(overrides: Partial<Reservation> = {}): Reservation {
  return {
    id: "r-1",
    visit_id: "v-1",
    item_key: "site.exits",
    text: "Dégager l'issue B",
    due_on: "2026-11-25",
    state: "open",
    response_note: null,
    responded_by_name: null,
    responded_at: null,
    lifted_by_name: null,
    lift_note: null,
    lifted_at: null,
    ...overrides,
  };
}

export function inspectedVisit(overrides: Partial<StaffVisit> = {}): StaffVisit {
  return makeVisit({
    status: "inspected",
    scheduled_on: "2026-10-24",
    inspector_name: "Cdt Ben Salah",
    inspected_on: "2026-10-24",
    attendees: "Directeur",
    has_report: true,
    comparison: {
      items: [
        { key: "building.capacity", section: "building", declared: 300, result: "nonconform", observed: "420", note: null },
        { key: "hazmat.0", section: "hazmat", declared: "Chlore (UN 1017): 200 kg", result: "conform", observed: null, note: null },
        { key: "equipment.extinguisher", section: "equipment", declared: 12, result: "conform", observed: null, note: null },
        { key: "site.exits", section: "site", declared: null, result: "nonconform", observed: null, note: "Issue B encombrée" },
      ],
      conform: 2,
      nonconform: 2,
      not_checked: 0,
      missing: [],
      changes: [{ section: "building", field: "capacity", certified: 300, current: 420 }],
      suggested: "approved_with_reservations",
    },
    ...overrides,
  });
}

export function decidedVisit(overrides: Partial<StaffVisit> = {}): StaffVisit {
  return inspectedVisit({
    status: "decided",
    decision: "approved_with_reservations",
    decided_by_name: "Leila Auditor",
    decided_at: "2026-10-25T10:00:00Z",
    checklist: [],
    certificate: makeCertificate({
      id: "c-9",
      kind: "prevention",
      code: "EHP-26-61-000009",
      status: "approved",
      reviewed_at: "2026-10-25T10:00:00Z",
      valid_until: "2027-10-25",
      verify_url: "http://localhost:5174/verify/EHP-26-61-000009",
    }),
    reservations: [makeReservation(), makeReservation({ id: "r-2", item_key: null, text: "Mettre à jour la capacité", state: "overdue", due_on: "2026-10-20" })],
    ...overrides,
  });
}

export function fakePreventionApi(): PreventionApi {
  return {
    preventionVisits: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    preventionVisit: vi.fn(() => Promise.resolve(makeVisit())),
    orgPreventionVisits: vi.fn(() => Promise.resolve([])),
    scheduleNewVisit: vi.fn(),
    scheduleVisit: vi.fn(),
    recordInspection: vi.fn(),
    decideVisit: vi.fn(),
    cancelVisit: vi.fn(),
    visitReport: vi.fn(() => Promise.resolve({ url: "https://s3.example/report.pdf?sig=x" })),
    liftReservation: vi.fn(),
  };
}
