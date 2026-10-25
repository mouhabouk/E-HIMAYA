import { type ReactNode, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";
import { IconTile, type IconName, type Tone } from "./Icon";
import { useAuth } from "../context/auth";
import { useLiveState } from "../context/live";
import { directionOf, LANGUAGES, type Language } from "../i18n";
import { useGouvernorats, useLanguage } from "../lib/hooks";
import {
  canEditAiSettings,
  canDraftMessage,
  canEditTips,
  canManageMedicalCommittee,
  canReviewDoctors,
  canHandleContact,
  canOpenLayers,
  canManageAccounts,
  canOpenBreakGlass,
  canReadPlatformSettings,
  canReadScopedAudit,
  canRequestBreakGlass,
  canSeeNationalQueues,
  canMonitorPerformance,
  canReadAnalytics,
  canReadKnowledge,
  canReadRewards,
  canReadOrgs,
  canReadResources,
  canReviewWeatherSuggestions,
  canUseNotifications,
  hasReadAccess,
  isCommittee,
  staffRoles,
} from "../lib/roles";
import { applyTheme, nextTheme, storedTheme, type Theme } from "../lib/theme";
import { NoAccessPage } from "../pages/NoAccessPage";
import { AlertFollowUpToasts } from "./AlertFollowUpToasts";
import { ActiveGrantBanner } from "./BreakGlass";
import { EnvironmentStrip } from "./EnvironmentStrip";
import { LevelBanner } from "./LevelBanner";
import { SoftphoneDock } from "./Softphone";
import { StreamAlertToasts } from "./StreamAlertToasts";

/** Native names of the interface languages, shown in their own script whatever the current language. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  ar: "العربية",
  fr: "Français",
  en: "English",
};

/**
 * Three-way language menu. Changing the language only re-renders: the route, its query string and the scope stay
 * as they are, and the document direction and title follow (`i18n/index.ts`).
 */
export function LanguageMenu() {
  const { t, i18n } = useTranslation();
  const lang = useLanguage();
  return (
    <div className="lang-menu" role="group" aria-label={t("header.language")}>
      {LANGUAGES.map((l) => (
        <button
          key={l}
          type="button"
          className="btn btn--ghost btn--small"
          lang={l}
          dir={directionOf(l)}
          aria-pressed={l === lang}
          onClick={() => {
            if (l !== lang) void i18n.changeLanguage(l);
          }}
        >
          {LANGUAGE_NAMES[l]}
        </button>
      ))}
    </div>
  );
}

export function ThemeToggle() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const label = t("header.themeToggle", {
    current: t(`header.theme.${theme}`),
  });
  return (
    <button
      type="button"
      className="btn btn--ghost btn--icon"
      aria-label={label}
      title={label}
      onClick={() => {
        const next = nextTheme(theme);
        applyTheme(next);
        setTheme(next);
      }}
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        aria-hidden="true"
        focusable="false"
      >
        {theme === "dark" ? (
          <path
            fill="currentColor"
            d="M20 15.5A8.5 8.5 0 0 1 8.5 4a8.5 8.5 0 1 0 11.5 11.5z"
          />
        ) : theme === "light" ? (
          <path
            fill="currentColor"
            d="M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm-1-6h2v3h-2zm0 19h2v3h-2zM1 11h3v2H1zm19 0h3v2h-3zM4.2 5.6l1.4-1.4 2.1 2.1-1.4 1.4zm12.1 12.1 1.4-1.4 2.1 2.1-1.4 1.4zM4.2 18.4l2.1-2.1 1.4 1.4-2.1 2.1zM16.3 6.3l2.1-2.1 1.4 1.4-2.1 2.1z"
          />
        ) : (
          <path
            fill="currentColor"
            d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm0 2v16a8 8 0 0 0 0-16z"
          />
        )}
      </svg>
    </button>
  );
}

function LiveIndicator() {
  const { t } = useTranslation();
  const state = useLiveState();
  return (
    <span className={`live live--${state}`} role="status" aria-live="polite">
      <span className="live__dot" aria-hidden="true" />
      <span>{t(`live.state.${state}`)}</span>
    </span>
  );
}

/**
 * Publishes the sticky header's height as `--header-h`, which the page uses as scroll padding: scrolling to an
 * anchor or moving the keyboard focus never leaves the target under the header (WCAG 2.4.11), however many rows
 * the navigation wraps to.
 */
function useHeaderHeight() {
  return useCallback((header: HTMLElement | null) => {
    if (!header || typeof ResizeObserver === "undefined") return;
    const root = document.documentElement;
    const observer = new ResizeObserver(() =>
      root.style.setProperty("--header-h", `${header.offsetHeight}px`),
    );
    observer.observe(header);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--header-h");
    };
  }, []);
}

/** Navigation link with its category icon tile (design system §3): the label carries the meaning. */
function NavItem({
  to,
  end,
  icon,
  tone,
  children,
}: {
  to: string;
  end?: boolean;
  icon: IconName;
  tone: Tone;
  children: ReactNode;
}) {
  return (
    <NavLink to={to} end={end}>
      <IconTile name={icon} tone={tone} size="sm" />
      {children}
    </NavLink>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();
  const live = useLiveState();
  const gouvernorats = useGouvernorats();
  const headerRef = useHeaderHeight();
  if (!user) return null;
  const { identity } = user;
  const scope = identity.national
    ? t("header.national")
    : t("header.gouvernorat", {
        name: gouvernorats.nameOf(identity.gouvernoratCode) ?? "",
      });
  // Only the screens the user's roles can use (the API enforces the same rules).
  const readsReports = hasReadAccess(identity.roles);
  const readsOrgs = canReadOrgs(identity.roles);
  const readsResources = canReadResources(identity.roles);
  const notifies = canUseNotifications(identity.roles);
  const editsTips = canEditTips(identity.roles);
  const reviewsDoctors = canReviewDoctors(identity.roles);
  const reviewsWeather = canReviewWeatherSuggestions(identity.roles);
  const committee =
    isCommittee(identity.roles) || canMonitorPerformance(identity.roles);
  const analytics = canReadAnalytics(identity.roles);
  const knowledge = canReadKnowledge(identity.roles);
  const rewards = canReadRewards(identity.roles);
  const nationalQueues = canSeeNationalQueues(identity);
  const aiSettings = readsReports || canEditAiSettings(identity);
  const roles = staffRoles(identity.roles)
    .map((r) => t(`roles.${r}`))
    .join(t("common.listSeparator"));

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        {t("app.skipToContent")}
      </a>
      <EnvironmentStrip />
      <header className="header" ref={headerRef}>
        <div className="header__brand">
          {/* Logo of the Office (phase A, §2.5): the name next to it is the accessible text. */}
          <img
            src="/brand/logo.png"
            alt=""
            width="32"
            height="32"
            className="header__logo"
          />
          <span>{t("app.name")}</span>
        </div>
        <nav aria-label={t("nav.main")} className="header__nav">
          {readsReports && (
            <>
              <NavItem to="/" end icon="home" tone="navy">
                {t("nav.home")}
              </NavItem>
              <NavItem to="/reports" icon="description" tone="red">
                {t("nav.reports")}
              </NavItem>
              <NavItem to="/incidents" icon="localFireDepartment" tone="red">
                {t("nav.incidents")}
              </NavItem>
              <NavItem to="/map" icon="map" tone="teal">
                {t("nav.map")}
              </NavItem>
              <NavItem to="/streams" icon="videocam" tone="red">
                {t("nav.streams")}
              </NavItem>
              <NavItem to="/volunteers" icon="volunteerActivism" tone="green">
                {t("nav.volunteers")}
              </NavItem>
              <NavItem to="/calls" icon="call" tone="green">
                {t("nav.calls")}
              </NavItem>
              <NavItem to="/resource-requests" icon="inventory2" tone="amber">
                {t("nav.resourceRequests")}
              </NavItem>
            </>
          )}
          {nationalQueues && (
            <>
              <NavItem to="/reports/late" icon="schedule" tone="orange">
                {t("nav.late")}
              </NavItem>
              <NavItem
                to="/reports/geo-queue"
                icon="wrongLocation"
                tone="orange"
              >
                {t("nav.geoQueue")}
              </NavItem>
            </>
          )}
          {reviewsDoctors && (
            <NavItem to="/doctors" icon="stethoscope" tone="purple">
              {t("nav.doctors")}
            </NavItem>
          )}
          {canManageMedicalCommittee(identity) && (
            <NavItem to="/medical-committee" icon="groups" tone="purple">
              {t("nav.medicalCommittee")}
            </NavItem>
          )}
          {readsResources && (
            <NavItem to="/resources" icon="localShipping" tone="amber">
              {t("nav.resources")}
            </NavItem>
          )}
          {notifies && (
            <NavItem to="/notifications" icon="campaign" tone="sky">
              {t("nav.notifications")}
            </NavItem>
          )}
          {reviewsWeather && (
            <NavItem
              to="/weather/suggestions"
              icon="partlyCloudyDay"
              tone="sky"
            >
              {t("nav.weatherSuggestions")}
            </NavItem>
          )}
          {committee && (
            <NavItem to="/committee" icon="monitoring" tone="navy">
              {t("nav.committee")}
            </NavItem>
          )}
          {analytics && (
            <>
              <NavItem to="/analytics" icon="analytics" tone="navy">
                {t("nav.analytics")}
              </NavItem>
              <NavItem to="/reports-library" icon="folderOpen" tone="slate">
                {t("nav.reportsLibrary")}
              </NavItem>
            </>
          )}
          {knowledge && (
            <>
              <NavItem to="/memory" icon="historyEdu" tone="purple">
                {t("nav.memory")}
              </NavItem>
              <NavItem to="/library" icon="menuBook" tone="purple">
                {t("nav.library")}
              </NavItem>
            </>
          )}
          {rewards && (
            <NavItem to="/rewards" icon="militaryTech" tone="pink">
              {t("nav.rewards")}
            </NavItem>
          )}
          {readsOrgs && (
            <>
              <NavItem to="/orgs" end icon="apartment" tone="navy">
                {t("nav.orgs")}
              </NavItem>
              <NavItem
                to="/orgs/certificates"
                icon="workspacePremium"
                tone="amber"
              >
                {t("nav.certificates")}
              </NavItem>
            </>
          )}
          {editsTips && (
            <NavItem to="/safety-tips" icon="healthAndSafety" tone="green">
              {t("nav.safetyTips")}
            </NavItem>
          )}
          {editsTips && (
            <NavItem to="/emergency-guide" icon="medicalServices" tone="red">
              {t("nav.emergencyGuide")}
            </NavItem>
          )}
          {canOpenLayers(identity.roles) && (
            <NavItem to="/layers" icon="layers" tone="teal">
              {t("nav.layers")}
            </NavItem>
          )}
          {canHandleContact(identity.roles) && (
            <NavItem to="/contact" icon="mail" tone="sky">
              {t("nav.contact")}
            </NavItem>
          )}
          {canReadPlatformSettings(identity.roles) && (
            <NavItem to="/settings" end icon="settings" tone="slate">
              {t("nav.settings")}
            </NavItem>
          )}
          {aiSettings && (
            <NavItem to="/settings/ai" icon="smartToy" tone="slate">
              {t("nav.aiSettings")}
            </NavItem>
          )}
          {canManageAccounts(identity) && (
            <NavItem to="/accounts" icon="manageAccounts" tone="slate">
              {t("nav.accounts")}
            </NavItem>
          )}
          {canReadScopedAudit(identity) && (
            <NavItem to="/audit" icon="policy" tone="slate">
              {t("nav.audit")}
            </NavItem>
          )}
          {canOpenBreakGlass(identity) && (
            <NavItem to="/break-glass" icon="lockOpen" tone="red">
              {t("nav.breakGlass")}
            </NavItem>
          )}
        </nav>
        <div className="header__tools">
          <LiveIndicator />
          <div className="header__user">
            <span className="header__name">{identity.name}</span>
            <span className="header__scope">
              <span className="visually-hidden">{t("header.scope")}: </span>
              {scope}
            </span>
            <span className="header__roles">
              <span className="visually-hidden">{t("header.roles")}: </span>
              {roles}
            </span>
          </div>
          <LanguageMenu />
          <ThemeToggle />
          <button type="button" className="btn" onClick={() => void signOut()}>
            {t("header.logout")}
          </button>
        </div>
      </header>
      <LevelBanner />
      {canRequestBreakGlass(identity.roles) && (
        <div className="shell__banner">
          <ActiveGrantBanner />
        </div>
      )}
      <main id="main" tabIndex={-1} className="main">
        {live === "forbidden" ? (
          <NoAccessPage reason="liveForbidden" embedded />
        ) : (
          <Outlet />
        )}
      </main>
      {readsReports && <StreamAlertToasts />}
      {canDraftMessage(identity.roles, "alert") && <AlertFollowUpToasts />}
      <SoftphoneDock />
    </div>
  );
}
