import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { CategorySelect, Markdown, MutationError, ReasonForm } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { isApiError } from "../lib/api";
import { changed, diffLines } from "../lib/diff";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { p8Keys } from "../lib/phase8Api";
import {
  MEMORY_ACCESS,
  MEMORY_SECTIONS,
  type MemoryAccess,
  type MemoryBody,
  type MemoryEntry,
  type MemorySection,
  type MemoryStatus,
  type MemoryTransition,
} from "../lib/phase8Types";
import { canAuthorMemory } from "../lib/roles";
import { MemoryStatusTag } from "./MemoryListPage";

const LANGS = ["ar", "fr"] as const;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function emptyMemoryBody(own: number | null): MemoryBody {
  const blank = { ar: "", fr: "" };
  return {
    title: { ...blank },
    event_type: "fire",
    started_at: null,
    ended_at: null,
    gouvernorats: own !== null ? [own] : [],
    incident_ids: [],
    sources: [],
    access: own !== null ? "gouvernorat" : "national",
    geometry: null,
    summary: { ...blank },
    strengths: { ...blank },
    weaknesses: { ...blank },
    lessons: { ...blank },
    recommendations: { ...blank },
  };
}

export function bodyOf(e: MemoryEntry): MemoryBody {
  return {
    title: e.title,
    event_type: e.event_type,
    started_at: e.started_at,
    ended_at: e.ended_at,
    gouvernorats: e.gouvernorats,
    incident_ids: e.incident_ids,
    sources: e.sources,
    access: e.access,
    geometry: e.geometry ?? null,
    summary: e.summary,
    strengths: e.strengths,
    weaknesses: e.weaknesses,
    lessons: e.lessons,
    recommendations: e.recommendations,
  };
}

/** Problems that block a save (the API validates again). */
export function memoryErrors(b: MemoryBody): string[] {
  const errors: string[] = [];
  if (!b.title.ar.trim() && !b.title.fr.trim()) errors.push("title");
  if (!b.started_at) errors.push("started_at");
  if (b.started_at && b.ended_at && b.ended_at < b.started_at) errors.push("ended_at");
  if (b.incident_ids.some((id) => !UUID_RE.test(id))) errors.push("incident_ids");
  if (b.sources.some((s) => !s.title.trim() || (s.url && !/^https?:\/\//i.test(s.url)))) errors.push("sources");
  return errors;
}

/** Workflow transitions offered to this user (the API enforces the same rules, and that a reviewer is not the author). */
export function allowedTransitions(e: Pick<MemoryEntry, "status" | "can_edit" | "can_review">): {
  to: MemoryStatus;
  action: "submit" | "publish" | "requestChanges" | "archive" | "restore";
  note: boolean;
}[] {
  const out: ReturnType<typeof allowedTransitions> = [];
  if (e.status === "draft" && e.can_edit) out.push({ to: "in_review", action: "submit", note: false });
  if (e.status === "in_review" && e.can_review) {
    out.push({ to: "published", action: "publish", note: false });
    out.push({ to: "draft", action: "requestChanges", note: true });
  }
  if ((e.status === "published" || e.status === "draft") && e.can_review) out.push({ to: "archived", action: "archive", note: true });
  if (e.status === "archived" && e.can_review) out.push({ to: "draft", action: "restore", note: false });
  return out;
}

/** `datetime-local` value ↔ ISO. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
const fromLocalInput = (v: string) => (v ? new Date(v).toISOString() : null);

function SectionEditor({
  section,
  value,
  onChange,
}: {
  section: MemorySection | "title";
  value: { ar: string; fr: string };
  onChange: (v: { ar: string; fr: string }) => void;
}) {
  const { t } = useTranslation();
  const base = useId();
  const [preview, setPreview] = useState(false);
  const multiline = section !== "title";
  return (
    <fieldset className="md-section">
      <legend>{t(`memory.section.${section}`)}</legend>
      {multiline && (
        <div className="segmented md-section__mode">
          <button type="button" className="btn btn--small btn--ghost" aria-pressed={!preview} onClick={() => setPreview(false)}>
            {t("memory.editor.write")}
          </button>
          <button type="button" className="btn btn--small btn--ghost" aria-pressed={preview} onClick={() => setPreview(true)}>
            {t("memory.editor.preview")}
          </button>
        </div>
      )}
      <div className="md-section__pair">
        {LANGS.map((l) => (
          <div key={l} className="field" lang={l}>
            <label htmlFor={`${base}-${l}`}>{t(`memory.editor.lang.${l}`)}</label>
            {!multiline ? (
              <input
                id={`${base}-${l}`}
                dir={l === "ar" ? "rtl" : "ltr"}
                maxLength={300}
                value={value[l]}
                onChange={(e) => onChange({ ...value, [l]: e.target.value })}
              />
            ) : preview ? (
              <div id={`${base}-${l}`} className="md-preview" aria-live="polite">
                {value[l].trim() ? <Markdown source={value[l]} lang={l} /> : <p className="muted">{t("memory.editor.empty")}</p>}
              </div>
            ) : (
              <textarea
                id={`${base}-${l}`}
                dir={l === "ar" ? "rtl" : "ltr"}
                rows={8}
                maxLength={50_000}
                value={value[l]}
                onChange={(e) => onChange({ ...value, [l]: e.target.value })}
              />
            )}
          </div>
        ))}
      </div>
    </fieldset>
  );
}

function MetaEditor({ body, set, national }: { body: MemoryBody; set: (patch: Partial<MemoryBody>) => void; national: boolean }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const base = useId();
  const [incidentText, setIncidentText] = useState(body.incident_ids.join("\n"));
  const options = national ? gouvernorats.list.map((g) => g.code) : body.gouvernorats;
  return (
    <fieldset className="card memory-meta">
      <legend>{t("memory.editor.meta")}</legend>
      <div className="fields-row">
        <CategorySelect value={body.event_type} onChange={(c) => set({ event_type: c ?? "other" })} label={t("memory.eventType")} />
        <div className="field">
          <label htmlFor={`${base}-start`}>{t("memory.startedAt")}</label>
          <input
            id={`${base}-start`}
            type="datetime-local"
            value={toLocalInput(body.started_at)}
            onChange={(e) => set({ started_at: fromLocalInput(e.target.value) })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-end`}>{t("memory.endedAt")}</label>
          <input
            id={`${base}-end`}
            type="datetime-local"
            value={toLocalInput(body.ended_at)}
            onChange={(e) => set({ ended_at: fromLocalInput(e.target.value) })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-access`}>{t("memory.accessField")}</label>
          <select id={`${base}-access`} value={body.access} onChange={(e) => set({ access: e.target.value as MemoryAccess })}>
            {MEMORY_ACCESS.map((a) => (
              <option key={a} value={a}>
                {t(`memory.access.${a}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <fieldset className="chips gouvernorat-picker">
        <legend>{t("memory.gouvernorats")}</legend>
        {options.map((code) => (
          <label key={code} className="chip-toggle">
            <input
              type="checkbox"
              checked={body.gouvernorats.includes(code)}
              disabled={!national}
              onChange={(e) =>
                set({
                  gouvernorats: e.target.checked
                    ? [...body.gouvernorats, code].sort((a, b) => a - b)
                    : body.gouvernorats.filter((c) => c !== code),
                })
              }
            />
            <span>{gouvernorats.nameOf(code)}</span>
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor={`${base}-inc`}>{t("memory.incidents")}</label>
        <textarea
          id={`${base}-inc`}
          dir="ltr"
          className="code"
          rows={2}
          value={incidentText}
          aria-describedby={`${base}-inc-hint`}
          onChange={(e) => {
            setIncidentText(e.target.value);
            set({ incident_ids: e.target.value.split(/[\s,]+/).filter(Boolean) });
          }}
        />
        <p id={`${base}-inc-hint`} className="muted">
          {t("memory.incidentsHint")}
        </p>
      </div>
      <fieldset className="memory-sources">
        <legend>{t("memory.sources")}</legend>
        {body.sources.map((s, i) => (
          <div key={i} className="fields-row">
            <div className="field">
              <label htmlFor={`${base}-st-${i}`}>{t("memory.sourceTitle")}</label>
              <input
                id={`${base}-st-${i}`}
                dir="auto"
                value={s.title}
                onChange={(e) => set({ sources: body.sources.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)) })}
              />
            </div>
            {s.media_id ? (
              <p className="muted">{t("memory.sourceMedia")}</p>
            ) : (
              <div className="field">
                <label htmlFor={`${base}-su-${i}`}>{t("memory.sourceUrl")}</label>
                <input
                  id={`${base}-su-${i}`}
                  type="url"
                  dir="ltr"
                  value={s.url ?? ""}
                  onChange={(e) => set({ sources: body.sources.map((x, j) => (j === i ? { ...x, url: e.target.value || null } : x)) })}
                />
              </div>
            )}
            <button
              type="button"
              className="btn btn--small btn--ghost"
              onClick={() => set({ sources: body.sources.filter((_, j) => j !== i) })}
            >
              {t("memory.removeSource")}
            </button>
          </div>
        ))}
        <button type="button" className="btn btn--small" onClick={() => set({ sources: [...body.sources, { title: "", url: null, media_id: null }] })}>
          {t("memory.addSource")}
        </button>
      </fieldset>
    </fieldset>
  );
}

function Editor({ entry, onSaved }: { entry: MemoryEntry | null; onSaved: (e: MemoryEntry) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const national = user?.identity.national ?? false;
  const own = user?.identity.gouvernoratCode ?? null;
  const [body, setBody] = useState<MemoryBody>(() => (entry ? bodyOf(entry) : emptyMemoryBody(national ? null : own)));
  const [touched, setTouched] = useState(false);
  const errors = memoryErrors(body);
  const set = (patch: Partial<MemoryBody>) => setBody((b) => ({ ...b, ...patch }));
  const save = useMutation({
    mutationFn: () => (entry ? api.updateMemoryEntry(entry.id, { ...body, version: entry.version }) : api.createMemoryEntry(body)),
    onSuccess: (saved) => {
      qc.setQueryData(p8Keys.memoryEntry(saved.id), saved);
      void qc.invalidateQueries({ queryKey: p8Keys.memoryAll });
      onSaved(saved);
    },
  });
  const conflict = isApiError(save.error) && save.error.code === "version_conflict";
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (errors.length === 0) save.mutate();
  };
  return (
    <form className="memory-editor" onSubmit={submit} noValidate aria-label={t("memory.editor.label")}>
      {entry?.status === "published" && <p className="alert alert--info">{t("memory.editor.publishedNote")}</p>}
      <SectionEditor section="title" value={body.title} onChange={(title) => set({ title })} />
      <MetaEditor body={body} set={set} national={national} />
      {MEMORY_SECTIONS.map((s) => (
        <SectionEditor key={s} section={s} value={body[s]} onChange={(v) => set({ [s]: v })} />
      ))}
      <p className="muted">{t("memory.editor.markdownHelp")}</p>
      {touched && errors.length > 0 && (
        <div className="alert alert--error" role="alert">
          <ul>
            {errors.map((e) => (
              <li key={e}>{t(`memory.editor.errors.${e}`)}</li>
            ))}
          </ul>
        </div>
      )}
      {conflict ? (
        <div className="alert alert--warn" role="alert">
          <p>{t("memory.editor.conflict")}</p>
          <button
            type="button"
            className="btn"
            onClick={() => entry && void qc.invalidateQueries({ queryKey: p8Keys.memoryEntry(entry.id) })}
          >
            {t("memory.editor.reload")}
          </button>
        </div>
      ) : (
        save.isError && <MutationError error={save.error} />
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {save.isPending ? t("ops.working") : entry ? t("memory.editor.save") : t("memory.editor.create")}
        </button>
      </div>
    </form>
  );
}

function ReadView({ entry }: { entry: MemoryEntry }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  return (
    <div className="memory-read">
      <dl className="fields fields--compact">
        <dt>{t("memory.eventType")}</dt>
        <dd>{t(`category.${entry.event_type}`, { defaultValue: entry.event_type })}</dd>
        <dt>{t("memory.period")}</dt>
        <dd>
          {entry.started_at ? fmt.dateTime(entry.started_at) : "—"}
          {entry.ended_at ? ` – ${fmt.dateTime(entry.ended_at)}` : ""}
        </dd>
        <dt>{t("memory.gouvernorats")}</dt>
        <dd>{entry.gouvernorats.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator")) || t("analytics.national")}</dd>
        <dt>{t("memory.accessField")}</dt>
        <dd>{t(`memory.access.${entry.access}`)}</dd>
        {entry.incident_ids.length > 0 && (
          <>
            <dt>{t("memory.incidents")}</dt>
            <dd>
              <ul className="inline-list">
                {entry.incident_ids.map((id) => (
                  <li key={id}>
                    <Link to={`/incidents/${encodeURIComponent(id)}`} className="code" dir="ltr">
                      {id.slice(0, 8)}
                    </Link>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        )}
        <dt>{t("memory.author")}</dt>
        <dd>{entry.author?.name ?? t("memory.unknownPerson")}</dd>
      </dl>
      {MEMORY_SECTIONS.map((s) => (
        <section key={s} className="card md-read" aria-labelledby={`md-${s}`}>
          <h2 id={`md-${s}`}>{t(`memory.section.${s}`)}</h2>
          <div className="md-section__pair">
            {LANGS.map((l) => (
              <div key={l}>
                <h3 className="visually-hidden">{t(`memory.editor.lang.${l}`)}</h3>
                {entry[s][l].trim() ? <Markdown source={entry[s][l]} lang={l} /> : <p className="muted">{t("memory.editor.empty")}</p>}
              </div>
            ))}
          </div>
        </section>
      ))}
      {entry.sources.length > 0 && (
        <section className="card" aria-labelledby="md-sources">
          <h2 id="md-sources">{t("memory.sources")}</h2>
          <ul>
            {entry.sources.map((src, i) => (
              <li key={i} dir="auto">
                {src.url && /^https?:\/\//i.test(src.url) ? (
                  <a href={src.url} target="_blank" rel="noopener noreferrer nofollow">
                    {src.title}
                  </a>
                ) : (
                  src.title
                )}
                {src.media_id && <span className="muted"> · {t("memory.sourceMedia")}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Workflow({ entry }: { entry: MemoryEntry }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [asking, setAsking] = useState<MemoryStatus | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const move = useMutation({
    mutationFn: (b: MemoryTransition) => api.transitionMemoryEntry(entry.id, b),
    onSuccess: (saved) => {
      setAsking(null);
      qc.setQueryData(p8Keys.memoryEntry(saved.id), saved);
      void qc.invalidateQueries({ queryKey: p8Keys.memoryAll });
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteMemoryEntry(entry.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p8Keys.memoryAll });
      void navigate("/memory");
    },
  });
  const transitions = allowedTransitions(entry);
  const pending = transitions.find((x) => x.to === asking);
  const deletable = entry.can_edit && entry.status === "draft" && entry.published_version === null;
  return (
    <section className="card memory-workflow" aria-labelledby="memory-workflow">
      <h2 id="memory-workflow">{t("memory.workflow.title")}</h2>
      <p>
        <MemoryStatusTag status={entry.status} /> · v{entry.version}
        {entry.published_version !== null && entry.published_version !== entry.version && (
          <span className="muted"> · {t("memory.publishedVersion", { v: entry.published_version })}</span>
        )}
      </p>
      <p className="muted">{t("memory.workflow.rule")}</p>
      {entry.reviewers.length > 0 && (
        <ul className="reviews">
          {entry.reviewers.map((r, i) => (
            <li key={`${r.id}-${i}`}>
              <strong>{r.name ?? t("memory.unknownPerson")}</strong> · {t(`memory.workflow.decision.${r.decision}`)} · v{r.version} ·{" "}
              <time dateTime={r.at}>{fmt.dateTime(r.at)}</time>
              {r.note && (
                <span className="cell-sub" dir="auto">
                  {r.note}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {pending?.note ? (
        <ReasonForm
          label={t(`memory.workflow.note.${pending.action}`)}
          submitLabel={t(`memory.workflow.action.${pending.action}`)}
          pending={move.isPending}
          error={move.error}
          onSubmit={(note) => move.mutate({ to: pending.to, note, version: entry.version })}
          onCancel={() => setAsking(null)}
        />
      ) : (
        <div className="actions">
          {transitions.map((x) => (
            <button
              key={x.action}
              type="button"
              className={x.action === "publish" || x.action === "submit" ? "btn btn--primary" : "btn"}
              disabled={move.isPending}
              onClick={() => (x.note ? setAsking(x.to) : move.mutate({ to: x.to, note: null, version: entry.version }))}
            >
              {t(`memory.workflow.action.${x.action}`)}
            </button>
          ))}
          {deletable &&
            (confirmDelete ? (
              <>
                <button type="button" className="btn btn--danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
                  {t("memory.workflow.confirmDelete")}
                </button>
                <button type="button" className="btn" onClick={() => setConfirmDelete(false)}>
                  {t("common.cancel")}
                </button>
              </>
            ) : (
              <button type="button" className="btn btn--ghost" onClick={() => setConfirmDelete(true)}>
                {t("memory.workflow.delete")}
              </button>
            ))}
        </div>
      )}
      {!pending?.note && move.isError && <MutationError error={move.error} />}
      {remove.isError && <MutationError error={remove.error} />}
    </section>
  );
}

/** Text of each diffable field of an entry version. */
function fieldTexts(b: Partial<MemoryBody> | undefined, t: (k: string) => string): { key: string; label: string; text: string }[] {
  if (!b) return [];
  const out: { key: string; label: string; text: string }[] = [];
  for (const l of LANGS) out.push({ key: `title.${l}`, label: `${t("memory.section.title")} (${l})`, text: b.title?.[l] ?? "" });
  out.push({
    key: "meta",
    label: t("memory.editor.meta"),
    text: [
      `event_type: ${b.event_type ?? ""}`,
      `started_at: ${b.started_at ?? ""}`,
      `ended_at: ${b.ended_at ?? ""}`,
      `access: ${b.access ?? ""}`,
      `gouvernorats: ${(b.gouvernorats ?? []).join(", ")}`,
      `incident_ids: ${(b.incident_ids ?? []).join(", ")}`,
      ...(b.sources ?? []).map((s) => `source: ${s.title} ${s.url ?? s.media_id ?? ""}`),
    ].join("\n"),
  });
  for (const s of MEMORY_SECTIONS)
    for (const l of LANGS) out.push({ key: `${s}.${l}`, label: `${t(`memory.section.${s}`)} (${l})`, text: b[s]?.[l] ?? "" });
  return out;
}

function Versions({ entry }: { entry: MemoryEntry }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const base = useId();
  const list = useQuery({
    queryKey: [...p8Keys.memoryVersions(entry.id), entry.version],
    queryFn: ({ signal }) => api.memoryVersions(entry.id, signal),
  });
  const versions = useMemo(() => [...(list.data ?? [])].sort((a, b) => b.version - a.version), [list.data]);
  const [chosen, setPair] = useState<{ a: number; b: number } | null>(null);
  // Default comparison: the previous version against the latest one.
  const pair = chosen ?? (versions.length >= 2 ? { a: versions[1]?.version ?? 1, b: versions[0]?.version ?? 1 } : null);
  const va = useQuery({
    queryKey: p8Keys.memoryVersion(entry.id, pair?.a ?? 0),
    queryFn: ({ signal }) => api.memoryVersion(entry.id, pair?.a ?? 0, signal),
    enabled: pair !== null,
    staleTime: Infinity,
  });
  const vb = useQuery({
    queryKey: p8Keys.memoryVersion(entry.id, pair?.b ?? 0),
    queryFn: ({ signal }) => api.memoryVersion(entry.id, pair?.b ?? 0, signal),
    enabled: pair !== null,
    staleTime: Infinity,
  });
  const diffs = useMemo(() => {
    if (!va.data || !vb.data) return [];
    const before = fieldTexts(va.data.entry, t);
    const after = fieldTexts(vb.data.entry, t);
    return after
      .map((f, i) => ({ ...f, before: before[i]?.text ?? "" }))
      .filter((f) => changed(f.before, f.text))
      .map((f) => ({ key: f.key, label: f.label, ops: diffLines(f.before, f.text) }));
  }, [va.data, vb.data, t]);
  return (
    <section className="card memory-versions" aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{t("memory.versions.title")}</h2>
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {versions.length > 0 && (
        <ol className="versions" reversed>
          {versions.map((v) => (
            <li key={v.version}>
              v{v.version} · {t(`memory.versions.change.${v.change}`)} · {v.created_by?.name ?? t("memory.unknownPerson")} ·{" "}
              <time dateTime={v.created_at}>{fmt.dateTime(v.created_at)}</time>
              {v.note && (
                <span className="cell-sub" dir="auto">
                  {v.note}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
      {versions.length >= 2 && pair && (
        <>
          <div className="fields-row">
            {(["a", "b"] as const).map((k) => (
              <div key={k} className="field">
                <label htmlFor={`${base}-${k}`}>{t(`memory.versions.${k === "a" ? "from" : "to"}`)}</label>
                <select id={`${base}-${k}`} value={pair[k]} onChange={(e) => setPair({ ...pair, [k]: Number(e.target.value) })}>
                  {versions.map((v) => (
                    <option key={v.version} value={v.version}>
                      v{v.version}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          {(va.isPending || vb.isPending) && <Loading />}
          {(va.isError || vb.isError) && <ErrorBox error={va.error ?? vb.error} />}
          {va.data && vb.data && diffs.length === 0 && <p className="muted">{t("memory.versions.same")}</p>}
          {diffs.map((d) => (
            <div key={d.key} className="diff">
              <h3>{d.label}</h3>
              <pre className="diff__body" dir="auto" aria-label={t("memory.versions.diffOf", { field: d.label })}>
                {d.ops.map((op, i) => (
                  <span key={i} className={`diff__line diff__line--${op.kind}`}>
                    <span className="visually-hidden">{t(`memory.versions.op.${op.kind}`)} </span>
                    <span aria-hidden="true">{op.kind === "add" ? "+ " : op.kind === "del" ? "− " : "  "}</span>
                    {op.text || " "}
                    {"\n"}
                  </span>
                ))}
              </pre>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

/** One entry: read view (ar/fr side by side), the editor, the review workflow and the version history with diff. */
export function MemoryEntryPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const navigate = useNavigate();
  const { id } = useParams();
  const isNew = id === undefined || id === "new";
  const [editing, setEditing] = useState(false);
  const query = useQuery({
    queryKey: p8Keys.memoryEntry(id ?? "new"),
    queryFn: ({ signal }) => api.memoryEntry(id ?? "", signal),
    enabled: !isNew,
  });
  if (isNew) {
    if (!canAuthorMemory(user?.identity.roles ?? [])) return <p className="alert alert--error">{t("errors.forbidden")}</p>;
    return (
      <div className="page">
        <p>
          <Link to="/memory">{t("memory.back")}</Link>
        </p>
        <h1>{t("memory.new")}</h1>
        <Editor entry={null} onSaved={(e) => void navigate(`/memory/${encodeURIComponent(e.id)}`, { replace: true })} />
      </div>
    );
  }
  const entry = query.data;
  return (
    <article className="page memory-entry" aria-labelledby="memory-title">
      <p>
        <Link to="/memory">{t("memory.back")}</Link>
      </p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {entry && (
        <>
          <div className="page__head">
            <h1 id="memory-title" dir="auto">
              {localized(entry.title, lang) || t("memory.untitled")}
            </h1>
            <MemoryStatusTag status={entry.status} />
            {entry.can_edit && entry.status !== "in_review" && entry.status !== "archived" && (
              <button type="button" className="btn" aria-pressed={editing} onClick={() => setEditing((v) => !v)}>
                {editing ? t("memory.editor.close") : t("memory.editor.open")}
              </button>
            )}
          </div>
          <Workflow entry={entry} />
          {editing ? (
            <Editor key={entry.version} entry={entry} onSaved={() => setEditing(false)} />
          ) : (
            <ReadView entry={entry} />
          )}
          <Versions entry={entry} />
        </>
      )}
    </article>
  );
}
