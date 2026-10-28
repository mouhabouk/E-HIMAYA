// covers: phase L3b (docs/phase-l/design-l3b.md §2, §6): one document of the register with its reference, status and
// dates, the attached file, the summary and text, the key recommendations and their status, the links to other
// documents (repeals, amends, complements), the crisis axes, the versions, and editing, repealing or deleting a draft.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { DocStatus, DocumentForm, Validity } from "../components/RegisterBits";
import { SimBadge } from "../components/crisis/CrisisBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { simText } from "../lib/crisisText";
import { useDebounced, useFormat } from "../lib/hooks";
import {
  DEFAULT_QUERY,
  fileSize,
  RECOMMENDATION_STATUSES,
  registerKeys,
  RELATIONS,
  type DocumentDetail,
  type Recommendation,
  type RecommendationStatus,
  type Relation,
} from "../lib/register";
import { canOpenAxes } from "../lib/roles";

function useInvalidate() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: registerKeys.all });
}

function FilePanel({ d }: { d: DocumentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const x = d.document;
  const open = useMutation({
    mutationFn: () => api.documentFileUrl(x.id),
    onSuccess: (url) => void window.open(url, "_blank", "noopener"),
  });
  const upload = useMutation({ mutationFn: (file: File) => api.uploadDocumentFile(x.id, file, file.name), onSuccess: done });
  const error = open.error ?? upload.error;
  return (
    <section className="card" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t("register.file.title")}</h2>
      {x.file_name ? (
        <p>
          <strong dir="auto">{x.file_name}</strong> <span className="muted">· {fileSize(x.file_size)}</span>
          <br />
          <span className="muted">
            {t("register.file.sha")} <code className="register-sha">{x.file_sha256}</code>
          </span>
        </p>
      ) : (
        <p className="muted">{t("register.file.none")}</p>
      )}
      <div className="form-actions">
        {x.file_name && (
          <button type="button" className="btn" onClick={() => open.mutate()} disabled={open.isPending}>
            {t("register.file.open")}
          </button>
        )}
        {x.can_edit && (
          <>
            <label htmlFor={`${id}-f`} className="visually-hidden">
              {t("register.file.upload")}
            </label>
            <input
              id={`${id}-f`}
              ref={input}
              type="file"
              className="visually-hidden"
              accept=".pdf,.docx,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) upload.mutate(file);
                e.target.value = "";
              }}
            />
            <button type="button" className="btn" onClick={() => input.current?.click()} disabled={upload.isPending}>
              {x.file_name ? t("register.file.replace") : t("register.file.upload")}
            </button>
            <span className="hint">{t("register.file.allowed")}</span>
          </>
        )}
      </div>
      {error && <p role="alert" className="field__error">{t(errorMessageKey(error))}</p>}
    </section>
  );
}

function RecommendationRow({ r, canEdit }: { r: Recommendation; canEdit: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [next, setNext] = useState<RecommendationStatus>(r.status);
  const [reason, setReason] = useState("");
  const save = useMutation({ mutationFn: () => api.recommendationStatus(r.id, next, reason.trim()), onSuccess: done });
  const tone = { proposed: "sky", in_progress: "amber", done: "green", dropped: "slate" }[r.status];
  return (
    <li className={`recommendation${r.overdue ? " is-overdue" : ""}`}>
      <span className="recommendation__no">{r.number}</span>
      <div className="recommendation__body">
        <p dir="auto">{r.body}</p>
        <p className="muted">
          {r.responsible && <>{r.responsible} · </>}
          {r.due_on ? t("register.rec.due", { date: fmt.date(r.due_on) }) : t("register.rec.noDue")}
          {r.overdue && <strong className="recommendation__late"> · {t("register.rec.overdue")}</strong>}
          {r.status_reason && <> · {r.status_reason}</>}
        </p>
      </div>
      <span className={`pill tone-${tone}`}>{t(`register.rec.status.${r.status}`)}</span>
      {canEdit && (
        <div className="recommendation__edit">
          <label htmlFor={`${id}-s`} className="visually-hidden">
            {t("register.rec.changeStatus", { n: r.number })}
          </label>
          <select id={`${id}-s`} value={next} onChange={(e) => setNext(e.target.value as RecommendationStatus)}>
            {RECOMMENDATION_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`register.rec.status.${s}`)}
              </option>
            ))}
          </select>
          {next === "dropped" && (
            <>
              <label htmlFor={`${id}-r`} className="visually-hidden">
                {t("register.rec.reason")}
              </label>
              <input id={`${id}-r`} value={reason} placeholder={t("register.rec.reason")} onChange={(e) => setReason(e.target.value)} />
            </>
          )}
          <button
            type="button"
            className="btn btn--small"
            disabled={save.isPending || next === r.status || (next === "dropped" && reason.trim().length < 5)}
            onClick={() => save.mutate()}
          >
            {t("register.rec.apply")}
          </button>
          {save.isError && <p role="alert" className="field__error">{t(errorMessageKey(save.error))}</p>}
        </div>
      )}
    </li>
  );
}

function Recommendations({ d, canEdit }: { d: DocumentDetail; canEdit: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [body, setBody] = useState("");
  const [responsible, setResponsible] = useState("");
  const [due, setDue] = useState("");
  const add = useMutation({
    mutationFn: () => api.addRecommendation(d.document.id, { body: body.trim(), responsible: responsible.trim(), due_on: due || null }),
    onSuccess: () => {
      setBody("");
      setResponsible("");
      setDue("");
      done();
    },
  });
  return (
    <section className="card" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t("register.rec.title", { open: d.document.recommendations_open, n: d.recommendations.length })}</h2>
      {d.recommendations.length === 0 ? (
        <p className="muted">{t("register.rec.none")}</p>
      ) : (
        <ol className="recommendations">
          {d.recommendations.map((r) => (
            <RecommendationRow key={r.id} r={r} canEdit={canEdit} />
          ))}
        </ol>
      )}
      {canEdit && (
        <form
          className="ops-form register-rec-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (body.trim().length >= 3) add.mutate();
          }}
        >
          <div className="field">
            <label htmlFor={`${id}-b`}>{t("register.rec.body")}</label>
            <input id={`${id}-b`} value={body} dir="auto" maxLength={2000} onChange={(e) => setBody(e.target.value)} />
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor={`${id}-w`}>{t("register.rec.responsible")}</label>
              <input id={`${id}-w`} value={responsible} dir="auto" maxLength={200} onChange={(e) => setResponsible(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor={`${id}-d`}>{t("register.rec.dueOn")}</label>
              <input id={`${id}-d`} type="date" value={due} onChange={(e) => setDue(e.target.value)} />
            </div>
          </div>
          <button type="submit" className="btn btn--small btn--primary" disabled={add.isPending || body.trim().length < 3}>
            {t("register.rec.add")}
          </button>
          {add.isError && <p role="alert" className="field__error">{t(errorMessageKey(add.error))}</p>}
        </form>
      )}
    </section>
  );
}

function LinkForm({ d }: { d: DocumentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [text, setText] = useState("");
  const [target, setTarget] = useState("");
  const [relation, setRelation] = useState<Relation>("complements");
  const q = useDebounced(text.trim(), 350);
  const found = useQuery({
    queryKey: registerKeys.search({ ...DEFAULT_QUERY, q, statuses: [], limit: 8 }),
    queryFn: ({ signal }) => api.registerSearch({ ...DEFAULT_QUERY, q, statuses: [], limit: 8 }, signal),
    enabled: q.length >= 2,
  });
  const options = (found.data?.items ?? []).filter((x) => x.id !== d.document.id);
  const add = useMutation({
    mutationFn: () => api.linkDocument(d.document.id, target, relation),
    onSuccess: () => {
      setText("");
      setTarget("");
      done();
    },
  });
  return (
    <form
      className="ops-form register-link-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (target) add.mutate();
      }}
    >
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-q`}>{t("register.links.find")}</label>
          <input id={`${id}-q`} type="search" dir="auto" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-t`}>{t("register.links.document")}</label>
          <select id={`${id}-t`} value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">—</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.number} · {o.title}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-r`}>{t("register.links.relation")}</label>
          <select id={`${id}-r`} value={relation} onChange={(e) => setRelation(e.target.value as Relation)}>
            {RELATIONS.map((r) => (
              <option key={r} value={r}>
                {t(`register.links.rel.${r}.out`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {relation === "repeals" && <p className="hint">{t("register.links.repealsHint")}</p>}
      <button type="submit" className="btn btn--small" disabled={!target || add.isPending}>
        {t("register.links.add")}
      </button>
      {add.isError && <p role="alert" className="field__error">{t(errorMessageKey(add.error))}</p>}
    </form>
  );
}

function Links({ d }: { d: DocumentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const unlink = useMutation({ mutationFn: (other: string) => api.unlinkDocument(d.document.id, other), onSuccess: done });
  const x = d.document;
  return (
    <section className="card" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t("register.links.title")}</h2>
      {d.links.length === 0 ? (
        <p className="muted">{t("register.links.none")}</p>
      ) : (
        <ul className="doc-refs">
          {d.links.map((l) => (
            <li key={`${l.direction}-${l.id}`}>
              <span className="muted">{t(`register.links.rel.${l.relation}.${l.direction}`)}</span>
              <Link to={`/register/${encodeURIComponent(l.id)}`} dir="auto">
                <bdi dir="ltr">{l.number}</bdi> · {simText(l.title).text}
              </Link>
              <DocStatus status={l.status} />
              {x.can_edit && l.direction === "out" && l.relation !== "repeals" && (
                <button type="button" className="btn btn--small btn--ghost" onClick={() => unlink.mutate(l.id)} disabled={unlink.isPending}>
                  {t("register.links.remove")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {x.can_edit && <LinkForm d={d} />}
    </section>
  );
}

function Revisions({ id: docId }: { id: string }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const [open, setOpen] = useState(false);
  const list = useQuery({ queryKey: registerKeys.revisions(docId), queryFn: ({ signal }) => api.documentRevisions(docId, signal), enabled: open });
  return (
    <section className="card">
      <button type="button" className="btn btn--ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {t("register.revisions.title")}
      </button>
      {open && list.isLoading && <Loading />}
      {open && list.data && (
        <ol className="timeline">
          {list.data.map((r) => (
            <li key={`${r.version}-${r.change}`}>
              <time dateTime={r.created_at}>{fmt.dateTime(r.created_at)}</time>
              <span>
                {t("register.revisions.version", { n: r.version })} · {t(`register.revisions.change.${r.change}`, { defaultValue: r.change })}
              </span>
              {r.created_by_name && <span className="muted">{r.created_by_name}</span>}
              {r.reason && <span className="muted">· {r.reason}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Repeal({ d, onDone }: { d: DocumentDetail; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const id = useId();
  const [reason, setReason] = useState("");
  const repeal = useMutation({
    mutationFn: () => api.repealDocument(d.document.id, reason.trim(), null),
    onSuccess: () => {
      done();
      onDone();
    },
  });
  return (
    <form
      className="card ops-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (reason.trim().length >= 5) repeal.mutate();
      }}
    >
      <div className="field">
        <label htmlFor={`${id}-r`}>{t("register.repeal.reason")}</label>
        <textarea id={`${id}-r`} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
        <p className="hint">{t("register.repeal.hint")}</p>
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--danger" disabled={repeal.isPending || reason.trim().length < 5}>
          {t("register.repeal.confirm")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      {repeal.isError && <p role="alert" className="field__error">{t(errorMessageKey(repeal.error))}</p>}
    </form>
  );
}

export function RegisterDocumentPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const roles = user?.identity.roles ?? [];
  const [mode, setMode] = useState<"view" | "edit" | "repeal">("view");
  const detail = useQuery({ queryKey: registerKeys.document(id), queryFn: ({ signal }) => api.registerDocument(id, signal) });
  const remove = useMutation({
    mutationFn: () => api.deleteDraft(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: registerKeys.all });
      void navigate("/register");
    },
  });
  if (detail.isLoading) return <Loading />;
  if (detail.isError || !detail.data) return <ErrorBox error={detail.error} onRetry={() => void detail.refetch()} />;
  const d = detail.data;
  const x = d.document;
  const writer = x.can_edit;
  return (
    <article className="page register-doc" aria-labelledby="doc-title">
      <p>
        <Link to="/register">{t("register.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="folderOpen" tone="navy" id="doc-title" dir="auto">
          {simText(x.title).text}
        </PageTitle>
        <div className="page-head__actions">
          {writer && mode === "view" && (
            <button type="button" className="btn" onClick={() => setMode("edit")}>
              {t("register.edit")}
            </button>
          )}
          {writer && mode === "view" && (x.status === "in_force" || x.status === "expired") && (
            <button type="button" className="btn btn--danger" onClick={() => setMode("repeal")}>
              {t("register.repeal.action")}
            </button>
          )}
          {writer && x.status === "draft" && (
            <button type="button" className="btn btn--danger" onClick={() => remove.mutate()} disabled={remove.isPending}>
              {t("register.deleteDraft")}
            </button>
          )}
        </div>
      </div>
      <p className="hit__meta register-doc__meta">
        <span className="tag">{t(`register.kind.${x.kind}`)}</span>
        <DocStatus status={x.status} />
        <span>{x.level === "central" ? t("register.level.central") : x.gouvernorat_name}</span>
        <span>
          <bdi dir="ltr">{x.number}</bdi>
        </span>
        {simText(x.title).sim && <SimBadge />}
      </p>
      {remove.isError && <p role="alert" className="field__error">{t(errorMessageKey(remove.error))}</p>}
      {mode === "edit" && <DocumentForm existing={d} canCentral={Boolean(user?.identity.national)} onClose={() => setMode("view")} />}
      {mode === "repeal" && <Repeal d={d} onDone={() => setMode("view")} />}
      {x.status === "repealed" && (
        <p className="alert alert--error">
          {t("register.repealedNote", { reason: x.repeal_reason ?? "" })}{" "}
          {x.repealed_by && <Link to={`/register/${encodeURIComponent(x.repealed_by)}`}>{t("register.openRepealing")}</Link>}
        </p>
      )}
      <div className="register-doc__grid">
        <section className="card" aria-labelledby="doc-facts">
          <h2 id="doc-facts">{t("register.facts")}</h2>
          <dl className="fields fields--compact">
            {x.reference && (
              <>
                <dt>{t("register.field.reference")}</dt>
                <dd dir="auto">{x.reference}</dd>
              </>
            )}
            <dt>{t("register.field.issuer")}</dt>
            <dd dir="auto">{x.issuer}</dd>
            {x.signatory && (
              <>
                <dt>{t("register.field.signatory")}</dt>
                <dd dir="auto">{x.signatory}</dd>
              </>
            )}
            <dt>{t("register.field.issuedOn")}</dt>
            <dd>{fmt.date(x.issued_on)}</dd>
            <dt>{t("register.field.validity")}</dt>
            <dd>
              <Validity d={x} />
            </dd>
            <dt>{t("register.field.access")}</dt>
            <dd>{t(`register.access.${x.access}`)}</dd>
            {x.topics.length > 0 && (
              <>
                <dt>{t("register.field.topics")}</dt>
                <dd>{x.topics.map((k) => t(`register.topic.${k}`, { defaultValue: k })).join(t("common.listSeparator"))}</dd>
              </>
            )}
            <dt>{t("register.field.source")}</dt>
            <dd>{x.source === "axis" ? (x.signed ? t("register.sourceAxisSigned") : t("register.fromAxis")) : t("register.sourceManual")}</dd>
            <dt>{t("register.field.updated")}</dt>
            <dd>
              {fmt.dateTime(x.updated_at)} {x.updated_by_name ? `· ${x.updated_by_name}` : ""} ·{" "}
              {t("register.revisions.version", { n: x.version })}
            </dd>
          </dl>
          {d.axes.length > 0 && (
            <>
              <h3>{t("register.axes")}</h3>
              <ul className="doc-refs">
                {d.axes.map((a) => (
                  <li key={a.id}>
                    {canOpenAxes(roles) ? (
                      <Link to={`/axes/${encodeURIComponent(a.id)}`}>
                        <bdi dir="ltr">{a.number}</bdi> · {simText(a.name).text}
                      </Link>
                    ) : (
                      <span>
                        <bdi dir="ltr">{a.number}</bdi> · {simText(a.name).text}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
        <FilePanel d={d} />
      </div>
      <section className="card" aria-labelledby="doc-text">
        <h2 id="doc-text">{t("register.text")}</h2>
        {x.summary && (
          <p className="register-doc__summary" dir="auto">
            {x.summary}
          </p>
        )}
        {d.body ? (
          <p className="report-text" dir="auto">
            {d.body}
          </p>
        ) : (
          !x.summary && <p className="muted">{t("register.noText")}</p>
        )}
      </section>
      <Recommendations d={d} canEdit={writer} />
      <Links d={d} />
      <Revisions id={x.id} />
    </article>
  );
}
