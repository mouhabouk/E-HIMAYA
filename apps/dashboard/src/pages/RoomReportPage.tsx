// covers: phase N (docs/phase-n/design-n.md §5): the room agent enters a report that came by telephone, radio or in
// person. It becomes a report like the others (tracking code, AI baseline, grouping, follow-up), held by the room.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router";
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
import type { Category } from "../lib/types";
import { DictatedTextarea } from "../components/Dictation";
import { CallCardPanel, useCallTimer } from "../components/CallCardPanel";
import { Icon, IconTile } from "../components/Icon";
import { CATEGORY_TILE, TILE_ORDER } from "../lib/categoryIcons";
import { callCardKeys, shownAnswers, type Answers } from "../lib/callCards";
import { canReadCallCards } from "../lib/roles";
import { ApiError } from "../lib/api";

/** A latitude and a longitude typed by hand, or null while either is not a number inside Tunisia's box. */
export function parsePoint(lat: string, lon: string): { lat: number; lon: number } | null {
  const y = Number(lat.replace(",", "."));
  const x = Number(lon.replace(",", "."));
  if (!lat.trim() || !lon.trim() || !Number.isFinite(y) || !Number.isFinite(x)) return null;
  return y >= 30 && y <= 37.6 && x >= 7.4 && x <= 11.7 ? { lat: y, lon: x } : null;
}

function answeredMs(at: string | null): number | undefined {
  const ms = at ? Date.parse(at) : NaN;
  return Number.isFinite(ms) ? ms : undefined;
}

/** An ISO time as the value of a datetime-local input, in the browser's time zone. */
function localInput(at: string | null): string {
  const ms = answeredMs(at);
  if (ms === undefined) return "";
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
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
  // Opened from the softphone (« enter a report from this call »): the call is linked on save, received at the answer.
  const [params] = useSearchParams();
  const callId = params.get("call") || null;
  const [channel, setChannel] = useState<IntakeChannel>("phone");
  const [text, setText] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [receivedAt, setReceivedAt] = useState(() => localInput(params.get("at")));
  const [tried, setTried] = useState(false);
  const [bounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const point = parsePoint(lat, lon);
  const timer = useCallTimer(answeredMs(params.get("at")));
  // The guided call-taking card of the category (OS2); the form works as before without it.
  const cards = useQuery({
    queryKey: callCardKeys.list("current"),
    queryFn: ({ signal }) => api.callCards("current", signal),
    enabled: canReadCallCards(user?.identity.roles ?? []),
    staleTime: 60_000,
  });
  const card = cards.data?.cards.find((c) => c.category === category && c.status === "approved") ?? null;
  const [answers, setAnswers] = useState<Answers>({});
  const [read, setRead] = useState<string[]>([]);
  const [skipCard, setSkipCard] = useState(false);
  const activeCard = skipCard ? null : card;
  const pickCategory = (c: Category) => {
    setCategory(c);
    setAnswers({});
    setRead([]);
  };
  const save = useMutation({
    mutationFn: () =>
      api.enterReport({
        category,
        channel,
        location: point ?? { lat: 0, lon: 0 },
        text: text.trim() || undefined,
        received_at: receivedAt ? new Date(receivedAt).toISOString() : undefined,
        call_id: callId ?? undefined,
        call_card:
          activeCard
            ? {
                card_id: activeCard.id,
                version: activeCard.version,
                answers: shownAnswers(activeCard.content, answers),
                read,
              }
            : undefined,
      }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["reports"] });
      void navigate(`/reports/${encodeURIComponent(r.id)}`);
    },
    onError: (e) => {
      // The Office approved a newer version during the call: load it; the answers are kept where the questions are.
      if (e instanceof ApiError && e.code === "call_card_changed") void qc.invalidateQueries({ queryKey: callCardKeys.all });
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
      {callId && (
        <p className="pill tone-green" role="status">
          <Icon name="call" /> {t("intake.fromCall")}
        </p>
      )}
      <p className="call-card__timer">
        <span className="pill tone-red">
          <Icon name="schedule" /> {t("callCards.timer")} <span className="call-card__clock">{timer}</span>
        </span>
      </p>
      <form className="intake-layout" onSubmit={submit} noValidate aria-describedby={`${id}-hint`}>
        <fieldset className="card intake-cats">
          <legend>{t("intake.categoryStep")}</legend>
          <div className="intake-cats__grid">
            {TILE_ORDER.map((c) => (
              <label key={c} className="intake-cats__tile">
                <input
                  type="radio"
                  className="visually-hidden"
                  name={`${id}-category`}
                  checked={category === c}
                  onChange={() => pickCategory(c)}
                />
                {category === c && (
                  <span className="intake-cats__check" aria-hidden="true">
                    <Icon name="check" />
                  </span>
                )}
                <IconTile name={CATEGORY_TILE[c][0]} tone={CATEGORY_TILE[c][1]} />
                <span>{t(`intake.tiles.${c}`)}</span>
              </label>
            ))}
          </div>
          <p className="muted intake-cats__hint">{t("intake.firstQuestion")}</p>
        </fieldset>
        <div className="card ops-form intake-form">
        <fieldset className="chips">
          <legend>{t("intake.channel")}</legend>
          {INTAKE_CHANNELS.map((c) => (
            <label key={c} className="chip-toggle">
              <input type="radio" name={`${id}-channel`} checked={channel === c} onChange={() => setChannel(c)} />
              <span>{t(`intake.channels.${c}`)}</span>
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor={`${id}-r`}>{t("intake.receivedAt")}</label>
          <input id={`${id}-r`} type="datetime-local" value={receivedAt} onChange={(e) => setReceivedAt(e.target.value)} />
        </div>
        {card && (
          <label className="call-card__skip">
            <input type="checkbox" checked={skipCard} onChange={(e) => setSkipCard(e.target.checked)} />
            {t("callCards.skip")}
          </label>
        )}
        {activeCard && (
          <CallCardPanel card={activeCard} answers={answers} onAnswers={setAnswers} read={read} onRead={setRead} />
        )}
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
        </div>
      </form>
    </div>
  );
}
