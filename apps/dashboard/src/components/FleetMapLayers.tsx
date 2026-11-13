// covers: OS3 follow-ups (docs/phase-os3/design-os3b.md §5; Yamen 2026-11-13: «أي خريطة في المنظومة يجب أن تكون لها
// نظير ويمكن كشفها أو حجبها»): the data drawn on the coverage page and the fleet report are also optional layers of
// the official interactive map, without leaving their pages: the live coverage of a gouvernorat (délégations and
// units, with the neighbouring units for the central room), the repositioning orders on their way, and the
// readiness of the fleet per gouvernorat. Each layer follows the rights of its page; a click opens the page.
import { useQuery } from "@tanstack/react-query";
import { useId, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { COVERAGE_FAMILIES, fleetKeys, readinessTone, type CoverageFamily } from "../lib/fleet";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { POI_ICON_PATHS } from "../lib/poiIcons";
import { canReadCoverage, canReadFleet } from "../lib/roles";
import type { FolderExtra } from "./MapDataLayers";
import type { MapLine, MapPoi } from "./MapView";

/** The tones of docs/design-system.md, as the map paints them. */
const COLOUR = {
  green: "#188038",
  red: "#d7141a",
  amber: "#b06f00",
  navy: "#1f3fa0",
  purple: "#7838a0",
  slate: "#5b6478",
} as const;
const DOT = "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z";
const KEYS = { coverage: "map.layer.coverage", orders: "map.layer.orders", readiness: "map.layer.readiness" } as const;

function stored(key: string): boolean {
  try {
    return sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function useSwitch(key: string): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => stored(key));
  return [
    on,
    (value) => {
      setOn(value);
      try {
        sessionStorage.setItem(key, value ? "1" : "0");
      } catch {
        /* ignore */
      }
    },
  ];
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (on: boolean) => void; label: string }) {
  const id = useId();
  return (
    <label htmlFor={id} className="checkbox">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function thisMonth(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Tunis", year: "numeric", month: "2-digit" }).format(new Date());
}

export interface FleetMapLayers {
  /**
   * The switches, for the «موارد الحماية المدنية» folder of the layer panel (ML, Yamen 2026-11-13): the coverage's
   * family, gouvernorat, neighbours and legend show under its switch when it is on.
   */
  extras: FolderExtra[];
  pois: MapPoi[];
  lines: MapLine[];
}

export function useFleetMapLayers(): FleetMapLayers {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const roles = user?.identity.roles ?? [];
  const national = user?.identity.national ?? false;
  const coverageAllowed = canReadCoverage(roles);
  const fleetAllowed = canReadFleet(roles);
  const [coverageOn, setCoverage] = useSwitch(KEYS.coverage);
  const [ordersOn, setOrders] = useSwitch(KEYS.orders);
  const [readinessOn, setReadiness] = useSwitch(KEYS.readiness);
  const [neighbours, setNeighbours] = useState(false);
  const [family, setFamily] = useState<CoverageFamily>("medical");
  const [picked, setPicked] = useState<number | null>(null);
  const familyId = useId();
  const gouvId = useId();
  const showCoverage = coverageAllowed && coverageOn;
  const showOrders = coverageAllowed && ordersOn;
  const showReadiness = fleetAllowed && readinessOn;
  const gouvernorat = national ? (picked ?? gouvernorats.list[0]?.code ?? null) : null;
  const withNeighbours = national && neighbours;

  const coverage = useQuery({
    queryKey: fleetKeys.coverage(gouvernorat, withNeighbours),
    queryFn: ({ signal }) => api.coverage(gouvernorat, signal, withNeighbours),
    enabled: showCoverage && (!national || gouvernorat !== null),
    refetchInterval: 60_000,
  });
  const orders = useQuery({
    queryKey: fleetKeys.orders(null),
    queryFn: ({ signal }) => api.repositionOrders(null, signal),
    enabled: showOrders,
    refetchInterval: 30_000,
  });
  const month = thisMonth();
  const report = useQuery({
    queryKey: fleetKeys.report(month, null),
    queryFn: ({ signal }) => api.fleetReport({ month, gouvernorat: null }, signal),
    enabled: showReadiness,
  });

  const pois = useMemo<MapPoi[]>(() => {
    const out: MapPoi[] = [];
    const data = showCoverage ? coverage.data : undefined;
    if (data) {
      for (const d of data.delegations) {
        const c = d.families[family];
        const state = c.covered ? "covered" : c.baseline_covered ? "lost" : "notCovered";
        out.push({
          id: `cov-place-${d.id}`,
          lon: d.lon,
          lat: d.lat,
          kind: "place",
          iconPath: DOT,
          colour: c.covered ? COLOUR.green : c.baseline_covered ? COLOUR.red : COLOUR.amber,
          title: t("map.fleet.placeTitle", { place: lang === "ar" ? d.name_ar : d.name_fr, state: t(`coverage.${state}`) }),
          subtitle: t("map.fleet.placeSub", {
            minutes: c.minutes === null ? "—" : t("coverage.minutes", { n: fmt.number(c.minutes) }),
            target: c.target,
            unit: c.unit_name ?? "—",
          }),
          details: [t("coverage.population") + " " + fmt.number(d.population)].concat(c.neighbour ? [t("coverage.fromNeighbour")] : []),
          href: "/coverage",
        });
      }
      for (const u of data.units) {
        out.push({
          id: `cov-unit-${u.id}`,
          lon: u.lon,
          lat: u.lat,
          kind: "place",
          iconPath: POI_ICON_PATHS.unit,
          colour: u.ready[family] === 0 ? COLOUR.slate : u.neighbour ? COLOUR.purple : COLOUR.navy,
          title: lang === "ar" ? u.name_ar : u.name_fr,
          subtitle: t("map.fleet.unitSub", { n: fmt.number(u.ready[family]), turnout: fmt.number(u.turnout_minutes) }),
          details: u.neighbour ? [t("coverage.neighbourUnit", { gouvernorat: gouvernorats.nameOf(u.gouvernorat_code) ?? "" })] : [],
          href: "/coverage",
        });
      }
    }
    if (showOrders) {
      for (const o of orders.data?.items ?? []) {
        if (!o.to_point || o.state === "arrived" || o.state === "closed") continue;
        out.push({
          id: `order-${o.id}`,
          lon: o.to_point[0],
          lat: o.to_point[1],
          kind: "place",
          iconPath: POI_ICON_PATHS.resource_busy,
          colour: o.overdue ? COLOUR.red : COLOUR.purple,
          title: t("map.fleet.orderTitle", { label: o.label, kind: t(`coverage.orderKind.${o.kind}`) }),
          subtitle: `${t("coverage.orderLine", { label: o.label, from: o.from_unit, to: o.to_unit })} · ${t(`coverage.orderState.${o.state}`)}`,
          details: o.overdue ? [t("coverage.overdue", { n: orders.data?.ack_minutes ?? 2 })] : [],
          href: "/coverage",
        });
      }
    }
    const r = showReadiness ? report.data : undefined;
    if (r) {
      for (const row of r.rows) {
        if (!row.point) continue;
        const tone = readinessTone(row.readiness_pct, r);
        out.push({
          id: `readiness-${row.gouvernorat_code}`,
          lon: row.point[0],
          lat: row.point[1],
          kind: "place",
          iconPath: POI_ICON_PATHS.sensor,
          colour: COLOUR[tone],
          title: t("map.fleet.readinessTitle", {
            name: lang === "ar" ? row.name_ar : row.name_fr,
            pct: row.readiness_pct === null ? "—" : fmt.percent(row.readiness_pct / 100),
          }),
          subtitle: t("map.fleet.readinessSub", { month: r.month, cost: fmt.number(Number(row.cost_total)), n: fmt.number(row.vehicles) }),
          href: "/fleet/report",
        });
      }
    }
    return out;
  }, [showCoverage, coverage.data, family, showOrders, orders.data, showReadiness, report.data, t, lang, fmt, gouvernorats]);

  const lines = useMemo<MapLine[]>(
    () =>
      showOrders
        ? (orders.data?.items ?? [])
            .filter((o) => o.from_point && o.to_point && o.state !== "arrived" && o.state !== "closed")
            .map((o) => ({
              id: `order-line-${o.id}`,
              coordinates: [o.from_point as [number, number], o.to_point as [number, number]],
              colour: o.overdue ? COLOUR.red : COLOUR.purple,
            }))
        : [],
    [showOrders, orders.data],
  );

  if (!coverageAllowed && !fleetAllowed) return { extras: [], pois, lines };
  const legendOf = (rows: [string, string][]): ReactNode =>
    rows.length > 0 ? (
      <ul className="map-legend">
        {rows.map(([colour, label]) => (
          <li key={label}>
            <span className="fleet-map-swatch" style={{ background: colour }} aria-hidden="true" />
            <span>{label}</span>
          </li>
        ))}
      </ul>
    ) : null;
  const coverageLegend: [string, string][] = [
    [COLOUR.green, t("map.fleet.legendCovered")],
    [COLOUR.red, t("map.fleet.legendLost")],
    [COLOUR.amber, t("map.fleet.legendOut")],
  ];
  if (withNeighbours) coverageLegend.push([COLOUR.purple, t("map.fleet.legendNeighbour")]);
  const hint = <p className="muted">{t("map.fleet.hint")}</p>;
  const coverageNote = (
    <div className="fleet-map-layers">
      <div className="field">
        <label htmlFor={familyId}>{t("map.fleet.family")}</label>
        <select id={familyId} value={family} onChange={(e) => setFamily(e.target.value as CoverageFamily)}>
          {COVERAGE_FAMILIES.map((f) => (
            <option key={f} value={f}>
              {t(`coverage.families.${f}`)}
            </option>
          ))}
        </select>
      </div>
      {national && (
        <div className="field">
          <label htmlFor={gouvId}>{t("map.fleet.gouvernorat")}</label>
          <select id={gouvId} value={gouvernorat ?? ""} onChange={(e) => setPicked(Number(e.target.value))}>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      )}
      {national && <Toggle checked={neighbours} onChange={setNeighbours} label={t("map.fleet.neighbours")} />}
      {legendOf(coverageLegend)}
      {hint}
    </div>
  );
  const coverageSource = { to: "/coverage", label: t("mapLayers.screen.coverage") };
  const extras: FolderExtra[] = [];
  if (coverageAllowed) {
    extras.push(
      { key: "coverage", label: t("map.fleet.coverage"), on: coverageOn, onChange: setCoverage, source: coverageSource, note: coverageNote },
      {
        key: "orders",
        label: t("map.fleet.orders"),
        on: ordersOn,
        onChange: setOrders,
        source: coverageSource,
        note: legendOf([[COLOUR.purple, t("map.fleet.legendOrder")]]),
      },
    );
  }
  if (fleetAllowed) {
    extras.push({
      key: "readiness",
      label: t("map.fleet.readiness"),
      on: readinessOn,
      onChange: setReadiness,
      source: { to: "/fleet/report", label: t("mapLayers.screen.fleet") },
    });
  }
  return { extras, pois, lines };
}
