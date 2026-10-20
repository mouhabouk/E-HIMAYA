import { describe, expect, it } from "vitest";
import { makeFireForecast, makeSuggestion } from "../test/phase7Fixtures";
import { prefillFromAction, prefillFromSuggestion, isAlertPrefillState } from "./alertPrefill";
import { bilingual, forecastBounds, forecastMapPolygons, inputText } from "./forecast";
import { parsePhase7Event } from "./live";
import { phase7Api } from "./phase7Api";
import type { ApiClient, RequestOptions } from "./api";
import {
  attributionOf,
  compassPoint,
  FIRE_DANGER_COLOURS,
  hourAt,
  normalizeWeatherValues,
  weatherMapData,
} from "./weather";

describe("weather helpers", () => {
  it("reads the contract names and the Open-Meteo spellings", () => {
    expect(
      normalizeWeatherValues({
        wind_speed_kmh: 30,
        wind_gust_kmh: 70,
        wind_direction_deg: 300,
        temperature_c: 28,
        humidity_pct: 22,
        precipitation_mm_h: 1.5,
        rain_24h_mm: 52,
        fire_danger: "high",
        fwi: 25,
        rain_level: "warning",
        time: "2026-10-20T12:00:00Z",
      }),
    ).toEqual({
      time: "2026-10-20T12:00:00Z",
      temperature_c: 28,
      humidity_pct: 22,
      wind_speed_kmh: 30,
      wind_gust_kmh: 70,
      wind_direction_deg: 300,
      precipitation_mm_h: 1.5,
      rain_24h_mm: 52,
      fwi: 25,
      fire_danger: "high",
      rain_level: "warning",
    });
    const alt = normalizeWeatherValues({
      wind_speed_10m: 12,
      wind_gusts_10m: 20,
      wind_direction_10m: 90,
      temperature_2m: 15,
      relative_humidity_2m: 60,
      fire_danger: { class: "extreme", fwi: 60 },
      heavy_rain_level: "watch",
    });
    expect(alt).toMatchObject({
      wind_speed_kmh: 12,
      wind_gust_kmh: 20,
      fire_danger: "extreme",
      fwi: 60,
      rain_level: "watch",
    });
    expect(normalizeWeatherValues({ fire_danger: "unknown", rain_level: 3 })).toMatchObject({
      fire_danger: null,
      rain_level: null,
    });
  });

  it("builds map features: colour by fire class, arrow pointing where the wind goes", () => {
    const data = weatherMapData({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [10, 36] },
          properties: { fire_danger: "very_high", wind_direction_deg: 315, wind_speed_kmh: 40 },
        },
        { type: "Feature", geometry: { type: "Point", coordinates: [9, 35] }, properties: { rain_level: "watch" } },
      ],
    });
    expect(data.features[0]?.properties).toMatchObject({
      fire: FIRE_DANGER_COLOURS.very_high,
      wind_to: 135,
      has_wind: true,
      rain_level: "none",
    });
    expect(data.features[1]?.properties).toMatchObject({ fire_class: "", has_wind: false, rain_level: "watch" });
    expect(weatherMapData(null).features).toEqual([]);
  });

  it("names compass points and forecast hours", () => {
    expect(compassPoint(0)).toBe("N");
    expect(compassPoint(359)).toBe("N");
    expect(compassPoint(225)).toBe("SW");
    expect(compassPoint(-90)).toBe("W");
    const now = new Date("2026-10-20T10:42:13Z");
    expect(hourAt(0, now).toISOString()).toBe("2026-10-20T10:00:00.000Z");
    expect(hourAt(47, now).toISOString()).toBe("2026-10-22T09:00:00.000Z");
  });

  it("always has an attribution, Open-Meteo CC BY 4.0 by default", () => {
    expect(attributionOf(null)).toEqual({
      text: "Open-Meteo.com",
      url: "https://open-meteo.com/",
      licence: "CC BY 4.0",
    });
    expect(attributionOf("Weather data by INM")).toMatchObject({ text: "Weather data by INM", licence: "CC BY 4.0" });
    expect(attributionOf({ text: "INM", url: "https://inm.example", license: "Etalab" })).toEqual({
      text: "INM",
      url: "https://inm.example",
      licence: "Etalab",
    });
  });
});

describe("alert prefill", () => {
  it("maps a weather suggestion onto the alert form, expiry within 7 days", () => {
    const now = new Date("2026-10-20T10:00:00Z");
    const state = prefillFromSuggestion(makeSuggestion({ valid_until: "2026-11-30T00:00:00Z" }), now);
    expect(isAlertPrefillState(state)).toBe(true);
    const form = state.alertPrefill.form;
    expect(form).toMatchObject({
      kind: "alert",
      category: "weather",
      severity: "high",
      hazard: "forest_fire",
      gouvernorats: [61],
      channels: ["push", "sms"],
      areaMode: "gouvernorats",
    });
    expect(form.title?.fr).toBe("Danger d’incendie très élevé");
    expect(new Date(form.expiresAt ?? "").getTime()).toBe(now.getTime() + 7 * 86_400_000);
  });

  it("maps an open_alert_form prefill, polygon included, and ignores unknown values", () => {
    const now = new Date("2026-10-20T10:00:00Z");
    const ring: [number, number][] = [
      [10, 36],
      [10.1, 36],
      [10.1, 36.1],
      [10, 36],
    ];
    const state = prefillFromAction(
      {
        title: { ar: "عنوان" },
        severity: "extreme",
        category: "hazard",
        area: { polygon: { type: "Polygon", coordinates: [ring] } },
      },
      now,
    );
    expect(state.alertPrefill.form).toMatchObject({ severity: "", category: "hazard", areaMode: "polygon" });
    expect(state.alertPrefill.form.vertices).toHaveLength(3);
    expect(state.alertPrefill.form.title).toEqual({ ar: "عنوان", fr: "", en: "" });
    expect(isAlertPrefillState({ alertPrefill: null })).toBe(false);
  });
});

describe("forecast helpers", () => {
  it("draws the longest horizon first, colours by horizon, fits the bounds", () => {
    const run = makeFireForecast();
    const polygons = forecastMapPolygons("fire", run);
    expect(polygons).toHaveLength(2);
    // 60 min (index 1 after sorting) below, 30 min on top.
    expect(polygons[0]?.colour).toBe("#ea580c");
    expect(polygons[1]?.colour).toBe("#f59e0b");
    expect(polygons.every((p) => p.outline === "solid")).toBe(true);
    const b = forecastBounds(polygons);
    expect(b?.[0]).toBeCloseTo(10.758);
    expect(b?.[3]).toBeCloseTo(34.762);
  });

  it("splits multipolygons and reads bilingual texts", () => {
    const run = makeFireForecast({
      polygons: [
        {
          level: "high",
          geojson: {
            type: "MultiPolygon",
            coordinates: [
              [
                [
                  [0, 0],
                  [1, 0],
                  [1, 1],
                  [0, 0],
                ],
              ],
              [
                [
                  [2, 2],
                  [3, 2],
                  [3, 3],
                  [2, 2],
                ],
              ],
            ],
          },
        },
      ],
    });
    const polygons = forecastMapPolygons("flood", run);
    expect(polygons).toHaveLength(2);
    expect(polygons[0]?.colour).toBe("#1e3a8a");
    expect(bilingual({ ar: "أ", fr: "" }, "fr")).toBe("أ");
    expect(bilingual("plain", "ar")).toBe("plain");
    expect(inputText({ wind: 12.345, ok: true })).toBe("wind: 12.35 · ok: ✓");
  });
});

describe("phase 7 live events", () => {
  it("normalises weather.suggestion and call events", () => {
    expect(parsePhase7Event({ type: "weather.suggestion", suggestion: makeSuggestion() })).toMatchObject({
      type: "weather.suggestion",
      suggestion_id: "ws-1",
    });
    expect(parsePhase7Event({ type: "weather.suggestion", suggestion_id: "x" })).toEqual({
      type: "weather.suggestion",
      suggestion_id: "x",
      suggestion: null,
    });
    expect(parsePhase7Event({ type: "weather.suggestion" })).toBeNull();
    expect(
      parsePhase7Event({
        type: "call.ringing",
        call: { id: "c1", queue: "operators" },
        queue: { name: "operators", waiting: 3 },
      }),
    ).toMatchObject({ type: "call.ringing", call_id: "c1", queue: { name: "operators", waiting: 3 } });
    expect(parsePhase7Event({ type: "call.ringing", call_id: "c2", waiting: 2 })).toMatchObject({
      call_id: "c2",
      call: null,
      queue: { name: null, waiting: 2 },
    });
    expect(parsePhase7Event({ type: "call.recording", call_id: "c3", media_id: "m1" })).toMatchObject({
      media_id: "m1",
      queue: null,
    });
    expect(parsePhase7Event({ type: "call.ended" })).toBeNull();
  });
});

describe("phase7Api requests", () => {
  function recorder() {
    const calls: { path: string; options: RequestOptions }[] = [];
    const client: ApiClient = {
      request: <T>(path: string, options: RequestOptions = {}) => {
        calls.push({ path, options });
        return Promise.resolve({ items: [] } as T);
      },
      requestRaw: () => Promise.reject(new Error("unused")),
    };
    return { calls, api: phase7Api(client) };
  }

  it("builds the contract's paths, queries and bodies", async () => {
    const { calls, api } = recorder();
    await api.weatherGrid([9, 34, 11, 37], 6);
    await api.route({ lat: 34.7, lon: 10.7 }, { lat: 34.74, lon: 10.76 }, "truck");
    await api.dismissWeatherSuggestion("ws/1", "duplicate");
    await api.fireForecast("i-1", { ignition: null, horizons_min: [30, 60] });
    await api.linkCall("c-1", { tracking_code: "EH-1" });
    await api.dial({ volunteer_id: "v-1" });
    expect(await api.weatherSuggestions()).toEqual([]);
    expect(calls.map((c) => c.path)).toEqual([
      "/api/v1/staff/weather/grid",
      "/api/v1/staff/route",
      "/api/v1/staff/weather/suggestions/ws%2F1/dismiss",
      "/api/v1/staff/incidents/i-1/forecast/fire",
      "/api/v1/staff/calls/c-1/link",
      "/api/v1/staff/calls/dial",
      "/api/v1/staff/weather/suggestions",
    ]);
    expect(calls[0]?.options.query).toEqual({ bbox: "9.00000,34.00000,11.00000,37.00000", hour: 6 });
    expect(calls[1]?.options.query).toEqual({
      from: "34.700000,10.700000",
      to: "34.740000,10.760000",
      profile: "truck",
    });
    expect(calls[2]?.options).toMatchObject({ method: "POST", body: { reason: "duplicate" } });
    expect(calls[3]?.options.body).toEqual({ ignition: null, horizons_min: [30, 60] });
    expect(calls[5]?.options.body).toEqual({ volunteer_id: "v-1" });
  });
});
