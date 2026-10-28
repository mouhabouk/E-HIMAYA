import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat } from "../lib/hooks";
import {
  BUILD_RANGE,
  LANGS,
  NOTES_MAX,
  parseTerms,
  releaseFrom,
  TERM_LENGTH,
  TERMS_MAX,
  termsFrom,
  validateRelease,
  type AppReleaseValue,
} from "../lib/phaseA";
import { reasonValid } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import type { PlatformSetting } from "../lib/phase9Types";
import { ReasonField } from "./Phase9Bits";
import { Stepper } from "./Stepper";

/** "Fields marked * are required." at the top of a form (phase A, rule 2). */
export function RequiredNote() {
  const { t } = useTranslation();
  return <p className="muted required-note">{t("common.requiredNote")}</p>;
}

/** Card, reason, save button and outcome shared by the phase A settings (same behaviour as the phase 9 cards). */
export function SettingForm({
  setting,
  title,
  help,
  error,
  toValue,
  children,
}: {
  setting: PlatformSetting;
  title: string;
  help: string;
  /** Message of the first problem of the form, or null when it can be sent. */
  error: string | null;
  toValue: () => unknown;
  children: (tried: boolean) => ReactNode;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      api.savePlatformSetting(setting.key, { value: toValue(), version: setting.version, reason: reason.trim() }),
    onSuccess: (updated) => {
      qc.setQueryData<PlatformSetting[]>(p9Keys.settings, (items) => items?.map((s) => (s.key === updated.key ? updated : s)));
      setReason("");
      setTried(false);
      setSaved(true);
    },
    onError: (e) => {
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
        {setting.editable && <RequiredNote />}
        <fieldset disabled={!setting.editable}>{children(tried)}</fieldset>
        {tried && error && (
          <p className="field__error" role="alert">
            {error}
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
        {setting.editable ? (
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

/** `app.release`: the version offered to the phones and the oldest one still allowed (addition 3). */
export function AppReleaseCard({ setting }: { setting: PlatformSetting }) {
  const { t } = useTranslation();
  const id = useId();
  const [v, setV] = useState<AppReleaseValue>(() => releaseFrom(setting.value));
  const problem = validateRelease(v);
  const error = problem
    ? t(`settings.release.errors.${problem}`, { min: BUILD_RANGE.min, max: BUILD_RANGE.max, notes: NOTES_MAX })
    : null;
  const invalid = (tried: boolean, ...fields: string[]) =>
    tried && problem !== null && fields.includes(problem) ? true : undefined;

  return (
    <SettingForm
      setting={setting}
      title={t("settings.release.title")}
      help={t("settings.release.help")}
      error={error}
      toValue={() => ({ ...v, latest_version: v.latest_version.trim() })}
    >
      {(tried) => (
        <>
          <div className="settings-grid">
            <div className="field">
              <label htmlFor={`${id}-version`}>{t("settings.release.version")}</label>
              <input
                id={`${id}-version`}
                dir="ltr"
                aria-required="true"
                placeholder="0.3.0"
                value={v.latest_version}
                aria-invalid={invalid(tried, "version")}
                onChange={(e) => setV({ ...v, latest_version: e.target.value })}
              />
            </div>
            <div className="field field--number">
              <label htmlFor={`${id}-latest`}>{t("settings.release.latestBuild")}</label>
              <Stepper
                id={`${id}-latest`}
                dir="ltr"
                required
                min={BUILD_RANGE.min}
                max={BUILD_RANGE.max}
                value={Number.isNaN(v.latest_build) ? null : v.latest_build}
                label={t("settings.release.latestBuild")}
                invalid={invalid(tried, "build", "order")}
                onChange={(n) => setV({ ...v, latest_build: n })}
                onClear={() => setV({ ...v, latest_build: Number.NaN })}
              />
            </div>
            <div className="field field--number">
              <label htmlFor={`${id}-min`}>{t("settings.release.minBuild")}</label>
              <Stepper
                id={`${id}-min`}
                dir="ltr"
                required
                min={BUILD_RANGE.min}
                max={BUILD_RANGE.max}
                value={Number.isNaN(v.min_build) ? null : v.min_build}
                label={t("settings.release.minBuild")}
                invalid={invalid(tried, "build", "order")}
                onChange={(n) => setV({ ...v, min_build: n })}
                onClear={() => setV({ ...v, min_build: Number.NaN })}
              />
            </div>
            <div className="field">
              <label htmlFor={`${id}-channel`}>{t("settings.release.channel")}</label>
              <select
                id={`${id}-channel`}
                aria-required="true"
                value={v.channel}
                onChange={(e) => setV({ ...v, channel: e.target.value === "play" ? "play" : "server" })}
              >
                <option value="server">{t("settings.release.channels.server")}</option>
                <option value="play">{t("settings.release.channels.play")}</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor={`${id}-url`}>{t("settings.release.downloadUrl")}</label>
            <input
              id={`${id}-url`}
              type="url"
              dir="ltr"
              placeholder="https://"
              aria-required={v.channel === "server" && v.latest_build > 1 ? "true" : undefined}
              value={v.download_url ?? ""}
              aria-invalid={invalid(tried, "url", "urlMissing")}
              onChange={(e) => setV({ ...v, download_url: e.target.value.trim() === "" ? null : e.target.value.trim() })}
            />
          </div>
          {LANGS.map((lang) => (
            <div className="field" key={lang}>
              <label htmlFor={`${id}-notes-${lang}`}>{t("settings.release.notes", { lang: t(`languages.${lang}`) })}</label>
              <textarea
                id={`${id}-notes-${lang}`}
                rows={3}
                dir={lang === "ar" ? "rtl" : "ltr"}
                lang={lang}
                maxLength={NOTES_MAX}
                value={v.notes[lang]}
                onChange={(e) => setV({ ...v, notes: { ...v.notes, [lang]: e.target.value } })}
              />
            </div>
          ))}
          <p className="muted">{t("settings.release.mandatoryNote")}</p>
        </>
      )}
    </SettingForm>
  );
}

/**
 * `moderation.extra_terms`: words added to the built-in list of the API. Used on profile names and other
 * non-emergency free text, never on reports or SOS.
 */
export function ModerationTermsCard({ setting }: { setting: PlatformSetting }) {
  const { t } = useTranslation();
  const id = useId();
  const [text, setText] = useState(() => termsFrom(setting.value).join("\n"));
  const parsed = parseTerms(text);
  const error = parsed.error
    ? t(`settings.moderation.errors.${parsed.error}`, { min: TERM_LENGTH.min, max: TERM_LENGTH.max, count: TERMS_MAX })
    : null;

  return (
    <SettingForm
      setting={setting}
      title={t("settings.moderation.title")}
      help={t("settings.moderation.help")}
      error={error}
      toValue={() => parsed.terms}
    >
      {(tried) => (
        <div className="field">
          <label htmlFor={`${id}-terms`}>{t("settings.moderation.label")}</label>
          <textarea
            id={`${id}-terms`}
            rows={6}
            dir="auto"
            value={text}
            aria-describedby={`${id}-hint`}
            aria-invalid={tried && parsed.error ? true : undefined}
            onChange={(e) => setText(e.target.value)}
          />
          <p id={`${id}-hint`} className="muted">
            {t("settings.moderation.hint", { count: parsed.terms.length, max: TERMS_MAX })}
          </p>
        </div>
      )}
    </SettingForm>
  );
}
