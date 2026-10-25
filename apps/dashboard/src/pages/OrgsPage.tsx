import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Pill } from "../components/Icon";
import { CertificateChip, classificationText, HazmatTag, orgKindLabel, OrgStatusChip } from "../components/OrgBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import {
  DEFAULT_ORG_FILTERS,
  orgFiltersFromSearch,
  orgFiltersToSearch,
  type OrgFilters,
} from "../lib/orgs";
import { queryKeys } from "../lib/staffApi";
import { ORG_CERTIFICATE_STATES, ORG_KINDS, ORG_STATUSES, type StaffOrg } from "../lib/types";
import { PageTitle } from "../components/PageTitle";

function OrgSearch({ value, onChange }: { value: string; onChange: (q: string) => void }) {
  const { t } = useTranslation();
  const [text, setText] = useState(value);
  const debounced = useDebounced(text, 350);
  const id = useId();
  // Push only what the user typed: an outside change of `value` (reset, back navigation) must not be undone.
  const sent = useRef(value);
  useEffect(() => {
    if (debounced === sent.current) return;
    sent.current = debounced;
    onChange(debounced);
  }, [debounced, onChange]);
  return (
    <div className="field field--search">
      <label htmlFor={id}>{t("orgs.filters.search")}</label>
      <input
        id={id}
        type="search"
        value={text}
        placeholder={t("orgs.filters.searchPlaceholder")}
        onChange={(e) => setText(e.target.value)}
        maxLength={100}
        autoComplete="off"
      />
    </div>
  );
}

function OrgFiltersBar({
  filters,
  onChange,
  onReset,
  showGouvernorat,
}: {
  filters: OrgFilters;
  onChange: (patch: Partial<OrgFilters>) => void;
  onReset: () => void;
  showGouvernorat: boolean;
}) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const ids = { status: useId(), kind: useId(), gouv: useId(), cert: useId(), hazmat: useId() };
  const [resetCount, setResetCount] = useState(0);
  return (
    <section className="filters card" aria-label={t("orgs.filters.title")}>
      <OrgSearch key={resetCount} value={filters.q} onChange={(q) => onChange({ q })} />
      <div className="filters__row">
        <div className="field">
          <label htmlFor={ids.status}>{t("orgs.filters.status")}</label>
          <select
            id={ids.status}
            value={filters.status ?? ""}
            onChange={(e) => onChange({ status: (e.target.value || null) as OrgFilters["status"] })}
          >
            <option value="">{t("orgs.filters.any")}</option>
            {ORG_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`orgs.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.kind}>{t("orgs.filters.kind")}</label>
          <select
            id={ids.kind}
            value={filters.kind ?? ""}
            onChange={(e) => onChange({ kind: (e.target.value || null) as OrgFilters["kind"] })}
          >
            <option value="">{t("orgs.filters.any")}</option>
            {ORG_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`orgs.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        {showGouvernorat && (
          <div className="field">
            <label htmlFor={ids.gouv}>{t("filters.gouvernorat")}</label>
            <select
              id={ids.gouv}
              value={filters.gouvernorat ?? ""}
              onChange={(e) => onChange({ gouvernorat: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{t("filters.allGouvernorats")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="field">
          <label htmlFor={ids.cert}>{t("orgs.filters.certificate")}</label>
          <select
            id={ids.cert}
            value={filters.certificate ?? ""}
            onChange={(e) => onChange({ certificate: (e.target.value || null) as OrgFilters["certificate"] })}
          >
            <option value="">{t("orgs.filters.any")}</option>
            {ORG_CERTIFICATE_STATES.map((c) => (
              <option key={c} value={c}>
                {t(`orgs.certificate.${c}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.hazmat}>{t("orgs.filters.hazmat")}</label>
          <select
            id={ids.hazmat}
            value={filters.hasHazmat === null ? "" : String(filters.hasHazmat)}
            onChange={(e) =>
              onChange({ hasHazmat: e.target.value === "true" ? true : e.target.value === "false" ? false : null })
            }
          >
            <option value="">{t("orgs.filters.any")}</option>
            <option value="true">{t("orgs.filters.hazmatYes")}</option>
            <option value="false">{t("orgs.filters.hazmatNo")}</option>
          </select>
        </div>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => {
            onReset();
            setResetCount((n) => n + 1);
          }}
        >
          {t("orgs.filters.reset")}
        </button>
      </div>
    </section>
  );
}

function CertificateCell({ org }: { org: StaffOrg }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <>
      <CertificateChip status={org.certificate_status} />
      {org.certificate_valid_until && (
        <span className="muted cell-sub">{t("orgs.validUntil", { date: fmt.date(org.certificate_valid_until) })}</span>
      )}
    </>
  );
}

/** FR-C-05: institutions of the user's scope, sorted by name, with filters kept in the URL. */
export function OrgsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const national = user?.identity.national ?? false;
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => {
    const f = orgFiltersFromSearch(params);
    // Outside national scope the token's gouvernorat applies: never send another one.
    return national ? f : { ...f, gouvernorat: null };
  }, [params, national]);

  const update = (patch: Partial<OrgFilters>) => setParams(orgFiltersToSearch({ ...filters, ...patch }), { replace: true });

  const query = useInfiniteQuery({
    queryKey: queryKeys.orgs(filters),
    queryFn: ({ pageParam, signal }) => api.orgs(filters, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });

  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="apartment" tone="navy">{t("orgs.title")}</PageTitle>
        <Link to="/orgs/certificates" className="btn">
          {t("orgs.queueLink")}
        </Link>
      </div>
      <p className="muted">{t("orgs.intro")}</p>
      <OrgFiltersBar
        filters={filters}
        onChange={update}
        onReset={() => setParams(orgFiltersToSearch(DEFAULT_ORG_FILTERS), { replace: true })}
        showGouvernorat={national}
      />

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("orgs.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("orgs.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("orgs.columns.name")}</th>
                <th scope="col">{t("orgs.columns.kind")}</th>
                <th scope="col">{t("orgs.columns.status")}</th>
                <th scope="col">{t("orgs.columns.gouvernorat")}</th>
                <th scope="col" className="num">
                  {t("orgs.columns.capacity")}
                </th>
                <th scope="col">{t("orgs.columns.classification")}</th>
                <th scope="col">{t("orgs.columns.hazmat")}</th>
                <th scope="col" className="num">
                  {t("orgs.columns.alerts")}
                </th>
                <th scope="col">{t("orgs.columns.certificate")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((o) => (
                <tr key={o.id}>
                  <td>
                    <Link to={`/orgs/${encodeURIComponent(o.id)}`} aria-label={t("orgs.openLabel", { name: o.name })} dir="auto">
                      {o.name}
                    </Link>
                    <span className="muted cell-sub code" dir="ltr">
                      {o.identifier}
                    </span>
                  </td>
                  <td>
                    {orgKindLabel(t, o.kind)}
                    {o.kind_review && (
                      <>
                        {" "}
                        <Pill tone="amber">{t("orgs.kindExtra.kindReview")}</Pill>
                      </>
                    )}
                  </td>
                  <td>
                    <OrgStatusChip status={o.status} />
                  </td>
                  <td>{gouvernorats.nameOf(o.gouvernorat_code) ?? t("common.notAvailable")}</td>
                  <td className="num">{o.capacity === null ? "—" : fmt.number(o.capacity)}</td>
                  <td>{classificationText(t, fmt, o.classification)}</td>
                  <td>
                    <HazmatTag count={o.hazmat_count} />
                  </td>
                  <td className="num">
                    {o.alerts_count > 0 ? (
                      <span className="tag tag--level-bad">{fmt.number(o.alerts_count)}</span>
                    ) : (
                      fmt.number(0)
                    )}
                  </td>
                  <td>
                    <CertificateCell org={o} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            aria-busy={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
      {query.isFetchNextPageError && <ErrorBox error={query.error} />}
    </div>
  );
}
