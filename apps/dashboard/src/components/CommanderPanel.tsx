/**
 * The commander's assistant on the incident page (AI5a, docs/phase-ai5/design-ai5.md §3–§5): numbered proposals
 * with their rationale and what commanders did with the same proposal elsewhere; the commander adopts, adopts
 * modified (some actions, a note) or rejects with a ready reason; a typed order becomes a card the same way, and a
 * question is answered from cited sources. AI-01: adopting executes nothing — the card's buttons open the usual
 * flows (assignment, alert form, call, route) where the usual confirmation applies. Switched off in the AI settings,
 * the classic recommendations panel shows instead.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useServices } from "../context/services";
import { isApiError } from "../lib/api";
import {
  REJECT_REASONS,
  type CommandCard,
  type CommandReading,
  type CommandTextResult,
  type DecideBody,
  type RejectReason,
  type RouteProfile,
} from "../lib/decisionTypes";
import { bilingual } from "../lib/forecast";
import { useFormat, useLanguage } from "../lib/hooks";
import { p7Keys } from "../lib/phase7Api";
import type { IncidentDetail } from "../lib/types";
import { ErrorBox, Loading } from "./Feedback";
import { Icon } from "./Icon";
import {
  AdvisoryNote,
  Inputs,
  MutationError,
  RecommendationActions,
  RecommendationsPanel,
  sourceHref,
} from "./IncidentDecision";
import { SimulationBand } from "./StreamBits";

type OnAssign = (resourceId: string | null, order: string | null) => void;
type OnRoute = (from: { lat: number; lon: number }, to: { lat: number; lon: number }, profile: RouteProfile) => void;

/** The board query, shared by the page (to know whether the assistant is on) and the panel. */
export function useCommandBoard(incidentId: string) {
  const { api } = useServices();
  return useQuery({
    queryKey: p7Keys.commandBoard(incidentId),
    queryFn: ({ signal }) => api.commandBoard(incidentId, signal),
    staleTime: 60_000,
    retry: (count, error) => !(isApiError(error) && error.code === "commander_off") && count < 2,
  });
}

export function isCommanderOff(error: unknown): boolean {
  return isApiError(error) && error.code === "commander_off";
}

/** Once the API said the assistant is off, it stays off for this page: a refetch must not blank the panels. */
export function useCommanderOff(board: ReturnType<typeof useCommandBoard>): boolean {
  const [off, setOff] = useState(false);
  if (!off && board.isError && isCommanderOff(board.error)) setOff(true);
  return off;
}

/** "Read as: send 2 × water tanker" — the reading of an order, so a misreading is seen before adopting. */
function ReadingLine({ reading }: { reading: CommandReading }) {
  const { t } = useTranslation();
  const parts = [t(`commander.action.${reading.action ?? "note"}`)];
  if (reading.resource_kind) {
    const kind = t(`resources.kind.${reading.resource_kind}`, {
      defaultValue: reading.resource_kind,
    });
    parts.push(reading.count ? `${reading.count} × ${kind}` : kind);
  }
  if (reading.level) parts.push(t(`levels.name.${reading.level}`, { defaultValue: reading.level }));
  return (
    <p className="commander__reading">
      <strong>{t("commander.readAs")}</strong> {parts.join(" · ")}{" "}
      <span className="muted">({t(`commander.reader.${reading.reader}`)})</span>
    </p>
  );
}

function TrackLine({ card }: { card: CommandCard }) {
  const { t } = useTranslation();
  const { track } = card;
  if (track.decided === 0) return <p className="muted commander__track">{t("commander.track.none")}</p>;
  return (
    <p className="commander__track">
      {t("commander.track.line", {
        adopted: track.adopted + track.modified,
        decided: track.decided,
        modified: track.modified,
        rejected: track.rejected,
      })}
      {track.top_reason && ` ${t("commander.track.reason", { reason: t(`commander.reasons.${track.top_reason}`) })}`}
    </p>
  );
}

function DecisionForm({ card, onDone }: { card: CommandCard; onDone: (decided: CommandCard) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const base = useId();
  const [mode, setMode] = useState<"modify" | "reject" | null>(null);
  const [kept, setKept] = useState<number[]>(card.actions.map((_, i) => i));
  const [reason, setReason] = useState<RejectReason | null>(null);
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: (body: DecideBody) => api.decideCommand(card.id, body),
    onSuccess: onDone,
  });
  const trimmed = note.trim();
  const unchanged = kept.length === card.actions.length && trimmed === "";
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (mode === "reject") {
      if (!reason || (reason === "other" && trimmed === "")) return;
      decide.mutate({
        verdict: "reject",
        reason_code: reason,
        ...(trimmed ? { note: trimmed } : {}),
      });
    } else if (mode === "modify") {
      if (unchanged) return;
      decide.mutate({
        verdict: "modify",
        kept_actions: kept,
        ...(trimmed ? { note: trimmed } : {}),
      });
    }
  };
  return (
    <div className="commander__decide">
      <div className="actions">
        <button
          type="button"
          className="btn btn--primary btn--small"
          disabled={decide.isPending}
          onClick={() => decide.mutate({ verdict: "adopt" })}
        >
          {t("commander.adopt")}
        </button>
        <button
          type="button"
          className="btn btn--small"
          aria-pressed={mode === "modify"}
          onClick={() => setMode(mode === "modify" ? null : "modify")}
        >
          {t("commander.modify")}
        </button>
        <button
          type="button"
          className="btn btn--small btn--danger"
          aria-pressed={mode === "reject"}
          onClick={() => setMode(mode === "reject" ? null : "reject")}
        >
          {t("commander.reject")}
        </button>
      </div>
      {mode && (
        <form className="ops-form" onSubmit={submit} noValidate>
          {mode === "modify" && card.actions.length > 0 && (
            <fieldset className="chips">
              <legend>{t("commander.keep")}</legend>
              {card.actions.map((a, i) => (
                <label key={i} className="chip-toggle">
                  <input
                    type="checkbox"
                    checked={kept.includes(i)}
                    onChange={(e) =>
                      setKept(e.target.checked ? [...kept, i].sort((x, y) => x - y) : kept.filter((k) => k !== i))
                    }
                  />
                  <span dir="auto">{bilingual(a.label ?? null, lang) || t(`decision.action.${a.type}`)}</span>
                </label>
              ))}
            </fieldset>
          )}
          {mode === "reject" && (
            <fieldset className="chips">
              <legend>{t("commander.reason")}</legend>
              {REJECT_REASONS.map((r) => (
                <label key={r} className="chip-toggle">
                  <input
                    type="radio"
                    name={`${base}-reason`}
                    required
                    checked={reason === r}
                    onChange={() => setReason(r)}
                  />
                  <span>{t(`commander.reasons.${r}`)}</span>
                </label>
              ))}
            </fieldset>
          )}
          {(mode === "modify" || reason !== null) && (
            <div className="field">
              <label htmlFor={`${base}-note`}>
                {mode === "reject" && reason === "other" ? t("commander.noteRequired") : t("commander.note")}
              </label>
              <textarea
                id={`${base}-note`}
                rows={2}
                maxLength={500}
                dir="auto"
                aria-required={mode === "reject" && reason === "other" ? true : undefined}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          )}
          {mode === "modify" && unchanged && <p className="muted">{t("commander.nothingChanged")}</p>}
          <div className="actions">
            <button
              type="submit"
              className="btn btn--primary btn--small"
              disabled={
                decide.isPending || (mode === "reject" ? !reason || (reason === "other" && trimmed === "") : unchanged)
              }
            >
              {mode === "reject" ? t("commander.confirmReject") : t("commander.confirmModify")}
            </button>
          </div>
        </form>
      )}
      <MutationError error={decide.error} />
    </div>
  );
}

function ProposalCard({
  card,
  number,
  onAssign,
  onRoute,
  onDecided,
}: {
  card: CommandCard;
  number: number;
  onAssign: OnAssign;
  onRoute: OnRoute;
  /** Left out for whoever sees the board without deciding (AI5b). */
  onDecided?: (decided: CommandCard) => void;
}) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const id = useId();
  const reading = card.inputs.reading as CommandReading | undefined;
  return (
    <li className="commander__card" aria-labelledby={id}>
      <div className="recommendation__head">
        <span className="commander__no" aria-hidden="true">
          {number}
        </span>
        <span className="tag">{t(`commander.kind.${card.kind}`)}</span>
        {card.origin === "order" && <span className="tag tag--order">{t("commander.yourOrder")}</span>}
        <h3 id={id} dir="auto">
          {bilingual(card.title, lang)}
        </h3>
        <span className={`chip chip--confidence-${card.confidence}`}>
          {t(`decision.confidence.${card.confidence}`)}
        </span>
      </div>
      <p className="assistant__label">
        <span className="tag tag--advisory">{t("commander.aiLabel")}</span>{" "}
        {card.model && <span className="muted code">{card.model}</span>}
      </p>
      {card.command_text && (
        <blockquote className="commander__said" dir="auto">
          {card.command_text}
        </blockquote>
      )}
      {reading && <ReadingLine reading={reading} />}
      <p className="recommendation__why" dir="auto">
        <strong>{t("decision.rationale")}</strong> {bilingual(card.rationale, lang)}
      </p>
      <TrackLine card={card} />
      <Inputs inputs={card.inputs} label={t("decision.inputs")} />
      <p className="muted">{t("commander.opensFlows")}</p>
      <RecommendationActions actions={card.actions} onAssign={onAssign} onRoute={onRoute} />
      {onDecided && <DecisionForm card={card} onDone={onDecided} />}
    </li>
  );
}

function DecidedItem({ card, onAssign, onRoute }: { card: CommandCard; onAssign: OnAssign; onRoute: OnRoute }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const fmt = useFormat();
  const kept = card.kept_actions ?? [];
  const actions = card.status === "rejected" ? [] : card.actions.filter((_, i) => kept.includes(i));
  return (
    <li className="commander__decided">
      <span className={`pill pill--decision-${card.status}`}>{t(`commander.status.${card.status}`)}</span>{" "}
      <strong dir="auto">{bilingual(card.title, lang)}</strong>
      <span className="muted">
        {" · "}
        {card.decided_by_name ?? "—"}
        {card.decided_at && (
          <>
            {" · "}
            <time dateTime={card.decided_at}>{fmt.dateTime(card.decided_at)}</time>
          </>
        )}
      </span>
      {card.reason_code && <p className="muted">{t(`commander.reasons.${card.reason_code}`)}</p>}
      {card.note && (
        <p dir="auto" className="muted">
          {card.note}
        </p>
      )}
      <RecommendationActions actions={actions} onAssign={onAssign} onRoute={onRoute} />
    </li>
  );
}

function Answer({ result }: { result: CommandTextResult }) {
  const { t } = useTranslation();
  const answer = result.answer;
  if (!answer) return null;
  return (
    <article className="assistant__turn" aria-live="polite">
      <p className="assistant__label">
        <span className="tag tag--advisory">{t("decision.advisory")}</span>{" "}
        <span className="muted code">{answer.model}</span>
      </p>
      <p dir="auto" className="assistant__text">
        {answer.answer}
      </p>
      {answer.sources.length > 0 && (
        <ol className="assistant__sources">
          {answer.sources.map((s) => {
            const href = sourceHref(s);
            return (
              <li key={`${s.kind}-${s.id}`}>
                <span className="tag">{t(`assistant.kind.${s.kind}`)}</span>{" "}
                {href ? (
                  <Link to={href} dir="auto">
                    {s.title}
                  </Link>
                ) : (
                  <strong dir="auto">{s.title}</strong>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </article>
  );
}

/** The longest voice message, in seconds (the API refuses longer ones). */
export const VOICE_MAX_S = 60;

function canRecord(): boolean {
  return typeof MediaRecorder !== "undefined" && typeof navigator !== "undefined" && !!navigator.mediaDevices;
}

/**
 * AI5b: the microphone of the command box. One press starts, a second press stops (or the minute does); the recording
 * is transcribed locally and its text put in the box to be corrected. Nothing is sent from here.
 */
function VoiceButton({
  incident,
  disabled,
  onText,
}: {
  incident: IncidentDetail;
  disabled: boolean;
  onText: (text: string, voiceId: string) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [recording, setRecording] = useState(false);
  const [refused, setRefused] = useState(false);
  const transcribe = useMutation({
    mutationFn: (audio: Blob) => api.commandVoice(incident.id, audio, lang),
    onSuccess: (result) => onText(result.text, result.voice_id),
  });
  const stopTimer = () => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
  };
  useEffect(
    () => () => {
      stopTimer();
      recorder.current?.stream.getTracks().forEach((track) => track.stop());
    },
    [],
  );
  const stop = () => {
    stopTimer();
    if (recorder.current?.state === "recording") recorder.current.stop();
  };
  // The minute is up: the recording stops as if pressed.
  useEffect(() => {
    if (!recording || seconds < VOICE_MAX_S) return;
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, [recording, seconds]);
  const start = async () => {
    setRefused(false);
    transcribe.reset();
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setRefused(true);
      return;
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    rec.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      recorder.current = null;
      setRecording(false);
      setSeconds(0);
      const audio = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (audio.size > 0) transcribe.mutate(audio);
    };
    recorder.current = rec;
    rec.start();
    setRecording(true);
    setSeconds(0);
    timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
  };
  if (!canRecord()) return null;
  return (
    <>
      <button
        type="button"
        className={`btn ${recording ? "btn--danger" : ""}`}
        aria-pressed={recording}
        disabled={disabled || transcribe.isPending}
        onClick={() => (recording ? stop() : void start())}
      >
        <Icon name={recording ? "stop" : "mic"} size={18} />{" "}
        {recording
          ? t("commander.voice.stop", { seconds: VOICE_MAX_S - seconds })
          : transcribe.isPending
            ? t("commander.voice.transcribing")
            : t("commander.voice.record")}
      </button>
      {refused && (
        <p className="alert alert--warn" role="alert">
          {t("commander.voice.refused")}
        </p>
      )}
      <MutationError error={transcribe.error} />
    </>
  );
}

function CommandBox({ incident, onCard }: { incident: IncidentDetail; onCard: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const base = useId();
  const [text, setText] = useState("");
  // The voice message the text came from: sent with it, so the correction is measured and learnt from (AI5b).
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [last, setLast] = useState<CommandTextResult | null>(null);
  const send = useMutation({
    mutationFn: (value: string) => api.commandText(incident.id, value, lang, voiceId),
    onSuccess: (result) => {
      setLast(result);
      setText("");
      setVoiceId(null);
      if (result.card) onCard();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (value.length >= 3) send.mutate(value);
  };
  const unavailable = isApiError(send.error) && send.error.code === "assistant_unavailable";
  return (
    <form className="ops-form commander__box" onSubmit={submit}>
      <div className="field">
        <label htmlFor={`${base}-text`}>{t("commander.textLabel")}</label>
        <textarea
          id={`${base}-text`}
          rows={2}
          maxLength={1000}
          dir="auto"
          placeholder={t("commander.textHint")}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      {voiceId && <p className="muted">{t("commander.voice.correct")}</p>}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={send.isPending || text.trim().length < 3}>
          {send.isPending ? t("assistant.thinking") : t("commander.send")}
        </button>
        <VoiceButton
          incident={incident}
          disabled={send.isPending}
          onText={(heard, id) => {
            setText(heard);
            setVoiceId(id);
            setLast(null);
          }}
        />
      </div>
      {unavailable ? (
        <p className="alert alert--warn" role="alert">
          {t("errors.assistant_unavailable")}
        </p>
      ) : (
        <MutationError error={send.error} />
      )}
      <div role="status" aria-live="polite">
        {last?.fallback && <p className="alert alert--warn">{t("commander.fallback")}</p>}
        {last?.card && <p className="alert alert--ok">{t("commander.cardAdded")}</p>}
      </div>
      {last?.answer && <Answer result={last} />}
    </form>
  );
}

export function CommanderPanel({
  incident,
  onAssign,
  onRoute,
}: {
  incident: IncidentDetail;
  onAssign: OnAssign;
  onRoute: OnRoute;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const qc = useQueryClient();
  const base = useId();
  const board = useCommandBoard(incident.id);
  const off = useCommanderOff(board);
  if (off) {
    return <RecommendationsPanel incident={incident} onAssign={onAssign} onRoute={onRoute} />;
  }
  const refresh = () => void qc.invalidateQueries({ queryKey: p7Keys.commandBoard(incident.id) });
  const data = board.data;
  return (
    <section className="card commander-panel" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("commander.title")}</h2>
      <AdvisoryNote text={t("commander.advisory")} />
      {board.data?.can_decide === false ? (
        <p className="muted">{t("commander.readOnly")}</p>
      ) : (
        <CommandBox incident={incident} onCard={refresh} />
      )}
      {board.isPending && <Loading />}
      {board.isError && <ErrorBox error={board.error} onRetry={() => void board.refetch()} />}
      {data && (
        <>
          {data.simulated && <SimulationBand note={t("decision.simBand")} />}
          <p className="muted">
            {t("decision.generated", { time: fmt.dateTime(data.generated_at) })}{" "}
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={board.isFetching}
              onClick={() => void board.refetch()}
            >
              {board.isFetching ? t("common.loading") : t("decision.refresh")}
            </button>
          </p>
          {data.proposals.length === 0 ? (
            <p className="muted">{t("decision.none")}</p>
          ) : (
            <ol className="commander__list" aria-label={t("commander.proposals")}>
              {data.proposals.map((card, i) => (
                <ProposalCard
                  key={card.id}
                  card={card}
                  number={i + 1}
                  onAssign={onAssign}
                  onRoute={onRoute}
                  onDecided={data.can_decide === false ? undefined : refresh}
                />
              ))}
            </ol>
          )}
          {data.decided.length > 0 && (
            <>
              <h3>{t("commander.decided")}</h3>
              <ul className="commander__history">
                {data.decided.map((card) => (
                  <DecidedItem key={card.id} card={card} onAssign={onAssign} onRoute={onRoute} />
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
