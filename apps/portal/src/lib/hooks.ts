import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { currentLanguage, type Language } from "../i18n";
import { createFormatters, type Formatters } from "./format";
import { queryKeys } from "./portalApi";
import type { Gouvernorat } from "./types";

export function useLanguage(): Language {
  const { i18n } = useTranslation();
  return currentLanguage(i18n);
}

export function useFormat(): Formatters {
  const lang = useLanguage();
  return useMemo(() => createFormatters(lang), [lang]);
}

/** Gouvernorat names (public reference; English uses the official French transliteration, as the API does). */
export function useGouvernorats() {
  const { api } = useServices();
  const lang = useLanguage();
  const query = useQuery({
    queryKey: queryKeys.gouvernorats,
    queryFn: ({ signal }) => api.gouvernorats(signal),
    staleTime: Infinity,
    gcTime: Infinity,
  });
  const nameOf = useMemo(() => {
    const byCode = new Map<number, Gouvernorat>((query.data ?? []).map((g) => [g.code, g]));
    return (code: number | null | undefined): string | null => {
      if (code === null || code === undefined) return null;
      const g = byCode.get(code);
      if (!g) return String(code);
      return lang === "ar" ? g.name_ar : g.name_fr;
    };
  }, [query.data, lang]);
  return { nameOf };
}

/** Stable id for idempotent creations (report `client_uuid`). */
export function newUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = ((b[6] ?? 0) & 0x0f) | 0x40;
  b[8] = ((b[8] ?? 0) & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
