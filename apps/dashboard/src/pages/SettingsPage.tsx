import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { AppReleaseCard, ModerationTermsCard } from "../components/PhaseASettings";
import { ReasonField } from "../components/Phase9Bits";
import { LocationHistoryCard } from "../components/SafetySettings";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat } from "../lib/hooks";
import {
  ACCESS_INFO_DAYS_RANGE,
  ACCURACY_RANGE,
  BAND_RANGE,
  bandsFrom,
  DELAY_RANGE,
  delaysFrom,
  QUOTA_RANGE,
  reasonValid,
  settingOf,
  usePlatformSettings,
  validateBands,
  validateDelays,
  validateIntRange,
  type SettingError,
} from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import { SLA_BANDS, type PlatformSetting } from "../lib/phase9Types";
import { CHECK_MAX_HOURS_RANGE, LIVE_MAX_MINUTES_RANGE } from "../lib/safetyApi";
import { PageTitle } from "../components/PageTitle";

type Values = Record<string, string>;

interface FieldSpec {
  name: string;
  label: string;
  unit?: string;
  min: number;
  max: number;
}

/**
 * One national setting as a form (§2): its fields, the reason of the change and the version it was read at. Without
 * `editable` (decided by the API for the caller) the values are shown read-only.
 */
function SettingCard({
  setting,
  title,
  help,
  fields,
  initial,
  toValue,
  validate,
  orderMessage,
}: {
  setting: PlatformSetting;
  title: string;
  help: string;
  fields: FieldSpec[];
  initial: Values;
  toValue: (v: Values) => unknown;
  validate: (v: Values) => SettingError | null;
  /** Message of an `order` error (each setting has its own rule). */
  orderMessage?: string;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [values, setValues] = useState<Values>(initial);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [saved, setSaved] = useState(false);
  const editable = setting.editable;
  const error = validate(values);

  const mutation = useMutation({
    mutationFn: () =>
      api.savePlatformSetting(setting.key, { value: toValue(values), version: setting.version, reason: reason.trim() }),
    onSuccess: (updated) => {
      qc.setQueryData<PlatformSetting[]>(p9Keys.settings, (items) => items?.map((s) => (s.key === updated.key ? updated : s)));
      setReason("");
      setTried(false);
      setSaved(true);
    },
    onError: (e) => {
      // Someone else saved first: reload the current value and version.
      if (isApiError(e) && e.code === "version_conflict") void qc.invalidateQueries({ queryKey: p9Keys.settings });
    },
  });

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    setSaved(false);
    if (error || !reasonValid(reason)) return;
    mutation.mutate();
  };

  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{title}</h2>
      <p className="muted">{help}</p>
      <form noValidate onSubmit={submit}>
        <div className="settings-grid">
          {fields.map((f) => (
            <div key={f.name} className={`field field--number${tried && error ? " field--invalid" : ""}`}>
              <label htmlFor={`${id}-${f.name}`}>{f.label}</label>
              <input
                id={`${id}-${f.name}`}
                type="number"
                inputMode="numeric"
                dir="ltr"
                min={f.min}
                max={f.max}
                step={1}
                value={values[f.name] ?? ""}
                readOnly={!editable}
                aria-invalid={tried && error ? true : undefined}
                onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              />
              {f.unit && <span className="muted">{f.unit}</span>}
            </div>
          ))}
        </div>
        {tried && error && (
          <p className="field__error" role="alert">
            {error === "order" && orderMessage
              ? orderMessage
              : t(`settings.validation.${error}`, {
                  min: fmt.number(fields[0]?.min ?? 0),
                  max: fmt.number(fields[0]?.max ?? 0),
                })}
          </p>
        )}
        <p className="muted">
          {setting.updated_at
            ? t("settings.lastChange", {
                name: setting.updated_by_name ?? t("claim.someone"),
                at: fmt.dateTime(setting.updated_at),
                version: setting.version,
              })
            : t("settings.defaultValue")}
        </p>
        {editable ? (
          <>
            <ReasonField label={t("settings.reason")} value={reason} onChange={setReason} showError={tried} />
            <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
              {mutation.isPending ? t("aiSettings.saving") : t("aiSettings.save")}
            </button>
          </>
        ) : (
          <p className="muted">{t("settings.readOnlyItem")}</p>
        )}
        <div role="status" aria-live="polite">
          {saved && !mutation.isPending && <p className="alert alert--ok">{t("aiSettings.saved")}</p>}
        </div>
        {mutation.isError && (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(mutation.error))}
          </p>
        )}
      </form>
    </section>
  );
}

const ints = (v: Values, names: readonly string[]) => names.map((n) => Number(v[n] === "" ? Number.NaN : v[n]));

/**
 * National settings (phase 9 §2): SLA delays and bands, anonymous quota, trusted location accuracy; phase A: the
 * mobile release and the extra refused words.
 */
export function SettingsPage() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const query = usePlatformSettings();

  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;

  const items = query.data;
  const delays = settingOf(items, "sla.claim_delay_s");
  const bands = settingOf(items, "sla.bands");
  const quota = settingOf(items, "anonymous.report_quota");
  const accuracy = settingOf(items, "geo.max_trusted_accuracy_m");
  const since = settingOf(items, "sla.enforced_since");
  const realSend = settingOf(items, "notify.real_send_enabled");
  const release = settingOf(items, "app.release");
  const extraTerms = settingOf(items, "moderation.extra_terms");
  const accessInfoDays = settingOf(items, "contact.access_info_days");
  const liveMax = settingOf(items, "safety.live_max_minutes");
  const checkMax = settingOf(items, "safety.check_max_hours");
  const locationHistory = settingOf(items, "safety.location_history");
  const anyEditable = items.some((s) => s.editable);
  const seconds = t("settings.seconds");

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="settings" tone="slate">{t("settings.title")}</PageTitle>
        <Link to="/settings/ai">{t("nav.aiSettings")}</Link>
      </div>
      <p className="muted">{t("settings.intro")}</p>
      {!anyEditable && <p className="alert alert--info">{t("settings.readOnly")}</p>}

      {delays && (
        <SettingCard
          key={`${delays.key}-${delays.version}`}
          setting={delays}
          title={t("settings.delays.title")}
          help={t("settings.delays.help")}
          orderMessage={t("settings.delays.order")}
          fields={SLA_BANDS.map((b) => ({ name: b, label: t(`sla.band.${b}`), unit: seconds, ...DELAY_RANGE }))}
          initial={Object.fromEntries(SLA_BANDS.map((b) => [b, String(delaysFrom(delays.value)[b])]))}
          toValue={(v) => Object.fromEntries(SLA_BANDS.map((b) => [b, Number(v[b])]))}
          validate={(v) => {
            const [critical = Number.NaN, high = Number.NaN, normal = Number.NaN, low = Number.NaN] = ints(v, SLA_BANDS);
            return validateDelays({ critical, high, normal, low });
          }}
        />
      )}

      {bands && (
        <SettingCard
          key={`${bands.key}-${bands.version}`}
          setting={bands}
          title={t("settings.bands.title")}
          help={t("settings.bands.help")}
          orderMessage={t("settings.bands.order")}
          fields={(["critical", "high", "normal"] as const).map((b) => ({
            name: b,
            label: t("settings.bands.lowerBound", { band: t(`sla.band.${b}`) }),
            ...BAND_RANGE,
          }))}
          initial={Object.fromEntries(Object.entries(bandsFrom(bands.value)).map(([k, n]) => [k, String(n)]))}
          toValue={(v) => ({ critical: Number(v.critical), high: Number(v.high), normal: Number(v.normal) })}
          validate={(v) => {
            const [critical = Number.NaN, high = Number.NaN, normal = Number.NaN] = ints(v, ["critical", "high", "normal"]);
            return validateBands({ critical, high, normal });
          }}
        />
      )}

      {quota && (
        <SettingCard
          key={`${quota.key}-${quota.version}`}
          setting={quota}
          title={t("settings.quota.title")}
          help={t("settings.quota.help")}
          fields={[{ name: "quota", label: t("settings.quota.label"), ...QUOTA_RANGE }]}
          initial={{ quota: String(typeof quota.value === "number" ? quota.value : 5) }}
          toValue={(v) => Number(v.quota)}
          validate={(v) => validateIntRange(Number(v.quota === "" ? Number.NaN : v.quota), QUOTA_RANGE)}
        />
      )}

      {accuracy && (
        <SettingCard
          key={`${accuracy.key}-${accuracy.version}`}
          setting={accuracy}
          title={t("settings.accuracy.title")}
          help={t("settings.accuracy.help")}
          fields={[{ name: "accuracy", label: t("settings.accuracy.label"), unit: t("settings.metres"), ...ACCURACY_RANGE }]}
          initial={{ accuracy: String(typeof accuracy.value === "number" ? accuracy.value : 1000) }}
          toValue={(v) => Number(v.accuracy)}
          validate={(v) => validateIntRange(Number(v.accuracy === "" ? Number.NaN : v.accuracy), ACCURACY_RANGE)}
        />
      )}

      {accessInfoDays && (
        <SettingCard
          key={`${accessInfoDays.key}-${accessInfoDays.version}`}
          setting={accessInfoDays}
          title={t("settings.accessInfoDays.title")}
          help={t("settings.accessInfoDays.help")}
          fields={[
            {
              name: "days",
              label: t("settings.accessInfoDays.label"),
              unit: t("settings.accessInfoDays.unit"),
              ...ACCESS_INFO_DAYS_RANGE,
            },
          ]}
          initial={{ days: String(typeof accessInfoDays.value === "number" ? accessInfoDays.value : 20) }}
          toValue={(v) => Number(v.days)}
          validate={(v) => validateIntRange(Number(v.days === "" ? Number.NaN : v.days), ACCESS_INFO_DAYS_RANGE)}
        />
      )}

      {release && <AppReleaseCard key={`${release.key}-${release.version}`} setting={release} />}

      {extraTerms && <ModerationTermsCard key={`${extraTerms.key}-${extraTerms.version}`} setting={extraTerms} />}

      {liveMax && (
        <SettingCard
          key={`${liveMax.key}-${liveMax.version}`}
          setting={liveMax}
          title={t("settings.liveMax.title")}
          help={t("settings.liveMax.help")}
          fields={[{ name: "minutes", label: t("settings.liveMax.label"), unit: t("settings.minutes"), ...LIVE_MAX_MINUTES_RANGE }]}
          initial={{ minutes: String(typeof liveMax.value === "number" ? liveMax.value : 480) }}
          toValue={(v) => Number(v.minutes)}
          validate={(v) => validateIntRange(Number(v.minutes === "" ? Number.NaN : v.minutes), LIVE_MAX_MINUTES_RANGE)}
        />
      )}

      {checkMax && (
        <SettingCard
          key={`${checkMax.key}-${checkMax.version}`}
          setting={checkMax}
          title={t("settings.checkMax.title")}
          help={t("settings.checkMax.help")}
          fields={[{ name: "hours", label: t("settings.checkMax.label"), unit: t("settings.hours"), ...CHECK_MAX_HOURS_RANGE }]}
          initial={{ hours: String(typeof checkMax.value === "number" ? checkMax.value : 24) }}
          toValue={(v) => Number(v.hours)}
          validate={(v) => validateIntRange(Number(v.hours === "" ? Number.NaN : v.hours), CHECK_MAX_HOURS_RANGE)}
        />
      )}

      {locationHistory && (
        <LocationHistoryCard key={`${locationHistory.key}-${locationHistory.version}`} setting={locationHistory} />
      )}

      <section className="card" aria-labelledby="settings-fixed">
        <h2 id="settings-fixed">{t("settings.fixed.title")}</h2>
        <dl className="fields">
          <dt>{t("settings.fixed.enforcedSince")}</dt>
          <dd>{typeof since?.value === "string" ? fmt.dateTime(since.value) : t("common.notAvailable")}</dd>
          <dt>{t("settings.fixed.realSend")}</dt>
          <dd>
            {realSend?.value === true ? t("common.yes") : t("common.no")}
            <span className="muted"> · {t("settings.fixed.realSendNote")}</span>
          </dd>
        </dl>
      </section>
    </div>
  );
}
