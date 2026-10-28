import { useEffect, useRef, type PointerEvent as ReactPointerEvent } from "react";
import { useTranslation } from "react-i18next";

/**
 * A number field drawn as − value + (R4a, design-system.md §3 `Stepper`): the user taps instead of typing.
 * The value stays typeable for a large number, the arrow keys step it, and a long press speeds up.
 * The buttons are never inside a <label>: name the field with a <label htmlFor={id}> or with `labelledBy`.
 */
export interface StepperProps {
  id?: string;
  value: number | null;
  onChange: (value: number) => void;
  /** Called when the user empties the field; without it an empty field keeps the last value. */
  onClear?: () => void;
  min?: number;
  max?: number;
  step?: number;
  /** Where the first tap on an empty field lands (a year: this year); the minimum when absent. */
  start?: number;
  /** The field's name for the buttons ("increase capacity"); the visible label names the input itself. */
  label?: string;
  labelledBy?: string;
  describedBy?: string;
  unit?: string;
  required?: boolean;
  invalid?: boolean;
  disabled?: boolean;
  /** Shown but not changeable (a setting the user may only read). */
  readOnly?: boolean;
  dir?: "ltr" | "rtl";
  className?: string;
}

const DELAY_MS = 400;
const REPEAT_MS = 80;
// After this many repeats a long press moves ten steps at a time, when the range allows it.
const FAST_AFTER = 10;

export function Stepper({
  id,
  value,
  onChange,
  onClear,
  min = 0,
  max = Number.MAX_SAFE_INTEGER,
  step = 1,
  start,
  label,
  labelledBy,
  describedBy,
  unit,
  required,
  invalid,
  disabled,
  readOnly,
  dir,
  className,
}: StepperProps) {
  const { t } = useTranslation();
  const clamp = (n: number) => Math.min(max, Math.max(min, n));
  // 0.1 + 0.2 is not 0.3: keep as many decimals as the step has.
  const decimals = (String(step).split(".")[1] ?? "").length;
  const tidy = (n: number) => Number(n.toFixed(decimals));
  // The hold reads the latest value, not the one of the render that started it.
  const current = useRef(value);
  current.current = value;
  const timer = useRef<{ delay?: number; repeat?: number }>({});

  const stop = () => {
    window.clearTimeout(timer.current.delay);
    window.clearInterval(timer.current.repeat);
    timer.current = {};
  };
  useEffect(() => stop, []);

  const move = (sign: 1 | -1, times = 1) => {
    if (current.current === null) {
      const first = clamp(start ?? min);
      current.current = first;
      onChange(first);
      return;
    }
    const next = clamp(current.current + sign * step * times);
    // Keep the value on the step grid that starts at min.
    const snapped = tidy(clamp(min + Math.round((next - min) / step) * step));
    if (snapped !== current.current) {
      current.current = snapped;
      onChange(snapped);
    }
  };

  const hold = (sign: 1 | -1) => (e: ReactPointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0) return;
    move(sign);
    let ticks = 0;
    const wide = max - min >= step * 100;
    timer.current.delay = window.setTimeout(() => {
      timer.current.repeat = window.setInterval(() => {
        ticks += 1;
        move(sign, wide && ticks > FAST_AFTER ? 10 : 1);
      }, REPEAT_MS);
    }, DELAY_MS);
  };

  const atMin = value !== null && value <= min;
  const atMax = value !== null && value >= max;
  const named = (key: "decrease" | "increase") => (label ? t(`stepper.${key}Named`, { label }) : t(`stepper.${key}`));

  const button = (sign: 1 | -1) => (
    <button
      type="button"
      className="stepper__btn"
      aria-label={named(sign > 0 ? "increase" : "decrease")}
      aria-controls={id}
      disabled={disabled || readOnly || (sign > 0 ? atMax : atMin)}
      onPointerDown={hold(sign)}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      onContextMenu={(e) => e.preventDefault()}
      // A pointer already stepped on pointerdown; the keyboard (Enter, Space) arrives as a click with detail 0.
      onClick={(e) => {
        if (e.detail === 0) move(sign);
      }}
    >
      <span aria-hidden="true">{sign > 0 ? "+" : "−"}</span>
    </button>
  );

  return (
    <div className={`stepper${className ? ` ${className}` : ""}`} data-disabled={disabled || undefined}>
      {button(-1)}
      <input
        id={id}
        className="stepper__value"
        type="number"
        inputMode="numeric"
        min={min}
        max={max === Number.MAX_SAFE_INTEGER ? undefined : max}
        step={step}
        value={value ?? ""}
        disabled={disabled}
        readOnly={readOnly}
        dir={dir}
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        aria-required={required || undefined}
        aria-invalid={invalid || undefined}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onClear?.();
            return;
          }
          const n = Number(raw);
          // Typing "15" with a minimum of 5 passes through "1": only the maximum is held while typing.
          if (Number.isFinite(n)) onChange(Math.min(max, n));
        }}
        onBlur={() => {
          if (value !== null && value < min) onChange(min);
        }}
      />
      {button(1)}
      {unit && (
        <span className="stepper__unit" aria-hidden="true">
          {unit}
        </span>
      )}
    </div>
  );
}
