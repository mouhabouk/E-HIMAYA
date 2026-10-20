import type { Language } from "../i18n";

/** Texts the API returns per language (`{ar, fr}`, sometimes `{ar, fr, en}`); any entry may be missing or empty. */
export type TextByLanguage = Partial<Record<Language, string | null | undefined>>;

/**
 * Order in which the languages of an API text are tried for each interface language (phase 9 §8): English falls back
 * to French then Arabic (most free texts have no English), French to Arabic, Arabic to French.
 */
export const TEXT_FALLBACK: Readonly<Record<Language, readonly Language[]>> = {
  ar: ["ar", "fr", "en"],
  fr: ["fr", "ar", "en"],
  en: ["en", "fr", "ar"],
};

/** Text of an API value in the interface language, with the fallback order above; a plain string is kept as is. */
export function localized(text: TextByLanguage | string | null | undefined, lang: Language): string {
  if (!text) return "";
  if (typeof text === "string") return text;
  for (const l of TEXT_FALLBACK[lang]) {
    const v = text[l];
    if (v && v.trim()) return v;
  }
  return "";
}

/** Language actually shown by `localized` (for the `lang`/`dir` attributes of the element), or null when empty. */
export function localizedLanguage(text: TextByLanguage | null | undefined, lang: Language): Language | null {
  if (!text) return null;
  return TEXT_FALLBACK[lang].find((l) => Boolean(text[l]?.trim())) ?? null;
}

/** A name the API gives as `name_ar`/`name_fr` (and `name_en` from phase 9 on), in the interface language. */
export function localizedName(
  v: { name_ar?: string | null; name_fr?: string | null; name_en?: string | null },
  lang: Language,
): string {
  return localized({ ar: v.name_ar, fr: v.name_fr, en: v.name_en }, lang);
}
