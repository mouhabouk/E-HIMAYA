import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../context/auth";
import { LANGUAGES } from "../i18n";
import { useLanguage } from "../lib/hooks";
import { applyTheme, nextTheme, storedTheme, type Theme } from "../lib/theme";

/** One button per language, each labelled in its own language (and `lang`), the current one pressed. */
export function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  const lang = useLanguage();
  return (
    <div className="lang-switch" role="group" aria-label={t("header.language")}>
      {LANGUAGES.map((l) => (
        <button
          key={l}
          type="button"
          className="btn btn--ghost btn--small"
          lang={l}
          aria-pressed={l === lang}
          onClick={() => void i18n.changeLanguage(l)}
        >
          {t(`header.languages.${l}`)}
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

/** Sign-in and account creation buttons (registration = authorization request with prompt=create). */
export function SignInButtons({ primary = false }: { primary?: boolean }) {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const lang = useLanguage();
  const location = useLocation();
  const target = location.pathname === "/" ? "/orgs/mine" : `${location.pathname}${location.search}`;
  return (
    <>
      <button type="button" className={`btn${primary ? " btn--primary" : ""}`} onClick={() => void signIn(target, lang)}>
        {t("auth.signIn")}
      </button>
      <button type="button" className="btn" onClick={() => void signIn(target, lang, { create: true })}>
        {t("auth.createAccount")}
      </button>
    </>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { status, user, signOut } = useAuth();
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        {t("app.skipToContent")}
      </a>
      <header className="header">
        <Link to="/" className="header__brand">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>{t("app.name")}</span>
        </Link>
        <nav aria-label={t("nav.main")} className="header__nav">
          {user && <NavLink to="/orgs/mine">{t("nav.myOrgs")}</NavLink>}
          <NavLink to="/verify">{t("nav.verify")}</NavLink>
        </nav>
        <div className="header__tools">
          <LanguageSwitch />
          <ThemeToggle />
          {user ? (
            <>
              <span className="header__name">{user.identity.name}</span>
              <button type="button" className="btn" onClick={() => void signOut()}>
                {t("auth.signOut")}
              </button>
            </>
          ) : (
            status === "signedOut" && <SignInButtons />
          )}
        </div>
      </header>
      <main id="main" tabIndex={-1} className="main">
        <Outlet />
      </main>
      <footer className="footer muted">
        <p>{t("app.footer")}</p>
      </footer>
    </div>
  );
}
