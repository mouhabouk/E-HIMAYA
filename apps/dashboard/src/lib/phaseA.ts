/**
 * Phase A national settings (docs/phase-a/design.md §2.4, §2.6): the mobile release offered to the phones
 * (`app.release`) and the extra offensive words (`moderation.extra_terms`). The checks mirror the API
 * (`services/api/app/modules/settings/domain.py`) so the form explains a refusal before sending it.
 */

export const LANGS = ["ar", "fr", "en"] as const;
export type Lang = (typeof LANGS)[number];

export const BUILD_RANGE = { min: 1, max: 1_000_000 } as const;
export const NOTES_MAX = 2000;
export const TERMS_MAX = 500;
export const TERM_LENGTH = { min: 2, max: 64 } as const;

export interface AppReleaseValue {
  latest_version: string;
  latest_build: number;
  min_build: number;
  notes: Record<Lang, string>;
  channel: "server" | "play";
  download_url: string | null;
}

export type ReleaseError = "version" | "build" | "order" | "url" | "urlMissing" | "notes";

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** The stored value, or the API default when it is missing or malformed. */
export function releaseFrom(value: unknown): AppReleaseValue {
  const v = isRecord(value) ? value : {};
  const notes = isRecord(v.notes) ? v.notes : {};
  return {
    latest_version: typeof v.latest_version === "string" ? v.latest_version : "0.2.0",
    latest_build: typeof v.latest_build === "number" ? v.latest_build : 1,
    min_build: typeof v.min_build === "number" ? v.min_build : 1,
    notes: {
      ar: typeof notes.ar === "string" ? notes.ar : "",
      fr: typeof notes.fr === "string" ? notes.fr : "",
      en: typeof notes.en === "string" ? notes.en : "",
    },
    channel: v.channel === "play" ? "play" : "server",
    download_url: typeof v.download_url === "string" && v.download_url !== "" ? v.download_url : null,
  };
}

const inBuildRange = (n: number) => Number.isInteger(n) && n >= BUILD_RANGE.min && n <= BUILD_RANGE.max;

export function validateRelease(v: AppReleaseValue): ReleaseError | null {
  if (!/^\d+\.\d+\.\d+$/.test(v.latest_version)) return "version";
  if (!inBuildRange(v.latest_build) || !inBuildRange(v.min_build)) return "build";
  if (v.min_build > v.latest_build) return "order";
  if (v.download_url !== null && (!v.download_url.startsWith("https://") || v.download_url.length > 500)) return "url";
  if (v.channel === "server" && v.latest_build > 1 && !v.download_url) return "urlMissing";
  if (LANGS.some((l) => v.notes[l].length > NOTES_MAX)) return "notes";
  return null;
}

export function termsFrom(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((t): t is string => typeof t === "string") : [];
}

export type TermsError = "length" | "count";

/** One word or expression per line; blank lines ignored, duplicates removed, like the API. */
export function parseTerms(text: string): { terms: string[]; error: TermsError | null } {
  const terms: string[] = [];
  for (const line of text.split("\n")) {
    const term = line.trim();
    if (term === "") continue;
    if (term.length < TERM_LENGTH.min || term.length > TERM_LENGTH.max) return { terms, error: "length" };
    if (!terms.includes(term)) terms.push(term);
  }
  return { terms, error: terms.length > TERMS_MAX ? "count" : null };
}
