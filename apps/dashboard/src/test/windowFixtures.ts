import { vi } from "vitest";
import type { windowApi } from "../lib/window";
import {
  WINDOW_ACCESS_FULL,
  WINDOW_COMPARE,
  WINDOW_DELEGATES,
  WINDOW_DELEGATION,
  WINDOW_NOW,
  WINDOW_SAVED,
  WINDOW_SEARCH,
  WINDOW_SUMMARY,
  WINDOW_SYNONYMS,
} from "./windowData";

const [SAVED] = WINDOW_SAVED as [(typeof WINDOW_SAVED)[number], ...typeof WINDOW_SAVED];
const [SYNONYM] = WINDOW_SYNONYMS as [(typeof WINDOW_SYNONYMS)[number], ...typeof WINDOW_SYNONYMS];

export function fakeWindowApi(): ReturnType<typeof windowApi> {
  return {
    windowAccess: vi.fn(() => Promise.resolve(WINDOW_ACCESS_FULL)),
    windowNow: vi.fn(() => Promise.resolve(WINDOW_NOW)),
    windowSearch: vi.fn(() => Promise.resolve(WINDOW_SEARCH)),
    windowCompare: vi.fn(() => Promise.resolve(WINDOW_COMPARE)),
    windowExport: vi.fn(() => Promise.resolve({ blob: new Blob(["x"]), filename: "window.pdf" })),
    windowSummary: vi.fn(() => Promise.resolve(WINDOW_SUMMARY)),
    savedSearches: vi.fn(() => Promise.resolve(WINDOW_SAVED)),
    saveSearch: vi.fn(() => Promise.resolve(SAVED)),
    deleteSearch: vi.fn(() => Promise.resolve(undefined)),
    synonyms: vi.fn(() => Promise.resolve(WINDOW_SYNONYMS)),
    putSynonym: vi.fn(() => Promise.resolve(SYNONYM)),
    deleteSynonym: vi.fn(() => Promise.resolve(undefined)),
    delegates: vi.fn(() => Promise.resolve(WINDOW_DELEGATES)),
    delegations: vi.fn(() => Promise.resolve([WINDOW_DELEGATION])),
    grantDelegation: vi.fn(() => Promise.resolve(WINDOW_DELEGATION)),
    addDelegationEvents: vi.fn(() => Promise.resolve(WINDOW_DELEGATION)),
    revokeDelegation: vi.fn(() => Promise.resolve({ ...WINDOW_DELEGATION, state: "revoked" as const })),
  };
}
