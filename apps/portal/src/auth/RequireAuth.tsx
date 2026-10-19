import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";
import { Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useLanguage } from "../lib/hooks";

/** Gate for the signed-in screens: redirects to Keycloak (realm ehimaya-public) when signed out. */
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
  return children;
}
