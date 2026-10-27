import type { ContactDetail, ContactInbox } from "../lib/contact";
import type { LayerFeature, MapLayer } from "../lib/layers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter, Route, Routes } from "react-router";
import { vi } from "vitest";
import type { AuthService, AuthUser } from "../auth/authService";
import { identityFromClaims } from "../auth/identity";
import { AuthProvider } from "../context/auth";
import { FiltersProvider } from "../context/filters";
import { LiveProvider } from "../context/live";
import { ServicesProvider, type Services } from "../context/services";
import { SoftphoneProvider } from "../context/softphone";
import { createI18n, type Language } from "../i18n";
import type { StaffApi } from "../lib/staffApi";
import { FakeWebSocket } from "./FakeWebSocket";
import { AI_STATUS_READY, fakeJwt } from "./fixtures";
import { fakeOpsApi } from "./opsFixtures";
import { fakeCoastalApi } from "./coastalFixtures";
import { FakeSipEngine, fakePhase7Api } from "./phase7Fixtures";
import { fakePhase8Api } from "./phase8Fixtures";
import { fakePhase9Api } from "./phase9Fixtures";
import { fakePreventionApi } from "./preventionFixtures";
import { FakeStreamSession, fakeStreamsApi } from "./streamFixtures";

export function fakeAuth(claims: Record<string, unknown> | null): AuthService {
  const token = claims ? fakeJwt(claims) : null;
  const user: AuthUser | null = token && claims ? { accessToken: token, identity: identityFromClaims(claims) } : null;
  return {
    getAccessToken: () => token,
    renew: vi.fn(() => Promise.resolve(token)),
    load: vi.fn(() => Promise.resolve(user)),
    signIn: vi.fn(() => Promise.resolve()),
    completeSignIn: vi.fn(() => Promise.resolve("/")),
    signOut: vi.fn(() => Promise.resolve()),
    subscribe: () => () => undefined,
  };
}

export const OPERATOR_CLAIMS = {
  sub: "u-1",
  name: "Sami Operator",
  realm_access: { roles: ["operator", "offline_access"] },
  gouvernorat_code: "61",
};

export const AUDITOR_CLAIMS = {
  sub: "u-9",
  name: "Leila Auditor",
  realm_access: { roles: ["org_auditor"] },
  gouvernorat_code: "61",
};

/** Emergency hub editor (phase B1). */
export function fakeGuideApi() {
  return {
    guide: vi.fn(() => Promise.resolve({ revision: 1, topics: [], icons: [], palette: [] })),
    createTopic: vi.fn(),
    updateTopic: vi.fn(),
    moveTopic: vi.fn(),
    createItem: vi.fn(),
    updateItem: vi.fn(),
    validateItem: vi.fn(),
    moveItem: vi.fn(),
  };
}

/** Contact us inbox (phase B1): empty unless a test gives requests. */
export function fakeContactApi() {
  return {
    contactInbox: vi.fn(() =>
      Promise.resolve<ContactInbox>({
        items: [],
        truncated: false,
        open_by_kind: { access_info: 0, hazard: 0, question: 0, suggestion: 0, app_problem: 0, partnership: 0 },
        overdue: 0,
      }),
    ),
    contactRequest: vi.fn<(id: string) => Promise<ContactDetail>>(),
    contactAct: vi.fn<(id: string, body: unknown) => Promise<ContactDetail>>(),
  };
}

/** Personal safety (phase B2): nothing attached, nothing found, unless a test says so. */
export function fakeSafetyApi() {
  return {
    reportMedical: vi.fn(),
    searchLocationHistory: vi.fn(() => Promise.resolve({ found: false, enabled: false, points: [] })),
  };
}

/** Doctors (phase C1-a): no registration unless a test gives some. */
export function fakeDoctorsApi() {
  return {
    doctors: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    doctor: vi.fn(),
    reviewDoctor: vi.fn(),
    medicalCommittee: vi.fn(() => Promise.resolve({ members: [], max_members: 7 })),
    committeeCandidates: vi.fn(() => Promise.resolve([])),
    appointMember: vi.fn(),
    revokeMember: vi.fn(),
  };
}

/** The settings a phase L1a layer has besides those of B1: published, for every audience, nothing to review. */
export const LAYER_L1A = {
  status: "published",
  audiences: ["citizen", "room", "field", "command", "support"],
  scope: [],
  default_on: true,
  sensitive: false,
  fields: { manager: ["room", "field", "command", "support"] },
  actions: { call: true, directions: true },
  geometry: "point",
  quality: { suggested: 0, duplicates: 0, deleted: 0 },
  deleted_at: null,
  delete_reason: null,
  purge_at: null,
} as const satisfies Partial<MapLayer>;

/** The quality columns of a phase L1a place: an official name, a point. */
export const FEATURE_L1A = {
  geometry: "point",
  name_status: "official",
  suggested_name: null,
  name_confidence: null,
  name_source: null,
  source_url: null,
  snapshot_at: null,
  possible_duplicate: false,
  deleted_at: null,
  delete_reason: null,
} as const satisfies Partial<LayerFeature>;

/** Map data layers (phase B1): no layer unless a test gives some. */
export function fakeLayersApi() {
  return {
    layers: vi.fn(() =>
      Promise.resolve({
        items: [],
        deleted: [],
        can_manage: false,
        icons: [],
        palette: ["#C62828", "#2E7D32"],
        limits: { file_bytes: 10 * 1024 * 1024, rows: 50_000 },
      }),
    ),
    createLayer: vi.fn(),
    updateLayer: vi.fn(),
    previewImport: vi.fn(),
    layerImports: vi.fn(() => Promise.resolve([])),
    applyImport: vi.fn(),
    discardImport: vi.fn(),
    undoImport: vi.fn(),
    layerFeatures: vi.fn(() => Promise.resolve({ items: [], truncated: false })),
    createFeature: vi.fn(),
    updateFeature: vi.fn(),
    exportLayer: vi.fn(),
    layerTemplate: vi.fn(),
    // Phase L1a.
    deleteLayer: vi.fn(),
    restoreLayer: vi.fn(),
    purgeLayer: vi.fn(),
    layerRevisions: vi.fn(() => Promise.resolve([])),
    restoreRevision: vi.fn(),
    reviewQueue: vi.fn(() => Promise.resolve({ items: [], counts: {}, total: 0 })),
    review: vi.fn(),
    deletedFeatures: vi.fn(() => Promise.resolve({ items: [], truncated: false })),
    deleteFeature: vi.fn(),
    restoreFeature: vi.fn(),
    // Phase L1b.
    layerShapes: vi.fn(() => Promise.resolve({ type: "FeatureCollection" as const, features: [], truncated: false })),
    certificateLookup: vi.fn(),
    addStamp: vi.fn(),
    putStampPhoto: vi.fn(),
    stampPhoto: vi.fn(),
  };
}

export function fakeApi(overrides: Partial<StaffApi> = {}): StaffApi {
  return {
    // Phase P5b: ratings of the mobile app (settings page).
    appFeedback: vi.fn(() =>
      Promise.resolve({ days: 90, count: 0, average: null, by_stars: {}, by_build: [], remarks: [] }),
    ),
    kpis: vi.fn(),
    reports: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    report: vi.fn(),
    changeStatus: vi.fn(),
    incidents: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    incident: vi.fn(),
    linkIncident: vi.fn(),
    detachIncident: vi.fn(),
    dismissSuggestion: vi.fn(),
    mergeIncident: vi.fn(),
    aiSettings: vi.fn(),
    saveAiSettings: vi.fn(),
    aiStatus: vi.fn(() => Promise.resolve(AI_STATUS_READY)),
    environment: vi.fn(() => Promise.resolve({ banner: null })),
    orgs: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    org: vi.fn(),
    orgReports: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    orgDocumentVersions: vi.fn(() => Promise.resolve([])),
    orgDocumentDownload: vi.fn(() => Promise.resolve({ url: "https://s3.example/doc?sig=x" })),
    certificatePdf: vi.fn(() => Promise.resolve({ url: "https://s3.example/cert.pdf?sig=x" })),
    orgsMap: vi.fn(() => Promise.resolve({ type: "FeatureCollection" as const, features: [] })),
    orgEvents: vi.fn(() => Promise.resolve([])),
    reviewOrg: vi.fn(),
    certificates: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    reviewCertificate: vi.fn(),
    revokeCertificate: vi.fn(),
    // Phase P4a: teams on duty and the leaders' phones.
    shifts: vi.fn(() => Promise.resolve([])),
    crewDevices: vi.fn(() => Promise.resolve([])),
    revokeCrewDevice: vi.fn(),
    markAlertSeen: vi.fn(),
    reportTemplates: vi.fn(() => Promise.resolve([])),
    createTemplate: vi.fn(),
    editTemplate: vi.fn(),
    approveTemplate: vi.fn(),
    retireTemplate: vi.fn(),
    discardTemplate: vi.fn(),
    ...fakeOpsApi(),
    ...fakeStreamsApi(),
    ...fakePhase7Api(),
    ...fakePhase8Api(),
    ...fakePhase9Api(),
    ...fakePreventionApi(),
    ...fakeLayersApi(),
    ...fakeCoastalApi(),
    ...fakeGuideApi(),
    ...fakeContactApi(),
    ...fakeSafetyApi(),
    ...fakeDoctorsApi(),
    gouvernorats: vi.fn(() =>
      Promise.resolve([
        { code: 11, iso_code: "TN-11", name: "تونس", name_ar: "تونس", name_fr: "Tunis", delegation_count: 21 },
        { code: 61, iso_code: "TN-61", name: "صفاقس", name_ar: "صفاقس", name_fr: "Sfax", delegation_count: 16 },
      ]),
    ),
    ...overrides,
  };
}

export function renderApp(
  ui: ReactNode,
  options: {
    api?: StaffApi;
    auth?: AuthService;
    lang?: Language;
    path?: string;
    route?: string;
    createStreamSession?: Services["createStreamSession"];
    sipEngine?: FakeSipEngine;
  } = {},
) {
  const i18n = createI18n(options.lang ?? "ar");
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const api = options.api ?? fakeApi();
  const auth = options.auth ?? fakeAuth(OPERATOR_CLAIMS);
  const sipEngine = options.sipEngine ?? new FakeSipEngine();
  const utils = render(
    <I18nextProvider i18n={i18n}>
      <ServicesProvider
        services={{
          api,
          auth,
          liveUrl: "ws://test/api/v1/staff/live",
          createSocket: (url) => new FakeWebSocket(url),
          mapStyleUrl: null,
          createStreamSession: options.createStreamSession ?? ((o) => new FakeStreamSession(o)),
          createSipEngine: () => Promise.resolve(sipEngine),
        }}
      >
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <LiveProvider>
              <SoftphoneProvider>
                <FiltersProvider>
                  <MemoryRouter initialEntries={[options.path ?? "/"]}>
                    <Routes>
                      <Route path={options.route ?? "*"} element={ui} />
                    </Routes>
                  </MemoryRouter>
                </FiltersProvider>
              </SoftphoneProvider>
            </LiveProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ServicesProvider>
    </I18nextProvider>,
  );
  return { ...utils, api, auth, i18n, queryClient, sipEngine };
}
