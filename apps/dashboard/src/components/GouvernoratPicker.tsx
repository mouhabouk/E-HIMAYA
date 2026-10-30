// covers: phase N (docs/phase-n/design-n.md §3): the gouvernorat checkboxes of the committee forms and of the
// disaster view, shared.
import { useTranslation } from "react-i18next";
import { useGouvernorats } from "../lib/hooks";

/** Checkboxes for target gouvernorats (a regional user only has its own, fixed). */
export function GouvernoratPicker({
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
