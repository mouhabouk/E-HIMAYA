// covers: phase L5b (docs/phase-l/design-l5.md §3.3, docs/sensor-gateway.md §8): the drones of the room as read-only
// sources: where each one is (read from its own stream), the alerts of its zones and battery, which an agent
// acknowledges, and for the operations manager the register (publish token shown once) and the work and no-fly zones
// drawn on the map. Nothing is ever sent to a drone: the pilot alone flies it.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyPolygonDrawMap } from "../components/LazyPolygonMap";
import { PageTitle } from "../components/PageTitle";
import { RequiredNote } from "../components/PhaseASettings";
import { Stepper } from "../components/Stepper";
import { SimTag } from "../components/StreamBits";
import { useAuth } from "../context/auth";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey } from "../lib/api";
import {
  droneKeys,
  isFresh,
  MAX_ZONE_VERTICES,
  type Drone,
  type DroneAlert,
  type DroneCreated,
  type Zone,
  type ZoneKind,
} from "../lib/drones";
import { useCan } from "../lib/features";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { useNow } from "../lib/phase9";
import { addVertex, fromPolygon, undoVertex, validateVertices, verticesBounds, type Vertex } from "../lib/polygon";
import { canAcknowledgeDroneAlerts, canManageDrones } from "../lib/roles";

function VideoPill({ status }: { status: string }) {
  const { t } = useTranslation();
  const live = status === "live";
  return (
    <span className={`pill ${live ? "tone-green" : "tone-slate"}`}>
      {t(live ? "drones.video.live" : "drones.video.off")}
    </span>
  );
}

function ZonePill({ kind }: { kind: ZoneKind }) {
  const { t } = useTranslation();
  return <span className={`pill ${kind === "no_fly" ? "tone-red" : "tone-green"}`}>{t(`drones.zone.kind.${kind}`)}</span>;
}

function RegisterForm({ onDone, onCreated }: { onDone: () => void; onCreated: (c: DroneCreated) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const id = useId();
  const geo = useGouvernorats();
  const own = user?.identity.gouvernoratCode ?? null;
  const national = own === null;
  const [label, setLabel] = useState("");
  const [code, setCode] = useState<number | null>(own);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.registerDrone({ label: label.trim(), gouvernorat_code: national ? code : null }),
    onSuccess: (created) => {
      void qc.invalidateQueries({ queryKey: droneKeys.all });
      onCreated(created);
      onDone();
    },
    onError: (e) => setError(t(errorMessageKey(e))),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setError(null);
    if (label.trim().length < 2) {
      setError(t("drones.errors.label"));
      return;
    }
    if (national && code === null) {
      setError(t("sensors.errors.gouvernorat"));
      return;
    }
    save.mutate();
  };
  return (
    <form className="card sensor-form" noValidate onSubmit={submit} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("drones.form.title")}</h2>
      <RequiredNote />
      <div className="field">
        <label htmlFor={`${id}-label`}>{t("sensors.field.name")}</label>
        <input
          id={`${id}-label`}
          dir="auto"
          required
          maxLength={100}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
      </div>
      {national && (
        <div className="field">
          <label htmlFor={`${id}-g`}>{t("filters.gouvernorat")}</label>
          <select
            id={`${id}-g`}
            required
            value={code ?? ""}
            onChange={(e) => setCode(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("referral.choose")}</option>
            {geo.list.map((g) => (
              <option key={g.code} value={g.code}>
                {g.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {t("drones.register")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

/** The publish address and token of the new drone's video, shown once. */
function SecretsPanel({ shown, onClose }: { shown: DroneCreated; onClose: () => void }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = () => {
    // On plain http inside the local network the clipboard may be missing: the token stays on screen to copy by hand.
    void Promise.resolve()
      .then(() => navigator.clipboard.writeText(shown.publish_token))
      .then(() => setCopied(true))
      .catch(() => setCopied(false));
  };
  return (
    <section className="card sensor-key" aria-labelledby="drone-key-title">
      <h2 id="drone-key-title">{t("drones.key.title", { name: shown.drone.label })}</h2>
      <p className="alert alert--warn" role="note">
        {t("towers.key.once")}
      </p>
      <dl className="fields">
        <div className="ops-dl-row">
          <dt>{t("drones.key.rtsp")}</dt>
          <dd className="code" dir="ltr">
            {shown.publish_url_rtsp}
          </dd>
        </div>
        <div className="ops-dl-row">
          <dt>{t("drones.key.rtmp")}</dt>
          <dd className="code" dir="ltr">
            {shown.publish_url_rtmp}
          </dd>
        </div>
        <div className="ops-dl-row">
          <dt>{t("towers.key.token")}</dt>
          <dd className="code sensor-key__value" dir="ltr">
            {shown.publish_token}
          </dd>
        </div>
      </dl>
      <div className="actions">
        <button type="button" className="btn btn--primary" onClick={copy}>
          {copied ? t("sensors.key.copied") : t("drones.key.copy")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("sensors.key.done")}
        </button>
      </div>
      <p className="muted">{t("drones.key.howTo")}</p>
    </section>
  );
}

function AlertsCard({ alerts, canAck }: { alerts: DroneAlert[]; canAck: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const ack = useMutation({
    mutationFn: (a: DroneAlert) => api.acknowledgeDroneAlert(a.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: droneKeys.all }),
  });
  const open = alerts.filter((a) => a.acknowledged_at === null);
  return (
    <section className="card" aria-labelledby="drone-alerts-title">
      <h2 id="drone-alerts-title">{t("drones.alerts.title", { n: fmt.number(open.length) })}</h2>
      {open.length === 0 && <p className="muted">{t("drones.alerts.none")}</p>}
      {ack.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(ack.error))}
        </p>
      )}
      {open.length > 0 && (
        <ul className="list drone-alerts" aria-live="polite">
          {open.map((a) => (
            <li key={a.id} className={`drone-alert drone-alert--${a.kind}`}>
              <div>
                <strong>{t(`drones.alerts.kind.${a.kind}`)}</strong> · <span dir="auto">{a.drone_label}</span>
                {a.zone_name && (
                  <>
                    {" "}
                    · <span dir="auto">{a.zone_name}</span>
                  </>
                )}
                {typeof a.detail.distance_m === "number" && (
                  <> · {t("drones.alerts.distance", { m: fmt.number(a.detail.distance_m) })}</>
                )}
                {typeof a.detail.battery_pct === "number" && (
                  <> · {t("drones.battery", { pct: fmt.number(Math.round(a.detail.battery_pct)) })}</>
                )}
                <div className="muted">{fmt.dateTime(a.at)}</div>
              </div>
              {canAck && (
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={ack.isPending}
                  onClick={() => ack.mutate(a)}
                >
                  {t("drones.alerts.ack")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ZoneForm({ zone, onDone }: { zone: Zone | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const lang = useLanguage();
  const fmt = useFormat();
  const id = useId();
  const geo = useGouvernorats();
  const own = user?.identity.gouvernoratCode ?? null;
  const national = own === null;
  const [kind, setKind] = useState<ZoneKind>(zone?.kind ?? "work");
  const [name, setName] = useState(zone?.name ?? "");
  const [margin, setMargin] = useState<number | null>(zone?.margin_m ?? 500);
  const [active, setActive] = useState(zone?.active ?? true);
  const [code, setCode] = useState<number | null>(own);
  const [vertices, setVertices] = useState<Vertex[]>(() =>
    zone ? fromPolygon({ type: "Polygon", coordinates: [zone.ring] }) : [],
  );
  const [drawing, setDrawing] = useState(vertices.length === 0);
  const [bounds] = useState(() => verticesBounds(vertices) ?? initialBoundsFor(own));
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => {
      const ring = vertices.map(([lon, lat]) => [lon, lat] as [number, number]);
      if (zone) return api.updateZone(zone.id, { name: name.trim(), ring, margin_m: margin ?? 0, active });
      return api.createZone({
        kind,
        name: name.trim(),
        ring,
        margin_m: margin ?? 0,
        gouvernorat_code: national ? code : null,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: droneKeys.all });
      onDone();
    },
    onError: (e) => setError(t(errorMessageKey(e))),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setError(null);
    if (name.trim().length < 2) {
      setError(t("drones.errors.zoneName"));
      return;
    }
    const problem = vertices.length > MAX_ZONE_VERTICES ? "too_many" : validateVertices(vertices);
    if (problem) {
      setError(t(`drones.errors.area.${problem}`, { max: MAX_ZONE_VERTICES }));
      return;
    }
    if (margin === null) {
      setError(t("drones.errors.margin"));
      return;
    }
    if (!zone && national && code === null) {
      setError(t("sensors.errors.gouvernorat"));
      return;
    }
    save.mutate();
  };
  return (
    <form className="card sensor-form" noValidate onSubmit={submit} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{zone ? t("drones.zone.editTitle", { name: zone.name }) : t("drones.zone.newTitle")}</h2>
      <RequiredNote />
      {!zone && (
        <fieldset className="segmented">
          <legend>{t("drones.zone.kindLabel")}</legend>
          {(["work", "no_fly"] as const).map((k) => (
            <label key={k} className="segmented__item">
              <input type="radio" name={`${id}-kind`} checked={kind === k} onChange={() => setKind(k)} />
              <span>{t(`drones.zone.kind.${k}`)}</span>
            </label>
          ))}
        </fieldset>
      )}
      <p className="muted">{t(`drones.zone.help.${zone?.kind ?? kind}`)}</p>
      <div className="field">
        <label htmlFor={`${id}-name`}>{t("drones.zone.name")}</label>
        <input
          id={`${id}-name`}
          dir="auto"
          required
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      {!zone && national && (
        <div className="field">
          <label htmlFor={`${id}-g`}>{t("filters.gouvernorat")}</label>
          <select
            id={`${id}-g`}
            required
            value={code ?? ""}
            onChange={(e) => setCode(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("referral.choose")}</option>
            {geo.list.map((g) => (
              <option key={g.code} value={g.code}>
                {g.name}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="field">
        <label id={`${id}-margin-label`} htmlFor={`${id}-margin`}>
          {t("drones.zone.margin")}
        </label>
        <Stepper
          id={`${id}-margin`}
          labelledBy={`${id}-margin-label`}
          label={t("drones.zone.marginShort")}
          value={margin}
          min={0}
          max={5000}
          step={100}
          onChange={setMargin}
          onClear={() => setMargin(null)}
        />
      </div>
      <div className="area-draw">
        <p className="muted">{t("drones.zone.drawHelp", { max: fmt.number(MAX_ZONE_VERTICES) })}</p>
        <Suspense fallback={<Loading />}>
          <LazyPolygonDrawMap
            className="map map--draw"
            vertices={vertices}
            onAddVertex={
              drawing && vertices.length < MAX_ZONE_VERTICES
                ? (lon, lat) => setVertices((v) => addVertex(v, lon, lat))
                : undefined
            }
            bounds={bounds}
            ariaLabel={t("drones.zone.mapLabel")}
            styleUrl={mapStyleUrl}
            dir={directionOf(lang)}
          />
        </Suspense>
        <p role="status" aria-live="polite">
          {t("notify.area.points", { count: fmt.number(vertices.length) })}
          {!drawing && ` · ${t("notify.area.closed")}`}
        </p>
        <div className="actions">
          {drawing ? (
            <button type="button" className="btn" disabled={vertices.length < 3} onClick={() => setDrawing(false)}>
              {t("notify.area.finish")}
            </button>
          ) : (
            <button type="button" className="btn" onClick={() => setDrawing(true)}>
              {t("notify.area.resume")}
            </button>
          )}
          <button
            type="button"
            className="btn btn--ghost"
            disabled={vertices.length === 0}
            onClick={() => setVertices((v) => undoVertex(v))}
          >
            {t("notify.area.undo")}
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={vertices.length === 0}
            onClick={() => {
              setVertices([]);
              setDrawing(true);
            }}
          >
            {t("notify.area.clear")}
          </button>
        </div>
      </div>
      {zone && (
        <label className="checkbox">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span>{t("drones.zone.active")}</span>
        </label>
      )}
      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {t("sensors.save")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function LastSeen({ drone, now }: { drone: Drone; now: number }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const last = drone.last;
  if (!last) return <span className="muted">{t("drones.position.none")}</span>;
  const parts = [
    last.alt_m !== null ? t("drones.altitude", { m: fmt.number(Math.round(last.alt_m)) }) : null,
    last.battery_pct !== null ? t("drones.battery", { pct: fmt.number(Math.round(last.battery_pct)) }) : null,
  ].filter(Boolean);
  return (
    <>
      <span className={`pill ${isFresh(drone, now) ? "tone-green" : "tone-slate"}`}>
        {t(isFresh(drone, now) ? "drones.position.fresh" : "drones.position.stale")}
      </span>{" "}
      {parts.join(" · ")}
      <div className="muted">{fmt.dateTime(last.at)}</div>
    </>
  );
}

export function DronesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const roles = user?.identity.roles ?? [];
  const registrar = useCan("drones.register", canManageDrones(roles));
  const zoner = useCan("drones.zones", canManageDrones(roles));
  const acker = useCan("drones.ack", canAcknowledgeDroneAlerts(roles));
  const [registering, setRegistering] = useState(false);
  const [shown, setShown] = useState<DroneCreated | null>(null);
  const [zoneEdit, setZoneEdit] = useState<Zone | "new" | null>(null);
  const list = useQuery({ queryKey: droneKeys.list, queryFn: ({ signal }) => api.drones(signal) });
  const alerts = useQuery({ queryKey: droneKeys.alerts, queryFn: ({ signal }) => api.droneAlerts(signal) });
  const zones = useQuery({ queryKey: droneKeys.zones, queryFn: ({ signal }) => api.droneZones(signal) });
  useLiveEvents((e) => {
    if (e.type === "drone.alert" || e.type === "stream.started" || e.type === "stream.ended") {
      void qc.invalidateQueries({ queryKey: droneKeys.all });
    } else if (e.type === "drone.telemetry") {
      void qc.invalidateQueries({ queryKey: droneKeys.list });
    }
  });
  const now = useNow(30_000);
  const items = [...(list.data?.items ?? [])].sort(
    (a, b) => b.open_alerts - a.open_alerts || a.label.localeCompare(b.label, "ar"),
  );
  const canRegister = registrar && Boolean(list.data?.can_register);
  return (
    <div className="page sensors-page">
      <div className="page__head">
        <PageTitle icon="drone" tone="purple">
          {t("drones.title")} <SimTag label={t("drones.simTag")} />
        </PageTitle>
        {canRegister && !registering && (
          <button type="button" className="btn btn--primary" onClick={() => setRegistering(true)}>
            {t("drones.new")}
          </button>
        )}
      </div>
      <p className="muted">
        {t("drones.intro")} <Link to="/map">{t("drones.toMap")}</Link>
      </p>
      <p className="alert alert--info" role="note">
        {t("drones.readOnly")}
      </p>
      {shown && <SecretsPanel shown={shown} onClose={() => setShown(null)} />}
      {registering && <RegisterForm onDone={() => setRegistering(false)} onCreated={setShown} />}
      {alerts.isError && <ErrorBox error={alerts.error} onRetry={() => void alerts.refetch()} />}
      {alerts.data && <AlertsCard alerts={alerts.data} canAck={acker} />}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && items.length === 0 && <p className="card ops-empty">{t("drones.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption>{t("drones.caption", { n: fmt.number(items.length) })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("sensors.field.name")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("drones.col.video")}</th>
                <th scope="col">{t("drones.col.position")}</th>
                <th scope="col">{t("drones.col.alerts")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <th scope="row" dir="auto">
                    {d.label}
                  </th>
                  <td>{d.gouvernorat_code !== null ? geo.nameOf(d.gouvernorat_code) : "—"}</td>
                  <td>
                    <VideoPill status={d.stream_status} />
                  </td>
                  <td>
                    <LastSeen drone={d} now={now} />
                  </td>
                  <td>
                    {d.open_alerts > 0 ? (
                      <span className="pill tone-red">{t("drones.openAlerts", { n: fmt.number(d.open_alerts) })}</span>
                    ) : (
                      <span className="muted">{t("drones.alerts.none")}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <section className="card" aria-labelledby="drone-zones-title">
        <div className="page__head">
          <h2 id="drone-zones-title">{t("drones.zone.title")}</h2>
          {zoner && zoneEdit === null && (
            <button type="button" className="btn" onClick={() => setZoneEdit("new")}>
              {t("drones.zone.new")}
            </button>
          )}
        </div>
        <p className="muted">{t("drones.zone.intro")}</p>
        {zones.isError && <ErrorBox error={zones.error} onRetry={() => void zones.refetch()} />}
        {zones.data && zones.data.length === 0 && <p className="muted">{t("drones.zone.none")}</p>}
        {zones.data && zones.data.length > 0 && (
          <div className="table-wrap">
            <table className="table table--compact">
              <caption className="visually-hidden">{t("drones.zone.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("drones.zone.name")}</th>
                  <th scope="col">{t("drones.zone.kindLabel")}</th>
                  <th scope="col">{t("filters.gouvernorat")}</th>
                  <th scope="col">{t("drones.zone.marginShort")}</th>
                  <th scope="col">
                    <span className="visually-hidden">{t("sensors.col.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {zones.data.map((z) => (
                  <tr key={z.id}>
                    <th scope="row" dir="auto">
                      {z.name}
                      {!z.active && <div className="muted">{t("drones.zone.off")}</div>}
                    </th>
                    <td>
                      <ZonePill kind={z.kind} />
                    </td>
                    <td>{geo.nameOf(z.gouvernorat_code)}</td>
                    <td>{t("drones.zone.metres", { m: fmt.number(z.margin_m) })}</td>
                    <td className="actions">
                      {zoner && zoneEdit === null && (
                        <button type="button" className="btn btn--small" onClick={() => setZoneEdit(z)}>
                          {t("sensors.edit")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {zoneEdit !== null && (
        <ZoneForm
          key={zoneEdit === "new" ? "new" : zoneEdit.id}
          zone={zoneEdit === "new" ? null : zoneEdit}
          onDone={() => setZoneEdit(null)}
        />
      )}
    </div>
  );
}
