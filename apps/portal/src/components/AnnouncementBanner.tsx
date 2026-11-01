import { useTranslation } from "react-i18next";
import { useAdminFeatures } from "../lib/hooks";

const LANGS = ["ar", "fr", "en"] as const;

/** Phase 5: the system administrator's message, on top of every page of the portal while they show it here. */
export function AnnouncementBanner() {
  const { i18n } = useTranslation();
  const message = useAdminFeatures().data?.announcement;
  if (!message) return null;
  const lang = LANGS.find((l) => i18n.language.startsWith(l)) ?? "ar";
  const text = message[lang].trim() || message.ar;
  return (
    <div className={`alert alert--${message.tone === "warn" ? "warn" : "info"} announcement`} role="status" dir="auto">
      {text}
    </div>
  );
}
