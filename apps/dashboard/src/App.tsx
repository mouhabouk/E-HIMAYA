import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { i18n } from "i18next";
import { useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
import { AuthProvider, useAuth } from "./context/auth";
import { FiltersProvider } from "./context/filters";
import { LiveProvider } from "./context/live";
import { ServicesProvider, type Services } from "./context/services";
import { isApiError } from "./lib/api";
import {
  canEditTips,
  canMonitorPerformance,
  canReadOrgs,
  canReadResources,
  canUseNotifications,
  hasReadAccess,
  isCommittee,
  landingPath,
} from "./lib/roles";
import { AiSettingsPage } from "./pages/AiSettingsPage";
import { CallbackPage } from "./pages/CallbackPage";
import { CertificatesPage } from "./pages/CertificatesPage";
import { CommitteePage } from "./pages/CommitteePage";
import { HomePage } from "./pages/HomePage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { MapPage } from "./pages/MapPage";
import { NoAccessPage } from "./pages/NoAccessPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { NotificationEditorPage } from "./pages/NotificationEditorPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { OrgDetailPage } from "./pages/OrgDetailPage";
import { OrgsPage } from "./pages/OrgsPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ResourcesPage } from "./pages/ResourcesPage";
import { SafetyTipsPage } from "./pages/SafetyTipsPage";
import { VolunteerDetailPage } from "./pages/VolunteerDetailPage";
import { VolunteersPage } from "./pages/VolunteersPage";

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

/** Screens of one area (reports or institutions) for the roles that can use it; the API checks again. */
export function Gate({ allow, children }: { allow: (roles: readonly string[]) => boolean; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !allow(user.identity.roles)) return <NoAccessPage reason="noRole" embedded />;
  return children;
}

/** The KPIs need a report read role; other staff start on the first area their roles open. */
function Home() {
  const { user } = useAuth();
  if (user && !hasReadAccess(user.identity.roles)) {
    const path = landingPath(user.identity.roles);
    if (path !== "/") return <Navigate to={path} replace />;
  }
  return <HomePage />;
}

const reports = (page: ReactNode) => <Gate allow={hasReadAccess}>{page}</Gate>;
const orgs = (page: ReactNode) => <Gate allow={canReadOrgs}>{page}</Gate>;
const resources = (page: ReactNode) => <Gate allow={canReadResources}>{page}</Gate>;
const notifications = (page: ReactNode) => <Gate allow={canUseNotifications}>{page}</Gate>;
const tips = (page: ReactNode) => <Gate allow={canEditTips}>{page}</Gate>;
const committee = (page: ReactNode) => (
  <Gate allow={(roles) => isCommittee(roles) || canMonitorPerformance(roles)}>{page}</Gate>
);

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
        <Route index element={<Home />} />
        <Route path="reports" element={reports(<ReportsPage />)} />
        <Route path="reports/:id" element={reports(<ReportDetailPage />)} />
        <Route path="incidents" element={reports(<IncidentsPage />)} />
        <Route path="incidents/:id" element={reports(<IncidentDetailPage />)} />
        <Route path="map" element={reports(<MapPage />)} />
        <Route path="settings/ai" element={reports(<AiSettingsPage />)} />
        <Route path="orgs" element={orgs(<OrgsPage />)} />
        <Route path="orgs/certificates" element={orgs(<CertificatesPage />)} />
        <Route path="orgs/:id" element={orgs(<OrgDetailPage />)} />
        <Route path="resources" element={resources(<ResourcesPage />)} />
        <Route path="volunteers" element={reports(<VolunteersPage />)} />
        <Route path="volunteers/:id" element={reports(<VolunteerDetailPage />)} />
        <Route path="notifications" element={notifications(<NotificationsPage />)} />
        <Route path="notifications/new" element={notifications(<NotificationEditorPage />)} />
        <Route path="notifications/:id" element={notifications(<NotificationEditorPage />)} />
        <Route path="safety-tips" element={tips(<SafetyTipsPage />)} />
        <Route path="committee" element={committee(<CommitteePage />)} />
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
