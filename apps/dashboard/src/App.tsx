import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { i18n } from "i18next";
import { useState } from "react";
import { I18nextProvider } from "react-i18next";
import { BrowserRouter, Route, Routes } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
import { AuthProvider } from "./context/auth";
import { FiltersProvider } from "./context/filters";
import { LiveProvider } from "./context/live";
import { ServicesProvider, type Services } from "./context/services";
import { isApiError } from "./lib/api";
import { AiSettingsPage } from "./pages/AiSettingsPage";
import { CallbackPage } from "./pages/CallbackPage";
import { HomePage } from "./pages/HomePage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { MapPage } from "./pages/MapPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { ReportsPage } from "./pages/ReportsPage";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Client errors (4xx) are not transient: do not hammer the API with retries.
        retry: (count, error) => !(isApiError(error) && error.status >= 400 && error.status < 500) && count < 2,
      },
    },
  });
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/callback" element={<CallbackPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="reports/:id" element={<ReportDetailPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="incidents/:id" element={<IncidentDetailPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="settings/ai" element={<AiSettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function App({ services, i18n }: { services: Services; i18n: i18n }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <I18nextProvider i18n={i18n}>
      <ServicesProvider services={services}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <LiveProvider>
              <FiltersProvider>
                <BrowserRouter>
                  <AppRoutes />
                </BrowserRouter>
              </FiltersProvider>
            </LiveProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ServicesProvider>
    </I18nextProvider>
  );
}
