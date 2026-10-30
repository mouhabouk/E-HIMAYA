import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { crewKeys } from "../lib/crewApi";
import type { FieldAgent, FieldFunction } from "../lib/crewTypes";
import { useFormat, useGouvernorats } from "../lib/hooks";

const FUNCTIONS: FieldFunction[] = ["leader", "agent", "driver"];

/** The one-time code, shown once in the answer that made it: the room chief hands it to the agent. */
function CodeNotice({ agent, onClose }: { agent: FieldAgent; onClose: () => void }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="alert alert--success field-code" role="status" aria-live="polite">
      <p>{t("fieldAgents.codeFor", { name: agent.name, matricule: agent.matricule })}</p>
      <p className="field-code__value">
        <bdi dir="ltr">{agent.code}</bdi>
      </p>
      <p className="muted">
        {t("fieldAgents.codeOnce")}
        {agent.code_expires_at && ` ${t("fieldAgents.codeUntil", { time: fmt.dateTime(agent.code_expires_at) })}`}
      </p>
      <button type="button" className="btn btn--small" onClick={onClose}>
        {t("fieldAgents.codeHanded")}
      </button>
    </div>
  );
}

function AddForm({ gouvernorat, onCode }: { gouvernorat: number | null; onCode: (a: FieldAgent) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [matricule, setMatricule] = useState("");
  const [name, setName] = useState("");
  const [fn, setFn] = useState<FieldFunction>("agent");
  const [shift, setShift] = useState("");
  const [phone, setPhone] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api.createFieldAgent({
        matricule: matricule.trim(),
        name: name.trim(),
        function: fn,
        shift_label: shift.trim() || null,
        phone: phone.trim() || null,
        gouvernorat_code: gouvernorat,
      }),
    onSuccess: (agent) => {
      setMatricule("");
      setName("");
      setShift("");
      setPhone("");
      onCode(agent);
      void qc.invalidateQueries({ queryKey: crewKeys.fieldAgentsAll });
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <form className="form-grid" onSubmit={submit} aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`}>{t("fieldAgents.add")}</h3>
      <div className="field">
        <label htmlFor={`${id}-m`}>{t("fieldAgents.matricule")}</label>
        <input
          id={`${id}-m`}
          value={matricule}
          required
          pattern="[0-9A-Za-z]{3,20}"
          dir="ltr"
          autoComplete="off"
          onChange={(e) => setMatricule(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-n`}>{t("fieldAgents.name")}</label>
        <input id={`${id}-n`} value={name} required minLength={2} maxLength={120} dir="auto" onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={`${id}-f`}>{t("fieldAgents.function")}</label>
        <select id={`${id}-f`} value={fn} onChange={(e) => setFn(e.target.value as FieldFunction)}>
          {FUNCTIONS.map((f) => (
            <option key={f} value={f}>
              {t(`fieldAgents.functions.${f}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-s`}>{t("fieldAgents.shift")}</label>
        <input id={`${id}-s`} value={shift} maxLength={60} dir="auto" onChange={(e) => setShift(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={`${id}-p`}>{t("fieldAgents.phone")}</label>
        <input
          id={`${id}-p`}
          value={phone}
          type="tel"
          pattern="\+?[0-9 ]{8,16}"
          dir="ltr"
          onChange={(e) => setPhone(e.target.value)}
        />
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={create.isPending}>
          {t("fieldAgents.addSubmit")}
        </button>
      </div>
      {create.isError && <ErrorBox error={create.error} />}
    </form>
  );
}

type Pending = { kind: "disable" | "delete"; reason: string } | { kind: "imei"; imei: string } | null;

function AgentRow({ agent, onCode }: { agent: FieldAgent; onCode: (a: FieldAgent) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [pending, setPending] = useState<Pending>(null);
  const done = () => {
    setPending(null);
    void qc.invalidateQueries({ queryKey: crewKeys.fieldAgentsAll });
  };
  const code = useMutation({
    mutationFn: () => api.renewFieldCode(agent.id),
    onSuccess: (a) => {
      onCode(a);
      done();
    },
  });
  const act = useMutation({
    mutationFn: (p: NonNullable<Pending>) =>
      p.kind === "imei"
        ? api.updateFieldAgent(agent.id, { imei: p.imei.trim() })
        : api.disableFieldAgent(agent.id, p.reason.trim() || null, p.kind === "delete"),
    onSuccess: done,
  });
  const device = agent.device;
  return (
    <tr>
      <td>
        <strong dir="auto">{agent.name}</strong>
        <div className="cell-sub">
          <bdi dir="ltr">{agent.matricule}</bdi> · {t(`fieldAgents.functions.${agent.function}`)}
          {agent.shift_label && <span dir="auto"> · {agent.shift_label}</span>}
        </div>
        {agent.phone && (
          <div className="cell-sub">
            <bdi dir="ltr">{agent.phone}</bdi>
          </div>
        )}
      </td>
      <td>
        <span className={`chip chip--agent-${agent.status}`}>{t(`fieldAgents.status.${agent.status}`)}</span>
        {agent.status === "active" && !agent.charter_accepted_at && (
          <div className="cell-sub">{t("fieldAgents.charterPending")}</div>
        )}
        {agent.disabled_reason && (
          <div className="cell-sub" dir="auto">
            {agent.disabled_reason}
          </div>
        )}
      </td>
      <td>
        {device ? (
          <>
            <span dir="auto">{device.model ?? device.platform}</span>
            {device.revoked_at && (
              <>
                {" "}
                <span className="chip chip--crew-revoked">{t("crew.revoked")}</span>
              </>
            )}
            <div className="cell-sub">
              {device.sim_number && (
                <>
                  {t("fieldAgents.sim")} <bdi dir="ltr">{device.sim_number}</bdi> ·{" "}
                </>
              )}
              {t("fieldAgents.imei")} {device.imei ? <bdi dir="ltr">{device.imei}</bdi> : "—"}
            </div>
            <div className="cell-sub">
              {t("crew.lastSeen")}: <time dateTime={device.last_seen_at}>{fmt.dateTime(device.last_seen_at)}</time>
            </div>
          </>
        ) : (
          <span className="muted">{t("fieldAgents.noDevice")}</span>
        )}
      </td>
      <td>
        {agent.last_position ? (
          <>
            <bdi dir="ltr">
              {agent.last_position.lat.toFixed(5)}, {agent.last_position.lon.toFixed(5)}
            </bdi>
            <div className="cell-sub">
              <time dateTime={agent.last_position.at}>{fmt.dateTime(agent.last_position.at)}</time>
            </div>
          </>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td>
        <div className="ops-row-actions">
          <button type="button" className="btn btn--small" disabled={code.isPending} onClick={() => code.mutate()}>
            {agent.status === "pending" ? t("fieldAgents.newCode") : t("fieldAgents.newPhone")}
          </button>
          {device && !device.revoked_at && (
            <button type="button" className="btn btn--small" onClick={() => setPending({ kind: "imei", imei: device.imei ?? "" })}>
              {t("fieldAgents.setImei")}
            </button>
          )}
          {agent.status !== "disabled" && (
            <button type="button" className="btn btn--small" onClick={() => setPending({ kind: "disable", reason: "" })}>
              {t("fieldAgents.disable")}
            </button>
          )}
          <button type="button" className="btn btn--small btn--danger" onClick={() => setPending({ kind: "delete", reason: "" })}>
            {t("fieldAgents.delete")}
          </button>
        </div>
        {pending && (
          <form
            className="ops-row-actions"
            onSubmit={(e) => {
              e.preventDefault();
              act.mutate(pending);
            }}
          >
            {pending.kind === "imei" ? (
              <>
                <label htmlFor={`${id}-i`}>{t("fieldAgents.imei")}</label>
                <input
                  id={`${id}-i`}
                  value={pending.imei}
                  required
                  pattern="[0-9]{14,16}"
                  inputMode="numeric"
                  dir="ltr"
                  onChange={(e) => setPending({ kind: "imei", imei: e.target.value })}
                />
              </>
            ) : (
              <>
                <span>
                  {pending.kind === "delete"
                    ? t("fieldAgents.deleteConfirm", { name: agent.name })
                    : t("fieldAgents.disableConfirm", { name: agent.name })}
                </span>
                <label className="visually-hidden" htmlFor={`${id}-r`}>
                  {t("fieldAgents.reason")}
                </label>
                <input
                  id={`${id}-r`}
                  value={pending.reason}
                  maxLength={300}
                  placeholder={t("fieldAgents.reason")}
                  dir="auto"
                  onChange={(e) => setPending({ kind: pending.kind, reason: e.target.value })}
                />
              </>
            )}
            <button
              type="submit"
              className={`btn btn--small${pending.kind === "imei" ? " btn--primary" : " btn--danger"}`}
              disabled={act.isPending}
            >
              {t("common.confirm")}
            </button>
            <button type="button" className="btn btn--small" onClick={() => setPending(null)}>
              {t("common.cancel")}
            </button>
          </form>
        )}
        {(code.isError || act.isError) && <ErrorBox error={code.error ?? act.error} />}
      </td>
    </tr>
  );
}

/** Phase F: the room chief adds the agents of the staff app, hands each a one-time code, follows their phones and
 * disables a lost one (its data stays on record). */
export function FieldAgentsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const national = user?.identity.national ?? false;
  const [chosen, setChosen] = useState("");
  const gouvernorat = national ? (chosen ? Number(chosen) : null) : (user?.identity.gouvernoratCode ?? null);
  const [shown, setShown] = useState<FieldAgent | null>(null);
  const pickId = useId();
  const query = useQuery({
    queryKey: crewKeys.fieldAgents(gouvernorat),
    queryFn: ({ signal }) => api.fieldAgents(gouvernorat, signal),
    enabled: gouvernorat !== null,
  });
  return (
    <div className="page field-agents-page">
      <div className="page__head">
        <PageTitle icon="groups" tone="green">
          {t("fieldAgents.pageTitle")}
        </PageTitle>
      </div>
      <p className="muted">{t("fieldAgents.intro")}</p>
      {national && (
        <div className="field">
          <label htmlFor={pickId}>{t("filters.gouvernorat")}</label>
          <select id={pickId} value={chosen} onChange={(e) => setChosen(e.target.value)}>
            <option value="">{t("referral.choose")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      )}
      {shown?.code && <CodeNotice agent={shown} onClose={() => setShown(null)} />}
      {gouvernorat !== null && (
        <section className="card" aria-labelledby="sec-agents">
          <h2 id="sec-agents">{t("fieldAgents.list")}</h2>
          {query.isPending && <Loading />}
          {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
          {query.isSuccess && query.data.length === 0 && <p className="muted">{t("fieldAgents.none")}</p>}
          {query.isSuccess && query.data.length > 0 && (
            <div className="table-wrap">
              <table className="table">
                <caption className="visually-hidden">{t("fieldAgents.list")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("fieldAgents.agent")}</th>
                    <th scope="col">{t("crew.state")}</th>
                    <th scope="col">{t("fieldAgents.device")}</th>
                    <th scope="col">{t("fieldAgents.lastPosition")}</th>
                    <th scope="col">{t("ops.assignment.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map((a) => (
                    <AgentRow key={a.id} agent={a} onCode={setShown} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <AddForm gouvernorat={national ? gouvernorat : null} onCode={setShown} />
        </section>
      )}
    </div>
  );
}
