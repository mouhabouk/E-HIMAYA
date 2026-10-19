import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";
import { Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useLanguage } from "../lib/hooks";
import { hasDashboardAccess } from "../lib/roles";
import { NoAccessPage } from "../pages/NoAccessPage";

/**
 * Gate for every staff screen: redirects to Keycloak when signed out (TOTP is enforced there),
 * and shows the no-access page to accounts without a staff read role (reports or institutions) or without a
 * geographic scope.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { status, user, signIn } = useAuth();
  const location = useLocation();
  const lang = useLanguage();
  const returnTo = `${location.pathname}${location.search}${location.hash}`;

  useEffect(() => {
    if (status === "signedOut") void signIn(returnTo, lang);
  }, [status, signIn, returnTo, lang]);

  if (status === "loading") return <Loading />;
  if (status === "signedOut" || !user) return <Loading label={t("auth.redirecting")} />;
  if (!hasDashboardAccess(user.identity.roles)) return <NoAccessPage reason="noRole" />;
  if (!user.identity.hasScope) return <NoAccessPage reason="noScope" />;
  return children;
}
