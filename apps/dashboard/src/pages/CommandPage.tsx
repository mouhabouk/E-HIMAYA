// covers: phase L3 (docs/phase-l/design-l3.md §6): the governor's and the minister's command screen.
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { ErrorBox, Loading } from "../components/Feedback";
import { Bars, Clock, DirectiveForm, DirectiveItem, FigureTiles, LevelPill, Panel, SimBadge } from "../components/crisis/CrisisBits";
import { crisisKeys, flatten, type Axis } from "../lib/crisis";
import { displayName, isSimulated } from "../lib/crisisText";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { initialBoundsFor, TUNISIA_BOUNDS } from "../lib/mapStyle";
import { isIssuer } from "../lib/roles";
import { DEFAULT_QUERY, registerKeys } from "../lib/register";
import { DocumentRefs } from "../components/RegisterBits";

const CommandMap = lazy(() => import("../components/crisis/CommandMap").then((m) => ({ default: m.CommandMap })));

type Tab = "decisions" | "plans" | "sitreps" | "archive";

export function CommandPage() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  const { nameOf: listName } = useGouvernorats();
  const [tab, setTab] = useState<Tab>("decisions");
  const [issuing, setIssuing] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const overview = useQuery({ queryKey: crisisKeys.command, queryFn: ({ signal }) => api.crisisCommand(signal), refetchInterval: 60_000 });
  const boundaries = useQuery({
    queryKey: crisisKeys.boundaries,
    queryFn: ({ signal }) => api.crisisBoundaries(signal),
    staleTime: Infinity,
  });
  const plans = useQuery({
    queryKey: registerKeys.latest,
    queryFn: ({ signal }) => api.registerSearch({ ...DEFAULT_QUERY, sort: "newest", limit: 12 }, signal),
    enabled: tab === "plans",
  });
  const o = overview.data;
  // The reference list's name in the page language, else the name the API gave.
  const nameOf = useCallback(
    (code: number | null) => {
      const n = listName(code);
      return n && n !== String(code) ? n : (o?.gouvernorats.find((g) => g.code === code)?.name ?? n);
    },
    [listName, o],
  );
  const all = useMemo(() => (o ? flatten(o.axes) : []), [o]);
  const levels = useMemo(() => Object.fromEntries((o?.gouvernorats ?? []).map((g) => [g.code, g.level ?? 0])), [o]);
  const labels = useMemo(() => Object.fromEntries((o?.gouvernorats ?? []).map((g) => [g.code, nameOf(g.code) ?? g.name])), [o, nameOf]);
  if (overview.isLoading) return <Loading />;
  if (overview.isError || !o) return <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />;

  const minister = o.role === "minister";
  const home = o.gouvernorat_code;
  const inView = (a: Axis) => selected === null || a.gouvernorat_code === selected || a.gouvernorats.includes(selected);
  const axes = o.axes.filter(inView);
  const bounds =
    selected !== null
      ? initialBoundsFor(selected)
      : minister
        ? TUNISIA_BOUNDS
        : initialBoundsFor(home);
  const simulated = all.some(isSimulated);
  const kinds = Object.entries(o.totals.resources_by_kind).map(([k, v]) => ({ label: t(`resources.kind.${k}`, { defaultValue: k }), value: v }));
  const axisName = (id: string) => {
    const a = all.find((x) => x.id === id);
    return a ? `${a.number} · ${a.gouvernorat_name ?? t("crisis.axis.national")}` : undefined;
  };
  const title = minister ? t("crisis.command.minister") : t("crisis.command.governor", { name: nameOf(home) ?? "" });

  return (
    <div className="ops-room">
      <h1 className="visually-hidden">{title}</h1>
      <div className="ops-room__map">
        <Suspense fallback={<Loading />}>
          <CommandMap
            ariaLabel={t("crisis.map.aria")}
            bounds={bounds}
            styleUrl={mapStyleUrl}
            framed
            tilted={minister}
            boundaries={boundaries.data}
            levels={levels}
            focus={minister ? undefined : home !== null ? [home] : undefined}
            labels={labels}
            axisAreas={all.map((a) => ({ id: a.id, area: a.area, level: a.level }))}
            onSelectGouvernorat={minister ? (code) => setSelected((s) => (s === code ? null : code)) : undefined}
          />
        </Suspense>
      </div>

      <header className="ops-topbar">
        <div className="ops-topbar__title">
          <span className="ops-topbar__eyebrow">{t("crisis.command.eyebrow")}</span>
          <p className="ops-topbar__name" aria-hidden="true">
            {title}
          </p>
        </div>
        {simulated && <SimBadge />}
        <span className="ops-topbar__live">
          <span className="live-dot" aria-hidden="true" />
          {t("crisis.command.active", { count: o.axes.length })}
        </span>
        <Clock />
        {isIssuer(roles) && o.axes.length > 0 && (
          <button type="button" className="btn btn--primary" onClick={() => setIssuing(true)} aria-expanded={issuing}>
            {t("crisis.directive.new")}
          </button>
        )}
      </header>

      <div className="ops-side ops-side--start">
        <Panel title={t("crisis.command.overview")}>
          <FigureTiles f={o.totals} />
        </Panel>
        <Panel
          title={selected !== null ? t("crisis.command.axesIn", { name: nameOf(selected) }) : t("crisis.command.axes")}
          actions={
            selected !== null ? (
              <button type="button" className="btn btn--small btn--ghost" onClick={() => setSelected(null)}>
                {t("crisis.command.allGouvernorats")}
              </button>
            ) : undefined
          }
        >
          {axes.length === 0 ? (
            <p className="ops-empty">{minister ? t("crisis.command.noneNational") : t("crisis.command.none")}</p>
          ) : (
            <ul className="axis-list">
              {axes.map((a) => (
                <li key={a.id} className={`axis-card level-${a.level}`}>
                  <div className="axis-card__head">
                    <LevelPill level={a.level} />
                    <span className="axis-card__no">{a.number}</span>
                    {isSimulated(a) && <SimBadge />}
                  </div>
                  <p className="axis-card__name">
                    {roles.some((r) => r === "operator" || r === "ops_manager") ? (
                      <Link to={`/axes/${a.id}`}>{displayName(a)}</Link>
                    ) : (
                      displayName(a)
                    )}
                  </p>
                  <p className="axis-card__meta">
                    {t(`crisis.kind.${a.kind}`)} · {a.scope === "national" ? t("crisis.axis.national") : a.gouvernorat_name} ·{" "}
                    {t("crisis.axis.since", { at: fmt.dateTime(a.opened_at) })}
                  </p>
                  <dl className="axis-card__figs">
                    <div>
                      <dt>{t("crisis.fig.incidentsOpen")}</dt>
                      <dd>{a.figures.incidents_open}</dd>
                    </div>
                    <div>
                      <dt>{t("crisis.fig.deceased")}</dt>
                      <dd>{a.figures.deceased}</dd>
                    </div>
                    <div>
                      <dt>{t("crisis.fig.evacuated")}</dt>
                      <dd>{a.figures.evacuated}</dd>
                    </div>
                    <div>
                      <dt>{t("crisis.fig.resources")}</dt>
                      <dd>{a.figures.resources}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="ops-side ops-side--end">
        {minister && (
          <Panel title={t("crisis.command.ranking")}>
            {o.gouvernorats.length === 0 ? (
              <p className="ops-empty">{t("crisis.command.noneNational")}</p>
            ) : (
              <table className="ops-table">
                <caption className="visually-hidden">{t("crisis.command.rankingCaption")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("crisis.command.gouvernorat")}</th>
                    <th scope="col">{t("crisis.command.level")}</th>
                    <th scope="col">{t("crisis.fig.incidentsOpen")}</th>
                    <th scope="col">{t("crisis.fig.resources")}</th>
                    <th scope="col">{t("crisis.command.weight")}</th>
                  </tr>
                </thead>
                <tbody>
                  {o.gouvernorats.map((g) => (
                    <tr key={g.code} aria-selected={selected === g.code || undefined}>
                      <th scope="row">
                        <button type="button" className="link-button" onClick={() => setSelected((s) => (s === g.code ? null : g.code))}>
                          {nameOf(g.code) ?? g.name}
                        </button>
                      </th>
                      <td>{g.level !== null ? <LevelPill level={g.level} /> : "—"}</td>
                      <td>{g.incidents_open}</td>
                      <td>{g.resources}</td>
                      <td>{g.weight !== null ? fmt.decimal(g.weight) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        )}
        <Panel title={t("crisis.command.resources")}>
          {kinds.length ? <Bars items={kinds} /> : <p className="ops-empty">{t("crisis.command.noResources")}</p>}
        </Panel>
        <Panel title={t("crisis.command.needs", { n: o.needs.length })}>
          {o.needs.length === 0 ? (
            <p className="ops-empty">{t("crisis.command.noNeeds")}</p>
          ) : (
            <ul className="need-list">
              {o.needs.map((n) => (
                <li key={n.id}>
                  <span className="need-list__q">{n.quantity}</span>
                  <span>{n.label}</span>
                  <span className="muted">{axisName(n.axis_id)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <section className="ops-bottom" aria-label={t("crisis.command.follow")}>
        <div role="tablist" className="ops-tabs" aria-label={t("crisis.command.follow")}>
          {(["decisions", "plans", "sitreps", "archive"] as const).map((k) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} className="ops-tab" onClick={() => setTab(k)}>
              {t(`crisis.command.tab.${k}`)}
            </button>
          ))}
        </div>
        <div role="tabpanel" className="ops-bottom__body" tabIndex={0}>
          {tab === "decisions" &&
            (o.directives.length === 0 ? (
              <p className="ops-empty">{t("crisis.directive.none")}</p>
            ) : (
              <ul className="directive-list">
                {o.directives.map((d) => (
                  <DirectiveItem key={d.id} d={d} axisName={axisName(d.axis_id)} />
                ))}
              </ul>
            ))}
          {tab === "plans" && (
            <>
              {plans.isLoading && <Loading />}
              {plans.data && plans.data.items.length === 0 && <p className="ops-empty">{t("register.command.none")}</p>}
              {plans.data && plans.data.items.length > 0 && <DocumentRefs items={plans.data.items} />}
              <p>
                <Link to="/register">{t("register.command.all")}</Link>
              </p>
            </>
          )}
          {tab === "sitreps" &&
            (o.sitreps.length === 0 ? (
              <p className="ops-empty">{t("crisis.sitrep.none")}</p>
            ) : (
              <ul className="sitrep-list">
                {o.sitreps.map((s) => (
                  <li key={s.id}>
                    <p className="sitrep-list__head">
                      {axisName(s.axis_id)} · {t("crisis.sitrep.number", { n: s.number })} ·{" "}
                      {s.sent_at ? fmt.dateTime(s.sent_at) : t("crisis.sitrep.draft")}
                    </p>
                    {s.assessment && <p>{s.assessment}</p>}
                    <p className="muted">
                      {t("crisis.sitrep.figures", {
                        incidents: s.figures.incidents ?? 0,
                        deceased: s.figures.deceased ?? 0,
                        evacuated: s.figures.evacuated ?? 0,
                        sheltered: s.figures.sheltered ?? 0,
                      })}
                    </p>
                  </li>
                ))}
              </ul>
            ))}
          {tab === "archive" &&
            (o.closed.length === 0 ? (
              <p className="ops-empty">{t("crisis.command.noArchive")}</p>
            ) : (
              <ul className="sitrep-list">
                {o.closed.map((a) => (
                  <li key={a.id}>
                    <p className="sitrep-list__head">
                      {a.number} · {displayName(a)}
                    </p>
                    <p className="muted">
                      {a.closed_at ? fmt.dateTime(a.closed_at) : ""} ·{" "}
                      {t("crisis.sitrep.figures", {
                        incidents: a.closing?.incidents ?? 0,
                        deceased: a.closing?.deceased ?? 0,
                        evacuated: a.closing?.evacuated ?? 0,
                        sheltered: a.closing?.sheltered ?? 0,
                      })}
                    </p>
                  </li>
                ))}
              </ul>
            ))}
        </div>
      </section>

      {issuing && (
        <div className="ops-drawer" role="dialog" aria-modal="false" aria-label={t("crisis.directive.new")}>
          <DirectiveForm axes={all} onDone={() => setIssuing(false)} />
        </div>
      )}
    </div>
  );
}
