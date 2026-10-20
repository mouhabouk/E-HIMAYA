import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useId, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import type { BBox } from "../lib/filters";
import { useDebounced, useFormat, useLanguage } from "../lib/hooks";
import { p7Keys } from "../lib/phase7Api";
import {
  attributionOf,
  CC_BY_URL,
  compassPoint,
  FIRE_DANGER_COLOURS,
  FORECAST_HOURS,
  hourAt,
  normalizeWeatherValues,
  RAIN_LEVEL_COLOURS,
  weatherMapData,
} from "../lib/weather";
import {
  FIRE_DANGER_CLASSES,
  type WeatherAttribution,
  type WeatherPointDetail,
  type WeatherValues,
} from "../lib/weatherTypes";
import { ErrorBox, Loading } from "./Feedback";
import type { MapWeather } from "./MapView";
import { SimTag, SimulationBand } from "./StreamBits";

export interface WeatherViews {
  fire: boolean;
  wind: boolean;
  rain: boolean;
}

/** Grid of the visible area at the chosen forecast hour; the slider is debounced so dragging stays light. */
export function useWeatherGrid(enabled: boolean, bbox: BBox | null, hour: number) {
  const { api } = useServices();
  const settledHour = useDebounced(hour, 250);
  return useQuery({
    queryKey: bbox ? p7Keys.weatherGrid(bbox, settledHour) : ["weather-grid", "pending"],
    enabled: enabled && bbox !== null,
    placeholderData: keepPreviousData,
    // The API refreshes the grid every 30 min.
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) => {
      if (!bbox) throw new Error("no bbox");
      return api.weatherGrid(bbox, settledHour, signal);
    },
  });
}

export function useMapWeather(
  grid: ReturnType<typeof useWeatherGrid>,
  views: WeatherViews,
  enabled: boolean,
): MapWeather | null {
  const data = grid.data;
  const mapData = useMemo(() => weatherMapData(data), [data]);
  return useMemo(
    () =>
      enabled
        ? { data: mapData, fire: views.fire, wind: views.wind, rain: views.rain }
        : { data: mapData, fire: false, wind: false, rain: false },
    [enabled, mapData, views.fire, views.wind, views.rain],
  );
}

/** "Weather data: Open-Meteo.com (CC BY 4.0)", with links (required by the licence). */
export function WeatherAttributionLine({ attribution }: { attribution?: WeatherAttribution | string | null }) {
  const { t } = useTranslation();
  const a = attributionOf(attribution);
  return (
    <p className="weather-attribution">
      {t("weather.attribution")}{" "}
      <a href={a.url} target="_blank" rel="noopener noreferrer" dir="ltr">
        {a.text}
      </a>{" "}
      (
      <a href={CC_BY_URL} target="_blank" rel="noopener noreferrer" dir="ltr">
        {a.licence}
      </a>
      )
    </p>
  );
}

function Swatch({ colour, ring = false }: { colour: string; ring?: boolean }) {
  return (
    <span
      className={`weather-swatch${ring ? " weather-swatch--ring" : ""}`}
      style={ring ? { borderColor: colour } : { background: colour }}
      aria-hidden="true"
    />
  );
}

export function WeatherLegend({ views }: { views: WeatherViews }) {
  const { t } = useTranslation();
  return (
    <div className="weather-legend" aria-label={t("weather.legend")} role="group">
      {views.fire && (
        <ul aria-label={t("weather.views.fire")}>
          {FIRE_DANGER_CLASSES.map((c) => (
            <li key={c}>
              <Swatch colour={FIRE_DANGER_COLOURS[c]} />
              {t(`weather.fireDanger.${c}`)}
            </li>
          ))}
        </ul>
      )}
      {views.rain && (
        <ul aria-label={t("weather.views.rain")}>
          {(["watch", "warning"] as const).map((l) => (
            <li key={l}>
              <Swatch colour={RAIN_LEVEL_COLOURS[l]} ring />
              {t(`weather.rainLevel.${l}`)}
            </li>
          ))}
        </ul>
      )}
      {views.wind && (
        <ul aria-label={t("weather.views.wind")}>
          <li>
            <span className="weather-arrow" aria-hidden="true">
              ↑
            </span>
            {t("weather.windLegend")}
          </li>
        </ul>
      )}
    </div>
  );
}

/** Switches, time slider, legend, attribution and simulation band of the weather layer (FR-C-08). */
export function WeatherControls({
  views,
  onViews,
  hour,
  onHour,
  grid,
  onCentre,
}: {
  views: WeatherViews;
  onViews: (v: WeatherViews) => void;
  hour: number;
  onHour: (h: number) => void;
  grid: ReturnType<typeof useWeatherGrid>;
  onCentre: () => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const base = useId();
  const at = hourAt(hour);
  const timeLabel =
    hour === 0 ? t("weather.now", { time: fmt.time(at.toISOString()) }) : fmt.dateTime(at.toISOString());
  const count = grid.data?.features.length ?? 0;
  return (
    <section className="card weather-panel" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`} className="weather-panel__title">
        {t("weather.title")}
      </h2>
      {grid.data?.simulated && <SimulationBand note={t("weather.simBand")} />}
      <fieldset className="weather-views">
        <legend className="visually-hidden">{t("weather.viewsLegend")}</legend>
        {(["fire", "wind", "rain"] as const).map((k) => (
          <label key={k} className="checkbox">
            <input type="checkbox" checked={views[k]} onChange={(e) => onViews({ ...views, [k]: e.target.checked })} />
            <span>{t(`weather.views.${k}`)}</span>
          </label>
        ))}
      </fieldset>
      <div className="field weather-slider">
        <label htmlFor={`${base}-hour`}>{t("weather.hourLabel")}</label>
        <input
          id={`${base}-hour`}
          type="range"
          min={0}
          max={FORECAST_HOURS - 1}
          step={1}
          value={hour}
          aria-valuetext={timeLabel}
          onChange={(e) => onHour(Number(e.target.value))}
        />
        <output htmlFor={`${base}-hour`} aria-live="polite">
          {timeLabel}
          {hour > 0 && ` · ${t("weather.plusHours", { count: hour })}`}
        </output>
      </div>
      <p className="muted" role="status" aria-live="polite">
        {grid.isFetching ? t("common.loading") : t("weather.points", { count: fmt.number(count) })}
        {grid.data?.generated_at && ` · ${t("weather.updated", { time: fmt.dateTime(grid.data.generated_at) })}`}
      </p>
      {grid.isError && <ErrorBox error={grid.error} onRetry={() => void grid.refetch()} />}
      <WeatherLegend views={views} />
      <div className="actions">
        <button type="button" className="btn btn--small" onClick={onCentre}>
          {t("weather.atCentre")}
        </button>
      </div>
      <p className="muted">{t("weather.clickHint")}</p>
      <WeatherAttributionLine attribution={grid.data?.attribution} />
    </section>
  );
}

/** The values of the hour shown by the slider: the matching hourly row, else the current values. */
export function valuesAtHour(detail: WeatherPointDetail, hour: number, now: Date = new Date()): WeatherValues | null {
  const rows = (detail.hourly ?? []).map(normalizeWeatherValues);
  if (hour > 0) {
    const target = hourAt(hour, now).getTime();
    const match = rows.find((r) => r.time !== null && Math.abs(Date.parse(r.time) - target) < 30 * 60_000);
    if (match) return match;
    if (rows[hour]) return rows[hour];
  }
  if (detail.current) return normalizeWeatherValues(detail.current);
  return rows[0] ?? null;
}

function ValueRows({ v }: { v: WeatherValues }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const n = (x: number | null, unit: string) => (x === null ? t("common.notAvailable") : `${fmt.decimal(x)} ${unit}`);
  return (
    <dl className="fields fields--compact">
      <dt>{t("weather.field.fireDanger")}</dt>
      <dd>
        {v.fire_danger ? (
          <span className={`weather-class weather-class--${v.fire_danger}`}>
            {t(`weather.fireDanger.${v.fire_danger}`)}
          </span>
        ) : (
          t("common.notAvailable")
        )}
        {v.fwi !== null && ` · ${t("weather.fwi", { value: fmt.decimal(v.fwi) })}`}
      </dd>
      <dt>{t("weather.field.wind")}</dt>
      <dd>
        {n(v.wind_speed_kmh, "km/h")}
        {v.wind_gust_kmh !== null && ` · ${t("weather.gusts", { value: fmt.decimal(v.wind_gust_kmh) })}`}
        {v.wind_direction_deg !== null &&
          ` · ${t("weather.from", { dir: t(`weather.compass.${compassPoint(v.wind_direction_deg)}`), deg: Math.round(v.wind_direction_deg) })}`}
      </dd>
      <dt>{t("weather.field.temperature")}</dt>
      <dd>{n(v.temperature_c, "°C")}</dd>
      <dt>{t("weather.field.humidity")}</dt>
      <dd>{n(v.humidity_pct, "%")}</dd>
      <dt>{t("weather.field.rain")}</dt>
      <dd>
        {n(v.precipitation_mm_h, "mm/h")}
        {v.rain_24h_mm !== null && ` · ${t("weather.rain24", { value: fmt.decimal(v.rain_24h_mm) })}`}
        {v.rain_level && v.rain_level !== "none" && (
          <>
            {" · "}
            <span className={`weather-class weather-class--rain-${v.rain_level}`}>
              {t(`weather.rainLevel.${v.rain_level}`)}
            </span>
          </>
        )}
      </dd>
    </dl>
  );
}

/** Point popup: the weather at the clicked place for the slider's hour, active weather alerts, attribution. */
export function WeatherPointCard({ lat, lon, hour }: { lat: number; lon: number; hour: number }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const query = useQuery({
    queryKey: p7Keys.weatherAt(lat, lon),
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) => api.weatherAt(lat, lon, signal),
  });
  const at = hourAt(hour).toISOString();
  return (
    // Scrollable when long: focusable so keyboard users can scroll it.
    <div className="weather-card" lang={lang} tabIndex={0} role="group" aria-label={t("weather.pointTitle")}>
      <strong>
        {t("weather.pointTitle")} {query.data?.simulated && <SimTag />}
      </strong>
      <div className="muted" dir="ltr">
        {(query.data?.lat ?? lat).toFixed(3)}, {(query.data?.lon ?? lon).toFixed(3)}
      </div>
      <div className="muted">{hour === 0 ? t("weather.now", { time: fmt.time(at) }) : fmt.dateTime(at)}</div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.data &&
        (() => {
          const v = valuesAtHour(query.data, hour);
          return v ? <ValueRows v={v} /> : <p className="muted">{t("common.notAvailable")}</p>;
        })()}
      {query.data?.alerts && query.data.alerts.length > 0 && (
        <ul className="weather-card__alerts" aria-label={t("weather.activeAlerts")}>
          {query.data.alerts.map((a) => (
            <li key={a.id}>
              <span className={`chip chip--severity-${a.severity ?? "low"}`}>
                {t(`ops.map.severity.${a.severity ?? "low"}`)}
              </span>{" "}
              <span dir="auto">{(lang === "ar" ? a.title?.ar : a.title?.fr || a.title?.ar) ?? ""}</span>
            </li>
          ))}
        </ul>
      )}
      {query.data && <WeatherAttributionLine attribution={query.data.attribution} />}
    </div>
  );
}
