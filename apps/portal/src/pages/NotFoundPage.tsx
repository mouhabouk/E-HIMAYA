import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <section className="card notice">
      <h1>{t("notFound.title")}</h1>
      <p>{t("notFound.body")}</p>
      <Link className="btn btn--primary" to="/">
        {t("notFound.home")}
      </Link>
    </section>
  );
}
