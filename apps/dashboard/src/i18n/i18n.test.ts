import { describe, expect, it } from "vitest";
import { ERROR_CODES } from "../lib/api";
import { READ_ROLES } from "../lib/roles";
import { CATEGORIES, REPORT_STATUSES } from "../lib/types";
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
      ...READ_ROLES.map((r) => `roles.${r}`),
      ...ERROR_CODES.map((c) => `errors.${c}`),
    ];
    for (const key of required) {
      expect(arKeys.has(key), key).toBe(true);
      expect(frKeys.has(key), key).toBe(true);
    }
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
