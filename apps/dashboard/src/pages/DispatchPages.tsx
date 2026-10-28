// covers: phase L3b (docs/phase-l/design-l3b.md §8): directives of the centre to every gouvernorat or to some, notices
// of a regional room to the centre about an event, and the threads of replies (one per gouvernorat: it reads its own,
// the centre reads them all), written in a text box or as attached Office, PDF or other files.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import {
  ATTACHMENT_ACCEPT,
  DEFAULT_DISPATCH_QUERY,
  dispatchKeys,
  fileSize,
  MAX_ATTACHMENTS,
  URGENCIES,
  URGENCY_TONE,
  type Attachment,
  type Dispatch,
  type DispatchBody,
  type DispatchDetail,
  type DispatchQuery,
  type Urgency,
} from "../lib/register";

function UrgencyPill({ u }: { u: Urgency }) {
  const { t } = useTranslation();
  return <span className={`pill tone-${URGENCY_TONE[u]}`}>{t(`dispatch.urgency.${u}`)}</span>;
}

/** Picks files to attach (several at once), shown with their size and a remove button. */
function FilePicker({ files, onChange }: { files: File[]; onChange: (f: File[]) => void }) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  return (
    <div className="file-picker">
      <label htmlFor={id} className="visually-hidden">
        {t("dispatch.attach")}
      </label>
      <input
        id={id}
        ref={input}
        type="file"
        multiple
        className="visually-hidden"
        accept={ATTACHMENT_ACCEPT}
        onChange={(e) => {
          const picked = Array.from(e.target.files ?? []);
          onChange([...files, ...picked].slice(0, MAX_ATTACHMENTS));
          e.target.value = "";
        }}
      />
      <button type="button" className="btn btn--small" onClick={() => input.current?.click()} disabled={files.length >= MAX_ATTACHMENTS}>
        {t("dispatch.attach")}
      </button>
      <span className="hint">{t("dispatch.attachHint")}</span>
      {files.length > 0 && (
        <ul className="file-picker__list">
          {files.map((f, n) => (
            <li key={`${f.name}-${n}`}>
              <span dir="auto">{f.name}</span> <span className="muted">{fileSize(f.size)}</span>
              <button
                type="button"
                className="btn btn--small btn--ghost"
                aria-label={t("dispatch.removeFile", { name: f.name })}
                onClick={() => onChange(files.filter((_, i) => i !== n))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Attachments({ items }: { items: Attachment[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const open = useMutation({
    mutationFn: (id: string) => api.attachmentUrl(id),
    onSuccess: (url) => void window.open(url, "_blank", "noopener"),
  });
  if (items.length === 0) return null;
  return (
    <>
      <ul className="attachments">
        {items.map((a) => (
          <li key={a.id}>
            <button type="button" className="link-button" onClick={() => open.mutate(a.id)} disabled={open.isPending} dir="auto">
              {a.file_name}
            </button>
            <span className="muted"> · {fileSize(a.size)}</span>
          </li>
        ))}
      </ul>
      {open.isError && <p role="alert" className="field__error">{t(errorMessageKey(open.error))}</p>}
    </>
  );
}

async function upload(
  api: ReturnType<typeof useServices>["api"],
  dispatchId: string,
  files: File[],
  replyId: string | null,
): Promise<void> {
  for (const f of files) await api.attachToDispatch(dispatchId, f, f.name, replyId);
}

function Compose({ mode, onClose }: { mode: "directive" | "notice"; onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { list } = useGouvernorats();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const id = useId();
  const [f, setF] = useState<DispatchBody>({
    kind: mode,
    audience: "all",
    gouvernorats: [],
    urgency: mode === "notice" ? "flash" : "normal",
    subject: "",
    body: "",
    topics: [],
    reply_required: true,
    reply_due_at: null,
  });
  const [files, setFiles] = useState<File[]>([]);
  const [tried, setTried] = useState(false);
  const send = useMutation({
    mutationFn: async () => {
      const d = await api.sendDispatch({ ...f, subject: f.subject.trim(), body: f.body.trim() });
      await upload(api, d.dispatch.id, files, null);
      return d.dispatch.id;
    },
    onSuccess: (dispatchId) => {
      void qc.invalidateQueries({ queryKey: dispatchKeys.all });
      void navigate(`/register/dispatches/${encodeURIComponent(dispatchId)}`);
    },
  });
  const ok =
    f.subject.trim().length >= 3 &&
    (f.body.trim().length > 0 || files.length > 0) &&
    (f.audience === "all" || f.gouvernorats.length > 0);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (ok) send.mutate();
  };
  return (
    <form className="card ops-form" onSubmit={submit} noValidate aria-labelledby={`${id}-t`}>
      <h2 id={`${id}-t`}>{mode === "directive" ? t("dispatch.newDirective") : t("dispatch.newNotice")}</h2>
      {mode === "directive" && (
        <>
          <div className="segmented" role="radiogroup" aria-label={t("dispatch.audience")}>
            {(["all", "targeted"] as const).map((a) => (
              <label key={a} className="segmented__item">
                <input type="radio" name={`${id}-aud`} checked={f.audience === a} onChange={() => setF({ ...f, audience: a })} />
                <span>{t(`dispatch.audienceOf.${a}`)}</span>
              </label>
            ))}
          </div>
          {f.audience === "targeted" && (
            <fieldset className="chips" aria-invalid={(tried && f.gouvernorats.length === 0) || undefined}>
              <legend>{t("dispatch.gouvernorats")}</legend>
              {list.map((g) => (
                <label key={g.code}>
                  <input
                    type="checkbox"
                    checked={f.gouvernorats.includes(g.code)}
                    onChange={(e) =>
                      setF({
                        ...f,
                        gouvernorats: e.target.checked ? [...f.gouvernorats, g.code] : f.gouvernorats.filter((c) => c !== g.code),
                      })
                    }
                  />
                  {g.name}
                </label>
              ))}
            </fieldset>
          )}
        </>
      )}
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-u`}>{t("dispatch.urgencyLabel")}</label>
          <select id={`${id}-u`} value={f.urgency} onChange={(e) => setF({ ...f, urgency: e.target.value as Urgency })}>
            {URGENCIES.map((u) => (
              <option key={u} value={u}>
                {t(`dispatch.urgency.${u}`)}
              </option>
            ))}
          </select>
        </div>
        {mode === "directive" && (
          <div className="field">
            <label htmlFor={`${id}-due`}>{t("dispatch.dueAt")}</label>
            <input
              id={`${id}-due`}
              type="datetime-local"
              value={f.reply_due_at ? f.reply_due_at.slice(0, 16) : ""}
              onChange={(e) => setF({ ...f, reply_due_at: e.target.value ? new Date(e.target.value).toISOString() : null })}
            />
          </div>
        )}
      </div>
      <div className="field">
        <label htmlFor={`${id}-s`}>{t("dispatch.subject")}</label>
        <input
          id={`${id}-s`}
          value={f.subject}
          dir="auto"
          maxLength={300}
          aria-invalid={(tried && f.subject.trim().length < 3) || undefined}
          onChange={(e) => setF({ ...f, subject: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-b`}>{t("dispatch.body")}</label>
        <textarea id={`${id}-b`} rows={5} dir="auto" value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
      </div>
      <FilePicker files={files} onChange={setFiles} />
      {mode === "directive" && (
        <label className="checkbox">
          <input type="checkbox" checked={f.reply_required} onChange={(e) => setF({ ...f, reply_required: e.target.checked })} />
          {t("dispatch.replyRequired")}
        </label>
      )}
      {tried && !ok && <p role="alert" className="field__error">{t("dispatch.incomplete")}</p>}
      {send.isError && <p role="alert" className="field__error">{t(errorMessageKey(send.error))}</p>}
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={send.isPending}>
          {mode === "directive" ? t("dispatch.sendDirective") : t("dispatch.sendNotice")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function DispatchCard({ d, centre }: { d: Dispatch; centre: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <li className={`card dispatch-card${d.unread ? " is-unread" : ""}${d.urgency === "flash" ? " is-flash" : ""}`}>
      <p className="hit__meta">
        <span className="tag">{t(`dispatch.kind.${d.kind}`)}</span>
        <UrgencyPill u={d.urgency} />
        {d.unread && <span className="pill tone-sky">{t("dispatch.unread")}</span>}
        {d.status === "closed" && <span className="pill tone-slate">{t("dispatch.closed")}</span>}
        {d.overdue && <span className="pill tone-red">{t("dispatch.overdue")}</span>}
        <span>
          <bdi dir="ltr">{d.number}</bdi>
        </span>
        <time dateTime={d.created_at}>{fmt.dateTime(d.created_at)}</time>
      </p>
      <h3>
        <Link to={`/register/dispatches/${encodeURIComponent(d.id)}`} dir="auto">
          {d.subject}
        </Link>
      </h3>
      <p className="muted">
        {d.kind === "notice"
          ? t("dispatch.fromGouvernorat", { name: d.origin_name ?? "" })
          : d.audience === "all"
            ? t("dispatch.audienceOf.all")
            : t("dispatch.toCount", { n: d.targets })}
        {d.created_by_name && <> · {d.created_by_name}</>}
        {d.attachments > 0 && <> · {t("dispatch.files", { n: d.attachments })}</>}
        {centre && d.kind === "directive" && d.reply_required && <> · {t("dispatch.repliedOf", { replied: d.replied, n: d.targets })}</>}
        {!centre && d.kind === "directive" && <> · {d.replied ? t("dispatch.youReplied") : d.reply_required ? t("dispatch.awaitingYou") : t("dispatch.forInfo")}</>}
      </p>
    </li>
  );
}

export function DispatchesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { list } = useGouvernorats();
  const id = useId();
  const [q, setQ] = useState<DispatchQuery>(DEFAULT_DISPATCH_QUERY);
  const [text, setText] = useState("");
  const [compose, setCompose] = useState<"none" | "directive" | "notice">("none");
  const debounced = useDebounced(text, 350);
  const query = { ...q, q: debounced };
  const page = useQuery({
    queryKey: dispatchKeys.list(query),
    queryFn: ({ signal }) => api.dispatches(query, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
  const data = page.data;
  const centre = Boolean(data?.can_direct);
  return (
    <div className="page dispatches-page">
      <div className="page__head">
        <PageTitle icon="campaign" tone="red">
          {t("dispatch.title")}
        </PageTitle>
        <div className="page-head__actions">
          {data?.can_direct && (
            <button type="button" className="btn btn--primary" onClick={() => setCompose("directive")}>
              {t("dispatch.newDirective")}
            </button>
          )}
          {data?.can_notify && (
            <button type="button" className="btn btn--danger" onClick={() => setCompose("notice")}>
              {t("dispatch.newNotice")}
            </button>
          )}
          <Link className="btn" to="/register">
            {t("register.title")}
          </Link>
        </div>
      </div>
      <p className="muted">{t("dispatch.intro")}</p>
      {compose !== "none" && <Compose mode={compose} onClose={() => setCompose("none")} />}
      <div className="segmented" role="radiogroup" aria-label={t("dispatch.box")}>
        {(["inbox", "sent", "all"] as const).map((b) => (
          <label key={b} className="segmented__item">
            <input type="radio" name={`${id}-box`} checked={q.box === b} onChange={() => setQ({ ...q, box: b })} />
            <span>
              {t(`dispatch.boxOf.${b}`)}
              {b === "inbox" && data && data.unread > 0 ? ` (${data.unread})` : ""}
            </span>
          </label>
        ))}
      </div>
      <form role="search" className="filters" onSubmit={(e) => e.preventDefault()}>
        <div className="filters__row">
          <div className="field field--search">
            <label htmlFor={`${id}-q`}>{t("dispatch.search")}</label>
            <input id={`${id}-q`} type="search" dir="auto" value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-u`}>{t("dispatch.urgencyLabel")}</label>
            <select id={`${id}-u`} value={q.urgency ?? ""} onChange={(e) => setQ({ ...q, urgency: (e.target.value || null) as Urgency | null })}>
              <option value="">{t("dispatch.any")}</option>
              {URGENCIES.map((u) => (
                <option key={u} value={u}>
                  {t(`dispatch.urgency.${u}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-st`}>{t("dispatch.state")}</label>
            <select id={`${id}-st`} value={q.state ?? ""} onChange={(e) => setQ({ ...q, state: (e.target.value || null) as DispatchQuery["state"] })}>
              <option value="">{t("dispatch.any")}</option>
              <option value="open">{t("dispatch.open")}</option>
              <option value="closed">{t("dispatch.closed")}</option>
            </select>
          </div>
          {centre && (
            <div className="field">
              <label htmlFor={`${id}-g`}>{t("register.field.gouvernorat")}</label>
              <select id={`${id}-g`} value={q.gouvernorat ?? ""} onChange={(e) => setQ({ ...q, gouvernorat: e.target.value ? Number(e.target.value) : null })}>
                <option value="">{t("register.search.anyGouvernorat")}</option>
                {list.map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field">
            <label htmlFor={`${id}-f`}>{t("register.search.from")}</label>
            <input id={`${id}-f`} type="date" value={q.from ?? ""} onChange={(e) => setQ({ ...q, from: e.target.value || null })} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-to`}>{t("register.search.to")}</label>
            <input id={`${id}-to`} type="date" value={q.to ?? ""} onChange={(e) => setQ({ ...q, to: e.target.value || null })} />
          </div>
        </div>
      </form>
      <p className="muted" role="status" aria-live="polite">
        {page.isFetching ? t("common.loading") : t("dispatch.count", { n: data?.total ?? 0 })}
      </p>
      {page.isPending && <Loading />}
      {page.isError && <ErrorBox error={page.error} onRetry={() => void page.refetch()} />}
      {data && data.items.length === 0 && <p className="card ops-empty">{t("dispatch.none")}</p>}
      <ol className="hits">
        {data?.items.map((d) => (
          <DispatchCard key={d.id} d={d} centre={centre} />
        ))}
      </ol>
    </div>
  );
}

function ReplyBox({ d, gouvernorat, label }: { d: DispatchDetail; gouvernorat: number | null; label: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const send = useMutation({
    mutationFn: async () => {
      const out = await api.replyDispatch(d.dispatch.id, body.trim(), gouvernorat);
      if (out.reply_id) await upload(api, d.dispatch.id, files, out.reply_id);
    },
    onSuccess: () => {
      setBody("");
      setFiles([]);
      void qc.invalidateQueries({ queryKey: dispatchKeys.all });
    },
  });
  const ok = body.trim().length > 0 || files.length > 0;
  return (
    <form
      className="ops-form reply-box"
      onSubmit={(e) => {
        e.preventDefault();
        if (ok) send.mutate();
      }}
    >
      <label htmlFor={`${id}-b`}>{label}</label>
      <textarea id={`${id}-b`} rows={3} dir="auto" value={body} onChange={(e) => setBody(e.target.value)} />
      <FilePicker files={files} onChange={setFiles} />
      <button type="submit" className="btn btn--primary btn--small" disabled={!ok || send.isPending}>
        {t("dispatch.sendReply")}
      </button>
      {send.isError && <p role="alert" className="field__error">{t(errorMessageKey(send.error))}</p>}
    </form>
  );
}

function Thread({ d, thread, centre }: { d: DispatchDetail; thread: DispatchDetail["threads"][number]; centre: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <section className="card thread" aria-label={t("dispatch.threadOf", { name: thread.gouvernorat_name ?? "" })}>
      <h3>{t("dispatch.threadOf", { name: thread.gouvernorat_name ?? "" })}</h3>
      {thread.replies.length === 0 ? (
        <p className="muted">{t("dispatch.noReply")}</p>
      ) : (
        <ol className="thread__list">
          {thread.replies.map((r) => (
            <li key={r.id} className={`thread__msg thread__msg--${r.side}`}>
              <p className="thread__head">
                <strong>{r.side === "centre" ? t("dispatch.centre") : thread.gouvernorat_name}</strong>
                {r.created_by_name && <span className="muted"> · {r.created_by_name}</span>}
                <time className="muted" dateTime={r.created_at}>
                  {" "}
                  · {fmt.dateTime(r.created_at)}
                </time>
              </p>
              {r.body && (
                <p className="report-text" dir="auto">
                  {r.body}
                </p>
              )}
              <Attachments items={r.attachments} />
            </li>
          ))}
        </ol>
      )}
      {d.can_reply && (
        <ReplyBox
          d={d}
          gouvernorat={centre ? thread.gouvernorat_code : null}
          label={centre ? t("dispatch.replyTo", { name: thread.gouvernorat_name ?? "" }) : t("dispatch.yourReply")}
        />
      )}
    </section>
  );
}

export function DispatchPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const qc = useQueryClient();
  const fid = useId();
  const [writeTo, setWriteTo] = useState<number | null>(null);
  const detail = useQuery({ queryKey: dispatchKeys.one(id), queryFn: ({ signal }) => api.dispatch(id, signal), refetchInterval: 30_000 });
  const close = useMutation({
    mutationFn: () => api.closeDispatch(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: dispatchKeys.all }),
  });
  if (detail.isLoading) return <Loading />;
  if (detail.isError || !detail.data) return <ErrorBox error={detail.error} onRetry={() => void detail.refetch()} />;
  const d = detail.data;
  const x = d.dispatch;
  const isCentre = d.viewer_side === "centre";
  const silent = d.targets.filter((tg) => !d.threads.some((th) => th.gouvernorat_code === tg.gouvernorat_code));
  return (
    <article className="page dispatch-page" aria-labelledby="dispatch-title">
      <p>
        <Link to="/register/dispatches">{t("dispatch.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="campaign" tone="red" id="dispatch-title" dir="auto">
          {x.subject}
        </PageTitle>
        {d.can_close && (
          <button type="button" className="btn" onClick={() => close.mutate()} disabled={close.isPending}>
            {t("dispatch.close")}
          </button>
        )}
      </div>
      <p className="hit__meta">
        <span className="tag">{t(`dispatch.kind.${x.kind}`)}</span>
        <UrgencyPill u={x.urgency} />
        {x.status === "closed" && <span className="pill tone-slate">{t("dispatch.closed")}</span>}
        {x.overdue && <span className="pill tone-red">{t("dispatch.overdue")}</span>}
        <span>
          <bdi dir="ltr">{x.number}</bdi>
        </span>
        <span>
          {x.kind === "notice"
            ? t("dispatch.fromGouvernorat", { name: x.origin_name ?? "" })
            : x.audience === "all"
              ? t("dispatch.audienceOf.all")
              : t("dispatch.toCount", { n: x.targets })}
        </span>
        <span>
          {x.created_by_name} · {fmt.dateTime(x.created_at)}
        </span>
        {x.reply_due_at && <span>{t("dispatch.dueOn", { at: fmt.dateTime(x.reply_due_at) })}</span>}
      </p>
      {close.isError && <p role="alert" className="field__error">{t(errorMessageKey(close.error))}</p>}
      <section className="card" aria-labelledby={`${fid}-b`}>
        <h2 id={`${fid}-b`}>{t("dispatch.text")}</h2>
        {x.body ? (
          <p className="report-text" dir="auto">
            {x.body}
          </p>
        ) : (
          <p className="muted">{t("dispatch.noText")}</p>
        )}
        <Attachments items={d.attachments} />
      </section>
      {isCentre && x.kind === "directive" && (
        <section className="card" aria-labelledby={`${fid}-f`}>
          <h2 id={`${fid}-f`}>{t("dispatch.follow", { replied: x.replied, seen: x.seen, n: x.targets })}</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("register.field.gouvernorat")}</th>
                  <th scope="col">{t("dispatch.seen")}</th>
                  <th scope="col">{t("dispatch.replied")}</th>
                </tr>
              </thead>
              <tbody>
                {d.targets.map((tg) => (
                  <tr key={tg.gouvernorat_code}>
                    <th scope="row">{tg.gouvernorat_name}</th>
                    <td>{tg.seen_at ? fmt.dateTime(tg.seen_at) : "—"}</td>
                    <td>
                      {tg.replied_at ? (
                        t("dispatch.repliesN", { n: tg.replies })
                      ) : tg.overdue ? (
                        <span className="pill tone-red">{t("dispatch.overdue")}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <h2>{t("dispatch.replies")}</h2>
      {d.threads.length === 0 && <p className="muted">{t("dispatch.noReply")}</p>}
      {d.threads.map((th) => (
        <Thread key={th.gouvernorat_code} d={d} thread={th} centre={isCentre} />
      ))}
      {isCentre && d.can_reply && silent.length > 0 && (
        <section className="card">
          <label htmlFor={`${fid}-w`}>{t("dispatch.writeTo")}</label>
          <select id={`${fid}-w`} value={writeTo ?? ""} onChange={(e) => setWriteTo(e.target.value ? Number(e.target.value) : null)}>
            <option value="">—</option>
            {silent.map((tg) => (
              <option key={tg.gouvernorat_code} value={tg.gouvernorat_code}>
                {tg.gouvernorat_name}
              </option>
            ))}
          </select>
          {writeTo !== null && (
            <ReplyBox d={d} gouvernorat={writeTo} label={t("dispatch.replyTo", { name: silent.find((s) => s.gouvernorat_code === writeTo)?.gouvernorat_name ?? "" })} />
          )}
        </section>
      )}
    </article>
  );
}
