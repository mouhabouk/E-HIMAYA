// covers: phase I2 (docs/phase-i/design-i.md §7): what the operations rooms read of the inspections of the rooms. A
// regional room reads its own room's reports, the central room reads every room's; only what the inspectorate
// disclosed is sent (the verdict, the score, the recommendations by audience). The upcoming programme is national and
// published by the inspectorate; the inspections in progress are dormant until the system administrator grants them.
// Inspections of units never reach the rooms (Yamen 2026-11-11). Every tab prints and exports its table.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { allowed, useMyFeatures } from "../lib/features";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { exportCsv, inspectionKeys, type Recommendation } from "../lib/inspectionsApi";

export type InspectionResultsTab = "results" | "upcoming" | "live";

function ExportButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  const { t } = useTranslation();
  return (
    <button type="button" className="btn btn--ghost btn--small no-print" onClick={onClick} disabled={disabled}>
      <Icon name="download" size={18} />
      {t("inspections.export")}
    </button>
  );
}

/** The tabs this caller sees: the upcoming programme nationally, the live inspections once granted. */
export function useResultTabs(): InspectionResultsTab[] {
  const { user } = useAuth();
  const access = useMyFeatures();
  const national = user?.identity.national ?? false;
  const tabs: InspectionResultsTab[] = ["results"];
  if (allowed(access, "inspection_results.upcoming", national)) tabs.push("upcoming");
  if (allowed(access, "inspection_results.live", false)) tabs.push("live");
  return tabs;
}

const PATHS: Record<InspectionResultsTab, string> = {
  results: "/inspection-results",
  upcoming: "/inspection-results/upcoming",
  live: "/inspection-results/live",
};

export function InspectionResultsPage({ tab }: { tab: InspectionResultsTab }) {
  const { t } = useTranslation();
  const tabs = useResultTabs();
  return (
    <div className="page inspections-page">
      <div className="page__head">
        <PageTitle print icon="verified" tone="navy">
          {t("inspections.results.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("inspections.results.intro")}</p>
      {tabs.length > 1 && (
        <nav className="tabs no-print" aria-label={t("inspections.tabs.label")}>
          {tabs.map((key) => (
            <NavLink
              key={key}
              to={PATHS[key]}
              end
              className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}
            >
              {t(`inspections.results.tabs.${key}`)}
            </NavLink>
          ))}
        </nav>
      )}
      {tab === "results" && <ResultsTab />}
      {tab === "upcoming" && <UpcomingTab />}
      {tab === "live" && <LiveTab />}
    </div>
  );
}

function Recommendations({ items }: { items: Recommendation[] }) {
  const { t } = useTranslation();
  if (items.length === 0) return <span className="muted">—</span>;
  return (
    <ul className="inspections-recs">
      {items.map((r) => (
        <li key={r.id}>
          {r.priority && <span className={`chip chip--insp-prio-${r.priority}`}>{t(`inspections.priority.${r.priority}`)}</span>}{" "}
          {r.text}
        </li>
      ))}
    </ul>
  );
}

function ResultsTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const q = useQuery({ queryKey: inspectionKeys.results, queryFn: ({ signal }) => api.roomResults(signal) });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} />;
  const rows = q.data;
  const exportRows = () =>
    exportCsv(
      "inspection-results",
      [
        t("inspections.columns.place"),
        t("filters.gouvernorat"),
        t("inspections.columns.kind"),
        t("inspections.columns.submittedAt"),
        t("inspections.columns.verdict"),
        t("inspections.columns.score"),
        t("inspections.recommendations"),
      ],
      rows.map((r) => [
        r.place,
        gouvernorats.nameOf(r.gouvernorat_code) ?? "",
        t(`inspections.kind.${r.kind}`),
        fmt.dateTime(r.submitted_at),
        r.verdict,
        r.score,
        r.recommendations.map((x) => x.text).join(" | "),
      ]),
    );
  return (
    <section className="card">
      <div className="inspections-head">
        <h2>{t("inspections.results.reports")}</h2>
        <ExportButton onClick={exportRows} disabled={rows.length === 0} />
      </div>
      {rows.length === 0 ? (
        <p className="empty">{t("inspections.results.none")}</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("inspections.columns.place")}</th>
              <th scope="col">{t("filters.gouvernorat")}</th>
              <th scope="col">{t("inspections.columns.kind")}</th>
              <th scope="col">{t("inspections.columns.submittedAt")}</th>
              <th scope="col">{t("inspections.columns.verdict")}</th>
              <th scope="col">{t("inspections.recommendations")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.place}</td>
                <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? "—"}</td>
                <td>{t(`inspections.kind.${r.kind}`)}</td>
                <td>{fmt.dateTime(r.submitted_at)}</td>
                <td>
                  {r.verdict || r.score !== null ? (
                    <span className="chip chip--insp-slate">
                      {r.verdict ?? ""}
                      {r.score !== null && <strong dir="ltr"> {r.score}%</strong>}
                    </span>
                  ) : (
                    <span className="muted">{t("inspections.results.notDisclosed")}</span>
                  )}
                </td>
                <td>
                  <Recommendations items={r.recommendations} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function UpcomingTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const q = useQuery({ queryKey: inspectionKeys.upcoming, queryFn: ({ signal }) => api.roomUpcoming(signal) });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} />;
  const rows = q.data;
  const exportRows = () =>
    exportCsv(
      "inspection-programme",
      [t("inspections.columns.ref"), t("inspections.columns.place"), t("filters.gouvernorat"), t("inspections.columns.date"), t("inspections.columns.kind")],
      rows.map((r) => [r.ref, r.place, gouvernorats.nameOf(r.gouvernorat_code) ?? "", fmt.date(r.on_date), t(`inspections.kind.${r.kind}`)]),
    );
  return (
    <section className="card">
      <div className="inspections-head">
        <h2>{t("inspections.results.tabs.upcoming")}</h2>
        <ExportButton onClick={exportRows} disabled={rows.length === 0} />
      </div>
      {rows.length === 0 ? (
        <p className="empty">{t("inspections.results.noUpcoming")}</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("inspections.columns.ref")}</th>
              <th scope="col">{t("inspections.columns.place")}</th>
              <th scope="col">{t("filters.gouvernorat")}</th>
              <th scope="col">{t("inspections.columns.date")}</th>
              <th scope="col">{t("inspections.columns.kind")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.ref + r.place}>
                <td dir="ltr">{r.ref}</td>
                <td>{r.place}</td>
                <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? "—"}</td>
                <td>{fmt.date(r.on_date)}</td>
                <td>{t(`inspections.kind.${r.kind}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function LiveTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const q = useQuery({
    queryKey: inspectionKeys.live,
    queryFn: ({ signal }) => api.roomLive(signal),
    refetchInterval: 30_000,
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} />;
  const rows = q.data;
  const exportRows = () =>
    exportCsv(
      "inspections-live",
      [
        t("inspections.columns.place"),
        t("filters.gouvernorat"),
        t("inspections.columns.inspector"),
        t("inspections.startedAt"),
        t("inspections.results.progress"),
      ],
      rows.map((r) => [
        r.place,
        gouvernorats.nameOf(r.gouvernorat_code) ?? "",
        r.inspector_name,
        fmt.dateTime(r.started_at),
        `${r.answered}/${r.items}`,
      ]),
    );
  return (
    <section className="card">
      <div className="inspections-head">
        <h2>{t("inspections.results.tabs.live")}</h2>
        <ExportButton onClick={exportRows} disabled={rows.length === 0} />
      </div>
      {rows.length === 0 ? (
        <p className="empty">{t("inspections.results.noLive")}</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("inspections.columns.place")}</th>
              <th scope="col">{t("filters.gouvernorat")}</th>
              <th scope="col">{t("inspections.columns.inspector")}</th>
              <th scope="col">{t("inspections.startedAt")}</th>
              <th scope="col">{t("inspections.results.progress")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.place}</td>
                <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? "—"}</td>
                <td>{r.inspector_name}</td>
                <td>{fmt.dateTime(r.started_at)}</td>
                <td>
                  <progress max={r.items} value={r.answered} aria-label={t("inspections.results.progress")} />{" "}
                  <span dir="ltr">
                    {r.answered}/{r.items}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
