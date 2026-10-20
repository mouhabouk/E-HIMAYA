/** Phase 9 helpers: national settings values, SLA countdowns, rooms, and the hooks the new screens share. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useServices } from "../context/services";
import { p9Keys } from "./phase9Api";
import {
  DEFAULT_CLAIM_DELAYS,
  DEFAULT_SLA_BANDS,
  SLA_BANDS,
  type PlatformSetting,
  type SlaBandBounds,
  type SlaClaimDelays,
} from "./phase9Types";

// ---------- settings values (§2) ----------

export const QUOTA_RANGE = { min: 1, max: 100 } as const;
export const ACCURACY_RANGE = { min: 50, max: 20000 } as const;
export const DELAY_RANGE = { min: 15, max: 3600 } as const;
export const BAND_RANGE = { min: 0, max: 100 } as const;
export const REASON_RANGE = { min: 5, max: 500 } as const;

function isRecord(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === "object" && !Array.isArray(v);
}

const num = (v: unknown, fallback: number) => (typeof v === "number" && Number.isFinite(v) ? v : fallback);

export function bandsFrom(value: unknown): SlaBandBounds {
  const v = isRecord(value) ? value : {};
  return {
    critical: num(v.critical, DEFAULT_SLA_BANDS.critical),
    high: num(v.high, DEFAULT_SLA_BANDS.high),
    normal: num(v.normal, DEFAULT_SLA_BANDS.normal),
  };
}

export function delaysFrom(value: unknown): SlaClaimDelays {
  const v = isRecord(value) ? value : {};
  return {
    critical: num(v.critical, DEFAULT_CLAIM_DELAYS.critical),
    high: num(v.high, DEFAULT_CLAIM_DELAYS.high),
    normal: num(v.normal, DEFAULT_CLAIM_DELAYS.normal),
    low: num(v.low, DEFAULT_CLAIM_DELAYS.low),
  };
}

export type SettingError = "integer" | "range" | "order";

const isInt = (n: number) => Number.isInteger(n);

/** Bands: integers 0–100, strictly decreasing critical > high > normal (the API answers `422 invalid_setting`). */
export function validateBands(b: SlaBandBounds): SettingError | null {
  const values = [b.critical, b.high, b.normal];
  if (values.some((n) => !isInt(n))) return "integer";
  if (values.some((n) => n < BAND_RANGE.min || n > BAND_RANGE.max)) return "range";
  if (!(b.critical > b.high && b.high > b.normal)) return "order";
  return null;
}

/** Claim delays: integers 15–3600 s with critical ≤ high ≤ normal ≤ low. */
export function validateDelays(d: SlaClaimDelays): SettingError | null {
  const values = SLA_BANDS.map((k) => d[k]);
  if (values.some((n) => !isInt(n))) return "integer";
  if (values.some((n) => n < DELAY_RANGE.min || n > DELAY_RANGE.max)) return "range";
  if (!(d.critical <= d.high && d.high <= d.normal && d.normal <= d.low)) return "order";
  return null;
}

export function validateIntRange(n: number, range: { min: number; max: number }): SettingError | null {
  if (!isInt(n)) return "integer";
  if (n < range.min || n > range.max) return "range";
  return null;
}

export function reasonValid(reason: string, range: { min: number; max: number } = REASON_RANGE): boolean {
  const n = reason.trim().length;
  return n >= range.min && n <= range.max;
}

// ---------- SLA countdown (§4.4) ----------

/** Seconds left before `dueAt` (negative once overdue); null without a due time. */
export function secondsUntil(dueAt: string | null | undefined, now: number): number | null {
  if (!dueAt) return null;
  const due = Date.parse(dueAt);
  return Number.isNaN(due) ? null : Math.round((due - now) / 1000);
}

/** "m:ss" (or "h:mm:ss") of an absolute number of seconds, digits only (the sign is said in words). */
export function clock(seconds: number): string {
  const s = Math.abs(Math.trunc(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

/** Current time, refreshed every `intervalMs` while the component is mounted. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

// ---------- hooks ----------

/** National settings (`GET /staff/settings`, any staff); refreshed by the `settings.changed` live event. */
export function usePlatformSettings(enabled = true) {
  const { api } = useServices();
  return useQuery({
    queryKey: p9Keys.settings,
    queryFn: ({ signal }) => api.platformSettings(signal),
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function settingOf(items: readonly PlatformSetting[] | undefined, key: string): PlatformSetting | undefined {
  return items?.find((s) => s.key === key);
}

/** Priority band bounds from the national settings (defaults until loaded or when unreadable). */
export function useSlaBands(): SlaBandBounds {
  const query = usePlatformSettings();
  const value = settingOf(query.data, "sla.bands")?.value;
  return useMemo(() => bandsFrom(value), [value]);
}

// ---------- geo-verification map (§4.5) ----------

/** Ring of [lon, lat] approximating the accuracy circle of a location (for the candidate map). */
export function accuracyCircle(lat: number, lon: number, radiusM: number, steps = 48): [number, number][] {
  const r = Math.max(radiusM, 1);
  const dLat = r / 111_320;
  const dLon = r / (111_320 * Math.max(Math.cos((lat * Math.PI) / 180), 0.01));
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (2 * Math.PI * i) / steps;
    ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return ring;
}
