import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { i18n } from "i18next";
import { lazy, Suspense, useState, type ComponentType, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import { Loading } from "./components/Feedback";
import { Layout } from "./components/Layout";
import { AuthProvider, useAuth } from "./context/auth";
import { FiltersProvider } from "./context/filters";
import { LiveProvider } from "./context/live";
import { ServicesProvider, type Services } from "./context/services";
import { SoftphoneProvider } from "./context/softphone";
import { isApiError } from "./lib/api";
import {
  canEditAiSettings,
  canEditTips,
  canHandleContact,
  canOpenCoastal,
  canOpenProgrammes,
  canOpenAxes,
  canOpenCommand,
  canOpenRegister,
  canOpenLayers,
  canManageAccounts,
  canOpenCrew,
  canOpenBreakGlass,
  canReadPlatformSettings,
  canReadScopedAudit,
  canSeeNationalQueues,
  canManageSchedules,
  canMonitorPerformance,
  canReadAnalytics,
  canReadKnowledge,
  canReadRewards,
  canRunScenarios,
  canSeeRewardActivity,
  canReadOrgs,
  canReadResources,
  canManageMedicalCommittee,
  canReviewDoctors,
  canReviewWeatherSuggestions,
  canUseNotifications,
  hasReadAccess,
  isCommittee,
  landingPath,
} from "./lib/roles";
import type { StaffIdentity } from "./auth/identity";
import { AccountsPage } from "./pages/AccountsPage";
import { AiSettingsPage } from "./pages/AiSettingsPage";
import { AuditPage } from "./pages/AuditPage";
import { BreakGlassPage } from "./pages/BreakGlassPage";
import { GeoQueuePage } from "./pages/GeoQueuePage";
import { LateReportsPage } from "./pages/LateReportsPage";
import { ResourceRequestsPage } from "./pages/ResourceRequestsPage";
import { CrewPage } from "./pages/CrewPage";
import { ReportTemplatesPage } from "./pages/ReportTemplatesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { CallsPage } from "./pages/CallsPage";
import { CallbackPage } from "./pages/CallbackPage";
import { CertificatesPage } from "./pages/CertificatesPage";
import { PreventionPage, VisitPage } from "./pages/PreventionPages";
import { CounterPage } from "./pages/CounterPage";
import { CommitteePage } from "./pages/CommitteePage";
import { DoctorDetailPage } from "./pages/DoctorDetailPage";
import { DoctorsPage } from "./pages/DoctorsPage";
import { MedicalCommitteePage } from "./pages/MedicalCommitteePage";
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
import { StreamArchivePage } from "./pages/StreamArchivePage";
import { StreamDetailPage } from "./pages/StreamDetailPage";
import { StreamsPage } from "./pages/StreamsPage";
import { StreamWallPage } from "./pages/StreamWallPage";
import { VolunteerDetailPage } from "./pages/VolunteerDetailPage";
import { VolunteersPage } from "./pages/VolunteersPage";
import { WeatherSuggestionsPage } from "./pages/WeatherSuggestionsPage";

// Phase 8 screens are loaded on demand: they bring the chart (uPlot) and Markdown (markdown-it, DOMPurify) code.
const page = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const AnalyticsPage = page(() => import("./pages/AnalyticsPage"), "AnalyticsPage");
const ScenariosPage = page(() => import("./pages/ScenariosPage"), "ScenariosPage");
const ScenarioDetailPage = page(() => import("./pages/ScenariosPage"), "ScenarioDetailPage");
const ReportsLibraryPage = page(() => import("./pages/ReportsLibraryPage"), "ReportsLibraryPage");
const ReportSchedulesPage = page(() => import("./pages/ReportSchedulesPage"), "ReportSchedulesPage");
const CommandPage = page(() => import("./pages/CommandPage"), "CommandPage");
const AxesPage = page(() => import("./pages/AxesPage"), "AxesPage");
const AxisPage = page(() => import("./pages/AxisPage"), "AxisPage");
// Phase L3b: register of plans, decisions and instructions.
const RegisterPage = page(() => import("./pages/RegisterPage"), "RegisterPage");
const RegisterDocumentPage = page(() => import("./pages/RegisterDocumentPage"), "RegisterDocumentPage");
const DispatchesPage = page(() => import("./pages/DispatchPages"), "DispatchesPage");
const DispatchPage = page(() => import("./pages/DispatchPages"), "DispatchPage");
const MemoryListPage = page(() => import("./pages/MemoryListPage"), "MemoryListPage");
const MemoryEntryPage = page(() => import("./pages/MemoryEntryPage"), "MemoryEntryPage");
const EventsLibraryPage = page(() => import("./pages/EventsLibraryPage"), "EventsLibraryPage");
const LibraryItemPage = page(() => import("./pages/EventsLibraryPage"), "LibraryItemPage");
const RewardRulesPage = page(() => import("./pages/RewardsPages"), "RewardRulesPage");
const RewardConfirmationsPage = page(() => import("./pages/RewardsPages"), "RewardConfirmationsPage");
const RewardNominationsPage = page(() => import("./pages/RewardsPages"), "RewardNominationsPage");
const RewardCertificatesPage = page(() => import("./pages/RewardsPages"), "RewardCertificatesPage");
const RewardLeaderboardPage = page(() => import("./pages/RewardsPages"), "RewardLeaderboardPage");
// Phase B1: map data layers (file import, preview map).
const LayersPage = page(() => import("./pages/LayersPage"), "LayersPage");
const CoastalPage = page(() => import("./pages/CoastalPage"), "CoastalPage");
// Phase L2: seasonal programmes.
const ProgrammesPage = page(() => import("./pages/ProgrammesPage"), "ProgrammesPage");
const ProgrammeDetailPage = page(() => import("./pages/ProgrammeDetailPage"), "ProgrammeDetailPage");
const EmergencyGuidePage = page(() => import("./pages/EmergencyGuidePage"), "EmergencyGuidePage");
const ContactInboxPage = page(() => import("./pages/ContactInboxPage"), "ContactInboxPage");

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

/** A screen whose access depends on the scope (national or regional room) as well as the roles (phase 9). */
export function ScopeGate({ allow, children }: { allow: (identity: StaffIdentity) => boolean; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !allow(user.identity)) return <NoAccessPage reason="noRole" embedded />;
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
const weather = (page: ReactNode) => <Gate allow={canReviewWeatherSuggestions}>{page}</Gate>;
/** A lazily loaded screen behind its role gate. */
const gated = (allow: (roles: readonly string[]) => boolean, el: ReactNode) => (
  <Gate allow={allow}>
    <Suspense fallback={<Loading />}>{el}</Suspense>
  </Gate>
);
const scoped = (allow: (identity: StaffIdentity) => boolean, page: ReactNode) => <ScopeGate allow={allow}>{page}</ScopeGate>;
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
        <Route path="reports/late" element={scoped(canSeeNationalQueues, <LateReportsPage />)} />
        <Route path="reports/geo-queue" element={scoped(canSeeNationalQueues, <GeoQueuePage />)} />
        <Route path="reports/:id" element={reports(<ReportDetailPage />)} />
        <Route path="incidents" element={reports(<IncidentsPage />)} />
        <Route path="incidents/:id" element={reports(<IncidentDetailPage />)} />
        <Route path="map" element={reports(<MapPage />)} />
        <Route path="streams" element={reports(<StreamsPage />)} />
        <Route path="streams/wall" element={reports(<StreamWallPage />)} />
        <Route path="streams/archive" element={reports(<StreamArchivePage />)} />
        <Route path="streams/:id" element={reports(<StreamDetailPage />)} />
        <Route path="settings" element={<Gate allow={canReadPlatformSettings}><SettingsPage /></Gate>} />
        <Route
          path="settings/ai"
          element={scoped((id) => hasReadAccess(id.roles) || canEditAiSettings(id), <AiSettingsPage />)}
        />
        <Route path="resource-requests" element={reports(<ResourceRequestsPage />)} />
        <Route path="crew" element={<Gate allow={canOpenCrew}><CrewPage /></Gate>} />
        <Route path="report-templates" element={reports(<ReportTemplatesPage />)} />
        <Route path="accounts" element={scoped(canManageAccounts, <AccountsPage />)} />
        <Route path="audit" element={scoped(canReadScopedAudit, <AuditPage />)} />
        <Route path="break-glass" element={scoped(canOpenBreakGlass, <BreakGlassPage />)} />
        <Route path="calls" element={reports(<CallsPage />)} />
        <Route path="weather/suggestions" element={weather(<WeatherSuggestionsPage />)} />
        <Route path="orgs" element={orgs(<OrgsPage />)} />
        <Route path="orgs/certificates" element={orgs(<CertificatesPage />)} />
        <Route path="orgs/certificates/counter" element={orgs(<CounterPage />)} />
        <Route path="orgs/prevention" element={orgs(<PreventionPage />)} />
        <Route path="orgs/prevention/:id" element={orgs(<VisitPage />)} />
        <Route path="orgs/:id" element={orgs(<OrgDetailPage />)} />
        <Route path="resources" element={resources(<ResourcesPage />)} />
        <Route path="volunteers" element={reports(<VolunteersPage />)} />
        <Route path="volunteers/:id" element={reports(<VolunteerDetailPage />)} />
        <Route path="doctors" element={gated(canReviewDoctors, <DoctorsPage />)} />
        <Route path="doctors/:id" element={gated(canReviewDoctors, <DoctorDetailPage />)} />
        <Route path="medical-committee" element={scoped(canManageMedicalCommittee, <MedicalCommitteePage />)} />
        <Route path="notifications" element={notifications(<NotificationsPage />)} />
        <Route path="notifications/new" element={notifications(<NotificationEditorPage />)} />
        <Route path="notifications/:id" element={notifications(<NotificationEditorPage />)} />
        <Route path="safety-tips" element={tips(<SafetyTipsPage />)} />
        <Route path="layers" element={gated(canOpenLayers, <LayersPage />)} />
        <Route path="coastal" element={gated(canOpenCoastal, <CoastalPage />)} />
        <Route path="programmes" element={gated(canOpenProgrammes, <ProgrammesPage />)} />
        <Route path="programmes/:id" element={gated(canOpenProgrammes, <ProgrammeDetailPage />)} />
        <Route path="axes" element={gated(canOpenAxes, <AxesPage />)} />
        <Route path="axes/:id" element={gated(canOpenAxes, <AxisPage />)} />
        <Route path="register" element={gated(canOpenRegister, <RegisterPage />)} />
        <Route path="register/dispatches" element={gated(canOpenRegister, <DispatchesPage />)} />
        <Route path="register/dispatches/:id" element={gated(canOpenRegister, <DispatchPage />)} />
        <Route path="register/:id" element={gated(canOpenRegister, <RegisterDocumentPage />)} />
        <Route path="command" element={gated(canOpenCommand, <CommandPage />)} />
        <Route path="emergency-guide" element={gated(canEditTips, <EmergencyGuidePage />)} />
        <Route path="contact" element={gated(canHandleContact, <ContactInboxPage />)} />
        <Route path="committee" element={committee(<CommitteePage />)} />
        <Route path="analytics" element={gated(canReadAnalytics, <AnalyticsPage />)} />
        <Route path="analytics/scenarios" element={gated(canRunScenarios, <ScenariosPage />)} />
        <Route path="analytics/scenarios/:id" element={gated(canRunScenarios, <ScenarioDetailPage />)} />
        <Route path="reports-library" element={gated(canReadAnalytics, <ReportsLibraryPage />)} />
        <Route path="reports-library/schedules" element={gated(canManageSchedules, <ReportSchedulesPage />)} />
        <Route path="memory" element={gated(canReadKnowledge, <MemoryListPage />)} />
        <Route path="memory/new" element={gated(canReadKnowledge, <MemoryEntryPage />)} />
        <Route path="memory/:id" element={gated(canReadKnowledge, <MemoryEntryPage />)} />
        <Route path="library" element={gated(canReadKnowledge, <EventsLibraryPage />)} />
        <Route path="library/items/:kind/:id" element={gated(canReadKnowledge, <LibraryItemPage />)} />
        <Route path="rewards" element={gated(canReadRewards, <RewardRulesPage />)} />
        <Route path="rewards/confirmations" element={gated(canSeeRewardActivity, <RewardConfirmationsPage />)} />
        <Route path="rewards/nominations" element={gated(canSeeRewardActivity, <RewardNominationsPage />)} />
        <Route path="rewards/certificates" element={gated(canSeeRewardActivity, <RewardCertificatesPage />)} />
        <Route path="rewards/leaderboard" element={gated(canSeeRewardActivity, <RewardLeaderboardPage />)} />
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
              <SoftphoneProvider>
                <FiltersProvider>
                  <BrowserRouter>
                    <AppRoutes />
                  </BrowserRouter>
                </FiltersProvider>
              </SoftphoneProvider>
            </LiveProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ServicesProvider>
    </I18nextProvider>
  );
}
