// «الموارد» and «سجل الموارد» are one entry of the menu with two tabs (Yamen 2026-11-13). Each tab keeps its own
// address (/resources, /inventory), so the links and the bookmarks stay; a role opening one only sees no tab bar.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink } from "react-router";
import { useAuth } from "../context/auth";
import { canOpenInventory, canReadResources } from "../lib/roles";

export type ResourcesTab = "resources" | "inventory";

export function ResourcesTabs({ tab, children }: { tab: ResourcesTab; children: ReactNode }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  const shown: ResourcesTab[] = [
    ...(canReadResources(roles) ? (["resources"] as const) : []),
    ...(canOpenInventory(roles) ? (["inventory"] as const) : []),
  ];
  if (!shown.includes(tab) && shown[0]) return <Navigate to={`/${shown[0]}`} replace />;
  return (
    <>
      {shown.length > 1 && (
        <nav className="tabs resources-tabs" aria-label={t("nav.resources")}>
          {shown.map((k) => (
            <NavLink
              key={k}
              to={`/${k}`}
              end
              className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}
            >
              {t(`resourcesTabs.${k}`)}
            </NavLink>
          ))}
        </nav>
      )}
      {children}
    </>
  );
}
