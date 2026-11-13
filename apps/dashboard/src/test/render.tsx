import type { ContactDetail, ContactInbox } from "../lib/contact";
import type { LayerFeature, MapLayer } from "../lib/layers";
import type { RefItem, RefLists } from "../lib/references";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter, Route, Routes } from "react-router";
import { vi } from "vitest";
import { ApiError } from "../lib/api";
import { fakeFeaturesApi } from "./featuresFixtures";
import { fakeWindowApi } from "./windowFixtures";
import { fakeDrillApi } from "./drillFixtures";
import { fakeSensorsApi } from "./sensorsFixtures";
import { fakeTowersApi } from "./towersFixtures";
import { fakeChecklistApi } from "./checklistFixtures";
import { fakeModelCardsApi } from "./modelCardsFixtures";
import { fakeLearningApi } from "./learningFixtures";
import { fakeDronesApi } from "./dronesFixtures";
import { fakeInspectionsApi } from "./inspectionsFixtures";
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
import { fakeProgrammesApi } from "./programmeFixtures";
import { fakeCrisisApi } from "./crisisFixtures";
import { fakeBasemapApi } from "./basemapFixtures";
import { fakeInventoryApi } from "./inventoryFixtures";
import { fakeRegisterApi } from "./registerFixtures";
import { fakeScheduleApi } from "./scheduleFixtures";
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
    layerPlaces: vi.fn(() => Promise.resolve({ items: [], truncated: false })),
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
    // Phase UI-3b.
    createLayerGroup: vi.fn(),
    updateLayerGroup: vi.fn(),
    deleteLayerGroup: vi.fn(),
    certificateLookup: vi.fn(),
    addStamp: vi.fn(),
    putStampPhoto: vi.fn(),
    stampPhoto: vi.fn(),
  };
}

const refItem = (id: string, label_ar: string, unit: RefItem["unit"] = null, code: string | null = null): RefItem => ({
  id,
  code,
  label_ar,
  label_fr: null,
  unit,
  sort: 10,
  active: true,
  updated_by_name: null,
  updated_at: "2026-11-01T08:00:00Z",
});

/** A part of the Office's reference lists: the places of the damages and the crops lost. */
export const REFERENCES: RefLists = {
  can_manage: false,
  lists: [
    { key: "forest_place", name_ar: "أماكن الحرائق الغابية", name_fr: "Lieux forestiers", name_en: "Forest places", items: [refItem("f1", "غابة", null, "1")] },
    { key: "agri_place", name_ar: "أماكن الأضرار الفلاحية", name_fr: "Lieux agricoles", name_en: "Farm places", items: [refItem("a1", "حقل", null, "2")] },
    {
      key: "crop_loss",
      name_ar: "الخسائر الفلاحية",
      name_fr: "Pertes agricoles",
      name_en: "Crop losses",
      items: [refItem("c1", "قمح", "ha", "1"), refItem("c5", "قرط", "bale", "5")],
    },
  ],
};

export function fakeApi(overrides: Partial<StaffApi> = {}): StaffApi {
  return {
    // Phase P5b: ratings of the mobile app (settings page).
    appFeedback: vi.fn(() =>
      Promise.resolve({ days: 90, count: 0, average: null, by_stars: {}, by_build: [], remarks: [] }),
    ),
    kpis: vi.fn(),
    // The four boards of the menu of 20 systems (2026-11-13).
    visionOverview: vi.fn(() =>
      Promise.resolve({
        hours: 24,
        counts: { fire: 0, smoke: 0, person: 0 },
        confirmed: 0,
        danger: { high: 0, medium: 0, low: 0 },
        watching: 0,
        alert_confidence: 0.6,
        items: [],
      }),
    ),
    forecastOverview: vi.fn(() =>
      Promise.resolve({ hours: 48, from: "2026-11-13T00:00:00Z", simulated: false, gouvernorats: [], runs: [] }),
    ),
    citizensOverview: vi.fn(() => Promise.resolve({ days: 90, national: {}, gouvernorats: [] })),
    adminBoardOverview: vi.fn(),
    // OS3: the fleet, the live coverage and the access profiles.
    fleetVehicles: vi.fn(() => Promise.resolve({ items: [], can_edit: false, can_set_state: false, can_maintain: false })),
    setVehicleState: vi.fn(),
    startMaintenance: vi.fn(),
    endMaintenance: vi.fn(),
    retireVehicle: vi.fn(),
    vehicleEvents: vi.fn(() => Promise.resolve({ items: [] })),
    coverage: vi.fn(),
    featureProfiles: vi.fn(() => Promise.resolve([])),
    saveFeatureProfile: vi.fn(),
    deleteFeatureProfile: vi.fn(),
    assignFeatureProfile: vi.fn(),
    profileAssignments: vi.fn(() => Promise.resolve([])),
    revokeProfileAssignment: vi.fn(),
    // Phase H1: personnel management.
    personnelUnits: vi.fn(() => Promise.resolve([])),
    personnelAgents: vi.fn(() => Promise.resolve({ on: "2026-11-08", items: [], can_edit: false })),
    createPersonnelAgent: vi.fn(),
    updatePersonnelAgent: vi.fn(),
    agentFile: vi.fn(),
    addPersonnelEvent: vi.fn(),
    cancelPersonnelEvent: vi.fn(),
    absences: vi.fn(() => Promise.resolve({ start: "2026-11-01", end: "2026-11-30", items: [], can_edit: false })),
    createAbsence: vi.fn(),
    updateAbsence: vi.fn(),
    cancelAbsence: vi.fn(),
    strength: vi.fn(),
    reports: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    report: vi.fn(),
    // Phase N: a report entered by a room.
    enterReport: vi.fn(),
    // Phase S: SNACR and the strategies menu.
    snacr: vi.fn(),
    snacrAnalysis: vi.fn(),
    importSnacr: vi.fn(),
    simulateSnacr: vi.fn(),
    liveSnacr: vi.fn(),
    deleteSnacrYear: vi.fn(),
    snacrUnmatched: vi.fn(() => Promise.resolve([])),
    snacrAliases: vi.fn(() => Promise.resolve([])),
    addSnacrAlias: vi.fn(),
    specialRisks: vi.fn(() => Promise.resolve([])),
    saveSpecialRisk: vi.fn(),
    deleteSpecialRisk: vi.fn(),
    snacrPlans: vi.fn(() => Promise.resolve([])),
    snacrPlan: vi.fn(),
    createSnacrPlan: vi.fn(),
    approveSnacrPlan: vi.fn(),
    snacrPlanPdf: vi.fn(),
    snacrStudies: vi.fn(() => Promise.resolve([])),
    snacrStudy: vi.fn(),
    launchSnacrStudy: vi.fn(),
    snacrStudyExport: vi.fn(),
    // Phase 2: the damage tables and the reference lists.
    importSnacrDamages: vi.fn(),
    snacrDamages: vi.fn(() => Promise.resolve([])),
    references: vi.fn(() => Promise.resolve(REFERENCES)),
    addReference: vi.fn(),
    changeReference: vi.fn(),
    referencesExport: vi.fn(),
    strategyItems: vi.fn(() => Promise.resolve({ items: [], can_manage: false })),
    strategyItem: vi.fn(),
    saveStrategyItem: vi.fn(),
    deleteStrategyItem: vi.fn(),
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
    // Phase F: the staff app's agents and the mission point picked on the map.
    fieldAgents: vi.fn(() => Promise.resolve([])),
    createFieldAgent: vi.fn(),
    updateFieldAgent: vi.fn(),
    renewFieldCode: vi.fn(),
    disableFieldAgent: vi.fn(),
    setAssignmentTarget: vi.fn(),
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
    ...fakeProgrammesApi(),
    ...fakeCrisisApi(),
    ...fakeRegisterApi(),
    ...fakeScheduleApi(),
    ...fakeInventoryApi(),
    ...fakeBasemapApi(),
    ...fakeGuideApi(),
    ...fakeContactApi(),
    ...fakeSafetyApi(),
    ...fakeDoctorsApi(),
    ...fakeFeaturesApi(),
    ...fakeWindowApi(),
    ...fakeDrillApi(),
    ...fakeSensorsApi(),
    ...fakeTowersApi(),
    ...fakeDronesApi(),
    // Phase I2: the periodic inspections.
    ...fakeInspectionsApi(),
    ...fakeChecklistApi(),
    ...fakeModelCardsApi(),
    ...fakeLearningApi(),
    anomalies: vi.fn(() => Promise.resolve({ enabled: true, items: [] })),
    boundaries: vi.fn(() => Promise.resolve({ type: "FeatureCollection" as const, features: [] })),
    delegationCounts: vi.fn(() => Promise.resolve([])),
    places: vi.fn(() => Promise.resolve([])),
    createPlace: vi.fn((body: { name: string; kind: "critical" | "important" | "other"; note: string | null; lat: number; lon: number }) =>
      Promise.resolve({
        id: "place-1",
        ...body,
        gouvernorat_code: 61,
        delegation_id: 6114,
        created_by_name: null,
        created_at: "2026-10-30T00:00:00Z",
        updated_by_name: null,
        updated_at: "2026-10-30T00:00:00Z",
      }),
    ),
    updatePlace: vi.fn(() => Promise.reject(new Error("not used"))),
    deletePlace: vi.fn(() => Promise.resolve(undefined)),
    gouvernorats: vi.fn(() =>
      Promise.resolve([
        { code: 11, iso_code: "TN-11", name: "تونس", name_ar: "تونس", name_fr: "Tunis", delegation_count: 21 },
        { code: 61, iso_code: "TN-61", name: "صفاقس", name_ar: "صفاقس", name_fr: "Sfax", delegation_count: 16 },
      ]),
    ),
    // Phase H5: system logs and the change journal.
    systemLogs: vi.fn(() => Promise.resolve({ items: [], query: "" })),
    systemLogSummary: vi.fn(() => Promise.resolve({ hours: 24, services: [] })),
    changes: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    changeSummary: vi.fn(() =>
      Promise.resolve({ hours: 24, total: 0, by_op: [], by_schema: [], by_actor_kind: [], tables: [] }),
    ),
    // The SQL window (docs/sql/console.md).
    sqlConnections: vi.fn(() => Promise.resolve([])),
    sqlTestConnection: vi.fn(),
    sqlSchema: vi.fn(() => Promise.resolve([])),
    sqlExamples: vi.fn(() => Promise.resolve([])),
    sqlQuery: vi.fn(),
    sqlExport: vi.fn(),
    sqlHistory: vi.fn(() => Promise.resolve([])),
    sqlEditHistory: vi.fn(),
    sqlDeleteHistory: vi.fn(),
    repoMap: vi.fn(() => Promise.resolve({ nodes: [], edges: [], routes: 0, generated_at: "2026-11-09T22:00:00Z" })),
    // OS2: guided call-taking cards.
    callCards: vi.fn(() => Promise.resolve({ cards: [] })),
    createCardDraft: vi.fn(),
    updateCardDraft: vi.fn(),
    discardCardDraft: vi.fn(),
    validateCardMedical: vi.fn(),
    approveCard: vi.fn(),
    reportCallCard: vi.fn(() => Promise.reject(new ApiError(404, "no_call_card"))),
    // OS8: address warnings.
    awCategories: vi.fn(() => Promise.resolve([])),
    awSaveCategory: vi.fn(),
    awMarkers: vi.fn(() =>
      Promise.resolve({ items: [], counts: { active: 0, pending: 0, review_due: 0, personal: 0 } }),
    ),
    awCreate: vi.fn(),
    awDecide: vi.fn(),
    awImportOrgs: vi.fn(() => Promise.resolve({ created: 0 })),
    awReveals: vi.fn(() => Promise.resolve([])),
    awIncident: vi.fn((id: string) =>
      Promise.resolve({ incident_id: id, incident_kind: "fire", location: null, items: [], unread: 0 }),
    ),
    awAck: vi.fn(),
    awReveal: vi.fn(),
    // OS20: informing the partner bodies by phone.
    liaisonBodies: vi.fn(() => Promise.resolve([])),
    liaisonBody: vi.fn(),
    liaisonCreateBody: vi.fn(),
    liaisonPatchBody: vi.fn(),
    liaisonArchiveBody: vi.fn(),
    liaisonAddOfficial: vi.fn(),
    liaisonArchiveOfficial: vi.fn(),
    liaisonIncident: vi.fn((id: string) =>
      Promise.resolve({ incident_id: id, gouvernorat_code: null, level: null, parties: [], suggestions: [] }),
    ),
    liaisonSetLevel: vi.fn(),
    liaisonPicker: vi.fn(() => Promise.resolve({ suggestions: [], used_before: [], history: [] })),
    liaisonAddParties: vi.fn(),
    liaisonRemoveParty: vi.fn(),
    liaisonAddCall: vi.fn(),
    liaisonFollowUps: vi.fn(() => Promise.resolve([])),
    liaisonFollowUpDone: vi.fn(),
    liaisonCalls: vi.fn(() => Promise.resolve([])),
    liaisonHistory: vi.fn(() => Promise.resolve([])),
    // OS7: crew accountability in danger zones.
    parIncidents: vi.fn(() => Promise.resolve([])),
    parBoard: vi.fn(),
    parSetting: vi.fn(() => Promise.reject(new ApiError(404, "not_found", "Not Found"))),
    parSaveSetting: vi.fn(),
    parSetNext: vi.fn(),
    parClearNext: vi.fn(),
    parPause: vi.fn(),
    parResume: vi.fn(),
    parCheckAll: vi.fn(),
    parTeam: vi.fn(),
    parMissing: vi.fn(),
    parClose: vi.fn(),
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
