// covers: phase L3 (docs/phase-l/design-l3.md §2, §6): field command of one axis for the operations rooms.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Bars, Clock, DirectiveItem, FigureTiles, LevelPill, Panel, SimBadge } from "../components/crisis/CrisisBits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { areaBounds, AXIS_LEVELS, crisisKeys, hoursUntil, type Axis, type AxisDetail } from "../lib/crisis";
import { DEFAULT_QUERY, registerKeys } from "../lib/register";
import { DocumentRefs } from "../components/RegisterBits";
import { SearchTab } from "../components/InventorySearch";
import { inventoryKeys } from "../lib/inventory";
import { displayName, isSimulated, simText } from "../lib/crisisText";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";

const CommandMap = lazy(() => import("../components/crisis/CommandMap").then((m) => ({ default: m.CommandMap })));

type Tab = "decisions" | "documents" | "sitreps" | "timeline" | "resources";

function useInvalidate() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: crisisKeys.all });
}

function Suggestions({ axis }: { axis: Axis }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const done = useInvalidate();
  const list = useQuery({ queryKey: crisisKeys.suggestions(axis.id), queryFn: ({ signal }) => api.axisSuggestions(axis.id, signal) });
  const attach = useMutation({ mutationFn: (id: string) => api.attachAxisIncident(axis.id, id), onSuccess: done });
  const dismiss = useMutation({ mutationFn: (id: string) => api.dismissAxisSuggestion(axis.id, id), onSuccess: done });
  const items = list.data ?? [];
  return (
    <Panel title={t("crisis.axis.suggested", { n: items.length })}>
      {list.isLoading && <Loading />}
      {!list.isLoading && items.length === 0 && <p className="ops-empty">{t("crisis.axis.noSuggestion")}</p>}
      <ul className="incident-list">
        {items.map((i) => (
          <li key={i.id}>
            <span className={`sev sev--${(i.severity ?? 0) >= 4 ? "high" : "mid"}`} aria-hidden="true" />
            <span className="incident-list__what">
              {t(`category.${i.category}`)}
              {i.title ? ` · ${i.title}` : ""}
            </span>
            <span className="muted">{fmt.time(i.opened_at)}</span>
            <span className="incident-list__actions">
              <button type="button" className="btn btn--small btn--primary" onClick={() => attach.mutate(i.id)} disabled={attach.isPending}>
                {axis.can_manage ? t("crisis.axis.attach") : t("crisis.axis.propose")}
              </button>
              {axis.can_manage && (
                <button type="button" className="btn btn--small btn--ghost" onClick={() => dismiss.mutate(i.id)}>
                  {t("crisis.axis.dismiss")}
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {attach.isError && <p role="alert" className="field__error">{t(errorMessageKey(attach.error))}</p>}
    </Panel>
  );
}

/** One-line forms of the room: a shelter, an evacuation zone, a need. */
function QuickAdd({ axis, kind }: { axis: Axis; kind: "shelter" | "evacuation" | "need" }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [name, setName] = useState("");
  const [n, setN] = useState("");
  const [m, setM] = useState("");
  const add = useMutation({
    mutationFn: (): Promise<unknown> => {
      const a = Number(n) || 0;
      if (kind === "shelter") return api.addShelter(axis.id, { name: name.trim(), capacity: a, occupants: Number(m) || 0 });
      if (kind === "evacuation") return api.addEvacuation(axis.id, { name: name.trim(), evacuated: a });
      return api.raiseNeed(axis.id, { label: name.trim(), quantity: Math.max(1, a) });
    },
    onSuccess: () => {
      setName("");
      setN("");
      setM("");
      done();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (name.trim().length >= 2) add.mutate();
  };
  return (
    <form className="quick-add" onSubmit={submit} aria-label={t(`crisis.add.${kind}`)}>
      <label htmlFor={`${id}-n`} className="visually-hidden">
        {t(`crisis.add.${kind}Name`)}
      </label>
      <input id={`${id}-n`} value={name} placeholder={t(`crisis.add.${kind}Name`)} onChange={(e) => setName(e.target.value)} />
      <label htmlFor={`${id}-q`} className="visually-hidden">
        {t(`crisis.add.${kind}Count`)}
      </label>
      <input id={`${id}-q`} inputMode="numeric" value={n} placeholder={t(`crisis.add.${kind}Count`)} onChange={(e) => setN(e.target.value)} />
      {kind === "shelter" && (
        <>
          <label htmlFor={`${id}-o`} className="visually-hidden">
            {t("crisis.add.occupants")}
          </label>
          <input id={`${id}-o`} inputMode="numeric" value={m} placeholder={t("crisis.add.occupants")} onChange={(e) => setM(e.target.value)} />
        </>
      )}
      <button type="submit" className="btn btn--small btn--primary" disabled={add.isPending}>
        {t("crisis.add.submit")}
      </button>
      {add.isError && <p role="alert" className="field__error">{t(errorMessageKey(add.error))}</p>}
    </form>
  );
}

function Commander({ axis }: { axis: Axis }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const { list } = useGouvernorats();
  const id = useId();
  const [mode, setMode] = useState<"none" | "escalate" | "close">("none");
  const [text, setText] = useState("");
  const [extra, setExtra] = useState<number[]>([]);
  const level = useMutation({ mutationFn: (l: number) => api.updateAxis(axis.id, { version: axis.version, level: l }), onSuccess: done });
  const escalate = useMutation({ mutationFn: () => api.escalateAxis(axis.id, extra, text.trim()), onSuccess: () => (setMode("none"), done()) });
  const close = useMutation({ mutationFn: () => api.closeAxis(axis.id, text.trim()), onSuccess: () => (setMode("none"), done()) });
  const error = level.error ?? escalate.error ?? close.error;
  return (
    <div className="commander">
      <label htmlFor={`${id}-l`}>{t("crisis.axis.level")}</label>
      <select id={`${id}-l`} value={axis.level} onChange={(e) => level.mutate(Number(e.target.value))}>
        {AXIS_LEVELS.map((l) => (
          <option key={l} value={l}>
            {l} · {t(`crisis.level.${l}`)}
          </option>
        ))}
      </select>
      <button type="button" className="btn btn--small" onClick={() => setMode(mode === "escalate" ? "none" : "escalate")}>
        {axis.scope === "national" ? t("crisis.axis.addGouvernorats") : t("crisis.axis.escalate")}
      </button>
      {!axis.parent_id && (
        <button type="button" className="btn btn--small btn--danger" onClick={() => setMode(mode === "close" ? "none" : "close")}>
          {t("crisis.axis.close")}
        </button>
      )}
      {mode !== "none" && (
        <form
          className="ops-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (mode === "escalate") escalate.mutate();
            else close.mutate();
          }}
        >
          {mode === "escalate" && (
            <fieldset className="chips">
              <legend>{t("crisis.axis.gouvernorats")}</legend>
              {list
                .filter((g) => !axis.gouvernorats.includes(g.code))
                .map((g) => (
                  <label key={g.code}>
                    <input
                      type="checkbox"
                      checked={extra.includes(g.code)}
                      onChange={(e) => setExtra((x) => (e.target.checked ? [...x, g.code] : x.filter((c) => c !== g.code)))}
                    />
                    {g.name}
                  </label>
                ))}
            </fieldset>
          )}
          <label htmlFor={`${id}-t`}>{mode === "escalate" ? t("crisis.axis.reason") : t("crisis.axis.summary")}</label>
          <textarea id={`${id}-t`} rows={2} value={text} onChange={(e) => setText(e.target.value)} />
          <button type="submit" className="btn btn--primary btn--small" disabled={text.trim().length < (mode === "close" ? 10 : 5)}>
            {mode === "escalate" ? t("crisis.axis.escalateConfirm") : t("crisis.axis.closeConfirm")}
          </button>
        </form>
      )}
      {error && <p role="alert" className="field__error">{t(errorMessageKey(error))}</p>}
    </div>
  );
}

/** The plan of the axis: a plan of the register in force (phase L3b), else the free text of L3. */
function PlanBlock({ axis }: { axis: Axis }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [picking, setPicking] = useState(false);
  const [choice, setChoice] = useState("");
  const query = { ...DEFAULT_QUERY, kinds: ["plan" as const], gouvernorat: null, limit: 50, sort: "newest" as const };
  const plans = useQuery({
    queryKey: registerKeys.plans(axis.gouvernorat_code),
    queryFn: ({ signal }) => api.registerSearch(query, signal),
    enabled: picking,
  });
  const save = useMutation({
    mutationFn: (clear: boolean) =>
      api.updateAxis(axis.id, clear ? { version: axis.version, clear_plan_document: true } : { version: axis.version, plan_document_id: choice }),
    onSuccess: () => (setPicking(false), done()),
  });
  const doc = axis.plan_document;
  return (
    <div className="ops-plan">
      {doc ? (
        <p>
          <span className="muted">{t("register.axis.plan")} </span>
          <Link to={`/register/${encodeURIComponent(doc.id)}`} dir="auto">
            {simText(doc.title).text}
          </Link>
          {doc.reference && <span className="muted"> · {doc.reference}</span>}
        </p>
      ) : (
        axis.plan && <p>{axis.plan}</p>
      )}
      {(axis.hazard_plans ?? []).length > 0 && (
        <div className="ops-plan__hazard">
          <p className="muted">{t("plans.axis.title")}</p>
          <ul className="doc-refs">
            {(axis.hazard_plans ?? []).map((p) => (
              <li key={p.id}>
                <span dir="auto">{simText(p.title).text}</span>
                <Link className="btn btn--small" to={`/plans/${encodeURIComponent(p.id)}`} aria-label={t("plans.axis.view", { title: simText(p.title).text })}>
                  {t("plans.view")}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      {axis.can_manage && axis.status === "open" && !picking && (
        <button type="button" className="btn btn--small btn--ghost" onClick={() => setPicking(true)}>
          {doc ? t("register.axis.changePlan") : t("register.axis.pickPlan")}
        </button>
      )}
      {picking && (
        <form
          className="directive__actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (choice) save.mutate(false);
          }}
        >
          <label htmlFor={`${id}-p`} className="visually-hidden">
            {t("register.axis.pickPlan")}
          </label>
          <select id={`${id}-p`} value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">{plans.isLoading ? t("common.loading") : "—"}</option>
            {plans.data?.items.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn--small btn--primary" disabled={!choice || save.isPending}>
            {t("register.axis.setPlan")}
          </button>
          {doc && (
            <button type="button" className="btn btn--small btn--ghost" onClick={() => save.mutate(true)} disabled={save.isPending}>
              {t("register.axis.clearPlan")}
            </button>
          )}
          <button type="button" className="btn btn--small btn--ghost" onClick={() => setPicking(false)}>
            {t("common.cancel")}
          </button>
        </form>
      )}
      {save.isError && <p role="alert" className="field__error">{t(errorMessageKey(save.error))}</p>}
    </div>
  );
}

function Sitreps({ d }: { d: AxisDetail }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [text, setText] = useState("");
  const draft = d.sitreps.find((s) => s.status === "draft" && s.axis_id === d.axis.id);
  const create = useMutation({ mutationFn: () => api.draftSitrep(d.axis.id), onSuccess: done });
  const send = useMutation({ mutationFn: (sid: string) => api.sendSitrep(sid, text.trim()), onSuccess: () => (setText(""), done()) });
  return (
    <div>
      {d.axis.can_manage &&
        (draft ? (
          <form
            className="ops-form"
            onSubmit={(e) => {
              e.preventDefault();
              send.mutate(draft.id);
            }}
          >
            <p>
              {t("crisis.sitrep.number", { n: draft.number })} · {t("crisis.sitrep.draft")} ·{" "}
              {t("crisis.sitrep.figures", {
                incidents: draft.figures.incidents ?? 0,
                deceased: draft.figures.deceased ?? 0,
                evacuated: draft.figures.evacuated ?? 0,
                sheltered: draft.figures.sheltered ?? 0,
              })}
            </p>
            <label htmlFor={`${id}-a`}>{t("crisis.sitrep.assessment")}</label>
            <textarea id={`${id}-a`} rows={2} value={text} onChange={(e) => setText(e.target.value)} />
            <button type="submit" className="btn btn--primary btn--small" disabled={text.trim().length < 5 || send.isPending}>
              {t("crisis.sitrep.send")}
            </button>
          </form>
        ) : (
          <button type="button" className="btn btn--small" onClick={() => create.mutate()}>
            {t("crisis.sitrep.prepare")}
          </button>
        ))}
      <ul className="sitrep-list">
        {d.sitreps
          .filter((s) => s.status === "sent")
          .map((s) => (
            <li key={s.id}>
              <p className="sitrep-list__head">
                {t("crisis.sitrep.number", { n: s.number })} · {s.sent_at ? fmt.dateTime(s.sent_at) : ""}
                {s.sent_by_name ? ` · ${s.sent_by_name}` : ""}
              </p>
              <p>{s.assessment}</p>
            </li>
          ))}
      </ul>
    </div>
  );
}

export function AxisPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api, mapStyleUrl } = useServices();
  const { nameOf } = useGouvernorats();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => (params.get("tab") === "resources" ? "resources" : "decisions"));
  const detail = useQuery({ queryKey: crisisKeys.axis(id), queryFn: ({ signal }) => api.crisisAxis(id, signal), refetchInterval: 30_000 });
  const boundaries = useQuery({ queryKey: crisisKeys.boundaries, queryFn: ({ signal }) => api.crisisBoundaries(signal), staleTime: Infinity });
  const d = detail.data;
  const family = useMemo(() => (d ? [d.axis, ...d.axis.children] : []), [d]);
  if (detail.isLoading) return <Loading />;
  if (detail.isError || !d) return <ErrorBox error={detail.error} onRetry={() => void detail.refetch()} />;
  const a = d.axis;
  const f = a.figures;
  const bounds = areaBounds([...family.map((x) => x.area), ...d.evacuations.map((e) => e.area)]) ?? initialBoundsFor(a.gouvernorat_code);
  const due = hoursUntil(a.next_sitrep_at);
  const kinds = Object.entries(f.resources_by_kind).map(([k, v]) => ({ label: t(`resources.kind.${k}`, { defaultValue: k }), value: v }));
  const levels = Object.fromEntries(family.filter((x) => x.gouvernorat_code).map((x) => [x.gouvernorat_code as number, x.level]));
  return (
    <div className="ops-room">
      <h1 className="visually-hidden">
        {a.number} · {displayName(a)}
      </h1>
      <div className="ops-room__map">
        <Suspense fallback={<Loading />}>
          <CommandMap
            ariaLabel={t("crisis.map.axisAria", { name: displayName(a) })}
            bounds={bounds}
            styleUrl={mapStyleUrl}
            framed
            boundaries={boundaries.data}
            levels={levels}
            focus={a.gouvernorats}
            labels={Object.fromEntries(a.gouvernorats.map((c) => [c, nameOf(c) ?? String(c)]))}
            axisAreas={family.map((x) => ({ id: x.id, area: x.area, level: x.level }))}
            incidents={d.incidents}
            shelters={d.shelters}
            evacuations={d.evacuations}
            decisionAreas={d.directives.filter((x) => !x.overridden_by).map((x) => ({ id: x.id, area: x.area }))}
            tilted={false}
          />
        </Suspense>
      </div>

      <header className="ops-topbar">
        <div className="ops-topbar__title">
          <span className="ops-topbar__eyebrow">
            <Link to="/axes">{t("crisis.axes.title")}</Link> · {a.number}
          </span>
          <p className="ops-topbar__name" aria-hidden="true">
            {displayName(a)}
          </p>
        </div>
        <LevelPill level={a.level} />
        {isSimulated(a) && <SimBadge />}
        <span className="ops-topbar__meta">
          {t(`crisis.kind.${a.kind}`)} · {a.scope === "national" ? t("crisis.axis.national") : a.gouvernorat_name}
        </span>
        {a.status === "open" && due !== null && (
          <span className={`ops-topbar__due${due < 0 ? " is-late" : ""}`}>
            {due < 0 ? t("crisis.sitrep.late") : t("crisis.sitrep.dueIn", { h: Math.max(0, Math.round(due * 10) / 10) })}
          </span>
        )}
        {a.status === "closed" && <span className="pill tone-slate">{t("crisis.axis.closed")}</span>}
        <Clock />
      </header>

      <div className="ops-side ops-side--start">
        <Panel title={t("crisis.axis.situation")}>
          <FigureTiles f={f} />
          <PlanBlock axis={a} />
          {a.can_command && <Commander axis={a} />}
        </Panel>
        {a.status === "open" && a.gouvernorat_code !== null && <Suggestions axis={a} />}
        <Panel title={t("crisis.axis.attached", { n: d.incidents.length })}>
          {d.incidents.length === 0 ? (
            <p className="ops-empty">{t("crisis.axis.noIncident")}</p>
          ) : (
            <ul className="incident-list">
              {d.incidents.map((i) => (
                <li key={i.id}>
                  <span className={`sev sev--${(i.severity ?? 0) >= 4 ? "high" : "mid"}`} aria-hidden="true" />
                  <span className="incident-list__what">
                    <Link to={`/incidents/${i.id}`}>{t(`category.${i.category}`)}</Link>
                    {i.title ? ` · ${i.title}` : ""}
                  </span>
                  <span className="muted">
                    {t("crisis.axis.incidentFigs", { d: i.deceased, i: i.injured, r: i.resources })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="ops-side ops-side--end">
        <Panel title={t("crisis.command.resources")}>
          {kinds.length ? <Bars items={kinds} /> : <p className="ops-empty">{t("crisis.command.noResources")}</p>}
        </Panel>
        <Panel title={t("crisis.axis.shelters", { n: d.shelters.length })}>
          <ul className="shelter-list">
            {d.shelters.map((s) => (
              <li key={s.id}>
                <span>{s.name}</span>
                <span className="meter" aria-hidden="true">
                  <span style={{ inlineSize: `${s.capacity ? Math.min(100, (s.occupants / s.capacity) * 100) : 0}%` }} />
                </span>
                <span className="shelter-list__n">
                  <bdi dir="ltr">
                    {fmt.number(s.occupants)} / {fmt.number(s.capacity)}
                  </bdi>
                </span>
              </li>
            ))}
          </ul>
          {a.can_manage && <QuickAdd axis={a} kind="shelter" />}
        </Panel>
        <Panel title={t("crisis.axis.evacuations", { n: f.evacuated })}>
          <ul className="shelter-list">
            {d.evacuations.map((e) => (
              <li key={e.id}>
                <span>{e.name}</span>
                <span className="shelter-list__n">{fmt.number(e.evacuated)}</span>
              </li>
            ))}
          </ul>
          {a.can_manage && <QuickAdd axis={a} kind="evacuation" />}
        </Panel>
        <Panel title={t("crisis.command.needs", { n: d.needs.filter((n) => n.status === "raised").length })}>
          <ul className="need-list">
            {d.needs.map((n) => (
              <li key={n.id} className={n.status === "met" ? "is-met" : undefined}>
                <span className="need-list__q">{n.quantity}</span>
                <span>{n.label}</span>
                <span className={`pill tone-${n.status === "met" ? "green" : "amber"}`}>{t(`crisis.need.${n.status}`)}</span>
                {a.can_manage && n.status === "raised" && <NeedMet axisId={a.id} needId={n.id} />}
              </li>
            ))}
          </ul>
          {a.can_manage && <QuickAdd axis={a} kind="need" />}
        </Panel>
      </div>

      <section className="ops-bottom" aria-label={t("crisis.command.follow")}>
        <div role="tablist" className="ops-tabs" aria-label={t("crisis.command.follow")}>
          {(["decisions", "documents", "sitreps", "timeline", "resources"] as const).map((k) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} className="ops-tab" onClick={() => setTab(k)}>
              {t(`crisis.command.tab.${k}`)}
            </button>
          ))}
        </div>
        <div role="tabpanel" className="ops-bottom__body" tabIndex={0}>
          {tab === "decisions" &&
            (d.directives.length === 0 ? (
              <p className="ops-empty">{t("crisis.directive.none")}</p>
            ) : (
              <ul className="directive-list">
                {d.directives.map((x) => (
                  <DirectiveItem key={x.id} d={x} />
                ))}
              </ul>
            ))}
          {tab === "documents" &&
            ((d.documents ?? []).length === 0 ? (
              <p className="ops-empty">{t("register.axis.noDocuments")}</p>
            ) : (
              <DocumentRefs items={d.documents ?? []} />
            ))}
          {tab === "sitreps" && <Sitreps d={d} />}
          {tab === "resources" && <AreaResources axis={a} />}
          {tab === "timeline" && (
            <ol className="timeline">
              {d.timeline.map((e, n) => (
                <li key={`${e.at}-${n}`}>
                  <time dateTime={e.at}>{fmt.time(e.at)}</time>
                  <span>{t(`crisis.event.${e.kind}`, { defaultValue: e.kind })}</span>
                  {e.actor_name && <span className="muted">{e.actor_name}</span>}
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>
    </div>
  );
}

/** RS1: the resources inside the axis area (its sub-axes included), counts by unit, never a name. */
function AreaResources({ axis }: { axis: Axis }) {
  const { api } = useServices();
  const catalogue = useQuery({ queryKey: inventoryKeys.catalogue, queryFn: ({ signal }) => api.inventoryCatalogue(signal), staleTime: 300_000 });
  if (catalogue.isPending) return <Loading />;
  if (catalogue.isError) return <ErrorBox error={catalogue.error} onRetry={() => void catalogue.refetch()} />;
  return <SearchTab catalogue={catalogue.data.items} national={false} axis={{ id: axis.id, number: axis.number }} />;
}

function NeedMet({ axisId, needId }: { axisId: string; needId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const met = useMutation({ mutationFn: () => api.needMet(axisId, needId), onSuccess: done });
  return (
    <button type="button" className="btn btn--small btn--ghost" onClick={() => met.mutate()} disabled={met.isPending}>
      {t("crisis.need.markMet")}
    </button>
  );
}
