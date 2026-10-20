/**
 * Weather layer helpers (phase 7 §1, FR-C-08 / FR-C-10): reading a grid point's values whatever the exact field
 * names, the colour bands of the fire danger and heavy-rain levels (always paired with a text label in the legend
 * and the popup), and the forecast hours of the time slider.
 */
import type { FeatureCollection } from "geojson";
import {
  FIRE_DANGER_CLASSES,
  RAIN_LEVELS,
  type FireDangerClass,
  type RainLevel,
  type WeatherAttribution,
  type WeatherGrid,
  type WeatherValues,
} from "./weatherTypes";

/** Forecast hours offered by the time slider: now (0) to +47 h (the 48 h forecast). */
export const FORECAST_HOURS = 48;

/** Open-Meteo data licence, shown whenever the layer or a point detail is on screen. */
export const OPEN_METEO_ATTRIBUTION: { text: string; url: string; licence: string } = {
  text: "Open-Meteo.com",
  url: "https://open-meteo.com/",
  licence: "CC BY 4.0",
};
export const CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/";

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

function first(p: Record<string, unknown>, names: readonly string[]): number | null {
  for (const n of names) {
    const v = num(p[n]);
    if (v !== null) return v;
  }
  return null;
}

export function isFireDanger(v: unknown): v is FireDangerClass {
  return typeof v === "string" && (FIRE_DANGER_CLASSES as readonly string[]).includes(v);
}

export function isRainLevel(v: unknown): v is RainLevel {
  return typeof v === "string" && (RAIN_LEVELS as readonly string[]).includes(v);
}

/** The class may come as a string or inside `fire_danger: {class, fwi}`. */
function fireDangerOf(p: Record<string, unknown>): { cls: FireDangerClass | null; fwi: number | null } {
  const raw = p.fire_danger;
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    return { cls: isFireDanger(o.class) ? o.class : null, fwi: num(o.fwi) ?? num(p.fwi) };
  }
  const cls = isFireDanger(raw) ? raw : isFireDanger(p.fire_danger_class) ? p.fire_danger_class : null;
  return { cls, fwi: num(p.fwi) };
}

/** Reads the values of one point at one hour (names of §1, plus the Open-Meteo spellings). */
export function normalizeWeatherValues(p: Record<string, unknown>): WeatherValues {
  const fire = fireDangerOf(p);
  const rain = p.rain_level ?? p.heavy_rain_level ?? p.heavy_rain;
  return {
    time: typeof p.time === "string" ? p.time : typeof p.hour === "string" ? p.hour : null,
    temperature_c: first(p, ["temperature_c", "temp_c", "temperature", "temperature_2m"]),
    humidity_pct: first(p, ["humidity_pct", "rh_pct", "relative_humidity", "relative_humidity_2m", "rh"]),
    wind_speed_kmh: first(p, ["wind_speed_kmh", "wind_kmh", "wind_speed", "wind_speed_10m"]),
    wind_gust_kmh: first(p, ["wind_gust_kmh", "wind_gusts_kmh", "gust_kmh", "wind_gusts", "wind_gusts_10m"]),
    wind_direction_deg: first(p, ["wind_direction_deg", "wind_dir_deg", "wind_direction", "wind_direction_10m"]),
    precipitation_mm_h: first(p, ["precipitation_mm_h", "rain_1h_mm", "precip_mm_h", "precipitation"]),
    rain_24h_mm: first(p, ["rain_24h_mm", "precipitation_24h_mm", "rain_24h"]),
    fwi: fire.fwi,
    fire_danger: fire.cls,
    rain_level: isRainLevel(rain) ? rain : null,
  };
}

/** Colours of the fire danger field (light to dark red), never shown without the class name. */
export const FIRE_DANGER_COLOURS: Readonly<Record<FireDangerClass, string>> = {
  low: "#4d9221",
  moderate: "#d9c400",
  high: "#f08c00",
  very_high: "#d6301f",
  extreme: "#6b0f1a",
};

export const RAIN_LEVEL_COLOURS: Readonly<Record<RainLevel, string>> = {
  none: "rgba(0,0,0,0)",
  watch: "#3b82f6",
  warning: "#1e3a8a",
};

/**
 * The map layers as GeoJSON: each point carries what the MapLibre paint expressions read (colour of the fire danger
 * cell, rotation of the wind arrow = direction the wind blows towards, rain ring colour).
 */
export function weatherMapData(grid: WeatherGrid | undefined | null): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: (grid?.features ?? []).map((f, i) => {
      const v = normalizeWeatherValues(f.properties);
      const [lon, lat] = f.geometry.coordinates;
      return {
        type: "Feature",
        id: i,
        geometry: { type: "Point", coordinates: [lon, lat] },
        properties: {
          lon,
          lat,
          fire: v.fire_danger ? FIRE_DANGER_COLOURS[v.fire_danger] : "rgba(0,0,0,0)",
          fire_class: v.fire_danger ?? "",
          rain: v.rain_level ? RAIN_LEVEL_COLOURS[v.rain_level] : "rgba(0,0,0,0)",
          rain_level: v.rain_level ?? "none",
          // Meteorological direction is where the wind comes FROM: the arrow points where it goes.
          wind_to: v.wind_direction_deg === null ? 0 : (v.wind_direction_deg + 180) % 360,
          wind: v.wind_speed_kmh ?? 0,
          has_wind: v.wind_direction_deg !== null && v.wind_speed_kmh !== null,
        },
      };
    }),
  };
}

/** Start of the current hour. */
export function currentHour(now: Date = new Date()): Date {
  const d = new Date(now);
  d.setMinutes(0, 0, 0);
  return d;
}

/** Wall-clock time of a slider position (hours from the current hour). */
export function hourAt(offset: number, now: Date = new Date()): Date {
  return new Date(currentHour(now).getTime() + offset * 3_600_000);
}

/** 16 compass points, for the screen-reader text of a wind direction ("from the north-west"). */
export const COMPASS = [
  "N",
  "NNE",
  "NE",
  "ENE",
  "E",
  "ESE",
  "SE",
  "SSE",
  "S",
  "SSW",
  "SW",
  "WSW",
  "W",
  "WNW",
  "NW",
  "NNW",
] as const;
export type CompassPoint = (typeof COMPASS)[number];

export function compassPoint(deg: number): CompassPoint {
  const i = Math.round((((deg % 360) + 360) % 360) / 22.5) % 16;
  return COMPASS[i] ?? "N";
}

/** The attribution of a response as text + link, Open-Meteo by default. */
export function attributionOf(raw: WeatherAttribution | string | null | undefined): {
  text: string;
  url: string;
  licence: string;
} {
  if (typeof raw === "string" && raw.trim()) {
    return { text: raw.trim(), url: OPEN_METEO_ATTRIBUTION.url, licence: OPEN_METEO_ATTRIBUTION.licence };
  }
  if (raw && typeof raw === "object" && raw.text.trim()) {
    return {
      text: raw.text.trim(),
      url: raw.url ?? OPEN_METEO_ATTRIBUTION.url,
      licence: raw.licence ?? raw.license ?? OPEN_METEO_ATTRIBUTION.licence,
    };
  }
  return { ...OPEN_METEO_ATTRIBUTION };
}

/** An image of an arrow pointing up (north), drawn on a canvas for the MapLibre symbol layer. */
export function windArrowImage(size = 32, colour = "#0f172a", halo = "#ffffff"): ImageData | null {
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const c = size / 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(c, 2);
  ctx.lineTo(c + size * 0.28, size * 0.45);
  ctx.lineTo(c + size * 0.09, size * 0.45);
  ctx.lineTo(c + size * 0.09, size - 2);
  ctx.lineTo(c - size * 0.09, size - 2);
  ctx.lineTo(c - size * 0.09, size * 0.45);
  ctx.lineTo(c - size * 0.28, size * 0.45);
  ctx.closePath();
  ctx.lineWidth = 3;
  ctx.strokeStyle = halo;
  ctx.stroke();
  ctx.fillStyle = colour;
  ctx.fill();
  return ctx.getImageData(0, 0, size, size);
}
