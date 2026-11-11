// covers: OS2 (docs/phase-os2/design-os2.md §2): the guided call-taking card in the room's intake form. The agent
// answers yes, no or unknown; the band, the flags, the suggested resources and the instructions to read follow at
// once. The server checks the answers again against the approved version.
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ANSWERS,
  askedQuestions,
  evaluate,
  type Answers,
  type CallCard,
  type CardAnswer,
  type Evaluation,
  type Reason,
} from "../lib/callCards";
import { Icon, IconTile } from "./Icon";

export function bandLabel(t: (k: string) => string, band: string): string {
  return t(`callCards.band.${band}`);
}

function ReasonLine({ reason }: { reason: Reason }) {
  const { t } = useTranslation();
  if (reason.kind === "start") return <>{t("callCards.reason.start", { band: bandLabel(t, reason.band) })}</>;
  if (reason.kind === "unknown") return <>{t("callCards.reason.unknown", { band: bandLabel(t, reason.band) })}</>;
  return (
    <>
      {reason.why}
      {reason.band && <> ← {bandLabel(t, reason.band)}</>}
    </>
  );
}

/** Beats at the compressions' rhythm so the agent counts aloud with the caller (CPR by telephone). */
function Metronome({ rate }: { rate: number }) {
  const { t } = useTranslation();
  return (
    <div className="call-card__metronome">
      <span className="call-card__beat" style={{ animationDuration: `${60 / rate}s` }} aria-hidden="true" />
      <div>
        <strong>{t("callCards.metronome", { rate })}</strong>
        <div className="muted">{t("callCards.metronomeHint")}</div>
      </div>
    </div>
  );
}

export function CallCardResult({
  card,
  result,
  read,
  onRead,
}: {
  card: CallCard;
  result: Evaluation;
  read?: string[];
  onRead?: (key: string, on: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="call-card__result" aria-live="polite">
      <div className={`call-card__band call-card__band--${result.band}`}>
        <Icon name={result.band === "critical" ? "crisisAlert" : "warning"} />
        <div>
          <div className="call-card__band-title">{t("callCards.bandTitle", { band: bandLabel(t, result.band) })}</div>
          <div className="call-card__band-hint">{t(`callCards.bandHint.${result.band}`)}</div>
        </div>
      </div>
      <div className="call-card__flags">
        {result.flags.length ? (
          result.flags.map((f) => (
            <span key={f} className="pill tone-red">
              <Icon name="warning" /> {f}
            </span>
          ))
        ) : (
          <span className="pill tone-slate">{t("callCards.noFlag")}</span>
        )}
      </div>
      <h4 className="call-card__sect">{t("callCards.why")}</h4>
      <ul className="call-card__why">
        {result.reasons.map((r, i) => (
          <li key={i}>
            <ReasonLine reason={r} />
          </li>
        ))}
      </ul>
      <h4 className="call-card__sect">{t("callCards.means")}</h4>
      <ul className="call-card__means">
        {result.means.map((m) => (
          <li key={m}>
            <IconTile name="localShipping" tone="navy" soft size="sm" />
            {m}
          </li>
        ))}
      </ul>
      {result.instructions.map((key) => {
        const ins = card.content.instructions[key];
        if (!ins) return null;
        return (
          <div key={key} className="call-card__script">
            <h4>
              <Icon name="campaign" /> {t("callCards.readToCaller")}: {ins.title}
            </h4>
            <ol>
              {ins.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
            {ins.metronome && <Metronome rate={ins.metronome} />}
            {onRead && (
              <label className="call-card__read">
                <input
                  type="checkbox"
                  checked={read?.includes(key) ?? false}
                  onChange={(e) => onRead(key, e.target.checked)}
                />
                {t("callCards.read")}
              </label>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function CallCardPanel({
  card,
  answers,
  onAnswers,
  read,
  onRead,
}: {
  card: CallCard;
  answers: Answers;
  onAnswers: (a: Answers) => void;
  read: string[];
  onRead: (read: string[]) => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const questions = askedQuestions(card.content, answers);
  const result = evaluate(card.content, answers);
  // Instructions the answers no longer offer are no longer read.
  useEffect(() => {
    const kept = read.filter((k) => result.instructions.includes(k));
    if (kept.length !== read.length) onRead(kept);
  }, [read, result.instructions, onRead]);
  const set = (q: string, a: CardAnswer) => onAnswers({ ...answers, [q]: answers[q] === a ? undefined : a });
  return (
    <section className="call-card" aria-labelledby={`${id}-h`}>
      <div className="call-card__questions">
        <div className="call-card__head">
          <h3 id={`${id}-h`}>{t("callCards.cardOf", { title: card.content.title })}</h3>
          <span className="pill tone-navy">{t("callCards.version", { version: card.version })}</span>
          {card.sim && <span className="tag tag--sim">[SIM]</span>}
          <span className="muted call-card__progress">
            {t("callCards.progress", { answered: result.answered, asked: result.asked })}
          </span>
        </div>
        {card.sim && <p className="muted call-card__sim">{t("callCards.simNote")}</p>}
        <div className="call-card__steps" aria-hidden="true">
          {questions.map((q) => (
            <i key={q.id} className={answers[q.id] ? "done" : undefined} />
          ))}
        </div>
        <ol className="call-card__list">
          {questions.map((q) => (
            <li key={q.id} className={`call-card__q${q.key ? " call-card__q--key" : ""}${q.when ? " call-card__q--follow" : ""}`}>
              <fieldset>
                <legend>
                  <span className="call-card__qtext">{q.text}</span>
                  {q.key && <span className="pill tone-red">{t("callCards.key")}</span>}
                  {q.help && <span className="muted call-card__help">{q.help}</span>}
                </legend>
                <div className="call-card__answers">
                  {ANSWERS.map((a) => (
                    <label key={a} className={`call-card__answer call-card__answer--${a}`}>
                      <input
                        type="radio"
                        name={`${id}-${q.id}`}
                        checked={answers[q.id] === a}
                        onChange={() => undefined}
                        onClick={() => set(q.id, a)}
                      />
                      <span>{t(`callCards.answer.${a}`)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </li>
          ))}
        </ol>
      </div>
      <CallCardResult
        card={card}
        result={result}
        read={read}
        onRead={(key, on) => onRead(on ? [...read, key] : read.filter((k) => k !== key))}
      />
    </section>
  );
}

/** Seconds since the form opened: how long the call has lasted so far. */
export function useCallTimer(): string {
  const [start] = useState(() => Date.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const s = Math.max(0, Math.floor((now - start) / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
