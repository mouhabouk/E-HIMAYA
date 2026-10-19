import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useGouvernorats } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import type { LevelRow, OpLevel } from "../lib/opsTypes";
import { canMonitorPerformance, isCommittee } from "../lib/roles";

/** Gouvernorats at crisis or disaster level that concern the user (national: all; regional: its own). */
export function raisedLevels(
  rows: readonly LevelRow[],
  identity: { national: boolean; gouvernoratCode: number | null },
): Record<Exclude<OpLevel, "normal">, number[]> {
  const out: Record<Exclude<OpLevel, "normal">, number[]> = { crisis: [], disaster: [] };
  for (const row of rows) {
    if (row.level === "normal") continue;
    if (!identity.national && row.gouvernorat_code !== identity.gouvernoratCode) continue;
    out[row.level].push(row.gouvernorat_code);
  }
  return out;
}

/** §6.4 / FR-C-24: a banner on every screen while a gouvernorat in the user's scope is above `normal`. */
export function LevelBanner() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const query = useQuery({
    queryKey: opsKeys.levels,
    queryFn: ({ signal }) => api.levels(signal),
    // Changes arrive live (`oplevel.changed`); the interval only covers a lost connection.
    refetchInterval: 5 * 60_000,
  });
  if (!user || !query.data) return null;
  const raised = raisedLevels(query.data, user.identity);
  const roles = user.identity.roles;
  const showLink = isCommittee(roles) || canMonitorPerformance(roles);
  const names = (codes: number[]) =>
    codes.map((c) => gouvernorats.nameOf(c) ?? String(c)).join(t("common.listSeparator"));
  return (
    <>
      {(["disaster", "crisis"] as const).map((level) =>
        raised[level].length > 0 ? (
          <div key={level} className={`level-banner level-banner--${level}`} role="status">
            <strong>{t(`levels.name.${level}`)}</strong>
            <span>{t(`levels.banner.${level}`, { places: names(raised[level]) })}</span>
            {showLink && <Link to="/committee">{t("levels.banner.link")}</Link>}
          </div>
        ) : null,
      )}
    </>
  );
}
