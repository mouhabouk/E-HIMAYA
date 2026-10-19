import { useTranslation } from "react-i18next";
import type { ReportStatus } from "../lib/types";

export function StatusChip({ status }: { status: ReportStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`chip chip--${status}`}>
      <span className="chip__dot" aria-hidden="true" />
      {t(`status.${status}`)}
    </span>
  );
}
