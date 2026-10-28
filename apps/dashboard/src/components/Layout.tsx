import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router";
import { Icon } from "./Icon";
import { Disclosure, MainNav, navGroups } from "./Navigation";
import { useAuth } from "../context/auth";
import { useLiveState } from "../context/live";
import { directionOf, LANGUAGES, type Language } from "../i18n";
import { useGouvernorats, useLanguage } from "../lib/hooks";
import { canDraftMessage, canRequestBreakGlass, hasReadAccess, staffRoles } from "../lib/roles";
import { MENU_POSITIONS, MENU_SHAPES, type MenuPrefs, saveMenu, storedMenu } from "../lib/menu";
import { applyTheme, nextTheme, storedTheme, THEMES, type Theme } from "../lib/theme";
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
function useHeaderHeight(top: boolean) {
  return useCallback((header: HTMLElement | null) => {
    if (!header || typeof ResizeObserver === "undefined") return;
    const root = document.documentElement;
    // A side bar takes no height: pages that fill the screen use the whole of it.
    if (!top) {
      root.style.setProperty("--header-h", "0px");
      return () => root.style.removeProperty("--header-h");
    }
    const observer = new ResizeObserver(() =>
      root.style.setProperty("--header-h", `${header.offsetHeight}px`),
    );
    observer.observe(header);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--header-h");
    };
  }, [top]);
}

/** Segmented choice inside the account menu: radio buttons styled as one pill row. */
function Segmented<T extends string>({
  label,
  name,
  options,
  value,
  onChange,
}: {
  label: string;
  name: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="segmented">
      <legend>{label}</legend>
      <div className="segmented__row">
        {options.map((o) => (
          <label key={o.value} className="segmented__option">
            <input type="radio" name={name} value={o.value} checked={o.value === value} onChange={() => onChange(o.value)} />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/**
 * The account menu (design UI-3 §2.3): who is signed in, the language, the theme, how the main menu shows, and
 * sign-out. Every choice applies at once.
 */
function AccountMenu({
  name,
  scope,
  roles,
  menu,
  onMenu,
  onSignOut,
}: {
  name: string;
  scope: string;
  roles: string;
  menu: MenuPrefs;
  onMenu: (m: MenuPrefs) => void;
  onSignOut: () => void;
}) {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const rail = menu.position !== "top" && menu.shape === "grouped";
  return (
    <Disclosure
      className="account"
      panelClassName="account__panel"
      hover={false}
      label={
        <>
          <span className="account__avatar" aria-hidden="true">
            <Icon name="accountCircle" size={rail ? 30 : 26} />
          </span>
          <span className="account__who">
            <span className="account__name">{name}</span>
            <span className="account__scope">{scope}</span>
          </span>
          <span className="visually-hidden">{t("header.account")}</span>
        </>
      }
    >
      <div className="account__user">
        <p className="account__name">{name}</p>
        <p className="muted">
          <span className="visually-hidden">{t("header.scope")}: </span>
          {scope}
        </p>
        <p className="muted">
          <span className="visually-hidden">{t("header.roles")}: </span>
          {roles}
        </p>
      </div>
      <div className="account__section">
        <p className="account__label">{t("header.language")}</p>
        <LanguageMenu />
      </div>
      <Segmented
        label={t("header.themeLabel")}
        name="theme"
        value={theme}
        options={THEMES.map((v) => ({ value: v, label: t(`header.theme.${v}`) }))}
        onChange={(v) => {
          applyTheme(v);
          setTheme(v);
        }}
      />
      <Segmented
        label={t("header.menu.shape")}
        name="menu-shape"
        value={menu.shape}
        options={MENU_SHAPES.map((v) => ({ value: v, label: t(`header.menu.shapes.${v}`) }))}
        onChange={(shape) => onMenu({ ...menu, shape })}
      />
      <Segmented
        label={t("header.menu.position")}
        name="menu-position"
        value={menu.position}
        options={MENU_POSITIONS.map((v) => ({ value: v, label: t(`header.menu.positions.${v}`) }))}
        onChange={(position) => onMenu({ ...menu, position })}
      />
      <button type="button" className="btn account__logout" onClick={onSignOut}>
        <Icon name="logout" size={20} />
        {t("header.logout")}
      </button>
    </Disclosure>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();
  const live = useLiveState();
  const gouvernorats = useGouvernorats();
  const [menu, setMenu] = useState<MenuPrefs>(storedMenu);
  const top = menu.position === "top";
  const headerRef = useHeaderHeight(top);
  if (!user) return null;
  const { identity } = user;
  const scope = identity.national
    ? t("header.national")
    : t("header.gouvernorat", {
        name: gouvernorats.nameOf(identity.gouvernoratCode) ?? "",
      });
  const readsReports = hasReadAccess(identity.roles);
  const roles = staffRoles(identity.roles)
    .map((r) => t(`roles.${r}`))
    .join(t("common.listSeparator"));
  const groups = navGroups(identity, t);

  return (
    <div className="shell" data-menu-shape={menu.shape} data-menu-position={menu.position}>
      <a className="skip-link" href="#main">
        {t("app.skipToContent")}
      </a>
      <EnvironmentStrip />
      <header className={`header header--${top ? "top" : "side"} header--${menu.shape}`} ref={headerRef}>
        <div className="header__brand">
          {/* Logo of the Office (phase A, §2.5): the name next to it is the accessible text. */}
          <img
            src="/brand/logo.png"
            alt=""
            width="32"
            height="32"
            className="header__logo"
          />
          <span className="header__title">{t("app.name")}</span>
        </div>
        <MainNav groups={groups} shape={menu.shape} position={menu.position} />
        <div className="header__tools">
          <LiveIndicator />
          <AccountMenu
            name={identity.name}
            scope={scope}
            roles={roles}
            menu={menu}
            onMenu={(m) => {
              saveMenu(m);
              setMenu(m);
            }}
            onSignOut={() => void signOut()}
          />
        </div>
      </header>
      <div className="shell__body">
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
      </div>
      {readsReports && <StreamAlertToasts />}
      {canDraftMessage(identity.roles, "alert") && <AlertFollowUpToasts />}
      <SoftphoneDock />
    </div>
  );
}
