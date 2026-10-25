import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { doctorKeys, type StaffDoctorDetail } from "../lib/doctorsApi";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { VOLUNTEER_DECISIONS_BY_STATUS, type VolunteerDecision } from "../lib/opsTypes";
import { AvailableTag, SpecialtyList } from "./DoctorsPage";
import { VolunteerStatusChip } from "./VolunteersPage";
import { PageTitle } from "../components/PageTitle";

const NEEDS_REASON: readonly VolunteerDecision[] = ["reject", "suspend"];

/** Verify (approve) or reject a registration, suspend or reinstate a doctor; the decision is e-mailed. */
function ReviewForm({ doctor }: { doctor: StaffDoctorDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const reasonId = useId();
  const decisions = VOLUNTEER_DECISIONS_BY_STATUS[doctor.status];
  const [decision, setDecision] = useState<VolunteerDecision | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);
  const [done, setDone] = useState(false);
  const mutation = useMutation({
    mutationFn: (v: { decision: VolunteerDecision; reason: string }) =>
      api.reviewDoctor(doctor.id, v.decision, v.reason),
    onSuccess: (updated) => {
      qc.setQueryData(doctorKeys.one(doctor.id), updated);
      void qc.invalidateQueries({ queryKey: doctorKeys.all });
      setDecision(null);
      setReason("");
      setDone(true);
    },
  });
  const status = (
    <div role="status" aria-live="polite">
      {done && <p className="alert alert--ok">{t("volunteers.review.done")}</p>}
    </div>
  );
  if (decisions.length === 0)
    return (
      <>
        {status}
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
      {doctor.status === "pending" && <p>{t("doctors.review.check")}</p>}
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
            {t(`doctors.review.decision.${d}`)}
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
      {status}
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

/** One doctor's registration (opening it is audited: `doctor.view`). */
export function DoctorDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const query = useQuery({
    queryKey: doctorKeys.one(id),
    queryFn: ({ signal }) => api.doctor(id, signal),
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });

  if (query.isPending) return <Loading />;
  if (query.isError)
    return (
      <div className="page">
        <Link to="/doctors">{t("doctors.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  const d = query.data;
  return (
    <article className="page detail" aria-labelledby="doctor-title">
      <p>
        <Link to="/doctors">{t("doctors.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="stethoscope" tone="purple" id="doctor-title" dir="auto">
          {d.full_name ?? t("doctors.unnamed")}
        </PageTitle>
        <VolunteerStatusChip status={d.status} />
        <AvailableTag doctor={d} />
      </div>
      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-doctor">
          <h2 id="sec-doctor">{t("doctors.detail.registration")}</h2>
          <dl className="fields">
            <dt>{t("doctors.columns.kind")}</dt>
            <dd>{t(`doctors.kind.${d.kind}`)}</dd>
            <dt>{t("doctors.columns.specialties")}</dt>
            <dd>
              <SpecialtyList specialties={d.specialties} />
            </dd>
            <dt>{t("doctors.detail.licence")}</dt>
            <dd dir="ltr">{d.licence_no ?? "—"}</dd>
            <dt>{t("doctors.columns.workplace")}</dt>
            <dd dir="auto">{d.workplace}</dd>
            <dt>{t("filters.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(d.gouvernorat_code)}</dd>
            {d.kind === "civil_protection" && (
              <>
                <dt>{t("doctors.detail.cpUnit")}</dt>
                <dd dir="auto">{d.cp_unit ?? "—"}</dd>
                <dt>{t("doctors.detail.cpStaffNo")}</dt>
                <dd dir="ltr">{d.cp_staff_no ?? "—"}</dd>
              </>
            )}
            <dt>{t("volunteers.detail.phone")}</dt>
            <dd>
              {d.phone ? (
                <a href={`tel:${d.phone}`} dir="ltr">
                  {d.phone}
                </a>
              ) : (
                "—"
              )}
            </dd>
            <dt>{t("volunteers.detail.email")}</dt>
            <dd dir="ltr">{d.email ? <a href={`mailto:${d.email}`}>{d.email}</a> : "—"}</dd>
            <dt>{t("volunteers.columns.submittedAt")}</dt>
            <dd>{fmt.dateTime(d.submitted_at)}</dd>
            {d.review_reason && (
              <>
                <dt>{t("volunteers.detail.reviewReason")}</dt>
                <dd dir="auto">{d.review_reason}</dd>
              </>
            )}
          </dl>
          <p className="muted">{t("doctors.detail.audited")}</p>
        </section>
        <section className="card" aria-labelledby="sec-doctor-review">
          <h2 id="sec-doctor-review">{t("doctors.review.title")}</h2>
          <ReviewForm doctor={d} />
        </section>
      </div>
      <section className="card" aria-labelledby="sec-doctor-reviews">
        <h2 id="sec-doctor-reviews">{t("volunteers.detail.reviews")}</h2>
        {d.reviews.length === 0 ? (
          <p className="muted">{t("volunteers.detail.noReview")}</p>
        ) : (
          <ol className="timeline">
            {d.reviews.map((r, i) => (
              <li key={`${r.at}-${i}`}>
                <strong>{t(`doctors.review.decision.${r.decision}`, { defaultValue: r.decision })}</strong>
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
    </article>
  );
}
