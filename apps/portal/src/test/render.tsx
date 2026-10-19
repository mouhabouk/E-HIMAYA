import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter, Route, Routes } from "react-router";
import { vi } from "vitest";
import type { AuthService, AuthUser } from "../auth/authService";
import { identityFromClaims } from "../auth/identity";
import { AuthProvider } from "../context/auth";
import { ServicesProvider } from "../context/services";
import { createI18n, type Language } from "../i18n";
import { createApiClient } from "../lib/api";
import { portalApi } from "../lib/portalApi";
import { mockFetch, type Handler } from "./fetch";
import { GOUVERNORATS, USER_CLAIMS, fakeJwt } from "./fixtures";

export const API = "http://api.test";
export const TUS = "http://tus.test/api/v1/uploads/";

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

/**
 * Renders a screen with the real API client over a mocked fetch (routes "METHOD /path" → reply),
 * a fake auth service, and a memory router.
 */
export function renderApp(
  ui: ReactNode,
  options: {
    routes?: Record<string, Handler | Handler[]>;
    auth?: AuthService;
    lang?: Language;
    path?: string;
    route?: string;
    /** Extra nested routes rendered under `route` (for workspace tabs). */
    children?: ReactNode;
  } = {},
) {
  const i18n = createI18n(options.lang ?? "ar");
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const fetcher = mockFetch({ "GET /api/v1/geo/gouvernorats": { body: GOUVERNORATS }, ...options.routes });
  const auth = options.auth ?? fakeAuth(USER_CLAIMS);
  const api = portalApi(createApiClient(API, auth, fetcher.fetch));
  const utils = render(
    <I18nextProvider i18n={i18n}>
      <ServicesProvider services={{ api, auth, tusEndpoint: TUS, mapStyleUrl: null, fetchImpl: fetcher.fetch }}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <MemoryRouter initialEntries={[options.path ?? "/"]}>
              <Routes>
                <Route path={options.route ?? "*"} element={ui}>
                  {options.children}
                </Route>
              </Routes>
            </MemoryRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ServicesProvider>
    </I18nextProvider>,
  );
  return { ...utils, auth, i18n, queryClient, fetch: fetcher.fetch, calls: fetcher.calls };
}
