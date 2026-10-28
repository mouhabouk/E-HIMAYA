// covers: phase L2 (docs/phase-l/design-l2.md §2.2, §2.5): pieces shared by the programme pages.
import { useTranslation } from "react-i18next";
import { useFormat } from "../lib/hooks";
import type { Problem, ProgrammeDiff, ProgrammeStatus } from "../lib/programmes";

const STATUS_TONE: Record<ProgrammeStatus, string> = {
  draft: "tone-slate",
  approved: "tone-green",
  updated: "tone-teal",
  ended: "tone-navy",
  cancelled: "tone-red",
};

export function ProgrammeStatusPill({ status, live }: { status: ProgrammeStatus; live?: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      <span className={`pill ${STATUS_TONE[status]}`}>{t(`programmes.status.${status}`)}</span>
      {live && (
        <>
          {" "}
          <span className="pill tone-sky">{t("programmes.live")}</span>
        </>
      )}
    </>
  );
}

/** One problem of an imported file, in words, with where it is ("line 12, BEACH-2026-096"). */
export function useProblemText() {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (p: Problem) => {
    const total = p.code.startsWith("total_") ? p.code.slice(6) : null;
    const what = total
      ? t("programmes.problem.total", {
          field: t(`programmes.totals.${total}`, { defaultValue: total }),
          value: p.value ?? "",
        })
      : t(`programmes.problem.${p.code}`, {
          defaultValue: p.code,
          value: p.value ?? "",
        });
    const where = [
      p.line ? t("programmes.problem.line", { line: fmt.number(p.line) }) : null,
      p.programme,
      p.ref,
    ].filter(Boolean);
    return where.length ? `${what} (${where.join(t("common.listSeparator"))})` : what;
  };
}

export function ProblemList({ title, items, tone }: { title: string; items: Problem[]; tone: "error" | "warning" }) {
  const text = useProblemText();
  const fmt = useFormat();
  if (items.length === 0) return null;
  return (
    <details className={`card programme-problems programme-problems--${tone}`} open={tone === "error"}>
      <summary>
        {title} ({fmt.number(items.length)})
      </summary>
      <ul>
        {items.map((p, i) => (
          <li key={i} dir="auto">
            {text(p)}
          </li>
        ))}
      </ul>
    </details>
  );
}

function shown(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

/** A value of the diff in words: point statuses are translated, the rest is shown as it is. */
function valueText(t: (k: string, o?: Record<string, unknown>) => string, field: string, value: unknown): string {
  if (field === "status" && typeof value === "string")
    return t(`programmes.pointStatus.${value}`, { defaultValue: value });
  if (field === "geo_confidence" && typeof value === "string") {
    return t(`programmes.confidence.${value}`, { defaultValue: value });
  }
  return shown(value);
}

function fieldLabel(t: (k: string, o?: Record<string, unknown>) => string, field: string): string {
  return t(`programmes.field.${field}`, { defaultValue: field });
}

/** Differences between two versions: programme fields, points added, removed (or closed) and changed. */
export function DiffView({ diff }: { diff: ProgrammeDiff }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const programme = Object.entries(diff.programme);
  const changed = Object.entries(diff.changed);
  const empty = programme.length + diff.added.length + diff.removed.length + changed.length === 0;
  return (
    <div className="programme-diff">
      <p className="muted">
        {t("programmes.diff.summary", {
          added: fmt.number(diff.added.length),
          removed: fmt.number(diff.removed.length),
          changed: fmt.number(changed.length),
        })}
      </p>
      {empty && <p className="muted">{t("programmes.diff.none")}</p>}
      {programme.length > 0 && (
        <ul className="programme-diff__list">
          {programme.map(([field, [before, after]]) => (
            <li key={field}>
              <strong>{fieldLabel(t, field)}</strong>: <del dir="auto">{valueText(t, field, before)}</del> →{" "}
              <ins dir="auto">{valueText(t, field, after)}</ins>
            </li>
          ))}
        </ul>
      )}
      {diff.added.length > 0 && (
        <p>
          <span className="pill tone-green">{t("programmes.diff.added")}</span>{" "}
          <span dir="ltr">{diff.added.join(", ")}</span>
        </p>
      )}
      {diff.removed.length > 0 && (
        <p>
          <span className="pill tone-red">{t("programmes.diff.removed")}</span>{" "}
          <span dir="ltr">{diff.removed.join(", ")}</span>
        </p>
      )}
      {changed.length > 0 && (
        <ul className="programme-diff__list">
          {changed.map(([ref, fields]) => (
            <li key={ref}>
              <span dir="ltr">{ref}</span>:{" "}
              {Object.entries(fields)
                .map(
                  ([field, [before, after]]) =>
                    `${fieldLabel(t, field)} ${valueText(t, field, before)} → ${valueText(t, field, after)}`,
                )
                .join(t("common.listSeparator"))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
