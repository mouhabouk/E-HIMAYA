import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { RevokeButton } from "../components/BreakGlass";
import { ErrorBox, Loading } from "../components/Feedback";
import { InlineDialog, ReasonField } from "../components/Phase9Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { REASON_RANGE } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import {
  BREAKGLASS_STATUSES,
  REVIEW_OUTCOMES,
  type BreakGlassGrant,
  type BreakGlassStatus,
  type ReviewOutcome,
} from "../lib/phase9Types";
import { canReviewBreakGlass } from "../lib/roles";
import { PageTitle } from "../components/PageTitle";

/** Status of a grant as the list shows it (the API filters by the same four states). */
export function grantStatus(grant: BreakGlassGrant, now: number = Date.now()): BreakGlassStatus {
  if (grant.state) return grant.state;
  if (grant.reviewed_at) return "reviewed";
  if (!grant.revoked_at && Date.parse(grant.expires_at) > now) return "active";
  return "pending_review";
}

function ReviewForm({ grant, onDone }: { grant: BreakGlassGrant; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [outcome, setOutcome] = useState<ReviewOutcome | null>(null);
  const [note, setNote] = useState("");
  const [tried, setTried] = useState(false);
  const range = REASON_RANGE;
  const review = useMutation({
    mutationFn: (o: ReviewOutcome) => api.reviewBreakGlass(grant.id, o, note.trim()),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p9Keys.grantsAll });
      onDone();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    const n = note.trim().length;
    if (!outcome || n < range.min || n > range.max) return;
    review.mutate(outcome);
  };
  return (
    <form noValidate onSubmit={submit}>
      <fieldset>
        <legend>{t("breakGlass.review.outcome")}</legend>
        {REVIEW_OUTCOMES.map((o) => (
          <label key={o} className="radio">
            <input type="radio" name={`${id}-outcome`} checked={outcome === o} onChange={() => setOutcome(o)} />{" "}
            {t(`breakGlass.review.${o}`)}
          </label>
        ))}
        {tried && !outcome && (
          <p className="field__error" role="alert">
            {t("breakGlass.review.outcomeRequired")}
          </p>
        )}
      </fieldset>
      <ReasonField label={t("breakGlass.review.note")} value={note} onChange={setNote} range={range} showError={tried} />
      <button type="submit" className="btn btn--primary" disabled={review.isPending}>
        {t("breakGlass.review.submit")}
      </button>
      {review.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(review.error))}
        </p>
      )}
    </form>
  );
}

function GrantTarget({ grant }: { grant: BreakGlassGrant }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  if (grant.target_kind === "gouvernorat") {
    return <>{t("breakGlass.targetGouvernorat", { name: gouvernorats.nameOf(grant.gouvernorat_code) ?? "" })}</>;
  }
  const path = grant.target_kind === "report" ? "reports" : "incidents";
  return (
    <>
      {t(`breakGlass.target.${grant.target_kind}`)}{" "}
      {grant.target_id && (
        <Link to={`/${path}/${encodeURIComponent(grant.target_id)}`} dir="ltr" className="code">
          {grant.target_id.slice(0, 8)}
        </Link>
      )}
    </>
  );
}

function GrantRow({ grant, reviewer, self }: { grant: BreakGlassGrant; reviewer: boolean; self: string | undefined }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const [reviewing, setReviewing] = useState(false);
  const status = grantStatus(grant);
  const own = grant.subject === self;
  return (
    <li className="card grant">
      <p>
        <strong dir="auto">{grant.subject_name ?? grant.subject}</strong> · <GrantTarget grant={grant} /> ·{" "}
        <span className={`tag tag--grant-${status}`}>
          {t(`breakGlass.status.${status}`)}
        </span>
      </p>
      <p className="muted">
        {t("breakGlass.period", { from: fmt.dateTime(grant.granted_at), to: fmt.dateTime(grant.revoked_at ?? grant.expires_at) })}
        {grant.revoked_at ? ` · ${t("breakGlass.revoked")}` : ""}
      </p>
      <blockquote dir="auto">{grant.justification}</blockquote>
      {grant.review_outcome && (
        <p>
          {t("breakGlass.review.result", { outcome: t(`breakGlass.review.${grant.review_outcome}`) })}
          {grant.reviewed_at ? ` · ${fmt.dateTime(grant.reviewed_at)}` : ""}
          {grant.review_note ? (
            <>
              {" · "}
              <span dir="auto">{grant.review_note}</span>
            </>
          ) : null}
        </p>
      )}
      <div className="actions">
        {status === "active" && (own || reviewer) && <RevokeButton grant={grant} />}
        {reviewer && !own && !grant.reviewed_at && !reviewing && (
          <button type="button" className="btn btn--small" onClick={() => setReviewing(true)}>
            {t("breakGlass.review.open")}
          </button>
        )}
        {reviewer && own && !grant.reviewed_at && <span className="muted">{t("breakGlass.review.selfNote")}</span>}
      </div>
      {reviewing && (
        <InlineDialog title={t("breakGlass.review.title")} onClose={() => setReviewing(false)}>
          <ReviewForm grant={grant} onDone={() => setReviewing(false)} />
        </InlineDialog>
      )}
    </li>
  );
}

/**
 * Break-glass grants (phase 9 §6.1). National security administrators see every grant, review expired ones
 * (justified/unjustified, not their own) and may revoke; other requesters see and revoke their own grants.
 */
export function BreakGlassPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const base = useId();
  const reviewer = user ? canReviewBreakGlass(user.identity) : false;
  const [status, setStatus] = useState<BreakGlassStatus | "">(reviewer ? "pending_review" : "");
  const query = useInfiniteQuery({
    queryKey: p9Keys.grants(status),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.breakGlassGrants({ status, cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="lockOpen" tone="red">{t("breakGlass.pageTitle")}</PageTitle>
      </div>
      <p className="muted">{reviewer ? t("breakGlass.pageIntroReviewer") : t("breakGlass.pageIntroOwn")}</p>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-status`}>{t("filters.status")}</label>
          <select id={`${base}-status`} value={status} onChange={(e) => setStatus(e.target.value as BreakGlassStatus | "")}>
            <option value="">{t("notify.filters.all")}</option>
            {BREAKGLASS_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`breakGlass.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("breakGlass.empty")}</p>}
      {items.length > 0 && (
        <ul className="grant-list">
          {items.map((g) => (
            <GrantRow key={g.id} grant={g} reviewer={reviewer} self={user?.identity.subject} />
          ))}
        </ul>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
