import { describe, expect, it } from "vitest";
import { ERROR_CODES } from "../lib/api";
import {
  ALERT_KINDS,
  CATEGORIES,
  CERTIFICATE_STATUSES,
  DOCUMENT_KINDS,
  EQUIPMENT_KINDS,
  FAMILIES,
  FEATURE_KINDS,
  HAZMAT_UNITS,
  MAINTENANCE_STATUSES,
  ORG_KINDS,
  ORG_ROLES,
  ORG_STATUSES,
  REPORT_STATUSES,
  REQUIREMENTS,
  TRAINING_STATUSES,
  VERSION_STATUSES,
} from "../lib/types";
import { KIND_FIELDS } from "../lib/kindFields";
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

const files = { ar: flatten(ar), fr: flatten(fr), en: flatten(en) };

function placeholders(s: unknown): string[] {
  return typeof s === "string" ? [...s.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1] ?? "").sort() : [];
}

describe("translation files", () => {
  it("have identical key sets in ar, fr and en", () => {
    const keys = [...files.ar.keys()].sort();
    expect([...files.fr.keys()].sort()).toEqual(keys);
    expect([...files.en.keys()].sort()).toEqual(keys);
  });

  it("have non-empty string values only", () => {
    for (const map of Object.values(files)) {
      for (const [key, value] of map) {
        expect(typeof value, key).toBe("string");
        expect((value as string).trim(), key).not.toBe("");
      }
    }
  });

  it("use the same interpolation placeholders in every language", () => {
    for (const [key, value] of files.en) {
      expect(placeholders(files.ar.get(key)), key).toEqual(placeholders(value));
      expect(placeholders(files.fr.get(key)), key).toEqual(placeholders(value));
    }
  });

  it("cover every code of the contract (statuses, kinds, roles, errors…)", () => {
    const required = [
      ...REPORT_STATUSES.map((s) => `status.${s}`),
      ...CATEGORIES.map((c) => `category.${c}`),
      ...ORG_STATUSES.map((s) => `orgStatus.${s}`),
      ...ORG_KINDS.map((k) => `kinds.${k}`),
      ...ORG_ROLES.flatMap((r) => [`roles.${r}`, `roleHelp.${r}`]),
      ...FAMILIES.map((f) => `family.${f}`),
      ...REQUIREMENTS.map((r) => `requirements.${r}`),
      ...ALERT_KINDS.map((a) => `alerts.kinds.${a}`),
      ...TRAINING_STATUSES.map((s) => `training.${s}`),
      ...MAINTENANCE_STATUSES.map((s) => `maintenance.${s}`),
      ...EQUIPMENT_KINDS.map((k) => `equipmentKinds.${k}`),
      ...HAZMAT_UNITS.map((u) => `units.${u}`),
      ...FEATURE_KINDS.map((k) => `featureKinds.${k}`),
      ...DOCUMENT_KINDS.map((k) => `documentKinds.${k}`),
      ...VERSION_STATUSES.map((s) => `versionStatus.${s}`),
      ...CERTIFICATE_STATUSES.map((s) => `certificateStatus.${s}`),
      ...ERROR_CODES.map((c) => `errors.${c}`),
      "charter.versions.2026-10.body",
      "charter.versions.2026-10.checkbox",
    ];
    for (const key of required) {
      for (const [lang, map] of Object.entries(files)) expect(map.has(key), `${lang}: ${key}`).toBe(true);
    }
  });

  it("use the contract's official labels", () => {
    expect(ar.status).toEqual({
      received: "مستلم",
      in_progress: "قيد المعالجة",
      intervened: "تم التدخل",
      ongoing: "التدخل متواصل",
      closed: "أُغلق التدخل",
      rejected: "مرفوض",
    });
    expect(Object.values(en.status)).toEqual(["Received", "Being processed", "Intervened", "Intervention ongoing", "Closed", "Rejected"]);
    // Twelve kinds since P2a (addition 12, working list [SIM]), in the order of ORG_KINDS, with their fields' labels.
    for (const dict of [ar, fr, en]) {
      expect(Object.keys(dict.kinds)).toEqual([...ORG_KINDS]);
      for (const specs of Object.values(KIND_FIELDS)) for (const f of specs) expect(dict.kindField).toHaveProperty(f.key);
    }
    expect(ar.kinds).toMatchObject({ health: "صحية", education: "تربوية", tourism: "سياحية", other: "أخرى" });
  });

  it("mark the charter text as a placeholder in every language", () => {
    expect(en.charter.versions["2026-10"].placeholderNotice).toMatch(/PLACEHOLDER/);
    expect(fr.charter.versions["2026-10"].placeholderNotice).toMatch(/PROVISOIRE/);
    expect(ar.charter.versions["2026-10"].placeholderNotice).toMatch(/مؤقت/);
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
    expect(document.documentElement.dir).toBe("rtl");
    await i18n.changeLanguage("en");
    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.title).toBe(en.app.documentTitle);
    expect(localStorage.getItem("ehimaya.portal.lang")).toBe("en");
    await i18n.changeLanguage("ar");
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("restores the persisted language", () => {
    localStorage.setItem("ehimaya.portal.lang", "fr");
    const i18n = createI18n();
    expect(i18n.language).toBe("fr");
    expect(document.documentElement.dir).toBe("ltr");
    applyDocumentLanguage("ar");
  });
});
