// covers: phase L5b (docs/phase-l/design-l5.md §3.2, docs/sensor-gateway.md): the watch towers of the local network,
// their camera, their field of view, the fire or smoke their edge computer confirmed, and for the operations manager
// the register, the bearing and the keys (shown once). An event becomes a suggestion in the alert centre, never a report.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { RequiredNote } from "../components/PhaseASettings";
import { Stepper } from "../components/Stepper";
import { SimTag } from "../components/StreamBits";
import { useAuth } from "../context/auth";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useCan } from "../lib/features";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { useNow } from "../lib/phase9";
import { canManageTowers } from "../lib/roles";
import {
  compassOf,
  recentEvent,
  towerKeys,
  type Tower,
  type TowerCreated,
  type TowerIn,
  type TowerLabel,
} from "../lib/towers";

function EventPill({ label }: { label: TowerLabel }) {
  const { t } = useTranslation();
  return <span className={`pill ${label === "fire" ? "tone-red" : "tone-amber"}`}>{t(`towers.label.${label}`)}</span>;
}

function CameraPill({ status }: { status: string }) {
  const { t } = useTranslation();
  const live = status === "live";
  return (
    <span className={`pill ${live ? "tone-green" : "tone-slate"}`}>
      {t(live ? "towers.camera.live" : "towers.camera.off")}
    </span>
  );
}

interface FormValues {
  code: string;
  label: string;
  gouvernorat_code: number | null;
  lat: string;
  lon: string;
  bearing_deg: number | null;
  fov_deg: number | null;
  range_m: number | null;
  simulated: boolean;
}

function blank(own: number | null): FormValues {
  return {
    code: "",
    label: "",
    gouvernorat_code: own,
    lat: "",
    lon: "",
    bearing_deg: 0,
    fov_deg: 60,
    range_m: 8000,
    simulated: true,
  };
}

function fromTower(tw: Tower): FormValues {
  return {
    code: tw.code,
    label: tw.label,
    gouvernorat_code: tw.gouvernorat_code,
    lat: String(tw.lat),
    lon: String(tw.lon),
    bearing_deg: tw.bearing_deg,
    fov_deg: tw.fov_deg,
    range_m: tw.range_m,
    simulated: tw.simulated,
  };
}

function TowerForm({
  tower,
  onDone,
  onCreated,
}: {
  tower: Tower | null;
  onDone: () => void;
  onCreated: (c: TowerCreated) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const id = useId();
  const geo = useGouvernorats();
  const own = user?.identity.gouvernoratCode ?? null;
  const national = own === null;
  const [form, setForm] = useState<FormValues>(() => (tower ? fromTower(tower) : blank(own)));
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof FormValues>(k: K, v: FormValues[K]) => setForm((f) => ({ ...f, [k]: v }));
  const save = useMutation({
    mutationFn: async () => {
      const common = {
        label: form.label.trim(),
        lat: Number(form.lat),
        lon: Number(form.lon),
        bearing_deg: form.bearing_deg ?? 0,
        fov_deg: form.fov_deg ?? 60,
        range_m: form.range_m ?? 8000,
      };
      if (tower) {
        await api.updateTower(tower.id, common);
        return null;
      }
      const body: TowerIn = {
        ...common,
        code: form.code.trim(),
        gouvernorat_code: national ? form.gouvernorat_code : null,
        simulated: form.simulated,
      };
      return api.createTower(body);
    },
    onSuccess: (created) => {
      void qc.invalidateQueries({ queryKey: towerKeys.all });
      if (created) onCreated(created);
      onDone();
    },
    onError: (e) => setError(t(errorMessageKey(e))),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setError(null);
    const lat = Number(form.lat);
    const lon = Number(form.lon);
    if (!tower && !/^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$/.test(form.code.trim())) {
      setError(t("sensors.errors.code"));
      return;
    }
    if (form.label.trim().length < 2) {
      setError(t("towers.errors.label"));
      return;
    }
    if (!(lat >= 30 && lat <= 38 && lon >= 7 && lon <= 12)) {
      setError(t("sensors.errors.place"));
      return;
    }
    if (form.bearing_deg === null || form.fov_deg === null || form.range_m === null) {
      setError(t("towers.errors.view"));
      return;
    }
    if (!tower && national && form.gouvernorat_code === null) {
      setError(t("sensors.errors.gouvernorat"));
      return;
    }
    save.mutate();
  };
  return (
    <form className="card sensor-form" noValidate onSubmit={submit} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{tower ? t("towers.form.editTitle", { name: tower.label }) : t("towers.form.newTitle")}</h2>
      <RequiredNote />
      {!tower && (
        <div className="field">
          <label htmlFor={`${id}-code`}>{t("sensors.field.code")}</label>
          <input
            id={`${id}-code`}
            dir="ltr"
            required
            maxLength={40}
            value={form.code}
            aria-describedby={`${id}-code-help`}
            onChange={(e) => set("code", e.target.value)}
          />
          <p className="muted" id={`${id}-code-help`}>
            {t("towers.field.codeHelp")}
          </p>
        </div>
      )}
      <div className="field">
        <label htmlFor={`${id}-label`}>{t("sensors.field.name")}</label>
        <input
          id={`${id}-label`}
          dir="auto"
          required
          maxLength={100}
          value={form.label}
          onChange={(e) => set("label", e.target.value)}
        />
      </div>
      {!tower && national && (
        <div className="field">
          <label htmlFor={`${id}-g`}>{t("filters.gouvernorat")}</label>
          <select
            id={`${id}-g`}
            required
            value={form.gouvernorat_code ?? ""}
            onChange={(e) => set("gouvernorat_code", e.target.value ? Number(e.target.value) : null)}
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
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${id}-lat`}>{t("sensors.field.lat")}</label>
          <input
            id={`${id}-lat`}
            dir="ltr"
            required
            inputMode="decimal"
            value={form.lat}
            onChange={(e) => set("lat", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-lon`}>{t("sensors.field.lon")}</label>
          <input
            id={`${id}-lon`}
            dir="ltr"
            required
            inputMode="decimal"
            value={form.lon}
            onChange={(e) => set("lon", e.target.value)}
          />
        </div>
      </div>
      <div className="filters__row">
        <div className="field">
          <label id={`${id}-bearing-label`} htmlFor={`${id}-bearing`}>
            {t("towers.field.bearing")}
          </label>
          <Stepper
            id={`${id}-bearing`}
            labelledBy={`${id}-bearing-label`}
            label={t("towers.field.bearingShort")}
            value={form.bearing_deg}
            min={0}
            max={359}
            step={5}
            onChange={(v) => set("bearing_deg", v)}
            onClear={() => set("bearing_deg", null)}
          />
          {form.bearing_deg !== null && (
            <p className="muted" aria-live="polite">
              {t(`towers.compass.${compassOf(form.bearing_deg)}`)}
            </p>
          )}
        </div>
        <div className="field">
          <label id={`${id}-fov-label`} htmlFor={`${id}-fov`}>
            {t("towers.field.fov")}
          </label>
          <Stepper
            id={`${id}-fov`}
            labelledBy={`${id}-fov-label`}
            label={t("towers.field.fovShort")}
            value={form.fov_deg}
            min={5}
            max={360}
            step={5}
            onChange={(v) => set("fov_deg", v)}
            onClear={() => set("fov_deg", null)}
          />
        </div>
        <div className="field">
          <label id={`${id}-range-label`} htmlFor={`${id}-range`}>
            {t("towers.field.range")}
          </label>
          <Stepper
            id={`${id}-range`}
            labelledBy={`${id}-range-label`}
            label={t("towers.field.rangeShort")}
            value={form.range_m}
            min={100}
            max={50000}
            step={500}
            onChange={(v) => set("range_m", v)}
            onClear={() => set("range_m", null)}
          />
        </div>
      </div>
      {!tower && (
        <label className="checkbox">
          <input type="checkbox" checked={form.simulated} onChange={(e) => set("simulated", e.target.checked)} />
          <span>{t("towers.field.simulated")}</span>
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

/** What is shown once: the edge computer's key, and after a creation the camera's publish address and token. */
function SecretsPanel({ shown, onClose }: { shown: TowerCreated | { tower: Tower; edge_key: string }; onClose: () => void }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = () => {
    // On plain http inside the local network the clipboard may be missing: the key stays on screen to copy by hand.
    void Promise.resolve()
      .then(() => navigator.clipboard.writeText(shown.edge_key))
      .then(() => setCopied(true))
      .catch(() => setCopied(false));
  };
  const created = "publish_token" in shown ? shown : null;
  return (
    <section className="card sensor-key" aria-labelledby="tower-key-title">
      <h2 id="tower-key-title">{t("towers.key.title", { code: shown.tower.code })}</h2>
      <p className="alert alert--warn" role="note">
        {t("towers.key.once")}
      </p>
      <dl className="fields">
        <div className="ops-dl-row">
          <dt>{t("towers.key.edge")}</dt>
          <dd className="code sensor-key__value" dir="ltr">
            {shown.edge_key}
          </dd>
        </div>
        {created && (
          <>
            <div className="ops-dl-row">
              <dt>{t("towers.key.rtsp")}</dt>
              <dd className="code" dir="ltr">
                {created.publish_url_rtsp}
              </dd>
            </div>
            <div className="ops-dl-row">
              <dt>{t("towers.key.token")}</dt>
              <dd className="code sensor-key__value" dir="ltr">
                {created.publish_token}
              </dd>
            </div>
          </>
        )}
      </dl>
      <div className="actions">
        <button type="button" className="btn btn--primary" onClick={copy}>
          {copied ? t("sensors.key.copied") : t("towers.key.copy")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("sensors.key.done")}
        </button>
      </div>
      <p className="muted">{t("towers.key.howTo")}</p>
    </section>
  );
}

function Events({ tower }: { tower: Tower }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const hours = 24;
  const q = useQuery({
    queryKey: towerKeys.events(tower.id, hours),
    queryFn: ({ signal }) => api.towerEvents(tower.id, hours, signal),
  });
  const items = q.data?.items ?? [];
  return (
    <section className="card" aria-labelledby={`events-${tower.id}`}>
      <h2 id={`events-${tower.id}`}>{t("towers.events.title", { name: tower.label })}</h2>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && items.length === 0 && <p className="muted">{t("towers.events.none")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption className="visually-hidden">{t("towers.events.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("sensors.readings.at")}</th>
                <th scope="col">{t("towers.events.what")}</th>
                <th scope="col">{t("towers.events.confidence")}</th>
                <th scope="col">{t("towers.events.frames")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={`${e.at}-${e.label}`}>
                  <td>{fmt.dateTime(e.at)}</td>
                  <td>
                    <EventPill label={e.label} />
                  </td>
                  <td dir="ltr">{fmt.percent(e.confidence)}</td>
                  <td>{t("towers.events.hits", { hits: fmt.number(e.hits), frames: fmt.number(e.frames) })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function TowersPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const manager = useCan("towers.manage", canManageTowers(user?.identity.roles ?? []));
  const rotator = useCan("towers.key", canManageTowers(user?.identity.roles ?? []));
  const [editing, setEditing] = useState<Tower | "new" | null>(null);
  const [shown, setShown] = useState<TowerCreated | { tower: Tower; edge_key: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: towerKeys.all, queryFn: ({ signal }) => api.towers(signal) });
  useLiveEvents((e) => {
    if (e.type === "stream.alert" || e.type === "stream.started" || e.type === "stream.ended") {
      void qc.invalidateQueries({ queryKey: towerKeys.all });
    }
  });
  const rotate = useMutation({
    mutationFn: (tw: Tower) => api.rotateTowerKey(tw.id),
    onSuccess: (k) => {
      setShown(k);
      void qc.invalidateQueries({ queryKey: towerKeys.all });
    },
  });
  const now = useNow(60_000);
  const items = [...(list.data?.items ?? [])].sort(
    (a, b) =>
      Number(recentEvent(b, now) !== null) - Number(recentEvent(a, now) !== null) || a.label.localeCompare(b.label, "ar"),
  );
  const chosen = items.find((tw) => tw.id === selected) ?? null;
  return (
    <div className="page sensors-page">
      <div className="page__head">
        <PageTitle icon="videocam" tone="orange">
          {t("towers.title")}
        </PageTitle>
        {manager && list.data?.can_manage && editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("towers.new")}
          </button>
        )}
      </div>
      <p className="muted">
        {t("towers.intro")} <Link to="/weather/suggestions">{t("sensors.toSuggestions")}</Link>
      </p>
      {shown && <SecretsPanel shown={shown} onClose={() => setShown(null)} />}
      {rotate.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(rotate.error))}
        </p>
      )}
      {editing !== null && (
        <TowerForm
          key={editing === "new" ? "new" : editing.id}
          tower={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
          onCreated={setShown}
        />
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && items.length === 0 && <p className="card ops-empty">{t("towers.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption>{t("towers.caption", { n: fmt.number(items.length) })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("sensors.field.name")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("towers.col.camera")}</th>
                <th scope="col">{t("towers.col.view")}</th>
                <th scope="col">{t("towers.col.last")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("sensors.col.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((tw) => (
                <tr key={tw.id} aria-selected={selected === tw.id}>
                  <th scope="row" dir="auto">
                    {tw.label} {tw.simulated && <SimTag />}
                    <div className="code muted" dir="ltr">
                      {tw.code}
                    </div>
                  </th>
                  <td>{geo.nameOf(tw.gouvernorat_code)}</td>
                  <td>
                    <CameraPill status={tw.stream_status} />
                  </td>
                  <td>
                    {t("towers.view", {
                      direction: t(`towers.compass.${compassOf(tw.bearing_deg)}`),
                      bearing: fmt.number(tw.bearing_deg),
                      fov: fmt.number(tw.fov_deg),
                      km: fmt.decimal(tw.range_m / 1000),
                    })}
                  </td>
                  <td>
                    {tw.last_event ? (
                      <>
                        <EventPill label={tw.last_event.label} /> {fmt.percent(tw.last_event.confidence)}
                        <div className="muted">{fmt.dateTime(tw.last_event.at)}</div>
                      </>
                    ) : (
                      <span className="muted">{t("towers.events.none")}</span>
                    )}
                  </td>
                  <td className="actions">
                    <button
                      type="button"
                      className="btn btn--small"
                      aria-pressed={selected === tw.id}
                      onClick={() => setSelected(selected === tw.id ? null : tw.id)}
                    >
                      {t("towers.events.show")}
                    </button>
                    {manager && list.data?.can_manage && (
                      <button type="button" className="btn btn--small" onClick={() => setEditing(tw)}>
                        {t("sensors.edit")}
                      </button>
                    )}
                    {rotator && list.data?.can_manage && (
                      <button
                        type="button"
                        className="btn btn--small"
                        disabled={rotate.isPending}
                        onClick={() => {
                          if (window.confirm(t("towers.key.confirmRotate", { code: tw.code }))) rotate.mutate(tw);
                        }}
                      >
                        {t("towers.key.rotate")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {chosen && <Events tower={chosen} />}
    </div>
  );
}
