import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";
import { MapPanel } from "../components/LazyMap";
import { Loading } from "../components/Feedback";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { queryKeys } from "../lib/portalApi";
import type { LivePoint } from "../lib/types";
import { PageTitle } from "../components/PageTitle";

/** Refresh while the share is on: the phone sends a position at most every 20 seconds. */
export const LIVE_REFRESH_MS = 30_000;
const TOKEN = /^[A-Za-z0-9_-]{20,100}$/;

/** The token of `/live#<token>`: kept in the fragment, so it never reaches a server log or a Referer header. */
export function liveToken(hash: string): string | null {
  const token = hash.replace(/^#/, "").trim();
  return TOKEN.test(token) ? token : null;
}

const osm = (p: LivePoint) =>
  `https://www.openstreetmap.org/?mlat=${p.lat.toFixed(5)}&mlon=${p.lon.toFixed(5)}#map=17/${p.lat.toFixed(5)}/${p.lon.toFixed(5)}`;

/** Ticks every 30 s so "updated 3 minutes ago" stays true between refreshes. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), LIVE_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

/**
 * Public live location (phase B2, `/live#<token>`): a citizen shared this link with their contacts. No sign-in, no
 * name, only the positions of the share; the link stops working when the person stops it or it expires.
 */
export function LivePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { hash } = useLocation();
  const fmt = useFormat();
  const now = useNow();
  const token = liveToken(hash);
  const query = useQuery({
    queryKey: queryKeys.liveView(token ?? ""),
    queryFn: ({ signal }) => api.liveView(token ?? "", signal),
    enabled: token !== null,
    retry: false,
    refetchInterval: (q) => (q.state.data?.active ? LIVE_REFRESH_MS : false),
  });

  const head = (
    <div className="page__head">
      <PageTitle icon="videocam" tone="red">{t("live.title")}</PageTitle>
    </div>
  );
  if (token === null) {
    return (
      <div className="page page--narrow">
        {head}
        <section className="card verdict verdict--invalid" role="alert">
          <h2>{t("live.badLinkTitle")}</h2>
          <p>{t("live.badLinkBody")}</p>
        </section>
      </div>
    );
  }
  if (query.isPending) return <Loading />;
  if (query.isError) {
    const gone = isApiError(query.error) && query.error.status === 404;
    return (
      <div className="page page--narrow">
        {head}
        <section className="card verdict verdict--invalid" role="alert">
          <h2>{gone ? t("live.notFoundTitle") : t("live.errorTitle")}</h2>
          <p>{gone ? t("live.notFoundBody") : t(errorMessageKey(query.error))}</p>
          {!gone && (
            <button type="button" className="btn" onClick={() => void query.refetch()}>
              {t("common.retry")}
            </button>
          )}
        </section>
      </div>
    );
  }

  const live = query.data;
  const last = live.points.at(-1) ?? null;
  const minutes = live.updated_at ? Math.max(0, Math.floor((now - Date.parse(live.updated_at)) / 60_000)) : null;

  return (
    <div className="page page--narrow">
      {head}
      <section className={`card verdict verdict--${live.active ? "valid" : "invalid"}`} aria-live="polite">
        <h2>{live.active ? t("live.activeTitle") : t("live.endedTitle")}</h2>
        <p>
          {live.active
            ? t("live.activeBody", { until: fmt.dateTime(live.expires_at) })
            : live.stopped_at
              ? t("live.stoppedBody", { at: fmt.dateTime(live.stopped_at) })
              : t("live.expiredBody", { at: fmt.dateTime(live.expires_at) })}
        </p>
        {minutes !== null && <p>{t("live.updated", { count: minutes })}</p>}
        {live.battery !== null && <p>{t("live.battery", { level: live.battery })}</p>}
      </section>

      {last ? (
        <section className="card" aria-labelledby="live-map-title">
          <h2 id="live-map-title">{t("live.lastPosition")}</h2>
          <MapPanel
            center={{ lat: last.lat, lon: last.lon }}
            zoom={16}
            followCenter
            ariaLabel={t("live.mapLabel")}
            markers={[{ id: "last", lat: last.lat, lon: last.lon, kind: "alarm", label: t("live.lastPosition") }]}
            circle={last.accuracy_m ? { center: { lat: last.lat, lon: last.lon }, meters: last.accuracy_m } : null}
          />
          <dl className="fields">
            <dt>{t("live.at")}</dt>
            <dd>{fmt.dateTime(last.at)}</dd>
            <dt>{t("live.coordinates")}</dt>
            <dd dir="ltr">
              {last.lat.toFixed(5)}, {last.lon.toFixed(5)}
            </dd>
            {last.accuracy_m !== null && (
              <>
                <dt>{t("live.accuracy")}</dt>
                <dd>{t("live.meters", { count: Math.ceil(last.accuracy_m) })}</dd>
              </>
            )}
          </dl>
          <p>
            <a className="btn" href={osm(last)} target="_blank" rel="noreferrer noopener">
              {t("live.openMap")}
            </a>
          </p>
        </section>
      ) : (
        <section className="card">
          <p>{t("live.noPosition")}</p>
        </section>
      )}

      <section className="card" aria-labelledby="live-help-title">
        <h2 id="live-help-title">{t("live.helpTitle")}</h2>
        <p>{t("live.helpBody")}</p>
        <p>
          <a className="btn btn--danger" href="tel:198">
            {t("live.call198")}
          </a>
        </p>
        <p className="muted">{t("live.privacy")}</p>
      </section>
    </div>
  );
}
