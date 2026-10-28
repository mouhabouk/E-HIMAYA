import { useEffect, useId, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useServices } from "../../context/services";
import { errorMessageKey } from "../../lib/api";
import {
  crisisKeys,
  DIRECTIVE_CATEGORIES,
  EXECUTORS,
  LEVEL_TONE,
  NEXT_STATUS,
  type Axis,
  type Directive,
  type DirectiveBody,
  type DirectiveStatus,
  type Figures,
} from "../../lib/crisis";
import { useFormat } from "../../lib/hooks";

/** The level of an axis: its colour and its name, never the colour alone. */
export function LevelPill({ level }: { level: number }) {
  const { t } = useTranslation();
  return (
    <span className={`level-pill tone-${LEVEL_TONE[level] ?? "slate"}`}>
      <span className="level-pill__n" aria-hidden="true">
        {level}
      </span>
      {t(`crisis.level.${level}`)}
    </span>
  );
}

/** The [SIM] badge of simulated data (standing rule): amber, always with the word. */
export function SimBadge() {
  const { t } = useTranslation();
  return <span className="sim-badge">[SIM] {t("crisis.sim")}</span>;
}

/** A glass panel of the operations room. */
export function Panel({ title, actions, children, className }: { title: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  const id = useId();
  return (
    <section className={`ops-panel ${className ?? ""}`} aria-labelledby={id}>
      <header className="ops-panel__head">
        <h2 id={id}>{title}</h2>
        {actions}
      </header>
      <div className="ops-panel__body">{children}</div>
    </section>
  );
}

/** A large figure with its label, and an optional ring (a share between 0 and 1). */
export function Kpi({ label, value, tone, share, hint }: { label: string; value: string; tone: string; share?: number | null; hint?: string }) {
  return (
    <div className={`kpi-tile tone-${tone}`}>
      {share !== undefined && share !== null && <Ring share={share} />}
      <div>
        <p className="kpi-tile__value">
          <bdi dir="ltr">{value}</bdi>
        </p>
        <p className="kpi-tile__label">{label}</p>
        {hint && <p className="kpi-tile__hint">{hint}</p>}
      </div>
    </div>
  );
}

export function Ring({ share, size = 52 }: { share: number; size?: number }) {
  const r = 20;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, share));
  return (
    <svg className="ring" width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="24" r={r} className="ring__track" />
      <circle cx="24" cy="24" r={r} className="ring__value" strokeDasharray={`${clamped * c} ${c}`} transform="rotate(-90 24 24)" />
      <text x="24" y="28" textAnchor="middle" className="ring__text">
        {Math.round(clamped * 100)}%
      </text>
    </svg>
  );
}

/** Horizontal bars (resources by kind), each value written in full. */
export function Bars({ items }: { items: { label: string; value: number }[] }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="ops-bars">
      {items.map((i) => (
        <li key={i.label}>
          <span className="ops-bars__label">{i.label}</span>
          <span className="ops-bars__track" aria-hidden="true">
            <span className="ops-bars__fill" style={{ inlineSize: `${(i.value / max) * 100}%` }} />
          </span>
          <span className="ops-bars__value">{i.value}</span>
        </li>
      ))}
    </ul>
  );
}

/** The figures of an axis as tiles. */
export function FigureTiles({ f }: { f: Figures }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const shelter = f.shelter_capacity ? f.sheltered / f.shelter_capacity : null;
  return (
    <div className="kpi-row">
      <Kpi label={t("crisis.fig.incidentsOpen")} value={`${fmt.number(f.incidents_open)} / ${fmt.number(f.incidents)}`} tone="red" />
      <Kpi label={t("crisis.fig.deceased")} value={fmt.number(f.deceased)} tone="slate" hint={t("crisis.fig.injuredHint", { n: f.injured })} />
      <Kpi label={t("crisis.fig.rescued")} value={fmt.number(f.rescued)} tone="green" />
      <Kpi label={t("crisis.fig.evacuated")} value={fmt.number(f.evacuated)} tone="teal" />
      <Kpi label={t("crisis.fig.sheltered")} value={`${fmt.number(f.sheltered)} / ${fmt.number(f.shelter_capacity)}`} tone="sky" share={shelter} />
      <Kpi label={t("crisis.fig.resources")} value={fmt.number(f.resources)} tone="amber" hint={t("crisis.fig.volunteersHint", { n: f.volunteers })} />
      <Kpi
        label={t("crisis.fig.decisionsDone")}
        value={`${fmt.number(f.decisions_done)} / ${fmt.number(f.decisions)}`}
        tone="purple"
        share={f.done_share}
        hint={f.mean_hours_to_done !== null ? t("crisis.fig.meanHours", { h: f.mean_hours_to_done }) : undefined}
      />
    </div>
  );
}

/** Local time, refreshed every half minute (the room's wall clock). */
export function Clock() {
  const fmt = useFormat();
  const [now, setNow] = useState(() => new Date().toISOString());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date().toISOString()), 30_000);
    return () => clearInterval(id);
  }, []);
  return (
    <time className="ops-clock" dateTime={now}>
      {fmt.dateTime(now)}
    </time>
  );
}

const STATUS_TONE: Record<DirectiveStatus, string> = {
  issued: "navy",
  received: "sky",
  in_progress: "amber",
  done: "green",
  failed: "red",
};

/** A recommendation or a decision, its signature, its history and (for the executing room) the next steps. */
export function DirectiveItem({ d, axisName }: { d: Directive; axisName?: string }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const id = useId();
  const change = useMutation({
    mutationFn: (status: DirectiveStatus) => api.axisDirectiveStatus(d.id, status, reason.trim()),
    onSuccess: () => {
      setReason("");
      void qc.invalidateQueries({ queryKey: crisisKeys.all });
    },
  });
  const tone = d.overridden_by ? "slate" : STATUS_TONE[d.status];
  return (
    <li className={`directive directive--${d.kind}${d.overridden_by ? " directive--overridden" : ""}`}>
      <div className="directive__head">
        <span className={`pill tone-${d.kind === "decision" ? "red" : "navy"}`}>{t(`crisis.directive.kind.${d.kind}`)}</span>
        <span className="directive__no">
          {d.axis_number} · {t("crisis.directive.number", { n: d.number })}
        </span>
        <span className={`pill tone-${tone}`}>
          {d.overridden_by ? t("crisis.directive.overridden") : t(`crisis.directive.status.${d.status}`)}
        </span>
        {d.overdue && <span className="pill tone-red">{t("crisis.directive.overdue")}</span>}
      </div>
      <p className="directive__body">{d.body}</p>
      <dl className="directive__meta">
        <div>
          <dt>{t("crisis.directive.category")}</dt>
          <dd>{t(`crisis.directive.cat.${d.category}`)}</dd>
        </div>
        <div>
          <dt>{t("crisis.directive.executor")}</dt>
          <dd>{d.executor === "partner" ? d.executor_name : t(`crisis.directive.exec.${d.executor}`)}</dd>
        </div>
        {d.due_at && (
          <div>
            <dt>{t("crisis.directive.due")}</dt>
            <dd>{fmt.dateTime(d.due_at)}</dd>
          </div>
        )}
        <div>
          <dt>{t("crisis.directive.issuer")}</dt>
          <dd>
            {t(`crisis.role.${d.issuer_role}`)}
            {d.issued_by_name ? ` · ${d.issued_by_name}` : ""} · {fmt.dateTime(d.issued_at)}
          </dd>
        </div>
        {axisName && (
          <div>
            <dt>{t("crisis.axis.label")}</dt>
            <dd>{axisName}</dd>
          </div>
        )}
      </dl>
      {d.signature ? (
        <p className="directive__sig">
          <span aria-hidden="true">✓ </span>
          {t("crisis.directive.signed", { key: d.key_id })}
        </p>
      ) : (
        <p className="directive__sig muted">{t("crisis.directive.unsigned")}</p>
      )}
      {d.status_reason && <p className="muted">{t("crisis.directive.reason", { reason: d.status_reason })}</p>}
      {d.can_update && (
        <div className="directive__actions">
          <label htmlFor={`${id}-r`} className="visually-hidden">
            {t("crisis.directive.reasonLabel")}
          </label>
          <input
            id={`${id}-r`}
            value={reason}
            placeholder={t("crisis.directive.reasonLabel")}
            onChange={(e) => setReason(e.target.value)}
          />
          {NEXT_STATUS[d.status].map((s) => (
            <button
              key={s}
              type="button"
              className={s === "failed" ? "btn btn--small btn--danger" : "btn btn--small btn--primary"}
              disabled={change.isPending || (s === "failed" && reason.trim().length < 5)}
              onClick={() => change.mutate(s)}
            >
              {t(`crisis.directive.to.${s}`)}
            </button>
          ))}
          {change.isError && <p role="alert" className="field__error">{t(errorMessageKey(change.error))}</p>}
        </div>
      )}
    </li>
  );
}

/** The governor's and the minister's form: one recommendation or decision on one axis. */
export function DirectiveForm({ axes, onDone }: { axes: Axis[]; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const issuable = axes.filter((a) => a.can_issue);
  const [axisId, setAxisId] = useState(issuable[0]?.id ?? "");
  const [form, setForm] = useState<DirectiveBody>({ kind: "decision", category: "evacuation", body: "", executor: "regional" });
  const [due, setDue] = useState("");
  const [tried, setTried] = useState(false);
  const issue = useMutation({
    mutationFn: () =>
      api.issueAxisDirective(axisId, {
        ...form,
        body: form.body.trim(),
        executor_name: form.executor === "partner" ? (form.executor_name ?? "").trim() : null,
        due_at: due ? new Date(due).toISOString() : null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: crisisKeys.all });
      onDone();
    },
  });
  const ok = axisId && form.body.trim().length >= 5 && (form.executor !== "partner" || (form.executor_name ?? "").trim().length >= 2);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (ok) issue.mutate();
  };
  if (issuable.length === 0) return <p className="muted">{t("crisis.directive.noAxis")}</p>;
  return (
    <form className="ops-form" onSubmit={submit} noValidate aria-labelledby={`${id}-t`}>
      <h3 id={`${id}-t`}>{t("crisis.directive.new")}</h3>
      <fieldset className="segmented">
        <legend>{t("crisis.directive.kindLabel")}</legend>
        {(["decision", "recommendation"] as const).map((k) => (
          <label key={k}>
            <input type="radio" name={`${id}-kind`} checked={form.kind === k} onChange={() => setForm((f) => ({ ...f, kind: k }))} />
            {t(`crisis.directive.kind.${k}`)}
          </label>
        ))}
      </fieldset>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-axis`}>{t("crisis.axis.label")}</label>
          <select id={`${id}-axis`} value={axisId} onChange={(e) => setAxisId(e.target.value)}>
            {issuable.map((a) => (
              <option key={a.id} value={a.id}>
                {a.number} · {a.gouvernorat_name ?? t("crisis.axis.national")}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-cat`}>{t("crisis.directive.category")}</label>
          <select id={`${id}-cat`} value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as DirectiveBody["category"] }))}>
            {DIRECTIVE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`crisis.directive.cat.${c}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-ex`}>{t("crisis.directive.executor")}</label>
          <select id={`${id}-ex`} value={form.executor} onChange={(e) => setForm((f) => ({ ...f, executor: e.target.value as DirectiveBody["executor"] }))}>
            {EXECUTORS.map((x) => (
              <option key={x} value={x}>
                {t(`crisis.directive.exec.${x}`)}
              </option>
            ))}
          </select>
        </div>
        {form.executor === "partner" && (
          <div className="field">
            <label htmlFor={`${id}-pn`}>{t("crisis.directive.partnerName")}</label>
            <input id={`${id}-pn`} value={form.executor_name ?? ""} onChange={(e) => setForm((f) => ({ ...f, executor_name: e.target.value }))} />
          </div>
        )}
        <div className="field">
          <label htmlFor={`${id}-due`}>{t("crisis.directive.due")}</label>
          <input id={`${id}-due`} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-body`}>{t("crisis.directive.text")}</label>
        <textarea
          id={`${id}-body`}
          rows={3}
          value={form.body}
          aria-invalid={(tried && form.body.trim().length < 5) || undefined}
          onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
        />
      </div>
      <p className="muted">{t("crisis.directive.signNote")}</p>
      {issue.isError && <p role="alert" className="field__error">{t(errorMessageKey(issue.error))}</p>}
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={issue.isPending}>
          {t("crisis.directive.issue")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}
