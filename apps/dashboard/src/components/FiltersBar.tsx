import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useFilters } from "../context/filters";
import { PERIODS, type Period } from "../lib/filters";
import { useDebounced, useGouvernorats } from "../lib/hooks";
import { CATEGORIES, REPORT_STATUSES, type Category, type ReportStatus } from "../lib/types";
import { CategoryIcon } from "./CategoryIcon";

function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function PeriodSelector({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  const { t } = useTranslation();
  const name = useId();
  return (
    <fieldset className="segmented">
      <legend>{t("period.label")}</legend>
      {PERIODS.map((p) => (
        <label key={p} className="segmented__item">
          <input type="radio" name={name} value={p} checked={value === p} onChange={() => onChange(p)} />
          <span>{t(`period.${p}`)}</span>
        </label>
      ))}
    </fieldset>
  );
}

function SearchBox() {
  const { t } = useTranslation();
  const { filters, setFilters } = useFilters();
  const [text, setText] = useState(filters.q);
  const debounced = useDebounced(text, 350);
  const id = useId();

  useEffect(() => {
    if (debounced !== filters.q) setFilters({ q: debounced });
  }, [debounced, filters.q, setFilters]);

  return (
    <div className="field field--search">
      <label htmlFor={id}>{t("filters.search")}</label>
      <input
        id={id}
        type="search"
        value={text}
        placeholder={t("filters.searchPlaceholder")}
        onChange={(e) => setText(e.target.value)}
        maxLength={100}
        autoComplete="off"
      />
    </div>
  );
}

/** Filters shared by the incidents list and the map. */
export function FiltersBar({ showGouvernorat }: { showGouvernorat: boolean }) {
  const { t } = useTranslation();
  const { filters, setFilters, reset } = useFilters();
  const gouvernorats = useGouvernorats();
  const selectId = useId();
  // Remount the search box on reset so its local text is cleared too.
  const [resetCount, setResetCount] = useState(0);

  return (
    <section className="filters card" aria-label={t("filters.title")}>
      <SearchBox key={resetCount} />
      <fieldset className="chips">
        <legend>{t("filters.status")}</legend>
        {REPORT_STATUSES.map((s: ReportStatus) => (
          <label key={s} className={`chip-toggle chip--${s}`}>
            <input
              type="checkbox"
              checked={filters.statuses.includes(s)}
              onChange={() => setFilters({ statuses: toggle(filters.statuses, s) })}
            />
            <span>
              <span className="chip__dot" aria-hidden="true" />
              {t(`status.${s}`)}
            </span>
          </label>
        ))}
      </fieldset>
      <fieldset className="chips">
        <legend>{t("filters.category")}</legend>
        {CATEGORIES.map((c: Category) => (
          <label key={c} className="chip-toggle">
            <input
              type="checkbox"
              checked={filters.categories.includes(c)}
              onChange={() => setFilters({ categories: toggle(filters.categories, c) })}
            />
            <span>
              <CategoryIcon category={c} size={16} />
              {t(`category.${c}`)}
            </span>
          </label>
        ))}
      </fieldset>
      <div className="filters__row">
        {showGouvernorat && (
          // Phase N (design §6): several gouvernorats at once, in a disclosure that keeps the bar short.
          <details className="filters__gouvernorats" id={selectId}>
            <summary>
              {t("filters.gouvernorat")}:{" "}
              {filters.gouvernorats.length === 0
                ? t("filters.allGouvernorats")
                : filters.gouvernorats.length <= 2
                  ? filters.gouvernorats.map((c) => gouvernorats.nameOf(c)).join("، ")
                  : t("filters.someGouvernorats", { count: filters.gouvernorats.length })}
            </summary>
            <fieldset className="chips">
              <legend className="visually-hidden">{t("filters.gouvernorat")}</legend>
              <button type="button" className="btn btn--small btn--ghost" onClick={() => setFilters({ gouvernorats: [] })}>
                {t("filters.allGouvernorats")}
              </button>
              {gouvernorats.list.map((g) => (
                <label key={g.code} className="chip-toggle">
                  <input
                    type="checkbox"
                    checked={filters.gouvernorats.includes(g.code)}
                    onChange={() => setFilters({ gouvernorats: toggle(filters.gouvernorats, g.code) })}
                  />
                  <span>{gouvernorats.nameOf(g.code)}</span>
                </label>
              ))}
            </fieldset>
          </details>
        )}
        <PeriodSelector value={filters.period} onChange={(period) => setFilters({ period })} />
        <label className="chip-toggle">
          <input
            type="checkbox"
            checked={Boolean(filters.unverified)}
            onChange={(e) => setFilters({ unverified: e.target.checked })}
          />
          <span>{t("filters.unverified")}</span>
        </label>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => {
            reset();
            setResetCount((n) => n + 1);
          }}
        >
          {t("filters.reset")}
        </button>
      </div>
    </section>
  );
}
