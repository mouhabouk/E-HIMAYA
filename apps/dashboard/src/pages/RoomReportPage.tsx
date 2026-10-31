// covers: phase N (docs/phase-n/design-n.md §5): the room agent enters a report that came by telephone, radio or in
// person. It becomes a report like the others (tracking code, AI baseline, grouping, follow-up), held by the room.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey } from "../lib/api";
import { useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { INTAKE_CHANNELS, type IntakeChannel } from "../lib/staffApi";
import { CATEGORIES, type Category } from "../lib/types";
import { DictatedTextarea } from "../components/Dictation";

/** A latitude and a longitude typed by hand, or null while either is not a number inside Tunisia's box. */
export function parsePoint(lat: string, lon: string): { lat: number; lon: number } | null {
  const y = Number(lat.replace(",", "."));
  const x = Number(lon.replace(",", "."));
  if (!lat.trim() || !lon.trim() || !Number.isFinite(y) || !Number.isFinite(x)) return null;
  return y >= 30 && y <= 37.6 && x >= 7.4 && x <= 11.7 ? { lat: y, lon: x } : null;
}

export function RoomReportPage() {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = useId();
  const [category, setCategory] = useState<Category>("sos");
  const [channel, setChannel] = useState<IntakeChannel>("phone");
  const [text, setText] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [receivedAt, setReceivedAt] = useState("");
  const [tried, setTried] = useState(false);
  const [bounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const point = parsePoint(lat, lon);
  const save = useMutation({
    mutationFn: () =>
      api.enterReport({
        category,
        channel,
        location: point ?? { lat: 0, lon: 0 },
        text: text.trim() || undefined,
        received_at: receivedAt ? new Date(receivedAt).toISOString() : undefined,
      }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["reports"] });
      void navigate(`/reports/${encodeURIComponent(r.id)}`);
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (point) save.mutate();
  };
  const pick = (x: number, y: number) => {
    setLat(y.toFixed(5));
    setLon(x.toFixed(5));
  };

  return (
    <div className="page">
      <p>
        <Link to="/reports">{t("intake.back")}</Link>
      </p>
      <PageTitle icon="description" tone="red">
        {t("intake.title")}
      </PageTitle>
      <p className="muted">{t("intake.intro")}</p>
      <form className="card ops-form intake-form" onSubmit={submit} noValidate aria-describedby={`${id}-hint`}>
        <fieldset className="chips">
          <legend>{t("intake.channel")}</legend>
          {INTAKE_CHANNELS.map((c) => (
            <label key={c} className="chip-toggle">
              <input type="radio" name={`${id}-channel`} checked={channel === c} onChange={() => setChannel(c)} />
              <span>{t(`intake.channels.${c}`)}</span>
            </label>
          ))}
        </fieldset>
        <div className="form-grid">
          <div className="field">
            <label htmlFor={`${id}-c`}>{t("intake.category")}</label>
            <select id={`${id}-c`} value={category} onChange={(e) => setCategory(e.target.value as Category)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(`category.${c}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-r`}>{t("intake.receivedAt")}</label>
            <input id={`${id}-r`} type="datetime-local" value={receivedAt} onChange={(e) => setReceivedAt(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor={`${id}-x`}>{t("intake.text")}</label>
          <DictatedTextarea field="intake.text" id={`${id}-x`} rows={3} maxLength={4000} value={text} onText={setText} />
        </div>
        <p id={`${id}-hint`} className="muted">
          {t("intake.where")}
        </p>
        <div className="form-grid">
          <div className="field">
            <label htmlFor={`${id}-lat`}>{t("intake.lat")}</label>
            <input
              id={`${id}-lat`}
              inputMode="decimal"
              dir="ltr"
              value={lat}
              aria-invalid={(tried && !point) || undefined}
              onChange={(e) => setLat(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`${id}-lon`}>{t("intake.lon")}</label>
            <input
              id={`${id}-lon`}
              inputMode="decimal"
              dir="ltr"
              value={lon}
              aria-invalid={(tried && !point) || undefined}
              onChange={(e) => setLon(e.target.value)}
            />
          </div>
        </div>
        {tried && !point && (
          <p role="alert" className="field__error">
            {t("intake.pointRequired")}
          </p>
        )}
        <Suspense fallback={<Loading />}>
          <LazyMapView
            className="map map--mini"
            markers={
              point
                ? [{ id: "new", lon: point.lon, lat: point.lat, status: "received", category, title: t("intake.point"), subtitle: t(`category.${category}`) }]
                : []
            }
            bounds={bounds}
            ariaLabel={t("intake.mapAria")}
            styleUrl={mapStyleUrl}
            dir={directionOf(lang)}
            onMapClick={pick}
          />
        </Suspense>
        {save.isError && (
          <p role="alert" className="field__error">
            {t(errorMessageKey(save.error))}
          </p>
        )}
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {t("intake.submit")}
          </button>
          <Link className="btn" to="/reports">
            {t("common.cancel")}
          </Link>
        </div>
      </form>
    </div>
  );
}
