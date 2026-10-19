import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { Loading } from "../components/Feedback";
import { useServices } from "../context/services";

/** OIDC redirect target: exchanges the authorization code (PKCE) and returns to the requested page. */
export function CallbackPage() {
  const { t } = useTranslation();
  const { auth } = useServices();
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    auth
      .completeSignIn()
      .then((returnTo) => {
        if (active) void navigate(returnTo, { replace: true });
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [auth, navigate]);

  if (!failed) return <Loading label={t("auth.completing")} />;
  return (
    <main id="main" className="standalone">
      <section className="card notice" role="alert">
        <h1>{t("auth.callbackErrorTitle")}</h1>
        <p>{t("auth.callbackError")}</p>
        <a className="btn btn--primary" href="/">
          {t("auth.retry")}
        </a>
      </section>
    </main>
  );
}
