import { useMemo } from "react";
import { useAuth } from "../context/auth";
import { useFilters } from "../context/filters";
import type { ReportFilters } from "../lib/filters";

/** Shared filters, minus the gouvernorat choice for users who are not national (the token's scope applies). */
export function useEffectiveFilters(): { filters: ReportFilters; national: boolean } {
  const { filters } = useFilters();
  const { user } = useAuth();
  const national = user?.identity.national ?? false;
  const effective = useMemo(() => (national ? filters : { ...filters, gouvernorats: [] }), [filters, national]);
  return { filters: effective, national };
}
