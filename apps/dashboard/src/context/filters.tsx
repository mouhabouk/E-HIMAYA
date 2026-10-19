import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_FILTERS, isPeriod, type ReportFilters } from "../lib/filters";
import { isCategory, isReportStatus } from "../lib/types";

const STORAGE_KEY = "ehimaya.filters";

interface FiltersContextValue {
  filters: ReportFilters;
  setFilters: (update: Partial<ReportFilters>) => void;
  reset: () => void;
}

const FiltersContext = createContext<FiltersContextValue | null>(null);

function load(): ReportFilters {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_FILTERS;
    const v = JSON.parse(raw) as Partial<Record<keyof ReportFilters, unknown>>;
    return {
      statuses: Array.isArray(v.statuses) ? v.statuses.filter(isReportStatus) : [],
      categories: Array.isArray(v.categories) ? v.categories.filter(isCategory) : [],
      gouvernorat: typeof v.gouvernorat === "number" ? v.gouvernorat : null,
      period: isPeriod(v.period) ? v.period : DEFAULT_FILTERS.period,
      q: typeof v.q === "string" ? v.q : "",
    };
  } catch {
    return DEFAULT_FILTERS;
  }
}

function save(f: ReportFilters): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(f));
  } catch {
    /* ignore */
  }
}

/** Filters shared by the incidents list and the live map (kept for the browser tab session). */
export function FiltersProvider({ children, initial }: { children: ReactNode; initial?: ReportFilters }) {
  const [filters, setState] = useState<ReportFilters>(() => initial ?? load());

  const setFilters = useCallback((update: Partial<ReportFilters>) => {
    setState((prev) => {
      const next = { ...prev, ...update };
      save(next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    save(DEFAULT_FILTERS);
    setState(DEFAULT_FILTERS);
  }, []);

  const value = useMemo(() => ({ filters, setFilters, reset }), [filters, setFilters, reset]);
  return <FiltersContext value={value}>{children}</FiltersContext>;
}

export function useFilters(): FiltersContextValue {
  const v = useContext(FiltersContext);
  if (!v) throw new Error("FiltersProvider missing");
  return v;
}
