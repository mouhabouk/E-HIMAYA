import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { useDebounced, useFormat } from "../lib/hooks";
import {
  systemKeys,
  valueText,
  type ChangeEntry,
  type ChangeFilters,
  type ChangeOp,
} from "../lib/systemApi";

const OPS: ChangeOp[] = ["I", "U", "D"];

function opClass(op: ChangeOp): string {
  return `change-op change-op--${op}`;
}

/** What changed: for each column its value before and after, or «محجوب» when the value was never kept. */
function ChangeCells({ entry }: { entry: ChangeEntry }) {
  const { t } = useTranslation();
  const hidden = new Set(entry.hidden);
  return (
    <ul className="change-columns" role="list">
      {entry.columns.map((c) => (
        <li key={c}>
          <span className="code" dir="ltr">
            {c}
          </span>
          {hidden.has(c) ? (
            <span className="muted"> · {t("changes.hidden")}</span>
          ) : (
            <span dir="ltr" className="code">
              {" "}
              {entry.op !== "I" && (
                <del>{valueText(entry.old_values?.[c])}</del>
              )}
              {entry.op === "U" && " → "}
              {entry.op !== "D" && (
                <ins>{valueText(entry.new_values?.[c])}</ins>
              )}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function Actor({ entry }: { entry: ChangeEntry }) {
  const { t } = useTranslation();
  if (entry.actor_kind === "staff")
    return (
      <span>
        {entry.actor_name ?? t("common.notAvailable")}
        <br />
        <span className="muted code" dir="ltr">
          {entry.actor.split(":").pop()?.slice(0, 8)}
        </span>
      </span>
    );
  return (
    <span>
      {t(`changes.actorKinds.${entry.actor_kind}`)}
      {entry.actor_kind !== "system" && (
        <>
          <br />
          <span className="muted code" dir="ltr">
            {entry.actor}
          </span>
        </>
      )}
    </span>
  );
}

/**
 * The change journal ("mouchard", docs/phase-h/design-h5.md §2): every addition, update and deletion on the
 * platform's tables, who made it and from which request. Personal, secret and free-text values were never stored.
 */
export function ChangesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const base = useId();
  const [params] = useSearchParams();
  const [filters, setFilters] = useState<ChangeFilters>({
    schema: params.get("schema") ?? "",
    table: params.get("table") ?? "",
    op: "",
    actor: params.get("actor") ?? "",
    actor_kind: "",
    request_id: params.get("request_id") ?? "",
    row: params.get("row") ?? "",
    from: "",
    to: "",
  });
  const row = useDebounced(filters.row ?? "", 400);
  const actor = useDebounced(filters.actor ?? "", 400);
  const effective = { ...filters, row, actor };
  const summary = useQuery({
    queryKey: systemKeys.changeSummary(24),
    queryFn: ({ signal }) => api.changeSummary(24, signal),
  });
  const query = useInfiniteQuery({
    queryKey: systemKeys.changes(effective),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.changes(effective, { cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const set = (k: keyof ChangeFilters) => (e: { target: { value: string } }) =>
    setFilters((f) => ({ ...f, [k]: e.target.value }));
  const tables = summary.data?.tables ?? [];
  const schemas = [...new Set(tables.map((n) => n.split(".")[0]))];
  const count = (key: string) =>
    summary.data?.by_op.find((c) => c.key === key)?.count ?? 0;

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="historyEdu" tone="slate">
          {t("changes.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("changes.intro")}</p>

      {summary.isSuccess && (
        <ul className="kpis" role="list" aria-label={t("changes.last24h")}>
          <li className="card kpi kpi--analysis">
            <span className="kpi__label">{t("changes.total24h")}</span>
            <p className="kpi__value">{fmt.number(summary.data.total)}</p>
          </li>
          {OPS.map((op) => (
            <li key={op} className={`card kpi kpi--op-${op}`}>
              <span className="kpi__label">{t(`changes.ops.${op}`)}</span>
              <p className="kpi__value">{fmt.number(count(op))}</p>
            </li>
          ))}
          <li className="card kpi">
            <span className="kpi__label">{t("changes.tablesFollowed")}</span>
            <p className="kpi__value">{fmt.number(tables.length)}</p>
          </li>
        </ul>
      )}

      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-schema`}>{t("changes.schema")}</label>
          <select
            id={`${base}-schema`}
            value={filters.schema ?? ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, schema: e.target.value, table: "" }))
            }
          >
            <option value="">{t("changes.all")}</option>
            {schemas.map((s) => (
              <option key={s} value={s}>
                {t(`changes.schemas.${s}`, { defaultValue: s })}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-table`}>{t("changes.table")}</label>
          <select
            id={`${base}-table`}
            value={filters.table ?? ""}
            onChange={set("table")}
          >
            <option value="">{t("changes.all")}</option>
            {tables
              .filter(
                (n) => !filters.schema || n.startsWith(`${filters.schema}.`),
              )
              .map((n) => (
                <option key={n} value={n.split(".")[1]}>
                  {n}
                </option>
              ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-op`}>{t("changes.op")}</label>
          <select
            id={`${base}-op`}
            value={filters.op ?? ""}
            onChange={set("op")}
          >
            <option value="">{t("changes.all")}</option>
            {OPS.map((op) => (
              <option key={op} value={op}>
                {t(`changes.ops.${op}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-kind`}>{t("changes.by")}</label>
          <select
            id={`${base}-kind`}
            value={filters.actor_kind ?? ""}
            onChange={set("actor_kind")}
          >
            <option value="">{t("changes.all")}</option>
            {(["staff", "public", "system", "database"] as const).map((k) => (
              <option key={k} value={k}>
                {t(`changes.actorKinds.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-actor`}>{t("changes.actor")}</label>
          <input
            id={`${base}-actor`}
            dir="ltr"
            value={filters.actor ?? ""}
            onChange={set("actor")}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-row`}>{t("changes.row")}</label>
          <input
            id={`${base}-row`}
            dir="ltr"
            value={filters.row ?? ""}
            onChange={set("row")}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-rid`}>{t("systemLogs.requestId")}</label>
          <input
            id={`${base}-rid`}
            dir="ltr"
            value={filters.request_id ?? ""}
            onChange={set("request_id")}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-from`}>{t("analytics.from")}</label>
          <input
            id={`${base}-from`}
            type="date"
            value={filters.from ?? ""}
            onChange={set("from")}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-to`}>{t("analytics.to")}</label>
          <input
            id={`${base}-to`}
            type="date"
            value={filters.to ?? ""}
            onChange={set("to")}
          />
        </div>
      </div>

      {query.isPending && <Loading />}
      {query.isError && (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      )}
      {query.isSuccess && items.length === 0 && (
        <p className="muted">{t("changes.empty")}</p>
      )}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">
              {t("changes.caption")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("changes.at")}</th>
                <th scope="col">{t("changes.op")}</th>
                <th scope="col">{t("changes.table")}</th>
                <th scope="col">{t("changes.row")}</th>
                <th scope="col">{t("changes.by")}</th>
                <th scope="col">{t("changes.what")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id}>
                  <td>
                    <time dateTime={e.at}>{fmt.dateTime(e.at)}</time>
                    {e.request_id && (
                      <>
                        <br />
                        <Link
                          className="code"
                          dir="ltr"
                          to={`/system-logs?request_id=${encodeURIComponent(e.request_id)}`}
                          title={t("changes.logsOfRequest")}
                        >
                          {e.request_id.slice(0, 12)}
                        </Link>
                      </>
                    )}
                  </td>
                  <td>
                    <span className={opClass(e.op)}>
                      {t(`changes.ops.${e.op}`)}
                    </span>
                  </td>
                  <td>
                    {t(`changes.schemas.${e.schema_name}`, {
                      defaultValue: e.schema_name,
                    })}
                    <br />
                    <span className="muted code" dir="ltr">
                      {e.schema_name}.{e.table_name}
                    </span>
                  </td>
                  <td dir="ltr" className="code">
                    {Object.values(e.row_key).map(valueText).join(" / ") || "—"}
                  </td>
                  <td>
                    <Actor entry={e} />
                  </td>
                  <td>
                    <ChangeCells entry={e} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <button
          type="button"
          className="btn"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
