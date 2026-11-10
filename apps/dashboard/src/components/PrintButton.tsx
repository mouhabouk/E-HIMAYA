// Printing a page of the dashboard (Yamen, 2026-11-10: a print button wherever a page is read on paper). The browser
// prints the page alone: the menus, banners and buttons are hidden and a header names the Office, the page and who
// printed it when (styles/global.css «Printing», PrintHeader in Layout).
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useFormat } from "../lib/hooks";
import { Icon } from "./Icon";

export function PrintButton() {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className="btn btn--ghost btn--small no-print print-button"
      onClick={() => window.print()}
    >
      <Icon name="print" size={18} />
      {t("print.button")}
    </button>
  );
}

/** Shown on paper only: the Office, the platform, who printed the page and when. */
export function PrintHeader() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const fmt = useFormat();
  return (
    <div className="print-only print-head" aria-hidden="true">
      <img src="/brand/logo.png" alt="" width="40" height="40" />
      <div>
        <strong>{t("print.office")}</strong>
        <div>{t("app.name")}</div>
      </div>
      <div className="print-head__meta">
        {t("print.printedBy", {
          name: user?.identity.name ?? "—",
          at: fmt.dateTime(new Date().toISOString()),
        })}
      </div>
    </div>
  );
}
