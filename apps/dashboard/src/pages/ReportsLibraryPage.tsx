import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { DownloadButton } from "../components/OrgBits";
import { AreaTabs, CategorySelect, GouvernoratSelect, LoadMore, MutationError } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { addDays, isIsoDate, isoDate } from "../lib/analytics";
import { useDebounced, useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { p8Keys } from "../lib/phase8Api";
import {
  LIBRARY_REPORT_KINDS,
  LIBRARY_REPORT_STATUSES,
  REPORT_FORMATS,
  type LibraryReport,
  type LibraryReportBody,
  type LibraryReportKind,
  type LibraryReportQuery,
  type LibraryReportStatus,
  type ReportFormat,
} from "../lib/phase8Types";
import { canCreateReports, canManageSchedules } from "../lib/roles";
import { CATEGORIES, type Category } from "../lib/types";
import { LANGUAGES, type Language } from "../i18n";

/** Tabs of the reports area (library, schedules). */
export function ReportsLibraryTabs() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const tabs = [{ to: "/reports-library", label: t("library.reports.tabs.reports"), end: true }];
  if (canManageSchedules(user?.identity.roles ?? []))
    tabs.push({ to: "/reports-library/schedules", label: t("library.reports.tabs.schedules"), end: false });
  return <AreaTabs label={t("library.reports.tabs.label")} tabs={tabs} />;
}

export function ReportStatusTag({ status }: { status: LibraryReportStatus }) {
  const { t } = useTranslation();
  return <span className={`tag tag--report-${status}`}>{t(`library.reports.status.${status}`)}</span>;
}

/** Kinds that need a linked object: incidents for summaries and after-action reviews, a run for scenarios. */
const NEEDS_INCIDENT: readonly LibraryReportKind[] = ["incident_summary", "after_action"];

export interface ReportFormState {
  kind: LibraryReportKind;
  title: string;
  from: string;
  to: string;
  gouvernorats: number[];
  category: Category | null;
  incidentId: string;
  scenarioId: string;
  format: ReportFormat;
  lang: Language;
}

/** Form state prefilled from the URL (analytics "export", a scenario, an incident). */
export function reportFormFromParams(params: URLSearchParams, lang: Language, today = new Date()): ReportFormState {
  const kind = params.get("kind");
  const to = isIsoDate(params.get("to")) ? (params.get("to") as string) : isoDate(today);
  const from = isIsoDate(params.get("from")) ? (params.get("from") as string) : addDays(to, -29);
  const g = Number(params.get("gouvernorat"));
  const category = params.get("category");
  return {
    kind: (LIBRARY_REPORT_KINDS as readonly string[]).includes(kind ?? "") ? (kind as LibraryReportKind) : "period_summary",
    title: (params.get("title") ?? "").slice(0, 200),
    from,
    to,
    gouvernorats: Number.isInteger(g) && g > 0 ? [g] : [],
    category: (CATEGORIES as readonly string[]).includes(category ?? "") ? (category as Category) : null,
    incidentId: params.get("incident") ?? "",
    scenarioId: params.get("scenario") ?? "",
    format: "pdf",
    lang,
  };
}

export function reportBody(f: ReportFormState): { body: LibraryReportBody | null; errors: Partial<Record<string, true>> } {
  const errors: Partial<Record<string, true>> = {};
  if (!f.title.trim()) errors.title = true;
  if (!isIsoDate(f.from) || !isIsoDate(f.to) || f.from > f.to) errors.period = true;
  if (NEEDS_INCIDENT.includes(f.kind) && !f.incidentId.trim()) errors.incident = true;
  if (f.kind === "scenario" && !f.scenarioId.trim()) errors.scenario = true;
  if (f.kind === "gouvernorat_summary" && f.gouvernorats.length === 0) errors.gouvernorats = true;
  if (Object.keys(errors).length > 0) return { body: null, errors };
  const filters: LibraryReportBody["filters"] = {};
  if (f.category) filters.category = f.category;
  if (NEEDS_INCIDENT.includes(f.kind)) filters.incident_id = f.incidentId.trim();
  if (f.kind === "scenario") filters.scenario_id = f.scenarioId.trim();
  return {
    body: {
      kind: f.kind,
      title: f.title.trim(),
      period_from: f.from,
      period_to: f.to,
      gouvernorats: f.gouvernorats,
      filters,
      format: f.format,
      lang: f.lang,
    },
    errors,
  };
}

function ReportForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const base = useId();
  const national = user?.identity.national ?? false;
  const own = user?.identity.gouvernoratCode ?? null;
  const [form, setForm] = useState<ReportFormState>(() => {
    const f = reportFormFromParams(params, lang);
    return !national && own !== null ? { ...f, gouvernorats: [own] } : f;
  });
  const [touched, setTouched] = useState(false);
  const { body, errors } = reportBody(form);
  const set = (patch: Partial<ReportFormState>) => setForm((f) => ({ ...f, ...patch }));
  const create = useMutation({
    mutationFn: (b: LibraryReportBody) => api.createLibraryReport(b),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p8Keys.libraryReportsAll });
      onClose();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (body) create.mutate(body);
  };
  const err = (k: string) => touched && errors[k];
  return (
    <form className="card ops-form report-form" onSubmit={submit} noValidate aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{t("library.reports.form.title")}</h2>
      <div className="fields-row">
        <div className="field">
          <label htmlFor={`${base}-kind`}>{t("library.reports.kind")}</label>
          <select id={`${base}-kind`} value={form.kind} onChange={(e) => set({ kind: e.target.value as LibraryReportKind })}>
            {LIBRARY_REPORT_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`library.reports.kinds.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={`field${err("title") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-title`}>{t("library.reports.titleField")}</label>
          <input
            id={`${base}-title`}
            dir="auto"
            maxLength={200}
            value={form.title}
            aria-invalid={err("title") ? true : undefined}
            onChange={(e) => set({ title: e.target.value })}
          />
          {err("title") && <p className="field__error">{t("library.reports.form.titleRequired")}</p>}
        </div>
      </div>
      <div className="fields-row">
        <div className={`field${err("period") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-from`}>{t("analytics.from")}</label>
          <input id={`${base}-from`} type="date" value={form.from} onChange={(e) => set({ from: e.target.value })} />
        </div>
        <div className={`field${err("period") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-to`}>{t("analytics.to")}</label>
          <input id={`${base}-to`} type="date" value={form.to} onChange={(e) => set({ to: e.target.value })} />
        </div>
        {national ? (
          <GouvernoratSelect
            value={form.gouvernorats[0] ?? null}
            onChange={(g) => set({ gouvernorats: g === null ? [] : [g] })}
            label={t("analytics.gouvernorat")}
            allLabel={t("analytics.national")}
          />
        ) : null}
        <CategorySelect
          value={form.category}
          onChange={(c) => set({ category: (c as Category | null) ?? null })}
          label={t("analytics.category")}
          allLabel={t("analytics.allCategories")}
        />
      </div>
      {err("period") && <p className="field__error">{t("library.reports.form.periodInvalid")}</p>}
      {err("gouvernorats") && <p className="field__error">{t("library.reports.form.gouvernoratRequired")}</p>}
      {NEEDS_INCIDENT.includes(form.kind) && (
        <div className={`field${err("incident") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-incident`}>{t("library.reports.form.incident")}</label>
          <input
            id={`${base}-incident`}
            dir="ltr"
            className="code"
            value={form.incidentId}
            aria-invalid={err("incident") ? true : undefined}
            onChange={(e) => set({ incidentId: e.target.value })}
          />
          {err("incident") && <p className="field__error">{t("library.reports.form.incidentRequired")}</p>}
        </div>
      )}
      {form.kind === "scenario" && (
        <div className={`field${err("scenario") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-scenario`}>{t("library.reports.form.scenario")}</label>
          <input
            id={`${base}-scenario`}
            dir="ltr"
            className="code"
            value={form.scenarioId}
            aria-invalid={err("scenario") ? true : undefined}
            onChange={(e) => set({ scenarioId: e.target.value })}
          />
          {err("scenario") && <p className="field__error">{t("library.reports.form.scenarioRequired")}</p>}
        </div>
      )}
      <div className="fields-row">
        <fieldset className="segmented">
          <legend>{t("library.reports.format")}</legend>
          {REPORT_FORMATS.map((f) => (
            <label key={f} className="segmented__item">
              <input type="radio" name={`${base}-format`} checked={form.format === f} onChange={() => set({ format: f })} />
              <span>{t(`library.reports.formats.${f}`)}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="segmented">
          <legend>{t("library.reports.lang")}</legend>
          {LANGUAGES.map((l) => (
            <label key={l} className="segmented__item">
              <input type="radio" name={`${base}-lang`} checked={form.lang === l} onChange={() => set({ lang: l })} />
              <span lang={l}>{t(`languages.${l}`)}</span>
            </label>
          ))}
        </fieldset>
      </div>
      <p className="muted">{t("library.reports.form.minCellNote")}</p>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={create.isPending}>
          {create.isPending ? t("ops.working") : t("library.reports.form.submit")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
      {create.isError && <MutationError error={create.error} />}
    </form>
  );
}

function ReadyNotices() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: p8Keys.reportNotifications,
    queryFn: ({ signal }) => api.reportNotifications(signal),
    refetchInterval: 60_000,
  });
  const read = useMutation({
    mutationFn: (id: string) => api.markReportNotificationRead(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: p8Keys.reportNotifications }),
  });
  const unread = (query.data?.items ?? []).filter((n) => !n.read_at);
  if (unread.length === 0) return null;
  return (
    <section className="alert alert--info" aria-labelledby="ready-notices">
      <h2 id="ready-notices">{t("library.reports.notices", { n: fmt.number(unread.length) })}</h2>
      <ul>
        {unread.map((n) => (
          <li key={n.id}>
            <span dir="auto">{n.title}</span> · <time dateTime={n.created_at}>{fmt.dateTime(n.created_at)}</time>{" "}
            <button type="button" className="btn btn--small btn--ghost" onClick={() => read.mutate(n.id)}>
              {t("library.reports.markRead")}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ReportRow({ r }: { r: LibraryReport }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  return (
    <tr>
      <th scope="row" dir="auto">
        {r.title}
        {r.schedule_id && <span className="tag">{t("library.reports.scheduled")}</span>}
      </th>
      <td>{t(`library.reports.kinds.${r.kind}`)}</td>
      <td>
        {fmt.date(r.period_from)} – {fmt.date(r.period_to)}
      </td>
      <td>
        {r.gouvernorats.length === 0
          ? t("analytics.national")
          : r.gouvernorats.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator"))}
      </td>
      <td>
        {t(`library.reports.formats.${r.format}`)}
        {r.lang ? ` · ${r.lang.toUpperCase()}` : ""}
      </td>
      <td>
        <ReportStatusTag status={r.status} />
        {r.status === "failed" && r.error && <span className="cell-sub">{r.error}</span>}
      </td>
      <td>{fmt.dateTime(r.created_at)}</td>
      <td>
        {r.status === "ready" ? (
          <DownloadButton fetchLink={() => api.libraryReportLink(r.id)} label={r.title} />
        ) : (
          <span className="muted">—</span>
        )}
        {r.sha256 && (
          <span className="cell-sub hash code" dir="ltr" title={r.sha256}>
            sha256 {r.sha256.slice(0, 12)}…
          </span>
        )}
      </td>
    </tr>
  );
}

/** Reports repository (FR-C-21): search and filters, status, download, and the report form ("export"). */
export function ReportsLibraryPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const [params, setParams] = useSearchParams();
  const ids = { q: useId(), kind: useId(), status: useId(), from: useId(), to: useId() };
  const national = user?.identity.national ?? false;
  const [text, setText] = useState("");
  const q = useDebounced(text, 350);
  const [filters, setFilters] = useState<Omit<LibraryReportQuery, "q">>({ kind: "", status: "", from: "", to: "", gouvernorat: null });
  const query = useMemo(() => ({ ...filters, q }), [filters, q]);
  const list = useInfiniteQuery({
    queryKey: p8Keys.libraryReports(query),
    queryFn: ({ pageParam, signal }) => api.libraryReports(query, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // Generation runs in a worker: poll while something is still being produced.
    refetchInterval: (q2) =>
      q2.state.data?.pages.some((p) => p.items.some((r) => r.status === "queued" || r.status === "running")) ? 5_000 : false,
  });
  const rows = list.data?.pages.flatMap((p) => p.items) ?? [];
  const creating = params.get("new") === "1";
  const canCreate = canCreateReports(user?.identity.roles ?? []);
  const closeForm = () => setParams(new URLSearchParams(), { replace: true });
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch }));
  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("library.reports.title")}</h1>
        {canCreate && !creating && (
          <Link className="btn btn--primary" to="/reports-library?new=1">
            {t("library.reports.new")}
          </Link>
        )}
      </div>
      <ReportsLibraryTabs />
      <ReadyNotices />
      {creating && canCreate && <ReportForm key={params.toString()} onClose={closeForm} />}
      <div className="filters" role="group" aria-label={t("library.reports.filters")}>
        <div className="filters__row">
          <div className="field field--search">
            <label htmlFor={ids.q}>{t("library.reports.search")}</label>
            <input id={ids.q} type="search" dir="auto" maxLength={200} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={ids.kind}>{t("library.reports.kind")}</label>
            <select id={ids.kind} value={filters.kind} onChange={(e) => set({ kind: e.target.value as LibraryReportKind | "" })}>
              <option value="">{t("library.reports.allKinds")}</option>
              {LIBRARY_REPORT_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`library.reports.kinds.${k}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.status}>{t("library.reports.statusField")}</label>
            <select
              id={ids.status}
              value={filters.status}
              onChange={(e) => set({ status: e.target.value as LibraryReportStatus | "" })}
            >
              <option value="">{t("library.reports.allStatuses")}</option>
              {LIBRARY_REPORT_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`library.reports.status.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.from}>{t("analytics.from")}</label>
            <input id={ids.from} type="date" value={filters.from} onChange={(e) => set({ from: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor={ids.to}>{t("analytics.to")}</label>
            <input id={ids.to} type="date" value={filters.to} onChange={(e) => set({ to: e.target.value })} />
          </div>
          {national && (
            <GouvernoratSelect
              value={filters.gouvernorat ?? null}
              onChange={(g) => set({ gouvernorat: g })}
              label={t("analytics.gouvernorat")}
              allLabel={t("filters.allGouvernorats")}
            />
          )}
        </div>
      </div>
      <p className="muted" role="status" aria-live="polite">
        {list.isFetching ? t("common.loading") : t("library.reports.count", { n: fmt.number(rows.length) })}
      </p>
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.isSuccess && rows.length === 0 && <p className="muted">{t("library.reports.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("library.reports.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("library.reports.titleField")}</th>
                <th scope="col">{t("library.reports.kind")}</th>
                <th scope="col">{t("library.reports.period")}</th>
                <th scope="col">{t("analytics.gouvernorat")}</th>
                <th scope="col">{t("library.reports.format")}</th>
                <th scope="col">{t("library.reports.statusField")}</th>
                <th scope="col">{t("library.reports.createdAt")}</th>
                <th scope="col">{t("library.reports.download")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <ReportRow key={r.id} r={r} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore hasNext={list.hasNextPage} loading={list.isFetchingNextPage} onMore={() => void list.fetchNextPage()} />
    </div>
  );
}
