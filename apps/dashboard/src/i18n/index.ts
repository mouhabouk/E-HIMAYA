import i18next, { type i18n } from "i18next";
import { initReactI18next } from "react-i18next";
import ar from "./ar.json";
import fr from "./fr.json";

export const LANGUAGES = ["ar", "fr"] as const;
export type Language = (typeof LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = "ar";
const STORAGE_KEY = "ehimaya.lang";

export function isLanguage(v: unknown): v is Language {
  return typeof v === "string" && (LANGUAGES as readonly string[]).includes(v);
}

export function directionOf(lang: Language): "rtl" | "ltr" {
  return lang === "ar" ? "rtl" : "ltr";
}

export function applyDocumentLanguage(lang: Language, doc: Document = document): void {
  doc.documentElement.lang = lang;
  doc.documentElement.dir = directionOf(lang);
  doc.title = lang === "ar" ? ar.app.documentTitle : fr.app.documentTitle;
}

function storedLanguage(): Language {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return isLanguage(v) ? v : DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

export function persistLanguage(lang: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* storage unavailable: the choice lasts for this tab only */
  }
}

export function currentLanguage(instance: i18n): Language {
  return isLanguage(instance.resolvedLanguage) ? instance.resolvedLanguage : DEFAULT_LANGUAGE;
}

export function createI18n(lang: Language = storedLanguage()): i18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources: { ar: { translation: ar }, fr: { translation: fr } },
    lng: lang,
    fallbackLng: false,
    supportedLngs: LANGUAGES,
    interpolation: { escapeValue: false },
    returnNull: false,
    initAsync: false,
  });
  instance.on("languageChanged", (lng) => {
    if (!isLanguage(lng)) return;
    applyDocumentLanguage(lng);
    persistLanguage(lng);
  });
  applyDocumentLanguage(lang);
  return instance;
}
