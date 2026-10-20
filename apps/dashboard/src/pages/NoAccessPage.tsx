import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { LanguageMenu } from "../components/Layout";

export type NoAccessReason = "noRole" | "noScope" | "liveForbidden";

export function NoAccessPage({ reason, embedded = false }: { reason: NoAccessReason; embedded?: boolean }) {
  const { t } = useTranslation();
  const { signOut, user } = useAuth();
  const body = (
    <section className="card notice" aria-labelledby="no-access-title">
      <h1 id="no-access-title">{t("noAccess.title")}</h1>
      <p>{t(`noAccess.${reason}`)}</p>
      <p className="muted">{t("noAccess.contact")}</p>
      {user && (
        <button type="button" className="btn btn--primary" onClick={() => void signOut()}>
          {t("header.logout")}
        </button>
      )}
    </section>
  );
  if (embedded) return body;
  return (
    <main id="main" className="standalone">
      <div className="standalone__tools">
        <LanguageMenu />
      </div>
      {body}
    </main>
  );
}
