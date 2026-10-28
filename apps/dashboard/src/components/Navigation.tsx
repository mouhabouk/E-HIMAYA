// The main menu (phase UI-3, docs/phase-ui3/design-menu.md): the same links under the same role rules as before,
// in seven groups. Grouped, each group is a disclosure button that opens a glass panel on hover, click or keyboard;
// flat, every link shows at once. At the top of the page or in a side bar, as the user chose in the account menu.
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { matchPath, NavLink, useLocation } from "react-router";
import type { TFunction } from "i18next";
import { Icon, IconTile, type IconName, type Tone } from "./Icon";
import type { StaffIdentity as Identity } from "../auth/identity";
import {
  canEditAiSettings,
  canEditTips,
  canHandleContact,
  canManageAccounts,
  canManageMedicalCommittee,
  canMonitorPerformance,
  canOpenAxes,
  canOpenBreakGlass,
  canOpenCoastal,
  canOpenCommand,
  canOpenCrew,
  canOpenInventory,
  canOpenLayers,
  canOpenProgrammes,
  canOpenRegister,
  canOpenSchedule,
  canReadAnalytics,
  canReadKnowledge,
  canReadOrgs,
  canReadPlatformSettings,
  canReadResources,
  canReadRewards,
  canReadScopedAudit,
  canReviewDoctors,
  canReviewWeatherSuggestions,
  canSeeNationalQueues,
  canUseNotifications,
  hasReadAccess,
  isCommittee,
} from "../lib/roles";
import type { MenuPosition, MenuShape } from "../lib/menu";

export interface NavEntry {
  to: string;
  end?: boolean;
  icon: IconName;
  tone: Tone;
  label: string;
}

export interface NavGroup {
  key: string;
  icon: IconName;
  tone: Tone;
  label: string;
  items: NavEntry[];
}

/** The links the user's roles can open (the API enforces the same rules), in their groups; empty groups dropped. */
export function navGroups(identity: Identity, t: TFunction): NavGroup[] {
  const roles = identity.roles;
  const reads = hasReadAccess(roles);
  const knowledge = canReadKnowledge(roles);
  const analytics = canReadAnalytics(roles);
  const editsTips = canEditTips(roles);
  const orgs = canReadOrgs(roles);
  const e = (show: boolean, to: string, icon: IconName, tone: Tone, key: string, end?: boolean): NavEntry[] =>
    show ? [{ to, end, icon, tone, label: t(`nav.${key}`) }] : [];
  const groups: NavGroup[] = [
    {
      key: "ops",
      icon: "dashboard",
      tone: "red",
      label: t("nav.group.ops"),
      items: [
        ...e(reads, "/", "home", "navy", "home", true),
        ...e(reads, "/reports", "description", "red", "reports"),
        ...e(reads, "/incidents", "localFireDepartment", "red", "incidents"),
        ...e(reads, "/map", "map", "teal", "map"),
        ...e(reads, "/streams", "videocam", "red", "streams"),
        ...e(reads, "/calls", "call", "green", "calls"),
        ...e(reads, "/resource-requests", "inventory2", "amber", "resourceRequests"),
        ...e(canSeeNationalQueues(identity), "/reports/late", "schedule", "orange", "late"),
        ...e(canSeeNationalQueues(identity), "/reports/geo-queue", "wrongLocation", "orange", "geoQueue"),
        ...e(canReadResources(roles), "/resources", "localShipping", "amber", "resources"),
        ...e(canOpenInventory(roles), "/inventory", "inventory2", "teal", "inventory"),
        ...e(canOpenCrew(roles), "/crew", "groups", "green", "crew"),
        ...e(canOpenSchedule(roles), "/schedule", "calendarMonth", "teal", "schedule"),
      ],
    },
    {
      key: "crisis",
      icon: "crisisAlert",
      tone: "navy",
      label: t("nav.group.crisis"),
      items: [
        ...e(canOpenCommand(roles), "/command", "militaryTech", "navy", "command"),
        ...e(canOpenAxes(roles), "/axes", "warning", "red", "axes"),
        ...e(canOpenRegister(roles), "/plans", "menuBook", "sky", "plans"),
        ...e(canOpenRegister(roles), "/register", "folderOpen", "navy", "register", true),
        ...e(canOpenRegister(roles), "/register/dispatches", "campaign", "red", "dispatches"),
        ...e(isCommittee(roles) || canMonitorPerformance(roles), "/committee", "monitoring", "navy", "committee"),
        ...e(canOpenProgrammes(roles), "/programmes", "schedule", "orange", "programmes"),
        ...e(canOpenCoastal(roles), "/coastal", "healthAndSafety", "sky", "coastal"),
      ],
    },
    {
      key: "alerts",
      icon: "campaign",
      tone: "sky",
      label: t("nav.group.alerts"),
      items: [
        ...e(canUseNotifications(roles), "/notifications", "campaign", "sky", "notifications"),
        ...e(canReviewWeatherSuggestions(roles), "/weather/suggestions", "partlyCloudyDay", "sky", "weatherSuggestions"),
        ...e(editsTips, "/safety-tips", "healthAndSafety", "green", "safetyTips"),
        ...e(editsTips, "/emergency-guide", "medicalServices", "red", "emergencyGuide"),
        ...e(canHandleContact(roles), "/contact", "mail", "sky", "contact"),
      ],
    },
    {
      key: "people",
      icon: "volunteerActivism",
      tone: "green",
      label: t("nav.group.people"),
      items: [
        ...e(reads, "/volunteers", "volunteerActivism", "green", "volunteers"),
        ...e(canReviewDoctors(roles), "/doctors", "stethoscope", "purple", "doctors"),
        ...e(canManageMedicalCommittee(identity), "/medical-committee", "groups", "purple", "medicalCommittee"),
        ...e(canReadRewards(roles), "/rewards", "militaryTech", "pink", "rewards"),
      ],
    },
    {
      key: "orgs",
      icon: "apartment",
      tone: "navy",
      label: t("nav.group.orgs"),
      items: [
        ...e(orgs, "/orgs", "apartment", "navy", "orgs", true),
        ...e(orgs, "/orgs/certificates", "workspacePremium", "amber", "certificates"),
        ...e(orgs, "/orgs/certificates/counter", "verified", "green", "counter"),
        ...e(orgs, "/orgs/prevention", "policy", "purple", "prevention"),
      ],
    },
    {
      key: "knowledge",
      icon: "insights",
      tone: "purple",
      label: t("nav.group.knowledge"),
      items: [
        ...e(analytics, "/analytics", "analytics", "navy", "analytics"),
        ...e(analytics, "/reports-library", "folderOpen", "slate", "reportsLibrary"),
        ...e(reads, "/report-templates", "description", "purple", "reportTemplates"),
        ...e(knowledge, "/memory", "historyEdu", "purple", "memory"),
        ...e(knowledge, "/library", "menuBook", "purple", "library"),
      ],
    },
    {
      key: "system",
      icon: "adminPanelSettings",
      tone: "slate",
      label: t("nav.group.system"),
      items: [
        ...e(canOpenLayers(roles), "/layers", "layers", "teal", "layers"),
        ...e(canReadPlatformSettings(roles), "/settings", "settings", "slate", "settings", true),
        ...e(reads || canEditAiSettings(identity), "/settings/ai", "smartToy", "slate", "aiSettings"),
        ...e(canManageAccounts(identity), "/accounts", "manageAccounts", "slate", "accounts"),
        ...e(canReadScopedAudit(identity), "/audit", "policy", "slate", "audit"),
        ...e(canOpenBreakGlass(identity), "/break-glass", "lockOpen", "red", "breakGlass"),
      ],
    },
  ];
  return groups.filter((g) => g.items.length > 0);
}

function NavItem({ entry }: { entry: NavEntry }) {
  return (
    <NavLink to={entry.to} end={entry.end} className="nav-link">
      <IconTile name={entry.icon} tone={entry.tone} size="sm" />
      <span>{entry.label}</span>
    </NavLink>
  );
}

function isActive(group: NavGroup, pathname: string): boolean {
  return group.items.some((i) => matchPath({ path: i.to, end: i.end ?? false }, pathname) !== null);
}

const OPEN_DELAY = 90;
const CLOSE_DELAY = 220;

/**
 * Disclosure that opens its glass panel on hover (mouse only, after a short delay), on click and on Enter or
 * Space; Escape closes it and gives the focus back to the button, and leaving it with the focus closes it.
 */
export function Disclosure({
  className,
  label,
  active,
  hover = true,
  panelClassName,
  children,
}: {
  className: string;
  label: ReactNode;
  active?: boolean;
  hover?: boolean;
  panelClassName: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const later = (next: boolean, ms: number) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(next), ms);
  };
  const close = () => {
    window.clearTimeout(timer.current);
    setOpen(false);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    if (!open) return;
    const outside = (ev: PointerEvent) => {
      if (root.current && !root.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return (
    <div
      ref={root}
      className={className}
      data-open={open || undefined}
      onPointerEnter={hover ? (ev) => ev.pointerType === "mouse" && later(true, OPEN_DELAY) : undefined}
      onPointerLeave={hover ? (ev) => ev.pointerType === "mouse" && later(false, CLOSE_DELAY) : undefined}
      onKeyDown={(ev) => {
        if (ev.key === "Escape" && open) {
          ev.stopPropagation();
          close();
          button.current?.focus();
        }
      }}
      onBlur={(ev) => {
        if (!ev.currentTarget.contains(ev.relatedTarget)) close();
      }}
    >
      <button
        ref={button}
        type="button"
        className="nav-group__btn"
        aria-expanded={open}
        aria-controls={id}
        data-active={active || undefined}
        onClick={() => {
          window.clearTimeout(timer.current);
          setOpen((o) => !o);
        }}
      >
        {label}
      </button>
      <div
        id={id}
        className={`glass-panel ${panelClassName}`}
        hidden={!open}
        onClick={(ev) => {
          // Following a link closes the panel; the page changes under it.
          if ((ev.target as Element).closest("a")) close();
        }}
      >
        {children}
      </div>
    </div>
  );
}

function GroupMenu({ group, rail }: { group: NavGroup; rail: boolean }) {
  const { pathname } = useLocation();
  const only = group.items.length === 1 ? group.items[0] : undefined;
  if (only) {
    return (
      <div className="nav-group nav-group--single">
        <NavItem entry={only} />
      </div>
    );
  }
  return (
    <Disclosure
      className="nav-group"
      panelClassName="nav-group__panel"
      active={isActive(group, pathname)}
      label={
        <>
          <IconTile name={group.icon} tone={group.tone} size="sm" />
          <span className="nav-group__label">{group.label}</span>
          {!rail && <Icon name="expandMore" size={18} />}
        </>
      }
    >
      <p className="nav-group__title" aria-hidden="true">
        {group.label}
      </p>
      <ul>
        {group.items.map((entry) => (
          <li key={entry.to}>
            <NavItem entry={entry} />
          </li>
        ))}
      </ul>
    </Disclosure>
  );
}

/** The main navigation in the chosen shape; the position only changes where the shell puts it. */
export function MainNav({
  groups,
  shape,
  position,
}: {
  groups: NavGroup[];
  shape: MenuShape;
  position: MenuPosition;
}) {
  const { t } = useTranslation();
  const side = position !== "top";
  return (
    <nav aria-label={t("nav.main")} className={`main-nav main-nav--${shape} main-nav--${side ? "side" : "top"}`}>
      {shape === "grouped"
        ? groups.map((g) => <GroupMenu key={g.key} group={g} rail={side} />)
        : groups.map((g) =>
            side ? (
              <section key={g.key} className="main-nav__section" aria-label={g.label}>
                <p className="main-nav__heading" aria-hidden="true">
                  {g.label}
                </p>
                {g.items.map((entry) => (
                  <NavItem key={entry.to} entry={entry} />
                ))}
              </section>
            ) : (
              g.items.map((entry) => <NavItem key={entry.to} entry={entry} />)
            ),
          )}
    </nav>
  );
}
