import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { i18n } from "i18next";
import { useState } from "react";
import { I18nextProvider } from "react-i18next";
import { BrowserRouter, Route, Routes } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
import { AuthProvider } from "./context/auth";
import { ServicesProvider, type Services } from "./context/services";
import { isApiError } from "./lib/api";
import { CallbackPage } from "./pages/CallbackPage";
import { InvitePage } from "./pages/InvitePage";
import { LandingPage } from "./pages/LandingPage";
import { MyOrgsPage } from "./pages/MyOrgsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RegisterOrgPage } from "./pages/RegisterOrgPage";
import { LivePage } from "./pages/LivePage";
import { VerifyPage } from "./pages/VerifyPage";
import { CardTab } from "./pages/org/CardTab";
import { ActivitiesTab } from "./pages/org/ActivitiesTab";
import { CertificatesTab } from "./pages/org/CertificatesTab";
import { DocumentsTab } from "./pages/org/DocumentsTab";
import { EquipmentTab } from "./pages/org/EquipmentTab";
import { FeaturesTab } from "./pages/org/FeaturesTab";
import { HazmatTab } from "./pages/org/HazmatTab";
import { MembersTab } from "./pages/org/MembersTab";
import { OrgWorkspace } from "./pages/org/OrgWorkspace";
import { OverviewTab } from "./pages/org/OverviewTab";
import { NewReportPage, ReportsTab } from "./pages/org/ReportsTab";
import { TeamTab } from "./pages/org/TeamTab";

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
      <Route element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="verify" element={<VerifyPage />} />
        <Route path="verify/:code" element={<VerifyPage />} />
        <Route path="live" element={<LivePage />} />
        <Route
          path="invite/:token"
          element={
            <RequireAuth>
              <InvitePage />
            </RequireAuth>
          }
        />
        <Route
          path="orgs/mine"
          element={
            <RequireAuth>
              <MyOrgsPage />
            </RequireAuth>
          }
        />
        <Route
          path="orgs/new"
          element={
            <RequireAuth>
              <RegisterOrgPage />
            </RequireAuth>
          }
        />
        <Route
          path="orgs/:orgId"
          element={
            <RequireAuth>
              <OrgWorkspace />
            </RequireAuth>
          }
        >
          <Route index element={<OverviewTab />} />
          <Route path="card" element={<CardTab />} />
          <Route path="team" element={<TeamTab />} />
          <Route path="hazmat" element={<HazmatTab />} />
          <Route path="equipment" element={<EquipmentTab />} />
          <Route path="map" element={<FeaturesTab />} />
          <Route path="documents" element={<DocumentsTab />} />
          <Route path="members" element={<MembersTab />} />
          <Route path="activities" element={<ActivitiesTab />} />
          <Route path="reports" element={<ReportsTab />} />
          <Route path="reports/new" element={<NewReportPage />} />
          <Route path="certificate" element={<CertificatesTab />} />
        </Route>
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
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ServicesProvider>
    </I18nextProvider>
  );
}
