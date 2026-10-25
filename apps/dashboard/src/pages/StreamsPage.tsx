import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { ConfidenceBadges, SimTag, SimulationBand, streamTitle } from "../components/StreamBits";
import { AlertSoundToggle } from "../components/StreamAlertToasts";
import { useAuth } from "../context/auth";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { useStreamList } from "../lib/streamHooks";
import type { StaffStream } from "../lib/streamTypes";
import { byDanger, loadWall, pinToFreeTile, saveWall } from "../lib/wall";
import { PageTitle } from "../components/PageTitle";

/** Tabs of the «البث المباشر» section. */
export function StreamsNav() {
  const { t } = useTranslation();
  return (
    <nav className="tabs" aria-label={t("streams.nav.label")}>
      <NavLink to="/streams" end className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}>
        {t("streams.nav.live")}
      </NavLink>
      <NavLink to="/streams/wall" className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}>
        {t("streams.nav.wall")}
      </NavLink>
      <NavLink to="/streams/archive" className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}>
        {t("streams.nav.archive")}
      </NavLink>
    </nav>
  );
}

/** Gouvernorat filter, offered to national accounts only (a regional account sees its gouvernorat anyway). */
export function GouvernoratFilter({ value, onChange }: { value: number | null; onChange: (code: number | null) => void }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const id = useId();
  if (!user?.identity.national) return null;
  return (
    <div className="field">
      <label htmlFor={id}>{t("streams.filters.gouvernorat")}</label>
      <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{t("streams.filters.allGouvernorats")}</option>
        {gouvernorats.list.map((g) => (
          <option key={g.code} value={g.code}>
            {gouvernorats.nameOf(g.code)}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Coordinates({ location }: { location: StaffStream["last_location"] }) {
  const { t } = useTranslation();
  if (!location) return <span className="muted">{t("streams.noLocation")}</span>;
  return (
    <span dir="ltr" className="code">
      {location.lat.toFixed(5)}, {location.lon.toFixed(5)}
    </span>
  );
}

/** FR-A-050..052 (staff side): live streams in the user's scope, the strongest fire or smoke first. */
export function StreamsPage() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const navigate = useNavigate();
  const gouvernorats = useGouvernorats();
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const query = useStreamList({ status: "live", gouvernorat });
  const items = useMemo(
    () => (query.data?.pages.flatMap((p) => p.items) ?? []).filter((s) => s.status === "live").sort(byDanger),
    [query.data],
  );
  const anySimulated = items.some((s) => s.simulated);

  const showOnWall = (id: string) => {
    saveWall(pinToFreeTile(loadWall(), id));
    void navigate("/streams/wall");
  };

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="videocam" tone="red">{t("streams.title")}</PageTitle>
        <StreamsNav />
      </div>
      <p className="muted">{t("streams.intro")}</p>
      <div className="filters__row list-tools">
        <GouvernoratFilter value={gouvernorat} onChange={setGouvernorat} />
        <AlertSoundToggle />
      </div>
      {anySimulated && <SimulationBand />}

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("streams.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("streams.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("streams.columns.stream")}</th>
                <th scope="col">{t("streams.columns.source")}</th>
                <th scope="col">{t("streams.columns.gouvernorat")}</th>
                <th scope="col">{t("streams.columns.started")}</th>
                <th scope="col">{t("streams.columns.location")}</th>
                <th scope="col">{t("streams.columns.detections")}</th>
                <th scope="col" className="num">
                  {t("streams.columns.recordings")}
                </th>
                <th scope="col">{t("streams.columns.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => {
                const name = streamTitle(t, s);
                return (
                  <tr key={s.id} className={s.simulated ? "row--sim" : undefined}>
                    <td>
                      <NavLink to={`/streams/${encodeURIComponent(s.id)}`} dir="auto">
                        {name}
                      </NavLink>
                      {s.simulated && <SimTag />}
                    </td>
                    <td>{t(`streams.source.${s.source}`)}</td>
                    <td>{gouvernorats.nameOf(s.gouvernorat_code) ?? t("common.notAvailable")}</td>
                    <td>{s.started_at ? <time dateTime={s.started_at}>{fmt.time(s.started_at)}</time> : "—"}</td>
                    <td>
                      <Coordinates location={s.last_location} />
                    </td>
                    <td>
                      <ConfidenceBadges stream={s} />
                    </td>
                    <td className="num">{fmt.number(s.recordings_count)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--small"
                        onClick={() => showOnWall(s.id)}
                        aria-label={t("streams.showOnWallLabel", { name })}
                      >
                        {t("streams.showOnWall")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            aria-busy={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}
