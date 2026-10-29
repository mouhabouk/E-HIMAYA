import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useFormat } from "../lib/hooks";
import {
  ANALYSIS_STEPS,
  PRIORITY_COMPONENTS,
  SENSITIVE_REASONS,
  STEP_STATES,
  type ExplainedScore,
  type Extraction,
  type ScoreComponent,
  type StaffReportDetail,
  type Transcript,
} from "../lib/types";
import { AnalysisChip, PriorityBadge } from "./AiBadges";
import { CategoryLabel } from "./CategoryIcon";
import { MaskedText } from "./MaskedText";

const CREDIBILITY_COMPONENTS = [
  "base",
  "registered",
  "confirmed_false_reports",
  "useful_reports",
  "media",
  "precise_location",
  "imprecise_location",
  "corroborated",
  "organization",
] as const;
const LIVES_SOURCES = ["model", "keywords", "category"] as const;
const TEXT_LANGS = ["ar", "fr", "en"] as const;
const MEDIA_KINDS = ["image", "video", "audio"] as const;
const TRANSCRIPT_ERRORS = [
  "media_undecodable",
  "audio_too_long",
  "media_too_large",
  "media_fetch_failed",
  "media_url_not_allowed",
  "invalid_model_output",
  "model_unavailable",
] as const;

function isOneOf<T extends string>(list: readonly T[], v: unknown): v is T {
  return typeof v === "string" && (list as readonly string[]).includes(v);
}

/** Translated label for a machine key, with a translated fallback for keys added later by the API. */
function labelOf(t: TFunction, prefix: string, known: readonly string[], key: string): string {
  return isOneOf(known, key) ? t(`${prefix}.${key}`) : t("ai.componentOther", { key });
}

export function languageLabel(t: TFunction, code: string | null | undefined): string {
  if (!code) return t("common.notAvailable");
  return isOneOf(TEXT_LANGS, code) ? t(`languages.${code}`) : code.toUpperCase();
}

/**
 * `sensitive_sites` (phase 4 §10): the nearest institution, its distance and why it is sensitive.
 * `detail` = {org_id, name, distance_m, reason}; without an institution nearby the value is shown alone.
 */
function SensitiveSite({ component }: { component: ScoreComponent }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { org_id: orgId, name, distance_m: distance, reason, counted } = component.detail;
  if (reason === "no_site_nearby") return <span className="muted score-source">{t("ai.sensitive.none")}</span>;
  if (component.value === null || component.value === undefined) return null;
  if (typeof orgId !== "string" || typeof name !== "string") {
    return <span className="muted score-source">{t("ai.sensitive.none")}</span>;
  }
  return (
    <span className="score-source sensitive-site">
      <Link to={`/orgs/${encodeURIComponent(orgId)}`} dir="auto">
        {name}
      </Link>
      {typeof distance === "number" && <> · {t("ai.sensitive.site", { distance: fmt.meters(distance) })}</>}
      {typeof reason === "string" && (
        <>
          {" · "}
          {isOneOf(SENSITIVE_REASONS, reason)
            ? t(`ai.sensitive.reason.${reason}`)
            : t("ai.sensitive.reason.other", { key: reason })}
        </>
      )}
      {counted === false && <> · {t("ai.sensitive.notCounted")}</>}
    </span>
  );
}

/** `vision_fire` (phase 6): which label was confirmed, on a live stream or an uploaded image. */
function VisionSource({ component }: { component: ScoreComponent }) {
  const { t } = useTranslation();
  const { label, source } = component.detail;
  if (component.value === null || component.value === undefined) return null;
  if ((label !== "fire" && label !== "smoke") || (source !== "stream" && source !== "image")) return null;
  return (
    <span className="muted score-source">
      {t("ai.visionSource", { label: t(`streams.label.${label}`), source: t(`ai.visionSourceKind.${source}`) })}
    </span>
  );
}

function PriorityBreakdown({ score }: { score: ExplainedScore }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const value = (c: ScoreComponent) => {
    if (c.value === null || c.value === undefined) return <span className="muted">{t("ai.panel.noDataYet")}</span>;
    const v = Math.min(1, Math.max(0, c.value));
    return (
      <span className="meter-cell">
        <span className="meter" aria-hidden="true">
          <span className="meter__bar" style={{ inlineSize: `${v * 100}%` }} />
        </span>
        <span>{fmt.percent(v)}</span>
      </span>
    );
  };
  return (
    <div className="ai-score">
      <h3>
        {t("ai.panel.priority")} <PriorityBadge score={score.score} />
      </h3>
      <table className="score-table">
        <caption className="visually-hidden">{t("ai.panel.priorityCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("ai.panel.component")}</th>
            <th scope="col">{t("ai.panel.value")}</th>
            <th scope="col" className="num">
              {t("ai.panel.points")}
            </th>
          </tr>
        </thead>
        <tbody>
          {score.components.map((c) => {
            const source = c.detail.source;
            return (
              <tr key={c.key} className={c.value === null || c.value === undefined ? "score-row--nodata" : undefined}>
                <th scope="row">
                  {labelOf(t, "ai.components", PRIORITY_COMPONENTS, c.key)}
                  {typeof c.weight === "number" && (
                    <span className="muted score-weight">{t("ai.panel.weight", { weight: fmt.number(c.weight) })}</span>
                  )}
                  {c.key === "lives" && isOneOf(LIVES_SOURCES, source) && (
                    <span className="muted score-source">
                      {t("ai.panel.livesSource", { source: t(`ai.livesSource.${source}`) })}
                    </span>
                  )}
                  {c.key === "sensitive_sites" && <SensitiveSite component={c} />}
                  {c.key === "vision_fire" && <VisionSource component={c} />}
                </th>
                <td>{value(c)}</td>
                <td className="num">{c.value === null || c.value === undefined ? "—" : fmt.decimal(c.points)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CredibilityBreakdown({ score }: { score: ExplainedScore }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="ai-score">
      <h3>
        {t("ai.panel.credibility")}{" "}
        <span className="score-total">{t("ai.panel.outOf", { score: fmt.number(score.score) })}</span>
      </h3>
      <table className="score-table">
        <caption className="visually-hidden">{t("ai.panel.credibilityCaption")}</caption>
        <tbody>
          {score.components.map((c) => (
            <tr key={c.key}>
              <th scope="row">{labelOf(t, "ai.credibility", CREDIBILITY_COMPONENTS, c.key)}</th>
              <td className={`num points ${c.points < 0 ? "points--neg" : "points--pos"}`} dir="ltr">
                {fmt.signed(c.points)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExtractionView({ extraction, reported }: { extraction: Extraction; reported: StaffReportDetail["category"] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const differs = extraction.category !== reported;
  const yesNo = (b: boolean) => (b ? t("common.yes") : t("common.no"));
  return (
    <div className="ai-extraction">
      <h3>{t("ai.panel.extraction")}</h3>
      <dl className="fields">
        <dt>{t("ai.panel.suggestedCategory")}</dt>
        <dd className={differs ? "suggested suggested--differs" : "suggested"}>
          <CategoryLabel category={extraction.category} />
          {differs && <span className="tag tag--differs">{t("ai.panel.differsFromReported")}</span>}
        </dd>
        <dt>{t("ai.livesAtRisk")}</dt>
        <dd className={extraction.lives_at_risk ? "flag--danger" : undefined}>{yesNo(extraction.lives_at_risk)}</dd>
        <dt>{t("ai.panel.peopleTrapped")}</dt>
        <dd className={extraction.people_trapped ? "flag--danger" : undefined}>{yesNo(extraction.people_trapped)}</dd>
        <dt>{t("ai.panel.injured")}</dt>
        <dd>{fmt.number(extraction.injured_count)}</dd>
        <dt>{t("ai.panel.deaths")}</dt>
        <dd className={extraction.deaths_reported ? "flag--danger" : undefined}>{yesNo(extraction.deaths_reported)}</dd>
        <dt>{t("ai.panel.hazards")}</dt>
        <dd>
          {extraction.hazards.length === 0
            ? t("common.none")
            : extraction.hazards.map((h) => (
                <span key={h} className="tag" dir="auto">
                  {h}
                </span>
              ))}
        </dd>
        <dt>{t("ai.panel.keywords")}</dt>
        <dd>
          {extraction.keywords.length === 0
            ? t("common.none")
            : extraction.keywords.map((k) => (
                <span key={k} className="tag" dir="auto">
                  {k}
                </span>
              ))}
        </dd>
        <dt>{t("ai.panel.confidence")}</dt>
        <dd>{fmt.percent(extraction.confidence)}</dd>
      </dl>
      {extraction.summary_ar && (
        <>
          <h4>{t("ai.panel.summary")}</h4>
          <p className="report-text" lang="ar" dir="rtl">
            {extraction.summary_ar}
          </p>
        </>
      )}
    </div>
  );
}

function TranscriptView({ item }: { item: Transcript }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const kind = isOneOf(MEDIA_KINDS, item.kind) ? t(`detail.mediaKind.${item.kind}`) : item.kind;
  return (
    <li className="transcript">
      <p className="transcript__head">
        <strong>{kind}</strong>
        <span className="muted">
          {t("ai.panel.language")}: {languageLabel(t, item.language)}
        </span>
        {typeof item.duration_s === "number" && (
          <span className="muted">
            {t("ai.panel.duration")}: {fmt.duration(item.duration_s)}
          </span>
        )}
      </p>
      {item.error ? (
        <p className="alert alert--error">
          {t("ai.panel.transcriptError", {
            reason: isOneOf(TRANSCRIPT_ERRORS, item.error)
              ? t(`ai.transcriptErrors.${item.error}`)
              : t("ai.transcriptErrors.other"),
          })}
        </p>
      ) : (
        <>
          {item.text && (
            <blockquote className="report-text" lang={item.language ?? undefined} dir="auto">
              <MaskedText text={item.text} masks={item.text_masks} />
            </blockquote>
          )}
          {item.translation_ar && (
            <>
              <p className="muted translation-label">{t("ai.translation")}</p>
              <blockquote className="report-text report-text--translation" lang="ar" dir="rtl">
                <MaskedText text={item.translation_ar} masks={item.translation_ar_masks} />
              </blockquote>
            </>
          )}
        </>
      )}
    </li>
  );
}

function AnalysisFooter({ analysis }: { analysis: NonNullable<StaffReportDetail["analysis"]> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const models = Object.entries(analysis.models).filter((e): e is [string, string] => typeof e[1] === "string");
  return (
    <footer className="ai-footer">
      <p>
        {t(`ai.state.${analysis.state}`)} · {t("ai.panel.attempts", { count: analysis.attempts })} ·{" "}
        {t("ai.panel.updatedAt", { date: fmt.dateTime(analysis.updated_at) })}
      </p>
      <ul className="ai-steps">
        {ANALYSIS_STEPS.map((step) => {
          const state = analysis.steps[step];
          if (!state) return null;
          return (
            <li key={step}>
              {t(`ai.steps.${step}`)}:{" "}
              {isOneOf(STEP_STATES, state) ? t(`ai.stepState.${state}`) : t("common.notAvailable")}
            </li>
          );
        })}
      </ul>
      {models.length > 0 && (
        <p>
          {t("ai.panel.models")}:{" "}
          {models.map(([k, m], i) => (
            <span key={k}>
              {i > 0 && t("common.listSeparator")}
              <span dir="ltr" className="code">
                {m}
              </span>
            </span>
          ))}
        </p>
      )}
    </footer>
  );
}

/**
 * "AI analysis" panel of a report: explained priority and credibility, the model's extraction, transcripts,
 * and the analysis steps. Everything is a suggestion; the decision stays human (BR-06).
 */
export function AnalysisPanel({ report }: { report: StaffReportDetail }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const analysis = report.analysis ?? null;
  return (
    <section className="card ai-panel" aria-labelledby="sec-ai">
      <div className="ai-panel__head">
        <h2 id="sec-ai">{t("ai.panel.title")}</h2>
        <AnalysisChip state={report.analysis_state} />
      </div>
      <p className="alert alert--info ai-notice" role="note">
        {t("ai.panel.notice")}
      </p>
      {!analysis ? (
        <>
          <dl className="fields">
            <dt>{t("ai.panel.priority")}</dt>
            <dd>
              <PriorityBadge score={report.priority_score} />
            </dd>
            <dt>{t("ai.panel.credibility")}</dt>
            <dd>
              {report.credibility_score === null
                ? "—"
                : t("ai.panel.outOf", { score: fmt.number(report.credibility_score) })}
            </dd>
          </dl>
          <p className="muted">{t("ai.panel.noAnalysis")}</p>
        </>
      ) : (
        <>
          <div className="ai-panel__scores">
            {analysis.priority ? (
              <PriorityBreakdown score={analysis.priority} />
            ) : (
              <p className="muted">{t("ai.panel.noPriority")}</p>
            )}
            {analysis.credibility && <CredibilityBreakdown score={analysis.credibility} />}
          </div>
          {analysis.extraction && <ExtractionView extraction={analysis.extraction} reported={report.category} />}
          {analysis.transcripts.length > 0 && (
            <div>
              <h3>{t("ai.panel.transcripts")}</h3>
              <ul className="transcripts">
                {analysis.transcripts.map((tr) => (
                  <TranscriptView key={tr.media_id} item={tr} />
                ))}
              </ul>
            </div>
          )}
          <AnalysisFooter analysis={analysis} />
        </>
      )}
    </section>
  );
}
