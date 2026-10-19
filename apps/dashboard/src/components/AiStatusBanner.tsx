import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAiStatus } from "../lib/hooks";
import { aiDegraded } from "../lib/priority";

/** Tells operators when scores come from the rules only (no AI service, or a model is down). */
export function AiStatusBanner() {
  const { t } = useTranslation();
  const status = useAiStatus();
  const degraded = aiDegraded(status.data);
  if (!degraded) return null;
  return (
    <div className="alert alert--warn ai-banner" role="status">
      <p>{t(`ai.banner.${degraded}`)}</p>
      <Link to="/settings/ai">{t("ai.banner.link")}</Link>
    </div>
  );
}
