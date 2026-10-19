import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import {
  VOLUNTEER_DECISIONS_BY_STATUS,
  type StaffVolunteerDetail,
  type VolunteerDecision,
} from "../lib/opsTypes";
import { canReviewVolunteers } from "../lib/roles";
import { ReadyTag, SkillList, VolunteerStatusChip } from "./VolunteersPage";

const NEEDS_REASON: readonly VolunteerDecision[] = ["reject", "suspend"];

/** FR-C-04 review: approve or reject an application, suspend or reinstate a volunteer (the decision is e-mailed). */
function ReviewForm({ volunteer }: { volunteer: StaffVolunteerDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const reasonId = useId();
  const decisions = VOLUNTEER_DECISIONS_BY_STATUS[volunteer.status];
  const [decision, setDecision] = useState<VolunteerDecision | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);
  const [done, setDone] = useState(false);
  const mutation = useMutation({
    mutationFn: (v: { decision: VolunteerDecision; reason: string }) => api.reviewVolunteer(volunteer.id, v.decision, v.reason),
    onSuccess: (updated) => {
      qc.setQueryData(opsKeys.volunteer(volunteer.id), updated);
      void qc.invalidateQueries({ queryKey: opsKeys.volunteersAll });
      setDecision(null);
      setReason("");
      setDone(true);
    },
  });
  if (decisions.length === 0)
    return (
      <>
        <div role="status" aria-live="polite">
          {done && <p className="alert alert--ok">{t("volunteers.review.done")}</p>}
        </div>
        <p className="muted">{t("volunteers.review.none")}</p>
      </>
    );
  const needsReason = decision !== null && NEEDS_REASON.includes(decision);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!decision) return;
    if (needsReason && !reason.trim()) {
      setReasonError(true);
      return;
    }
    setReasonError(false);
    mutation.mutate({ decision, reason: reason.trim() });
  };
  return (
    <form className="review" onSubmit={submit} noValidate>
      <div className="actions" role="group" aria-label={t("volunteers.review.choose")}>
        {decisions.map((d) => (
          <button
            key={d}
            type="button"
            className={`btn${decision === d ? " btn--primary" : ""}`}
            aria-pressed={decision === d}
            onClick={() => {
              setDecision(d);
              setDone(false);
            }}
          >
            {t(`volunteers.review.decision.${d}`)}
          </button>
        ))}
      </div>
      {decision && (
        <>
          <div className={`field${reasonError ? " field--invalid" : ""}`}>
            <label htmlFor={reasonId}>
              {needsReason ? t("volunteers.review.reason") : t("volunteers.review.reasonOptional")}
            </label>
            <textarea
              id={reasonId}
              value={reason}
              rows={3}
              maxLength={1000}
              dir="auto"
              aria-invalid={reasonError || undefined}
              aria-describedby={reasonError ? `${reasonId}-error` : undefined}
              onChange={(e) => setReason(e.target.value)}
            />
            {reasonError && (
              <span id={`${reasonId}-error`} className="field__error">
                {t("volunteers.review.reasonRequired")}
              </span>
            )}
          </div>
          <p className="muted">{t("volunteers.review.emailNotice")}</p>
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
              {mutation.isPending ? t("ops.working") : t("volunteers.review.confirm")}
            </button>
            <button type="button" className="btn" onClick={() => setDecision(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </>
      )}
      <div role="status" aria-live="polite">
        {done && <p className="alert alert--ok">{t("volunteers.review.done")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

/** One volunteer (opening it is audited: `volunteer.view`). */
export function VolunteerDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const canReview = canReviewVolunteers(user?.identity.roles ?? []);
  const query = useQuery({
    queryKey: opsKeys.volunteer(id),
    queryFn: ({ signal }) => api.volunteer(id, signal),
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });

  if (query.isPending) return <Loading />;
  if (query.isError)
    return (
      <div className="page">
        <Link to="/volunteers">{t("volunteers.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  const v = query.data;
  return (
    <article className="page detail" aria-labelledby="volunteer-title">
      <p>
        <Link to="/volunteers">{t("volunteers.back")}</Link>
      </p>
      <div className="page__head">
        <h1 id="volunteer-title" dir="auto">
          {v.full_name ?? t("ops.volunteer")}
        </h1>
        <VolunteerStatusChip status={v.status} />
        <ReadyTag volunteer={v} />
      </div>
      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-volunteer">
          <h2 id="sec-volunteer">{t("volunteers.detail.profile")}</h2>
          <dl className="fields">
            <dt>{t("volunteers.columns.skills")}</dt>
            <dd>
              <SkillList skills={v.skills} />
              {v.other_skill && <span dir="auto"> {v.other_skill}</span>}
            </dd>
            <dt>{t("volunteers.columns.availability")}</dt>
            <dd>{t(`volunteers.availability.${v.availability}`)}</dd>
            <dt>{t("volunteers.detail.period")}</dt>
            <dd>
              {v.period_to
                ? t("volunteers.detail.periodRange", { from: fmt.date(v.period_from), to: fmt.date(v.period_to) })
                : t("volunteers.detail.periodOpen", { from: fmt.date(v.period_from) })}
            </dd>
            <dt>{t("filters.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(v.gouvernorat_code)}</dd>
            <dt>{t("volunteers.detail.phone")}</dt>
            <dd dir="ltr">{v.phone ? <a href={`tel:${v.phone}`}>{v.phone}</a> : "—"}</dd>
            <dt>{t("volunteers.detail.email")}</dt>
            <dd dir="ltr">{v.email ? <a href={`mailto:${v.email}`}>{v.email}</a> : "—"}</dd>
            <dt>{t("volunteers.columns.submittedAt")}</dt>
            <dd>{fmt.dateTime(v.submitted_at)}</dd>
            {v.notes && (
              <>
                <dt>{t("volunteers.detail.notes")}</dt>
                <dd dir="auto">{v.notes}</dd>
              </>
            )}
            {v.review_reason && (
              <>
                <dt>{t("volunteers.detail.reviewReason")}</dt>
                <dd dir="auto">{v.review_reason}</dd>
              </>
            )}
          </dl>
        </section>
        {canReview && (
          <section className="card" aria-labelledby="sec-review">
            <h2 id="sec-review">{t("volunteers.review.title")}</h2>
            <ReviewForm volunteer={v} />
          </section>
        )}
      </div>
      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-reviews">
          <h2 id="sec-reviews">{t("volunteers.detail.reviews")}</h2>
          {v.reviews.length === 0 ? (
            <p className="muted">{t("volunteers.detail.noReview")}</p>
          ) : (
            <ol className="timeline">
              {v.reviews.map((r, i) => (
                <li key={`${r.at}-${i}`}>
                  <strong>{t(`volunteers.review.decision.${r.decision}`, { defaultValue: r.decision })}</strong>
                  <time dateTime={r.at}>{fmt.dateTime(r.at)}</time>
                  {r.reason && (
                    <p className="timeline__note" dir="auto">
                      {r.reason}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
        <section className="card" aria-labelledby="sec-vol-callouts">
          <h2 id="sec-vol-callouts">{t("volunteers.detail.callouts")}</h2>
          {v.callouts.length === 0 ? (
            <p className="muted">{t("volunteers.detail.noCallout")}</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <caption className="visually-hidden">{t("volunteers.detail.callouts")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("volunteers.detail.sentAt")}</th>
                    <th scope="col">{t("volunteers.columns.skills")}</th>
                    <th scope="col">{t("ops.callout.answer")}</th>
                    <th scope="col">{t("volunteers.detail.incident")}</th>
                  </tr>
                </thead>
                <tbody>
                  {v.callouts.map((c) => (
                    <tr key={c.callout_id}>
                      <td>
                        <time dateTime={c.sent_at}>{fmt.dateTime(c.sent_at)}</time>
                      </td>
                      <td>{t(`volunteers.skill.${c.skill}`)}</td>
                      <td>{t(`ops.callout.target.${c.status}`)}</td>
                      <td>
                        <Link to={`/incidents/${encodeURIComponent(c.incident_id)}`}>{t("volunteers.detail.openIncident")}</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </article>
  );
}
