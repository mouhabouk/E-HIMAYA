import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon, IconTile, Pill } from "../components/Icon";
import { LazyMapView } from "../components/LazyMap";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import {
  AW_INCIDENT_KINDS,
  awIcon,
  awKeys,
  awTone,
  hhmm,
  type AwCategory,
  type AwFilter,
  type AwMarker,
  type AwMarkerBody,
} from "../lib/addressWarnings";
import { useFormat, useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { canManageIncidents } from "../lib/roles";

type Tab = "register" | "settings" | "reveals";
const FILTERS: AwFilter[] = ["", "pending", "review_due", "archived", "rejected"];
const SOURCES: AwMarkerBody["source"][] = ["room", "report", "municipality", "org"];

/**
 * Address warnings (OS8, docs/phase-os8/design-os8.md): the register of the marks of the room's gouvernorat (the
 * central room: every one), the category settings (central room) and the journal of the names read.
 */
export function AddressWarningsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const [tab, setTab] = useState<Tab>("register");
  const cats = useQuery({ queryKey: awKeys.categories, queryFn: ({ signal }) => api.awCategories(signal) });
  return (
    <div className="page">
      <PageTitle print icon="warning" tone="amber">
        {t("addressWarnings.title")}
      </PageTitle>
      <p className="muted">{t("addressWarnings.intro")}</p>
      <div className="aw-tabs" role="group" aria-label={t("addressWarnings.title")}>
        {(["register", "settings", "reveals"] as const).map((k) => (
          <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}>
            {t(`addressWarnings.tab.${k}`)}
          </button>
        ))}
      </div>
      {cats.isLoading && <Loading />}
      {cats.isError && <ErrorBox error={cats.error} onRetry={() => void cats.refetch()} />}
      {cats.data && tab === "register" && <Register categories={cats.data} />}
      {cats.data && tab === "settings" && <Settings categories={cats.data} />}
      {cats.data && tab === "reveals" && <Reveals categories={cats.data} />}
    </div>
  );
}

function CategoryCell({ c }: { c: AwCategory | undefined }) {
  return (
    <span className="aw-cat">
      <IconTile name={awIcon(c)} tone={awTone(c)} size="sm" />
      {c?.name ?? "—"}
    </span>
  );
}

function StatusPill({ m }: { m: AwMarker }) {
  const { t } = useTranslation();
  if (m.review_due) return <Pill tone="red">{t("addressWarnings.status.review_due")}</Pill>;
  const tone = { pending: "amber", active: "green", archived: "slate", rejected: "slate", withdrawn: "slate" } as const;
  return <Pill tone={tone[m.status]}>{t(`addressWarnings.status.${m.status}`)}</Pill>;
}

function Register({ categories }: { categories: AwCategory[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const [filter, setFilter] = useState<AwFilter>("");
  const [adding, setAdding] = useState(false);
  const byKey = new Map(categories.map((c) => [c.key, c]));
  const q = useQuery({ queryKey: awKeys.markers(filter), queryFn: ({ signal }) => api.awMarkers(filter, signal) });
  const pending = useQuery({
    queryKey: awKeys.markers("pending"),
    queryFn: ({ signal }) => api.awMarkers("pending", signal),
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: awKeys.all });
  const decide = useMutation({
    mutationFn: ({ id, action, reason }: { id: string; action: "approve" | "reject" | "archive" | "confirm"; reason?: string }) =>
      api.awDecide(id, action, reason),
    onSuccess: refresh,
  });
  const imported = useMutation({ mutationFn: () => api.awImportOrgs(), onSuccess: refresh });
  const ask = (id: string, action: "reject" | "archive") => {
    const reason = window.prompt(t(`addressWarnings.ask.${action}`));
    if (reason && reason.trim().length >= 2) decide.mutate({ id, action, reason: reason.trim() });
  };
  const counts = q.data?.counts;
  return (
    <>
      {counts && (
        <dl className="kpis aw-kpis">
          <div className="kpi">
            <dt className="kpi__label">{t("addressWarnings.kpi.active")}</dt>
            <dd className="kpi__value">{fmt.number(counts.active)}</dd>
          </div>
          <div className="kpi aw-kpi--pending">
            <dt className="kpi__label">{t("addressWarnings.kpi.pending")}</dt>
            <dd className="kpi__value">{fmt.number(counts.pending)}</dd>
          </div>
          <div className="kpi aw-kpi--due">
            <dt className="kpi__label">{t("addressWarnings.kpi.reviewDue")}</dt>
            <dd className="kpi__value">{fmt.number(counts.review_due)}</dd>
          </div>
          <div className="kpi aw-kpi--personal">
            <dt className="kpi__label">{t("addressWarnings.kpi.personal")}</dt>
            <dd className="kpi__value">{fmt.number(counts.personal)}</dd>
          </div>
        </dl>
      )}
      {decide.isError && <ErrorBox error={decide.error} />}
      {(pending.data?.items.length ?? 0) > 0 && (
        <section className="card aw-queue" aria-labelledby="aw-queue">
          <h2 id="aw-queue">
            <IconTile name="addLocationAlt" tone="orange" size="sm" /> {t("addressWarnings.queue.title")}
          </h2>
          <ul className="aw-list">
            {pending.data?.items.map((m) => (
              <li key={m.id} className="aw-item aw-item--pending">
                <IconTile name={awIcon(byKey.get(m.category))} tone={awTone(byKey.get(m.category))} />
                <div className="aw-item__body">
                  <div className="aw-item__title">
                    <strong>{byKey.get(m.category)?.name}</strong>
                    <Pill tone="navy">{t(`addressWarnings.source.${m.source}`)}</Pill>
                  </div>
                  <p className="aw-item__desc" dir="auto">
                    {m.description}
                  </p>
                  <p className="muted aw-item__addr" dir="auto">
                    {m.address} · {m.source_ref ?? m.created_by_name}
                    {m.incident_id && (
                      <>
                        {" · "}
                        <Link to={`/incidents/${m.incident_id}`}>{t("addressWarnings.queue.incident")}</Link>
                      </>
                    )}
                  </p>
                  {canWrite && (
                    <div className="aw-item__acts">
                      <button
                        type="button"
                        className="btn btn--small btn--primary"
                        onClick={() => decide.mutate({ id: m.id, action: "approve" })}
                      >
                        {t("addressWarnings.action.approve")}
                      </button>
                      <button type="button" className="btn btn--small" onClick={() => ask(m.id, "reject")}>
                        {t("addressWarnings.action.reject")}
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="card">
        <div className="aw-toolbar">
          {canWrite && (
            <button type="button" className="btn btn--primary" onClick={() => setAdding((x) => !x)} aria-expanded={adding}>
              <Icon name="addLocationAlt" /> {t("addressWarnings.add.button")}
            </button>
          )}
          {canWrite && (
            <button type="button" className="btn" onClick={() => imported.mutate()} disabled={imported.isPending}>
              {t("addressWarnings.import.button")}
            </button>
          )}
          {imported.data && (
            <span role="status" className="muted">
              {t("addressWarnings.import.done", { n: imported.data.created })}
            </span>
          )}
          <label>
            {t("addressWarnings.filter")}{" "}
            <select value={filter} onChange={(e) => setFilter(e.target.value as AwFilter)}>
              {FILTERS.map((f) => (
                <option key={f} value={f}>
                  {t(`addressWarnings.filterOption.${f || "current"}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {adding && <AddForm categories={categories} onDone={() => setAdding(false)} />}
        {q.isLoading && <Loading />}
        {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && q.data.items.length === 0 && <p className="muted">{t("addressWarnings.empty")}</p>}
        {q.data && q.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("addressWarnings.col.category")}</th>
                  <th>{t("addressWarnings.col.address")}</th>
                  <th>{t("addressWarnings.col.source")}</th>
                  <th>{t("addressWarnings.col.shownTo")}</th>
                  <th>{t("addressWarnings.col.review")}</th>
                  <th>{t("addressWarnings.col.status")}</th>
                  {canWrite && <th>{t("addressWarnings.col.actions")}</th>}
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <CategoryCell c={byKey.get(m.category)} />
                    </td>
                    <td>
                      <strong dir="auto">{m.address}</strong>
                      <div className="muted" dir="auto">
                        {m.description}
                        {m.hours && ` · ${hhmm(m.hours.start)}–${hhmm(m.hours.end)}`}
                      </div>
                    </td>
                    <td>
                      {t(`addressWarnings.source.${m.source}`)}
                      {m.source_ref && (
                        <div className="muted" dir="auto">
                          {m.source_ref}
                        </div>
                      )}
                    </td>
                    <td>{t(m.team_visible ? "addressWarnings.panel.team" : "addressWarnings.panel.roomOnly")}</td>
                    <td>{fmt.date(m.review_on)}</td>
                    <td>
                      <StatusPill m={m} />
                    </td>
                    {canWrite && (
                      <td className="aw-actions">
                        {m.status === "pending" && (
                          <button
                            type="button"
                            className="btn btn--small btn--primary"
                            onClick={() => decide.mutate({ id: m.id, action: "approve" })}
                          >
                            {t("addressWarnings.action.approve")}
                          </button>
                        )}
                        {m.review_due && (
                          <button
                            type="button"
                            className="btn btn--small btn--primary"
                            onClick={() => decide.mutate({ id: m.id, action: "confirm" })}
                          >
                            {t("addressWarnings.action.confirm")}
                          </button>
                        )}
                        {(m.status === "active" || m.status === "pending") && (
                          <button type="button" className="btn btn--small" onClick={() => ask(m.id, "archive")}>
                            {t("addressWarnings.action.archive")}
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted aw-note">
          <Icon name="lockOpen" size={16} /> {t("addressWarnings.personalNote")}
        </p>
      </section>
    </>
  );
}

function AddForm({ categories, onDone }: { categories: AwCategory[]; onDone: () => void }) {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const qc = useQueryClient();
  const rooms = categories.filter((c) => !c.personal);
  const [category, setCategory] = useState(rooms[0]?.key ?? "gas");
  const [point, setPoint] = useState<{ lat: number; lon: number } | null>(null);
  const [address, setAddress] = useState("");
  const [example, setExample] = useState(0);
  const [note, setNote] = useState("");
  const [source, setSource] = useState<AwMarkerBody["source"]>("room");
  const [teamVisible, setTeamVisible] = useState(true);
  const [hours, setHours] = useState({ start: 450, end: 1050 });
  const cat = rooms.find((c) => c.key === category);
  const description = [example >= 0 ? cat?.examples[example] : "", note.trim()].filter(Boolean).join(" · ");
  const create = useMutation({
    mutationFn: () => {
      if (!point) throw new Error("point");
      return api.awCreate({
        category,
        location: point,
        address: address.trim(),
        description,
        source,
        team_visible: teamVisible,
        hours: category === "occ" ? hours : null,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: awKeys.all });
      onDone();
    },
  });
  const ready = point !== null && address.trim().length >= 2 && description.length >= 2;
  return (
    <form
      className="aw-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) create.mutate();
      }}
    >
      <fieldset>
        <legend>
          {t("addressWarnings.add.category")} <span className="required">*</span>
        </legend>
        <div className="aw-choices">
          {categories.map((c) => (
            <button
              key={c.key}
              type="button"
              className="aw-choice"
              aria-pressed={c.key === category}
              disabled={c.personal}
              onClick={() => {
                setCategory(c.key);
                setExample(0);
              }}
            >
              <IconTile name={awIcon(c)} tone={awTone(c)} size="sm" /> {c.name}
            </button>
          ))}
        </div>
        <p className="muted">{t("addressWarnings.add.personal")}</p>
      </fieldset>
      <fieldset>
        <legend>
          {t("addressWarnings.add.place")} <span className="required">*</span>
        </legend>
        <p className="muted">
          {point ? t("addressWarnings.add.picked", { lat: point.lat.toFixed(5), lon: point.lon.toFixed(5) }) : t("addressWarnings.add.pick")}
        </p>
        <Suspense fallback={<Loading />}>
          <LazyMapView
            className="map map--mini"
            markers={[]}
            bounds={initialBoundsFor(user?.identity.gouvernoratCode ?? null)}
            ariaLabel={t("addressWarnings.add.place")}
            styleUrl={mapStyleUrl}
            dir={directionOf(lang)}
            onMapClick={(lon, lat) => setPoint({ lat, lon })}
            centroid={point ? { ...point, label: cat?.name ?? "" } : null}
          />
        </Suspense>
      </fieldset>
      <label className="field">
        <span>
          {t("addressWarnings.add.address")} <span className="required">*</span>
        </span>
        <input value={address} maxLength={200} dir="auto" onChange={(e) => setAddress(e.target.value)} />
      </label>
      <fieldset>
        <legend>
          {t("addressWarnings.add.description")} <span className="required">*</span>
        </legend>
        <div className="aw-chips">
          {(cat?.examples ?? []).map((ex, i) => (
            <button
              key={ex}
              type="button"
              className={`aw-chip${i === example ? " aw-chip--on" : ""}`}
              aria-pressed={i === example}
              onClick={() => setExample(i)}
            >
              {ex}
            </button>
          ))}
          <button
            type="button"
            className={`aw-chip${example === -1 ? " aw-chip--on" : ""}`}
            aria-pressed={example === -1}
            onClick={() => setExample(-1)}
          >
            {t("addressWarnings.add.other")}
          </button>
        </div>
        <textarea
          value={note}
          maxLength={300}
          dir="auto"
          aria-label={t("addressWarnings.add.note")}
          placeholder={t("addressWarnings.add.note")}
          onChange={(e) => setNote(e.target.value)}
        />
      </fieldset>
      {category === "occ" && (
        <fieldset>
          <legend>{t("addressWarnings.add.hours")}</legend>
          <label>
            {t("addressWarnings.add.from")}{" "}
            <input
              type="time"
              value={hhmm(hours.start)}
              onChange={(e) => {
                const [h, m] = e.target.value.split(":").map(Number);
                setHours((x) => ({ ...x, start: (h ?? 0) * 60 + (m ?? 0) }));
              }}
            />
          </label>{" "}
          <label>
            {t("addressWarnings.add.to")}{" "}
            <input
              type="time"
              value={hhmm(hours.end)}
              onChange={(e) => {
                const [h, m] = e.target.value.split(":").map(Number);
                setHours((x) => ({ ...x, end: (h ?? 0) * 60 + (m ?? 0) }));
              }}
            />
          </label>
        </fieldset>
      )}
      <div className="aw-form__row">
        <label>
          {t("addressWarnings.add.source")}{" "}
          <select value={source} onChange={(e) => setSource(e.target.value as AwMarkerBody["source"])}>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`addressWarnings.source.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={teamVisible} onChange={(e) => setTeamVisible(e.target.checked)} />{" "}
          {t("addressWarnings.add.teamVisible")}
        </label>
      </div>
      {create.isError && <ErrorBox error={create.error} />}
      <div className="form-actions">
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
        <button type="submit" className="btn btn--primary" disabled={!ready || create.isPending}>
          {t("addressWarnings.add.save")}
        </button>
      </div>
    </form>
  );
}

function Settings({ categories }: { categories: AwCategory[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const national = user?.identity.gouvernoratCode === null;
  const canEdit = national && user.identity.roles.includes("ops_manager");
  const save = useMutation({
    mutationFn: (c: AwCategory) =>
      api.awSaveCategory(c.key, {
        radius_m: c.radius_m,
        review_months: c.review_months,
        team: c.team,
        critical_with: c.critical_with,
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: awKeys.categories }),
  });
  const step = (c: AwCategory, field: "radius_m" | "review_months", d: number) => {
    const [lo, hi] = field === "radius_m" ? [20, 1000] : [1, 36];
    save.mutate({ ...c, [field]: Math.min(hi, Math.max(lo, c[field] + d)) });
  };
  return (
    <section className="card">
      <p className="muted">{t(canEdit ? "addressWarnings.settings.intro" : "addressWarnings.settings.readOnly")}</p>
      {save.isError && <ErrorBox error={save.error} />}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>{t("addressWarnings.col.category")}</th>
              <th>{t("addressWarnings.settings.radius")}</th>
              <th>{t("addressWarnings.settings.review")}</th>
              <th>{t("addressWarnings.settings.team")}</th>
              <th>{t("addressWarnings.settings.critical")}</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((c) => (
              <tr key={c.key}>
                <td>
                  <CategoryCell c={c} /> {c.personal && <Pill tone="green">{t("addressWarnings.settings.personal")}</Pill>}
                </td>
                <td>
                  <span className="aw-stepper">
                    <button type="button" disabled={!canEdit} aria-label={t("addressWarnings.settings.less")} onClick={() => step(c, "radius_m", -10)}>
                      −
                    </button>
                    <span>{t("addressWarnings.settings.metres", { n: c.radius_m })}</span>
                    <button type="button" disabled={!canEdit} aria-label={t("addressWarnings.settings.more")} onClick={() => step(c, "radius_m", 10)}>
                      +
                    </button>
                  </span>
                </td>
                <td>
                  <span className="aw-stepper">
                    <button type="button" disabled={!canEdit} aria-label={t("addressWarnings.settings.less")} onClick={() => step(c, "review_months", -1)}>
                      −
                    </button>
                    <span>{t("addressWarnings.settings.months", { n: c.review_months })}</span>
                    <button type="button" disabled={!canEdit} aria-label={t("addressWarnings.settings.more")} onClick={() => step(c, "review_months", 1)}>
                      +
                    </button>
                  </span>
                </td>
                <td>
                  <input
                    type="checkbox"
                    role="switch"
                    aria-label={t("addressWarnings.settings.team")}
                    checked={c.team}
                    disabled={!canEdit}
                    onChange={(e) => save.mutate({ ...c, team: e.target.checked })}
                  />
                </td>
                <td>
                  <div className="aw-chips">
                    {AW_INCIDENT_KINDS.map((k) => {
                      const on = c.critical_with.includes(k);
                      return (
                        <button
                          key={k}
                          type="button"
                          className={`aw-chip${on ? " aw-chip--on" : ""}`}
                          aria-pressed={on}
                          disabled={!canEdit}
                          onClick={() =>
                            save.mutate({
                              ...c,
                              critical_with: on ? c.critical_with.filter((x) => x !== k) : [...c.critical_with, k],
                            })
                          }
                        >
                          {t(`category.${k}`)}
                        </button>
                      );
                    })}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Reveals({ categories }: { categories: AwCategory[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const byKey = new Map(categories.map((c) => [c.key, c]));
  const q = useQuery({ queryKey: awKeys.reveals, queryFn: ({ signal }) => api.awReveals(signal) });
  return (
    <section className="card">
      <p className="muted">{t("addressWarnings.reveals.intro")}</p>
      {q.isLoading && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && q.data.length === 0 && <p className="muted">{t("addressWarnings.reveals.none")}</p>}
      {q.data && q.data.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>{t("addressWarnings.reveals.at")}</th>
              <th>{t("addressWarnings.reveals.by")}</th>
              <th>{t("addressWarnings.col.category")}</th>
              <th>{t("addressWarnings.reveals.incident")}</th>
              <th>{t("addressWarnings.reveals.reason")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((r) => (
              <tr key={`${r.at}-${r.address}`}>
                <td>{fmt.dateTime(r.at)}</td>
                <td>{r.by_name ?? "—"}</td>
                <td>
                  <CategoryCell c={byKey.get(r.category)} />
                </td>
                <td>{r.incident_id ? <Link to={`/incidents/${r.incident_id}`}>{t("addressWarnings.queue.incident")}</Link> : "—"}</td>
                <td>{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
