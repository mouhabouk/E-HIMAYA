/**
 * One incident file across gouvernorats (phase 9 §5.2–§5.3): the lead gouvernorat, the participating ones, and the
 * command level. Participants are managed by the lead room or nationally; the lead and the command level are
 * changed nationally only. Every change carries a reason (timeline and audit).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useGouvernorats } from "../lib/hooks";
import { reasonValid } from "../lib/phase9";
import type { CommandLevel } from "../lib/phase9Types";
import { canDirectIncidents, mayManageParticipants } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { IncidentDetail } from "../lib/types";
import { InlineDialog, ReasonField } from "./Phase9Bits";

type Action =
  | { kind: "add"; code: number }
  | { kind: "remove"; code: number }
  | { kind: "lead"; code: number }
  | { kind: "level"; level: CommandLevel | null };

type Panel = "add" | "lead" | "level" | { remove: number } | null;

export function CommandLevelTag({ level }: { level: CommandLevel | undefined }) {
  const { t } = useTranslation();
  if (!level) return null;
  return <span className={`tag tag--command-${level}`}>{t(`command.level.${level}`)}</span>;
}

export function IncidentCommandPanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const id = useId();
  const [panel, setPanel] = useState<Panel>(null);
  const [code, setCode] = useState("");
  const [level, setLevel] = useState<CommandLevel | "auto">("central");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [done, setDone] = useState(false);

  const lead = incident.lead_gouvernorat_code ?? incident.gouvernorat_code;
  const participants = incident.participating_gouvernorats ?? [];
  const identity = user?.identity;
  const manage = identity ? mayManageParticipants(identity, lead) && incident.status === "open" : false;
  const direct = identity ? canDirectIncidents(identity) && incident.status === "open" : false;

  const mutation = useMutation({
    mutationFn: (a: Action) => {
      const r = reason.trim();
      switch (a.kind) {
        case "add":
          return api.addParticipant(incident.id, a.code, r);
        case "remove":
          return api.removeParticipant(incident.id, a.code, r);
        case "lead":
          return api.transferLead(incident.id, a.code, r);
        case "level":
          return api.setCommandLevel(incident.id, a.level, r);
      }
    },
    onSuccess: (updated) => {
      qc.setQueryData(queryKeys.incident(incident.id), updated);
      void qc.invalidateQueries({ queryKey: queryKeys.incidentsAll });
      setPanel(null);
      setReason("");
      setCode("");
      setTried(false);
      setDone(true);
    },
  });

  const open = (p: Panel) => {
    setPanel(p);
    setReason("");
    setCode("");
    setTried(false);
    setDone(false);
    mutation.reset();
  };

  const submit = (action: () => Action | null) => (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    const a = action();
    if (!a || !reasonValid(reason)) return;
    mutation.mutate(a);
  };

  const candidates = gouvernorats.list.filter((g) => g.code !== lead && !participants.includes(g.code));
  const picker = (label: string, list: { code: number }[]) => (
    <div className="field">
      <label htmlFor={`${id}-code`}>{label}</label>
      <select id={`${id}-code`} value={code} onChange={(e) => setCode(e.target.value)} aria-invalid={tried && !code ? true : undefined}>
        <option value="">{t("referral.choose")}</option>
        {list.map((g) => (
          <option key={g.code} value={g.code}>
            {gouvernorats.nameOf(g.code)}
          </option>
        ))}
      </select>
    </div>
  );
  const reasonField = <ReasonField label={t("command.reason")} value={reason} onChange={setReason} showError={tried} />;
  const submitButton = (label: string) => (
    <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
      {label}
    </button>
  );

  return (
    <section className="card" aria-labelledby="sec-command">
      <h2 id="sec-command">{t("command.title")}</h2>
      <dl className="fields">
        <dt>{t("command.lead")}</dt>
        <dd>{lead !== null && lead !== undefined ? gouvernorats.nameOf(lead) : t("command.noLead")}</dd>
        <dt>{t("command.participants")}</dt>
        <dd>
          {participants.length === 0 ? (
            t("common.none")
          ) : (
            <ul className="inline-list">
              {participants.map((c) => (
                <li key={c}>
                  {gouvernorats.nameOf(c)}
                  {manage && (
                    <>
                      {" "}
                      <button
                        type="button"
                        className="btn btn--small"
                        aria-label={t("command.removeLabel", { name: gouvernorats.nameOf(c) })}
                        onClick={() => open({ remove: c })}
                      >
                        {t("command.remove")}
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </dd>
        <dt>{t("command.levelLabel")}</dt>
        <dd>
          <CommandLevelTag level={incident.command_level} />
          {incident.command_level_manual && <span className="muted"> · {t("command.manual")}</span>}
          {incident.command_level_reason && (
            <span className="muted" dir="auto">
              {" "}
              · {incident.command_level_reason}
            </span>
          )}
        </dd>
      </dl>
      <p className="muted">{t(`command.levelHelp.${incident.command_level ?? "regional"}`)}</p>

      <div className="actions">
        {manage && (
          <button type="button" className="btn" onClick={() => open("add")}>
            {t("command.add")}
          </button>
        )}
        {direct && (
          <>
            <button type="button" className="btn" onClick={() => open("lead")}>
              {t("command.transfer")}
            </button>
            <button type="button" className="btn" onClick={() => open("level")}>
              {t("command.setLevel")}
            </button>
          </>
        )}
      </div>

      {panel === "add" && (
        <InlineDialog title={t("command.add")} onClose={() => setPanel(null)}>
          <form noValidate onSubmit={submit(() => (code ? { kind: "add", code: Number(code) } : null))}>
            {picker(t("command.gouvernorat"), candidates)}
            {reasonField}
            {submitButton(t("command.add"))}
          </form>
        </InlineDialog>
      )}
      {panel !== null && typeof panel === "object" && (
        <InlineDialog
          title={t("command.removeLabel", { name: gouvernorats.nameOf(panel.remove) })}
          onClose={() => setPanel(null)}
        >
          <form noValidate onSubmit={submit(() => ({ kind: "remove", code: panel.remove }))}>
            {reasonField}
            {submitButton(t("command.remove"))}
          </form>
        </InlineDialog>
      )}
      {panel === "lead" && (
        <InlineDialog title={t("command.transfer")} onClose={() => setPanel(null)}>
          <form noValidate onSubmit={submit(() => (code ? { kind: "lead", code: Number(code) } : null))}>
            <p className="muted">{t("command.transferHelp")}</p>
            {picker(t("command.newLead"), gouvernorats.list.filter((g) => g.code !== lead))}
            {reasonField}
            {submitButton(t("command.transfer"))}
          </form>
        </InlineDialog>
      )}
      {panel === "level" && (
        <InlineDialog title={t("command.setLevel")} onClose={() => setPanel(null)}>
          <form noValidate onSubmit={submit(() => ({ kind: "level", level: level === "auto" ? null : level }))}>
            <fieldset>
              <legend>{t("command.levelLabel")}</legend>
              {(["regional", "central", "auto"] as const).map((l) => (
                <label key={l} className="radio">
                  <input type="radio" name={`${id}-level`} checked={level === l} onChange={() => setLevel(l)} />{" "}
                  {l === "auto" ? t("command.auto") : t(`command.level.${l}`)}
                </label>
              ))}
            </fieldset>
            {reasonField}
            {submitButton(t("command.apply"))}
          </form>
        </InlineDialog>
      )}

      <div role="status" aria-live="polite">
        {done && !mutation.isPending && <p className="alert alert--ok">{t("command.done")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </section>
  );
}
