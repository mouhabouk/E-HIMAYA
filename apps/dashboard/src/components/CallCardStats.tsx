// covers: OS2-3 (Yamen 2026-11-13, docs/phase-os2b/design-os2b.md §2): statistics of the guided call-taking cards.
// Card use and call time per room, and per card what the callers answered, how often the team changed an answer from
// the scene, the instructions read and what the team found compared with the card. A regional room sees its own row
// with the national figures beside it. No agent is named.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import {
  INTAKE_CHANNELS,
  STATS_CHECKS,
  STATS_DAYS,
  callCardKeys,
  minutes,
  percent,
  statsCsv,
  type CardFigures,
  type StatsChannel,
  type StatsFigures,
} from "../lib/callCards";
import { CATEGORY_TILE } from "../lib/categoryIcons";
import { useFormat } from "../lib/hooks";
import { saveDownload } from "../lib/layersApi";
import { ErrorBox, Loading } from "./Feedback";
import { IconTile } from "./Icon";
import { useRoomName } from "./Phase9Bits";

/** The colour of each comparison with the scene, in the order of the legend. */
const CHECK_TONE: Record<(typeof STATS_CHECKS)[number], string> = {
  confirmed: "green",
  nature_differs: "slate",
  lives_not_on_card: "red",
  injured_not_on_card: "purple",
  band_below_toll: "orange",
};

/** A share as a bar and its percentage; "—" when there is nothing to count. */
function Share({ part, whole, warnBelow }: { part: number; whole: number; warnBelow?: number }) {
  const p = percent(part, whole);
  if (p === null) return <span className="muted">—</span>;
  const tone = warnBelow !== undefined && p < warnBelow ? "amber" : "teal";
  return (
    <span className="cc-share">
      <span className="cc-bar" aria-hidden="true">
        <i className={`cc-bar__seg cc-tone-${tone}`} style={{ inlineSize: `${p}%` }} />
      </span>
      <span className="cc-share__value">{p}%</span>
    </span>
  );
}

function MatchPill({ figures }: { figures: Pick<StatsFigures, "field_checked" | "field_confirmed"> }) {
  const p = percent(figures.field_confirmed, figures.field_checked);
  if (p === null) return <span className="muted">—</span>;
  return <span className={`pill tone-${p >= 80 ? "green" : p >= 60 ? "amber" : "red"}`}>{p}%</span>;
}

/** The comparisons with the scene of one card, as one stacked bar (each segment is named in the legend). */
function ChecksBar({ card }: { card: CardFigures }) {
  const { t } = useTranslation();
  const total = STATS_CHECKS.reduce((n, k) => n + card.checks[k], 0);
  if (total === 0) return <span className="muted">{t("callCards.stats.noField")}</span>;
  const label = STATS_CHECKS.filter((k) => card.checks[k] > 0)
    .map((k) => `${t(`callCards.stats.check.${k}`)} ${percent(card.checks[k], total) ?? 0}%`)
    .join("، ");
  return (
    <span className="cc-bar cc-bar--stack" role="img" aria-label={label} title={label}>
      {STATS_CHECKS.map((k) =>
        card.checks[k] > 0 ? (
          <i key={k} className={`cc-bar__seg cc-tone-${CHECK_TONE[k]}`} style={{ inlineSize: `${(100 * card.checks[k]) / total}%` }} />
        ) : null,
      )}
    </span>
  );
}

/** Per question of one card: how callers answered and how often the team changed the answer. */
export function CardQuestionStats({ card }: { card: CardFigures }) {
  const { t } = useTranslation();
  const worst = Math.max(0, ...card.questions.map((q) => percent(q.unknown, q.yes + q.no + q.unknown) ?? 0));
  return (
    <div className="cc-questions">
      {card.questions.map((q) => {
        const n = q.yes + q.no + q.unknown;
        const unknown = percent(q.unknown, n);
        return (
          <div key={q.id} className={`cc-q${q.key ? " cc-q--key" : ""}`}>
            <div className="cc-q__text">
              {q.text}
              {q.key && <span className="pill tone-red">{t("callCards.key")}</span>}
            </div>
            {n === 0 ? (
              <p className="muted cc-q__meta">{t("callCards.stats.notAsked")}</p>
            ) : (
              <>
                <span
                  className="cc-bar cc-bar--stack cc-bar--tall"
                  role="img"
                  aria-label={t("callCards.stats.answersLabel", {
                    yes: percent(q.yes, n),
                    no: percent(q.no, n),
                    unknown,
                  })}
                >
                  <i className="cc-bar__seg cc-tone-navy" style={{ inlineSize: `${(100 * q.yes) / n}%` }} />
                  <i className="cc-bar__seg cc-tone-navy-soft" style={{ inlineSize: `${(100 * q.no) / n}%` }} />
                  <i className="cc-bar__seg cc-tone-amber" style={{ inlineSize: `${(100 * q.unknown) / n}%` }} />
                </span>
                <p className="cc-q__meta">
                  <span>{t("callCards.stats.yes", { p: percent(q.yes, n) })}</span>
                  <span>{t("callCards.stats.no", { p: percent(q.no, n) })}</span>
                  <span className={unknown !== null && unknown === worst && unknown >= 20 ? "cc-q__warn" : undefined}>
                    {t("callCards.stats.unknown", { p: unknown })}
                    {unknown !== null && unknown === worst && unknown >= 20 && ` · ${t("callCards.stats.unknownHigh")}`}
                  </span>
                  {q.field_answered > 0 && (
                    <span>{t("callCards.stats.fieldChanged", { p: percent(q.field_changed, q.field_answered) })}</span>
                  )}
                </p>
              </>
            )}
          </div>
        );
      })}
      {Object.keys(card.read).length > 0 && (
        <p className="muted cc-q__meta">
          {t("callCards.stats.read")}{" "}
          {Object.entries(card.read)
            .map(([k, n]) => `${card.instruction_titles[k] ?? k} ${n}`)
            .join("، ")}
        </p>
      )}
    </div>
  );
}

export function CallCardStats() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const roomName = useRoomName();
  const national = (user?.identity.gouvernoratCode ?? null) === null;
  const [days, setDays] = useState<number>(30);
  const [channels, setChannels] = useState<StatsChannel[]>([...INTAKE_CHANNELS]);
  const [room, setRoom] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQuery({
    queryKey: callCardKeys.stats(days, channels.join(","), room),
    queryFn: ({ signal }) => api.cardStats(days, channels, room, signal),
    enabled: channels.length > 0,
  });
  const toggle = (c: StatsChannel) =>
    setChannels((xs) => (xs.includes(c) ? xs.filter((x) => x !== c) : INTAKE_CHANNELS.filter((x) => x === c || xs.includes(x))));
  const data = q.data;
  const shownCard = data?.cards.find((c) => c.category === open) ?? null;
  return (
    <div className="cc-stats">
      <section className="card cc-filters" aria-label={t("callCards.stats.filters")}>
        <div className="segmented__row" role="group" aria-label={t("callCards.stats.period")}>
          <strong>{t("callCards.stats.period")}</strong>
          {STATS_DAYS.map((d) => (
            <button key={d} type="button" className={`btn btn--small${days === d ? " btn--primary" : ""}`} aria-pressed={days === d} onClick={() => setDays(d)}>
              {t("callCards.stats.days", { n: d })}
            </button>
          ))}
        </div>
        {national && data && (
          <label className="cc-filters__room">
            <strong>{t("callCards.stats.room")}</strong>
            <select value={room ?? ""} onChange={(e) => setRoom(e.target.value || null)}>
              <option value="">{t("callCards.stats.allRooms")}</option>
              {(room ? [{ room }] : data.rooms).map((r) => (
                <option key={r.room} value={r.room}>
                  {roomName(r.room)}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="segmented__row" role="group" aria-label={t("callCards.stats.channel")}>
          <strong>{t("callCards.stats.channel")}</strong>
          {INTAKE_CHANNELS.map((c) => (
            <button key={c} type="button" className={`btn btn--small${channels.includes(c) ? " btn--primary" : ""}`} aria-pressed={channels.includes(c)} onClick={() => toggle(c)}>
              {t(`intake.channels.${c}`)}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="btn btn--small cc-filters__csv"
          disabled={!data}
          onClick={() =>
            data &&
            saveDownload({
              blob: new Blob(["﻿", statsCsv(data, roomName)], { type: "text/csv;charset=utf-8" }),
              filename: `call-cards-stats-${days}d.csv`,
            })
          }
        >
          {t("callCards.stats.csv")}
        </button>
      </section>

      {channels.length === 0 ? (
        <p className="muted">{t("callCards.stats.pickChannel")}</p>
      ) : q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorBox error={q.error} />
      ) : data ? (
        <>
          <ul className="kpis cc-kpis" role="list" aria-label={t("callCards.stats.summary")}>
            <li className="card kpi">
              <span className="kpi__label">{t("callCards.stats.entered")}</span>
              <p className="kpi__value">{fmt.number(data.total.entered)}</p>
            </li>
            <li className="card kpi">
              <span className="kpi__label">{t("callCards.stats.withCard", { n: fmt.number(data.total.with_card) })}</span>
              <p className="kpi__value">{percent(data.total.with_card, data.total.entered) ?? "—"}%</p>
            </li>
            <li className="card kpi">
              <span className="kpi__label">{t("callCards.stats.medianWith")}</span>
              <p className="kpi__value">{minutes(data.total.median_with_s)}</p>
              <span className="muted">{t("callCards.stats.versusWithout", { time: minutes(data.total.median_without_s) })}</span>
            </li>
            <li className="card kpi">
              <span className="kpi__label">{t("callCards.stats.matched", { n: fmt.number(data.total.field_checked) })}</span>
              <p className="kpi__value">{percent(data.total.field_confirmed, data.total.field_checked) ?? "—"}%</p>
            </li>
          </ul>

          <section className="card">
            <h2>{t("callCards.stats.byRoom")}</h2>
            <p className="muted">{t("callCards.stats.timeHint")}</p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("callCards.stats.col.room")}</th>
                    <th>{t("callCards.stats.col.entered")}</th>
                    <th>{t("callCards.stats.col.withCard")}</th>
                    <th>{t("callCards.stats.col.medianWith")}</th>
                    <th>{t("callCards.stats.col.medianWithout")}</th>
                    <th>{t("callCards.stats.col.p90")}</th>
                    <th>{t("callCards.stats.col.matched")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rooms.length === 0 && (
                    <tr>
                      <td colSpan={7} className="muted">
                        {t("callCards.stats.empty")}
                      </td>
                    </tr>
                  )}
                  {data.rooms.map((r) => (
                    <tr key={r.room}>
                      <th scope="row">{roomName(r.room)}</th>
                      <td>{fmt.number(r.entered)}</td>
                      <td>
                        <Share part={r.with_card} whole={r.entered} warnBelow={50} />
                      </td>
                      <td>{minutes(r.median_with_s)}</td>
                      <td>{minutes(r.median_without_s)}</td>
                      <td>{minutes(r.p90_s)}</td>
                      <td>
                        <MatchPill figures={r} />
                      </td>
                    </tr>
                  ))}
                  {!national && (
                    <tr className="cc-national">
                      <th scope="row">{t("callCards.stats.national")}</th>
                      <td>{fmt.number(data.national.entered)}</td>
                      <td>
                        <Share part={data.national.with_card} whole={data.national.entered} />
                      </td>
                      <td>{minutes(data.national.median_with_s)}</td>
                      <td>{minutes(data.national.median_without_s)}</td>
                      <td>{minutes(data.national.p90_s)}</td>
                      <td>
                        <MatchPill figures={data.national} />
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="alert alert--info">{t(national ? "callCards.stats.scopeNational" : "callCards.stats.scopeRegional")}</p>
          </section>

          <section className="card">
            <h2>{t("callCards.stats.byCard")}</h2>
            <p className="muted">{t("callCards.stats.byCardHint")}</p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("callCards.col.card")}</th>
                    <th>{t("callCards.col.used")}</th>
                    <th>{t("callCards.stats.col.median")}</th>
                    <th>{t("callCards.stats.col.keyUnknown")}</th>
                    <th>{t("callCards.stats.col.found")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cards.map((c) => {
                    const unknown = percent(c.key_unknown, c.key_answered);
                    return (
                      <tr key={c.category} className={open === c.category ? "row--selected" : undefined}>
                        <td>
                          <button type="button" className="call-cards__pick" aria-expanded={open === c.category} onClick={() => setOpen(open === c.category ? null : c.category)}>
                            <IconTile name={CATEGORY_TILE[c.category][0]} tone={CATEGORY_TILE[c.category][1]} size="sm" />
                            {c.title}
                          </button>
                        </td>
                        <td>{fmt.number(c.used)}</td>
                        <td>{minutes(c.median_s)}</td>
                        <td>
                          {unknown === null ? (
                            <span className="muted">—</span>
                          ) : (
                            <span className={`pill tone-${unknown >= 20 ? "red" : unknown >= 10 ? "amber" : "green"}`}>{unknown}%</span>
                          )}
                        </td>
                        <td className="cc-found">
                          <ChecksBar card={c} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <ul className="cc-legend" aria-label={t("callCards.stats.legend")}>
              {STATS_CHECKS.map((k) => (
                <li key={k}>
                  <i className={`cc-tone-${CHECK_TONE[k]}`} aria-hidden="true" />
                  {t(`callCards.stats.check.${k}`)}
                </li>
              ))}
            </ul>
          </section>

          {shownCard && (
            <section className="card" aria-label={shownCard.title}>
              <div className="call-cards__detail-head">
                <IconTile name={CATEGORY_TILE[shownCard.category][0]} tone={CATEGORY_TILE[shownCard.category][1]} />
                <h2>{shownCard.title}</h2>
              </div>
              <p className="muted">{t("callCards.stats.perQuestionHint")}</p>
              <CardQuestionStats card={shownCard} />
              <ul className="cc-legend">
                <li>
                  <i className="cc-tone-navy" aria-hidden="true" />
                  {t("callCards.answer.yes")}
                </li>
                <li>
                  <i className="cc-tone-navy-soft" aria-hidden="true" />
                  {t("callCards.answer.no")}
                </li>
                <li>
                  <i className="cc-tone-amber" aria-hidden="true" />
                  {t("callCards.answer.unknown")}
                </li>
              </ul>
            </section>
          )}
        </>
      ) : null}
    </div>
  );
}
