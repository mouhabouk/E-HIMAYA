// covers: FR-M-07 — docs/phase-m/design-m.md §5: an alert to some délégations, picked from the Map Tunisia list of a
// gouvernorat instead of drawing a polygon; the people concerned (census 2024) are counted before sending, and the
// chosen délégations are shown on a map.
import { useQuery } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { ADMIN_LINE, adminKeys, type AdminProps } from "../lib/admin";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localizedName } from "../lib/localized";
import { initialBoundsFor } from "../lib/mapStyle";
import { areaRings, type MultiPolygon, type Polygon } from "../lib/opsTypes";
import { verticesBounds } from "../lib/polygon";
import { Loading } from "./Feedback";
import { LazyMapView } from "./LazyMap";
import type { MapAdmin } from "./MapView";

const CHOSEN = "#D7141A";
const OTHER = "#E3E7EF";

/** Our délégation ids are `<gouvernorat code> × 100 + n` (migration 0002). */
export function gouvernoratOfDelegation(id: number): number {
  return Math.floor(id / 100);
}

/** The délégations of one gouvernorat, from the boundaries (names in both languages and census). */
export function useDelegations(gouvernorat: number | null) {
  const { api } = useServices();
  return useQuery({
    queryKey: adminKeys.boundaries("delegations", gouvernorat),
    enabled: gouvernorat !== null,
    staleTime: Infinity,
    queryFn: ({ signal }) => api.boundaries("delegations", gouvernorat, signal),
  });
}

export function DelegationPicker({
  value,
  onChange,
  error,
}: {
  value: number[];
  onChange: (ids: number[]) => void;
  error?: string;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { mapStyleUrl } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const own = user?.identity.national ? null : (user?.identity.gouvernoratCode ?? null);
  const first = value[0];
  const [chosenGov, setChosenGov] = useState<number | null>(
    own ?? (first !== undefined ? gouvernoratOfDelegation(first) : null),
  );
  const gov = own ?? chosenGov;
  const query = useDelegations(gov);
  const units = useMemo(
    () => (query.data?.features ?? []).map((f) => f.properties as AdminProps),
    [query.data],
  );
  const chosen = new Set(value);
  const people = units.filter((u) => chosen.has(Number(u.id))).reduce((n, u) => n + (u.population_2024 ?? 0), 0);
  const preview = useMemo<MapAdmin | null>(
    () =>
      query.data
        ? {
            filled: true,
            data: {
              type: "FeatureCollection",
              features: query.data.features.map((f) => ({
                ...f,
                properties: {
                  ...f.properties,
                  line: ADMIN_LINE,
                  fill: value.includes(Number(f.properties?.id)) ? CHOSEN : OTHER,
                },
              })),
            },
          }
        : null,
    [query.data, value],
  );
  const toggle = (unit: number, on: boolean) =>
    onChange(on ? [...value, unit].sort((a, b) => a - b) : value.filter((v) => v !== unit));

  return (
    <div className="delegation-picker">
      {own === null && (
        <div className="field">
          <label htmlFor={`${id}-gov`}>{t("notify.area.delegationsGouvernorat")}</label>
          <select
            id={`${id}-gov`}
            value={gov ?? ""}
            onChange={(e) => {
              setChosenGov(e.target.value ? Number(e.target.value) : null);
              onChange([]);
            }}
          >
            <option value="">{t("notify.area.delegationsPick")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      )}
      {gov !== null && (
        <fieldset className="chips" aria-describedby={error ? `${id}-error` : undefined}>
          <legend>{t("notify.area.delegations")}</legend>
          {query.isLoading && <Loading />}
          {units.length > 0 && (
            <div className="actions">
              <button type="button" className="btn btn--ghost btn--small" onClick={() => onChange(units.map((u) => Number(u.id)))}>
                {t("notify.area.delegationsAll")}
              </button>
              <button type="button" className="btn btn--ghost btn--small" disabled={value.length === 0} onClick={() => onChange([])}>
                {t("notify.area.clear")}
              </button>
            </div>
          )}
          {units.map((u) => (
            <label key={String(u.id)} className="chip-toggle">
              <input type="checkbox" checked={chosen.has(Number(u.id))} onChange={(e) => toggle(Number(u.id), e.target.checked)} />
              <span dir="auto">{localizedName(u, lang)}</span>
            </label>
          ))}
        </fieldset>
      )}
      <p role="status" aria-live="polite">
        {t("notify.area.delegationsChosen", { count: value.length, people: fmt.number(people) })}
      </p>
      {error && (
        <p className="field__error" id={`${id}-error`} role="alert">
          {t(`notify.validation.${error}`)}
        </p>
      )}
      {gov !== null && preview && (
        <Suspense fallback={<Loading />}>
          <LazyMapView
            className="map map--draw"
            markers={[]}
            bounds={initialBoundsFor(gov)}
            ariaLabel={t("notify.area.delegationsMap")}
            styleUrl={mapStyleUrl}
            dir={directionOf(lang)}
            admin={preview}
            onAdminClick={(p) => toggle(Number(p.id), !chosen.has(Number(p.id)))}
          />
        </Suspense>
      )}
    </div>
  );
}

/** The délégations of a sent alert: their names and their union on a map. */
export function DelegationArea({ ids, polygon }: { ids: readonly number[]; polygon: Polygon | MultiPolygon | null }) {
  const { t } = useTranslation();
  const { mapStyleUrl } = useServices();
  const lang = useLanguage();
  const first = ids[0];
  const query = useDelegations(first !== undefined ? gouvernoratOfDelegation(first) : null);
  const names = (query.data?.features ?? [])
    .map((f) => f.properties as AdminProps)
    .filter((u) => ids.includes(Number(u.id)))
    .map((u) => localizedName(u, lang));
  const parts = areaRings(polygon);
  const points = parts.flatMap((p) => p[0] ?? []);
  const bounds = verticesBounds(points);
  return (
    <>
      <p dir="auto">{names.length > 0 ? names.join(t("common.listSeparator")) : t("notify.target.delegations", { count: ids.length })}</p>
      {bounds && (
        <Suspense fallback={<Loading />}>
          <LazyMapView
            className="map map--draw"
            markers={[]}
            bounds={bounds}
            ariaLabel={t("notify.area.delegationsMap")}
            styleUrl={mapStyleUrl}
            dir={directionOf(lang)}
            polygons={parts.map((coordinates, i) => ({ id: `area-${i}`, coordinates, tone: "high" as const }))}
          />
        </Suspense>
      )}
    </>
  );
}
