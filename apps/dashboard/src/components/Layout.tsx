import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";
import { useAuth } from "../context/auth";
import { useLiveState } from "../context/live";
import { directionOf, LANGUAGES, type Language } from "../i18n";
import { useGouvernorats, useLanguage } from "../lib/hooks";
import {
  canEditAiSettings,
  canDraftMessage,
  canEditTips,
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
import { LevelBanner } from "./LevelBanner";
import { SoftphoneDock } from "./Softphone";
import { StreamAlertToasts } from "./StreamAlertToasts";

/** Native names of the interface languages, shown in their own script whatever the current language. */
export const LANGUAGE_NAMES: Record<Language, string> = { ar: "العربية", fr: "Français", en: "English" };

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
  const label = t("header.themeToggle", { current: t(`header.theme.${theme}`) });
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
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
        {theme === "dark" ? (
          <path fill="currentColor" d="M20 15.5A8.5 8.5 0 0 1 8.5 4a8.5 8.5 0 1 0 11.5 11.5z" />
        ) : theme === "light" ? (
          <path
            fill="currentColor"
            d="M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm-1-6h2v3h-2zm0 19h2v3h-2zM1 11h3v2H1zm19 0h3v2h-3zM4.2 5.6l1.4-1.4 2.1 2.1-1.4 1.4zm12.1 12.1 1.4-1.4 2.1 2.1-1.4 1.4zM4.2 18.4l2.1-2.1 1.4 1.4-2.1 2.1zM16.3 6.3l2.1-2.1 1.4 1.4-2.1 2.1z"
          />
        ) : (
          <path fill="currentColor" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm0 2v16a8 8 0 0 0 0-16z" />
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
    const observer = new ResizeObserver(() => root.style.setProperty("--header-h", `${header.offsetHeight}px`));
    observer.observe(header);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--header-h");
    };
  }, []);
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
    : t("header.gouvernorat", { name: gouvernorats.nameOf(identity.gouvernoratCode) ?? "" });
  // Only the screens the user's roles can use (the API enforces the same rules).
  const readsReports = hasReadAccess(identity.roles);
  const readsOrgs = canReadOrgs(identity.roles);
  const readsResources = canReadResources(identity.roles);
  const notifies = canUseNotifications(identity.roles);
  const editsTips = canEditTips(identity.roles);
  const reviewsWeather = canReviewWeatherSuggestions(identity.roles);
  const committee = isCommittee(identity.roles) || canMonitorPerformance(identity.roles);
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
      <header className="header" ref={headerRef}>
        <div className="header__brand">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>{t("app.name")}</span>
        </div>
        <nav aria-label={t("nav.main")} className="header__nav">
          {readsReports && (
            <>
              <NavLink to="/" end>
                {t("nav.home")}
              </NavLink>
              <NavLink to="/reports">{t("nav.reports")}</NavLink>
              <NavLink to="/incidents">{t("nav.incidents")}</NavLink>
              <NavLink to="/map">{t("nav.map")}</NavLink>
              <NavLink to="/streams">{t("nav.streams")}</NavLink>
              <NavLink to="/volunteers">{t("nav.volunteers")}</NavLink>
              <NavLink to="/calls">{t("nav.calls")}</NavLink>
              <NavLink to="/resource-requests">{t("nav.resourceRequests")}</NavLink>
            </>
          )}
          {nationalQueues && (
            <>
              <NavLink to="/reports/late">{t("nav.late")}</NavLink>
              <NavLink to="/reports/geo-queue">{t("nav.geoQueue")}</NavLink>
            </>
          )}
          {readsResources && <NavLink to="/resources">{t("nav.resources")}</NavLink>}
          {notifies && <NavLink to="/notifications">{t("nav.notifications")}</NavLink>}
          {reviewsWeather && <NavLink to="/weather/suggestions">{t("nav.weatherSuggestions")}</NavLink>}
          {committee && <NavLink to="/committee">{t("nav.committee")}</NavLink>}
          {analytics && (
            <>
              <NavLink to="/analytics">{t("nav.analytics")}</NavLink>
              <NavLink to="/reports-library">{t("nav.reportsLibrary")}</NavLink>
            </>
          )}
          {knowledge && (
            <>
              <NavLink to="/memory">{t("nav.memory")}</NavLink>
              <NavLink to="/library">{t("nav.library")}</NavLink>
            </>
          )}
          {rewards && <NavLink to="/rewards">{t("nav.rewards")}</NavLink>}
          {readsOrgs && (
            <>
              <NavLink to="/orgs" end>
                {t("nav.orgs")}
              </NavLink>
              <NavLink to="/orgs/certificates">{t("nav.certificates")}</NavLink>
            </>
          )}
          {editsTips && <NavLink to="/safety-tips">{t("nav.safetyTips")}</NavLink>}
          {canReadPlatformSettings(identity.roles) && (
            <NavLink to="/settings" end>
              {t("nav.settings")}
            </NavLink>
          )}
          {aiSettings && <NavLink to="/settings/ai">{t("nav.aiSettings")}</NavLink>}
          {canManageAccounts(identity) && <NavLink to="/accounts">{t("nav.accounts")}</NavLink>}
          {canReadScopedAudit(identity) && <NavLink to="/audit">{t("nav.audit")}</NavLink>}
          {canOpenBreakGlass(identity) && <NavLink to="/break-glass">{t("nav.breakGlass")}</NavLink>}
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
        {live === "forbidden" ? <NoAccessPage reason="liveForbidden" embedded /> : <Outlet />}
      </main>
      {readsReports && <StreamAlertToasts />}
      {canDraftMessage(identity.roles, "alert") && <AlertFollowUpToasts />}
      <SoftphoneDock />
    </div>
  );
}
