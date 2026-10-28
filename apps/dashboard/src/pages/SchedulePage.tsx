// covers: phase PL2 (docs/phase-pl/design-plans.md §3): the daily, weekly and monthly programmes of a gouvernorat on a
// calendar, its activities (every kind: duty, patrol, exercise, prevention visit, maintenance…) with their repetition,
// the copy of the previous period, the approval path each gouvernorat chooses, the follow-up, the print, and the
// progress of every gouvernorat (the only part the governor and the minister see).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { INTL_LOCALE } from "../lib/format";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { hasReadAccess } from "../lib/roles";
import {
  ACTIVITIES,
  ACTIVITY_KEYS,
  APPROVALS,
  bounds,
  daysOf,
  hhmm,
  isoDay,
  ITEM_TONE,
  WITH_REASON,
  monthWeeks,
  moveSpan,
  PERIOD_TONE,
  REPEATS,
  scheduleKeys,
  SPANS,
  type Approval,
  type Counts,
  type ItemBody,
  type ItemStatus,
  type PeriodDetail,
  type ScheduleItem,
  type ScheduleTemplate,
  type Span,
} from "../lib/schedule";

type Tab = "programme" | "templates" | "progress" | "settings";

const todayIso = () => isoDay(new Date());

function useDayNames() {
  const lang = useLanguage();
  return useMemo(() => {
    const locale = INTL_LOCALE[lang];
    const weekday = new Intl.DateTimeFormat(locale, { weekday: "long", timeZone: "UTC" });
    const short = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", timeZone: "UTC" });
    const month = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" });
    const at = (iso: string) => new Date(`${iso}T00:00:00Z`);
    return {
      weekday: (iso: string) => weekday.format(at(iso)),
      short: (iso: string) => short.format(at(iso)),
      month: (iso: string) => month.format(at(iso)),
    };
  }, [lang]);
}

function useRefresh() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: scheduleKeys.all });
}

function Rate({ counts }: { counts: Counts }) {
  const fmt = useFormat();
  const { t } = useTranslation();
  if (counts.rate === null) return <span className="muted">{t("schedule.progress.notDue")}</span>;
  return (
    <span className="rate">
      <span className="rate__bar" aria-hidden="true">
        <span style={{ inlineSize: `${Math.round(counts.rate * 100)}%` }} />
      </span>
      {fmt.percent(counts.rate)}
    </span>
  );
}

function ActivityChip({ item, onOpen, compact }: { item: ScheduleItem; onOpen: (i: ScheduleItem) => void; compact?: boolean }) {
  const { t } = useTranslation();
  const time = item.starts_at ? `${hhmm(item.starts_at)}${item.ends_at ? `–${hhmm(item.ends_at)}` : ""}` : t("schedule.allDay");
  return (
    <button
      type="button"
      className={`sched-chip tone-${ACTIVITIES[item.activity]} sched-chip--${item.status}`}
      onClick={() => onOpen(item)}
      aria-label={t("schedule.item.open", {
        title: item.title,
        activity: t(`schedule.activity.${item.activity}`),
        time,
        status: t(`schedule.itemStatus.${item.status}`),
      })}
    >
      <span className="sched-chip__time">
        <bdi>{time}</bdi>
      </span>
      <span className="sched-chip__title" dir="auto">
        {item.title}
      </span>
      {!compact && (
        <span className="sched-chip__meta">
          {t(`schedule.activity.${item.activity}`)}
          {item.unit_name && <> · {item.unit_name}</>}
          {item.status !== "planned" && <> · {t(`schedule.itemStatus.${item.status}`)}</>}
        </span>
      )}
    </button>
  );
}

function Calendar({ detail, span, onOpen }: { detail: PeriodDetail; span: Span; onOpen: (i: ScheduleItem) => void }) {
  const { t } = useTranslation();
  const names = useDayNames();
  const p = detail.period;
  const byDay = useMemo(() => {
    const m = new Map<string, ScheduleItem[]>();
    for (const i of detail.items) m.set(i.on_date, [...(m.get(i.on_date) ?? []), i]);
    return m;
  }, [detail.items]);
  const today = todayIso();
  if (span === "day") {
    const items = byDay.get(p.starts_on) ?? [];
    return items.length ? (
      <ol className="sched-day">
        {items.map((i) => (
          <li key={i.id}>
            <ActivityChip item={i} onOpen={onOpen} />
          </li>
        ))}
      </ol>
    ) : (
      <p className="card ops-empty">{t("schedule.emptyDay")}</p>
    );
  }
  if (span === "week") {
    return (
      <div className="sched-week">
        {daysOf(p.starts_on, p.ends_on).map((d) => (
          <section key={d} className={`sched-week__day${d === today ? " sched-week__day--today" : ""}`} aria-label={names.weekday(d)}>
            <h3>{names.short(d)}</h3>
            <ol>
              {(byDay.get(d) ?? []).map((i) => (
                <li key={i.id}>
                  <ActivityChip item={i} onOpen={onOpen} compact />
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    );
  }
  const weeks = monthWeeks(p.starts_on, p.ends_on);
  const first = weeks[0] ?? [];
  return (
    <table className="sched-month">
      <caption className="visually-hidden">{names.month(p.starts_on)}</caption>
      <thead>
        <tr>
          {first.map((d) => (
            <th key={d} scope="col">
              {names.weekday(d)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {weeks.map((w) => (
          <tr key={w[0]}>
            {w.map((d) => {
              const inside = d >= p.starts_on && d <= p.ends_on;
              const items = byDay.get(d) ?? [];
              return (
                <td key={d} className={`${inside ? "" : "sched-month__out"}${d === today ? " sched-month__today" : ""}`}>
                  {inside && (
                    <>
                      <span className="sched-month__no">{Number(d.slice(8))}</span>
                      <ol>
                        {items.map((i) => (
                          <li key={i.id}>
                            <ActivityChip item={i} onOpen={onOpen} compact />
                          </li>
                        ))}
                      </ol>
                    </>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const blankItem = (on: string): ItemBody => ({
  activity: "duty",
  title: "",
  on_date: on,
  starts_at: "08:00",
  ends_at: "16:00",
  unit_id: null,
  place: "",
  responsible: "",
  staff_count: null,
  resources: [],
  plan_document_id: null,
  notes: "",
  repeat: "none",
});

function ItemForm({
  detail,
  existing,
  day,
  onDone,
}: {
  detail: PeriodDetail;
  existing: ScheduleItem | null;
  day: string;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh();
  const id = useId();
  const p = detail.period;
  const options = useQuery({
    queryKey: scheduleKeys.options(p.gouvernorat_code),
    queryFn: ({ signal }) => api.scheduleOptions(p.gouvernorat_code, signal),
  });
  const [f, setF] = useState<ItemBody>(() =>
    existing
      ? {
          activity: existing.activity,
          title: existing.title,
          on_date: existing.on_date,
          starts_at: hhmm(existing.starts_at) || null,
          ends_at: hhmm(existing.ends_at) || null,
          unit_id: existing.unit_id,
          place: existing.place,
          responsible: existing.responsible,
          staff_count: existing.staff_count,
          resources: existing.resources.map((r) => ({ category_key: r.category_key, qty: r.qty })),
          plan_document_id: existing.plan_document_id,
          notes: existing.notes,
        }
      : blankItem(day),
  );
  const allDay = f.starts_at === null;
  const set = (patch: Partial<ItemBody>) => setF((x) => ({ ...x, ...patch }));
  const save = useMutation({
    mutationFn: () => (existing ? api.updateScheduleItem(existing.id, f) : api.addScheduleItem(p.id, f)),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  const lang = i18n.language.slice(0, 2);
  return (
    <form
      className="card sched-form"
      aria-labelledby={`${id}-h`}
      onSubmit={(e) => {
        e.preventDefault();
        if (f.title.trim().length >= 2) save.mutate();
      }}
    >
      <h3 id={`${id}-h`}>{existing ? t("schedule.item.edit") : t("schedule.item.add")}</h3>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-a`}>{t("schedule.item.activity")}</label>
          <select id={`${id}-a`} value={f.activity} onChange={(e) => set({ activity: e.target.value as ItemBody["activity"] })}>
            {ACTIVITY_KEYS.map((k) => (
              <option key={k} value={k}>
                {t(`schedule.activity.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field field--wide">
          <label htmlFor={`${id}-t`}>{t("schedule.item.title")}</label>
          <input id={`${id}-t`} dir="auto" required minLength={2} maxLength={300} value={f.title} onChange={(e) => set({ title: e.target.value })} />
        </div>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-d`}>{t("schedule.item.date")}</label>
          <input
            id={`${id}-d`}
            type="date"
            required
            min={p.starts_on}
            max={p.ends_on}
            value={f.on_date}
            onChange={(e) => set({ on_date: e.target.value })}
          />
        </div>
        <label className="checkbox sched-form__allday">
          <input
            type="checkbox"
            checked={allDay}
            onChange={(e) => set(e.target.checked ? { starts_at: null, ends_at: null } : { starts_at: "08:00", ends_at: "16:00" })}
          />
          {t("schedule.allDay")}
        </label>
        {!allDay && (
          <>
            <div className="field">
              <label htmlFor={`${id}-s`}>{t("schedule.item.starts")}</label>
              <input id={`${id}-s`} type="time" value={f.starts_at ?? ""} onChange={(e) => set({ starts_at: e.target.value || null })} />
            </div>
            <div className="field">
              <label htmlFor={`${id}-e`}>{t("schedule.item.ends")}</label>
              <input id={`${id}-e`} type="time" value={f.ends_at ?? ""} onChange={(e) => set({ ends_at: e.target.value || null })} />
            </div>
          </>
        )}
        {!existing && (
          <div className="field">
            <label htmlFor={`${id}-r`}>{t("schedule.item.repeat")}</label>
            <select id={`${id}-r`} value={f.repeat ?? "none"} onChange={(e) => set({ repeat: e.target.value as ItemBody["repeat"] })}>
              {REPEATS.map((r) => (
                <option key={r} value={r}>
                  {t(`schedule.repeat.${r}`)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-u`}>{t("schedule.item.unit")}</label>
          <select id={`${id}-u`} value={f.unit_id ?? ""} onChange={(e) => set({ unit_id: e.target.value || null })}>
            <option value="">—</option>
            {options.data?.units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-pl`}>{t("schedule.item.place")}</label>
          <input id={`${id}-pl`} dir="auto" maxLength={300} value={f.place} onChange={(e) => set({ place: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-re`}>{t("schedule.item.responsible")}</label>
          <input id={`${id}-re`} dir="auto" maxLength={200} value={f.responsible} onChange={(e) => set({ responsible: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-n`}>{t("schedule.item.staff")}</label>
          <input
            id={`${id}-n`}
            type="number"
            min={0}
            max={10000}
            value={f.staff_count ?? ""}
            onChange={(e) => set({ staff_count: e.target.value === "" ? null : Math.max(0, Number(e.target.value)) })}
          />
        </div>
      </div>
      <fieldset className="sched-form__resources">
        <legend>{t("schedule.item.resources")}</legend>
        {f.resources.map((r, n) => (
          <div className="form-grid" key={n}>
            <div className="field">
              <label htmlFor={`${id}-rc${n}`}>{t("schedule.item.resource")}</label>
              <select
                id={`${id}-rc${n}`}
                value={r.category_key}
                onChange={(e) => set({ resources: f.resources.map((x, k) => (k === n ? { ...x, category_key: e.target.value } : x)) })}
              >
                {options.data?.categories.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.name[lang] || c.name.ar || c.key}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor={`${id}-rq${n}`}>{t("schedule.item.qty")}</label>
              <input
                id={`${id}-rq${n}`}
                type="number"
                min={1}
                max={1000}
                value={r.qty}
                onChange={(e) => set({ resources: f.resources.map((x, k) => (k === n ? { ...x, qty: Math.max(1, Number(e.target.value) || 1) } : x)) })}
              />
            </div>
            <button type="button" className="btn btn--small btn--ghost" onClick={() => set({ resources: f.resources.filter((_, k) => k !== n) })}>
              {t("schedule.item.removeResource")}
            </button>
          </div>
        ))}
        {options.data && options.data.categories.length > 0 && f.resources.length < 20 && (
          <button
            type="button"
            className="btn btn--small"
            onClick={() => set({ resources: [...f.resources, { category_key: options.data.categories[0]?.key ?? "", qty: 1 }] })}
          >
            {t("schedule.item.addResource")}
          </button>
        )}
      </fieldset>
      <div className="form-grid">
        <div className="field field--wide">
          <label htmlFor={`${id}-p`}>{t("schedule.item.plan")}</label>
          <select id={`${id}-p`} value={f.plan_document_id ?? ""} onChange={(e) => set({ plan_document_id: e.target.value || null })}>
            <option value="">—</option>
            {options.data?.plans.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </div>
        <div className="field field--wide">
          <label htmlFor={`${id}-no`}>{t("schedule.item.notes")}</label>
          <textarea id={`${id}-no`} dir="auto" rows={2} maxLength={2000} value={f.notes} onChange={(e) => set({ notes: e.target.value })} />
        </div>
      </div>
      {save.isError && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending || f.title.trim().length < 2}>
          {existing ? t("schedule.item.save") : t("schedule.item.add")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function ItemPanel({
  detail,
  item,
  onEdit,
  onClose,
}: {
  detail: PeriodDetail;
  item: ScheduleItem;
  onEdit: () => void;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefresh();
  const id = useId();
  const [reason, setReason] = useState("");
  const lang = i18n.language.slice(0, 2);
  const status = useMutation({
    mutationFn: (s: ItemStatus) => api.scheduleItemStatus(item.id, s, reason.trim()),
    onSuccess: () => (refresh(), onClose()),
  });
  const remove = useMutation({
    mutationFn: (series: boolean) => api.deleteScheduleItem(item.id, series),
    onSuccess: () => (refresh(), onClose()),
  });
  const error = status.error ?? remove.error;
  const due = item.on_date <= todayIso();
  return (
    <section className="card sched-panel" aria-labelledby={`${id}-h`}>
      <div className="inline-dialog__head">
        <h3 id={`${id}-h`} dir="auto">
          {item.title}
        </h3>
        <button type="button" className="btn btn--ghost btn--small" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
      <p>
        <span className={`pill tone-${ACTIVITIES[item.activity]}`}>{t(`schedule.activity.${item.activity}`)}</span>{" "}
        <span className={`pill tone-${ITEM_TONE[item.status]}`}>{t(`schedule.itemStatus.${item.status}`)}</span>
        {item.status_auto && <span className="muted"> · {t("schedule.follow.auto")}</span>}
      </p>
      <dl className="sched-panel__facts">
        <dt>{t("schedule.item.date")}</dt>
        <dd>
          {fmt.date(item.on_date)}
          {item.starts_at ? (
            <>
              {" "}
              · <bdi>{hhmm(item.starts_at)}</bdi>
              {item.ends_at && (
                <>
                  –<bdi>{hhmm(item.ends_at)}</bdi>
                </>
              )}
            </>
          ) : (
            <> · {t("schedule.allDay")}</>
          )}
          {item.series_id && <> · {t("schedule.item.inSeries")}</>}
        </dd>
        {item.unit_name && (
          <>
            <dt>{t("schedule.item.unit")}</dt>
            <dd>{item.unit_name}</dd>
          </>
        )}
        {item.place && (
          <>
            <dt>{t("schedule.item.place")}</dt>
            <dd dir="auto">{item.place}</dd>
          </>
        )}
        {item.responsible && (
          <>
            <dt>{t("schedule.item.responsible")}</dt>
            <dd dir="auto">{item.responsible}</dd>
          </>
        )}
        {item.staff_count !== null && (
          <>
            <dt>{t("schedule.item.staff")}</dt>
            <dd>{fmt.number(item.staff_count)}</dd>
          </>
        )}
        {item.resources.length > 0 && (
          <>
            <dt>{t("schedule.item.resources")}</dt>
            <dd>{item.resources.map((r) => `${r.name[lang] || r.name.ar || r.category_key} × ${fmt.number(r.qty)}`).join(t("common.listSeparator"))}</dd>
          </>
        )}
        {item.plan_title && (
          <>
            <dt>{t("schedule.item.plan")}</dt>
            <dd dir="auto">{item.plan_title}</dd>
          </>
        )}
        {item.notes && (
          <>
            <dt>{t("schedule.item.notes")}</dt>
            <dd dir="auto">{item.notes}</dd>
          </>
        )}
        {item.status_at && (
          <>
            <dt>{t("schedule.item.followUp")}</dt>
            <dd>
              {item.status_by_name ?? "—"} · {fmt.dateTime(item.status_at)}
              {item.status_reason && <> · {item.status_reason}</>}
            </dd>
          </>
        )}
      </dl>
      {detail.can_follow_up && (
        <div className="sched-panel__follow">
          <div className="field">
            <label htmlFor={`${id}-why`}>{t("schedule.item.reason")}</label>
            <input id={`${id}-why`} dir="auto" maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div className="form-actions">
            {(["in_progress", "done"] as const).map((s) => (
              <button key={s} type="button" className="btn btn--primary" disabled={!due || item.status === s || status.isPending} onClick={() => status.mutate(s)}>
                {t(`schedule.follow.${s}`)}
              </button>
            ))}
            {WITH_REASON.map((s) => (
              <button
                key={s}
                type="button"
                className="btn"
                disabled={reason.trim().length < 5 || (s === "not_done" && !due) || status.isPending}
                onClick={() => status.mutate(s)}
              >
                {t(`schedule.follow.${s}`)}
              </button>
            ))}
            {(item.status !== "planned" || item.status_auto) && (
              <button type="button" className="btn btn--ghost" disabled={status.isPending} onClick={() => status.mutate("planned")}>
                {t("schedule.follow.planned")}
              </button>
            )}
          </div>
          {item.starts_at && <p className="muted">{t("schedule.follow.autoHint")}</p>}
          {!due && <p className="muted">{t("schedule.follow.notDue")}</p>}
        </div>
      )}
      {detail.can_edit && (
        <div className="form-actions">
          <button type="button" className="btn" onClick={onEdit}>
            {t("schedule.item.edit")}
          </button>
          <button type="button" className="btn btn--ghost" disabled={remove.isPending} onClick={() => remove.mutate(false)}>
            {t("schedule.item.remove")}
          </button>
          {item.series_id && (
            <button type="button" className="btn btn--ghost" disabled={remove.isPending} onClick={() => remove.mutate(true)}>
              {t("schedule.item.removeSeries")}
            </button>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(error))}
        </p>
      )}
    </section>
  );
}

function PeriodBar({ detail }: { detail: PeriodDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefresh();
  const id = useId();
  const p = detail.period;
  const [returning, setReturning] = useState(false);
  const [reason, setReason] = useState("");
  const step = useMutation({
    mutationFn: (action: "submit" | "approve" | "return" | "copy-previous") =>
      api.periodStep(p.id, action, p.version, action === "return" ? reason.trim() : undefined),
    onSuccess: () => (setReturning(false), setReason(""), refresh()),
  });
  const remove = useMutation({ mutationFn: () => api.deletePeriod(p.id), onSuccess: refresh });
  const error = step.error ?? remove.error;
  const who = (name: string | null, at: string | null) => (at ? `${name ?? "—"} · ${fmt.dateTime(at)}` : null);
  return (
    <section className="card sched-bar" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="visually-hidden">
        {t("schedule.period.title")}
      </h2>
      <p className="sched-bar__state">
        <span className={`pill tone-${PERIOD_TONE[p.status]}`}>{t(`schedule.status.${p.status}`)}</span>
        <span className="muted">{t(`schedule.approval.${p.approval}`)}</span>
        <span>
          {t("schedule.period.counts", {
            items: fmt.number(p.counts.items),
            done: fmt.number(p.counts.done),
            postponed: fmt.number(p.counts.postponed),
          })}
        </span>
        <Rate counts={p.counts} />
      </p>
      {p.return_reason && p.status === "returned" && <p className="alert alert--warn">{t("schedule.period.returned", { reason: p.return_reason })}</p>}
      <p className="muted sched-bar__who">
        {who(p.submitted_by_name, p.submitted_at) && <>{t("schedule.period.submitted", { who: who(p.submitted_by_name, p.submitted_at) })} </>}
        {who(p.approved_by_name, p.approved_at) && <>{t("schedule.period.approved", { who: who(p.approved_by_name, p.approved_at) })} </>}
        {who(p.centre_approved_by_name, p.centre_approved_at) && (
          <>{t("schedule.period.centreApproved", { who: who(p.centre_approved_by_name, p.centre_approved_at) })}</>
        )}
      </p>
      <div className="form-actions no-print">
        {detail.can_submit && (
          <button type="button" className="btn btn--primary" disabled={step.isPending} onClick={() => step.mutate("submit")}>
            {p.approval === "direct" ? t("schedule.period.publish") : t("schedule.period.submit")}
          </button>
        )}
        {detail.can_approve && (
          <button type="button" className="btn btn--primary" disabled={step.isPending} onClick={() => step.mutate("approve")}>
            {t("schedule.period.approve")}
          </button>
        )}
        {detail.can_return && !returning && (
          <button type="button" className="btn" onClick={() => setReturning(true)}>
            {t("schedule.period.return")}
          </button>
        )}
        {detail.can_submit && detail.previous_id && (
          <button type="button" className="btn" disabled={step.isPending} onClick={() => step.mutate("copy-previous")}>
            {t("schedule.period.copy")}
          </button>
        )}
        <button type="button" className="btn btn--ghost" onClick={() => window.print()}>
          <Icon name="print" size={18} />
          {t("schedule.period.print")}
        </button>
        {detail.can_delete && (
          <button type="button" className="btn btn--ghost" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {t("schedule.period.delete")}
          </button>
        )}
      </div>
      {returning && (
        <form
          className="directive__actions no-print"
          onSubmit={(e) => {
            e.preventDefault();
            if (reason.trim().length >= 5) step.mutate("return");
          }}
        >
          <label htmlFor={`${id}-why`}>{t("schedule.period.returnReason")}</label>
          <input id={`${id}-why`} dir="auto" minLength={5} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
          <button type="submit" className="btn btn--primary" disabled={reason.trim().length < 5 || step.isPending}>
            {t("schedule.period.return")}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setReturning(false)}>
            {t("common.cancel")}
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(error))}
        </p>
      )}
    </section>
  );
}

/** The templates of the gouvernorat for this span (Yamen, 2026-10-28: a programme repeats, it is not written again). */
function useTemplates(gouvernorat: number | null, span: Span | null, enabled = true) {
  const { api } = useServices();
  return useQuery({
    queryKey: scheduleKeys.templates(gouvernorat, span),
    queryFn: ({ signal }) => api.scheduleTemplates(gouvernorat, span, signal),
    enabled: enabled && gouvernorat !== null,
  });
}

function TemplatePicker({ templates, value, onChange, label }: { templates: ScheduleTemplate[]; value: string; onChange: (v: string) => void; label: string }) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">—</option>
        {templates.map((x) => (
          <option key={x.id} value={x.id}>
            {t("schedule.template.option", { name: x.name, count: x.items })}
          </option>
        ))}
      </select>
    </>
  );
}

/** Apply a template to this programme, or keep it as one. */
function TemplateBar({ detail }: { detail: PeriodDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh();
  const id = useId();
  const p = detail.period;
  const editable = detail.can_edit && (p.status === "draft" || p.status === "returned");
  const keeps = (detail.can_edit || detail.can_follow_up) && detail.items.length > 0;
  const templates = useTemplates(p.gouvernorat_code, p.span, editable);
  const [choice, setChoice] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const apply = useMutation({
    mutationFn: () => api.applyScheduleTemplate(p.id, p.version, choice),
    onSuccess: () => (setChoice(""), refresh()),
  });
  const keep = useMutation({
    mutationFn: () => api.saveScheduleTemplate(p.id, name.trim()),
    onSuccess: (x) => (setSaving(false), setName(""), setSaved(x.name), refresh()),
  });
  if (!editable && !keeps) return null;
  const error = apply.error ?? keep.error;
  return (
    <section className="card sched-templates no-print" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="sched-templates__title">
        {t("schedule.template.title")}
      </h2>
      {editable && (templates.data ?? []).length > 0 && (
        <form
          className="directive__actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (choice) apply.mutate();
          }}
        >
          <TemplatePicker templates={templates.data ?? []} value={choice} onChange={setChoice} label={t("schedule.template.pick")} />
          <button type="submit" className="btn btn--primary" disabled={!choice || apply.isPending}>
            {t("schedule.template.apply")}
          </button>
        </form>
      )}
      {editable && templates.data && templates.data.length === 0 && <p className="muted">{t("schedule.template.noneYet")}</p>}
      {keeps && !saving && (
        <button type="button" className="btn" onClick={() => (setSaved(null), setSaving(true))}>
          {t("schedule.template.keep")}
        </button>
      )}
      {saving && (
        <form
          className="directive__actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim().length >= 2) keep.mutate();
          }}
        >
          <label htmlFor={`${id}-n`}>{t("schedule.template.name")}</label>
          <input id={`${id}-n`} dir="auto" minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" className="btn btn--primary" disabled={name.trim().length < 2 || keep.isPending}>
            {t("schedule.template.save")}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setSaving(false)}>
            {t("common.cancel")}
          </button>
        </form>
      )}
      {saved && (
        <p role="status" className="muted">
          {t("schedule.template.saved", { name: saved })}
        </p>
      )}
      {error && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(error))}
        </p>
      )}
    </section>
  );
}

/** A new programme started empty or from a template. */
function StartPeriod({ span, on, gouvernorat }: { span: Span; on: string; gouvernorat: number }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh();
  const templates = useTemplates(gouvernorat, span);
  const [choice, setChoice] = useState("");
  const create = useMutation({
    mutationFn: async (template: string | null) => {
      const made = await api.createPeriod(span, on, gouvernorat);
      return template ? api.applyScheduleTemplate(made.period.id, made.period.version, template) : made;
    },
    onSettled: refresh,
  });
  return (
    <>
      <button type="button" className="btn btn--primary" disabled={create.isPending} onClick={() => create.mutate(null)}>
        {t(`schedule.create.${span}`)}
      </button>
      {(templates.data ?? []).length > 0 && (
        <form
          className="directive__actions sched-start"
          onSubmit={(e) => {
            e.preventDefault();
            if (choice) create.mutate(choice);
          }}
        >
          <TemplatePicker templates={templates.data ?? []} value={choice} onChange={setChoice} label={t("schedule.template.startFrom")} />
          <button type="submit" className="btn" disabled={!choice || create.isPending}>
            {t("schedule.template.create")}
          </button>
        </form>
      )}
      {create.isError && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(create.error))}
        </p>
      )}
    </>
  );
}

function TemplateRow({ template }: { template: ScheduleTemplate }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefresh();
  const id = useId();
  const [name, setName] = useState(template.name);
  const rename = useMutation({ mutationFn: () => api.renameScheduleTemplate(template.id, name.trim()), onSuccess: refresh });
  const remove = useMutation({ mutationFn: () => api.deleteScheduleTemplate(template.id), onSuccess: refresh });
  const error = rename.error ?? remove.error;
  return (
    <tr>
      <td>
        <form
          className="directive__actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim().length >= 2 && name.trim() !== template.name) rename.mutate();
          }}
        >
          <label htmlFor={`${id}-n`} className="visually-hidden">
            {t("schedule.template.nameOf", { name: template.name })}
          </label>
          <input id={`${id}-n`} dir="auto" minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" className="btn btn--small" disabled={name.trim().length < 2 || name.trim() === template.name || rename.isPending}>
            {t("schedule.template.rename")}
          </button>
        </form>
        {error && (
          <span role="alert" className="field__error">
            {t(errorMessageKey(error))}
          </span>
        )}
      </td>
      <td>{t(`schedule.span.${template.span}`)}</td>
      <td>
        {(Object.entries(template.activities) as [keyof typeof ACTIVITIES, number][])
          .map(([k, n]) => `${t(`schedule.activity.${k}`)} × ${fmt.number(n)}`)
          .join(t("common.listSeparator"))}
      </td>
      <td className="muted">
        {template.updated_by_name ?? "—"} · {fmt.dateTime(template.updated_at)}
      </td>
      <td>
        <button
          type="button"
          className="btn btn--small btn--ghost"
          disabled={remove.isPending}
          onClick={() => remove.mutate()}
          aria-label={t("schedule.template.deleteOf", { name: template.name })}
        >
          {t("schedule.template.delete")}
        </button>
      </td>
    </tr>
  );
}

function TemplatesView({ gouvernorat }: { gouvernorat: number }) {
  const { t } = useTranslation();
  const templates = useTemplates(gouvernorat, null);
  if (templates.isPending) return <Loading />;
  if (templates.isError) return <ErrorBox error={templates.error} onRetry={() => void templates.refetch()} />;
  return (
    <section aria-labelledby="sched-templates">
      <h2 id="sched-templates">{t("schedule.template.listTitle")}</h2>
      <p className="muted">{t("schedule.template.intro")}</p>
      {templates.data.length === 0 ? (
        <p className="card ops-empty">{t("schedule.template.noneYet")}</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">{t("schedule.template.listTitle")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("schedule.template.name")}</th>
              <th scope="col">{t("schedule.span.label")}</th>
              <th scope="col">{t("schedule.template.activities")}</th>
              <th scope="col">{t("schedule.settings.updated")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("schedule.template.delete")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {templates.data.map((x) => (
              <TemplateRow key={`${x.id}-${x.name}`} template={x} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Programme({ span, on, gouvernorat }: { span: Span; on: string; gouvernorat: number | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const slot = useQuery({
    queryKey: scheduleKeys.slot(gouvernorat, span, on),
    queryFn: ({ signal }) => api.scheduleSlot(span, on, gouvernorat, signal),
  });
  const [open, setOpen] = useState<ScheduleItem | null>(null);
  const [form, setForm] = useState<"new" | ScheduleItem | null>(null);
  if (slot.isPending) return <Loading />;
  if (slot.isError) return <ErrorBox error={slot.error} onRetry={() => void slot.refetch()} />;
  const detail = slot.data.period;
  if (!detail) {
    return (
      <div className="card ops-empty">
        <p>{t("schedule.none")}</p>
        {slot.data.can_create && gouvernorat !== null && <StartPeriod span={span} on={on} gouvernorat={gouvernorat} />}
      </div>
    );
  }
  const current = open ? (detail.items.find((i) => i.id === open.id) ?? null) : null;
  const day = on >= detail.period.starts_on && on <= detail.period.ends_on ? on : detail.period.starts_on;
  return (
    <div className="sched-programme">
      <PeriodBar detail={detail} />
      <TemplateBar detail={detail} />
      {detail.can_edit && form === null && (
        <p className="no-print">
          <button type="button" className="btn" onClick={() => (setOpen(null), setForm("new"))}>
            {t("schedule.item.add")}
          </button>
        </p>
      )}
      {form !== null && (
        <ItemForm key={form === "new" ? "new" : form.id} detail={detail} existing={form === "new" ? null : form} day={day} onDone={() => setForm(null)} />
      )}
      {current && form === null && (
        <ItemPanel detail={detail} item={current} onEdit={() => setForm(current)} onClose={() => setOpen(null)} />
      )}
      <Calendar detail={detail} span={span} onOpen={(i) => (setForm(null), setOpen(i))} />
      <ul className="sched-legend" aria-label={t("schedule.legend")}>
        {ACTIVITY_KEYS.map((k) => (
          <li key={k}>
            <span className={`sched-legend__dot tone-${ACTIVITIES[k]}`} aria-hidden="true" />
            {t(`schedule.activity.${k}`)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProgressView({ span, on, onOpen }: { span: Span; on: string; onOpen: ((code: number) => void) | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const progress = useQuery({ queryKey: scheduleKeys.progress(span, on), queryFn: ({ signal }) => api.scheduleProgress(span, on, signal) });
  if (progress.isPending) return <Loading />;
  if (progress.isError) return <ErrorBox error={progress.error} onRetry={() => void progress.refetch()} />;
  return (
    <table className="table">
      <caption className="visually-hidden">{t("schedule.progress.title")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("schedule.progress.gouvernorat")}</th>
          <th scope="col">{t("schedule.progress.status")}</th>
          <th scope="col">{t("schedule.progress.items")}</th>
          <th scope="col">{t("schedule.progress.done")}</th>
          <th scope="col">{t("schedule.progress.postponed")}</th>
          <th scope="col">{t("schedule.progress.rate")}</th>
          {onOpen && progress.data.lists && (
            <th scope="col">
              <span className="visually-hidden">{t("schedule.progress.open")}</span>
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {progress.data.rows.map((r) => (
          <tr key={r.gouvernorat_code}>
            <th scope="row">{r.gouvernorat_name}</th>
            <td>
              {r.status ? <span className={`pill tone-${PERIOD_TONE[r.status]}`}>{t(`schedule.status.${r.status}`)}</span> : <span className="muted">{t("schedule.progress.none")}</span>}
            </td>
            <td>{fmt.number(r.counts.items)}</td>
            <td>{fmt.number(r.counts.done)}</td>
            <td>{fmt.number(r.counts.postponed)}</td>
            <td>{r.period_id ? <Rate counts={r.counts} /> : "—"}</td>
            {onOpen && progress.data.lists && (
              <td>
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => onOpen(r.gouvernorat_code)}
                  aria-label={t("schedule.progress.openOf", { name: r.gouvernorat_name })}
                >
                  {t("schedule.progress.open")}
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SettingRow({ code, name, approval, canEdit, updated }: { code: number; name: string | null; approval: Approval; canEdit: boolean; updated: string | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh();
  const id = useId();
  const [value, setValue] = useState<Approval>(approval);
  const save = useMutation({ mutationFn: () => api.saveScheduleSetting(code, value), onSuccess: refresh });
  return (
    <tr>
      <th scope="row">{name}</th>
      <td>
        {canEdit ? (
          <form
            className="directive__actions"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <label htmlFor={`${id}-a`} className="visually-hidden">
              {t("schedule.settings.approvalOf", { name })}
            </label>
            <select id={`${id}-a`} value={value} onChange={(e) => setValue(e.target.value as Approval)}>
              {APPROVALS.map((a) => (
                <option key={a} value={a}>
                  {t(`schedule.approval.${a}`)}
                </option>
              ))}
            </select>
            <button type="submit" className="btn btn--small btn--primary" disabled={value === approval || save.isPending}>
              {t("schedule.settings.save")}
            </button>
            {save.isError && (
              <span role="alert" className="field__error">
                {t(errorMessageKey(save.error))}
              </span>
            )}
          </form>
        ) : (
          t(`schedule.approval.${approval}`)
        )}
      </td>
      <td className="muted">{updated ?? "—"}</td>
    </tr>
  );
}

function SettingsView() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const settings = useQuery({ queryKey: scheduleKeys.settings, queryFn: ({ signal }) => api.scheduleSettings(signal) });
  if (settings.isPending) return <Loading />;
  if (settings.isError) return <ErrorBox error={settings.error} onRetry={() => void settings.refetch()} />;
  return (
    <section aria-labelledby="sched-settings">
      <h2 id="sched-settings">{t("schedule.settings.title")}</h2>
      <p className="muted">{t("schedule.settings.intro")}</p>
      <table className="table">
        <caption className="visually-hidden">{t("schedule.settings.title")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("schedule.progress.gouvernorat")}</th>
            <th scope="col">{t("schedule.settings.approval")}</th>
            <th scope="col">{t("schedule.settings.updated")}</th>
          </tr>
        </thead>
        <tbody>
          {settings.data.map((s) => (
            <SettingRow
              key={`${s.gouvernorat_code}-${s.approval}`}
              code={s.gouvernorat_code}
              name={s.gouvernorat_name}
              approval={s.approval}
              canEdit={s.can_edit}
              updated={s.updated_at ? `${s.updated_by_name ?? "—"} · ${fmt.dateTime(s.updated_at)}` : null}
            />
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function SchedulePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { list, nameOf } = useGouvernorats();
  const names = useDayNames();
  const fmt = useFormat();
  const id = useId();
  const roles = user?.identity.roles ?? [];
  const national = Boolean(user?.identity.national);
  const lists = hasReadAccess(roles);
  // The user may arrive after the first render: the defaults follow it until a choice is made.
  const [chosenTab, setTab] = useState<Tab | null>(null);
  const tab: Tab = lists ? (chosenTab ?? (national ? "progress" : "programme")) : "progress";
  const [span, setSpan] = useState<Span>("week");
  const [on, setOn] = useState(todayIso);
  const [chosen, setGouvernorat] = useState<number | null>(null);
  const gouvernorat = national ? chosen : (user?.identity.gouvernoratCode ?? null);
  const [start, end] = bounds(span, on);
  const label =
    span === "day" ? `${names.weekday(on)} ${fmt.date(on)}` : span === "week" ? t("schedule.weekOf", { from: fmt.date(start), to: fmt.date(end) }) : names.month(start);
  const tabs: Tab[] = lists ? ["programme", "templates", "progress", "settings"] : ["progress"];
  return (
    <div className="page schedule-page">
      <div className="page__head">
        <PageTitle icon="calendarMonth" tone="teal">
          {t("schedule.title")}
        </PageTitle>
      </div>
      <p className="muted no-print">{t("schedule.intro")}</p>
      {tabs.length > 1 && (
        <div role="tablist" aria-label={t("schedule.tabs.label")} className="tabs no-print">
          {tabs.map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
              onClick={() => setTab(k)}
            >
              {t(`schedule.tabs.${k}`)}
            </button>
          ))}
        </div>
      )}
      {tab !== "settings" && (
        <div className="sched-nav no-print">
          {tab !== "templates" && (
            <>
          <div className="segmented__row" role="group" aria-label={t("schedule.span.label")}>
            {SPANS.map((s) => (
              <button key={s} type="button" className={`btn btn--small${span === s ? " btn--primary" : ""}`} aria-pressed={span === s} onClick={() => setSpan(s)}>
                {t(`schedule.span.${s}`)}
              </button>
            ))}
          </div>
          <div className="sched-nav__dates">
            <button type="button" className="btn btn--small" onClick={() => setOn(moveSpan(span, on, -1))} aria-label={t(`schedule.previous.${span}`)}>
              <span className="flip-rtl" aria-hidden="true">
                <Icon name="chevronRight" size={18} />
              </span>
            </button>
            <button type="button" className="btn btn--small" onClick={() => setOn(todayIso())}>
              {t("schedule.today")}
            </button>
            <button type="button" className="btn btn--small" onClick={() => setOn(moveSpan(span, on, 1))} aria-label={t(`schedule.next.${span}`)}>
              <span className="flip-rtl" aria-hidden="true">
                <Icon name="chevronLeft" size={18} />
              </span>
            </button>
            <label className="visually-hidden" htmlFor={`${id}-on`}>
              {t("schedule.pickDay")}
            </label>
            <input id={`${id}-on`} type="date" value={on} onChange={(e) => e.target.value && setOn(e.target.value)} />
          </div>
            </>
          )}
          {national && (tab === "programme" || tab === "templates") && (
            <div className="field">
              <label htmlFor={`${id}-g`}>{t("schedule.progress.gouvernorat")}</label>
              <select id={`${id}-g`} value={gouvernorat ?? ""} onChange={(e) => setGouvernorat(e.target.value ? Number(e.target.value) : null)}>
                <option value="">—</option>
                {list.map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}
      {(tab === "programme" || tab === "progress") && (
        <h2 className="sched-heading">
          {label}
          {tab === "programme" && gouvernorat !== null && <span className="muted"> · {nameOf(gouvernorat)}</span>}
        </h2>
      )}
      {tab === "programme" &&
        (gouvernorat === null ? <p className="card ops-empty">{t("schedule.pickGouvernorat")}</p> : <Programme span={span} on={on} gouvernorat={gouvernorat} />)}
      {tab === "progress" && (
        <ProgressView
          span={span}
          on={on}
          onOpen={
            lists
              ? (code) => {
                  setGouvernorat(code);
                  setTab("programme");
                }
              : null
          }
        />
      )}
      {tab === "templates" &&
        (gouvernorat === null ? <p className="card ops-empty">{t("schedule.pickGouvernorat")}</p> : <TemplatesView gouvernorat={gouvernorat} />)}
      {tab === "settings" && <SettingsView />}
    </div>
  );
}
