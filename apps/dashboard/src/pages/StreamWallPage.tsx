import { useQuery } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { MapPoi } from "../components/MapView";
import { MapLegend } from "../components/OrgBits";
import { ConfidenceBadges, SimTag, SimulationBand, streamTitle } from "../components/StreamBits";
import { StreamPlayer } from "../components/StreamPlayer";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { ALERT_CONFIDENCE, MIN_CONFIDENCE } from "../lib/detections";
import { useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { streamKeys } from "../lib/streamsApi";
import type { StaffStream } from "../lib/streamTypes";
import { arrangeWall, loadWall, pinStream, saveWall, WALL_LAYOUTS, type WallLayout, type WallState } from "../lib/wall";
import { useStreamList } from "../lib/streamHooks";
import { Coordinates, StreamsNav } from "./StreamsPage";

/**
 * Detail of a tile's stream, read only when the tile needs it (each read is audited `stream.detail`): for the boxes of
 * a stream with detections (reloaded by `stream.alert`), or for a pinned stream that is no longer listed as live.
 */
function useTileDetail(id: string | null, row: StaffStream | null) {
  const { api } = useServices();
  const detected = row !== null && Math.max(row.max_fire_confidence ?? 0, row.max_smoke_confidence ?? 0) >= MIN_CONFIDENCE;
  return useQuery({
    queryKey: streamKeys.detail(id ?? ""),
    queryFn: ({ signal }) => api.stream(id ?? "", signal),
    enabled: id !== null && (row === null || detected),
    staleTime: 60_000,
  });
}

function isAlerting(s: StaffStream): boolean {
  return Math.max(s.max_fire_confidence ?? 0, s.max_smoke_confidence ?? 0) >= ALERT_CONFIDENCE;
}

function Tile({
  slot,
  streamId,
  pinned,
  row,
  choices,
  onPin,
}: {
  slot: number;
  streamId: string | null;
  pinned: boolean;
  row: StaffStream | null;
  choices: StaffStream[];
  onPin: (slot: number, id: string | null) => void;
}) {
  const { t } = useTranslation();
  const selectId = useId();
  const detail = useTileDetail(streamId, row);
  const stream: StaffStream | null = row ?? detail.data ?? null;
  const screen = t("streams.wall.screen", { n: slot + 1 });
  const name = stream ? streamTitle(t, stream) : null;
  const headingId = `${selectId}-h`;

  return (
    <section className={`tile${stream?.simulated ? " tile--sim" : ""}`} aria-labelledby={headingId}>
      <header className="tile__head">
        <h2 id={headingId} className="tile__title">
          <span className="tile__screen">{screen}</span>
          {name && (
            <span dir="auto" className="tile__name">
              {name}
            </span>
          )}
          {stream?.simulated && <SimTag />}
        </h2>
        {stream && <ConfidenceBadges stream={stream} />}
      </header>
      {stream?.simulated && <div className="tile__sim" aria-hidden="true">وضع المحاكاة · Mode simulation</div>}
      {stream ? (
        <StreamPlayer
          stream={stream}
          title={t("streams.player.label", { name })}
          detections={detail.data?.detections}
          className="player--tile"
        />
      ) : streamId && detail.isPending ? (
        <Loading />
      ) : streamId && detail.isError ? (
        <ErrorBox error={detail.error} />
      ) : (
        <p className="tile__empty muted">{t("streams.wall.emptyTile")}</p>
      )}
      <footer className="tile__foot">
        {stream && <Coordinates location={stream.last_location} />}
        {stream && (
          <Link to={`/streams/${encodeURIComponent(stream.id)}`} aria-label={t("streams.wall.openLabel", { screen })}>
            {t("streams.wall.open")}
          </Link>
        )}
        {stream?.report_id && (
          <Link to={`/reports/${encodeURIComponent(stream.report_id)}`} aria-label={t("streams.wall.reportLabel", { screen })}>
            {t("streams.wall.report")}
          </Link>
        )}
        <span className="field field--inline">
          <label htmlFor={selectId} className="visually-hidden">
            {t("streams.wall.chooseLabel", { screen })}
          </label>
          <select
            id={selectId}
            value={pinned && streamId ? streamId : ""}
            onChange={(e) => onPin(slot, e.target.value || null)}
          >
            <option value="">{t("streams.wall.auto")}</option>
            {pinned && streamId && !choices.some((c) => c.id === streamId) && (
              <option value={streamId}>{name ?? streamId}</option>
            )}
            {choices.map((c) => (
              <option key={c.id} value={c.id}>
                {c.simulated ? "[SIM] " : ""}
                {streamTitle(t, c)}
              </option>
            ))}
          </select>
        </span>
      </footer>
    </section>
  );
}

/** Multi-screen wall: 1, 4 or 9 live streams side by side, with their positions on one map. */
export function StreamWallPage() {
  const { t } = useTranslation();
  const lang = useLanguage();
  const navigate = useNavigate();
  const { mapStyleUrl } = useServices();
  const { user } = useAuth();
  const layoutName = useId();
  const [wall, setWall] = useState<WallState>(loadWall);
  const query = useStreamList({ status: "live", gouvernorat: null });
  const live = useMemo(() => (query.data?.pages.flatMap((p) => p.items) ?? []).filter((s) => s.status === "live"), [query.data]);
  const byId = useMemo(() => new Map(live.map((s) => [s.id, s])), [live]);
  const tiles = arrangeWall(wall, live);

  const update = (next: WallState) => {
    setWall(next);
    saveWall(next);
  };

  const onWall = tiles.flatMap((tile) => {
    const s = tile.streamId ? byId.get(tile.streamId) : undefined;
    return s ? [{ tile, stream: s }] : [];
  });
  const pois: MapPoi[] = onWall.flatMap(({ tile, stream }) =>
    stream.last_location
      ? [
          {
            id: stream.id,
            lon: stream.last_location.lon,
            lat: stream.last_location.lat,
            kind: isAlerting(stream) ? ("stream_alert" as const) : ("stream" as const),
            title: `${t("streams.wall.screen", { n: tile.slot + 1 })} — ${streamTitle(t, stream)}`,
            subtitle: stream.simulated ? "[SIM]" : undefined,
            href: `/streams/${encodeURIComponent(stream.id)}`,
          },
        ]
      : [],
  );

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("streams.wall.title")}</h1>
        <StreamsNav />
      </div>
      <div className="filters__row list-tools">
        <fieldset className="segmented">
          <legend>{t("streams.wall.layout")}</legend>
          {WALL_LAYOUTS.map((n: WallLayout) => (
            <label key={n} className="segmented__item">
              <input
                type="radio"
                name={layoutName}
                value={n}
                checked={wall.layout === n}
                onChange={() => update({ ...wall, layout: n })}
              />
              <span>{t("streams.wall.layoutOption", { count: n })}</span>
            </label>
          ))}
        </fieldset>
        <p className="muted">{t("streams.wall.hint")}</p>
      </div>
      {onWall.some(({ stream }) => stream.simulated) && <SimulationBand />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isPending ? (
        <Loading />
      ) : (
        <div className="wall__body">
          <div className={`wall wall--${wall.layout}`}>
            {tiles.map((tile) => (
              <Tile
                key={tile.slot}
                slot={tile.slot}
                streamId={tile.streamId}
                pinned={tile.pinned}
                row={tile.streamId ? (byId.get(tile.streamId) ?? null) : null}
                choices={live}
                onPin={(slot, id) => update(pinStream(wall, slot, id))}
              />
            ))}
          </div>
          <section className="card wall__map" aria-labelledby="wall-map-title">
            <h2 id="wall-map-title">{t("streams.wall.mapTitle")}</h2>
            <Suspense fallback={<Loading />}>
              <LazyMapView
                className="map map--mini"
                markers={[]}
                pois={pois}
                bounds={initialBoundsFor(user?.identity.gouvernoratCode ?? null)}
                ariaLabel={t("streams.wall.mapLabel")}
                styleUrl={mapStyleUrl}
                dir={directionOf(lang)}
                poiOpenLabel={t("streams.wall.open")}
                onOpenPoi={(href) => void navigate(href)}
              />
            </Suspense>
            <MapLegend
              items={[
                { kind: "stream", label: t("streams.legend.stream") },
                { kind: "stream_alert", label: t("streams.legend.alert") },
              ]}
            />
            {pois.length === 0 ? (
              <p className="muted">{t("streams.wall.noPositions")}</p>
            ) : (
              <ul className="wall__positions">
                {pois.map((p) => (
                  <li key={p.id}>
                    <Link to={p.href ?? "#"}>{p.title}</Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
