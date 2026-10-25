import type { TFunction } from "i18next";
import { Fragment, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessageKey } from "../lib/api";
import type { BBox } from "../lib/filters";
import type { Formatters } from "../lib/format";
import { useFormat } from "../lib/hooks";
import { isPoiKind, POI_ICON_PATHS, type PoiKind } from "../lib/poiIcons";
import {
  CERTIFICATE_STATUSES,
  EQUIPMENT_KINDS,
  FEATURE_KINDS,
  HAZMAT_UNITS,
  isOneOf,
  MAINTENANCE_STATUSES,
  ORG_ALERT_KINDS,
  ORG_CERTIFICATE_STATES,
  ORG_FAMILIES,
  ORG_KINDS,
  ORG_STATUSES,
  REQUIREMENTS,
  TRAINING_STATUSES,
  type Classification,
  type DownloadLink,
  type Hazmat,
  type MapFeature,
} from "../lib/types";
import { kindFieldRows, VISIBILITY_TONE, type KindFieldValue } from "../lib/kindFields";
import { Pill } from "./Icon";
import type { MapPoi } from "./MapView";

// ---------- Labels with a translated fallback for values added later by the API ----------

export function orgKindLabel(t: TFunction, kind: string | null | undefined): string {
  if (!kind) return t("common.notAvailable");
  return isOneOf(ORG_KINDS, kind) ? t(`orgs.kind.${kind}`) : t("orgs.kind.other");
}

export function familyLabel(t: TFunction, family: string): string {
  return isOneOf(ORG_FAMILIES, family) ? t(`orgs.family.${family}`) : t("orgs.family.other", { key: family });
}

/** "Établissement recevant du public · catégorie 3", or the family alone. */
export function classificationText(t: TFunction, fmt: Formatters, c: Classification | null | undefined): string {
  if (!c) return t("common.notAvailable");
  const family = familyLabel(t, c.family);
  return typeof c.category === "number"
    ? `${family} · ${t("orgs.erpCategory", { category: fmt.number(c.category) })}`
    : family;
}

export function requirementLabel(t: TFunction, code: string): string {
  return isOneOf(REQUIREMENTS, code) ? t(`orgs.requirement.${code}`) : t("orgs.requirement.other", { key: code });
}

export function alertLabel(t: TFunction, kind: string): string {
  return isOneOf(ORG_ALERT_KINDS, kind) ? t(`orgs.alertKind.${kind}`) : t("orgs.alertKind.other", { key: kind });
}

export function featureKindLabel(t: TFunction, kind: string): string {
  return isOneOf(FEATURE_KINDS, kind) ? t(`orgs.featureKind.${kind}`) : t("orgs.featureKind.other");
}

export function equipmentKindLabel(t: TFunction, kind: string): string {
  return isOneOf(EQUIPMENT_KINDS, kind) ? t(`orgs.equipmentKind.${kind}`) : t("orgs.equipmentKind.other");
}

/** "2,5 t" with the unit translated. */
export function hazmatQuantity(t: TFunction, fmt: Formatters, h: Pick<Hazmat, "quantity" | "unit">): string {
  if (h.quantity === null) return t("common.notAvailable");
  const unit = h.unit ? (isOneOf(HAZMAT_UNITS, h.unit) ? t(`orgs.units.${h.unit}`) : h.unit) : "";
  return `${fmt.decimal(h.quantity)}${unit ? ` ${unit}` : ""}`;
}

/** ISO date ("2026-10-19") or date-time shown as a calendar date. */
export function formatDay(fmt: Formatters, iso: string | null | undefined, fallback: string): string {
  if (!iso) return fallback;
  return fmt.date(iso);
}

// ---------- Chips and badges (colour always paired with text) ----------

export function OrgStatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const known = isOneOf(ORG_STATUSES, status);
  return (
    <span className={`chip chip--org-${known ? status : "unknown"}`}>
      <span className="chip__dot" aria-hidden="true" />
      {known ? t(`orgs.status.${status}`) : status}
    </span>
  );
}

export function CertificateChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const known = isOneOf(ORG_CERTIFICATE_STATES, status) || isOneOf(CERTIFICATE_STATUSES, status);
  return (
    <span className={`tag tag--cert tag--cert-${known ? status : "none"}`}>
      {known ? t(`orgs.certificate.${status}`) : t("common.notAvailable")}
    </span>
  );
}

export function TrainingBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const s = isOneOf(TRAINING_STATUSES, status) ? status : "unknown";
  return <span className={`tag tag--level-${s === "valid" ? "ok" : s === "expiring" ? "warn" : s === "expired" ? "bad" : "none"}`}>{t(`orgs.trainingStatus.${s}`)}</span>;
}

export function MaintenanceBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const s = isOneOf(MAINTENANCE_STATUSES, status) ? status : "unknown";
  return <span className={`tag tag--level-${s === "ok" ? "ok" : s === "due_soon" ? "warn" : s === "overdue" ? "bad" : "none"}`}>{t(`orgs.maintenanceStatus.${s}`)}</span>;
}

export function HazmatTag({ count }: { count: number }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (count <= 0) return <span className="muted">{fmt.number(0)}</span>;
  return <span className="tag tag--hazmat">{t("orgs.hazmatBadge", { count: fmt.number(count) })}</span>;
}

export function PoiIcon({ kind }: { kind: PoiKind }) {
  return (
    <span className={`map-poi map-poi--${kind} map-poi--static`} aria-hidden="true">
      <svg viewBox="0 0 24 24" focusable="false">
        <path d={POI_ICON_PATHS[kind]} fill="currentColor" fillRule="evenodd" />
      </svg>
    </span>
  );
}

/** Small inline icon (building, warning…) for text runs; decorative. */
export function InlineIcon({ kind, size = 14 }: { kind: PoiKind; size?: number }) {
  return (
    <svg className="inline-icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={POI_ICON_PATHS[kind]} fill="currentColor" fillRule="evenodd" />
    </svg>
  );
}

/** Legend of the institutions layer: same shapes as on the map, with their labels. */
export function MapLegend({ items }: { items: { kind: PoiKind; label: string }[] }) {
  const { t } = useTranslation();
  return (
    <ul className="map-legend" aria-label={t("orgs.layer.legend")}>
      {items.map((i) => (
        <li key={i.kind}>
          <PoiIcon kind={i.kind} />
          <span>{i.label}</span>
        </li>
      ))}
    </ul>
  );
}

const LINK_LIFETIME_MS = 9 * 60_000; // pre-signed for 10 minutes

/**
 * Asks the API for a pre-signed link (documents, certificate PDFs) on demand, then shows it as a plain link:
 * links expire after 10 minutes, so they are never fetched in advance nor kept longer.
 */
export function DownloadButton({ fetchLink, label }: { fetchLink: () => Promise<DownloadLink>; label: string }) {
  const { t } = useTranslation();
  const [state, setState] = useState<
    { s: "idle" } | { s: "loading" } | { s: "ready"; url: string } | { s: "error"; error: unknown }
  >({ s: "idle" });

  useEffect(() => {
    if (state.s !== "ready") return;
    const id = setTimeout(() => setState({ s: "idle" }), LINK_LIFETIME_MS);
    return () => clearTimeout(id);
  }, [state]);

  const get = () => {
    setState({ s: "loading" });
    fetchLink().then(
      (link) => setState({ s: "ready", url: link.url }),
      (error: unknown) => setState({ s: "error", error }),
    );
  };

  if (state.s === "ready") {
    return (
      <span className="download">
        <a href={state.url} target="_blank" rel="noopener noreferrer" aria-label={`${t("orgs.download.open")} — ${label}`}>
          {t("orgs.download.open")}
        </a>
        <span className="muted download__hint">{t("orgs.download.validity")}</span>
      </span>
    );
  }
  return (
    <span className="download">
      <button
        type="button"
        className="btn btn--small"
        onClick={get}
        disabled={state.s === "loading"}
        aria-label={`${t("orgs.download.get")} — ${label}`}
      >
        {state.s === "loading" ? t("orgs.download.getting") : t("orgs.download.get")}
      </button>
      {state.s === "error" && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(state.error))}
        </span>
      )}
    </span>
  );
}

// ---------- Map helpers ----------

/** Bounds around a set of points (at least ~1 km wide). */
export function pointsBounds(points: readonly { lon: number; lat: number }[], pad = 0.006): BBox | null {
  if (points.length === 0) return null;
  const lons = points.map((p) => p.lon);
  const lats = points.map((p) => p.lat);
  return [Math.min(...lons) - pad, Math.min(...lats) - pad, Math.max(...lons) + pad, Math.max(...lats) + pad];
}

/** Institution point + its features (evacuation, water, alarms) as map points with distinct kinds. */
export function orgPois(
  org: { id: string; name: string; location: { lat: number; lon: number } | null },
  hasHazmat: boolean,
  features: readonly MapFeature[],
  label: (f: MapFeature) => string,
  subtitle?: string,
): MapPoi[] {
  const pois: MapPoi[] = [];
  if (org.location) {
    pois.push({
      id: org.id,
      lon: org.location.lon,
      lat: org.location.lat,
      kind: hasHazmat ? "org_hazmat" : "org",
      title: org.name,
      subtitle,
    });
  }
  for (const f of features) {
    if (!isPoiKind(f.kind)) continue;
    pois.push({ id: f.id, lon: f.location.lon, lat: f.location.lat, kind: f.kind, title: label(f) });
  }
  return pois;
}

export function useLegendItems(withHazmat: boolean, withOrg = true): { kind: PoiKind; label: string }[] {
  const { t } = useTranslation();
  return useMemo(() => {
    const items: { kind: PoiKind; label: string }[] = [];
    if (withOrg) items.push({ kind: "org", label: t("orgs.layer.org") });
    if (withHazmat) items.push({ kind: "org_hazmat", label: t("orgs.layer.hazmat") });
    items.push(
      { kind: "evacuation_point", label: t("orgs.featureKind.evacuation_point") },
      { kind: "water_point", label: t("orgs.featureKind.water_point") },
      { kind: "alarm", label: t("orgs.featureKind.alarm") },
    );
    return items;
  }, [t, withHazmat, withOrg]);
}


/**
 * The answers to the kind's fields (P2a), each with the badge of who may see it. The API already left out what this
 * reader may not see. Working list [SIM] until the Office approves it.
 */
export function KindFieldsList({ kind, values }: { kind: string; values: Readonly<Record<string, KindFieldValue>> | undefined }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const rows = kindFieldRows(kind, values);
  if (rows.length === 0) return <p className="muted">{t("common.notAvailable")}</p>;
  return (
    <dl className="fields kind-fields">
      {rows.map(({ spec, value }) => (
        <Fragment key={spec.key}>
          <dt>
            {t(`orgs.kindField.${spec.key}`, { defaultValue: spec.key })}{" "}
            <Pill tone={VISIBILITY_TONE[spec.visibility]}>{t(`orgs.visibility.${spec.visibility}`)}</Pill>
          </dt>
          <dd dir={spec.key === "reception_phone" ? "ltr" : "auto"}>
            {typeof value === "boolean"
              ? value
                ? t("common.yes")
                : t("common.no")
              : typeof value === "number"
                ? fmt.number(value)
                : value}
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}
