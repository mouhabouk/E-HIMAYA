import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useServices } from "../context/services";
import { useFormat } from "../lib/hooks";
import {
  p7Keys,
  type GalleryItem,
  type IncidentGallery,
} from "../lib/phase7Api";
import { ErrorBox, Loading } from "./Feedback";
import { Pill } from "./Icon";
import { SimTag } from "./StreamBits";

const ORDER: GalleryItem["kind"][] = [
  "photo",
  "video",
  "voice",
  "frame",
  "recording",
  "stream",
];

/** The one line above the gallery: «12 photos · 2 videos · 3 voice notes · 1 stream live now». */
export function gallerySummary(
  t: (key: string, o?: Record<string, unknown>) => string,
  g: IncidentGallery,
): string {
  const parts = ORDER.filter((k) => (g.counts[k] ?? 0) > 0).map((k) =>
    t(`gallery.count.${k}`, { count: g.counts[k] }),
  );
  if (g.live_streams > 0)
    parts.push(t("gallery.liveNow", { count: g.live_streams }));
  return parts.length > 0 ? parts.join(" · ") : t("gallery.none");
}

function Item({ item }: { item: GalleryItem }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const caption = (
    <figcaption>
      <span>{t(`gallery.origin.${item.origin}`)}</span>
      {item.label && (
        <>
          {" · "}
          <span dir="auto">{item.label}</span>
        </>
      )}
      {" · "}
      <time dateTime={item.at}>{fmt.dateTime(item.at)}</time>
      {item.simulated && <SimTag />}
    </figcaption>
  );
  let body;
  if (item.kind === "stream") {
    body = (
      <Link
        className="gallery__stream"
        to={`/streams/${encodeURIComponent(item.id)}`}
      >
        {item.live ? (
          <Pill tone="red">{t("gallery.live")}</Pill>
        ) : (
          <Pill tone="slate">{t("gallery.ended")}</Pill>
        )}{" "}
        {t("gallery.openStream")}
      </Link>
    );
  } else if (!item.url) {
    body = <p className="muted">{t("gallery.unavailable")}</p>;
  } else if (item.kind === "photo" || item.kind === "frame") {
    body = (
      <a href={item.url} target="_blank" rel="noreferrer">
        <img
          src={item.url}
          alt={t(`gallery.alt.${item.kind}`)}
          loading="lazy"
        />
      </a>
    );
  } else if (item.kind === "voice") {
    body = (
      <>
        <audio
          controls
          preload="none"
          src={item.url}
          aria-label={t("gallery.alt.voice")}
        />
        {item.transcript && (
          <blockquote className="gallery__transcript" dir="auto">
            {item.transcript}
          </blockquote>
        )}
      </>
    );
  } else {
    body = (
      <video
        controls
        preload="none"
        src={item.url}
        aria-label={t(`gallery.alt.${item.kind}`)}
      />
    );
  }
  return (
    <figure
      className={`gallery__item gallery__item--${item.kind}`}
      data-testid={`gallery-${item.id}`}
    >
      {body}
      {caption}
    </figure>
  );
}

/** Review point 21 (phase D): what the citizens, the teams, the cameras and the vision service gave of the incident,
 * in one place and in time order, under one summary line. */
export function IncidentGallerySection({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const query = useQuery({
    queryKey: p7Keys.incidentMedia(incidentId),
    queryFn: ({ signal }) => api.incidentMedia(incidentId, signal),
    refetchInterval: 30_000,
  });
  return (
    <section className="card gallery" aria-labelledby="sec-gallery">
      <h2 id="sec-gallery">{t("gallery.title")}</h2>
      {query.isPending && <Loading />}
      {query.isError && (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      )}
      {query.isSuccess && (
        <>
          <p className="gallery__summary" data-testid="gallery-summary">
            {gallerySummary(t, query.data)}
          </p>
          {query.data.items.length > 0 && (
            <div className="gallery__grid">
              {query.data.items.map((item) => (
                <Item key={`${item.kind}-${item.id}`} item={item} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
