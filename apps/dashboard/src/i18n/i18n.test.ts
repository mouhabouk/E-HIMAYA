import { describe, expect, it } from "vitest";
import { ERROR_CODES } from "../lib/api";
import {
  BADGE_STATUSES,
  BADGES,
  LIBRARY_KINDS,
  LIBRARY_REPORT_KINDS,
  LIBRARY_REPORT_STATUSES,
  MEMORY_ACCESS,
  MEMORY_SECTIONS,
  MEMORY_STATUSES,
  NOMINATION_KINDS,
  NOMINATION_STATUSES,
  REPORT_FORMATS,
  REPORT_SOURCES,
  RESPONSE_STAGES,
  REWARD_REASONS,
  SCENARIO_WEATHERS,
  SCHEDULE_FREQUENCIES,
  SUBJECT_KINDS,
  TREE_AXES,
  TREND_INTERVALS,
  TREND_METRICS,
  VERSION_CHANGES,
} from "../lib/phase8Types";
import { STAFF_ROLES } from "../lib/roles";
import { KIND_FIELDS } from "../lib/kindFields";
import {
  CATEGORIES,
  DOCUMENT_KINDS,
  EQUIPMENT_KINDS,
  FEATURE_KINDS,
  HAZMAT_UNITS,
  MAINTENANCE_STATUSES,
  MEMBER_ROLES,
  ORG_ALERT_KINDS,
  ORG_CERTIFICATE_STATES,
  ORG_DECISIONS,
  ORG_FAMILIES,
  ORG_KINDS,
  ORG_STATUSES,
  REPORT_STATUSES,
  REQUIREMENTS,
  SENSITIVE_REASONS,
  TEAM_ROLES,
  TRAINING_STATUSES,
} from "../lib/types";
import { DETECTION_LABELS, STREAM_END_REASONS, STREAM_SOURCES, STREAM_STATUSES } from "../lib/streamTypes";
import {
  BREAKGLASS_STATUSES,
  BREAKGLASS_TARGETS,
  COMMAND_LEVELS,
  ESCALATION_KINDS,
  ESCALATION_STATES,
  GEO_REASONS,
  GEO_STATES,
  PHASE9_TIMELINE_KINDS,
  RESOURCE_REQUEST_STATUSES,
  REVIEW_OUTCOMES,
  SCOPE_LEVELS,
  SLA_BANDS,
} from "../lib/phase9Types";
import ar from "./ar.json";
import en from "./en.json";
import fr from "./fr.json";
import { applyDocumentLanguage, createI18n, directionOf } from "./index";

function flatten(obj: unknown, prefix = ""): Map<string, unknown> {
  const out = new Map<string, unknown>();
  if (obj && typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      const key = prefix ? `${prefix}.${k}` : k;
      if (v && typeof v === "object") for (const [kk, vv] of flatten(v, key)) out.set(kk, vv);
      else out.set(key, v);
    }
  }
  return out;
}

const arKeys = flatten(ar);
const frKeys = flatten(fr);
const enKeys = flatten(en);

function placeholders(s: unknown): string[] {
  return typeof s === "string" ? [...s.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1] ?? "").sort() : [];
}

describe("translation files", () => {
  it("have identical key sets in ar, fr and en", () => {
    expect([...arKeys.keys()].sort()).toEqual([...frKeys.keys()].sort());
    expect([...enKeys.keys()].sort()).toEqual([...arKeys.keys()].sort());
  });

  it("have non-empty string values only", () => {
    for (const [key, value] of [...arKeys, ...frKeys, ...enKeys]) {
      expect(typeof value, key).toBe("string");
      expect((value as string).trim(), key).not.toBe("");
    }
  });

  it("use the same interpolation placeholders in the three languages", () => {
    for (const [key, value] of arKeys) {
      expect(placeholders(frKeys.get(key)), key).toEqual(placeholders(value));
      expect(placeholders(enKeys.get(key)), key).toEqual(placeholders(value));
    }
  });

  it("cover every code of the phase 9 contract (rooms, SLA, geography, escalation, break-glass)", () => {
    const required = [
      ...SLA_BANDS.map((b) => `sla.band.${b}`),
      ...GEO_STATES.map((g) => `geo.state.${g}`),
      ...GEO_REASONS.map((r) => `geo.reasonCode.${r}`),
      ...ESCALATION_STATES.map((e) => `escalation.state.${e}`),
      ...ESCALATION_KINDS.map((e) => `escalation.kind.${e}`),
      ...COMMAND_LEVELS.map((l) => `command.level.${l}`),
      ...COMMAND_LEVELS.map((l) => `command.levelHelp.${l}`),
      ...RESOURCE_REQUEST_STATUSES.map((r) => `resourceRequests.status.${r}`),
      ...BREAKGLASS_TARGETS.map((b) => `breakGlass.target.${b}`),
      ...BREAKGLASS_STATUSES.map((b) => `breakGlass.status.${b}`),
      ...REVIEW_OUTCOMES.map((o) => `breakGlass.review.${o}`),
      ...SCOPE_LEVELS.map((l) => `accounts.scopeLevel.${l}`),
      ...PHASE9_TIMELINE_KINDS.map((k) => `incidents.timeline.${k}`),
    ];
    for (const key of required) {
      for (const keys of [arKeys, frKeys, enKeys]) expect(keys.has(key), key).toBe(true);
    }
  });

  it("cover every status, category, role and error code of the contract", () => {
    const required = [
      ...REPORT_STATUSES.map((s) => `status.${s}`),
      ...CATEGORIES.map((c) => `category.${c}`),
      ...STAFF_ROLES.map((r) => `roles.${r}`),
      ...ERROR_CODES.map((c) => `errors.${c}`),
    ];
    for (const key of required) {
      expect(arKeys.has(key), key).toBe(true);
      expect(frKeys.has(key), key).toBe(true);
    }
  });

  it("cover every institution enum of the phase 4 contract", () => {
    const required = [
      "nav.orgs",
      "nav.certificates",
      ...ORG_STATUSES.map((s) => `orgs.status.${s}`),
      ...ORG_KINDS.map((k) => `orgs.kind.${k}`),
      ...ORG_FAMILIES.map((f) => `orgs.family.${f}`),
      ...ORG_CERTIFICATE_STATES.map((c) => `orgs.certificate.${c}`),
      ...REQUIREMENTS.map((r) => `orgs.requirement.${r}`),
      ...ORG_ALERT_KINDS.map((a) => `orgs.alertKind.${a}`),
      ...TRAINING_STATUSES.map((s) => `orgs.trainingStatus.${s}`),
      ...TEAM_ROLES.map((r) => `orgs.teamRole.${r}`),
      ...EQUIPMENT_KINDS.map((k) => `orgs.equipmentKind.${k}`),
      ...MAINTENANCE_STATUSES.map((s) => `orgs.maintenanceStatus.${s}`),
      ...FEATURE_KINDS.map((k) => `orgs.featureKind.${k}`),
      ...DOCUMENT_KINDS.map((k) => `orgs.docKind.${k}`),
      ...MEMBER_ROLES.map((r) => `orgs.memberRole.${r}`),
      ...HAZMAT_UNITS.map((u) => `orgs.units.${u}`),
      ...ORG_DECISIONS.map((d) => `orgs.review.decision.${d}`),
      ...ORG_DECISIONS.map((d) => `orgs.review.confirmText.${d}`),
      ...SENSITIVE_REASONS.map((r) => `ai.sensitive.reason.${r}`),
    ];
    for (const key of required) {
      expect(arKeys.has(key), key).toBe(true);
      expect(frKeys.has(key), key).toBe(true);
    }
  });

  it("cover every live stream enum of the phase 6 contract", () => {
    const required = [
      "nav.streams",
      "detail.mediaKind.recording",
      ...STREAM_STATUSES.map((s) => `streams.status.${s}`),
      ...STREAM_SOURCES.map((s) => `streams.source.${s}`),
      ...STREAM_END_REASONS.map((r) => `streams.endReason.${r}`),
      ...DETECTION_LABELS.map((l) => `streams.label.${l}`),
      ...["fire", "smoke"].map((l) => `streams.alerts.title.${l}`),
      ...["connecting", "playing", "reconnecting", "suspended", "forbidden", "unavailable", "ended", "idle"].map(
        (s) => `streams.player.${s}`,
      ),
    ];
    for (const key of required) {
      expect(arKeys.has(key), key).toBe(true);
      expect(frKeys.has(key), key).toBe(true);
    }
    expect(ar.nav.streams).toBe("البث المباشر");
    expect(fr.nav.streams).toBe("Diffusion en direct");
  });

  it("use the contract's labels for institution kinds and keep «الحوادث» for grouped incidents only", () => {
    // Twelve kinds since P2a (addition 12), each labelled in the three languages, with the labels of their fields.
    for (const dict of [ar, fr, en]) {
      expect(Object.keys(dict.orgs.kind)).toEqual([...ORG_KINDS]);
      for (const specs of Object.values(KIND_FIELDS)) {
        for (const s of specs) expect(dict.orgs.kindField).toHaveProperty(s.key);
      }
    }
    expect(ar.orgs.kind).toMatchObject({ industrial: "صناعية", education: "تربوية", tourism: "سياحية", other: "أخرى" });
    expect(fr.orgs.kind).toMatchObject({ industrial: "Industrielle", public_admin: "Administration publique", other: "Autre" });
    expect(ar.nav.orgs).toBe("المؤسسات");
    expect(ar.nav.incidents).toBe("الحوادث");
    expect(ar.nav.orgs).not.toBe(ar.nav.incidents);
  });

  it("use the contract's official status labels", () => {
    expect(ar.status).toEqual({
      received: "مستلم",
      in_progress: "قيد المعالجة",
      intervened: "تم التدخل",
      ongoing: "التدخل متواصل",
      closed: "أُغلق التدخل",
      rejected: "مرفوض",
    });
    expect(fr.status).toEqual({
      received: "Reçu",
      in_progress: "En cours de traitement",
      intervened: "Intervention effectuée",
      ongoing: "Intervention en cours",
      closed: "Intervention clôturée",
      rejected: "Rejeté",
    });
  });
});

describe("phase 8 translations", () => {
  it("cover every phase 8 enum (analytics, reports, memory, library, rewards)", () => {
    const required = [
      "nav.analytics",
      "nav.reportsLibrary",
      "nav.memory",
      "nav.library",
      "nav.rewards",
      ...TREND_METRICS.map((m) => `analytics.metric.${m}`),
      ...TREND_INTERVALS.map((i) => `analytics.interval.${i}`),
      ...RESPONSE_STAGES.map((s) => `analytics.responseTime.${s}`),
      ...REPORT_SOURCES.map((s) => `analytics.source.${s}`),
      ...[1, 2, 3, 4, 5, 6, 7].map((d) => `analytics.weekday.${d}`),
      ...[1, 2, 3, 4, 5, 6, 7].map((d) => `events.calendar.short.${d}`),
      ...SCENARIO_WEATHERS.map((w) => `scenarios.weather.${w}`),
      ...LIBRARY_REPORT_KINDS.map((k) => `library.reports.kinds.${k}`),
      ...LIBRARY_REPORT_STATUSES.map((s) => `library.reports.status.${s}`),
      ...REPORT_FORMATS.map((f) => `library.reports.formats.${f}`),
      ...SCHEDULE_FREQUENCIES.map((f) => `schedules.frequencies.${f}`),
      ...SCHEDULE_FREQUENCIES.map((f) => `schedules.cron.${f}`),
      ...MEMORY_STATUSES.map((s) => `memory.status.${s}`),
      ...MEMORY_ACCESS.map((a) => `memory.access.${a}`),
      ...MEMORY_SECTIONS.map((s) => `memory.section.${s}`),
      ...VERSION_CHANGES.map((c) => `memory.versions.change.${c}`),
      ...LIBRARY_KINDS.map((k) => `events.kind.${k}`),
      ...TREE_AXES.map((a) => `events.tree.axis.${a}`),
      ...REWARD_REASONS.map((r) => `rewards.reason.${r}`),
      ...BADGES.map((b) => `rewards.badge.${b}`),
      ...BADGE_STATUSES.map((s) => `rewards.badgeStatus.${s}`),
      ...NOMINATION_KINDS.map((k) => `rewards.nominationKind.${k}`),
      ...NOMINATION_STATUSES.map((s) => `rewards.nominationStatus.${s}`),
      ...SUBJECT_KINDS.map((k) => `rewards.nominations.subject.${k}`),
    ];
    for (const key of required) {
      expect(arKeys.has(key), key).toBe(true);
      expect(frKeys.has(key), key).toBe(true);
      expect(enKeys.has(key), key).toBe(true);
    }
  });
});

describe("document language and direction", () => {
  it("maps languages to directions", () => {
    expect(directionOf("ar")).toBe("rtl");
    expect(directionOf("fr")).toBe("ltr");
    expect(directionOf("en")).toBe("ltr");
  });

  it("sets <html lang dir> on start and on switch, and persists the choice", async () => {
    const i18n = createI18n("ar");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");

    await i18n.changeLanguage("fr");
    expect(document.documentElement.lang).toBe("fr");
    expect(document.documentElement.dir).toBe("ltr");
    expect(localStorage.getItem("ehimaya.lang")).toBe("fr");
    expect(document.title).toBe(fr.app.documentTitle);

    await i18n.changeLanguage("en");
    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.title).toBe(en.app.documentTitle);

    await i18n.changeLanguage("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(localStorage.getItem("ehimaya.lang")).toBe("ar");
  });

  it("restores the persisted language", () => {
    localStorage.setItem("ehimaya.lang", "fr");
    const i18n = createI18n();
    expect(i18n.language).toBe("fr");
    expect(document.documentElement.dir).toBe("ltr");
    applyDocumentLanguage("ar");
  });
});
