import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { AreaTabs, CategorySelect, Fact, GouvernoratSelect, LoadMore, MutationError, ReasonForm } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { p8Keys } from "../lib/phase8Api";
import {
  BADGE_STATUSES,
  BADGES,
  MULTIPLIER_RANGE,
  NOMINATION_KINDS,
  NOMINATION_STATUSES,
  NOMINATION_SUBJECT,
  POINTS_RANGE,
  RULE_REASONS,
  type BadgeAward,
  type BadgeStatus,
  type Nomination,
  type NominationBody,
  type NominationKind,
  type NominationStatus,
  type RewardCertificate,
  type RewardRule,
  type RuleReason,
} from "../lib/phase8Types";
import { canEditRewardRules, canManageRewards, canSeeRewardActivity } from "../lib/roles";
import type { Category } from "../lib/types";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ids = (text: string) => text.split(/[\s,]+/).filter(Boolean);

function RewardsTabs() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const tabs = [{ to: "/rewards", label: t("rewards.tabs.rules"), end: true }];
  if (canSeeRewardActivity(user?.identity.roles ?? [])) {
    tabs.push(
      { to: "/rewards/confirmations", label: t("rewards.tabs.confirmations"), end: false },
      { to: "/rewards/nominations", label: t("rewards.tabs.nominations"), end: false },
      { to: "/rewards/certificates", label: t("rewards.tabs.certificates"), end: false },
      { to: "/rewards/leaderboard", label: t("rewards.tabs.leaderboard"), end: false },
    );
  }
  return <AreaTabs label={t("rewards.tabs.label")} tabs={tabs} />;
}

function RewardsFrame({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="page">
      <div className="page__head">
        <h1>{title}</h1>
      </div>
      <RewardsTabs />
      <p className="alert alert--info rewards-safety" role="note">
        {t("rewards.safety")}
      </p>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------- settings and rules

function SettingsCard() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const query = useQuery({ queryKey: p8Keys.rewardSettings, queryFn: ({ signal }) => api.rewardSettings(signal) });
  const s = query.data;
  return (
    <section className="card" aria-labelledby="reward-settings">
      <h2 id="reward-settings">{t("rewards.settings.title")}</h2>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {s && (
        <>
          <dl className="kpis">
            <Fact label={t("rewards.settings.dailyCap")}>{t("rewards.points", { n: fmt.number(s.daily_cap) })}</Fact>
            {BADGES.map((b) => (
              <Fact key={b} label={t("rewards.settings.threshold", { badge: t(`rewards.badge.${b}`) })}>
                {t("rewards.points", { n: fmt.number(s.thresholds[b]) })}
              </Fact>
            ))}
          </dl>
          <p className="muted">{t("rewards.settings.readOnly")}</p>
          {s.paused_gouvernorats.length > 0 && (
            <p className="alert alert--warn">
              {t("rewards.settings.paused", {
                list: s.paused_gouvernorats.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator")),
              })}
            </p>
          )}
        </>
      )}
      <p className="muted">{t("rewards.settings.noCash")}</p>
    </section>
  );
}

function isMultiplier(reason: RuleReason) {
  return reason === "accurate_category";
}

export function ruleValueError(reason: RuleReason, raw: string): boolean {
  const n = Number(raw);
  if (raw.trim() === "" || !Number.isFinite(n)) return true;
  if (isMultiplier(reason)) return n < MULTIPLIER_RANGE[0] || n > MULTIPLIER_RANGE[1];
  return !Number.isInteger(n) || n < POINTS_RANGE[0] || n > POINTS_RANGE[1];
}

function RuleRow({ rule, editable }: { rule: RewardRule; editable: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const base = useId();
  const multiplier = isMultiplier(rule.reason);
  const current = multiplier ? (rule.multiplier ?? 1) : (rule.points ?? 0);
  const [value, setValue] = useState(String(current));
  const invalid = ruleValueError(rule.reason, value);
  const done = () => void qc.invalidateQueries({ queryKey: p8Keys.rewardRules });
  const save = useMutation({
    mutationFn: (patch: Parameters<typeof api.updateRewardRule>[1]) => api.updateRewardRule(rule.id, patch),
    onSuccess: done,
  });
  const remove = useMutation({ mutationFn: () => api.deleteRewardRule(rule.id), onSuccess: done });
  const label = `${t(`rewards.reason.${rule.reason}`)}${rule.category ? ` · ${t(`category.${rule.category}`)}` : ""}`;
  return (
    <tr>
      <th scope="row">
        {t(`rewards.reason.${rule.reason}`)}
        {rule.is_default && <span className="tag">{t("rewards.rules.default")}</span>}
      </th>
      <td>{rule.category ? t(`category.${rule.category}`) : t("rewards.rules.allCategories")}</td>
      <td>
        {editable ? (
          <span className="input-with-button">
            <label htmlFor={`${base}-v`} className="visually-hidden">
              {t("rewards.rules.valueOf", { rule: label })}
            </label>
            <input
              id={`${base}-v`}
              type="number"
              className="input--short"
              step={multiplier ? 0.1 : 1}
              min={multiplier ? MULTIPLIER_RANGE[0] : POINTS_RANGE[0]}
              max={multiplier ? MULTIPLIER_RANGE[1] : POINTS_RANGE[1]}
              value={value}
              aria-invalid={invalid ? true : undefined}
              onChange={(e) => setValue(e.target.value)}
            />
            <button
              type="button"
              className="btn btn--small"
              disabled={invalid || Number(value) === current || save.isPending}
              onClick={() => save.mutate(multiplier ? { multiplier: Number(value) } : { points: Number(value) })}
            >
              {t("rewards.rules.save")}
            </button>
          </span>
        ) : multiplier ? (
          `×${fmt.decimal(current)}`
        ) : (
          t("rewards.points", { n: fmt.signed(current) })
        )}
        {(save.isError || remove.isError) && (
          <span className="field__error" role="alert">
            {t(errorMessageKey(save.error ?? remove.error))}
          </span>
        )}
      </td>
      <td>
        {editable ? (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={rule.enabled}
              disabled={save.isPending}
              onChange={() => save.mutate({ enabled: !rule.enabled })}
              aria-label={t("rewards.rules.enabledOf", { rule: label })}
            />
          </label>
        ) : rule.enabled ? (
          t("common.yes")
        ) : (
          t("common.no")
        )}
      </td>
      <td>
        {editable && !rule.is_default && (
          <button type="button" className="btn btn--small btn--ghost" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {t("rewards.rules.delete")}
          </button>
        )}
      </td>
    </tr>
  );
}

function NewRuleForm() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const base = useId();
  const [reason, setReason] = useState<RuleReason>("report_verified");
  const [category, setCategory] = useState<Category>("fire");
  const [value, setValue] = useState("50");
  const invalid = ruleValueError(reason, value);
  const create = useMutation({
    mutationFn: () =>
      api.createRewardRule({
        reason,
        category,
        enabled: true,
        ...(isMultiplier(reason) ? { multiplier: Number(value) } : { points: Number(value) }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: p8Keys.rewardRules }),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!invalid) create.mutate();
  };
  return (
    <form className="ops-form" onSubmit={submit} noValidate aria-labelledby={`${base}-h`}>
      <h3 id={`${base}-h`}>{t("rewards.rules.newOverride")}</h3>
      <div className="fields-row">
        <div className="field">
          <label htmlFor={`${base}-r`}>{t("rewards.rules.reason")}</label>
          <select id={`${base}-r`} value={reason} onChange={(e) => setReason(e.target.value as RuleReason)}>
            {RULE_REASONS.map((r) => (
              <option key={r} value={r}>
                {t(`rewards.reason.${r}`)}
              </option>
            ))}
          </select>
        </div>
        <CategorySelect value={category} onChange={(c) => setCategory((c ?? "fire") as Category)} label={t("analytics.category")} />
        <div className={`field field--number${invalid ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-v`}>{isMultiplier(reason) ? t("rewards.rules.multiplier") : t("rewards.rules.pointsField")}</label>
          <input id={`${base}-v`} type="number" value={value} onChange={(e) => setValue(e.target.value)} aria-describedby={`${base}-hint`} />
          <p id={`${base}-hint`} className="muted">
            {isMultiplier(reason)
              ? t("rewards.rules.multiplierRange", { min: MULTIPLIER_RANGE[0], max: MULTIPLIER_RANGE[1] })
              : t("rewards.rules.pointsRange", { min: POINTS_RANGE[0], max: POINTS_RANGE[1] })}
          </p>
        </div>
      </div>
      <div className="actions">
        <button type="submit" className="btn" disabled={invalid || create.isPending}>
          {t("rewards.rules.add")}
        </button>
      </div>
      {create.isError && <MutationError error={create.error} />}
    </form>
  );
}

/** Rules (configurable, audited) and the read-only settings; no prize or cash configuration exists. */
export function RewardRulesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const editable = user ? canEditRewardRules(user.identity) : false;
  const query = useQuery({ queryKey: p8Keys.rewardRules, queryFn: ({ signal }) => api.rewardRules(signal) });
  const rules = [...(query.data ?? [])].sort(
    (a, b) => RULE_REASONS.indexOf(a.reason) - RULE_REASONS.indexOf(b.reason) || Number(b.is_default) - Number(a.is_default),
  );
  return (
    <RewardsFrame title={t("rewards.title")}>
      <SettingsCard />
      <section className="card" aria-labelledby="reward-rules">
        <h2 id="reward-rules">{t("rewards.rules.title")}</h2>
        <p className="muted">{editable ? t("rewards.rules.intro") : t("rewards.rules.readOnly")}</p>
        {query.isPending && <Loading />}
        {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
        {rules.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("rewards.rules.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("rewards.rules.reason")}</th>
                  <th scope="col">{t("analytics.category")}</th>
                  <th scope="col">{t("rewards.rules.value")}</th>
                  <th scope="col">{t("rewards.rules.enabled")}</th>
                  <th scope="col">
                    <span className="visually-hidden">{t("schedules.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <RuleRow key={`${r.id}-${r.points ?? ""}-${r.multiplier ?? ""}`} rule={r} editable={editable} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {editable && <NewRuleForm />}
      </section>
    </RewardsFrame>
  );
}

// ---------------------------------------------------------------- badge confirmations

function BadgeRow({ award, manage }: { award: BadgeAward; manage: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [asking, setAsking] = useState<"reject" | "revoke" | null>(null);
  const done = () => {
    setAsking(null);
    void qc.invalidateQueries({ queryKey: p8Keys.badgesAll });
  };
  const decide = useMutation({
    mutationFn: ({ action, reason }: { action: "confirm" | "reject" | "revoke"; reason?: string }) =>
      api.decideBadge(award.id, action, reason),
    onSuccess: done,
  });
  const issue = useMutation({
    mutationFn: () => api.issueRewardCertificate({ badge_award_id: award.id }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: p8Keys.certificates }),
  });
  const certifiable = award.status === "confirmed" && (award.level === "gold" || award.level === "ambassador");
  return (
    <tr>
      <th scope="row" className="code">
        {award.pseudonym}
      </th>
      <td>
        <span className={`tag tag--badge-${award.level}`}>{t(`rewards.badge.${award.level}`)}</span>
      </td>
      <td>{award.balance !== null ? fmt.number(award.balance) : "—"}</td>
      <td>{fmt.dateTime(award.awarded_at)}</td>
      <td>
        {t(`rewards.badgeStatus.${award.status}`)}
        {award.reason && (
          <span className="cell-sub" dir="auto">
            {award.reason}
          </span>
        )}
      </td>
      <td>
        {manage && asking ? (
          <ReasonForm
            label={t(`rewards.badges.${asking}Reason`)}
            submitLabel={t(`rewards.badges.${asking}`)}
            pending={decide.isPending}
            error={decide.error}
            onSubmit={(reason) => decide.mutate({ action: asking, reason })}
            onCancel={() => setAsking(null)}
          />
        ) : manage ? (
          <div className="ops-row-actions">
            {award.status === "pending" && (
              <>
                <button
                  type="button"
                  className="btn btn--small btn--primary"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ action: "confirm" })}
                >
                  {t("rewards.badges.confirm")}
                </button>
                <button type="button" className="btn btn--small" onClick={() => setAsking("reject")}>
                  {t("rewards.badges.reject")}
                </button>
              </>
            )}
            {award.status === "confirmed" && (
              <button type="button" className="btn btn--small btn--ghost" onClick={() => setAsking("revoke")}>
                {t("rewards.badges.revoke")}
              </button>
            )}
            {certifiable && (
              <button type="button" className="btn btn--small" disabled={issue.isPending || issue.isSuccess} onClick={() => issue.mutate()}>
                {issue.isSuccess ? t("rewards.certificates.issued") : t("rewards.certificates.issue")}
              </button>
            )}
            {decide.isError && <MutationError error={decide.error} />}
            {issue.isError && <MutationError error={issue.error} />}
          </div>
        ) : null}
      </td>
    </tr>
  );
}

/** Pending confirmations: silver and gold badges and the ambassador distinction show only once a staff member confirms. */
export function RewardConfirmationsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const base = useId();
  const manage = canManageRewards(user?.identity.roles ?? []);
  const [status, setStatus] = useState<BadgeStatus>("pending");
  const query = useInfiniteQuery({
    queryKey: p8Keys.badges(status),
    queryFn: ({ pageParam, signal }) => api.badgeAwards(status, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = query.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <RewardsFrame title={t("rewards.badges.title")}>
      <p className="muted">{t("rewards.badges.intro")}</p>
      <div className="field field--inline">
        <label htmlFor={`${base}-s`}>{t("rewards.badges.statusField")}</label>
        <select id={`${base}-s`} value={status} onChange={(e) => setStatus(e.target.value as BadgeStatus)}>
          {BADGE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`rewards.badgeStatus.${s}`)}
            </option>
          ))}
        </select>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("rewards.badges.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("rewards.badges.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("rewards.pseudonym")}</th>
                <th scope="col">{t("rewards.badges.level")}</th>
                <th scope="col">{t("rewards.balance")}</th>
                <th scope="col">{t("rewards.badges.awardedAt")}</th>
                <th scope="col">{t("rewards.badges.statusField")}</th>
                <th scope="col">{t("schedules.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <BadgeRow key={a.id} award={a} manage={manage} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore hasNext={query.hasNextPage} loading={query.isFetchingNextPage} onMore={() => void query.fetchNextPage()} />
    </RewardsFrame>
  );
}

// ---------------------------------------------------------------- nominations

export function nominationErrors(f: { subjectId: string; year: string; reason: string; reportIds: string; interventionIds: string }): string[] {
  const errors: string[] = [];
  if (!f.subjectId.trim()) errors.push("subject");
  const y = Number(f.year);
  if (!Number.isInteger(y) || y < 2020 || y > 2100) errors.push("year");
  if (f.reason.trim().length < 10) errors.push("reason");
  if ([...ids(f.reportIds), ...ids(f.interventionIds)].some((x) => !UUID_RE.test(x))) errors.push("evidence");
  return errors;
}

function NominationForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const base = useId();
  const [kind, setKind] = useState<NominationKind>("vigilant_citizen");
  const [f, setF] = useState({ subjectId: "", year: String(new Date().getFullYear()), reason: "", reportIds: "", interventionIds: "" });
  const [touched, setTouched] = useState(false);
  const errors = nominationErrors(f);
  const create = useMutation({
    mutationFn: (body: NominationBody) => api.createNomination(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p8Keys.nominationsAll });
      onDone();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (errors.length > 0) return;
    create.mutate({
      kind,
      subject_kind: NOMINATION_SUBJECT[kind],
      subject_id: f.subjectId.trim(),
      year: Number(f.year),
      reason: f.reason.trim(),
      evidence: { report_ids: ids(f.reportIds), intervention_ids: ids(f.interventionIds) },
    });
  };
  const bad = (k: string) => touched && errors.includes(k);
  return (
    <form className="card ops-form" onSubmit={submit} noValidate aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{t("rewards.nominations.new")}</h2>
      <div className="fields-row">
        <div className="field">
          <label htmlFor={`${base}-k`}>{t("rewards.nominations.kind")}</label>
          <select id={`${base}-k`} value={kind} onChange={(e) => setKind(e.target.value as NominationKind)}>
            {NOMINATION_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`rewards.nominationKind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={`field${bad("subject") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-s`}>{t(`rewards.nominations.subject.${NOMINATION_SUBJECT[kind]}`)}</label>
          <input id={`${base}-s`} dir="ltr" className="code" value={f.subjectId} onChange={(e) => setF({ ...f, subjectId: e.target.value })} />
        </div>
        <div className={`field field--number${bad("year") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-y`}>{t("rewards.nominations.year")}</label>
          <input id={`${base}-y`} type="number" value={f.year} onChange={(e) => setF({ ...f, year: e.target.value })} />
        </div>
      </div>
      <div className={`field${bad("reason") ? " field--invalid" : ""}`}>
        <label htmlFor={`${base}-r`}>{t("rewards.nominations.reason")}</label>
        <textarea id={`${base}-r`} dir="auto" rows={3} maxLength={2000} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />
      </div>
      <div className="fields-row">
        <div className={`field${bad("evidence") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-er`}>{t("rewards.nominations.reportIds")}</label>
          <textarea id={`${base}-er`} dir="ltr" className="code" rows={2} value={f.reportIds} onChange={(e) => setF({ ...f, reportIds: e.target.value })} />
        </div>
        <div className={`field${bad("evidence") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-ei`}>{t("rewards.nominations.interventionIds")}</label>
          <textarea
            id={`${base}-ei`}
            dir="ltr"
            className="code"
            rows={2}
            value={f.interventionIds}
            onChange={(e) => setF({ ...f, interventionIds: e.target.value })}
          />
        </div>
      </div>
      {touched && errors.length > 0 && (
        <ul className="alert alert--error" role="alert">
          {errors.map((e) => (
            <li key={e}>{t(`rewards.nominations.errors.${e}`)}</li>
          ))}
        </ul>
      )}
      <p className="muted">{t("rewards.nominations.humanDecides")}</p>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={create.isPending}>
          {t("rewards.nominations.submit")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      {create.isError && <MutationError error={create.error} />}
    </form>
  );
}

function NominationCard({ n, manage }: { n: Nomination; manage: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const [asking, setAsking] = useState<"approve" | "reject" | null>(null);
  const decide = useMutation({
    mutationFn: ({ action, reason }: { action: "approve" | "reject"; reason: string }) => api.decideNomination(n.id, action, reason),
    onSuccess: () => {
      setAsking(null);
      void qc.invalidateQueries({ queryKey: p8Keys.nominationsAll });
    },
  });
  const issue = useMutation({
    mutationFn: () => api.issueRewardCertificate({ nomination_id: n.id }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: p8Keys.certificates }),
  });
  return (
    <article className="card nomination" aria-labelledby={`nom-${n.id}`}>
      <header className="suggestion__head">
        <h3 id={`nom-${n.id}`}>
          {t(`rewards.nominationKind.${n.kind}`)} · {n.year}
        </h3>
        <span className={`tag tag--nomination-${n.status}`}>{t(`rewards.nominationStatus.${n.status}`)}</span>
      </header>
      <dl className="fields fields--compact">
        <dt>{t(`rewards.nominations.subject.${n.subject_kind}`)}</dt>
        <dd className="code">{n.subject_label ?? t("rewards.nominations.anonymised")}</dd>
        {n.gouvernorat_code !== null && (
          <>
            <dt>{t("analytics.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(n.gouvernorat_code)}</dd>
          </>
        )}
        <dt>{t("rewards.nominations.evidence")}</dt>
        <dd>
          {t("rewards.nominations.evidenceCount", {
            reports: fmt.number(n.evidence.report_ids.length),
            interventions: fmt.number(n.evidence.intervention_ids.length),
          })}
        </dd>
        <dt>{t("rewards.nominations.proposedAt")}</dt>
        <dd>{fmt.dateTime(n.created_at)}</dd>
        {n.decided_at && (
          <>
            <dt>{t("rewards.nominations.decidedAt")}</dt>
            <dd>
              {fmt.dateTime(n.decided_at)}
              {n.decision_reason && (
                <span className="cell-sub" dir="auto">
                  {n.decision_reason}
                </span>
              )}
            </dd>
          </>
        )}
      </dl>
      <p dir="auto">{n.reason}</p>
      {manage && n.status === "proposed" && (
        <>
          {asking ? (
            <ReasonForm
              label={t(`rewards.nominations.${asking}Reason`)}
              submitLabel={t(`rewards.nominations.${asking}`)}
              required={asking === "reject"}
              pending={decide.isPending}
              error={decide.error}
              onSubmit={(reason) => decide.mutate({ action: asking, reason })}
              onCancel={() => setAsking(null)}
            />
          ) : (
            <div className="actions">
              <button type="button" className="btn btn--primary" onClick={() => setAsking("approve")}>
                {t("rewards.nominations.approve")}
              </button>
              <button type="button" className="btn" onClick={() => setAsking("reject")}>
                {t("rewards.nominations.reject")}
              </button>
            </div>
          )}
          <p className="muted">{t("rewards.nominations.sameReviewer")}</p>
        </>
      )}
      {manage && n.status === "approved" && (
        <div className="actions">
          <button type="button" className="btn" disabled={issue.isPending || issue.isSuccess} onClick={() => issue.mutate()}>
            {issue.isSuccess ? t("rewards.certificates.issued") : t("rewards.certificates.issue")}
          </button>
        </div>
      )}
      {issue.isError && <MutationError error={issue.error} />}
    </article>
  );
}

/** Nominations (FR-C-20): proposed by staff, decided by another staff member, audited. */
export function RewardNominationsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const base = useId();
  const manage = canManageRewards(user?.identity.roles ?? []);
  const [creating, setCreating] = useState(false);
  const [status, setStatus] = useState<NominationStatus | "">("proposed");
  const [year, setYear] = useState<number | null>(null);
  const query = useInfiniteQuery({
    queryKey: p8Keys.nominations(status, year),
    queryFn: ({ pageParam, signal }) => api.nominations({ status, year }, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = query.data?.pages.flatMap((p) => p.items) ?? [];
  const thisYear = new Date().getFullYear();
  return (
    <RewardsFrame title={t("rewards.nominations.title")}>
      {manage && !creating && (
        <p>
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
            {t("rewards.nominations.new")}
          </button>
        </p>
      )}
      {creating && <NominationForm onDone={() => setCreating(false)} />}
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-s`}>{t("rewards.nominations.statusField")}</label>
          <select id={`${base}-s`} value={status} onChange={(e) => setStatus(e.target.value as NominationStatus | "")}>
            <option value="">{t("library.reports.allStatuses")}</option>
            {NOMINATION_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`rewards.nominationStatus.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-y`}>{t("rewards.nominations.year")}</label>
          <select id={`${base}-y`} value={year ?? ""} onChange={(e) => setYear(e.target.value ? Number(e.target.value) : null)}>
            <option value="">{t("rewards.allYears")}</option>
            {[0, 1, 2, 3].map((d) => (
              <option key={d} value={thisYear - d}>
                {thisYear - d}
              </option>
            ))}
          </select>
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("rewards.nominations.none")}</p>}
      <div className="suggestions">
        {rows.map((n) => (
          <NominationCard key={n.id} n={n} manage={manage} />
        ))}
      </div>
      <LoadMore hasNext={query.hasNextPage} loading={query.isFetchingNextPage} onMore={() => void query.fetchNextPage()} />
    </RewardsFrame>
  );
}

// ---------------------------------------------------------------- certificates

/**
 * Fetches the PDF (audited): a pre-signed link is shown as a plain link, a PDF body as a same-origin blob link whose
 * object URL is released afterwards.
 */
function PdfButton({ id, label }: { id: string; label: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const [link, setLink] = useState<{ url: string; blob: boolean } | null>(null);
  const pdf = useMutation({
    mutationFn: () => api.rewardCertificatePdf(id),
    onSuccess: (r) => setLink(r.kind === "link" ? { url: r.url, blob: false } : { url: URL.createObjectURL(r.blob), blob: true }),
  });
  useEffect(
    () => () => {
      if (link?.blob) URL.revokeObjectURL(link.url);
    },
    [link],
  );
  if (link)
    return (
      <a href={link.url} target="_blank" rel="noopener noreferrer" download={link.blob ? `${label}.pdf` : undefined}>
        {t("rewards.certificates.openPdf")}
      </a>
    );
  return (
    <>
      <button
        type="button"
        className="btn btn--small"
        disabled={pdf.isPending}
        onClick={() => pdf.mutate()}
        aria-label={`${t("rewards.certificates.getPdf")} — ${label}`}
      >
        {pdf.isPending ? t("orgs.download.getting") : t("rewards.certificates.getPdf")}
      </button>
      {pdf.isError && <MutationError error={pdf.error} />}
    </>
  );
}

function CertificateRow({ c, manage }: { c: RewardCertificate; manage: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [revoking, setRevoking] = useState(false);
  const revoke = useMutation({
    mutationFn: (reason: string) => api.revokeRewardCertificate(c.id, reason),
    onSuccess: () => {
      setRevoking(false);
      void qc.invalidateQueries({ queryKey: p8Keys.certificates });
    },
  });
  return (
    <tr>
      <th scope="row" className="code" dir="ltr">
        {c.code}
      </th>
      <td dir="auto">{c.distinction}</td>
      <td className="code">{c.subject_label}</td>
      <td>{c.year}</td>
      <td>{fmt.date(c.issued_at)}</td>
      <td>
        {c.revoked_at ? (
          <>
            {t("rewards.certificates.revokedOn", { date: fmt.date(c.revoked_at) })}
            {c.revoked_reason && (
              <span className="cell-sub" dir="auto">
                {c.revoked_reason}
              </span>
            )}
          </>
        ) : (
          t("rewards.certificates.valid")
        )}
      </td>
      <td>
        <div className="ops-row-actions">
          <PdfButton id={c.id} label={c.code} />
          {/^https?:\/\//.test(c.verify_url) && (
            <a href={c.verify_url} target="_blank" rel="noopener noreferrer">
              {t("rewards.certificates.verify")}
            </a>
          )}
          {manage && !c.revoked_at && !revoking && (
            <button type="button" className="btn btn--small btn--ghost" onClick={() => setRevoking(true)}>
              {t("rewards.certificates.revoke")}
            </button>
          )}
        </div>
        {revoking && (
          <ReasonForm
            label={t("rewards.certificates.revokeReason")}
            submitLabel={t("rewards.certificates.revoke")}
            pending={revoke.isPending}
            error={revoke.error}
            onSubmit={(r) => revoke.mutate(r)}
            onCancel={() => setRevoking(false)}
          />
        )}
      </td>
    </tr>
  );
}

export function RewardCertificatesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const manage = canManageRewards(user?.identity.roles ?? []);
  const query = useInfiniteQuery({
    queryKey: p8Keys.certificates,
    queryFn: ({ pageParam, signal }) => api.rewardCertificates({ cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = query.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <RewardsFrame title={t("rewards.certificates.title")}>
      <p className="muted">{t("rewards.certificates.intro")}</p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("rewards.certificates.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("rewards.certificates.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("rewards.certificates.code")}</th>
                <th scope="col">{t("rewards.certificates.distinction")}</th>
                <th scope="col">{t("rewards.pseudonym")}</th>
                <th scope="col">{t("rewards.nominations.year")}</th>
                <th scope="col">{t("rewards.certificates.issuedAt")}</th>
                <th scope="col">{t("rewards.certificates.state")}</th>
                <th scope="col">{t("schedules.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <CertificateRow key={c.id} c={c} manage={manage} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore hasNext={query.hasNextPage} loading={query.isFetchingNextPage} onMore={() => void query.fetchNextPage()} />
    </RewardsFrame>
  );
}

// ---------------------------------------------------------------- leaderboard

/** Leaderboard (pseudonyms only), national or per gouvernorat, per year. */
export function RewardLeaderboardPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const base = useId();
  const national = user?.identity.national ?? false;
  const own = user?.identity.gouvernoratCode ?? null;
  const thisYear = new Date().getFullYear();
  const [scope, setScope] = useState<"national" | "gouvernorat">(national ? "national" : "gouvernorat");
  const [gouvernorat, setGouvernorat] = useState<number | null>(national ? null : own);
  const [year, setYear] = useState(thisYear);
  const effectiveG = scope === "gouvernorat" ? (national ? gouvernorat : own) : null;
  const query = useQuery({
    queryKey: p8Keys.leaderboard(scope, effectiveG, year),
    queryFn: ({ signal }) => api.leaderboard({ scope, gouvernorat: effectiveG, year }, signal),
    enabled: scope === "national" || effectiveG !== null,
  });
  const rows = query.data?.items ?? [];
  return (
    <RewardsFrame title={t("rewards.leaderboard.title")}>
      <p className="muted">{t("rewards.leaderboard.intro")}</p>
      <div className="filters__row">
        {national && (
          <fieldset className="segmented">
            <legend>{t("rewards.leaderboard.scope")}</legend>
            {(["national", "gouvernorat"] as const).map((s) => (
              <label key={s} className="segmented__item">
                <input type="radio" name={`${base}-scope`} checked={scope === s} onChange={() => setScope(s)} />
                <span>{t(`rewards.leaderboard.scopes.${s}`)}</span>
              </label>
            ))}
          </fieldset>
        )}
        {national && scope === "gouvernorat" && (
          <GouvernoratSelect value={gouvernorat} onChange={setGouvernorat} label={t("analytics.gouvernorat")} allLabel={t("rewards.leaderboard.choose")} />
        )}
        <div className="field">
          <label htmlFor={`${base}-y`}>{t("rewards.nominations.year")}</label>
          <select id={`${base}-y`} value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[0, 1, 2, 3].map((d) => (
              <option key={d} value={thisYear - d}>
                {thisYear - d}
              </option>
            ))}
          </select>
        </div>
      </div>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("rewards.leaderboard.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("rewards.leaderboard.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("rewards.leaderboard.rank")}</th>
                <th scope="col">{t("rewards.pseudonym")}</th>
                <th scope="col">{t("rewards.leaderboard.points")}</th>
                <th scope="col">{t("analytics.gouvernorat")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.rank}-${r.pseudonym}`}>
                  <td>{fmt.number(r.rank)}</td>
                  <th scope="row" className="code">
                    {r.pseudonym}
                  </th>
                  <td>{fmt.number(r.points)}</td>
                  <td>{r.gouvernorat_code !== null ? gouvernorats.nameOf(r.gouvernorat_code) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </RewardsFrame>
  );
}
