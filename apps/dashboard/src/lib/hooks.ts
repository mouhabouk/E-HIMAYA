import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { currentLanguage, type Language } from "../i18n";
import { createFormatters, type Formatters } from "./format";
import { queryKeys } from "./staffApi";
import type { Gouvernorat } from "./types";

export function useLanguage(): Language {
  const { i18n } = useTranslation();
  return currentLanguage(i18n);
}

export function useFormat(): Formatters {
  const lang = useLanguage();
  return useMemo(() => createFormatters(lang), [lang]);
}

/** Reference list of the 24 gouvernorats (both names are returned, so one fetch serves both languages). */
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
  return { list: query.data ?? [], nameOf, isLoading: query.isLoading };
}

export function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
