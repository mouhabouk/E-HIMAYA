/**
 * Opening the phase 5 alert composer prefilled (phase 7): from an accepted weather suggestion (§1) or an
 * `open_alert_form` recommendation (§3). The composer only fills its form: the alert is saved and published by the
 * existing alert endpoints after a human reviewed it.
 */
import { MAX_ALERT_DAYS, toLocalInput, type MessageForm } from "./messageForm";
import {
  ALERT_CATEGORIES,
  HAZARDS,
  SEVERITIES,
  type AlertCategory,
  type Hazard,
  type Localized,
  type Severity,
} from "./opsTypes";
import { fromPolygon } from "./polygon";
import type { WeatherSuggestion } from "./weatherTypes";

export type PrefillSource = "weather_suggestion" | "recommendation";

/** Router state of `/notifications/new?kind=alert`. */
export interface AlertPrefillState {
  alertPrefill: { source: PrefillSource; sourceId: string | null; form: Partial<MessageForm> };
}

export const NEW_ALERT_PATH = "/notifications/new?kind=alert";

const isObject = (v: unknown): v is Record<string, unknown> => Boolean(v) && typeof v === "object";

export function isAlertPrefillState(v: unknown): v is AlertPrefillState {
  return isObject(v) && isObject(v.alertPrefill) && isObject(v.alertPrefill.form);
}

function localized(v: unknown): Localized {
  const o = isObject(v) ? v : {};
  const s = (x: unknown) => (typeof x === "string" ? x : "");
  return { ar: s(o.ar), fr: s(o.fr), en: s(o.en) };
}

const severity = (v: unknown): Severity | "" => ((SEVERITIES as readonly unknown[]).includes(v) ? (v as Severity) : "");
const category = (v: unknown): AlertCategory | "" =>
  (ALERT_CATEGORIES as readonly unknown[]).includes(v) ? (v as AlertCategory) : "";
const hazard = (v: unknown): Hazard | "" => ((HAZARDS as readonly unknown[]).includes(v) ? (v as Hazard) : "");

/** Expiry within the composer's 7-day limit (and in the future). */
function expiry(iso: unknown, now: Date): string {
  const max = now.getTime() + MAX_ALERT_DAYS * 86_400_000;
  const t = typeof iso === "string" ? Date.parse(iso) : Number.NaN;
  const at = Number.isNaN(t) || t <= now.getTime() ? now.getTime() + 24 * 3_600_000 : Math.min(t, max);
  return toLocalInput(new Date(at));
}

function codes(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((c): c is number => typeof c === "number" && Number.isInteger(c)) : [];
}

export function prefillFromSuggestion(s: WeatherSuggestion, now: Date = new Date()): AlertPrefillState {
  return {
    alertPrefill: {
      source: "weather_suggestion",
      sourceId: s.id,
      form: {
        kind: "alert",
        title: localized(s.title),
        body: localized(s.body),
        severity: severity(s.severity),
        category: "weather",
        hazard: hazard(s.hazard),
        gouvernorats: codes(s.gouvernorat_codes),
        areaMode: "gouvernorats",
        vertices: [],
        // A high-severity weather alert also goes by SMS (reaches phones without the app).
        channels: s.severity === "high" ? ["push", "sms"] : ["push"],
        expiresAt: expiry(s.valid_until, now),
      },
    },
  };
}

/** `prefill` of an `open_alert_form` action: the fields of a phase 5 message body, all optional. */
export function prefillFromAction(
  prefill: Record<string, unknown> | null | undefined,
  now: Date = new Date(),
): AlertPrefillState {
  const p = prefill ?? {};
  const area = isObject(p.area) ? p.area : {};
  const polygon = isObject(area.polygon) ? area.polygon : isObject(p.polygon) ? p.polygon : null;
  const vertices =
    polygon && Array.isArray(polygon.coordinates)
      ? fromPolygon({ type: "Polygon", coordinates: polygon.coordinates as [number, number][][] })
      : [];
  const form: Partial<MessageForm> = {
    kind: "alert",
    title: localized(p.title),
    body: localized(p.body),
    severity: severity(p.severity),
    category: category(p.category),
    hazard: hazard(p.hazard),
    gouvernorats: codes(area.gouvernorat_codes ?? p.gouvernorat_codes),
    areaMode: vertices.length >= 3 ? "polygon" : "gouvernorats",
    vertices,
    expiresAt: expiry(p.expires_at, now),
  };
  return { alertPrefill: { source: "recommendation", sourceId: null, form } };
}
