// covers: phase N (docs/phase-n/design-n.md §3): the disaster view, apart from the daily command. Ongoing and closed
// disasters with their final summary, a choice of several disasters and gouvernorats, the summed figures and a map
// that shows the places of the chosen disasters only. The rooms, the commander and both committees see it, each in
// its gouvernorat (the API's row-level security).
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { CommitteeHeading } from "../components/CommitteeHeading";
import { FigureTiles, LevelPill, SimBadge } from "../components/crisis/CrisisBits";
import { ErrorBox, Loading } from "../components/Feedback";
import { GouvernoratPicker } from "../components/GouvernoratPicker";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { areaBounds, crisisKeys, type Axis } from "../lib/crisis";
import { displayName, isSimulated } from "../lib/crisisText";
import type { BBox } from "../lib/filters";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { initialBoundsFor, TUNISIA_BOUNDS } from "../lib/mapStyle";
import { canOpenAxes } from "../lib/roles";

const CommandMap = lazy(() => import("../components/crisis/CommandMap").then((m) => ({ default: m.CommandMap })));

/** The box around the given gouvernorats (Tunisia when none). */
export function gouvernoratsBounds(codes: readonly number[]): BBox {
  if (codes.length === 0) return TUNISIA_BOUNDS;
  const boxes = codes.map((c) => initialBoundsFor(c));
  return [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ];
}

function DisasterCard({ a, chosen, onToggle, linked }: { a: Axis; chosen: boolean; onToggle: (on: boolean) => void; linked: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const where = a.gouvernorats.map((c) => nameOf(c) ?? String(c)).join("، ");
  return (
    <li className={`axis-card level-${a.level} disaster-card`}>
      <div className="axis-card__head">
        <label className="check">
          <input type="checkbox" checked={chosen} onChange={(e) => onToggle(e.target.checked)} />
          <span className="visually-hidden">{t("disasters.show", { name: displayName(a) })}</span>
        </label>
        <LevelPill level={a.level} />
        <span className="axis-card__no">{a.number}</span>
        {isSimulated(a) && <SimBadge />}
      </div>
      <p className="axis-card__name">{linked ? <Link to={`/axes/${a.id}`}>{displayName(a)}</Link> : displayName(a)}</p>
      <p className="axis-card__meta">
        {t(`crisis.kind.${a.kind}`)} · {where} · {t("crisis.axis.since", { at: fmt.dateTime(a.opened_at) })}
      </p>
      {a.status === "closed" && a.closing && (
        <div className="disaster-card__closing">
          <p className="muted">
            {t("disasters.closedAfter", { at: a.closed_at ? fmt.dateTime(a.closed_at) : "—", hours: fmt.number(a.closing.hours) })}
          </p>
          {a.closing.summary && <p>{a.closing.summary}</p>}
        </div>
      )}
    </li>
  );
}

export function DisastersPage() {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const { nameOf } = useGouvernorats();
  const roles = user?.identity.roles ?? [];
  const [state, setState] = useState<"open" | "closed">("open");
  // null: every gouvernorat, every disaster (the default until the user narrows the view).
  const [codes, setCodes] = useState<number[] | null>(null);
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const axes = useQuery({ queryKey: crisisKeys.axes(state), queryFn: ({ signal }) => api.crisisAxes(state, signal), refetchInterval: 60_000 });
  const boundaries = useQuery({ queryKey: crisisKeys.boundaries, queryFn: ({ signal }) => api.crisisBoundaries(signal), staleTime: Infinity });

  const all = useMemo(() => axes.data ?? [], [axes.data]);
  const options = useMemo(() => [...new Set(all.flatMap((a) => a.gouvernorats))].sort((a, b) => a - b), [all]);
  const selectedCodes = codes ?? options;
  const visible = all.filter((a) => a.gouvernorats.some((c) => selectedCodes.includes(c)) || a.gouvernorats.length === 0);
  const chosen = visible.filter((a) => picked === null || picked.has(a.id));
  const ids = chosen.map((a) => a.id);
  const places = useQuery({
    queryKey: crisisKeys.disasterMap(ids),
    queryFn: ({ signal }) => api.disasterMap(ids, signal),
    enabled: ids.length > 0,
    refetchInterval: state === "open" ? 60_000 : false,
  });
  const p = places.data;
  const levels: Record<number, number> = {};
  for (const a of chosen) for (const c of a.gouvernorats) levels[c] = Math.max(levels[c] ?? 0, a.level);
  const shownCodes = [...new Set(chosen.flatMap((a) => a.gouvernorats))].filter((c) => selectedCodes.includes(c));
  const bounds = areaBounds(p?.areas.map((x) => x.area) ?? []) ?? gouvernoratsBounds(shownCodes);
  const toggle = (id: string, on: boolean) => {
    const next = new Set(picked ?? visible.map((a) => a.id));
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };
  const changeState = (s: "open" | "closed") => {
    setState(s);
    setCodes(null);
    setPicked(null);
  };

  return (
    <div className="disasters-page">
      <div className="page-head">
        <div>
          <PageTitle icon="warning" tone="red">
            {t("disasters.title")}
          </PageTitle>
          <CommitteeHeading />
        </div>
        {canOpenAxes(roles) && (
          <div className="page-head__actions">
            <Link className="btn" to="/axes">
              {t("nav.axes")}
            </Link>
          </div>
        )}
      </div>
      <p className="muted">{t("disasters.intro")}</p>
      <div className="segmented" role="radiogroup" aria-label={t("crisis.axes.state")}>
        {(["open", "closed"] as const).map((s) => (
          <label key={s} className="segmented__item">
            <input type="radio" name="disasters-state" checked={state === s} onChange={() => changeState(s)} />
            <span>{t(`disasters.${s}`)}</span>
          </label>
        ))}
      </div>
      {axes.isLoading && <Loading />}
      {axes.isError && <ErrorBox error={axes.error} onRetry={() => void axes.refetch()} />}
      {axes.data && all.length === 0 && <p className="ops-empty card">{t(state === "open" ? "disasters.noneOpen" : "disasters.noneClosed")}</p>}
      {all.length > 0 && (
        <>
          {options.length > 1 && (
            <GouvernoratPicker legend={t("disasters.gouvernorats")} options={options} selected={selectedCodes} onChange={(c) => setCodes(c)} />
          )}
          <section className="card" aria-labelledby="disasters-summary">
            <h2 id="disasters-summary">{t("disasters.summary", { count: chosen.length })}</h2>
            {chosen.length === 0 ? (
              <p className="muted">{t("disasters.chooseOne")}</p>
            ) : places.isError ? (
              <ErrorBox error={places.error} onRetry={() => void places.refetch()} />
            ) : p ? (
              <FigureTiles f={p.figures} />
            ) : (
              <Loading />
            )}
          </section>
          <div className="disasters-layout">
            <section className="disasters-layout__list" aria-labelledby="disasters-list">
              <div className="disasters-layout__head">
                <h2 id="disasters-list">{t("disasters.list")}</h2>
                <button type="button" className="btn btn--small btn--ghost" onClick={() => setPicked(null)}>
                  {t("committee.selectAll")}
                </button>
                <button type="button" className="btn btn--small btn--ghost" onClick={() => setPicked(new Set())}>
                  {t("committee.selectNone")}
                </button>
              </div>
              <ul className="axis-list">
                {visible.map((a) => (
                  <DisasterCard key={a.id} a={a} chosen={picked === null || picked.has(a.id)} onToggle={(on) => toggle(a.id, on)} linked={canOpenAxes(roles)} />
                ))}
              </ul>
            </section>
            <div className="disasters-layout__map">
              <Suspense fallback={<Loading />}>
                <CommandMap
                  ariaLabel={t("disasters.mapAria", { count: chosen.length })}
                  bounds={bounds}
                  styleUrl={mapStyleUrl}
                  boundaries={boundaries.data}
                  levels={levels}
                  focus={shownCodes.length > 0 ? shownCodes : undefined}
                  labels={Object.fromEntries(shownCodes.map((c) => [c, nameOf(c) ?? String(c)]))}
                  axisAreas={p?.areas ?? []}
                  incidents={p?.incidents ?? []}
                  shelters={p?.shelters ?? []}
                  evacuations={p?.evacuations ?? []}
                  tilted={false}
                />
              </Suspense>
            </div>
          </div>
          {p && (p.incidents.length > 0 || p.shelters.length > 0) && (
            <section className="card" aria-labelledby="disasters-places">
              <h2 id="disasters-places">{t("disasters.places")}</h2>
              <ul className="disasters-places">
                {p.incidents.map((i) => (
                  <li key={i.id}>
                    <span className="chip">{t(`category.${i.category}`)}</span> {i.title ?? "—"} · {nameOf(i.gouvernorat_code) ?? ""}
                  </li>
                ))}
                {p.shelters.map((s) => (
                  <li key={s.id}>
                    <span className="chip">{t("disasters.shelter")}</span> {s.name} · {t("disasters.occupancy", { n: s.occupants, of: s.capacity })}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
