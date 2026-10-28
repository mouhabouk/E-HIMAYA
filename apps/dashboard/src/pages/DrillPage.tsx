// covers: phase L5a (docs/phase-l/design-l5.md §2.1): one digital dry run through its steps: the plan and the
// scenario (injects written or generated), the approval of each gouvernorat, the run (the rooms answer the due injects
// and book their real resources inside the dry run only), the stop that is never hidden, the evaluation by an
// independent evaluator and the report.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { SimBadge } from "../components/crisis/CrisisBits";
import { DecisionPill, DRILL_HAZARDS, DrillStatusPill, Needs } from "../components/DrillBits";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { ReasonField } from "../components/Phase9Bits";
import { Stepper } from "../components/Stepper";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import {
  drillKeys,
  INJECT_KINDS,
  PLAN_FOLLOWED,
  RESOURCE_KINDS,
  RESPONSE_ACTIONS,
  STARTED,
  type Drill,
  type FeedItem,
  type FreeResource,
  type Inject,
  type InjectKind,
  type PlanFollowed,
  type ResourceKind,
  type ResponseAction,
} from "../lib/drill";
import { useCan } from "../lib/features";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { reasonValid } from "../lib/phase9";
import { simText } from "../lib/crisisText";

type Tab = "scenario" | "run" | "evaluation" | "report";

function useDrillMutation<A>(id: string, fn: (a: A) => Promise<unknown>, onDone?: () => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: drillKeys.all });
      onDone?.();
    },
    meta: { id },
  });
}

function Alert({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p role="alert" className="alert alert--error">
      {t(errorMessageKey(error))}
    </p>
  );
}

/** Text that may carry the [SIM] tag: shown without it, with the amber badge. */
function Sim({ text }: { text: string }) {
  const s = simText(text);
  return (
    <>
      {s.sim && <SimBadge />} <span dir="auto">{s.text}</span>
    </>
  );
}

// ---------------------------------------------------------------- steps 2 and 3: approvals and the planner's buttons

function Participants({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  // Refusing or withdrawing asks for its reason first; approving does not.
  const [asking, setAsking] = useState<"refused" | "withdrawn" | null>(null);
  const decide = useDrillMutation(
    drill.id,
    (d: "approved" | "refused" | "withdrawn") => api.decideDrill(drill.id, d, d === "approved" ? undefined : reason.trim()),
    () => {
      setAsking(null);
      setReason("");
      setTried(false);
    },
  );
  const mine = drill.participants.find((p) => p.gouvernorat_code === drill.my_approval);
  return (
    <section className="card drill-participants" aria-labelledby="drill-participants">
      <h2 id="drill-participants">{t("drill.approval.title")}</h2>
      <p className="muted">{t("drill.approval.intro")}</p>
      <ul className="drill-participants__list">
        {drill.participants.map((p) => (
          <li key={p.gouvernorat_code}>
            <strong>{geo.nameOf(p.gouvernorat_code)}</strong> <DecisionPill decision={p.decision} />
            {p.decided_at && (
              <span className="muted">
                {" "}
                {p.decided_by_name ?? "—"} · {fmt.dateTime(p.decided_at)}
              </span>
            )}
            {p.reason && (
              <div className="muted" dir="auto">
                {p.reason}
              </div>
            )}
          </li>
        ))}
      </ul>
      {mine && drill.my_approval !== null && (
        <div className="drill-participants__mine">
          <h3>{t("drill.approval.mine", { name: geo.nameOf(drill.my_approval) })}</h3>
          {asking === null ? (
            <div className="actions">
              {drill.status === "submitted" && mine.decision !== "approved" && (
                <button type="button" className="btn btn--primary" disabled={decide.isPending} onClick={() => decide.mutate("approved")}>
                  {t("drill.approval.approve")}
                </button>
              )}
              {drill.status !== "running" && mine.decision !== "refused" && (
                <button type="button" className="btn" onClick={() => setAsking("refused")}>
                  {t("drill.approval.refuse")}
                </button>
              )}
              {mine.decision !== "withdrawn" && (
                <button type="button" className="btn btn--danger" onClick={() => setAsking("withdrawn")}>
                  {t("drill.approval.withdraw")}
                </button>
              )}
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setTried(true);
                if (reasonValid(reason)) decide.mutate(asking);
              }}
            >
              <ReasonField
                label={t(asking === "refused" ? "drill.approval.refuseReason" : "drill.approval.withdrawReason")}
                value={reason}
                onChange={setReason}
                showError={tried}
              />
              <div className="actions">
                <button type="submit" className={`btn ${asking === "withdrawn" ? "btn--danger" : "btn--primary"}`} disabled={decide.isPending}>
                  {t(asking === "refused" ? "drill.approval.refuse" : "drill.approval.withdraw")}
                </button>
                <button type="button" className="btn" onClick={() => setAsking(null)}>
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          )}
          <Alert error={decide.error} />
        </div>
      )}
    </section>
  );
}

function PlannerActions({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const submit = useDrillMutation(drill.id, () => api.submitDrill(drill.id));
  const start = useDrillMutation(drill.id, () => api.startDrill(drill.id));
  if (!drill.can_submit && !drill.can_start) return null;
  return (
    <div className="actions">
      {drill.can_submit && (
        <button type="button" className="btn btn--primary" disabled={submit.isPending} onClick={() => submit.mutate(undefined)}>
          {t("drill.actions.submit")}
        </button>
      )}
      {drill.can_start && (
        <button type="button" className="btn btn--primary" disabled={start.isPending} onClick={() => start.mutate(undefined)}>
          {t("drill.actions.start")}
        </button>
      )}
      <Alert error={submit.error ?? start.error} />
    </div>
  );
}

/** The stop of a running dry run: never hidden by the administrator (a safety button), with its reason. */
function StopBar({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const stop = useDrillMutation(drill.id, () => api.stopDrill(drill.id, reason.trim()), () => setOpen(false));
  if (!drill.can_stop) return null;
  return (
    <div className="drill-stop" role="region" aria-label={t("drill.stop.label")}>
      {!open ? (
        <button type="button" className="btn btn--danger" onClick={() => setOpen(true)}>
          {t("drill.stop.open")}
        </button>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setTried(true);
            if (reasonValid(reason)) stop.mutate(undefined);
          }}
        >
          <ReasonField label={t("drill.stop.reason")} value={reason} onChange={setReason} showError={tried} />
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={stop.isPending}>
              {t("drill.stop.confirm")}
            </button>
            <button type="button" className="btn" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </button>
          </div>
          <Alert error={stop.error} />
        </form>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- step 1: the scenario

function InjectForm({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const geo = useGouvernorats();
  const id = useId();
  const blank = { offset_min: 0, gouvernorat_code: null as number | null, kind: "report" as InjectKind, title: "", body: "", expected: "" };
  const [f, setF] = useState(blank);
  const [needs, setNeeds] = useState<Partial<Record<ResourceKind, number>>>({});
  const [tried, setTried] = useState(false);
  const add = useDrillMutation(drill.id, () => api.addInject(drill.id, { ...f, title: f.title.trim(), needs }), () => {
    setF(blank);
    setNeeds({});
    setTried(false);
  });
  const titleOk = f.title.trim().length >= 3;
  const offsetOk = f.offset_min >= 0 && f.offset_min < drill.duration_min;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (titleOk && offsetOk) add.mutate(undefined);
  };
  return (
    <form className="card drill-inject-form" aria-labelledby={`${id}-t`} onSubmit={submit} noValidate>
      <h3 id={`${id}-t`}>{t("drill.inject.new")}</h3>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-offset`}>{t("drill.inject.offset")}</label>
          <Stepper
            id={`${id}-offset`}
            min={0}
            max={drill.duration_min - 1}
            step={5}
            value={f.offset_min}
            label={t("drill.inject.offset")}
            required
            invalid={tried && !offsetOk}
            onChange={(n) => setF({ ...f, offset_min: n })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-kind`}>{t("drill.inject.kind")}</label>
          <select id={`${id}-kind`} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as InjectKind })}>
            {INJECT_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`drill.injectKind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-g`}>{t("drill.inject.gouvernorat")}</label>
          <select
            id={`${id}-g`}
            value={f.gouvernorat_code ?? ""}
            onChange={(e) => setF({ ...f, gouvernorat_code: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">{t("drill.inject.all")}</option>
            {drill.gouvernorats.map((c) => (
              <option key={c} value={c}>
                {geo.nameOf(c)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-title`}>{t("drill.inject.title")}</label>
          <input
            id={`${id}-title`}
            value={f.title}
            maxLength={200}
            aria-required="true"
            aria-invalid={(tried && !titleOk) || undefined}
            onChange={(e) => setF({ ...f, title: e.target.value })}
          />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-body`}>{t("drill.inject.body")}</label>
        <textarea id={`${id}-body`} rows={2} maxLength={2000} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
      </div>
      <fieldset className="drill-needs">
        <legend>{t("drill.inject.needs")}</legend>
        <div className="drill-needs__grid">
          {RESOURCE_KINDS.map((k) => (
            <div key={k} className="drill-needs__item">
              <span id={`${id}-need-${k}`}>{t(`resources.kind.${k}`)}</span>
              <Stepper
                min={0}
                max={50}
                value={needs[k] ?? 0}
                labelledBy={`${id}-need-${k}`}
                label={t(`resources.kind.${k}`)}
                onChange={(n) => {
                  setNeeds((cur) => {
                    const rest: Partial<Record<ResourceKind, number>> = {};
                    for (const kind of RESOURCE_KINDS) if (kind !== k && cur[kind]) rest[kind] = cur[kind];
                    return n > 0 ? { ...rest, [k]: n } : rest;
                  });
                }}
              />
            </div>
          ))}
        </div>
      </fieldset>
      <div className="field">
        <label htmlFor={`${id}-expected`}>{t("drill.inject.expected")}</label>
        <textarea
          id={`${id}-expected`}
          rows={2}
          maxLength={2000}
          value={f.expected}
          onChange={(e) => setF({ ...f, expected: e.target.value })}
        />
      </div>
      <Alert error={add.error} />
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={add.isPending}>
          {t("drill.inject.add")}
        </button>
      </div>
    </form>
  );
}

function Generator({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [count, setCount] = useState(30);
  const [kinds, setKinds] = useState<string[]>(drill.hazard_key && (DRILL_HAZARDS as readonly string[]).includes(drill.hazard_key) ? [drill.hazard_key] : ["fire", "traffic_accident"]);
  const [seed, setSeed] = useState(1);
  const gen = useDrillMutation(drill.id, () => api.generateInjects(drill.id, { count, kinds, seed }));
  const ok = count >= 1 && count <= 300 && kinds.length > 0;
  return (
    <section className="card drill-generator" aria-labelledby={`${id}-t`}>
      <h3 id={`${id}-t`}>
        {t("drill.generate.title")} <SimBadge />
      </h3>
      <p className="muted">{t("drill.generate.intro")}</p>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-count`}>{t("drill.generate.count")}</label>
          <Stepper id={`${id}-count`} min={1} max={300} step={10} value={count} label={t("drill.generate.count")} onChange={setCount} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-seed`}>{t("drill.generate.seed")}</label>
          <Stepper id={`${id}-seed`} min={0} max={2 ** 31 - 1} value={seed} label={t("drill.generate.seed")} onChange={setSeed} />
        </div>
      </div>
      <fieldset>
        <legend>{t("drill.generate.kinds")}</legend>
        <div className="drill-form__grid">
          {DRILL_HAZARDS.map((h) => (
            <label key={h} className="checkbox">
              <input
                type="checkbox"
                checked={kinds.includes(h)}
                onChange={() => setKinds((cur) => (cur.includes(h) ? cur.filter((x) => x !== h) : [...cur, h]))}
              />
              {t(`drill.hazard.${h}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <Alert error={gen.error} />
      <div className="actions">
        <button type="button" className="btn" disabled={!ok || gen.isPending} onClick={() => gen.mutate(undefined)}>
          {t("drill.generate.run")}
        </button>
      </div>
      {gen.isSuccess && (
        <p role="status" className="alert alert--ok">
          {t("drill.generate.done", { count })}
        </p>
      )}
    </section>
  );
}

function InjectTable({ injects, drill, onDelete }: { injects: Inject[]; drill: Drill; onDelete?: (i: Inject) => void }) {
  const { t } = useTranslation();
  const geo = useGouvernorats();
  return (
    <div className="table-wrap">
      <table className="table drill-injects">
        <caption>{t("drill.inject.caption", { count: injects.length })}</caption>
        <thead>
          <tr>
            <th scope="col">{t("drill.inject.offset")}</th>
            <th scope="col">{t("drill.inject.kind")}</th>
            <th scope="col">{t("drill.inject.title")}</th>
            <th scope="col">{t("drill.inject.gouvernorat")}</th>
            <th scope="col">{t("drill.inject.needs")}</th>
            {onDelete && <th scope="col">{t("drill.inject.actions")}</th>}
          </tr>
        </thead>
        <tbody>
          {injects.length === 0 && (
            <tr>
              <td colSpan={onDelete ? 6 : 5} className="muted">
                {t("drill.inject.empty")}
              </td>
            </tr>
          )}
          {injects.map((i) => (
            <tr key={i.id}>
              <td>+{t("drill.minutes", { count: i.offset_min })}</td>
              <td>
                {t(`drill.injectKind.${i.kind}`)}
                {i.generated && <div className="muted">{t("drill.inject.generated")}</div>}
              </td>
              <th scope="row">
                <Sim text={i.title} />
                {i.expected && (
                  <div className="muted" dir="auto">
                    {t("drill.inject.expectedShort")}: {i.expected}
                  </div>
                )}
              </th>
              <td>{i.gouvernorat_code === null ? t("drill.inject.all") : geo.nameOf(i.gouvernorat_code)}</td>
              <td>
                <Needs needs={i.needs} />
              </td>
              {onDelete && (
                <td>
                  <button type="button" className="btn btn--small" onClick={() => onDelete(i)} disabled={!drill.can_edit}>
                    {t("drill.inject.delete")}
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScenarioTab({ drill, injects }: { drill: Drill; injects: Inject[] }) {
  const { api } = useServices();
  const remove = useDrillMutation(drill.id, (i: Inject) => api.deleteInject(drill.id, i.id));
  return (
    <div className="drill-scenario">
      {drill.can_edit && (
        <div className="drill-scenario__editors">
          <InjectForm drill={drill} />
          <Generator drill={drill} />
        </div>
      )}
      <Alert error={remove.error} />
      <InjectTable injects={injects} drill={drill} onDelete={drill.can_edit ? (i) => remove.mutate(i) : undefined} />
    </div>
  );
}

// ---------------------------------------------------------------- step 4: the run

function Answer({ drill, item, free }: { drill: Drill; item: FeedItem; free: FreeResource[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [action, setAction] = useState<ResponseAction>("dispatched");
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const respond = useDrillMutation(
    drill.id,
    () => api.respondInject(drill.id, item.inject.id, { action, text: text.trim(), resource_ids: action === "dispatched" ? picked : [] }),
    () => {
      setText("");
      setPicked([]);
    },
  );
  const wanted = new Set(Object.keys(item.inject.needs));
  const choices = free.filter((r) => wanted.size === 0 || wanted.has(r.kind)).slice(0, 40);
  return (
    <form
      className="drill-answer"
      aria-labelledby={`${id}-t`}
      onSubmit={(e) => {
        e.preventDefault();
        respond.mutate(undefined);
      }}
    >
      <h4 id={`${id}-t`}>{t("drill.run.answer")}</h4>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-a`}>{t("drill.run.action")}</label>
          <select id={`${id}-a`} value={action} onChange={(e) => setAction(e.target.value as ResponseAction)}>
            {RESPONSE_ACTIONS.map((a) => (
              <option key={a} value={a}>
                {t(`drill.action.${a}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-x`}>{t("drill.run.text")}</label>
          <input id={`${id}-x`} value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
        </div>
      </div>
      {action === "dispatched" && (
        <fieldset>
          <legend>{t("drill.run.book")}</legend>
          {choices.length === 0 ? (
            <p className="muted">{t("drill.run.noneFree")}</p>
          ) : (
            <div className="drill-form__grid">
              {choices.map((r) => (
                <label key={r.id} className="checkbox">
                  <input
                    type="checkbox"
                    checked={picked.includes(r.id)}
                    disabled={!picked.includes(r.id) && picked.length >= 20}
                    onChange={() => setPicked((cur) => (cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id]))}
                  />
                  <span dir="auto">
                    {t(`resources.kind.${r.kind}`, { defaultValue: r.kind })} · {simText(r.label).text} ({simText(r.unit).text})
                  </span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
      )}
      <Alert error={respond.error} />
      <button type="submit" className="btn btn--primary drill-answer__send" disabled={respond.isPending}>
        {t("drill.run.send")}
      </button>
    </form>
  );
}

function RunTab({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const canRespond = useCan("drill.respond", false);
  const feed = useQuery({
    queryKey: drillKeys.feed(drill.id),
    queryFn: ({ signal }) => api.drillFeed(drill.id, signal),
    refetchInterval: drill.status === "running" ? 15_000 : false,
  });
  const release = useDrillMutation(drill.id, (rid: string) => api.releaseResponse(drill.id, rid));
  if (feed.isLoading) return <Loading />;
  if (feed.isError) return <ErrorBox error={feed.error} onRetry={() => void feed.refetch()} />;
  const f = feed.data;
  if (!f) return null;
  const mine = drill.participants.some((p) => p.gouvernorat_code === drill.my_approval && p.decision === "approved");
  return (
    <div className="drill-run">
      <div className="drill-run__clock" role="status">
        <span className="pill tone-red">{t("drill.run.elapsed", { count: f.elapsed_min })}</span>{" "}
        {f.status === "running" && <span className="pill tone-slate">{t("drill.run.remaining", { count: f.remaining_min })}</span>}
      </div>
      {Object.keys(f.free).length > 0 && (
        <p className="muted">
          {t("drill.run.free")}: <Needs needs={f.free} />
        </p>
      )}
      {f.items.length === 0 && <p className="muted">{t("drill.run.nothingYet")}</p>}
      <ol className="drill-feed">
        {f.items.map((item) => (
          <li key={item.inject.id} className="card drill-feed__item">
            <header className="drill-feed__head">
              <span className="pill tone-navy">+{t("drill.minutes", { count: item.inject.offset_min })}</span>{" "}
              <span className="pill tone-slate">{t(`drill.injectKind.${item.inject.kind}`)}</span>{" "}
              <strong>
                <Sim text={item.inject.title} />
              </strong>
              <span className="muted">
                {" "}
                · {item.inject.gouvernorat_code === null ? t("drill.inject.all") : geo.nameOf(item.inject.gouvernorat_code)} ·{" "}
                {fmt.time(item.due_at)}
              </span>
            </header>
            {item.inject.body && (
              <p dir="auto">
                <Sim text={item.inject.body} />
              </p>
            )}
            {Object.keys(item.inject.needs).length > 0 && (
              <p className="muted">
                {t("drill.inject.needs")}: <Needs needs={item.inject.needs} />
              </p>
            )}
            {item.responses.length > 0 && (
              <ul className="drill-feed__answers">
                {item.responses.map((r) => (
                  <li key={r.id}>
                    <span className="pill tone-green">{t(`drill.action.${r.action}`)}</span>{" "}
                    <span className="muted">
                      {geo.nameOf(r.gouvernorat_code)} · {r.responded_by_name ?? "—"} · {fmt.time(r.responded_at)}
                    </span>
                    {r.text && (
                      <div dir="auto">
                        <Sim text={r.text} />
                      </div>
                    )}
                    {r.bookings.length > 0 && (
                      <div className="muted">
                        {t("drill.run.booked")}:{" "}
                        {r.bookings
                          .map((b) => `${simText(b.label).text}${b.released ? ` (${t("drill.run.released")})` : ""}`)
                          .join(t("common.listSeparator"))}
                        {f.status === "running" &&
                          r.gouvernorat_code === drill.my_approval &&
                          r.bookings.some((b) => !b.released) && (
                            <>
                              {" "}
                              <button type="button" className="btn btn--small" disabled={release.isPending} onClick={() => release.mutate(r.id)}>
                                {t("drill.run.release")}
                              </button>
                            </>
                          )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {f.status === "running" && mine && canRespond && <Answer drill={drill} item={item} free={f.free_resources} />}
          </li>
        ))}
      </ol>
      <Alert error={release.error} />
    </div>
  );
}

// ---------------------------------------------------------------- step 5: evaluation and report

function EvaluateRow({ drill, inject }: { drill: Drill; inject: Inject }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [plan, setPlan] = useState<PlanFollowed>("yes");
  const [score, setScore] = useState(3);
  const [notes, setNotes] = useState("");
  const save = useDrillMutation(drill.id, () => api.evaluateInject(drill.id, inject.id, { plan_followed: plan, score, notes: notes.trim() }));
  return (
    <tr>
      <th scope="row">
        +{t("drill.minutes", { count: inject.offset_min })} · <Sim text={inject.title} />
      </th>
      <td>
        <label className="visually-hidden" htmlFor={`${id}-p`}>
          {t("drill.eval.plan")}
        </label>
        <select id={`${id}-p`} value={plan} onChange={(e) => setPlan(e.target.value as PlanFollowed)}>
          {PLAN_FOLLOWED.map((p) => (
            <option key={p} value={p}>
              {t(`drill.planFollowed.${p}`)}
            </option>
          ))}
        </select>
      </td>
      <td>
        <label className="visually-hidden" htmlFor={`${id}-s`}>
          {t("drill.eval.score")}
        </label>
        <Stepper id={`${id}-s`} min={0} max={5} value={score} label={t("drill.eval.score")} onChange={setScore} />
      </td>
      <td>
        <label className="visually-hidden" htmlFor={`${id}-n`}>
          {t("drill.eval.notes")}
        </label>
        <input id={`${id}-n`} value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} />
      </td>
      <td>
        <button type="button" className="btn btn--small" disabled={save.isPending} onClick={() => save.mutate(undefined)}>
          {save.isSuccess ? t("drill.eval.saved") : t("drill.eval.save")}
        </button>
        {save.isError && (
          <span role="alert" className="field__error">
            {t(errorMessageKey(save.error))}
          </span>
        )}
      </td>
    </tr>
  );
}

function EvaluationTab({ drill, injects }: { drill: Drill; injects: Inject[] }) {
  const { t } = useTranslation();
  return (
    <section className="card" aria-labelledby="drill-eval">
      <h2 id="drill-eval">{t("drill.eval.title")}</h2>
      <p className="muted">{t("drill.eval.intro")}</p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("drill.inject.title")}</th>
              <th scope="col">{t("drill.eval.plan")}</th>
              <th scope="col">{t("drill.eval.score")}</th>
              <th scope="col">{t("drill.eval.notes")}</th>
              <th scope="col">{t("drill.inject.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {injects.map((i) => (
              <EvaluateRow key={i.id} drill={drill} inject={i} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReportTab({ drill }: { drill: Drill }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const [conclusion, setConclusion] = useState("");
  const report = useQuery({ queryKey: drillKeys.report(drill.id), queryFn: ({ signal }) => api.drillReport(drill.id, signal) });
  const close = useDrillMutation(drill.id, () => api.closeDrill(drill.id, conclusion.trim()));
  if (report.isLoading) return <Loading />;
  if (report.isError) return <ErrorBox error={report.error} onRetry={() => void report.refetch()} />;
  const r = report.data;
  if (!r) return null;
  const total = r.answered + r.unanswered;
  return (
    <div className="drill-report">
      <ul className="kpi-row drill-report__kpis">
        <li className="kpi-tile tone-green">
          <div>
          <p className="kpi-tile__value">
            <bdi dir="ltr">
              {fmt.number(r.answered)}/{fmt.number(total)}
            </bdi>
          </p>
          <p className="kpi-tile__label">{t("drill.report.answered")}</p>
          </div>
        </li>
        <li className="kpi-tile tone-navy">
          <div>
          <p className="kpi-tile__value">
            <bdi dir="ltr">{r.median_answer_min === null ? "—" : fmt.decimal(r.median_answer_min)}</bdi>
          </p>
          <p className="kpi-tile__label">{t("drill.report.median")}</p>
          </div>
        </li>
        <li className="kpi-tile tone-amber">
          <div>
          <p className="kpi-tile__value">
            <bdi dir="ltr">{r.mean_score === null ? "—" : fmt.decimal(r.mean_score)}</bdi>
          </p>
          <p className="kpi-tile__label">{t("drill.report.score")}</p>
          </div>
        </li>
        <li className="kpi-tile tone-red">
          <div>
          <p className="kpi-tile__value">
            <bdi dir="ltr">{fmt.number(r.resources.reduce((n, l) => n + l.short, 0))}</bdi>
          </p>
          <p className="kpi-tile__label">{t("drill.report.short")}</p>
          </div>
        </li>
      </ul>
      <div className="table-wrap">
        <table className="table">
          <caption>{t("drill.report.resources")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("drill.inject.gouvernorat")}</th>
              <th scope="col">{t("drill.report.kind")}</th>
              <th scope="col">{t("drill.report.atStart")}</th>
              <th scope="col">{t("drill.report.peak")}</th>
              <th scope="col">{t("drill.report.shortCol")}</th>
            </tr>
          </thead>
          <tbody>
            {r.resources.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  {t("drill.report.noResources")}
                </td>
              </tr>
            )}
            {r.resources.map((l) => (
              <tr key={`${l.gouvernorat_code}-${l.kind}`}>
                <th scope="row">{geo.nameOf(l.gouvernorat_code)}</th>
                <td>{t(`resources.kind.${l.kind}`, { defaultValue: l.kind })}</td>
                <td>{fmt.number(l.available_at_start)}</td>
                <td>{fmt.number(l.peak_booked)}</td>
                <td>{l.short > 0 ? <span className="pill tone-red">{fmt.number(l.short)}</span> : "0"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-wrap">
        <table className="table">
          <caption>{t("drill.report.injects")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("drill.inject.title")}</th>
              <th scope="col">{t("drill.report.firstAnswer")}</th>
              <th scope="col">{t("drill.report.booked")}</th>
              <th scope="col">{t("drill.report.shortfall")}</th>
              <th scope="col">{t("drill.eval.plan")}</th>
            </tr>
          </thead>
          <tbody>
            {r.injects.map((i) => (
              <tr key={i.inject.id}>
                <th scope="row">
                  +{t("drill.minutes", { count: i.inject.offset_min })} · <Sim text={i.inject.title} />
                </th>
                <td>
                  {i.first_answer_min === null ? (
                    <span className="pill tone-amber">{t("drill.report.unanswered")}</span>
                  ) : (
                    t("drill.minutes", { count: Math.round(i.first_answer_min) })
                  )}
                </td>
                <td>
                  <Needs needs={i.booked} />
                </td>
                <td>
                  <Needs needs={i.shortfall} />
                </td>
                <td>{i.evaluation ? `${t(`drill.planFollowed.${i.evaluation.plan_followed}`)} · ${i.evaluation.score}/5` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="card" aria-labelledby="drill-stress">
        <h2 id="drill-stress">{t("drill.report.stress")}</h2>
        <p className="muted">{t("drill.report.stressIntro")}</p>
        {r.stress.length === 0 ? (
          <p className="muted">{t("drill.report.noStress")}</p>
        ) : (
          <ul>
            {r.stress.map((s, n) => (
              <li key={n}>
                {t("drill.report.stressLine", {
                  sent: fmt.number(s.reports_sent),
                  accepted: fmt.number(s.reports_accepted),
                  peak: fmt.decimal(s.peak_per_second),
                  p95: fmt.number(Math.round(s.latency_p95_ms)),
                  errors: fmt.number(s.errors_5xx),
                })}
                {s.attacks_sent > 0 && (
                  <div>
                    {t("drill.report.attacks", { sent: fmt.number(s.attacks_sent), blocked: fmt.number(s.attacks_blocked) })}{" "}
                    <span className={`pill ${s.attacks_blocked === s.attacks_sent ? "tone-green" : "tone-red"}`}>
                      {s.attacks_blocked === s.attacks_sent ? t("drill.report.allBlocked") : t("drill.report.notAllBlocked")}
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      {drill.conclusion && (
        <section className="card">
          <h2>{t("drill.report.conclusion")}</h2>
          <p dir="auto">{drill.conclusion}</p>
        </section>
      )}
      {drill.can_close && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            if (conclusion.trim().length >= 3) close.mutate(undefined);
          }}
        >
          <div className="field">
            <label htmlFor="drill-conclusion">{t("drill.report.conclusion")}</label>
            <textarea
              id="drill-conclusion"
              rows={3}
              maxLength={4000}
              value={conclusion}
              aria-required="true"
              onChange={(e) => setConclusion(e.target.value)}
            />
          </div>
          <Alert error={close.error} />
          <button type="submit" className="btn btn--primary" disabled={close.isPending}>
            {t("drill.actions.close")}
          </button>
        </form>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- the page

export function DrillPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const { id = "" } = useParams();
  const drill = useQuery({ queryKey: drillKeys.one(id), queryFn: ({ signal }) => api.drill(id, signal) });
  // The scenario is the planner's and the evaluator's: the others are refused, and the tab is not shown.
  const injects = useQuery({
    queryKey: drillKeys.injects(id),
    queryFn: ({ signal }) => api.injects(id, signal),
    retry: false,
    enabled: drill.isSuccess,
  });
  const d = drill.data;
  const started = d ? STARTED.has(d.status) : false;
  const tabs: Tab[] = [];
  if (injects.data) tabs.push("scenario");
  if (started) tabs.push("run");
  if (d?.can_evaluate && injects.data) tabs.push("evaluation");
  if (d && (d.status === "stopped" || d.status === "ended" || d.status === "closed")) tabs.push("report");
  const [chosen, setChosen] = useState<Tab | null>(null);
  const tab = chosen && tabs.includes(chosen) ? chosen : (started ? (d?.status === "running" ? "run" : "report") : tabs[0]) ?? null;
  if (drill.isLoading) return <Loading />;
  if (drill.isError) return <ErrorBox error={drill.error} onRetry={() => void drill.refetch()} />;
  if (!d) return null;
  return (
    <div className="page drill-page">
      <p>
        <Link to="/drills">{t("drill.back")}</Link>
      </p>
      <PageTitle icon="militaryTech" tone="amber">
        {d.title}
      </PageTitle>
      <div className="drill-page__meta">
        <SimBadge /> <DrillStatusPill status={d.status} />{" "}
        <span className="muted">
          {fmt.dateTime(d.planned_start)} · {t("drill.minutes", { count: d.duration_min })}
          {d.hazard_key && <> · {t(`drill.hazard.${d.hazard_key}`, { defaultValue: d.hazard_key })}</>}
          {d.evaluator_name && <> · {t("drill.field.evaluator_name")}: {d.evaluator_name}</>}
        </span>
      </div>
      <p dir="auto">{d.objective}</p>
      {d.stop_reason && (
        <p className="alert alert--warn">
          {t("drill.stop.stopped", { name: d.stopped_by_name ?? "—" })}: {d.stop_reason === "all_withdrawn" ? t("drill.stop.allWithdrawn") : d.stop_reason}
        </p>
      )}
      <StopBar drill={d} />
      <PlannerActions drill={d} />
      {d.status !== "draft" && <Participants drill={d} />}
      {injects.isError && !isApiError(injects.error) && <ErrorBox error={injects.error} onRetry={() => void injects.refetch()} />}
      {tabs.length > 0 && (
        <div role="tablist" aria-label={t("drill.tabs.label")} className="tabs">
          {tabs.map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
              onClick={() => setChosen(k)}
            >
              {t(`drill.tabs.${k}`)}
            </button>
          ))}
        </div>
      )}
      <div role="tabpanel">
        {tab === "scenario" && injects.data && <ScenarioTab drill={d} injects={injects.data} />}
        {tab === "run" && <RunTab drill={d} />}
        {tab === "evaluation" && injects.data && <EvaluationTab drill={d} injects={injects.data} />}
        {tab === "report" && <ReportTab drill={d} />}
      </div>
    </div>
  );
}
