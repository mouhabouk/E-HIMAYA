// covers: phase L3 (docs/phase-l/design-l3.md §2, §6): the axes of the operations rooms, the declaration requests,
// opening an axis (commander) and requesting one (regional operations manager).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { LevelPill, SimBadge } from "../components/crisis/CrisisBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { AXIS_KINDS, AXIS_LEVELS, crisisKeys, type Axis, type AxisKind, type DeclarationRequest } from "../lib/crisis";
import { displayName, isSimulated, readPromotion, type Promotion } from "../lib/crisisText";
import { useFormat, useGouvernorats } from "../lib/hooks";

interface DraftAxis {
  name: string;
  kind: AxisKind;
  level: number;
  gouvernorat: number | null;
  text: string;
  national: boolean;
}

function AxisForm({ mode, onClose, from }: { mode: "open" | "request"; onClose: () => void; from?: Promotion | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const { list } = useGouvernorats();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const id = useId();
  const [f, setF] = useState<DraftAxis>({
    name: from?.name ?? "",
    kind: from?.kind ?? "flood",
    level: 2,
    gouvernorat: from?.gouvernorat ?? user?.identity.gouvernoratCode ?? null,
    text: "",
    national: false,
  });
  const [tried, setTried] = useState(false);
  // Phase N (design §4): a disaster promoted from an intervention carries it from the start.
  const incidents = from ? [from.incident] : [];
  const save = useMutation({
    mutationFn: async () => {
      if (mode === "request")
        return api
          .requestDeclaration({ name: f.name.trim(), kind: f.kind, level: f.level, facts: f.text.trim(), incident_ids: incidents })
          .then(() => null);
      return api
        .openAxis({
          name: f.name.trim(),
          kind: f.kind,
          level: f.level,
          gouvernorat_code: f.gouvernorat,
          plan: f.text.trim(),
          national: f.national,
          gouvernorats: f.national && f.gouvernorat ? [f.gouvernorat] : [],
          incident_ids: incidents,
        })
        .then((a) => a.id);
    },
    onSuccess: (axisId) => {
      void qc.invalidateQueries({ queryKey: crisisKeys.all });
      if (axisId) void navigate(`/axes/${axisId}`);
      else onClose();
    },
  });
  const ok = f.name.trim().length >= 3 && (mode === "open" ? f.gouvernorat !== null : f.text.trim().length >= 10);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (ok) save.mutate();
  };
  return (
    <form className="card ops-form" onSubmit={submit} noValidate aria-labelledby={`${id}-t`}>
      <h2 id={`${id}-t`}>{mode === "open" ? t("crisis.axes.open") : t("crisis.axes.request")}</h2>
      {from && <p className="muted">{t("disasters.promoted")}</p>}
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-n`}>{t("crisis.axes.name")}</label>
          <input
            id={`${id}-n`}
            value={f.name}
            aria-invalid={(tried && f.name.trim().length < 3) || undefined}
            placeholder={t("crisis.axes.namePlaceholder")}
            onChange={(e) => setF({ ...f, name: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-k`}>{t("crisis.axes.kind")}</label>
          <select id={`${id}-k`} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as AxisKind })}>
            {AXIS_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`crisis.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-l`}>{t("crisis.axis.level")}</label>
          <select id={`${id}-l`} value={f.level} onChange={(e) => setF({ ...f, level: Number(e.target.value) })}>
            {AXIS_LEVELS.map((l) => (
              <option key={l} value={l}>
                {l} · {t(`crisis.level.${l}`)}
              </option>
            ))}
          </select>
        </div>
        {mode === "open" && (
          <div className="field">
            <label htmlFor={`${id}-g`}>{t("crisis.command.gouvernorat")}</label>
            <select
              id={`${id}-g`}
              value={f.gouvernorat ?? ""}
              aria-invalid={(tried && f.gouvernorat === null) || undefined}
              onChange={(e) => setF({ ...f, gouvernorat: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">—</option>
              {list.map((g) => (
                <option key={g.code} value={g.code}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {mode === "open" && (
        <label className="check">
          <input type="checkbox" checked={f.national} onChange={(e) => setF({ ...f, national: e.target.checked })} />
          {t("crisis.axes.national")}
        </label>
      )}
      <div className="field">
        <label htmlFor={`${id}-x`}>{mode === "open" ? t("crisis.axes.plan") : t("crisis.axes.facts")}</label>
        <textarea
          id={`${id}-x`}
          rows={3}
          value={f.text}
          aria-invalid={(tried && mode === "request" && f.text.trim().length < 10) || undefined}
          onChange={(e) => setF({ ...f, text: e.target.value })}
        />
      </div>
      {save.isError && <p role="alert" className="field__error">{t(errorMessageKey(save.error))}</p>}
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {mode === "open" ? t("crisis.axes.openConfirm") : t("crisis.axes.requestConfirm")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function RequestItem({ r, canDecide }: { r: DeclarationRequest; canDecide: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const id = useId();
  const [reason, setReason] = useState("");
  const decide = useMutation({
    mutationFn: (accept: boolean) => api.decideRequest(r.id, accept, reason.trim()),
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: crisisKeys.all });
      if (d.axis_id) void navigate(`/axes/${d.axis_id}`);
    },
  });
  return (
    <li className="request-card">
      <p className="request-card__head">
        <LevelPill level={r.level} /> <strong>{r.name}</strong> · {r.gouvernorat_name} · {t(`crisis.kind.${r.kind}`)}
      </p>
      <p>{r.facts}</p>
      <p className="muted">
        {r.created_by_name} · {fmt.dateTime(r.created_at)} · {t("crisis.axes.requestIncidents", { n: r.incident_ids.length })}
      </p>
      {r.status !== "pending" && (
        <p className="muted">
          {t(`crisis.axes.requestStatus.${r.status}`)} {r.decision_reason ? `· ${r.decision_reason}` : ""}
        </p>
      )}
      {canDecide && r.status === "pending" && (
        <div className="directive__actions">
          <label htmlFor={`${id}-r`} className="visually-hidden">
            {t("crisis.axes.rejectReason")}
          </label>
          <input id={`${id}-r`} value={reason} placeholder={t("crisis.axes.rejectReason")} onChange={(e) => setReason(e.target.value)} />
          <button type="button" className="btn btn--small btn--primary" onClick={() => decide.mutate(true)} disabled={decide.isPending}>
            {t("crisis.axes.accept")}
          </button>
          <button
            type="button"
            className="btn btn--small btn--danger"
            onClick={() => decide.mutate(false)}
            disabled={decide.isPending || reason.trim().length < 5}
          >
            {t("crisis.axes.reject")}
          </button>
        </div>
      )}
      {decide.isError && <p role="alert" className="field__error">{t(errorMessageKey(decide.error))}</p>}
    </li>
  );
}

function AxisTile({ a }: { a: Axis }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <li className={`axis-card axis-card--tile level-${a.level}`}>
      <div className="axis-card__head">
        <LevelPill level={a.level} />
        <span className="axis-card__no">{a.number}</span>
        {isSimulated(a) && <SimBadge />}
      </div>
      <p className="axis-card__name">
        <Link to={`/axes/${a.id}`}>{displayName(a)}</Link>
      </p>
      <p className="axis-card__meta">
        {t(`crisis.kind.${a.kind}`)} · {a.scope === "national" ? t("crisis.axis.nationalOf", { n: a.gouvernorats.length }) : a.gouvernorat_name} ·{" "}
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
          <dt>{t("crisis.fig.decisionsDone")}</dt>
          <dd>
            {a.figures.decisions_done}/{a.figures.decisions}
          </dd>
        </div>
      </dl>
    </li>
  );
}

export function AxesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const identity = user?.identity;
  const roles = identity?.roles ?? [];
  const national = Boolean(identity?.national);
  const commander = national && roles.includes("ops_manager");
  const regionalManager = !national && roles.includes("ops_manager");
  const [state, setState] = useState<"open" | "closed">("open");
  const [params] = useSearchParams();
  const promotion = readPromotion(params);
  // null until the user picks: a promotion from an intervention opens its form once the account is known.
  const [picked, setForm] = useState<"none" | "open" | "request" | null>(null);
  const form = picked ?? (promotion && commander ? "open" : promotion && regionalManager ? "request" : "none");
  const axes = useQuery({ queryKey: crisisKeys.axes(state), queryFn: ({ signal }) => api.crisisAxes(state, signal), refetchInterval: 60_000 });
  const requests = useQuery({ queryKey: crisisKeys.requests("pending"), queryFn: ({ signal }) => api.declarationRequests("pending", signal) });
  return (
    <div className="axes-page">
      <div className="page-head">
        <PageTitle icon="warning" tone="red">
          {t("crisis.axes.title")}
        </PageTitle>
        <div className="page-head__actions">
          {commander && (
            <button type="button" className="btn btn--primary" onClick={() => setForm("open")}>
              {t("crisis.axes.open")}
            </button>
          )}
          {regionalManager && (
            <button type="button" className="btn btn--primary" onClick={() => setForm("request")}>
              {t("crisis.axes.request")}
            </button>
          )}
          <Link className="btn" to="/command">
            {t("nav.command")}
          </Link>
        </div>
      </div>
      <p className="muted">{t("crisis.axes.intro")}</p>
      {form !== "none" && <AxisForm mode={form} onClose={() => setForm("none")} from={promotion} />}
      {(requests.data?.length ?? 0) > 0 && (
        <section className="card" aria-labelledby="axes-requests">
          <h2 id="axes-requests">{t("crisis.axes.pending", { n: requests.data?.length ?? 0 })}</h2>
          <ul className="request-list">
            {requests.data?.map((r) => (
              <RequestItem key={r.id} r={r} canDecide={commander} />
            ))}
          </ul>
        </section>
      )}
      <div className="segmented" role="radiogroup" aria-label={t("crisis.axes.state")}>
        {(["open", "closed"] as const).map((s) => (
          <label key={s} className="segmented__item">
            <input type="radio" name="axes-state" checked={state === s} onChange={() => setState(s)} />
            <span>{t(`crisis.axes.${s}List`)}</span>
          </label>
        ))}
      </div>
      {axes.isLoading && <Loading />}
      {axes.isError && <ErrorBox error={axes.error} onRetry={() => void axes.refetch()} />}
      {axes.data && axes.data.length === 0 && <p className="ops-empty card">{t(state === "open" ? "crisis.axes.noneOpen" : "crisis.axes.noneClosed")}</p>}
      <ul className="axis-grid">
        {axes.data?.map((a) => (
          <AxisTile key={a.id} a={a} />
        ))}
      </ul>
    </div>
  );
}
