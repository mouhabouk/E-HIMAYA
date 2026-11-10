// covers: OS2 (Yamen 2026-11-10, docs/phase-os2/design-os2.md §4): the room agent's guide. A report's life from the
// call to the closure, stage by stage (what is recorded, who decides), the statuses, the claim deadlines read from
// the national settings, and the procedure of the guided call-taking card.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { IconTile, type IconName, type Tone } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { useAuth } from "../context/auth";
import { p9Keys } from "../lib/phase9Api";
import { canEnterReports } from "../lib/roles";

const STAGES: { key: string; icon: IconName; tone: Tone }[] = [
  { key: "intake", icon: "call", tone: "red" },
  { key: "record", icon: "description", tone: "navy" },
  { key: "analysis", icon: "smartToy", tone: "purple" },
  { key: "deadline", icon: "schedule", tone: "amber" },
  { key: "claim", icon: "verified", tone: "navy" },
  { key: "dispatch", icon: "localShipping", tone: "red" },
  { key: "closure", icon: "check", tone: "green" },
  { key: "after", icon: "insights", tone: "teal" },
];
const STATUSES = ["received", "in_progress", "intervened", "ongoing", "closed"] as const;
const STATUS_TONE: Record<string, Tone> = {
  received: "red",
  in_progress: "amber",
  intervened: "navy",
  ongoing: "purple",
  closed: "green",
};
const BANDS = ["critical", "high", "normal", "low"] as const;
// Defaults of the national settings (services/api/app/modules/settings/domain.py), shown when they cannot be read.
const DEFAULT_THRESHOLDS: Record<string, number> = { critical: 85, high: 70, normal: 40 };
const DEFAULT_DELAYS: Record<string, number> = { critical: 60, high: 90, normal: 120, low: 180 };

function list(t: (k: string, o: { returnObjects: true }) => unknown, key: string): string[] {
  const v = t(key, { returnObjects: true });
  return Array.isArray(v) ? (v as string[]) : [];
}

export function RoomGuidePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const settings = useQuery({
    queryKey: p9Keys.settings,
    queryFn: ({ signal }) => api.platformSettings(signal),
    staleTime: 300_000,
  });
  const value = (key: string) => settings.data?.find((s) => s.key === key)?.value as Record<string, number> | undefined;
  const thresholds = value("sla.bands") ?? DEFAULT_THRESHOLDS;
  const delays = value("sla.claim_delay_s") ?? DEFAULT_DELAYS;
  return (
    <div className="page room-guide">
      <PageTitle print icon="menuBook" tone="navy">
        {t("roomGuide.title")}
      </PageTitle>
      <p className="muted">{t("roomGuide.intro")}</p>
      {canEnterReports(user?.identity.roles ?? []) && (
        <p>
          <Link className="btn btn--primary" to="/reports/new">
            {t("roomGuide.enter")}
          </Link>
        </p>
      )}

      <h2 className="room-guide__h">{t("roomGuide.lifeTitle")}</h2>
      <ol className="room-guide__stages">
        {STAGES.map((s, i) => (
          <li key={s.key} className="card room-guide__stage">
            <div className="room-guide__stage-head">
              <IconTile name={s.icon} tone={s.tone} />
              <div>
                <h3>
                  <span className="room-guide__num">{i + 1}</span> {t(`roomGuide.stages.${s.key}.title`)}
                </h3>
                <div className="muted">{t(`roomGuide.stages.${s.key}.who`)}</div>
              </div>
            </div>
            <ul>
              {list(t, `roomGuide.stages.${s.key}.items`).map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            {list(t, `roomGuide.stages.${s.key}.card`).length > 0 && (
              <div className="room-guide__card-note">
                <strong>{t("roomGuide.withCard")}</strong>
                <ul>
                  {list(t, `roomGuide.stages.${s.key}.card`).map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ol>

      <div className="room-guide__row">
        <section className="card">
          <h2 className="room-guide__h">{t("roomGuide.statusesTitle")}</h2>
          <p className="room-guide__statuses">
            {STATUSES.map((s, i) => (
              <span key={s}>
                {i > 0 && <span aria-hidden="true"> {t("roomGuide.arrow")} </span>}
                <span className={`pill tone-${STATUS_TONE[s]}`}>{t(`status.${s}`)}</span>
              </span>
            ))}
          </p>
          <ul>
            {list(t, "roomGuide.statusRules").map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2 className="room-guide__h">{t("roomGuide.deadlinesTitle")}</h2>
          <table className="table">
            <thead>
              <tr>
                <th>{t("roomGuide.band")}</th>
                <th>{t("roomGuide.from")}</th>
                <th>{t("roomGuide.claimWithin")}</th>
              </tr>
            </thead>
            <tbody>
              {BANDS.map((b) => (
                <tr key={b}>
                  <td>
                    <span className={`call-card__band-pill call-card__band-pill--${b}`}>{t(`callCards.band.${b}`)}</span>
                  </td>
                  <td>{b === "low" ? t("roomGuide.below", { n: thresholds.normal }) : t("roomGuide.atLeast", { n: thresholds[b] })}</td>
                  <td>{t("roomGuide.seconds", { n: delays[b] })}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">{settings.data ? t("roomGuide.fromSettings") : t("roomGuide.defaults")}</p>
          <ul>
            {list(t, "roomGuide.deadlineRules").map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="card">
        <h2 className="room-guide__h">{t("roomGuide.cardTitle")}</h2>
        <ol className="room-guide__steps">
          {list(t, "roomGuide.cardSteps").map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ol>
        <h3>{t("roomGuide.rulesTitle")}</h3>
        <ul>
          {list(t, "roomGuide.rules").map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
        <p>
          <Link to="/call-cards">{t("roomGuide.cardsLink")}</Link>
        </p>
      </section>
    </div>
  );
}
