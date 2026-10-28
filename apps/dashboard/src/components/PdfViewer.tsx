// covers: docs/phase-pl/design-plans.md §2: a plan is read on the screen, not downloaded. One page at a time on a
// canvas, fitted to the width and zoomable, with the page number, the table of contents of the PDF, a search in its
// text that lists the pages found, and full screen for the room's large display.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { planKeys } from "../lib/plans";
import { ErrorBox, Loading } from "./Feedback";
import { Icon } from "./Icon";

type PdfModule = typeof import("../lib/pdf");
type PdfDocument = Awaited<ReturnType<PdfModule["openPdf"]>>;

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3] as const;
const zoomOf = (i: number) => ZOOMS[i] ?? 1;

export function PdfViewer({ documentId, title }: { documentId: string; title: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const frame = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(2);
  const [width, setWidth] = useState(0);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<number[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [renderError, setRenderError] = useState(false);

  const file = useQuery({
    queryKey: planKeys.file(documentId),
    queryFn: async ({ signal }) => {
      const [lib, bytes] = await Promise.all([import("../lib/pdf"), api.documentFileBytes(documentId, signal)]);
      const doc = await lib.openPdf(bytes);
      return { lib, doc, toc: await lib.outline(doc) };
    },
    staleTime: Infinity,
    gcTime: 5 * 60 * 1000,
    retry: false,
  });
  const doc: PdfDocument | undefined = file.data?.doc;
  const pages = doc?.numPages ?? 0;

  // The width the page is fitted to follows the viewer's own width.
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => entry && setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, [doc]);

  useEffect(() => {
    if (!doc || !canvas.current || width <= 0) return;
    const run: { cancelled: boolean; task: { cancel: () => void } | null } = { cancelled: false, task: null };
    void (async () => {
      try {
        const p = await doc.getPage(page);
        if (run.cancelled || !canvas.current) return;
        const base = p.getViewport({ scale: 1 });
        const scale = ((width - 2) / base.width) * zoomOf(zoom);
        const ratio = window.devicePixelRatio || 1;
        const viewport = p.getViewport({ scale: scale * ratio });
        const c = canvas.current;
        c.width = Math.floor(viewport.width);
        c.height = Math.floor(viewport.height);
        c.style.width = `${Math.floor(viewport.width / ratio)}px`;
        c.style.height = `${Math.floor(viewport.height / ratio)}px`;
        const render = p.render({ canvas: c, viewport });
        run.task = render;
        await render.promise;
        setRenderError(false);
      } catch (e) {
        if (!run.cancelled && (e as { name?: string }).name !== "RenderingCancelledException") setRenderError(true);
      }
    })();
    return () => {
      run.cancelled = true;
      run.task?.cancel();
    };
  }, [doc, page, zoom, width]);

  if (file.isPending) return <Loading />;
  if (file.isError) return <ErrorBox error={file.error} onRetry={() => void file.refetch()} />;

  const go = (n: number) => setPage(Math.min(Math.max(1, n), pages));
  const { lib, doc: pdf, toc } = file.data;
  const search = async () => {
    setSearching(true);
    try {
      const found = await lib.findPages(pdf, query);
      setHits(found);
      if (found[0] !== undefined) go(found[0]);
    } finally {
      setSearching(false);
    }
  };
  const keys = (e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
    if (e.key === "PageDown") go(page + 1);
    else if (e.key === "PageUp") go(page - 1);
    else if (e.key === "Home") go(1);
    else if (e.key === "End") go(pages);
    else return;
    e.preventDefault();
  };

  return (
    <section className="pdf-viewer" aria-label={t("plans.viewer.label", { title })} onKeyDown={keys}>
      <div className="pdf-viewer__bar" role="toolbar" aria-label={t("plans.viewer.tools")}>
        <div className="pdf-viewer__group">
          <button type="button" className="btn btn--small" onClick={() => go(page - 1)} disabled={page <= 1}>
            <span className="flip-rtl" aria-hidden="true">
              <Icon name="chevronLeft" size={18} />
            </span>
            {t("plans.viewer.previous")}
          </button>
          <span className="pdf-viewer__page">
            <label htmlFor={`${id}-p`}>{t("plans.viewer.page")}</label>
            <input
              id={`${id}-p`}
              type="number"
              min={1}
              max={pages}
              value={page}
              onChange={(e) => go(Number(e.target.value) || 1)}
            />
            <span>{t("plans.viewer.of", { count: pages })}</span>
          </span>
          <button type="button" className="btn btn--small" onClick={() => go(page + 1)} disabled={page >= pages}>
            {t("plans.viewer.next")}
            <span className="flip-rtl" aria-hidden="true">
              <Icon name="chevronRight" size={18} />
            </span>
          </button>
        </div>
        <div className="pdf-viewer__group">
          <button
            type="button"
            className="btn btn--small btn--icon"
            onClick={() => setZoom((z) => Math.max(0, z - 1))}
            disabled={zoom === 0}
            aria-label={t("plans.viewer.zoomOut")}
          >
            <Icon name="zoomOut" size={18} />
          </button>
          <output className="pdf-viewer__zoom" aria-live="polite">
            {Math.round(zoomOf(zoom) * 100)}%
          </output>
          <button
            type="button"
            className="btn btn--small btn--icon"
            onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))}
            disabled={zoom === ZOOMS.length - 1}
            aria-label={t("plans.viewer.zoomIn")}
          >
            <Icon name="zoomIn" size={18} />
          </button>
          <button
            type="button"
            className="btn btn--small"
            onClick={() => void frame.current?.closest(".pdf-viewer")?.requestFullscreen()}
          >
            <Icon name="fullscreen" size={18} />
            {t("plans.viewer.fullscreen")}
          </button>
        </div>
        <form
          className="pdf-viewer__group"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            void search();
          }}
        >
          <label className="visually-hidden" htmlFor={`${id}-q`}>
            {t("plans.viewer.search")}
          </label>
          <input
            id={`${id}-q`}
            type="search"
            dir="auto"
            value={query}
            placeholder={t("plans.viewer.search")}
            onChange={(e) => {
              setQuery(e.target.value);
              setHits(null);
            }}
          />
          <button type="submit" className="btn btn--small" disabled={!query.trim() || searching}>
            <Icon name="search" size={18} />
            {t("plans.viewer.find")}
          </button>
        </form>
      </div>
      {(hits !== null || toc.length > 0) && (
        <div className="pdf-viewer__aside">
          {hits !== null && (
            <p role="status">
              {hits.length === 0 ? t("plans.viewer.noHit") : t("plans.viewer.hits", { count: hits.length })}{" "}
              {hits.map((n) => (
                <button key={n} type="button" className="btn btn--small" aria-current={n === page || undefined} onClick={() => go(n)}>
                  {n}
                </button>
              ))}
            </p>
          )}
          {toc.length > 0 && (
            <div className="field pdf-viewer__toc">
              <label htmlFor={`${id}-toc`}>{t("plans.viewer.contents")}</label>
              <select id={`${id}-toc`} value="" onChange={(e) => e.target.value && go(Number(e.target.value))}>
                <option value="">—</option>
                {toc.map((entry, i) => (
                  <option key={i} value={entry.page}>
                    {entry.title} ({entry.page})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}
      <div className="pdf-viewer__frame" ref={frame} tabIndex={0} aria-label={t("plans.viewer.pageOf", { page, count: pages })}>
        {/* PDF.js draws glyph by glyph from the left: an RTL canvas would shift every Arabic glyph by its width. */}
        {renderError ? (
          <p className="alert alert--error">{t("plans.viewer.renderError")}</p>
        ) : (
          <canvas ref={canvas} dir="ltr" role="img" aria-label={t("plans.viewer.pageOf", { page, count: pages })} />
        )}
      </div>
    </section>
  );
}
