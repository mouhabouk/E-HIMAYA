// The dashboard menu read from its one source, menu.json (Yamen 2026-11-13: 20 systems in 4 blocks). The same file
// feeds the API's features catalogue, the atlas, the spider web, the mind maps and the UI reference workbook
// (scripts/menu). Each entry names a gate: the role rule that shows it, kept here because it is code.
import type { StaffIdentity as Identity } from "../auth/identity";
import type { IconName, Tone } from "../components/Icon";
import type { Language } from "../i18n";
import { canReadSystemTrail } from "../lib/systemApi";
import { canUseSqlConsole } from "../lib/sqlApi";
import { canUseDevTools } from "../lib/repoMap";
import {
  canEditAiSettings,
  canReadModelCards,
  canOpenLearning,
  canEditTips,
  canHandleContact,
  canManageAccounts,
  canManageMedicalCommittee,
  canManagePermissions,
  canMonitorPerformance,
  canOpenAxes,
  canOpenDisasters,
  canOpenBreakGlass,
  canOpenCoastal,
  canOpenCommand,
  canManageFieldAgents,
  canOpenCrew,
  canOpenInventory,
  canOpenLayers,
  canOpenProgrammes,
  canOpenRegister,
  canOpenSchedule,
  canOpenSnacr,
  canOpenWindowFull,
  canReadAnalytics,
  canReadKnowledge,
  canReadOrgs,
  canReadPersonnel,
  canManageInspections,
  canReadInspectionResults,
  canAdministerInspections,
  canReviewOrgs,
  canReadPlatformSettings,
  canReadResources,
  canReadRewards,
  canReadScopedAudit,
  canReviewDoctors,
  canReviewWeatherSuggestions,
  canSeeNationalQueues,
  canUseNotifications,
  hasReadAccess,
  canOpenMap,
  isCommittee,
  canReadAddressWarnings,
  canReadLiaison,
  canReadPar,
  canReadCallCards,
  canReadRoomGuide,
  canReadCoverage,
  canReadFleet,
} from "../lib/roles";
import source from "./menu.json";

export type Names = Record<Language, string>;

export interface MenuItemSpec {
  key: string;
  path: string;
  end?: boolean;
  icon: IconName;
  tone: Tone;
  gate: GateName;
  /** A screen still to build: kept out of the menu, listed in the atlas and the admin's systems page. */
  planned?: boolean;
  /** The request or idea it answers (OS4, OS13 ...), for a planned entry. */
  ref?: string;
  /** Also shown here, its own place being the named system (the rewards under the organisations). */
  alias?: string;
  /** A sub-heading inside the system (the developer tools inside the settings). */
  section?: string;
  /** A tab of another entry's page, not a link of its own (Yamen 2026-11-13: «سجل الموارد» inside «الموارد»). */
  tabOf?: string;
}

export interface SystemSpec {
  key: string;
  number: number;
  names: Names;
  icon: IconName;
  tone: Tone;
  items: MenuItemSpec[];
}

export interface BlockSpec {
  key: string;
  names: Names;
  icon: IconName;
  tone: Tone;
  systems: SystemSpec[];
}

export interface GateContext {
  /** The decision window is open to the caller (it can be opened to more people for a crisis). */
  windowOpen?: boolean;
}

type Gate = (who: Identity, ctx: GateContext) => boolean;

const r = (f: (roles: readonly string[]) => boolean): Gate => (who) => f(who.roles);
const admin: Gate = (who) => who.national && who.roles.includes("sysadmin");

/** The role rule of each gate name used in menu.json (the API enforces the same rules on every route). */
export const GATES = {
  always: () => true,
  // Shown only when the administrator grants it (L5a: the drill is dormant until then).
  granted: () => false,
  sysadmin: admin,
  reads: r(hasReadAccess),
  map: r(canOpenMap),
  callCards: r(canReadCallCards),
  nationalQueues: (who) => canSeeNationalQueues(who),
  roomGuide: r(canReadRoomGuide),
  crew: r(canOpenCrew),
  fieldAgents: r(canManageFieldAgents),
  schedule: r(canOpenSchedule),
  coverage: r(canReadCoverage),
  par: r(canReadPar),
  addressWarnings: r(canReadAddressWarnings),
  layers: r(canOpenLayers),
  weatherSuggestions: r(canReviewWeatherSuggestions),
  coastal: r(canOpenCoastal),
  modelCards: (who) => canReadModelCards(who),
  window: (who, ctx) => ctx.windowOpen ?? canOpenWindowFull(who),
  command: r(canOpenCommand),
  committee: r((roles) => isCommittee(roles) || canMonitorPerformance(roles)),
  analytics: r(canReadAnalytics),
  snacr: r(canOpenSnacr),
  register: r(canOpenRegister),
  programmes: r(canOpenProgrammes),
  disasters: r(canOpenDisasters),
  axes: r(canOpenAxes),
  liaison: r(canReadLiaison),
  personnel: r(canReadPersonnel),
  fleet: r(canReadFleet),
  resources: r(canReadResources),
  // «الموارد» and «سجل الموارد» are one page with two tabs (Yamen 2026-11-13).
  resourcesHub: r((roles) => canReadResources(roles) || canOpenInventory(roles)),
  inventory: r(canOpenInventory),
  inspections: r(canManageInspections),
  inspectionResults: r(canReadInspectionResults),
  inspectionAdmin: r(canAdministerInspections),
  knowledge: r(canReadKnowledge),
  learning: (who) => canOpenLearning(who),
  orgs: r(canReadOrgs),
  reviewOrgs: r(canReviewOrgs),
  rewards: r(canReadRewards),
  doctors: r(canReviewDoctors),
  medicalCommittee: (who) => canManageMedicalCommittee(who),
  notifications: r(canUseNotifications),
  tips: r(canEditTips),
  contact: r(canHandleContact),
  platformSettings: r(canReadPlatformSettings),
  aiSettings: (who) => hasReadAccess(who.roles) || canEditAiSettings(who),
  accounts: (who) => canManageAccounts(who),
  permissions: (who) => canManagePermissions(who),
  breakGlass: (who) => canOpenBreakGlass(who),
  audit: (who) => canReadScopedAudit(who),
  systemTrail: (who) => canReadSystemTrail(who),
  sql: (who) => canUseSqlConsole(who),
  devTools: (who) => canUseDevTools(who),
} satisfies Record<string, Gate>;

export type GateName = keyof typeof GATES;

export interface MenuSource {
  version: number;
  home: MenuItemSpec;
  blocks: BlockSpec[];
}

export const MENU = source as unknown as MenuSource;

export const SYSTEMS: readonly SystemSpec[] = MENU.blocks.flatMap((b) => b.systems);

/** The block each system belongs to. */
export const BLOCK_OF: Readonly<Record<string, string>> = Object.fromEntries(
  MENU.blocks.flatMap((b) => b.systems.map((s) => [s.key, b.key])),
);

/** The system of a menu path (its own place, not an alias); undefined for the home page or an unknown path. */
export function systemOfPath(path: string): SystemSpec | undefined {
  return SYSTEMS.find((s) => s.items.some((i) => i.path === path && !i.alias));
}

export function gateAllows(gate: GateName, who: Identity, ctx: GateContext = {}): boolean {
  return GATES[gate](who, ctx);
}
