// covers: FR-M-05, FR-M-06 — docs/phase-m/design-m.md §4: the administrative boundaries of Map Tunisia on the map
// (gouvernorats, délégations, imadas, municipalities), and the délégations coloured by their reports per 10,000
// inhabitants over the last 30 days. Colour is never the only sign: the card of a clicked unit and the list under the
// switches give the figures in words.
import { useQuery } from "@tanstack/react-query";
import { useCallback, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import {
  ADMIN_LEVELS,
  ADMIN_LINE,
  adminKeys,
  rateBreaks,
  rateColour,
  ratePer10k,
  RATE_COLOURS,
  type AdminLevel,
  type AdminProps,
} from "../lib/admin";
import { useFormat, useLanguage } from "../lib/hooks";
import { localizedName } from "../lib/localized";
import type { MapAdmin, MapPopupContent } from "./MapView";

const LEVEL_KEY = "ehimaya.mapAdminLevel";
const ON_KEY = "ehimaya.mapAdminLayer";
const RATE_KEY = "ehimaya.mapAdminRate";
const DAYS = 30;

function stored(key: string, fallback: string): string {
  try {
    return sessionStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function store(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function useAdminLayer() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const id = useId();
  const own = user?.identity.gouvernoratCode ?? null;
  const [on, setOnState] = useState(() => stored(ON_KEY, "0") === "1");
  const [level, setLevelState] = useState<AdminLevel>(() => {
    const v = stored(LEVEL_KEY, "delegations");
    return (ADMIN_LEVELS as readonly string[]).includes(v) ? (v as AdminLevel) : "delegations";
  });
  const [rate, setRateState] = useState(() => stored(RATE_KEY, "0") === "1");
  const [clicked, setClicked] = useState<{ props: AdminProps; lon: number; lat: number } | null>(null);
  const setOn = (v: boolean) => {
    setOnState(v);
    store(ON_KEY, v ? "1" : "0");
    if (!v) setClicked(null);
  };
  const setLevel = (v: AdminLevel) => {
    setLevelState(v);
    store(LEVEL_KEY, v);
    setClicked(null);
  };
  const setRate = (v: boolean) => {
    setRateState(v);
    store(RATE_KEY, v ? "1" : "0");
  };
  const showRate = on && rate && level === "delegations";

  // A regional room loads its own gouvernorat only (the national room, the whole country).
  const scope = level === "gouvernorats" ? null : own;
  const boundaries = useQuery({
    queryKey: adminKeys.boundaries(level, scope),
    enabled: on,
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    queryFn: ({ signal }) => api.boundaries(level, scope, signal),
  });
  const counts = useQuery({
    queryKey: adminKeys.counts(DAYS),
    enabled: showRate,
    staleTime: 5 * 60 * 1000,
    queryFn: ({ signal }) =>
      api.delegationCounts(new Date(Date.now() - DAYS * 24 * 3600 * 1000).toISOString(), signal),
  });

  const countOf = useMemo(
    () => new Map((counts.data ?? []).map((c) => [c.delegation_id, c.count])),
    [counts.data],
  );
  const ranked = useMemo(() => {
    if (!showRate || !boundaries.data) return [];
    return boundaries.data.features
      .map((f) => {
        const p = f.properties as AdminProps;
        const count = countOf.get(Number(p.id)) ?? 0;
        return { props: p, count, rate: ratePer10k(count, p.population_2024) };
      })
      .sort((a, b) => (b.rate ?? -1) - (a.rate ?? -1));
  }, [showRate, boundaries.data, countOf]);
  const breaks = useMemo(() => rateBreaks(ranked.flatMap((r) => (r.rate ? [r.rate] : []))), [ranked]);

  const mapAdmin = useMemo<MapAdmin | null>(() => {
    if (!on || !boundaries.data) return null;
    const rates = new Map(ranked.map((r) => [String(r.props.id), r.rate]));
    return {
      filled: showRate,
      data: {
        type: "FeatureCollection",
        features: boundaries.data.features.map((f) => ({
          ...f,
          properties: {
            ...f.properties,
            line: ADMIN_LINE,
            fill: showRate ? rateColour(rates.get(String(f.properties?.id)) ?? null, breaks) : ADMIN_LINE,
          },
        })),
      },
    };
  }, [on, boundaries.data, showRate, ranked, breaks]);

  const onAdminClick = useCallback((properties: Record<string, unknown>, lon: number, lat: number) => {
    setClicked({ props: properties as unknown as AdminProps, lon, lat });
  }, []);

  const card = (p: AdminProps) => {
    const count = level === "delegations" ? (countOf.get(Number(p.id)) ?? 0) : null;
    const r = count !== null && showRate ? ratePer10k(count, p.population_2024) : null;
    return (
      <div className="admin-card">
        <strong dir="auto">{localizedName(p, lang)}</strong>
        <div className="muted">
          {t(`admin.levelOne.${level}`)}
          {p.ins_code ? ` · ${t("admin.ins", { code: String(p.ins_code) })}` : ""}
        </div>
        {p.population_2024 ? <div>{t("admin.population", { count: fmt.number(p.population_2024) })}</div> : null}
        {p.area_km2 ? <div>{t("admin.area", { value: fmt.decimal(p.area_km2) })}</div> : null}
        {showRate && count !== null && (
          <div>
            {t("admin.reports", { count: fmt.number(count), days: DAYS })}
            {r !== null && ` · ${t("admin.rate", { value: fmt.decimal(r) })}`}
          </div>
        )}
      </div>
    );
  };

  const popup: MapPopupContent | null =
    on && clicked
      ? { lon: clicked.lon, lat: clicked.lat, key: `admin:${level}:${clicked.props.id}`, node: card(clicked.props) }
      : null;

  const controls = (
    <div className="admin-layer">
      <label htmlFor={`${id}-on`} className="checkbox">
        <input id={`${id}-on`} type="checkbox" checked={on} onChange={(e) => setOn(e.target.checked)} />
        <span>{t("admin.toggle")}</span>
      </label>
      {on && (
        <>
          <fieldset className="segmented" aria-label={t("admin.level")}>
            {ADMIN_LEVELS.map((l) => (
              <label key={l} className="segmented__item">
                <input type="radio" name={`${id}-level`} checked={level === l} onChange={() => setLevel(l)} />
                <span>{t(`admin.levels.${l}`)}</span>
              </label>
            ))}
          </fieldset>
          {level === "delegations" && (
            <label htmlFor={`${id}-rate`} className="checkbox">
              <input id={`${id}-rate`} type="checkbox" checked={rate} onChange={(e) => setRate(e.target.checked)} />
              <span>{t("admin.rateToggle", { days: DAYS })}</span>
            </label>
          )}
          <span className="muted" role="status" aria-live="polite">
            {boundaries.isFetching || counts.isFetching
              ? t("common.loading")
              : boundaries.isError
                ? t("admin.error")
                : t("admin.count", { count: fmt.number(boundaries.data?.features.length ?? 0) })}
          </span>
          <span className="muted admin-layer__source">{t("admin.source")}</span>
        </>
      )}
      {showRate && breaks.length > 0 && (
        <details className="admin-layer__rates">
          <summary>
            <span className="admin-legend" aria-hidden="true">
              {RATE_COLOURS.map((c) => (
                <span key={c} style={{ background: c }} />
              ))}
            </span>
            {t("admin.legend", { max: fmt.decimal(breaks.at(-1) ?? 0) })}
          </summary>
          <ol>
            {ranked
              .filter((r) => r.count > 0)
              .slice(0, 15)
              .map((r) => (
                <li key={String(r.props.id)}>
                  <span dir="auto">{localizedName(r.props, lang)}</span>
                  {" — "}
                  {t("admin.reports", { count: fmt.number(r.count), days: DAYS })}
                  {r.rate !== null && ` · ${t("admin.rate", { value: fmt.decimal(r.rate) })}`}
                </li>
              ))}
          </ol>
        </details>
      )}
    </div>
  );

  return { admin: mapAdmin, onAdminClick, popup, closePopup: () => setClicked(null), controls };
}
