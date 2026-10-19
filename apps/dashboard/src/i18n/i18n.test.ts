import { describe, expect, it } from "vitest";
import { ERROR_CODES } from "../lib/api";
import { STAFF_ROLES } from "../lib/roles";
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
import ar from "./ar.json";
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

function placeholders(s: unknown): string[] {
  return typeof s === "string" ? [...s.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1] ?? "").sort() : [];
}

describe("translation files", () => {
  it("have identical key sets in ar and fr", () => {
    expect([...arKeys.keys()].sort()).toEqual([...frKeys.keys()].sort());
  });

  it("have non-empty string values only", () => {
    for (const [key, value] of [...arKeys, ...frKeys]) {
      expect(typeof value, key).toBe("string");
      expect((value as string).trim(), key).not.toBe("");
    }
  });

  it("use the same interpolation placeholders in both languages", () => {
    for (const [key, value] of arKeys) {
      expect(placeholders(frKeys.get(key)), key).toEqual(placeholders(value));
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

  it("use the contract's labels for institution kinds and keep «الحوادث» for grouped incidents only", () => {
    expect(ar.orgs.kind).toMatchObject({ industrial: "صناعية", educational: "تعليمية", hotel: "نزل", government: "حكومية", private: "خاصة", other: "أخرى" });
    expect(fr.orgs.kind).toMatchObject({
      industrial: "Industrielle",
      educational: "Éducative",
      hotel: "Hôtel",
      government: "Administration publique",
      private: "Privée",
      other: "Autre",
    });
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

describe("document language and direction", () => {
  it("maps languages to directions", () => {
    expect(directionOf("ar")).toBe("rtl");
    expect(directionOf("fr")).toBe("ltr");
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
