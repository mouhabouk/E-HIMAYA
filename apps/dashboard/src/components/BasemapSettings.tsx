// covers: docs/phase-r/design-basemap.md §3: the paid imagery provider the administration chooses. The national system
// administrator enters its tile address and licence key, tests the connection, then switches it on. The key goes to the
// API and never comes back (only its last four characters); every change is audited.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  basemapKeys,
  PROVIDER_EXAMPLES,
  PROVIDERS,
  type BasemapSettings,
  type BasemapSettingsBody,
  type Provider,
} from "../lib/basemap";
import { useFormat } from "../lib/hooks";
import { ErrorBox, Loading } from "./Feedback";

function SettingsForm({ saved }: { saved: BasemapSettings }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [provider, setProvider] = useState<Provider>(saved.provider ?? "esri");
  const [url, setUrl] = useState(saved.url_template ?? "");
  const [key, setKey] = useState("");
  const [dropKey, setDropKey] = useState(false);
  const [header, setHeader] = useState(saved.key_header ?? "");
  const [attribution, setAttribution] = useState(saved.attribution ?? "");
  const [maxZoom, setMaxZoom] = useState(saved.max_zoom);
  const [enabled, setEnabled] = useState(saved.enabled);
  const body = (): BasemapSettingsBody => ({
    provider,
    url_template: url.trim(),
    api_key: dropKey ? "" : key.trim() || null,
    key_header: header.trim() || null,
    attribution: attribution.trim(),
    max_zoom: maxZoom,
    enabled,
  });
  const test = useMutation({ mutationFn: () => api.testBasemap(body()) });
  const save = useMutation({
    mutationFn: () => api.saveBasemapSettings(body()),
    onSuccess: (next) => {
      qc.setQueryData(basemapKeys.settings, next);
      void qc.invalidateQueries({ queryKey: basemapKeys.view });
      setKey("");
      setDropKey(false);
    },
  });
  const example = PROVIDER_EXAMPLES[provider];
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const ready = url.trim().length > 0 && attribution.trim().length > 1;

  return (
    <form className="card inventory-form basemap-settings" aria-labelledby={`${id}-title`} onSubmit={submit} noValidate>
      <h2 id={`${id}-title`}>{t("basemap.settings.title")}</h2>
      <p className="alert alert--info">{t("basemap.settings.open")}</p>
      <p className="muted">{t("basemap.settings.intro")}</p>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${id}-provider`}>{t("basemap.settings.provider")}</label>
          <select id={`${id}-provider`} value={provider} onChange={(e) => setProvider(e.target.value as Provider)}>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {t(`basemap.provider.${p}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-zoom`}>{t("basemap.settings.maxZoom")}</label>
          <input
            id={`${id}-zoom`}
            type="number"
            min={1}
            max={22}
            value={maxZoom}
            onChange={(e) => setMaxZoom(Math.max(1, Math.min(22, Number(e.target.value) || 1)))}
          />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-url`}>{t("basemap.settings.url")}</label>
        <input id={`${id}-url`} dir="ltr" value={url} onChange={(e) => setUrl(e.target.value)} aria-describedby={`${id}-url-help`} />
        <span id={`${id}-url-help`} className="muted">
          {t("basemap.settings.urlHelp")}
        </span>
        {example && (
          <div className="actions">
            <button
              type="button"
              className="btn btn--small"
              onClick={() => {
                setUrl(example.url);
                if (!attribution.trim()) setAttribution(example.attribution);
              }}
            >
              {t("basemap.settings.useExample")}
            </button>
          </div>
        )}
      </div>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${id}-key`}>{t("basemap.settings.key")}</label>
          <input
            id={`${id}-key`}
            type="password"
            dir="ltr"
            autoComplete="off"
            value={key}
            disabled={dropKey}
            onChange={(e) => setKey(e.target.value)}
            aria-describedby={`${id}-key-help`}
          />
          <span id={`${id}-key-help`} className="muted">
            {saved.key_hint ? t("basemap.settings.keyKept", { hint: `\u2068${saved.key_hint}\u2069` }) : t("basemap.settings.keyNone")}
          </span>
        </div>
        <div className="field">
          <label htmlFor={`${id}-header`}>{t("basemap.settings.header")}</label>
          <input id={`${id}-header`} dir="ltr" value={header} onChange={(e) => setHeader(e.target.value)} placeholder="X-Api-Key" />
        </div>
      </div>
      {saved.key_hint && (
        <label className="checkbox">
          <input type="checkbox" checked={dropKey} onChange={(e) => setDropKey(e.target.checked)} />
          <span>{t("basemap.settings.dropKey")}</span>
        </label>
      )}
      <div className="field">
        <label htmlFor={`${id}-attribution`}>{t("basemap.settings.attribution")}</label>
        <input id={`${id}-attribution`} dir="auto" value={attribution} onChange={(e) => setAttribution(e.target.value)} />
      </div>
      <label className="checkbox">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        <span>{t("basemap.settings.enabled")}</span>
      </label>
      <p className="muted">{t("basemap.settings.fallback")}</p>
      {saved.configured && (
        <p className="muted">
          {saved.last_test_at
            ? t(saved.last_test_ok ? "basemap.settings.lastTestOk" : "basemap.settings.lastTestFailed", {
                time: fmt.dateTime(saved.last_test_at),
              })
            : t("basemap.settings.notTested")}
          {saved.updated_at && ` · ${t("basemap.settings.updated", { name: saved.updated_by_name ?? "—", time: fmt.dateTime(saved.updated_at) })}`}
        </p>
      )}
      <div role="status" aria-live="polite">
        {test.data && (
          <p className={`alert ${test.data.ok ? "alert--info" : "alert--error"}`}>
            {test.data.ok
              ? t("basemap.settings.testOk", { ms: fmt.number(test.data.ms) })
              : t("basemap.settings.testFailed", { status: test.data.status ?? test.data.error ?? "—" })}
          </p>
        )}
        {save.isSuccess && <p className="alert alert--info">{t("basemap.settings.saved")}</p>}
      </div>
      {test.isError && (
        <p className="field__error" role="alert">
          {t(errorMessageKey(test.error))}
        </p>
      )}
      {save.isError && (
        <p className="field__error" role="alert">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="actions">
        <button type="button" className="btn" disabled={!ready || test.isPending} onClick={() => test.mutate()}>
          {t("basemap.settings.test")}
        </button>
        <button type="submit" className="btn btn--primary" disabled={!ready || save.isPending}>
          {t("basemap.settings.save")}
        </button>
      </div>
    </form>
  );
}

/** The "map background" tab of the layers page (national system administrator). */
export function BasemapSettingsCard() {
  const { api } = useServices();
  const query = useQuery({ queryKey: basemapKeys.settings, queryFn: ({ signal }) => api.basemapSettings(signal) });
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;
  return <SettingsForm saved={query.data} />;
}
