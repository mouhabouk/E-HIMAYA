import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Badge, OrgStatusBadge, RoleBadge } from "../components/Badges";
import { ErrorBox, ForwardIcon, Loading } from "../components/Feedback";
import { IconTile } from "../components/Icon";
import { useServices } from "../context/services";
import { useFormat } from "../lib/hooks";
import { queryKeys } from "../lib/portalApi";
import { PageTitle } from "../components/PageTitle";

/** "My institutions" (`GET /orgs/mine`). */
export function MyOrgsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useQuery({ queryKey: queryKeys.myOrgs, queryFn: ({ signal }) => api.myOrgs(signal) });

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="apartment" tone="navy">{t("myOrgs.title")}</PageTitle>
        <Link className="btn btn--primary" to="/orgs/new">
          {t("myOrgs.register")}
        </Link>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.length === 0 ? (
        <section className="card notice">
          <h2>{t("myOrgs.emptyTitle")}</h2>
          <p>{t("myOrgs.emptyBody")}</p>
        </section>
      ) : (
        <ul className="org-list">
          {query.data.map((o) => (
            <li key={o.id} className="card org-item">
              <IconTile name="apartment" tone="navy" soft />
              <div className="org-item__main">
                <h2>
                  <Link to={`/orgs/${encodeURIComponent(o.id)}`}>{o.name}</Link>
                </h2>
                <p className="muted">{t(`kinds.${o.kind}`)}</p>
              </div>
              <div className="org-item__badges">
                <OrgStatusBadge status={o.status} />
                <RoleBadge role={o.my_role} />
                {o.alerts_count > 0 ? (
                  <Badge tone="danger">{t("myOrgs.alerts", { n: fmt.number(o.alerts_count) })}</Badge>
                ) : (
                  <Badge tone="ok">{t("myOrgs.noAlerts")}</Badge>
                )}
              </div>
              <Link className="btn" to={`/orgs/${encodeURIComponent(o.id)}`} aria-label={t("myOrgs.open", { name: o.name })}>
                {t("common.open")}
                <ForwardIcon />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
