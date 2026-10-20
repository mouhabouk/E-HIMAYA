import type { LocalizedText } from "./phase8Types";

/** `{ar, fr}` text in the interface language, falling back to the other language when one is empty. */
export function localized(text: LocalizedText | null | undefined, lang: "ar" | "fr"): string {
  if (!text) return "";
  return lang === "fr" ? text.fr || text.ar : text.ar || text.fr;
}
