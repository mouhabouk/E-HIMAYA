import { useMutation } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { rememberSoftphone, useSoftphone, useSoftphoneState } from "../context/softphone";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { canUseTelephony } from "../lib/roles";
import type { SoftphoneCall } from "../lib/softphone";
import { CIVIL_PROTECTION_NUMBER, type CallLinkBody, type DialBody } from "../lib/telephonyTypes";
import { SimTag } from "./StreamBits";

/** Seconds since `from`, refreshed every second while shown. */
function useElapsed(from: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (from === null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [from]);
  return from === null ? 0 : Math.max(0, Math.round((now - from) / 1000));
}

function RemoteAudio({ stream, label }: { stream: MediaStream | null; label: string }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.srcObject = stream;
    if (stream) void el.play().catch(() => undefined);
  }, [stream]);
  return <audio ref={ref} autoPlay aria-label={label} />;
}

/** Copy the number to the clipboard (scenario 1: the operator calls 198 from their own phone). */
function CopyNumber({ number }: { number: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <span className="copy-number">
      <strong className="code" dir="ltr">
        {number}
      </strong>
      <button
        type="button"
        className="btn btn--small"
        onClick={() => {
          void navigator.clipboard
            .writeText(number)
            .then(() => setCopied(true))
            .catch(() => setCopied(false));
        }}
      >
        {t("phone.copyNumber")}
      </button>
      <span role="status" aria-live="polite">
        {copied && t("phone.copied")}
      </span>
    </span>
  );
}

/** Scenario 2 button when the API enables it; otherwise the scenario 1 instruction (ADR-10). */
function Transfer198({ call }: { call: SoftphoneCall }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const phone = useSoftphone();
  const state = useSoftphoneState();
  const [confirming, setConfirming] = useState(false);
  const transfer = useMutation({
    mutationFn: (id: string) => api.transferTo198(id),
    onSuccess: (row) => {
      phone?.noteCallRow(row);
      setConfirming(false);
    },
    onError: () => setConfirming(false),
  });
  if (!state.transfer198) {
    return (
      <div className="phone-198 alert alert--info">
        <p>{t("phone.scenario1")}</p>
        <CopyNumber number={CIVIL_PROTECTION_NUMBER} />
      </div>
    );
  }
  const id = call.apiCallId;
  return (
    <div className="phone-198">
      {confirming ? (
        <>
          <p className="alert alert--warn" role="alert">
            {t("phone.transferConfirmText")}
          </p>
          <div className="actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={!id || transfer.isPending}
              onClick={() => id && transfer.mutate(id)}
            >
              {transfer.isPending ? t("ops.working") : t("phone.transferConfirm")}
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)}>
              {t("common.cancel")}
            </button>
          </div>
        </>
      ) : (
        <button type="button" className="btn" disabled={!id} onClick={() => setConfirming(true)}>
          {t("phone.transfer198")}
        </button>
      )}
      {transfer.isSuccess && <p className="alert alert--ok">{t("phone.transferred")}</p>}
      {transfer.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(transfer.error))}
        </p>
      )}
    </div>
  );
}

type LinkKind = "tracking_code" | "report_id" | "incident_id";

/** Link the call to a report (tracking code or id) or an incident; the API stores it on the call row. */
function CallLinkForm({ call }: { call: SoftphoneCall }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const phone = useSoftphone();
  const ids = { kind: useId(), value: useId() };
  const [kind, setKind] = useState<LinkKind>("tracking_code");
  const [value, setValue] = useState("");
  const link = useMutation({
    mutationFn: ({ id, body }: { id: string; body: CallLinkBody }) => api.linkCall(id, body),
    onSuccess: (row) => {
      phone?.noteCallRow(row);
      setValue("");
    },
  });
  const row = call.apiCall;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const v = value.trim();
    if (!v || !call.apiCallId) return;
    const body: CallLinkBody =
      kind === "tracking_code"
        ? { tracking_code: v.toUpperCase() }
        : kind === "report_id"
          ? { report_id: v }
          : { incident_id: v };
    link.mutate({ id: call.apiCallId, body });
  };
  return (
    <form className="phone-link" onSubmit={submit} aria-label={t("phone.link.title")}>
      {(row?.report_id ?? row?.incident_id) && (
        <p className="phone-link__current">
          {t("phone.link.linked")}{" "}
          {row.report_id && (
            <Link to={`/reports/${encodeURIComponent(row.report_id)}`} dir="ltr" className="code">
              {row.tracking_code ?? t("phone.link.report")}
            </Link>
          )}
          {row.incident_id && (
            <>
              {" "}
              <Link to={`/incidents/${encodeURIComponent(row.incident_id)}`}>{t("phone.link.incident")}</Link>
            </>
          )}
        </p>
      )}
      <div className="phone-link__row">
        <div className="field">
          <label htmlFor={ids.kind}>{t("phone.link.kind")}</label>
          <select id={ids.kind} value={kind} onChange={(e) => setKind(e.target.value as LinkKind)}>
            {(["tracking_code", "report_id", "incident_id"] as const).map((k) => (
              <option key={k} value={k}>
                {t(`phone.link.kinds.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.value}>{t("phone.link.value")}</label>
          <input id={ids.value} dir="ltr" value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" />
        </div>
      </div>
      <button type="submit" className="btn btn--small" disabled={!value.trim() || !call.apiCallId || link.isPending}>
        {link.isPending ? t("ops.working") : t("phone.link.submit")}
      </button>
      {!call.apiCallId && <p className="muted">{t("phone.link.waitingId")}</p>}
      <div role="status" aria-live="polite">
        {link.isSuccess && <p className="alert alert--ok">{t("phone.link.done")}</p>}
      </div>
      {link.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(link.error))}
        </p>
      )}
    </form>
  );
}

function callerLabel(t: (k: string) => string, call: SoftphoneCall): string {
  if (call.purpose === "conference") return t("phone.conference");
  return call.apiCall?.caller_number ?? (call.remote || t("phone.unknownCaller"));
}

function IncomingCall({ call }: { call: SoftphoneCall }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const phone = useSoftphone();
  const waited = useElapsed(call.apiCall?.started_at ? Date.parse(call.apiCall.started_at) : call.startedAt);
  return (
    <section className="phone-call phone-call--ringing" role="alert" aria-label={t("phone.incoming")}>
      <h3>{t("phone.incoming")}</h3>
      <p className="phone-call__who" dir="ltr">
        {callerLabel(t, call)}
      </p>
      <dl className="fields fields--compact">
        <dt>{t("phone.queue")}</dt>
        <dd>{call.queue?.name ?? call.apiCall?.queue ?? t("phone.defaultQueue")}</dd>
        {call.queue?.waiting !== null && call.queue?.waiting !== undefined && (
          <>
            <dt>{t("phone.waiting")}</dt>
            <dd>{fmt.number(call.queue.waiting)}</dd>
          </>
        )}
        <dt>{t("phone.waited")}</dt>
        <dd>{fmt.duration(waited)}</dd>
        {call.apiCall?.tracking_code && (
          <>
            <dt>{t("phone.link.report")}</dt>
            <dd className="code" dir="ltr">
              {call.apiCall.tracking_code}
            </dd>
          </>
        )}
      </dl>
      <div className="actions">
        <button type="button" className="btn btn--primary btn--call" onClick={() => phone?.answer(call.key)}>
          {t("phone.answer")}
        </button>
        <button type="button" className="btn" onClick={() => phone?.hangup(call.key)}>
          {t("phone.decline")}
        </button>
      </div>
    </section>
  );
}

function ActiveCall({ call }: { call: SoftphoneCall }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const phone = useSoftphone();
  const { user } = useAuth();
  const talking = useElapsed(call.answeredAt);
  const telephony = canUseTelephony(user?.identity.roles ?? []);
  const ended = call.phase === "ended";
  const title =
    call.purpose === "conference"
      ? t("phone.inConference", { room: call.conferenceRoom ?? "" })
      : call.phase === "dialing"
        ? t("phone.dialing")
        : ended
          ? t("phone.ended")
          : t("phone.inCall");
  return (
    <section className={`phone-call${ended ? " phone-call--ended" : ""}`} aria-label={title}>
      <h3>{title}</h3>
      <p className="phone-call__who" dir="ltr">
        {callerLabel(t, call)}
      </p>
      <p className="muted" role="timer" aria-live="off">
        {call.answeredAt ? fmt.duration(talking) : t("phone.connecting")}
        {call.onHold && ` · ${t("phone.onHold")}`}
        {call.muted && ` · ${t("phone.muted")}`}
      </p>
      <RemoteAudio stream={call.remoteStream} label={t("phone.remoteAudio")} />
      {!ended && (
        <div className="actions phone-controls">
          <button
            type="button"
            className="btn"
            aria-pressed={call.onHold}
            onClick={() => phone?.hold(call.key, !call.onHold)}
          >
            {call.onHold ? t("phone.resume") : t("phone.hold")}
          </button>
          <button
            type="button"
            className="btn"
            aria-pressed={call.muted}
            onClick={() => phone?.mute(call.key, !call.muted)}
          >
            {call.muted ? t("phone.unmute") : t("phone.mute")}
          </button>
          <button type="button" className="btn btn--danger" onClick={() => phone?.hangup(call.key)}>
            {t("phone.hangup")}
          </button>
        </div>
      )}
      {!ended && telephony && call.purpose !== "conference" && (
        <>
          <CallLinkForm call={call} />
          {call.purpose === "queue" && <Transfer198 call={call} />}
        </>
      )}
    </section>
  );
}

/**
 * Docked softphone (phase 7 §4): on/off, incoming queue calls with their queue info, the call in progress with
 * hold / mute / hang-up, linking to a report or incident and the 198 transfer (scenario 2) or instruction (1).
 */
export function SoftphoneDock() {
  const { t } = useTranslation();
  const phone = useSoftphone();
  const state = useSoftphoneState();
  const [open, setOpen] = useState(false);
  const ringing = state.calls.filter((c) => c.phase === "ringing" && c.direction === "incoming");
  const others = state.calls.filter((c) => !ringing.includes(c));
  const expanded = open || state.calls.length > 0;
  if (!phone) return null;
  const on = state.status !== "off";
  return (
    <aside className={`softphone${expanded ? " softphone--open" : ""}`} aria-label={t("phone.title")}>
      <div className="softphone__bar">
        <button
          type="button"
          className="btn btn--ghost softphone__toggle"
          aria-expanded={expanded}
          onClick={() => setOpen(!open)}
        >
          <span className={`softphone__dot softphone__dot--${state.status}`} aria-hidden="true" />
          {t("phone.title")} · <span role="status">{t(`phone.status.${state.status}`)}</span>
          {ringing.length > 0 && (
            <span className="tag tag--new">{t("phone.ringingCount", { count: ringing.length })}</span>
          )}
        </button>
        {state.simulated && <SimTag />}
      </div>
      {expanded && (
        <div className="softphone__body">
          <div className="actions">
            {on ? (
              <button
                type="button"
                className="btn btn--small"
                onClick={() => {
                  rememberSoftphone(false);
                  phone.disconnect();
                }}
              >
                {t("phone.disconnect")}
              </button>
            ) : (
              <button
                type="button"
                className="btn btn--small btn--primary"
                onClick={() => {
                  rememberSoftphone(true);
                  void phone.connect();
                }}
              >
                {t("phone.connect")}
              </button>
            )}
          </div>
          {state.error && (
            <p className="alert alert--error" role="alert">
              {state.error === "registration_failed" || state.error === "microphone"
                ? t(`phone.error.${state.error}`)
                : t(`errors.${state.error}`)}
            </p>
          )}
          {ringing.map((c) => (
            <IncomingCall key={c.key} call={c} />
          ))}
          {others.map((c) => (
            <ActiveCall key={c.key} call={c} />
          ))}
          {state.calls.length === 0 && state.status === "ready" && <p className="muted">{t("phone.idle")}</p>}
        </div>
      )}
    </aside>
  );
}

/** "Call" button of a report, volunteer, map point or responder: dials out through the operator's softphone. */
export function CallButton({ body, label, className }: { body: DialBody; label?: string; className?: string }) {
  const { t } = useTranslation();
  const phone = useSoftphone();
  const { user } = useAuth();
  const dial = useMutation({
    mutationFn: (b: DialBody) => (phone ? phone.dial(b) : Promise.reject(new Error("no softphone"))),
  });
  if (!phone || !canUseTelephony(user?.identity.roles ?? [])) return null;
  return (
    <span className="call-button">
      <button
        type="button"
        className={className ?? "btn btn--small btn--call"}
        disabled={dial.isPending}
        onClick={() => dial.mutate(body)}
      >
        {dial.isPending ? t("phone.dialing") : (label ?? t("phone.call"))}
      </button>
      <span role="status" aria-live="polite">
        {dial.isSuccess && <span className="muted">{t("phone.dialStarted")}</span>}
      </span>
      {dial.isError && (
        <span className="field__error" role="alert">
          {dial.error instanceof Error && dial.error.message === "softphone_not_registered"
            ? t("errors.softphone_not_registered")
            : t(errorMessageKey(dial.error))}
        </span>
      )}
    </span>
  );
}
