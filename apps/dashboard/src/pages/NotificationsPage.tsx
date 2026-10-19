import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import { CHANNELS, MESSAGE_KINDS, MESSAGE_STATUSES, type Message, type MessageKind, type MessageStatus } from "../lib/opsTypes";
import { canDraftMessage, hasReadAccess } from "../lib/roles";

/** Title in the dashboard language, Arabic when the French text is empty (the contract's fallback). */
export function localizedTitle(m: Pick<Message, "title">, lang: "ar" | "fr"): string {
  return m.title[lang] || m.title.ar;
}

export function MessageKindTag({ message }: { message: Pick<Message, "kind" | "severity"> }) {
  const { t } = useTranslation();
  if (message.kind === "alert") {
    return (
      <span className={`tag tag--severity-${message.severity ?? "low"}`}>
        {t("notify.kind.alert")}
        {message.severity && ` · ${t(`notify.severity.${message.severity}`)}`}
      </span>
    );
  }
  return <span className="tag">{t("notify.kind.info")}</span>;
}

export function MessageStatusTag({ status }: { status: MessageStatus }) {
  const { t } = useTranslation();
  return <span className={`tag tag--message-${status}`}>{t(`notify.status.${status}`)}</span>;
}

/** Who a message targets, in one line. */
export function TargetText({ message }: { message: Message }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  if (message.audience === "user") return <>{t("notify.target.user")}</>;
  const place = message.area.polygon
    ? t("notify.target.polygon")
    : message.area.gouvernorat_codes.length === 0
      ? t("notify.target.national")
      : message.area.gouvernorat_codes.map((c) => gouvernorats.nameOf(c) ?? String(c)).join(t("common.listSeparator"));
  return (
    <>
      {place}
      {message.kind === "info" && message.audience && message.audience !== "all" && (
        <span className="muted"> · {t(`notify.audience.${message.audience}`)}</span>
      )}
    </>
  );
}

export function StatsText({ message }: { message: Message }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const parts = CHANNELS.filter((c) => message.channels.includes(c)).map((c) => {
    const s = message.stats[c];
    if (!s) return t(`notify.channel.${c}`);
    return t("notify.statsLine", {
      channel: t(`notify.channel.${c}`),
      status: t(`notify.dispatch.${s.status}`, { defaultValue: s.status }),
      sent: fmt.number(s.sent),
      failed: fmt.number(s.failed),
    });
  });
  return <>{parts.join(" · ")}</>;
}

/** Active alerts in the user's scope (also shown to operators as a map layer). */
function ActiveAlerts() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const query = useQuery({ queryKey: opsKeys.activeAlerts, queryFn: ({ signal }) => api.activeAlerts(signal) });
  if (!query.data || query.data.length === 0) return null;
  return (
    <section className="card" aria-labelledby="sec-active-alerts">
      <h2 id="sec-active-alerts">{t("notify.activeAlerts", { count: query.data.length })}</h2>
      <ul className="active-alerts">
        {query.data.map((m) => (
          <li key={m.id}>
            <MessageKindTag message={m} /> <Link to={`/notifications/${encodeURIComponent(m.id)}`}>{localizedTitle(m, lang)}</Link>{" "}
            <span className="muted">
              <TargetText message={m} />
              {m.expires_at && ` · ${t("notify.until", { at: fmt.dateTime(m.expires_at) })}`}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** FR-C-17, FR-C-18: register of informational notifications and alerts, with their delivery. */
export function NotificationsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const base = useId();
  const roles = user?.identity.roles ?? [];
  const [kind, setKind] = useState<MessageKind | "">("");
  const [status, setStatus] = useState<MessageStatus | "">("");

  const query = useInfiniteQuery({
    queryKey: opsKeys.messages(kind, status),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.messages({ kind, status }, { cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("notify.title")}</h1>
        <div className="actions">
          {canDraftMessage(roles, "alert") && (
            <Link className="btn btn--primary" to="/notifications/new?kind=alert">
              {t("notify.newAlert")}
            </Link>
          )}
          {canDraftMessage(roles, "info") && (
            <Link className="btn" to="/notifications/new?kind=info">
              {t("notify.newInfo")}
            </Link>
          )}
        </div>
      </div>
      <p className="muted">{t("notify.intro")}</p>
      {(hasReadAccess(roles) || canDraftMessage(roles, "alert")) && <ActiveAlerts />}

      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-kind`}>{t("notify.filters.kind")}</label>
          <select id={`${base}-kind`} value={kind} onChange={(e) => setKind(e.target.value as MessageKind | "")}>
            <option value="">{t("notify.filters.all")}</option>
            {MESSAGE_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`notify.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-status`}>{t("notify.filters.status")}</label>
          <select id={`${base}-status`} value={status} onChange={(e) => setStatus(e.target.value as MessageStatus | "")}>
            <option value="">{t("notify.filters.all")}</option>
            {MESSAGE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`notify.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="empty">{t("notify.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("notify.register")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("notify.columns.kind")}</th>
                <th scope="col">{t("notify.columns.title")}</th>
                <th scope="col">{t("notify.columns.status")}</th>
                <th scope="col">{t("notify.columns.target")}</th>
                <th scope="col">{t("notify.columns.delivery")}</th>
                <th scope="col">{t("notify.columns.date")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td>
                    <MessageKindTag message={m} />
                  </td>
                  <td>
                    <Link to={`/notifications/${encodeURIComponent(m.id)}`} dir="auto">
                      {localizedTitle(m, lang)}
                    </Link>
                  </td>
                  <td>
                    <MessageStatusTag status={m.status} />
                  </td>
                  <td>
                    <TargetText message={m} />
                  </td>
                  <td>
                    <StatsText message={m} />
                  </td>
                  <td>
                    <time dateTime={m.published_at ?? m.created_at}>{fmt.dateTime(m.published_at ?? m.created_at)}</time>
                    <div className="cell-sub">{m.published_by ?? m.created_by ?? ""}</div>
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
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("notify.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}
