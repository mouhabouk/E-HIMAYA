import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router";
import { OrgStatusBadge, RoleBadge } from "../../components/Badges";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { isApiError } from "../../lib/api";
import { queryKeys } from "../../lib/portalApi";
import { blockedReason, can, type OrgAction } from "../../lib/roles";
import type { Organization } from "../../lib/types";

export interface OrgContext {
  org: Organization;
  /** Whether the caller's role and the institution's status allow an action. */
  can: (action: OrgAction) => boolean;
  /** Why an action is unavailable ("role" | "status"), null when allowed. */
  blocked: (action: OrgAction) => "role" | "status" | null;
}

export function useOrg(): OrgContext {
  return useOutletContext<OrgContext>();
}

export const TABS = [
  { path: "", key: "overview" },
  { path: "card", key: "card" },
  { path: "team", key: "team" },
  { path: "hazmat", key: "hazmat" },
  { path: "equipment", key: "equipment" },
  { path: "map", key: "map" },
  { path: "documents", key: "documents" },
  { path: "members", key: "members" },
  { path: "reports", key: "reports" },
  { path: "certificate", key: "certificate" },
] as const;

/** Workspace of one institution: header, section navigation and the selected section. */
export function OrgWorkspace() {
  const { t } = useTranslation();
  const { orgId = "" } = useParams();
  const { api } = useServices();
  const query = useQuery({ queryKey: queryKeys.org(orgId), queryFn: ({ signal }) => api.org(orgId, signal) });

  if (query.isPending) return <Loading />;
  if (query.isError) {
    if (isApiError(query.error) && (query.error.code === "org_not_found" || query.error.status === 404)) {
      return (
        <section className="card notice" role="alert">
          <h1>{t("workspace.notFoundTitle")}</h1>
          <p>{t("errors.org_not_found")}</p>
          <Link className="btn" to="/orgs/mine">
            {t("nav.myOrgs")}
          </Link>
        </section>
      );
    }
    return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;
  }

  const org = query.data;
  const ctx: OrgContext = {
    org,
    can: (action) => can(org.my_role, org.status, action),
    blocked: (action) => blockedReason(org.my_role, org.status, action),
  };
  const base = `/orgs/${encodeURIComponent(org.id)}`;
  return (
    <div className="page workspace">
      <div className="page__head">
        <div>
          <p className="muted breadcrumb">
            <Link to="/orgs/mine">{t("nav.myOrgs")}</Link>
          </p>
          <h1>{org.name}</h1>
        </div>
        <div className="org-item__badges">
          <OrgStatusBadge status={org.status} />
          <span className="visually-hidden">{t("workspace.yourRole")}</span>
          <RoleBadge role={org.my_role} />
        </div>
      </div>
      <nav className="tabs" aria-label={t("workspace.sections")}>
        {TABS.map((tab) => (
          <NavLink key={tab.key} to={tab.path ? `${base}/${tab.path}` : base} end={tab.path === ""}>
            {t(`workspace.tabs.${tab.key}`)}
          </NavLink>
        ))}
      </nav>
      <div className="workspace__body">
        <Outlet context={ctx} />
      </div>
    </div>
  );
}

/** Explanation shown in place of an action the caller cannot use. */
export function BlockedNote({ action }: { action: OrgAction }) {
  const { t } = useTranslation();
  const { org, blocked } = useOrg();
  const reason = blocked(action);
  if (!reason) return null;
  return (
    <p className="muted blocked-note">
      {reason === "role"
        ? t("workspace.roleRequired", { role: t(`roles.${org.my_role}`) })
        : t("workspace.notActive", { status: t(`orgStatus.${org.status}`) })}
    </p>
  );
}
