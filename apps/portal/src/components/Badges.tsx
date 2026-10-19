import { useTranslation } from "react-i18next";
import type {
  CertificateStatus,
  MaintenanceStatus,
  OrgRole,
  OrgStatus,
  ReportStatus,
  TrainingStatus,
  VersionStatus,
} from "../lib/types";

type Tone = "ok" | "warn" | "danger" | "info" | "neutral";

/** Coloured pill, always with a text label (never colour alone). */
export function Badge({ tone, children }: { tone: Tone; children: string }) {
  return (
    <span className={`badge badge--${tone}`}>
      <span className="badge__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

const ORG_TONE: Record<OrgStatus, Tone> = { pending_review: "info", active: "ok", rejected: "danger", suspended: "warn" };
export function OrgStatusBadge({ status }: { status: OrgStatus }) {
  const { t } = useTranslation();
  return <Badge tone={ORG_TONE[status]}>{t(`orgStatus.${status}`)}</Badge>;
}

export function RoleBadge({ role }: { role: OrgRole }) {
  const { t } = useTranslation();
  return <Badge tone="neutral">{t(`roles.${role}`)}</Badge>;
}

const TRAINING_TONE: Record<TrainingStatus, Tone> = { valid: "ok", expiring: "warn", expired: "danger", unknown: "neutral" };
export function TrainingBadge({ status }: { status: TrainingStatus }) {
  const { t } = useTranslation();
  return <Badge tone={TRAINING_TONE[status]}>{t(`training.${status}`)}</Badge>;
}

const MAINTENANCE_TONE: Record<MaintenanceStatus, Tone> = { ok: "ok", due_soon: "warn", overdue: "danger", unknown: "neutral" };
export function MaintenanceBadge({ status }: { status: MaintenanceStatus }) {
  const { t } = useTranslation();
  return <Badge tone={MAINTENANCE_TONE[status]}>{t(`maintenance.${status}`)}</Badge>;
}

const VERSION_TONE: Record<VersionStatus, Tone> = { uploading: "info", verifying: "info", stored: "ok", rejected: "danger" };
export function VersionStatusBadge({ status }: { status: VersionStatus }) {
  const { t } = useTranslation();
  return <Badge tone={VERSION_TONE[status]}>{t(`versionStatus.${status}`)}</Badge>;
}

const CERT_TONE: Record<CertificateStatus, Tone> = { draft: "neutral", submitted: "info", approved: "ok", rejected: "danger" };
export function CertificateStatusBadge({ status }: { status: CertificateStatus }) {
  const { t } = useTranslation();
  return <Badge tone={CERT_TONE[status]}>{t(`certificateStatus.${status}`)}</Badge>;
}

/** Report status chip with the phase 2 official labels (same colours as the dashboard). */
export function StatusChip({ status }: { status: ReportStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`chip chip--${status}`}>
      <span className="chip__dot" aria-hidden="true" />
      {t(`status.${status}`)}
    </span>
  );
}
