import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";
import { useAuth } from "../context/auth";
import { useLiveState } from "../context/live";
import { useGouvernorats, useLanguage } from "../lib/hooks";
import { staffRoles } from "../lib/roles";
import { applyTheme, nextTheme, storedTheme, type Theme } from "../lib/theme";
import { NoAccessPage } from "../pages/NoAccessPage";

export function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  const lang = useLanguage();
  const other = lang === "ar" ? "fr" : "ar";
  return (
    <button
      type="button"
      className="btn btn--ghost"
      lang={other}
      onClick={() => void i18n.changeLanguage(other)}
      aria-label={t("header.switchLanguage")}
    >
      {t("header.otherLanguage")}
    </button>
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

export function Layout() {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();
  const live = useLiveState();
  const gouvernorats = useGouvernorats();
  if (!user) return null;
  const { identity } = user;
  const scope = identity.national
    ? t("header.national")
    : t("header.gouvernorat", { name: gouvernorats.nameOf(identity.gouvernoratCode) ?? "" });
  const roles = staffRoles(identity.roles)
    .map((r) => t(`roles.${r}`))
    .join(t("common.listSeparator"));

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        {t("app.skipToContent")}
      </a>
      <header className="header">
        <div className="header__brand">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>{t("app.name")}</span>
        </div>
        <nav aria-label={t("nav.main")} className="header__nav">
          <NavLink to="/" end>
            {t("nav.home")}
          </NavLink>
          <NavLink to="/reports">{t("nav.reports")}</NavLink>
          <NavLink to="/incidents">{t("nav.incidents")}</NavLink>
          <NavLink to="/map">{t("nav.map")}</NavLink>
          <NavLink to="/settings/ai">{t("nav.aiSettings")}</NavLink>
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
          <LanguageSwitch />
          <ThemeToggle />
          <button type="button" className="btn" onClick={() => void signOut()}>
            {t("header.logout")}
          </button>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="main">
        {live === "forbidden" ? <NoAccessPage reason="liveForbidden" embedded /> : <Outlet />}
      </main>
    </div>
  );
}
