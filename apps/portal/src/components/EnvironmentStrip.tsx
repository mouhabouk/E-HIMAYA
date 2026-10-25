import { useTranslation } from "react-i18next";
import { useEnvironment } from "../lib/hooks";

/**
 * Backlog G3: a thin amber strip above the header while the server holds test data (development, field pilot,
 * exercise), so a test entry is never taken for a real one. Nothing in production.
 */
export function EnvironmentStrip() {
  const { t } = useTranslation();
  const banner = useEnvironment().data?.banner;
  if (!banner) return null;
  return (
    <div className="env-strip" role="note" data-testid="environment-strip">
      <span className="env-strip__tag">SIM</span>
      <span>{t(`environment.${banner}`)}</span>
    </div>
  );
}
