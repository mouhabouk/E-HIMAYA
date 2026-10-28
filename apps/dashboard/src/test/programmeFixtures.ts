import { vi } from "vitest";
import type {
  Programme,
  ProgrammeDetail,
  ProgrammeDiff,
  ProgrammeImport,
  ProgrammePoint,
  Revision,
} from "../lib/programmes";
import type { programmesApi } from "../lib/programmes";

type ProgrammesApi = ReturnType<typeof programmesApi>;

export const PROGRAMME: Programme = {
  id: "p-beach",
  code: "BEACH-2026",
  kind: "beach",
  title: "Plan de surveillance des plages 2026",
  season: "Été 2026",
  valid_from: "2026-06-15",
  valid_to: "2026-09-15",
  status: "approved",
  version: 3,
  source_document: "Note 2026/114",
  declared: { lifeguards_planned: 2154 },
  approved_by_name: "Salma",
  approved_at: "2026-06-01T09:00:00Z",
  cancel_reason: null,
  layer_key: "prog_beach_2026",
  live: true,
  updated_by_name: "Salma",
  updated_at: "2026-07-01T09:00:00Z",
  figures: {
    points: 2,
    unlocated: 1,
    open: 1,
    gouvernorats: 2,
    staff: 30,
    lifeguards_planned: 10,
    lifeguards_deployed: 4,
  },
  can_edit: true,
  can_follow_up: true,
};

export const DRAFT: Programme = {
  ...PROGRAMME,
  id: "p-road",
  code: "ROAD-2026",
  kind: "road",
  title: "Secours routier 2026",
  status: "draft",
  version: 1,
  approved_by_name: null,
  approved_at: null,
  layer_key: null,
  live: false,
  declared: {},
};

export const POINT_OPEN: ProgrammePoint = {
  id: "pt-1",
  ref: "BEACH-2026-001",
  gouvernorat_code: 17,
  place_name: "Plage de la Corniche",
  sub_points: null,
  lat: 37.27,
  lon: 9.87,
  geo_confidence: "confirmed",
  geo_note: null,
  staff_count: 20,
  staff_composition: null,
  supervisors: 1,
  lifeguards_planned: 8,
  lifeguards_deployed: 2,
  equipment: null,
  hours: "08:00-19:00",
  opening_date: null,
  closing_date: null,
  status: "open",
  supervisor_name: "Responsable A",
  supervisor_phone: "+216 70 000 000",
  notes: null,
  updated_at: "2026-07-01T09:00:00Z",
  can_follow_up: true,
};

export const POINT_UNLOCATED: ProgrammePoint = {
  ...POINT_OPEN,
  id: "pt-2",
  ref: "BEACH-2026-002",
  gouvernorat_code: 51,
  place_name: "Plage Boujaafar",
  lat: null,
  lon: null,
  geo_confidence: "unknown",
  lifeguards_planned: 2,
  lifeguards_deployed: 2,
  status: "closed",
  supervisor_name: null,
  supervisor_phone: null,
};

export const DETAIL: ProgrammeDetail = {
  programme: PROGRAMME,
  points: [POINT_OPEN, POINT_UNLOCATED],
  computed: { staff: 30, lifeguards_planned: 10, lifeguards_deployed: 4 },
};

export const REVISIONS: Revision[] = [
  {
    number: 3,
    action: "follow_up",
    reason: "متابعة يومية",
    created_by_name: "Amine",
    created_at: "2026-07-01T09:00:00Z",
    points: 2,
  },
  {
    number: 2,
    action: "approve",
    reason: null,
    created_by_name: "Salma",
    created_at: "2026-06-01T09:00:00Z",
    points: 2,
  },
  {
    number: 1,
    action: "import",
    reason: "chargement",
    created_by_name: null,
    created_at: "2026-05-20T09:00:00Z",
    points: 2,
  },
];

export const PREVIEW: ProgrammeImport = {
  format: "xlsx",
  applied: false,
  programmes: [
    {
      code: "BEACH-2026",
      title: "Plan de surveillance des plages 2026",
      kind: "beach",
      exists: true,
      status: "approved",
      points: 3,
      unlocated: 1,
      computed: { lifeguards_planned: 2127 },
      declared: { lifeguards_planned: 2154 },
      diff: {
        number: 4,
        against: 3,
        programme: {},
        added: ["BEACH-2026-003"],
        removed: [],
        changed: { "BEACH-2026-001": { lifeguards_planned: [8, 10] } },
      },
    },
  ],
  errors: [
    {
      code: "outside_tunisia",
      programme: "BEACH-2026",
      ref: "BEACH-2026-009",
      line: 12,
      value: "48.1,2.3",
    },
  ],
  warnings: [
    {
      code: "total_lifeguards_planned",
      programme: "BEACH-2026",
      value: "2154≠2127",
    },
  ],
};

export function fakeProgrammesApi(): ProgrammesApi {
  return {
    programmes: vi.fn(() => Promise.resolve({ items: [PROGRAMME, DRAFT], can_create: true })),
    programme: vi.fn(() => Promise.resolve(DETAIL)),
    createProgramme: vi.fn(() => Promise.resolve({ ...DETAIL, programme: DRAFT, points: [] })),
    updateProgramme: vi.fn(() => Promise.resolve(DETAIL)),
    deleteProgramme: vi.fn(() => Promise.resolve(undefined)),
    approveProgramme: vi.fn(() => Promise.resolve(DETAIL)),
    cancelProgramme: vi.fn(() =>
      Promise.resolve({
        ...DETAIL,
        programme: {
          ...PROGRAMME,
          status: "cancelled" as const,
          cancel_reason: "annulé",
          live: false,
        },
      }),
    ),
    copyProgramme: vi.fn(() =>
      Promise.resolve({
        ...DETAIL,
        programme: { ...DRAFT, id: "p-copy", code: "BEACH-2027" },
      }),
    ),
    addProgrammePoint: vi.fn(() => Promise.resolve(DETAIL)),
    updateProgrammePoint: vi.fn(() => Promise.resolve(DETAIL)),
    deleteProgrammePoint: vi.fn(() => Promise.resolve(DETAIL)),
    programmeRevisions: vi.fn(() => Promise.resolve(REVISIONS)),
    programmeDiff: vi.fn(() =>
      Promise.resolve<ProgrammeDiff>({
        number: 3,
        against: 2,
        programme: {},
        added: [],
        removed: [],
        changed: { "BEACH-2026-001": { lifeguards_deployed: [0, 2] } },
      }),
    ),
    restoreProgramme: vi.fn(() => Promise.resolve(DETAIL)),
    importProgrammes: vi.fn((_file: File, apply: boolean) =>
      Promise.resolve(apply ? { ...PREVIEW, errors: [], applied: true } : PREVIEW),
    ),
  };
}
