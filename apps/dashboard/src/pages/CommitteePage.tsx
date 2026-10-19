import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import {
  URGENCIES,
  type Directive,
  type LevelRow,
  type OpLevel,
  type PerformanceRow,
  type Urgency,
} from "../lib/opsTypes";
import {
  canAcknowledgeDirectives,
  canIssueDirectives,
  canMonitorPerformance,
  isCommittee,
  settableLevels,
} from "../lib/roles";

export const REASON_MIN = 5;
export const REASON_MAX = 500;
export const PERIODS = [7, 30, 90] as const;
type Period = (typeof PERIODS)[number];

/** Start of the performance window, rounded to the hour so the query key stays stable while the page is open. */
export function sinceFor(days: number, now: number = Date.now()): string {
  const d = new Date(now - days * 86_400_000);
  d.setMinutes(0, 0, 0);
  return d.toISOString();
}

export function LevelTag({ level }: { level: OpLevel | null }) {
  const { t } = useTranslation();
  if (!level) return <span className="muted">—</span>;
  return <span className={`level-tag level-tag--${level}`}>{t(`levels.name.${level}`)}</span>;
}

/** Checkboxes for target gouvernorats (a regional user only has its own, fixed). */
function GouvernoratPicker({
  legend,
  options,
  selected,
  onChange,
  disabled,
  hint,
}: {
  legend: string;
  options: number[];
  selected: number[];
  onChange: (codes: number[]) => void;
  disabled?: boolean;
  hint?: string;
}) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const toggle = (code: number, on: boolean) =>
    onChange(on ? [...selected, code].sort((a, b) => a - b) : selected.filter((c) => c !== code));
  return (
    <fieldset className="chips gouvernorat-picker" disabled={disabled}>
      <legend>{legend}</legend>
      {hint && <p className="muted">{hint}</p>}
      {options.length > 1 && (
        <div className="actions">
          <button type="button" className="btn btn--small btn--ghost" onClick={() => onChange([...options])}>
            {t("committee.selectAll")}
          </button>
          <button type="button" className="btn btn--small btn--ghost" onClick={() => onChange([])}>
            {t("committee.selectNone")}
          </button>
        </div>
      )}
      {options.map((code) => (
        <label key={code} className="chip-toggle">
          <input type="checkbox" checked={selected.includes(code)} onChange={(e) => toggle(code, e.target.checked)} />
          <span>{gouvernorats.nameOf(code) ?? code}</span>
        </label>
      ))}
    </fieldset>
  );
}

// ---------------------------------------------------------------- levels (§1)

function LevelForm({ rows }: { rows: LevelRow[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const base = useId();
  const identity = user?.identity;
  const levels = identity ? settableLevels(identity) : [];
  const options = useMemo(
    () =>
      identity?.national
        ? rows.map((r) => r.gouvernorat_code)
        : identity?.gouvernoratCode != null
          ? [identity.gouvernoratCode]
          : [],
    [identity, rows],
  );
  const [codes, setCodes] = useState<number[]>(() => (options.length === 1 ? [...options] : []));
  const [level, setLevel] = useState<OpLevel | "">("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<{ codes?: boolean; level?: boolean; reason?: boolean }>({});
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.setLevels({ gouvernorat_codes: codes, level: level as OpLevel, reason: reason.trim() }),
    onSuccess: (updated) => {
      const byCode = new Map(updated.map((r) => [r.gouvernorat_code, r]));
      qc.setQueryData<LevelRow[]>(opsKeys.levels, (old) => old?.map((r) => byCode.get(r.gouvernorat_code) ?? r));
      void qc.invalidateQueries({ queryKey: ["performance"] });
      setDone(t("committee.levels.saved", { count: updated.length, level: t(`levels.name.${level || "normal"}`) }));
      setConfirming(false);
      setReason("");
      if (options.length > 1) setCodes([]);
    },
    onError: () => setConfirming(false),
  });

  if (levels.length === 0 || options.length === 0) return null;

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const trimmed = reason.trim();
    const next = {
      codes: codes.length === 0,
      level: level === "",
      reason: trimmed.length < REASON_MIN || trimmed.length > REASON_MAX,
    };
    setErrors(next);
    setDone(null);
    if (next.codes || next.level || next.reason) return;
    // Every change is confirmed; a disaster declaration states its effects first.
    if (!confirming) {
      setConfirming(true);
      return;
    }
    mutation.mutate();
  };

  const reasonId = `${base}-reason`;
  return (
    <form className="level-form" onSubmit={submit} noValidate aria-labelledby={`${base}-title`}>
      <h3 id={`${base}-title`}>{t("committee.levels.formTitle")}</h3>
      <GouvernoratPicker
        legend={t("committee.levels.targets")}
        options={options}
        selected={codes}
        onChange={(c) => {
          setCodes(c);
          setConfirming(false);
        }}
        disabled={mutation.isPending || options.length === 1}
        hint={options.length === 1 ? t("committee.levels.ownOnly") : undefined}
      />
      {errors.codes && (
        <p className="field__error" role="alert">
          {t("committee.levels.targetsRequired")}
        </p>
      )}
      <fieldset className="segmented" disabled={mutation.isPending}>
        <legend>{t("committee.levels.level")}</legend>
        {levels.map((l) => (
          <label key={l} className="segmented__item">
            <input
              type="radio"
              name={`${base}-level`}
              value={l}
              checked={level === l}
              onChange={() => {
                setLevel(l);
                setConfirming(false);
              }}
            />
            <span>{t(`levels.name.${l}`)}</span>
          </label>
        ))}
      </fieldset>
      {errors.level && (
        <p className="field__error" role="alert">
          {t("committee.levels.levelRequired")}
        </p>
      )}
      {!levels.includes("disaster") && <p className="muted">{t("committee.levels.localLimit")}</p>}
      <div className={`field${errors.reason ? " field--invalid" : ""}`}>
        <label htmlFor={reasonId}>{t("committee.levels.reason")}</label>
        <textarea
          id={reasonId}
          rows={3}
          maxLength={REASON_MAX}
          value={reason}
          aria-invalid={errors.reason ? true : undefined}
          aria-describedby={errors.reason ? `${reasonId}-error` : undefined}
          disabled={mutation.isPending}
          onChange={(e) => {
            setReason(e.target.value);
            setConfirming(false);
          }}
        />
        {errors.reason && (
          <p id={`${reasonId}-error`} className="field__error">
            {t("committee.levels.reasonLength", { min: REASON_MIN, max: REASON_MAX })}
          </p>
        )}
      </div>
      {confirming && (
        <div className={`alert ${level === "disaster" ? "alert--error" : "alert--warn"}`} role="alert">
          <p>
            {t("committee.levels.confirmText", {
              count: codes.length,
              level: t(`levels.name.${level || "normal"}`),
            })}
          </p>
          {level === "disaster" && <p>{t("committee.levels.disasterEffects")}</p>}
          {level === "crisis" && <p>{t("committee.levels.crisisEffects")}</p>}
        </div>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending
            ? t("committee.saving")
            : confirming
              ? t("committee.levels.confirm")
              : t("committee.levels.apply")}
        </button>
        {confirming && (
          <button type="button" className="btn" onClick={() => setConfirming(false)}>
            {t("common.cancel")}
          </button>
        )}
      </div>
      <div role="status" aria-live="polite">
        {done && <p className="alert alert--ok">{done}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

function LevelsSection() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const query = useQuery({ queryKey: opsKeys.levels, queryFn: ({ signal }) => api.levels(signal) });
  const rows = useMemo(
    () => [...(query.data ?? [])].sort((a, b) => a.gouvernorat_code - b.gouvernorat_code),
    [query.data],
  );
  return (
    <section className="card" aria-labelledby="sec-levels">
      <h2 id="sec-levels">{t("committee.levels.title")}</h2>
      <p className="muted">{t("committee.levels.intro")}</p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && (
        <>
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("committee.levels.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("committee.columns.gouvernorat")}</th>
                  <th scope="col">{t("committee.columns.level")}</th>
                  <th scope="col">{t("committee.columns.since")}</th>
                  <th scope="col">{t("committee.columns.reason")}</th>
                  <th scope="col">{t("committee.columns.setBy")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.gouvernorat_code}>
                    <th scope="row">{gouvernorats.nameOf(r.gouvernorat_code)}</th>
                    <td>
                      <LevelTag level={r.level} />
                    </td>
                    <td>
                      <time dateTime={r.since}>{fmt.dateTime(r.since)}</time>
                    </td>
                    <td dir="auto">{r.reason ?? "—"}</td>
                    <td>{r.set_by ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <LevelForm rows={rows} />
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- directives (§2)

function targetsText(
  codes: number[],
  t: (k: string) => string,
  nameOf: (c: number) => string | null,
): string {
  if (codes.length === 0) return t("committee.directives.allGouvernorats");
  return codes.map((c) => nameOf(c) ?? String(c)).join(t("common.listSeparator"));
}

function AckForm({ directive }: { directive: Directive }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [note, setNote] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.acknowledgeDirective(directive.id, note),
    onSuccess: () => void qc.invalidateQueries({ queryKey: opsKeys.directivesAll }),
  });
  return (
    <form
      className="ack-form"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <div className="field">
        <label htmlFor={id}>{t("committee.directives.ackNote")}</label>
        <input
          id={id}
          type="text"
          maxLength={1000}
          value={note}
          disabled={mutation.isPending}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {t("committee.directives.acknowledge")}
        </button>
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

function DirectiveItem({ directive }: { directive: Directive }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const own = user?.identity.gouvernoratCode ?? null;
  const mayAck =
    canAcknowledgeDirectives(user?.identity.roles ?? []) && own !== null && directive.pending_acks.includes(own);
  return (
    <li className={`directive directive--${directive.urgency}`}>
      <div className="directive__head">
        <h3 dir="auto">{directive.title}</h3>
        <span className={`tag tag--urgency-${directive.urgency}`}>{t(`committee.urgency.${directive.urgency}`)}</span>
        <span className="tag">{t(`committee.directives.from.${directive.from_level}`)}</span>
      </div>
      <p className="muted">
        {t("committee.directives.issued", { by: directive.issued_by ?? "—", at: fmt.dateTime(directive.issued_at) })}
        {" · "}
        {t("committee.directives.targets", {
          targets: targetsText(directive.gouvernorat_codes, t, gouvernorats.nameOf),
        })}
      </p>
      <p className="directive__body" dir="auto">
        {directive.body}
      </p>
      {directive.acks.length > 0 && (
        <div>
          <h4>{t("committee.directives.acks")}</h4>
          <ul className="directive__acks">
            {directive.acks.map((a) => (
              <li key={a.gouvernorat_code}>
                <strong>{gouvernorats.nameOf(a.gouvernorat_code)}</strong>{" "}
                <span className="muted">
                  {t("committee.directives.ackedBy", { by: a.acked_by ?? "—", at: fmt.dateTime(a.acked_at) })}
                </span>
                {a.note && (
                  <span dir="auto">
                    {" — "}
                    {a.note}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {directive.pending_acks.length > 0 && (
        <p>
          <strong>{t("committee.directives.pending")}</strong>{" "}
          {directive.pending_acks.map((c) => gouvernorats.nameOf(c) ?? String(c)).join(t("common.listSeparator"))}
        </p>
      )}
      {mayAck && <AckForm directive={directive} />}
    </li>
  );
}

function IssueForm() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const base = useId();
  const national = user?.identity.national ?? false;
  const own = user?.identity.gouvernoratCode ?? null;
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [urgency, setUrgency] = useState<Urgency>("normal");
  const [codes, setCodes] = useState<number[]>([]);
  const [errors, setErrors] = useState<{ title?: boolean; body?: boolean }>({});
  const [done, setDone] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      api.issueDirective({
        title: title.trim(),
        body: body.trim(),
        urgency,
        // A local committee addresses its own gouvernorat (§0).
        gouvernorat_codes: national ? codes : own !== null ? [own] : [],
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: opsKeys.directivesAll });
      setTitle("");
      setBody("");
      setUrgency("normal");
      setCodes([]);
      setDone(true);
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const next = { title: title.trim().length < 3, body: body.trim().length < 1 };
    setErrors(next);
    setDone(false);
    if (next.title || next.body) return;
    mutation.mutate();
  };
  const titleId = `${base}-title`;
  const bodyId = `${base}-body`;
  return (
    <form className="directive-form" onSubmit={submit} noValidate aria-labelledby={`${base}-heading`}>
      <h3 id={`${base}-heading`}>{t("committee.directives.issueTitle")}</h3>
      <div className={`field${errors.title ? " field--invalid" : ""}`}>
        <label htmlFor={titleId}>{t("committee.directives.fieldTitle")}</label>
        <input
          id={titleId}
          type="text"
          maxLength={150}
          value={title}
          aria-invalid={errors.title ? true : undefined}
          onChange={(e) => setTitle(e.target.value)}
        />
        {errors.title && <p className="field__error">{t("committee.directives.titleLength")}</p>}
      </div>
      <div className={`field${errors.body ? " field--invalid" : ""}`}>
        <label htmlFor={bodyId}>{t("committee.directives.fieldBody")}</label>
        <textarea
          id={bodyId}
          rows={5}
          maxLength={5000}
          value={body}
          aria-invalid={errors.body ? true : undefined}
          onChange={(e) => setBody(e.target.value)}
        />
        {errors.body && <p className="field__error">{t("committee.directives.bodyRequired")}</p>}
      </div>
      <fieldset className="segmented">
        <legend>{t("committee.directives.urgency")}</legend>
        {URGENCIES.map((u) => (
          <label key={u} className="segmented__item">
            <input
              type="radio"
              name={`${base}-urgency`}
              value={u}
              checked={urgency === u}
              onChange={() => setUrgency(u)}
            />
            <span>{t(`committee.urgency.${u}`)}</span>
          </label>
        ))}
      </fieldset>
      {national ? (
        <GouvernoratPicker
          legend={t("committee.directives.targetsLegend")}
          hint={t("committee.directives.emptyIsAll")}
          options={gouvernorats.list.map((g) => g.code)}
          selected={codes}
          onChange={setCodes}
        />
      ) : (
        <p className="muted">
          {t("committee.directives.ownTarget", { name: gouvernorats.nameOf(own) ?? "—" })}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("committee.saving") : t("committee.directives.issue")}
        </button>
      </div>
      <div role="status" aria-live="polite">
        {done && <p className="alert alert--ok">{t("committee.directives.issuedOk")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

function DirectivesSection() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const pendingId = useId();
  const [pending, setPending] = useState(false);
  const query = useInfiniteQuery({
    queryKey: opsKeys.directives(pending),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.directives({ pending, cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section className="card" aria-labelledby="sec-directives">
      <h2 id="sec-directives">{t("committee.directives.title")}</h2>
      {canIssueDirectives(user?.identity.roles ?? []) && <IssueForm />}
      <div className="list-tools">
        <label htmlFor={pendingId} className="checkbox">
          <input id={pendingId} type="checkbox" checked={pending} onChange={(e) => setPending(e.target.checked)} />
          <span>{t("committee.directives.pendingOnly")}</span>
        </label>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="empty">{t("committee.directives.empty")}</p>}
      {items.length > 0 && (
        <ul className="directives" aria-label={t("committee.directives.title")}>
          {items.map((d) => (
            <DirectiveItem key={d.id} directive={d} />
          ))}
        </ul>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("committee.loadMore")}
          </button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- performance (§2)

function PerformanceCells({ row }: { row: PerformanceRow }) {
  const fmt = useFormat();
  const duration = (s: number | null) => (s === null ? "—" : fmt.duration(s));
  return (
    <>
      <td>
        <LevelTag level={row.level} />
      </td>
      <td>{fmt.number(row.reports)}</td>
      <td>{fmt.number(row.closed)}</td>
      <td>{fmt.number(row.rejected)}</td>
      <td>{duration(row.avg_first_response_s)}</td>
      <td>{duration(row.avg_resolution_s)}</td>
      <td>{fmt.number(row.open_incidents)}</td>
      <td>{fmt.number(row.active_assignments)}</td>
      <td>
        {fmt.number(row.volunteers_ready)} / {fmt.number(row.volunteers_approved)}
      </td>
      <td>{fmt.number(row.alerts_active)}</td>
    </>
  );
}

function PerformanceSection() {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const periodId = useId();
  const [period, setPeriod] = useState<Period>(30);
  const since = useMemo(() => sinceFor(period), [period]);
  const query = useQuery({
    queryKey: opsKeys.performance(since),
    queryFn: ({ signal }) => api.performance(since, signal),
  });
  const columns = [
    "gouvernorat",
    "level",
    "reports",
    "closed",
    "rejected",
    "firstResponse",
    "resolution",
    "openIncidents",
    "activeAssignments",
    "volunteers",
    "alerts",
  ] as const;
  return (
    <section className="card" aria-labelledby="sec-performance">
      <h2 id="sec-performance">{t("committee.performance.title")}</h2>
      <p className="muted">{t("committee.performance.intro")}</p>
      <div className="field">
        <label htmlFor={periodId}>{t("committee.performance.period")}</label>
        <select id={periodId} value={period} onChange={(e) => setPeriod(Number(e.target.value) as Period)}>
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {t("committee.performance.lastDays", { count: p })}
            </option>
          ))}
        </select>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && (
        <div className="table-wrap">
          <table className="table performance-table">
            <caption className="visually-hidden">{t("committee.performance.title")}</caption>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c} scope="col">
                    {t(`committee.performance.columns.${c}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data.rows.map((r) => (
                <tr key={r.gouvernorat_code ?? "none"}>
                  <th scope="row">{gouvernorats.nameOf(r.gouvernorat_code) ?? t("common.notAvailable")}</th>
                  <PerformanceCells row={r} />
                </tr>
              ))}
            </tbody>
            {query.data.rows.length > 1 && (
              <tfoot>
                <tr>
                  <th scope="row">{t("committee.performance.total")}</th>
                  <PerformanceCells row={query.data.national} />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </section>
  );
}

/** FR-C-15, FR-C-16, FR-C-24: operational levels, directives and performance monitoring for the committees. */
export function CommitteePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("committee.title")}</h1>
      </div>
      <LevelsSection />
      {isCommittee(roles) && <DirectivesSection />}
      {canMonitorPerformance(roles) && <PerformanceSection />}
    </div>
  );
}
