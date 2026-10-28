// covers: phase L5b (docs/phase-l/design-l5.md §3.0 and §3.1, docs/sensor-gateway.md): the sensors of the local
// network, their level live, their last readings, and for the operations manager the register, the thresholds and the
// signing key (shown once). A crossed threshold becomes a suggestion in the alert centre, never a message from here.
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
import { canManageSensors } from "../lib/roles";
import {
  KIND_RANGE,
  SENSOR_KINDS,
  STATE_ORDER,
  sensorKeys,
  type Sensor,
  type SensorIn,
  type SensorKey,
  type SensorKind,
  type SensorState,
} from "../lib/sensors";

const STATE_TONE: Record<SensorState, string> = {
  alarm: "tone-red",
  watch: "tone-amber",
  silent: "tone-slate",
  normal: "tone-green",
  disabled: "tone-slate",
};

function StatePill({ state }: { state: SensorState }) {
  const { t } = useTranslation();
  return <span className={`pill ${STATE_TONE[state]}`}>{t(`sensors.state.${state}`)}</span>;
}

/** A value with the sensor's unit, in the user's number format. */
function useValue() {
  const fmt = useFormat();
  return (value: number | null, unit: string) => (value === null ? "—" : `${fmt.decimal(value)} ${unit}`);
}

interface FormValues {
  code: string;
  name: string;
  kind: SensorKind;
  gouvernorat_code: number | null;
  lat: string;
  lon: string;
  provider: string;
  watch_threshold: number | null;
  alarm_threshold: number | null;
  silent_after_min: number | null;
  simulated: boolean;
  enabled: boolean;
}

const PROVIDERS = ["providers.office", "providers.inm", "providers.agriculture"] as const;

function blank(own: number | null): FormValues {
  return {
    code: "",
    name: "",
    kind: "rain_1h",
    gouvernorat_code: own,
    lat: "",
    lon: "",
    provider: "",
    watch_threshold: 20,
    alarm_threshold: 40,
    silent_after_min: 30,
    simulated: true,
    enabled: true,
  };
}

function fromSensor(s: Sensor): FormValues {
  return {
    code: s.code,
    name: s.name,
    kind: s.kind,
    gouvernorat_code: s.gouvernorat_code,
    lat: String(s.lat),
    lon: String(s.lon),
    provider: s.provider,
    watch_threshold: s.watch_threshold,
    alarm_threshold: s.alarm_threshold,
    silent_after_min: s.silent_after_min,
    simulated: s.simulated,
    enabled: s.enabled,
  };
}

function SensorForm({
  sensor,
  onDone,
  onKey,
}: {
  sensor: Sensor | null;
  onDone: () => void;
  onKey: (k: SensorKey) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const id = useId();
  const geo = useGouvernorats();
  const own = user?.identity.gouvernoratCode ?? null;
  const national = own === null;
  const [form, setForm] = useState<FormValues>(() => (sensor ? fromSensor(sensor) : blank(own)));
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof FormValues>(k: K, v: FormValues[K]) => setForm((f) => ({ ...f, [k]: v }));
  const range = KIND_RANGE[form.kind];
  const save = useMutation({
    mutationFn: async () => {
      const lat = Number(form.lat);
      const lon = Number(form.lon);
      const common = {
        name: form.name.trim(),
        lat,
        lon,
        provider: form.provider.trim(),
        watch_threshold: form.watch_threshold ?? 0,
        alarm_threshold: form.alarm_threshold ?? 0,
        silent_after_min: form.silent_after_min ?? 30,
      };
      if (sensor) {
        await api.updateSensor(sensor.id, { ...common, enabled: form.enabled });
        return null;
      }
      const body: SensorIn = {
        ...common,
        code: form.code.trim(),
        kind: form.kind,
        gouvernorat_code: national ? form.gouvernorat_code : null,
        simulated: form.simulated,
      };
      return api.createSensor(body);
    },
    onSuccess: (created) => {
      void qc.invalidateQueries({ queryKey: sensorKeys.all });
      if (created) onKey(created);
      onDone();
    },
    onError: (e) => setError(t(errorMessageKey(e))),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setError(null);
    const lat = Number(form.lat);
    const lon = Number(form.lon);
    if (!sensor && !/^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$/.test(form.code.trim())) {
      setError(t("sensors.errors.code"));
      return;
    }
    if (form.name.trim().length < 2 || form.provider.trim().length < 2) {
      setError(t("sensors.errors.required"));
      return;
    }
    if (!(lat >= 30 && lat <= 38 && lon >= 7 && lon <= 12)) {
      setError(t("sensors.errors.place"));
      return;
    }
    if (form.watch_threshold === null || form.alarm_threshold === null || form.alarm_threshold < form.watch_threshold) {
      setError(t("sensors.errors.thresholds"));
      return;
    }
    if (!sensor && national && form.gouvernorat_code === null) {
      setError(t("sensors.errors.gouvernorat"));
      return;
    }
    save.mutate();
  };
  return (
    <form className="card sensor-form" noValidate onSubmit={submit} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{sensor ? t("sensors.form.editTitle", { name: sensor.name }) : t("sensors.form.newTitle")}</h2>
      <RequiredNote />
      {!sensor && (
        <>
          <fieldset className="segmented">
            <legend>{t("sensors.field.kind")}</legend>
            {SENSOR_KINDS.map((k) => (
              <label key={k} className="segmented__item">
                <input
                  type="radio"
                  name={`${id}-kind`}
                  checked={form.kind === k}
                  onChange={() => {
                    const r = KIND_RANGE[k];
                    const defaults: Record<SensorKind, [number, number]> = {
                      rain_1h: [20, 40],
                      water_level: [2, 3.5],
                      temperature: [40, 45],
                    };
                    setForm((f) => ({
                      ...f,
                      kind: k,
                      watch_threshold: Math.min(Math.max(defaults[k][0], r.min), r.max),
                      alarm_threshold: Math.min(Math.max(defaults[k][1], r.min), r.max),
                    }));
                  }}
                />
                <span>{t(`sensors.kind.${k}`)}</span>
              </label>
            ))}
          </fieldset>
          <div className="field">
            <label htmlFor={`${id}-code`}>
              {t("sensors.field.code")}
            </label>
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
              {t("sensors.field.codeHelp")}
            </p>
          </div>
        </>
      )}
      <div className="field">
        <label htmlFor={`${id}-name`}>
          {t("sensors.field.name")}
        </label>
        <input id={`${id}-name`} dir="auto" required maxLength={120} value={form.name} onChange={(e) => set("name", e.target.value)} />
      </div>
      {!sensor && national && (
        <div className="field">
          <label htmlFor={`${id}-g`}>
            {t("filters.gouvernorat")}
          </label>
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
          <label htmlFor={`${id}-lat`}>
            {t("sensors.field.lat")}
          </label>
          <input id={`${id}-lat`} dir="ltr" required inputMode="decimal" value={form.lat} onChange={(e) => set("lat", e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-lon`}>
            {t("sensors.field.lon")}
          </label>
          <input id={`${id}-lon`} dir="ltr" required inputMode="decimal" value={form.lon} onChange={(e) => set("lon", e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-provider`}>
          {t("sensors.field.provider")}
        </label>
        <input
          id={`${id}-provider`}
          dir="auto"
          required
          list={`${id}-providers`}
          maxLength={80}
          value={form.provider}
          onChange={(e) => set("provider", e.target.value)}
        />
        <datalist id={`${id}-providers`}>
          {PROVIDERS.map((p) => (
            <option key={p} value={t(`sensors.${p}`)} />
          ))}
        </datalist>
      </div>
      <div className="filters__row">
        <div className="field">
          <label id={`${id}-watch-label`} htmlFor={`${id}-watch`}>
            {t("sensors.field.watch", { unit: t(`sensors.unit.${form.kind}`) })}
          </label>
          <Stepper
            id={`${id}-watch`}
            labelledBy={`${id}-watch-label`}
            label={t("sensors.field.watchShort")}
            value={form.watch_threshold}
            min={range.min}
            max={range.max}
            step={range.step}
            onChange={(v) => set("watch_threshold", v)}
            onClear={() => set("watch_threshold", null)}
          />
        </div>
        <div className="field">
          <label id={`${id}-alarm-label`} htmlFor={`${id}-alarm`}>
            {t("sensors.field.alarm", { unit: t(`sensors.unit.${form.kind}`) })}
          </label>
          <Stepper
            id={`${id}-alarm`}
            labelledBy={`${id}-alarm-label`}
            label={t("sensors.field.alarmShort")}
            value={form.alarm_threshold}
            min={range.min}
            max={range.max}
            step={range.step}
            onChange={(v) => set("alarm_threshold", v)}
            onClear={() => set("alarm_threshold", null)}
          />
        </div>
        <div className="field">
          <label id={`${id}-silent-label`} htmlFor={`${id}-silent`}>
            {t("sensors.field.silent")}
          </label>
          <Stepper
            id={`${id}-silent`}
            labelledBy={`${id}-silent-label`}
            label={t("sensors.field.silentShort")}
            value={form.silent_after_min}
            min={5}
            max={1440}
            step={5}
            onChange={(v) => set("silent_after_min", v)}
            onClear={() => set("silent_after_min", null)}
          />
        </div>
      </div>
      {sensor ? (
        <label className="checkbox">
          <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <span>{t("sensors.field.enabled")}</span>
        </label>
      ) : (
        <label className="checkbox">
          <input type="checkbox" checked={form.simulated} onChange={(e) => set("simulated", e.target.checked)} />
          <span>{t("sensors.field.simulated")}</span>
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

/** The signing key, shown this once: copy it into the sensor now. */
function KeyPanel({ shown, onClose }: { shown: SensorKey; onClose: () => void }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = () => {
    // On plain http inside the local network the clipboard may be missing: the key stays on screen to copy by hand.
    void Promise.resolve()
      .then(() => navigator.clipboard.writeText(shown.key))
      .then(() => setCopied(true))
      .catch(() => setCopied(false));
  };
  return (
    <section className="card sensor-key" aria-labelledby="sensor-key-title">
      <h2 id="sensor-key-title">{t("sensors.key.title", { code: shown.sensor.code })}</h2>
      <p className="alert alert--warn" role="note">
        {t("sensors.key.once")}
      </p>
      <p className="code sensor-key__value" dir="ltr">
        {shown.key}
      </p>
      <div className="actions">
        <button type="button" className="btn btn--primary" onClick={copy}>
          {copied ? t("sensors.key.copied") : t("sensors.key.copy")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("sensors.key.done")}
        </button>
      </div>
      <p className="muted">{t("sensors.key.howTo")}</p>
    </section>
  );
}

function Readings({ sensor }: { sensor: Sensor }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const value = useValue();
  const hours = 24;
  const q = useQuery({
    queryKey: sensorKeys.readings(sensor.id, hours),
    queryFn: ({ signal }) => api.sensorReadings(sensor.id, hours, signal),
  });
  const items = [...(q.data?.items ?? [])].reverse().slice(0, 48);
  return (
    <section className="card" aria-labelledby={`readings-${sensor.id}`}>
      <h2 id={`readings-${sensor.id}`}>{t("sensors.readings.title", { name: sensor.name })}</h2>
      <p className="muted">
        {t("sensors.readings.thresholds", {
          watch: value(sensor.watch_threshold, sensor.unit),
          alarm: value(sensor.alarm_threshold, sensor.unit),
        })}
      </p>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && items.length === 0 && <p className="muted">{t("sensors.readings.none")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption className="visually-hidden">{t("sensors.readings.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("sensors.readings.at")}</th>
                <th scope="col">{t("sensors.readings.value")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => {
                const level = r.value >= sensor.alarm_threshold ? "alarm" : r.value >= sensor.watch_threshold ? "watch" : null;
                return (
                  <tr key={r.at}>
                    <td>{fmt.dateTime(r.at)}</td>
                    <td dir="ltr">
                      {value(r.value, sensor.unit)} {level && <StatePill state={level} />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function SensorsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const value = useValue();
  const manager = useCan("sensors.manage", canManageSensors(user?.identity.roles ?? []));
  const rotator = useCan("sensors.key", canManageSensors(user?.identity.roles ?? []));
  const [editing, setEditing] = useState<Sensor | "new" | null>(null);
  const [shown, setShown] = useState<SensorKey | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: sensorKeys.all, queryFn: ({ signal }) => api.sensors(signal) });
  useLiveEvents((e) => {
    if (e.type === "sensor.reading") void qc.invalidateQueries({ queryKey: sensorKeys.all });
  });
  const rotate = useMutation({
    mutationFn: (s: Sensor) => api.rotateSensorKey(s.id),
    onSuccess: (k) => {
      setShown(k);
      void qc.invalidateQueries({ queryKey: sensorKeys.all });
    },
  });
  const items = [...(list.data?.items ?? [])].sort(
    (a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state] || a.name.localeCompare(b.name, "ar"),
  );
  const counts = items.reduce<Partial<Record<SensorState, number>>>((acc, s) => ({ ...acc, [s.state]: (acc[s.state] ?? 0) + 1 }), {});
  const chosen = items.find((s) => s.id === selected) ?? null;
  return (
    <div className="page sensors-page">
      <div className="page__head">
        <PageTitle icon="water" tone="sky">
          {t("sensors.title")}
        </PageTitle>
        {manager && list.data?.can_manage && editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("sensors.new")}
          </button>
        )}
      </div>
      <p className="muted">
        {t("sensors.intro")} <Link to="/weather/suggestions">{t("sensors.toSuggestions")}</Link>
      </p>
      {shown && <KeyPanel shown={shown} onClose={() => setShown(null)} />}
      {rotate.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(rotate.error))}
        </p>
      )}
      {editing !== null && (
        <SensorForm
          key={editing === "new" ? "new" : editing.id}
          sensor={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
          onKey={setShown}
        />
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && items.length === 0 && <p className="card ops-empty">{t("sensors.empty")}</p>}
      {items.length > 0 && (
        <>
          <ul className="sensor-counts" aria-label={t("sensors.countsLabel")}>
            {(["alarm", "watch", "silent", "normal"] as const).map((s) => (
              <li key={s}>
                <StatePill state={s} /> <strong>{fmt.number(counts[s] ?? 0)}</strong>
              </li>
            ))}
          </ul>
          <div className="table-wrap">
            <table className="table">
              <caption>{t("sensors.caption", { n: fmt.number(items.length) })}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("sensors.field.name")}</th>
                  <th scope="col">{t("sensors.field.kind")}</th>
                  <th scope="col">{t("filters.gouvernorat")}</th>
                  <th scope="col">{t("sensors.col.last")}</th>
                  <th scope="col">{t("sensors.col.state")}</th>
                  <th scope="col">{t("sensors.col.thresholds")}</th>
                  <th scope="col">
                    <span className="visually-hidden">{t("sensors.col.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.id} aria-selected={selected === s.id}>
                    <th scope="row" dir="auto">
                      {s.name} {s.simulated && <SimTag />}
                      <div className="code muted" dir="ltr">
                        {s.code} · {s.provider}
                      </div>
                    </th>
                    <td>{t(`sensors.kind.${s.kind}`)}</td>
                    <td>{geo.nameOf(s.gouvernorat_code)}</td>
                    <td>
                      <span dir="ltr">{value(s.last_value, s.unit)}</span>
                      {s.last_at && <div className="muted">{fmt.dateTime(s.last_at)}</div>}
                    </td>
                    <td>
                      <StatePill state={s.state} />
                    </td>
                    <td dir="ltr">
                      {fmt.decimal(s.watch_threshold)} / {fmt.decimal(s.alarm_threshold)} {s.unit}
                    </td>
                    <td className="actions">
                      <button
                        type="button"
                        className="btn btn--small"
                        aria-pressed={selected === s.id}
                        onClick={() => setSelected(selected === s.id ? null : s.id)}
                      >
                        {t("sensors.readings.show")}
                      </button>
                      {manager && list.data?.can_manage && (
                        <button type="button" className="btn btn--small" onClick={() => setEditing(s)}>
                          {t("sensors.edit")}
                        </button>
                      )}
                      {rotator && list.data?.can_manage && (
                        <button
                          type="button"
                          className="btn btn--small"
                          disabled={rotate.isPending}
                          onClick={() => {
                            if (window.confirm(t("sensors.key.confirmRotate", { code: s.code }))) rotate.mutate(s);
                          }}
                        >
                          {t("sensors.key.rotate")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {chosen && <Readings sensor={chosen} />}
    </div>
  );
}
