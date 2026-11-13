// The main menu (phase UI-3, docs/phase-ui3/design-menu.md), rebuilt on 2026-11-13 (Yamen) as 20 systems in 4 blocks
// read from one source, src/menu/menu.json. Grouped, each block is a disclosure button that opens a glass panel with
// its systems on hover, click or keyboard; flat, every link shows at once. At the top of the page or in a side bar, as
// the user chose in the account menu.
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { matchPath, NavLink, useLocation } from "react-router";
import i18next, { type TFunction } from "i18next";
import { Icon, IconTile, type IconName, type Tone } from "./Icon";
import type { StaffIdentity as Identity } from "../auth/identity";
import { isLanguage, type Language } from "../i18n";
import type { MenuPosition, MenuShape } from "../lib/menu";
import { allowed, featureOfPath, type FeatureAccess } from "../lib/features";
import { localized } from "../lib/localized";
import { BLOCK_OF, gateAllows, MENU, SYSTEMS, type MenuItemSpec } from "../menu/menu";

export interface NavEntry {
  to: string;
  end?: boolean;
  icon: IconName;
  tone: Tone;
  label: string;
  /** A sub-heading inside the system (the developer tools inside the settings). */
  section?: string;
}

export interface NavGroup {
  /** The system's key (menu.json), or "home" for the first screen outside every system. */
  key: string;
  /** The block the system belongs to (operational, support, partner spaces, mother boards). */
  block: string;
  number?: number;
  icon: IconName;
  tone: Tone;
  label: string;
  items: NavEntry[];
  /** The administrator suspended the whole system: its message, shown in place of its links. */
  suspended?: string;
}

function currentLanguage(): Language {
  const lng = i18next.resolvedLanguage ?? i18next.language;
  return isLanguage(lng) ? lng : "ar";
}

/** The links the user's roles can open (the API enforces the same rules), in their systems; empty systems dropped. */
export function navGroups(
  identity: Identity,
  t: TFunction,
  access?: FeatureAccess,
  windowOpen?: boolean,
  strategies: readonly NavEntry[] = [],
  lang: Language = currentLanguage(),
): NavGroup[] {
  const ctx = { windowOpen };
  // The administrator's rules (L4 §8): a hidden page leaves the menu, a granted one joins it.
  const entry = (spec: MenuItemSpec, byRole: boolean): NavEntry[] =>
    !spec.planned && !spec.tabOf && (access ? allowed(access, featureOfPath(spec.path), byRole) : byRole)
      ? [
          {
            to: spec.path,
            end: spec.end,
            icon: spec.icon,
            tone: spec.tone,
            label: t(`nav.${spec.key}`),
            ...(spec.section ? { section: spec.section } : {}),
          },
        ]
      : [];
  const home = MENU.home;
  const groups: NavGroup[] = [
    {
      key: "home",
      block: "home",
      icon: home.icon,
      tone: home.tone,
      label: t(`nav.${home.key}`),
      items: entry(home, gateAllows(home.gate, identity, ctx)),
    },
    ...SYSTEMS.map((s) => {
      const message = access?.suspended?.[s.key];
      const byRole = s.items.filter((i) => !i.planned && !i.tabOf && gateAllows(i.gate, identity, ctx));
      const group: NavGroup = {
        key: s.key,
        block: BLOCK_OF[s.key] ?? "",
        number: s.number,
        icon: s.icon,
        tone: s.tone,
        label: localized(s.names, lang),
        items: s.items.flatMap((i) => entry(i, gateAllows(i.gate, identity, ctx))),
      };
      // Suspended (phase 2026-11-13): the system stays in the menu of those who could open it, with the message.
      if (message && byRole.length > 0) return { ...group, items: [], suspended: localized(message, lang) };
      return group;
    }),
  ];
  // The items the system administrator added (their own page, or a page of the platform not already listed).
  const own = groups.find((g) => g.key === "strategies");
  if (own && !own.suspended) {
    own.items.push(...strategies.filter((s) => !groups.some((g) => g.items.some((i) => i.to === s.to))));
    // The overview alone is no menu, except for the administrator who adds the items.
    if (own.items.length === 1 && !(identity.national && identity.roles.includes("sysadmin"))) own.items = [];
  }
  return groups.filter((g) => g.items.length > 0 || g.suspended);
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
  return group.items.some(
    (i) => matchPath({ path: i.to, end: i.end ?? false }, pathname) !== null,
  );
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
      if (root.current && !root.current.contains(ev.target as Node))
        setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return (
    <div
      ref={root}
      className={className}
      data-open={open || undefined}
      onPointerEnter={
        hover
          ? (ev) => ev.pointerType === "mouse" && later(true, OPEN_DELAY)
          : undefined
      }
      onPointerLeave={
        hover
          ? (ev) => ev.pointerType === "mouse" && later(false, CLOSE_DELAY)
          : undefined
      }
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

/** The links of one system, with its sub-headings (the developer tools), or the administrator's suspension message. */
function SystemLinks({ group }: { group: NavGroup }) {
  const { t } = useTranslation();
  if (group.suspended)
    return (
      <p className="nav-system__suspended" role="note">
        <Icon name="lockOpen" size={16} /> {t("nav.suspended")}: {group.suspended}
      </p>
    );
  const plain = group.items.filter((i) => !i.section);
  const sections = [...new Set(group.items.flatMap((i) => (i.section ? [i.section] : [])))];
  return (
    <>
      <ul>
        {plain.map((entry) => (
          <li key={entry.to}>
            <NavItem entry={entry} />
          </li>
        ))}
      </ul>
      {sections.map((s) => (
        <div key={s} className="nav-system__section">
          <p className="nav-system__subtitle">{t(`nav.section.${s}`)}</p>
          <ul>
            {group.items
              .filter((i) => i.section === s)
              .map((entry) => (
                <li key={entry.to}>
                  <NavItem entry={entry} />
                </li>
              ))}
          </ul>
        </div>
      ))}
    </>
  );
}

function SystemTitle({ group }: { group: NavGroup }) {
  return (
    <p className="nav-system__title">
      <IconTile name={group.icon} tone={group.tone} size="sm" />
      <span>
        {group.number !== undefined && <span className="nav-system__number">{group.number}.</span>} {group.label}
      </span>
    </p>
  );
}

export interface NavBlock {
  key: string;
  icon: IconName;
  tone: Tone;
  label: string;
  systems: NavGroup[];
}

/** The systems in their blocks, in the order given (the administrator's order); a block with no system dropped. */
export function navBlocks(groups: readonly NavGroup[], lang: Language = currentLanguage()): NavBlock[] {
  const out: NavBlock[] = [];
  for (const g of groups) {
    let block = out.find((b) => b.key === g.block);
    if (!block) {
      const spec = MENU.blocks.find((b) => b.key === g.block);
      block = {
        key: g.block,
        icon: spec?.icon ?? g.icon,
        tone: spec?.tone ?? g.tone,
        label: spec ? localized(spec.names, lang) : g.label,
        systems: [],
      };
      out.push(block);
    }
    block.systems.push(g);
  }
  return out;
}

function BlockMenu({ block, rail }: { block: NavBlock; rail: boolean }) {
  const { pathname } = useLocation();
  const only = block.systems.length === 1 && block.systems[0]?.items.length === 1 ? block.systems[0].items[0] : undefined;
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
      panelClassName={`nav-group__panel nav-block__panel nav-block__panel--${Math.min(block.systems.length, 4)}`}
      active={block.systems.some((g) => isActive(g, pathname))}
      label={
        <>
          <IconTile name={block.icon} tone={block.tone} size="sm" />
          <span className="nav-group__label">{block.label}</span>
          {!rail && <Icon name="expandMore" size={18} />}
        </>
      }
    >
      <p className="nav-group__title" aria-hidden="true">
        {block.label}
      </p>
      <div className="nav-block__systems">
        {block.systems.map((g) => (
          <section key={g.key} className="nav-system" aria-label={g.label} data-system={g.key}>
            <SystemTitle group={g} />
            <SystemLinks group={g} />
          </section>
        ))}
      </div>
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
  const { t, i18n } = useTranslation();
  const side = position !== "top";
  const blocks = navBlocks(groups, isLanguage(i18n.language) ? i18n.language : "ar");
  return (
    <nav
      aria-label={t("nav.main")}
      className={`main-nav main-nav--${shape} main-nav--${side ? "side" : "top"}`}
    >
      {shape === "grouped"
        ? blocks.map((b) => <BlockMenu key={b.key} block={b} rail={side} />)
        : groups.map((g) =>
            side ? (
              <section key={g.key} className="main-nav__section" aria-label={g.label}>
                <p className="main-nav__heading" aria-hidden="true">
                  {g.number !== undefined ? `${g.number}. ` : ""}
                  {g.label}
                </p>
                {g.suspended ? (
                  <SystemLinks group={g} />
                ) : (
                  g.items.map((entry) => <NavItem key={entry.to} entry={entry} />)
                )}
              </section>
            ) : (
              // At the top and flat, a page shown in two systems (an alias) is shown once.
              g.items
                .filter((entry) => groups.find((o) => o.items.some((i) => i.to === entry.to)) === g)
                .map((entry) => <NavItem key={`${g.key}:${entry.to}`} entry={entry} />)
            ),
          )}
    </nav>
  );
}
