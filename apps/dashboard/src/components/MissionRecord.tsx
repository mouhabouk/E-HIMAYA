import { useMutation } from "@tanstack/react-query";
import { useId, useMemo, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import {
  CONSUMABLES,
  EDITABLE_STEPS,
  INDICATORS,
  REQUIRED_ONCE_SET,
  anchorOf,
  clockOf,
  correctedSteps,
  dateForClock,
  dayOffset,
  indicators,
  maskClock,
  parseClock,
  recordBody,
  recordErrors,
  shiftDays,
  shiftSeconds,
  timesOf,
  type EditableStep,
  type RecordError,
  type RecordTimes,
  type TimeSource,
  type TimeSuggestion,
} from "../lib/missionRecord";
import type { Assignment } from "../lib/opsTypes";
import { Stepper } from "./Stepper";

/** Ready reasons for correcting a time the team gave (design-system.md "less typing"); «other» opens the text. */
const REASONS = ["late_press", "early_press", "no_network", "radio_log", "other"] as const;
type Reason = (typeof REASONS)[number];

/**
 * The durations of a mission, each from its two times (phase S2): what the SNACR indicators are made of.
 * Shown under the assignment and on top of the editor.
 */
export function MissionIndicators({ assignment, calledAt }: { assignment: Assignment; calledAt?: string | null }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const values = indicators(timesOf(assignmentTimes(assignment)), calledAt ? new Date(calledAt) : null);
  const shown = INDICATORS.filter((i) => values[i.key] !== undefined);
  const warnings = assignment.record_warnings ?? [];
  if (shown.length === 0 && warnings.length === 0) return null;
  return (
    <>
      {shown.length > 0 && (
        <ul className="record-indicators" aria-label={t("record.indicators")}>
          {shown.map((i) => (
            <li key={i.key}>
              <span className="record-indicators__label">{t(`record.indicator.${i.key}`)}</span>
              <strong>{fmt.duration(values[i.key] ?? 0)}</strong>
            </li>
          ))}
        </ul>
      )}
      <RecordWarnings warnings={warnings} />
    </>
  );
}

/** Times that hold but are not credible (phase S2, rules on the server): to check, never blocking. */
export function RecordWarnings({ warnings }: { warnings: readonly string[] }) {
  const { t } = useTranslation();
  if (warnings.length === 0) return null;
  return (
    <ul className="record-warnings" aria-label={t("record.warningsTitle")}>
      {warnings.map((w) => (
        <li key={w} className="record-pill record-pill--warning">
          {t(`record.warning.${w}`, { defaultValue: w })}
        </li>
      ))}
    </ul>
  );
}

function assignmentTimes(a: Assignment) {
  return {
    created_at: a.created_at,
    en_route_at: a.en_route_at,
    on_scene_at: a.on_scene_at,
    left_scene_at: a.left_scene_at ?? null,
    at_hospital_at: a.at_hospital_at ?? null,
    available_at: a.available_at ?? null,
    back_at_unit_at: a.back_at_unit_at ?? null,
  };
}

interface TimeFieldProps {
  step: EditableStep;
  value: Date | null;
  anchor: Date | null;
  error?: RecordError;
  source?: TimeSource;
  changed: boolean;
  clearable: boolean;
  disabled: boolean;
  onChange: (value: Date | null) => void;
}

/**
 * One time of the mission: typed as digits (the colons come by themselves, seconds optional), stepped with the arrow
 * keys (Shift: ten minutes) or the − and + buttons, or set to now. The date follows the time before it and crosses
 * midnight by itself; the day buttons move it when a mission lasts longer.
 */
function TimeField({ step, value, anchor, error, source, changed, clearable, disabled, onChange }: TimeFieldProps) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const [text, setText] = useState(value ? clockOf(value) : "");
  const [typing, setTyping] = useState(false);
  const shown = typing ? text : value ? clockOf(value) : "";
  const commit = (raw: string) => {
    setTyping(false);
    if (!raw.trim()) {
      if (clearable) onChange(null);
      return;
    }
    const seconds = parseClock(raw);
    if (seconds !== null) onChange(dateForClock(seconds, anchor, new Date()));
  };
  const nudge = (seconds: number) => {
    const base = value ?? anchor ?? new Date();
    onChange(shiftSeconds(base, seconds));
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      nudge((e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 600 : 60));
    } else if (e.key === "Enter") {
      e.preventDefault();
      commit(text);
    } else if (e.key === "Escape") {
      setTyping(false);
    }
  };
  const days = value && anchor ? dayOffset(value, anchor) : 0;
  const invalidText = typing && text.length > 0 && parseClock(text) === null;
  return (
    <div className={`record-step${error ? " record-step--error" : ""}${changed ? " record-step--changed" : ""}`}>
      <div className="record-step__head">
        <label htmlFor={id} className="record-step__label">
          {t(`record.step.${step}`)}
        </label>
        {changed ? (
          <span className="record-pill record-pill--changed">{t("record.source.changed")}</span>
        ) : (
          value &&
          source && <span className={`record-pill record-pill--${source}`}>{t(`record.source.${source}`)}</span>
        )}
      </div>
      <div className="record-step__controls">
        <button
          type="button"
          className="btn btn--small record-step__nudge"
          disabled={disabled}
          onClick={() => nudge(-60)}
          aria-label={t("record.minus", { step: t(`record.step.${step}`) })}
        >
          −
        </button>
        <input
          id={id}
          className="record-step__clock"
          dir="ltr"
          inputMode="numeric"
          autoComplete="off"
          placeholder={t("record.clockPlaceholder")}
          value={shown}
          disabled={disabled}
          aria-invalid={Boolean(error) || invalidText}
          aria-describedby={`${hintId}${error ? ` ${errorId}` : ""}`}
          onFocus={() => {
            setText(value ? clockOf(value) : "");
            setTyping(true);
          }}
          onChange={(e) => {
            setTyping(true);
            setText(maskClock(e.target.value));
          }}
          onBlur={() => commit(text)}
          onKeyDown={onKey}
        />
        <button
          type="button"
          className="btn btn--small record-step__nudge"
          disabled={disabled}
          onClick={() => nudge(60)}
          aria-label={t("record.plus", { step: t(`record.step.${step}`) })}
        >
          +
        </button>
        <button
          type="button"
          className="btn btn--small"
          disabled={disabled}
          onClick={() => onChange(new Date(Math.floor(Date.now() / 1000) * 1000))}
        >
          {t("record.now")}
        </button>
        {value && (
          <span className="record-step__day">
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={disabled}
              onClick={() => onChange(shiftDays(value, -1))}
              aria-label={t("record.dayBefore")}
            >
              ‹
            </button>
            <span>
              {days === 0
                ? fmt.date(value.toISOString())
                : t("record.dayAfter", {
                    count: days,
                    date: fmt.date(value.toISOString()),
                  })}
            </span>
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={disabled}
              onClick={() => onChange(shiftDays(value, 1))}
              aria-label={t("record.dayNext")}
            >
              ›
            </button>
          </span>
        )}
        {clearable && value && (
          <button
            type="button"
            className="btn btn--small btn--ghost"
            disabled={disabled}
            onClick={() => onChange(null)}
          >
            {t("record.clear")}
          </button>
        )}
      </div>
      <p id={hintId} className="record-step__hint muted">
        {value && anchor && value.getTime() >= anchor.getTime()
          ? t("record.after", {
              duration: fmt.duration((value.getTime() - anchor.getTime()) / 1000),
            })
          : t("record.hint")}
      </p>
      {(error || invalidText) && (
        <p id={errorId} className="field__error" role="alert">
          {t(invalidText ? "record.error.clock" : `record.error.${error}`)}
        </p>
      )}
    </div>
  );
}

/**
 * The room's editor of a mission's record (phase S2): the six times in order, each checked as it is typed against
 * the one before, the crew and the resources used. A time the team gave keeps its source until the room changes it,
 * and then needs a reason. Saved in one write; the server checks the same rules.
 */
/**
 * Times read from what was written about the mission (phase S2, design-s2 §6): the room's notes, the team's text notes
 * and a radio log pasted here. Each one is applied to its field only when the operator presses it.
 */
function TimeSuggestions({
  assignmentId,
  times,
  disabled,
  onApply,
}: {
  assignmentId: string;
  times: RecordTimes;
  disabled: boolean;
  onApply: (s: TimeSuggestion) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const id = useId();
  const [text, setText] = useState("");
  const read = useMutation({ mutationFn: () => api.suggestMissionTimes(assignmentId, text) });
  const open = (read.data ?? []).filter((s) => times[s.step]?.getTime() !== new Date(s.at).getTime());
  return (
    <details className="record-suggest">
      <summary>{t("record.suggest.title")}</summary>
      <p className="muted">{t("record.suggest.intro")}</p>
      <div className="field">
        <label htmlFor={id}>{t("record.suggest.paste")}</label>
        <textarea
          id={id}
          rows={3}
          dir="auto"
          maxLength={8000}
          value={text}
          placeholder={t("record.suggest.placeholder")}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <button type="button" className="btn" disabled={disabled || read.isPending} onClick={() => read.mutate()}>
        {read.isPending ? t("ops.working") : t("record.suggest.read")}
      </button>
      {read.error ? (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(read.error))}
        </p>
      ) : null}
      {read.data && open.length === 0 && <p className="muted">{t("record.suggest.none")}</p>}
      {open.length > 0 && (
        <ul className="record-suggest__list" aria-label={t("record.suggest.title")}>
          {open.map((s) => (
            <li key={`${s.step}-${s.at}-${s.source}`}>
              <span className="record-step__label">{t(`record.step.${s.step}`)}</span>
              <strong dir="ltr">{clockOf(new Date(s.at), false)}</strong>
              <span className="record-pill record-pill--room">{t(`record.suggest.source.${s.source}`)}</span>
              <q dir="auto">{s.words}</q>
              <span className="muted">{fmt.date(s.written_at)}</span>
              {s.conflict && (
                <span className="field__error">{t(`record.error.${s.conflict}`, { defaultValue: s.conflict })}</span>
              )}
              <button type="button" className="btn btn--small" disabled={disabled} onClick={() => onApply(s)}>
                {t("record.suggest.apply")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

export function MissionRecordEditor({
  assignment,
  calledAt,
  onSaved,
  onCancel,
}: {
  assignment: Assignment;
  calledAt?: string | null;
  onSaved: (a: Assignment) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const ids = { crew: useId(), reason: useId(), other: useId() };
  const initial = useMemo(() => timesOf(assignmentTimes(assignment)), [assignment]);
  const [times, setTimes] = useState<RecordTimes>(initial);
  const crewBefore = assignment.crew_count ?? assignment.crew?.crew_size ?? null;
  const [crew, setCrew] = useState<number | null>(crewBefore);
  const usedBefore = useMemo(
    () => Object.fromEntries(Object.entries(assignment.consumables ?? {}).map(([k, v]) => [k, v ?? 0])),
    [assignment.consumables],
  );
  const [used, setUsed] = useState<Record<string, number>>(usedBefore);
  const [reason, setReason] = useState<Reason | null>(null);
  const [other, setOther] = useState("");
  const sources = assignment.time_sources ?? {};
  const now = new Date();
  const errors = recordErrors(times, now, initial);
  const corrected = correctedSteps(initial, times, sources);
  const reasonText = reason === "other" ? other.trim() : reason ? t(`record.reason.${reason}`) : "";
  const needsReason = corrected.length > 0 && !reasonText;
  const body = recordBody(
    initial,
    times,
    { before: crewBefore, after: crew },
    { before: usedBefore, after: used },
    corrected.length > 0 ? reasonText : "",
  );
  const nothing = !body.times && body.crew_count === undefined && !body.consumables;
  const invalid = Object.keys(errors).length > 0;
  const mutation = useMutation({
    mutationFn: () => api.saveMissionRecord(assignment.id, body),
    onSuccess: (a) => onSaved(a),
  });
  const preview = indicators(times, calledAt ? new Date(calledAt) : null);
  const locked = assignment.status === "cancelled" || mutation.isPending;
  return (
    <form
      className="record-editor"
      aria-label={t("record.title")}
      onSubmit={(e) => {
        e.preventDefault();
        if (!invalid && !needsReason && !nothing) mutation.mutate();
      }}
    >
      <h3>{t("record.title")}</h3>
      <p className="muted">{t("record.intro")}</p>
      <RecordWarnings warnings={assignment.record_warnings ?? []} />
      <ol className="record-steps">
        <li className="record-step record-step--fixed">
          <div className="record-step__head">
            <span className="record-step__label">{t("record.step.created_at")}</span>
            <span className="record-pill record-pill--order">{t("record.source.order")}</span>
          </div>
          <p className="record-step__fixed">
            {times.created_at ? (
              <>
                <span dir="ltr">{clockOf(times.created_at)}</span> · <span>{fmt.date(times.created_at.toISOString())}</span>
              </>
            ) : (
              "—"
            )}
          </p>
        </li>
        {EDITABLE_STEPS.map((step) => (
          <li key={step}>
            <TimeField
              step={step}
              value={times[step]}
              anchor={anchorOf(times, step)}
              error={errors[step]}
              source={sources[step]}
              changed={(initial[step]?.getTime() ?? null) !== (times[step]?.getTime() ?? null)}
              clearable={!REQUIRED_ONCE_SET.includes(step) || initial[step] === null}
              disabled={locked}
              onChange={(v) => setTimes((cur) => ({ ...cur, [step]: v }))}
            />
          </li>
        ))}
      </ol>
      <TimeSuggestions
        assignmentId={assignment.id}
        times={times}
        disabled={locked}
        onApply={(s) => {
          setTimes((cur) => ({ ...cur, [s.step]: new Date(s.at) }));
          if (s.source === "pasted" && reason === null) setReason("radio_log");
        }}
      />
      {Object.keys(preview).length > 0 && (
        <ul className="record-indicators" aria-label={t("record.indicators")}>
          {INDICATORS.filter((i) => preview[i.key] !== undefined).map((i) => (
            <li key={i.key}>
              <span className="record-indicators__label">{t(`record.indicator.${i.key}`)}</span>
              <strong>{fmt.duration(preview[i.key] ?? 0)}</strong>
            </li>
          ))}
        </ul>
      )}
      <div className="record-grid">
        <div className="field">
          <label htmlFor={ids.crew}>{t("record.crew")}</label>
          <Stepper
            id={ids.crew}
            value={crew}
            min={1}
            max={60}
            label={t("record.crew")}
            disabled={locked}
            onChange={setCrew}
            onClear={() => setCrew(null)}
          />
        </div>
      </div>
      <fieldset className="record-consumables">
        <legend>{t("record.consumables")}</legend>
        <div className="record-grid">
          {CONSUMABLES.map((c) => (
            <div className="field" key={c.key}>
              <label htmlFor={`${ids.crew}-${c.key}`}>{t(`record.consumable.${c.key}`)}</label>
              <Stepper
                id={`${ids.crew}-${c.key}`}
                value={used[c.key] ?? 0}
                min={0}
                max={c.max}
                step={c.step}
                label={t(`record.consumable.${c.key}`)}
                disabled={locked}
                onChange={(v) => setUsed((cur) => ({ ...cur, [c.key]: v }))}
                onClear={() => setUsed((cur) => ({ ...cur, [c.key]: 0 }))}
              />
            </div>
          ))}
        </div>
      </fieldset>
      {corrected.length > 0 && (
        <fieldset className="chips" aria-describedby={ids.reason}>
          <legend>
            {t("record.reasonTitle")}{" "}
            <span className="record-required" aria-hidden="true">
              *
            </span>
          </legend>
          <p id={ids.reason} className="muted">
            {t("record.reasonHint", {
              steps: corrected.map((s) => t(`record.step.${s}`)).join("، "),
            })}
          </p>
          {REASONS.map((r) => (
            <label key={r} className="chip-toggle">
              <input type="radio" name={ids.reason} checked={reason === r} onChange={() => setReason(r)} />
              <span>{t(`record.reason.${r}`)}</span>
            </label>
          ))}
          {reason === "other" && (
            <div className="field">
              <label htmlFor={ids.other}>{t("record.reasonOther")}</label>
              <input
                id={ids.other}
                value={other}
                maxLength={300}
                dir="auto"
                onChange={(e) => setOther(e.target.value)}
              />
            </div>
          )}
        </fieldset>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={locked || invalid || needsReason || nothing}>
          {mutation.isPending ? t("ops.working") : t("record.save")}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          {t("record.close")}
        </button>
      </div>
      <div role="status" aria-live="polite" className="muted">
        {invalid ? t("record.fixErrors") : needsReason ? t("record.needReason") : nothing ? t("record.nothing") : ""}
      </div>
      {mutation.error ? (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      ) : null}
    </form>
  );
}
