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
import { FakeSipEngine, fakePhase7Api } from "./phase7Fixtures";
import { fakePhase8Api } from "./phase8Fixtures";
import { fakePhase9Api } from "./phase9Fixtures";
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

export function fakeApi(overrides: Partial<StaffApi> = {}): StaffApi {
  return {
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
    orgs: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    org: vi.fn(),
    orgReports: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    orgDocumentVersions: vi.fn(() => Promise.resolve([])),
    orgDocumentDownload: vi.fn(() => Promise.resolve({ url: "https://s3.example/doc?sig=x" })),
    certificatePdf: vi.fn(() => Promise.resolve({ url: "https://s3.example/cert.pdf?sig=x" })),
    orgsMap: vi.fn(() => Promise.resolve({ type: "FeatureCollection" as const, features: [] })),
    reviewOrg: vi.fn(),
    certificates: vi.fn(() => Promise.resolve({ items: [], next_cursor: null })),
    reviewCertificate: vi.fn(),
    ...fakeOpsApi(),
    ...fakeStreamsApi(),
    ...fakePhase7Api(),
    ...fakePhase8Api(),
    ...fakePhase9Api(),
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
