// covers: OS2 follow-up (docs/phase-os2/design-os2.md §6): the call-taking card on the report's page, the caller's
// answers beside the team's from the scene, kept live, and what the teams found set beside the card.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { isApiError } from "../lib/api";
import { callCardKeys, type CardBand, type SceneCheck } from "../lib/callCards";
import { useFormat } from "../lib/hooks";
import { Icon } from "./Icon";

const CHECK_TONE: Record<SceneCheck, string> = {
  nature_differs: "tone-amber",
  lives_not_on_card: "tone-red",
  injured_not_on_card: "tone-red",
  band_below_toll: "tone-red",
  confirmed: "tone-green",
};

function Band({ band }: { band: CardBand }) {
  const { t } = useTranslation();
  return <span className={`call-card__band-pill call-card__band-pill--${band}`}>{t(`callCards.band.${band}`)}</span>;
}

export function ReportCallCard({ reportId }: { reportId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useQuery({
    queryKey: callCardKeys.report(reportId),
    queryFn: ({ signal }) => api.reportCallCard(reportId, signal),
    // Kept live by the teams' events (lib/liveCache); a report entered without a card answers 404.
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });
  if (!query.data) return null;
  const c = query.data;
  const field = c.field_answers ?? {};
  const hasField = c.field_outcome !== null;
  const scene = c.scene;
  const found = scene && (scene.nature || scene.injured || scene.deceased || scene.trapped);
  return (
    <section className="card report-card" aria-labelledby="sec-call-card">
      <h2 id="sec-call-card">
        {t("callCards.report.title", { title: c.title })}{" "}
        <span className="muted">{t("callCards.version", { version: c.card_version })}</span>
        {c.sim && <span className="sim-badge">[SIM]</span>}
      </h2>
      <div className="report-card__bands">
        <span>
          {t("callCards.report.call")} <Band band={c.outcome.band} />
        </span>
        <span>
          {t("callCards.report.field")}{" "}
          {c.field_outcome ? <Band band={c.field_outcome.band} /> : <span className="muted">{t("callCards.report.waiting")}</span>}
        </span>
      </div>
      {hasField && c.field_at && (
        <p className="muted">{t("callCards.report.fieldBy", { name: c.field_by_name ?? "—", at: fmt.dateTime(c.field_at) })}</p>
      )}
      <div className="table-wrap">
        <table className="table report-card__table">
          <thead>
            <tr>
              <th scope="col">{t("callCards.report.question")}</th>
              <th scope="col">{t("callCards.report.call")}</th>
              <th scope="col">{t("callCards.report.field")}</th>
            </tr>
          </thead>
          <tbody>
            {c.questions.map((q) => {
              const call = c.answers[q.id];
              const scn = field[q.id];
              const changed = call !== undefined && scn !== undefined && call !== scn;
              return (
                <tr key={q.id} className={changed ? "report-card__changed" : undefined}>
                  <th scope="row">
                    {q.text}
                    {q.key && <span className="pill tone-red report-card__key">{t("callCards.key")}</span>}
                  </th>
                  <td>{call ? t(`callCards.answer.${call}`) : <span className="muted">—</span>}</td>
                  <td>
                    {scn ? t(`callCards.answer.${scn}`) : <span className="muted">—</span>}
                    {changed && <span className="visually-hidden"> {t("callCards.report.changed")}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {(c.field_outcome ?? c.outcome).flags.length > 0 && (
        <div className="call-card__flags">
          {(c.field_outcome ?? c.outcome).flags.map((f) => (
            <span key={f} className="pill tone-red">
              <Icon name="warning" /> {f}
            </span>
          ))}
        </div>
      )}
      <h3 className="call-card__sect">{t("callCards.report.scene")}</h3>
      {scene && found ? (
        <>
          <dl className="fields">
            <dt>{t("callCards.report.nature")}</dt>
            <dd>{scene.nature ? t(`crew.nature.${scene.nature}`) : t("common.notAvailable")}</dd>
            <dt>{t("callCards.report.toll")}</dt>
            <dd>
              {t("callCards.report.tollLine", {
                injured: scene.injured,
                serious: scene.serious,
                deceased: scene.deceased,
                trapped: scene.trapped,
              })}
            </dd>
          </dl>
          <ul className="report-card__checks" aria-live="polite">
            {scene.checks.map((k) => (
              <li key={k} className={`pill ${CHECK_TONE[k]}`}>
                <Icon name={k === "confirmed" ? "check" : "warning"} /> {t(`callCards.report.checks.${k}`)}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">{t("callCards.report.nothingYet")}</p>
      )}
    </section>
  );
}
