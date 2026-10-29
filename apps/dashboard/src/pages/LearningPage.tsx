// covers: the training centre (docs/learning.md): the system administrator chooses which trainings run, launches
// them or schedules them, and reads their results; the anonymised report texts are the data set (self-learning).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { Stepper } from "../components/Stepper";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { saveDownload } from "../lib/layersApi";
import {
  LEARNING_SCHEDULE,
  LEARNING_TASKS,
  learningKeys,
  type JobState,
  type LearningSchedule,
  type ScheduleEntry,
  type TaskOverview,
  type TrainingJob,
} from "../lib/learning";
import { p9Keys } from "../lib/phase9Api";
import { canLaunchTraining } from "../lib/roles";

const ACTIVE: readonly JobState[] = ["queued", "running", "waiting_trainer"];

const STATE_TONE: Record<JobState, string> = {
  queued: "tone-slate",
  running: "tone-amber",
  waiting_trainer: "tone-amber",
  done: "tone-green",
  skipped: "tone-slate",
  failed: "tone-red",
};

function Failure({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p role="alert" className="field__error">
      {t(errorMessageKey(error))}
    </p>
  );
}

function StatePill({ state }: { state: JobState }) {
  const { t } = useTranslation();
  return (
    <span className={`pill ${STATE_TONE[state]}`}>
      {t(`learning.state.${state}`)}
    </span>
  );
}

/** The schedule of the trainings, kept in the platform setting `learning.schedule`. */
function useSchedule() {
  const { api } = useServices();
  const settings = useQuery({
    queryKey: p9Keys.settings,
    queryFn: ({ signal }) => api.platformSettings(signal),
  });
  return settings.data?.find((s) => s.key === LEARNING_SCHEDULE);
}

function ScheduleControl({
  task,
  entry,
  editable,
}: {
  task: TaskOverview;
  entry: ScheduleEntry;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const setting = useSchedule();
  const save = useMutation({
    mutationFn: (next: ScheduleEntry) => {
      if (!setting) throw new Error("settings not loaded");
      const value = {
        ...(setting.value as LearningSchedule),
        [task.task]: next,
      };
      return api.savePlatformSetting(LEARNING_SCHEDULE, {
        value,
        version: setting.version,
        reason: t("learning.schedule.reason"),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p9Keys.settings });
      void qc.invalidateQueries({ queryKey: learningKeys.overview });
    },
  });
  const disabled = !editable || !setting || save.isPending;
  return (
    <div className="learning__schedule">
      <label className="checkbox">
        <input
          type="checkbox"
          role="switch"
          checked={entry.enabled}
          disabled={disabled}
          onChange={(e) => save.mutate({ ...entry, enabled: e.target.checked })}
        />
        <span>{t("learning.schedule.enabled")}</span>
      </label>
      <div className="field field--inline">
        <span id={`${id}-every`}>{t("learning.schedule.every")}</span>
        <Stepper
          value={entry.every_days}
          min={1}
          max={90}
          labelledBy={`${id}-every`}
          unit={t("learning.schedule.days")}
          disabled={disabled}
          onChange={(v) => save.mutate({ ...entry, every_days: v })}
        />
      </div>
      <Failure error={save.error} />
    </div>
  );
}

function Percent({ value }: { value: number | undefined }) {
  const fmt = useFormat();
  return (
    <span dir="ltr">{value === undefined ? "—" : fmt.percent(value)}</span>
  );
}

function JobSummary({ job }: { job: TrainingJob }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const r = job.result;
  return (
    <div className="learning__job">
      <p>
        <StatePill state={job.state} /> {t(`learning.trigger.${job.trigger}`)} ·{" "}
        {job.requested_by_name} · {fmt.dateTime(job.requested_at)}
      </p>
      {r.skipped && (
        <p className="muted">
          {t(`learning.skipped.${r.skipped}`, { defaultValue: r.skipped })}
        </p>
      )}
      {r.promoted !== undefined && (
        <p>
          {r.promoted
            ? t("learning.result.promoted", { version: r.version })
            : t("learning.result.kept", { version: r.version })}{" "}
          · {t("learning.result.primary")}: <Percent value={r.primary} />
        </p>
      )}
      {r.train !== undefined && (
        <p className="muted">
          {t("learning.result.samples", {
            train: r.train,
            trainConfirmed: r.train_confirmed ?? 0,
            heldout: r.heldout ?? 0,
            heldoutConfirmed: r.heldout_confirmed ?? 0,
          })}
        </p>
      )}
      {r.images !== undefined && (
        <p className="muted">
          {t("learning.result.images", {
            images: r.images,
            confirmed: r.confirmed ?? 0,
            fire: r.boxes?.fire ?? 0,
            smoke: r.boxes?.smoke ?? 0,
          })}
        </p>
      )}
      {job.state === "waiting_trainer" && (
        <p className="muted">{t("learning.result.waitingTrainer")}</p>
      )}
      {r.trainer && (
        <p>
          {t("learning.result.trainer", {
            model: r.trainer.model,
            by: r.trainer.by,
          })}{" "}
          {Object.entries(r.trainer.metrics).map(([k, v]) => (
            <span key={k} className="tag" dir="ltr">
              {k} {v}
            </span>
          ))}
        </p>
      )}
      {job.error && (
        <p className="field__error">
          {t("learning.result.failed", { error: job.error })}
        </p>
      )}
    </div>
  );
}

function CurrentModel({ task }: { task: TaskOverview }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const m = task.current;
  if (!m) return <p className="muted">{t("learning.model.none")}</p>;
  const scores = m.metrics.model;
  return (
    <div className="learning__model">
      <p>
        <strong>{t("learning.model.version", { version: m.version })}</strong> ·{" "}
        {m.trained_by_name} · {fmt.dateTime(m.trained_at)} ·{" "}
        <span className="pill tone-slate">{t("learning.model.shadow")}</span>
      </p>
      <dl className="learning__figures">
        <div>
          <dt>{t("learning.model.macroF1")}</dt>
          <dd>
            <Percent value={scores?.macro_f1} />
          </dd>
        </div>
        <div>
          <dt>{t("learning.model.accuracy")}</dt>
          <dd>
            <Percent value={scores?.accuracy} />
          </dd>
        </div>
        {m.metrics.baseline && (
          <div>
            <dt>{t("learning.model.baseline")}</dt>
            <dd>
              <Percent value={m.metrics.baseline.macro_f1} />
            </dd>
          </div>
        )}
        <div>
          <dt>{t("learning.model.samples")}</dt>
          <dd>
            {t("learning.model.samplesValue", {
              train: m.train_samples,
              heldout: m.heldout_samples,
            })}
            {m.metrics.evaluated_on && (
              <>
                {" "}
                · {t(`learning.model.evaluatedOn.${m.metrics.evaluated_on}`)}
              </>
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function Candidates({ job }: { job: TrainingJob | null }) {
  const { t } = useTranslation();
  const words = job?.result.candidates ?? [];
  if (words.length === 0)
    return <p className="muted">{t("learning.words.none")}</p>;
  return (
    <div className="table-wrap">
      <table className="table table--compact">
        <caption className="visually-hidden">
          {t("learning.words.caption")}
        </caption>
        <thead>
          <tr>
            <th scope="col">{t("learning.words.word")}</th>
            <th scope="col">{t("learning.words.count")}</th>
            <th scope="col">{t("learning.words.script")}</th>
            <th scope="col">{t("learning.words.category")}</th>
          </tr>
        </thead>
        <tbody>
          {words.slice(0, 50).map((w) => (
            <tr key={w.word}>
              <th scope="row" dir="auto">
                {w.word}
              </th>
              <td>{w.count}</td>
              <td>{t(`learning.words.scripts.${w.script}`)}</td>
              <td>
                {t(`category.${w.category}`, { defaultValue: w.category })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TaskCard({
  task,
  launcher,
}: {
  task: TaskOverview;
  launcher: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const busy = task.last_job !== null && ACTIVE.includes(task.last_job.state);
  const launch = useMutation({
    mutationFn: () => api.launchTraining(task.task),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["learning"] }),
  });
  return (
    <section className="card learning__task" aria-labelledby={`${id}-t`}>
      <div className="learning__head">
        <h2 id={`${id}-t`}>{t(`learning.task.${task.task}.title`)}</h2>
        {task.runner === "trainer" && (
          <span className="pill tone-slate">{t("learning.gpu")}</span>
        )}
      </div>
      <p className="muted">{t(`learning.task.${task.task}.help`)}</p>
      <ScheduleControl task={task} entry={task.schedule} editable={launcher} />
      {launcher && (
        <div className="actions">
          <button
            type="button"
            className="btn btn--primary btn--small"
            disabled={busy || launch.isPending}
            onClick={() => launch.mutate()}
          >
            {busy ? t("learning.launch.busy") : t("learning.launch.start")}
          </button>
        </div>
      )}
      <Failure error={launch.error} />
      <h3>{t("learning.lastJob")}</h3>
      {task.last_job ? (
        <JobSummary job={task.last_job} />
      ) : (
        <p className="muted">{t("learning.noJob")}</p>
      )}
      {task.task === "derja_words" ? (
        <>
          <h3>{t("learning.words.title")}</h3>
          <p className="muted">{t("learning.words.help")}</p>
          <Candidates job={task.last_job} />
        </>
      ) : task.runner === "worker" ? (
        <>
          <h3>{t("learning.model.title")}</h3>
          <CurrentModel task={task} />
        </>
      ) : null}
    </section>
  );
}

function Exports() {
  const { t } = useTranslation();
  const { api } = useServices();
  const download = useMutation({
    mutationFn: (set: "reports" | "fire_smoke") => api.learningDataset(set),
    onSuccess: saveDownload,
  });
  return (
    <div className="actions">
      <button
        type="button"
        className="btn btn--small"
        disabled={download.isPending}
        onClick={() => download.mutate("reports")}
      >
        {t("learning.export.reports")}
      </button>
      <button
        type="button"
        className="btn btn--small"
        disabled={download.isPending}
        onClick={() => download.mutate("fire_smoke")}
      >
        {t("learning.export.fireSmoke")}
      </button>
      <Failure error={download.error} />
    </div>
  );
}

export function LearningPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const launcher = user !== null && canLaunchTraining(user.identity);
  const id = useId();
  const query = useQuery({
    queryKey: learningKeys.overview,
    queryFn: ({ signal }) => api.learning(signal),
    refetchInterval: (q) =>
      q.state.data?.tasks.some(
        (task) => task.last_job && ACTIVE.includes(task.last_job.state),
      )
        ? 15_000
        : false,
  });
  const samples = query.data?.samples;
  const tasks = LEARNING_TASKS.map((key) =>
    query.data?.tasks.find((task) => task.task === key),
  ).filter((task): task is TaskOverview => task !== undefined);
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="science" tone="slate">
          {t("learning.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("learning.intro")}</p>
      {query.isPending && <Loading />}
      {query.isError && (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      )}
      {samples && (
        <section className="card" aria-labelledby={`${id}-data`}>
          <h2 id={`${id}-data`}>{t("learning.data.title")}</h2>
          <p className="muted">{t("learning.data.help")}</p>
          <dl className="learning__figures">
            <div>
              <dt>{t("learning.data.total")}</dt>
              <dd>{samples.total}</dd>
            </div>
            {(["weak", "operator", "commander"] as const).map((origin) => (
              <div key={origin}>
                <dt>{t(`learning.data.origin.${origin}`)}</dt>
                <dd>{samples.by_origin[origin] ?? 0}</dd>
              </div>
            ))}
            <div>
              <dt>{t("learning.data.heldout")}</dt>
              <dd>{samples.by_split.heldout ?? 0}</dd>
            </div>
          </dl>
          {launcher && <Exports />}
        </section>
      )}
      {tasks.map((task) => (
        <TaskCard key={task.task} task={task} launcher={launcher} />
      ))}
    </div>
  );
}
