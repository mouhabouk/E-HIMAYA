import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox } from "../../components/Feedback";
import { Pill } from "../../components/Icon";
import { useServices } from "../../context/services";
import { useFormat, useGouvernorats } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import { ALERT_KINDS, REQUIREMENTS, isOneOf, type Requirement } from "../../lib/types";
import { useOrg } from "./OrgWorkspace";

/** Where each completeness item is fixed. */
export const REQUIREMENT_TAB: Readonly<Record<Requirement, string>> = {
  safety_file: "documents",
  safety_plan: "documents",
  safety_team: "team",
  training: "team",
  hazmat_sds: "hazmat",
  equipment: "equipment",
  evacuation_points: "map",
};

function alertTab(kind: string): string {
  return kind.startsWith("training") ? "team" : kind.startsWith("maintenance") ? "equipment" : "";
}

function StatusPanel() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const resubmit = useMutation({
    mutationFn: () => api.resubmit(org.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.org(org.id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.myOrgs });
    },
  });
  if (org.status === "active") return null;
  const tone = org.status === "pending_review" ? "info" : org.status === "rejected" ? "error" : "warn";
  return (
    <section className={`alert alert--${tone}`} aria-labelledby="status-title">
      <h2 id="status-title">{t(`overview.status.${org.status}.title`)}</h2>
      <p>{t(`overview.status.${org.status}.body`)}</p>
      {org.review.reason && (org.status === "rejected" || org.status === "suspended") && (
        <p>
          <strong>{t("overview.reason")}</strong> {org.review.reason}
          {org.review.at && <span className="muted"> — {fmt.dateTime(org.review.at)}</span>}
        </p>
      )}
      {org.status === "rejected" && (
        <div className="actions">
          <Link className="btn" to="card">
            {t("overview.fixCard")}
          </Link>
          {can("resubmit") ? (
            <button type="button" className="btn btn--primary" disabled={resubmit.isPending} onClick={() => resubmit.mutate()}>
              {t("overview.resubmit")}
            </button>
          ) : (
            <span className="muted">{t("overview.resubmitAdminOnly")}</span>
          )}
        </div>
      )}
      {resubmit.isError && <ErrorBox error={resubmit.error} />}
    </section>
  );
}

/** Overview: status, classification (FR-B-003), completeness checklist and alerts. */
export function OverviewTab() {
  const { t } = useTranslation();
  const { org } = useOrg();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const c = org.classification;
  const required = c.required.filter((r): r is Requirement => isOneOf(REQUIREMENTS, r));
  const missing = new Set(org.completeness.missing);
  const family = t(`family.${c.family}`);

  return (
    <div className="stack">
      <StatusPanel />
      <div className="grid-2">
        <section className="card" aria-labelledby="class-title">
          <h2 id="class-title">{t("classification.title")}</h2>
          <dl className="fields">
            <dt>{t("classification.family")}</dt>
            <dd>{family}</dd>
            <dt>{t("classification.category")}</dt>
            <dd>{c.category !== null ? t("classification.categoryN", { n: c.category }) : t("classification.noCategory")}</dd>
            <dt>{t("classification.highRise")}</dt>
            <dd>{c.high_rise ? t("common.yes") : t("common.no")}</dd>
            <dt>{t("org.kind")}</dt>
            <dd>{t(`kinds.${org.kind}`)}</dd>
            <dt>{t("org.capacity")}</dt>
            <dd>{fmt.number(org.capacity)}</dd>
            <dt>{t("org.gouvernorat")}</dt>
            <dd>{nameOf(org.gouvernorat_code) ?? t("common.notAvailable")}</dd>
          </dl>
          <p className="muted">{t("classification.computed")}</p>
          {c.provisional && (
            <div className="alert alert--warn">
              <p>{t("classification.provisional")}</p>
            </div>
          )}
        </section>

        <section className="card" aria-labelledby="complete-title">
          <h2 id="complete-title">
            {t("completeness.title")}
            {typeof org.readiness === "number" && (
              <>
                {" "}
                <Pill tone={org.readiness === 100 ? "green" : "amber"}>
                  {t("kindExtra.readiness")} {fmt.number(org.readiness)}%
                </Pill>
              </>
            )}
          </h2>
          <p className={org.completeness.ok ? "ok-text" : "muted"}>
            {org.completeness.ok ? t("completeness.ok") : t("completeness.notOk", { n: org.completeness.missing.length })}
          </p>
          <ul className="checklist">
            {required.map((r) => {
              const done = !missing.has(r);
              return (
                <li key={r} className={done ? "checklist__done" : "checklist__missing"}>
                  <span className="checklist__mark" aria-hidden="true">
                    {done ? "✓" : "!"}
                  </span>
                  <span>
                    <span className="visually-hidden">{done ? t("completeness.done") : t("completeness.missing")}: </span>
                    {t(`requirements.${r}`)}
                  </span>
                  {!done && (
                    <Link to={REQUIREMENT_TAB[r]} className="checklist__fix">
                      {t("completeness.fix")}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      <section className="card" aria-labelledby="alerts-title">
        <h2 id="alerts-title">{t("alerts.title")}</h2>
        {org.alerts.length === 0 ? (
          <p className="muted">{t("alerts.none")}</p>
        ) : (
          <ul className="alerts">
            {org.alerts.map((a, i) => {
              const known = isOneOf(ALERT_KINDS, a.kind);
              const danger = a.kind.endsWith("expired") || a.kind.endsWith("overdue");
              const tab = alertTab(a.kind);
              return (
                <li key={`${a.kind}-${a.ref ?? i}`} className={`alert alert--${danger ? "error" : "warn"}`}>
                  <span>
                    {known ? t(`alerts.kinds.${a.kind}`) : t("alerts.other")}
                    {a.since && <span className="muted"> — {t("alerts.since", { date: fmt.date(a.since) })}</span>}
                  </span>
                  {tab && (
                    <Link to={tab} className="btn btn--small">
                      {t("alerts.view")}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
