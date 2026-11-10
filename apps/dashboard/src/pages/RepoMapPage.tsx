import { useQuery } from "@tanstack/react-query";
import { useId, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon, Pill } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { useFormat } from "../lib/hooks";
import {
  GROUP_TONE,
  LINK_KINDS,
  MAP_GROUPS,
  fit,
  layout,
  repoMapKeys,
  type LinkKind,
  type MapEdge,
  type MapGroup,
  type MapNode,
} from "../lib/repoMap";

interface View {
  x: number;
  y: number;
  k: number;
}
const W = 1000;
const H = 680;

/**
 * The system map (Yamen, 2026-11-09; docs/dev/repo-map.md): every page, mobile feature, API module, service and
 * piece of infrastructure, with the code imports, the HTTP calls and the settings that tie them. Search, filter by
 * kind, drag to move, wheel to zoom, and a click on a node lists what it uses and what uses it.
 */
export function RepoMapPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const base = useId();
  const map = useQuery({
    queryKey: repoMapKeys.map,
    queryFn: ({ signal }) => api.repoMap(signal),
    retry: false,
    staleTime: Infinity,
  });
  const [groups, setGroups] = useState<Set<MapGroup>>(() => new Set(MAP_GROUPS));
  const [kinds, setKinds] = useState<Set<LinkKind>>(() => new Set(LINK_KINDS));
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<View | null>(null);
  const drag = useRef<{ px: number; py: number; x: number; y: number } | null>(null);

  const placed = useMemo(() => (map.data ? layout(map.data.nodes, map.data.edges) : null), [map.data]);
  const start = useMemo(() => (placed ? fit(placed, W, H) : { x: 0, y: 0, k: 1 }), [placed]);
  const shown: View = view ?? start;
  const byId = useMemo(() => new Map((map.data?.nodes ?? []).map((n) => [n.id, n])), [map.data]);
  const nodes = useMemo(() => (map.data?.nodes ?? []).filter((n) => groups.has(n.group)), [map.data, groups]);
  const shownIds = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes]);
  const edges = useMemo(
    () => (map.data?.edges ?? []).filter((e) => kinds.has(e.k) && shownIds.has(e.s) && shownIds.has(e.t)),
    [map.data, kinds, shownIds],
  );
  const term = search.trim().toLowerCase();
  const matches = useMemo(
    () => (term ? nodes.filter((n) => n.label.toLowerCase().includes(term) || n.id.toLowerCase().includes(term)) : []),
    [nodes, term],
  );
  const near = useMemo(() => {
    if (!selected) return null;
    const ids = new Set([selected]);
    for (const e of edges) {
      if (e.s === selected) ids.add(e.t);
      if (e.t === selected) ids.add(e.s);
    }
    return ids;
  }, [selected, edges]);
  const node = selected ? byId.get(selected) : undefined;
  const uses = useMemo(() => edges.filter((e) => e.s === selected), [edges, selected]);
  const usedBy = useMemo(() => edges.filter((e) => e.t === selected), [edges, selected]);

  const focus = (id: string) => {
    setSelected(id);
    const p = placed?.get(id);
    if (p) setView({ ...shown, x: -p.x * shown.k, y: -p.y * shown.k });
  };
  const toggle = <T,>(set: Set<T>, value: T) => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  };
  const zoom = (factor: number) => {
    const k = Math.min(4, Math.max(0.1, shown.k * factor));
    const f = k / shown.k;
    setView({ x: shown.x * f, y: shown.y * f, k });
  };
  const onWheel = (e: WheelEvent<SVGSVGElement>) => zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15);
  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest("[data-node]")) return;
    drag.current = { px: e.clientX, py: e.clientY, x: shown.x, y: shown.y };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const scale = W / e.currentTarget.getBoundingClientRect().width;
    setView({ ...shown, x: d.x + (e.clientX - d.px) * scale, y: d.y + (e.clientY - d.py) * scale });
  };
  const onUp = () => {
    drag.current = null;
  };

  if (map.isPending) return <Loading />;
  if (map.isError)
    return (
      <div className="page">
        <PageTitle icon="hub" tone="slate">
          {t("repoMap.title")}
        </PageTitle>
        <ErrorBox error={map.error} onRetry={() => void map.refetch()} />
      </div>
    );

  const data = map.data;
  const totals = data.nodes.reduce((a, n) => ({ files: a.files + n.files, loc: a.loc + n.loc }), { files: 0, loc: 0 });
  const dim = (id: string) => (near ? !near.has(id) : term ? !matches.some((m) => m.id === id) : false);
  const edgeLine = (e: MapEdge) => {
    const a = placed?.get(e.s);
    const b = placed?.get(e.t);
    if (!a || !b) return null;
    const lit = near ? e.s === selected || e.t === selected : false;
    return (
      <line
        key={`${e.s}>${e.t}>${e.k}`}
        x1={a.x}
        y1={a.y}
        x2={b.x}
        y2={b.y}
        className={`repo-edge repo-edge--${e.k}${lit ? " repo-edge--lit" : ""}${near && !lit ? " repo-edge--dim" : ""}`}
        strokeWidth={Math.min(1 + Math.log2(e.w + 1) * 0.6, 4) / shown.k ** 0.3}
        markerEnd={lit ? "url(#repo-arrow)" : undefined}
      />
    );
  };
  const list = (title: string, items: MapEdge[], side: "s" | "t") => (
    <section className="repo-links">
      <h3>
        {title} <span className="muted">({items.length})</span>
      </h3>
      <ul>
        {items
          .slice()
          .sort((a, b) => b.w - a.w)
          .map((e) => {
            const other = byId.get(e[side]);
            if (!other) return null;
            return (
              <li key={`${e[side]}-${e.k}`}>
                <button type="button" className="link-button" onClick={() => focus(other.id)}>
                  <span className={`repo-dot tone-${GROUP_TONE[other.group]}`} aria-hidden="true" />
                  <span dir="ltr">{other.label}</span>
                </button>
                <span className="muted"> · {t(`repoMap.kinds.${e.k}`)}</span>
                {e.via.length > 0 && (
                  <ul className="repo-via" dir="ltr">
                    {e.via.map((v) => (
                      <li key={v}>
                        <code>{v}</code>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
      </ul>
    </section>
  );

  return (
    <div className="page repo-map">
      <div className="page__head">
        <PageTitle icon="hub" tone="slate">
          {t("repoMap.title")}
        </PageTitle>
        <div className="sql-console__limits">
          <Pill tone="slate">{t("repoMap.counts.nodes", { count: data.nodes.length })}</Pill>
          <Pill tone="slate">{t("repoMap.counts.edges", { count: data.edges.length })}</Pill>
          <Pill tone="navy">{t("repoMap.counts.routes", { count: data.routes })}</Pill>
          <Pill tone="slate">
            {t("repoMap.counts.code", { files: fmt.number(totals.files), loc: fmt.number(totals.loc) })}
          </Pill>
        </div>
      </div>
      <p className="muted">{t("repoMap.intro", { date: fmt.dateTime(data.generated_at) })}</p>

      <div className="card repo-bar">
        <input
          type="search"
          className="sql-search repo-bar__search"
          aria-label={t("repoMap.search")}
          placeholder={t("repoMap.search")}
          dir="auto"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setSelected(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches[0]) focus(matches[0].id);
          }}
        />
        <div className="repo-bar__chips" role="group" aria-label={t("repoMap.groupsLabel")}>
          {MAP_GROUPS.map((g) => (
            <button
              key={g}
              type="button"
              aria-pressed={groups.has(g)}
              className={`repo-chip ${groups.has(g) ? "repo-chip--on" : ""}`}
              onClick={() => setGroups((s) => toggle(s, g))}
            >
              <span className={`repo-dot tone-${GROUP_TONE[g]}`} aria-hidden="true" />
              {t(`repoMap.groups.${g}`)}
              <span className="muted">{data.nodes.filter((n) => n.group === g).length}</span>
            </button>
          ))}
        </div>
        <div className="repo-bar__chips" role="group" aria-label={t("repoMap.kindsLabel")}>
          {LINK_KINDS.map((k) => (
            <button
              key={k}
              type="button"
              aria-pressed={kinds.has(k)}
              className={`repo-chip ${kinds.has(k) ? "repo-chip--on" : ""}`}
              onClick={() => setKinds((s) => toggle(s, k))}
            >
              <span className={`repo-line repo-line--${k}`} aria-hidden="true" />
              {t(`repoMap.kinds.${k}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="repo-map__grid">
        <figure className="card repo-canvas" aria-labelledby={`${base}-cap`}>
          <figcaption id={`${base}-cap`} className="visually-hidden">
            {t("repoMap.caption")}
          </figcaption>
          <div className="repo-canvas__tools">
            <button type="button" className="btn btn--icon" aria-label={t("repoMap.zoomIn")} onClick={() => zoom(1.25)}>
              <Icon name="zoomIn" size={18} />
            </button>
            <button type="button" className="btn btn--icon" aria-label={t("repoMap.zoomOut")} onClick={() => zoom(0.8)}>
              <Icon name="zoomOut" size={18} />
            </button>
            <button
              type="button"
              className="btn btn--small"
              onClick={() => {
                setView(null);
                setSelected(null);
              }}
            >
              {t("repoMap.reset")}
            </button>
          </div>
          <svg
            viewBox={`${-W / 2} ${-H / 2} ${W} ${H}`}
            className="repo-svg"
            role="img"
            aria-label={t("repoMap.caption")}
            onWheel={onWheel}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
          >
            <defs>
              <marker id="repo-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M0 0 L10 5 L0 10 z" className="repo-arrow" />
              </marker>
            </defs>
            <g transform={`translate(${shown.x} ${shown.y}) scale(${shown.k})`}>
              <g>{edges.map(edgeLine)}</g>
              <g>
                {nodes.map((n: MapNode) => {
                  const p = placed?.get(n.id);
                  if (!p) return null;
                  const showLabel = n.deg >= 12 || n.id === selected || (near?.has(n.id) ?? false) || matches.some((m) => m.id === n.id) || shown.k > 1.4;
                  return (
                    <g
                      key={n.id}
                      data-node={n.id}
                      transform={`translate(${p.x} ${p.y})`}
                      className={`repo-node${dim(n.id) ? " repo-node--dim" : ""}${n.id === selected ? " repo-node--on" : ""}`}
                      role="button"
                      tabIndex={0}
                      aria-label={`${n.label} (${t(`repoMap.groups.${n.group}`)})`}
                      onClick={() => setSelected(n.id === selected ? null : n.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelected(n.id);
                        }
                      }}
                    >
                      <circle r={p.r} className={`repo-fill tone-${GROUP_TONE[n.group]}`} />
                      {showLabel && (
                        <text y={p.r + 11} textAnchor="middle" className="repo-label" fontSize={11 / Math.max(shown.k, 0.6) ** 0.5}>
                          {n.label}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            </g>
          </svg>
          <p className="muted repo-canvas__hint">{t("repoMap.hint")}</p>
        </figure>

        <aside className="card repo-side" aria-live="polite">
          {node ? (
            <>
              <h2 className="sql-card-title">
                <span className={`repo-dot repo-dot--lg tone-${GROUP_TONE[node.group]}`} aria-hidden="true" />
                <span dir="ltr">{node.label}</span>
              </h2>
              <p className="muted">
                {t(`repoMap.groups.${node.group}`)} · <code dir="ltr">{node.id}</code>
              </p>
              <p>
                {t("repoMap.size", { files: fmt.number(node.files), loc: fmt.number(node.loc) })}
              </p>
              {list(t("repoMap.uses"), uses, "t")}
              {list(t("repoMap.usedBy"), usedBy, "s")}
            </>
          ) : term ? (
            <>
              <h2 className="sql-card-title">{t("repoMap.results", { count: matches.length })}</h2>
              <ul className="repo-results">
                {matches.slice(0, 40).map((m) => (
                  <li key={m.id}>
                    <button type="button" className="link-button" onClick={() => focus(m.id)}>
                      <span className={`repo-dot tone-${GROUP_TONE[m.group]}`} aria-hidden="true" />
                      <span dir="ltr">{m.label}</span>
                    </button>
                    <span className="muted"> · {t(`repoMap.groups.${m.group}`)}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <h2 className="sql-card-title">{t("repoMap.howTitle")}</h2>
              <p className="muted">{t("repoMap.how")}</p>
              <h3>{t("repoMap.mostUsed")}</h3>
              <ol className="repo-results">
                {data.nodes
                  .slice()
                  .sort((a, b) => b.deg - a.deg)
                  .slice(0, 10)
                  .map((m) => (
                    <li key={m.id}>
                      <button type="button" className="link-button" onClick={() => focus(m.id)}>
                        <span className={`repo-dot tone-${GROUP_TONE[m.group]}`} aria-hidden="true" />
                        <span dir="ltr">{m.label}</span>
                      </button>
                      <span className="muted"> · {t("repoMap.links", { count: m.deg })}</span>
                    </li>
                  ))}
              </ol>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
