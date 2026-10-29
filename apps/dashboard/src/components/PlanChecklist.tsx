// covers: L5 (docs/phase-l/design-l5.md §2.3, AI2): the task list read from the intervention plan, on a crisis axis
// and in a dry run. The local model suggests; the room manager reviews each task and approves; the rooms follow.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  checklistKeys,
  isReading,
  kept,
  MAX_ACTION,
  MAX_SHORT,
  READING_POLL_MS,
  TASK_STATUSES,
  type Checklist,
  type ChecklistOwner,
  type PlanTask,
  type TaskIn,
} from "../lib/checklist";
import { simText } from "../lib/crisisText";
import { useFormat } from "../lib/hooks";
import { ErrorBox, Loading } from "./Feedback";
import { RequiredNote } from "./PhaseASettings";
import { Stepper } from "./Stepper";

const STATUS_TONE = { todo: "slate", doing: "amber", done: "green", not_applicable: "slate" } as const;
/** Up to this many plans are offered as segmented buttons; more as a list. */
const SEGMENTED_PLANS = 4;

function Failure({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p role="alert" className="field__error">
      {t(errorMessageKey(error))}
    </p>
  );
}

/** Pick the plan and ask the local model to read it. */
function ReadForm({ owner, list }: { owner: ChecklistOwner; list: Checklist }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [choice, setChoice] = useState(list.plan?.id ?? list.plans[0]?.id ?? "");
  const read = useMutation({
    mutationFn: () => api.readPlan(owner, choice, list.id ? list.version : null),
    onSuccess: (data) => qc.setQueryData(checklistKeys.one(owner), data),
  });
  if (list.plans.length === 0) return <p className="muted">{t("checklist.noPlan")}</p>;
  const again = list.state === "review" && list.tasks.length > 0;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (choice) read.mutate();
  };
  return (
    <form className="checklist-read" onSubmit={submit} aria-labelledby={`${id}-t`}>
      <p id={`${id}-t`} className="checklist-read__title">
        {t("checklist.read.title")}
      </p>
      {list.plans.length <= SEGMENTED_PLANS ? (
        <fieldset className="segmented">
          <legend className="visually-hidden">{t("checklist.read.plan")}</legend>
          {list.plans.map((p) => (
            <label key={p.id} className="segmented__item">
              <input type="radio" name={`${id}-plan`} checked={choice === p.id} onChange={() => setChoice(p.id)} />
              <span dir="auto">{simText(p.title).text}</span>
            </label>
          ))}
        </fieldset>
      ) : (
        <div className="field">
          <label htmlFor={`${id}-plan`}>{t("checklist.read.plan")}</label>
          <select id={`${id}-plan`} value={choice} onChange={(e) => setChoice(e.target.value)}>
            {list.plans.map((p) => (
              <option key={p.id} value={p.id}>
                {simText(p.title).text}
              </option>
            ))}
          </select>
        </div>
      )}
      {again && <p className="muted">{t("checklist.read.againHelp")}</p>}
      <button type="submit" className="btn btn--primary btn--small" disabled={!choice || read.isPending}>
        {again ? t("checklist.read.again") : t("checklist.read.start")}
      </button>
      <Failure error={read.error} />
    </form>
  );
}

/** The fields of a task, written or corrected by the reviewer. */
function TaskForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
  pending,
  error,
}: {
  initial: TaskIn;
  submitLabel: string;
  onSubmit: (task: TaskIn) => void;
  onCancel?: () => void;
  pending: boolean;
  error: unknown;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [task, setTask] = useState<TaskIn>(initial);
  const [invalid, setInvalid] = useState(false);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const action = task.action.trim();
    if (action.length < 3) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onSubmit({ action, owner: task.owner.trim(), resource: task.resource.trim(), page: task.page });
  };
  return (
    <form className="checklist-form" noValidate onSubmit={submit}>
      <RequiredNote />
      <div className="field">
        <label htmlFor={`${id}-a`}>{t("checklist.task.action")}</label>
        <textarea
          id={`${id}-a`}
          dir="auto"
          required
          rows={2}
          maxLength={MAX_ACTION}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? `${id}-e` : undefined}
          value={task.action}
          onChange={(e) => setTask({ ...task, action: e.target.value })}
        />
        {invalid && (
          <p id={`${id}-e`} role="alert" className="field__error">
            {t("checklist.task.actionRequired")}
          </p>
        )}
      </div>
      <div className="checklist-form__row">
        <div className="field">
          <label htmlFor={`${id}-o`}>{t("checklist.task.owner")}</label>
          <input id={`${id}-o`} dir="auto" maxLength={MAX_SHORT} value={task.owner} onChange={(e) => setTask({ ...task, owner: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-r`}>{t("checklist.task.resource")}</label>
          <input id={`${id}-r`} dir="auto" maxLength={MAX_SHORT} value={task.resource} onChange={(e) => setTask({ ...task, resource: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-p`}>{t("checklist.task.page")}</label>
          <Stepper
            id={`${id}-p`}
            value={task.page}
            min={1}
            max={2000}
            label={t("checklist.task.page")}
            onChange={(page) => setTask({ ...task, page })}
            onClear={() => setTask({ ...task, page: null })}
          />
        </div>
      </div>
      <div className="directive__actions">
        <button type="submit" className="btn btn--primary btn--small" disabled={pending}>
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="btn btn--ghost btn--small" onClick={onCancel}>
            {t("common.cancel")}
          </button>
        )}
      </div>
      <Failure error={error} />
    </form>
  );
}

function Quote({ task }: { task: PlanTask }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (task.origin !== "ai") return null;
  return (
    <div className="checklist-quote">
      {task.quote && (
        <blockquote dir="auto">
          «{task.quote}»
        </blockquote>
      )}
      <p className="muted">
        {task.page !== null && t("checklist.task.onPage", { page: fmt.number(task.page) })}
        {task.quote_found === false && (
          <>
            {" "}
            <span className="pill tone-amber">{t("checklist.task.quoteMissing")}</span>
          </>
        )}
        {task.quote_found === true && (
          <>
            {" "}
            <span className="pill tone-green">{t("checklist.task.quoteFound")}</span>
          </>
        )}
      </p>
    </div>
  );
}

function TaskBody({ task }: { task: PlanTask }) {
  const { t } = useTranslation();
  return (
    <div className="checklist-task__body">
      <p className="checklist-task__action" dir="auto">
        {task.action}
      </p>
      {(task.owner || task.resource) && (
        <p className="muted">
          {task.owner && (
            <>
              {t("checklist.task.owner")}: <bdi>{task.owner}</bdi>
            </>
          )}
          {task.owner && task.resource && " · "}
          {task.resource && (
            <>
              {t("checklist.task.resource")}: <bdi>{task.resource}</bdi>
            </>
          )}
        </p>
      )}
      {task.suggested && typeof task.suggested.action === "string" && (
        <p className="muted">
          {t("checklist.task.suggestedWas")}: <bdi>{task.suggested.action}</bdi>
        </p>
      )}
    </div>
  );
}

/** One task in review: accept, correct or delete what the model suggested. */
function ReviewItem({ owner, task, canReview }: { owner: ChecklistOwner; task: PlanTask; canReview: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const decide = useMutation({
    mutationFn: ({ decision, body }: { decision: "accept" | "edit" | "delete"; body?: TaskIn }) =>
      api.reviewTask(owner, task.id, decision, body),
    onSuccess: (data) => {
      setEditing(false);
      qc.setQueryData(checklistKeys.one(owner), data);
    },
  });
  const deleted = task.review === "deleted";
  return (
    <li className={`checklist-task${deleted ? " is-deleted" : ""}`}>
      <span className={`pill tone-${task.review === "suggested" ? "purple" : deleted ? "slate" : "green"}`}>
        {t(`checklist.review.${task.review}`)}
      </span>
      {editing ? (
        <TaskForm
          initial={{ action: task.action, owner: task.owner, resource: task.resource, page: task.page }}
          submitLabel={t("checklist.task.saveEdit")}
          onSubmit={(body) => decide.mutate({ decision: "edit", body })}
          onCancel={() => setEditing(false)}
          pending={decide.isPending}
          error={decide.error}
        />
      ) : (
        <>
          <TaskBody task={task} />
          <Quote task={task} />
          {canReview && task.review === "suggested" && (
            <div className="directive__actions">
              <button
                type="button"
                className="btn btn--small btn--primary"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ decision: "accept" })}
              >
                {t("checklist.task.accept")}
              </button>
              <button type="button" className="btn btn--small" onClick={() => setEditing(true)}>
                {t("checklist.task.edit")}
              </button>
              <button
                type="button"
                className="btn btn--small btn--ghost"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ decision: "delete" })}
              >
                {t("checklist.task.delete")}
              </button>
            </div>
          )}
          <Failure error={decide.error} />
        </>
      )}
    </li>
  );
}

/** One kept task of the approved list, and its state set with one tap. */
function FollowItem({ owner, task, canFollow }: { owner: ChecklistOwner; task: PlanTask; canFollow: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const id = useId();
  const follow = useMutation({
    mutationFn: (status: PlanTask["status"]) => api.followTask(owner, task.id, status, ""),
    onSuccess: (data) => qc.setQueryData(checklistKeys.one(owner), data),
  });
  return (
    <li className={`checklist-task checklist-task--${task.status}`}>
      <TaskBody task={task} />
      {task.page !== null && <p className="muted">{t("checklist.task.onPage", { page: fmt.number(task.page) })}</p>}
      {canFollow ? (
        <fieldset className="segmented segmented--small">
          <legend className="visually-hidden">{t("checklist.follow.label", { action: task.action })}</legend>
          {TASK_STATUSES.map((s) => (
            <label key={s} className="segmented__item">
              <input
                type="radio"
                name={`${id}-s`}
                checked={task.status === s}
                disabled={follow.isPending}
                onChange={() => follow.mutate(s)}
              />
              <span>{t(`checklist.status.${s}`)}</span>
            </label>
          ))}
        </fieldset>
      ) : (
        <span className={`pill tone-${STATUS_TONE[task.status]}`}>{t(`checklist.status.${task.status}`)}</span>
      )}
      {task.status_at && (
        <p className="muted">
          {fmt.time(task.status_at)}
          {task.status_by_name && ` · ${task.status_by_name}`}
        </p>
      )}
      <Failure error={follow.error} />
    </li>
  );
}

function AddTask({ owner }: { owner: ChecklistOwner }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [round, setRound] = useState(0);
  const add = useMutation({
    mutationFn: (task: TaskIn) => api.addTask(owner, task),
    onSuccess: (data) => {
      qc.setQueryData(checklistKeys.one(owner), data);
      setRound((n) => n + 1);
      setOpen(false);
    },
  });
  if (!open) {
    return (
      <button type="button" className="btn btn--small" onClick={() => setOpen(true)}>
        {t("checklist.task.add")}
      </button>
    );
  }
  return (
    <TaskForm
      key={round}
      initial={{ action: "", owner: "", resource: "", page: null }}
      submitLabel={t("checklist.task.addSave")}
      onSubmit={(task) => add.mutate(task)}
      onCancel={() => setOpen(false)}
      pending={add.isPending}
      error={add.error}
    />
  );
}

function Approve({ owner, list }: { owner: ChecklistOwner; list: Checklist }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const approve = useMutation({
    mutationFn: () => api.approveChecklist(owner, list.version),
    onSuccess: (data) => qc.setQueryData(checklistKeys.one(owner), data),
  });
  const waiting = list.counts.suggested;
  return (
    <div className="checklist-approve">
      <button
        type="button"
        className="btn btn--primary"
        disabled={waiting > 0 || list.counts.kept === 0 || approve.isPending}
        onClick={() => approve.mutate()}
      >
        {t("checklist.approve")}
      </button>
      <p className="muted">
        {waiting > 0 ? t("checklist.waiting", { count: waiting }) : t("checklist.approveHelp")}
      </p>
      <Failure error={approve.error} />
    </div>
  );
}

export function PlanChecklist({ owner }: { owner: ChecklistOwner }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useQuery({
    queryKey: checklistKeys.one(owner),
    queryFn: ({ signal }) => api.checklist(owner, signal),
    refetchInterval: (q) => (isReading(q.state.data) ? READING_POLL_MS : false),
  });
  if (query.isLoading) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;
  const list = query.data;
  if (!list) return null;
  const readable = list.reading_available && list.state !== "approved" && !isReading(list);
  const tasks = list.state === "approved" ? kept(list) : list.tasks;
  const done = list.counts.done + list.counts.not_applicable;
  return (
    <div className="checklist">
      <p className="checklist__notice">
        <span className="tag tag--ai">{t("checklist.aiLabel")}</span> {t("checklist.notice")}
      </p>
      {list.plan && (
        <p className="muted" dir="auto">
          {t("checklist.from", { title: simText(list.plan.title).text })}
          {list.model && ` · ${t("checklist.model", { model: list.model })}`}
          {list.pages !== null &&
            ` · ${t("checklist.pages", { read: fmt.number(list.pages_read ?? 0), total: fmt.number(list.pages) })}`}
        </p>
      )}
      {list.state === null && !list.reading_available && <p className="ops-empty">{t("checklist.none")}</p>}
      {isReading(list) && (
        <p className="alert alert--info" role="status">
          {t("checklist.reading")}
        </p>
      )}
      {list.state === "failed" && (
        <p className="alert alert--error" role="alert">
          {t(`checklist.failure.${list.error ?? "unknown"}`, { defaultValue: t("checklist.failure.unknown") })}
        </p>
      )}
      {readable && <ReadForm owner={owner} list={list} />}
      {list.state === "review" && (
        <>
          {list.tasks.length === 0 && <p className="ops-empty">{t("checklist.noTask")}</p>}
          <ol className="checklist-tasks">
            {tasks.map((task) => (
              <ReviewItem key={task.id} owner={owner} task={task} canReview={list.can_review} />
            ))}
          </ol>
          {list.can_review && (
            <>
              <AddTask owner={owner} />
              <Approve owner={owner} list={list} />
            </>
          )}
        </>
      )}
      {list.state === "approved" && (
        <>
          <p className="checklist__progress">
            <span className="meter" aria-hidden="true">
              <span style={{ inlineSize: `${list.counts.kept ? (done / list.counts.kept) * 100 : 0}%` }} />
            </span>{" "}
            {t("checklist.progress", { done: fmt.number(done), total: fmt.number(list.counts.kept) })}
            {list.approved_by_name && (
              <span className="muted"> · {t("checklist.approvedBy", { name: list.approved_by_name })}</span>
            )}
          </p>
          <ol className="checklist-tasks">
            {tasks.map((task) => (
              <FollowItem key={task.id} owner={owner} task={task} canFollow={list.can_follow} />
            ))}
          </ol>
          {list.can_review && <AddTask owner={owner} />}
        </>
      )}
    </div>
  );
}
