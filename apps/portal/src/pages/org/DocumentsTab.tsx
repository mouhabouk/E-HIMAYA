import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { VersionStatusBadge } from "../../components/Badges";
import { ConfirmDialog, Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { useFormat } from "../../lib/hooks";
import { openPresigned } from "../../lib/openUrl";
import { queryKeys } from "../../lib/portalApi";
import { DOCUMENT_KINDS, type DocumentKind, type DocumentVersion, type OrgDocument } from "../../lib/types";
import { NOTE_MAX_LENGTH, acceptFor } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { Field } from "./RegisterParts";
import { useDocumentUpload } from "./useDocumentUpload";

const PENDING = new Set(["uploading", "verifying"]);

function DownloadButton({ docId, version, filename }: { docId: string; version: number; filename: string }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const [fallback, setFallback] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: () => openPresigned(() => api.downloadUrl(org.id, docId, version)),
    onSuccess: (url) => setFallback(url),
  });
  return (
    <span className="download">
      <button
        type="button"
        className="btn btn--small"
        disabled={open.isPending}
        onClick={() => open.mutate()}
        aria-label={t("documents.downloadNamed", { name: filename, version })}
      >
        {t("documents.download")}
      </button>
      {fallback && (
        <a href={fallback} target="_blank" rel="noopener noreferrer">
          {t("documents.downloadLink")}
        </a>
      )}
      {open.isError && <ErrorBox error={open.error} />}
    </span>
  );
}

function Versions({ doc }: { doc: OrgDocument }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useQuery({
    queryKey: queryKeys.versions(org.id, doc.id),
    queryFn: ({ signal }) => api.versions(org.id, doc.id, signal),
    // Follow the server-side verification of a fresh upload.
    refetchInterval: (q) => ((q.state.data ?? []).some((v) => PENDING.has(v.status)) ? 3000 : false),
  });
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;
  if (query.data.length === 0) return <p className="muted">{t("documents.noVersions")}</p>;
  return (
    <div className="table-wrap">
      <table className="table table--compact">
        <caption className="visually-hidden">{t("documents.historyOf", { title: doc.title })}</caption>
        <thead>
          <tr>
            <th scope="col">{t("documents.version")}</th>
            <th scope="col">{t("documents.file")}</th>
            <th scope="col">{t("documents.status")}</th>
            <th scope="col">{t("documents.uploaded")}</th>
            <th scope="col">{t("documents.note")}</th>
            <th scope="col">{t("documents.sha256")}</th>
            <th scope="col">{t("common.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {query.data.map((v: DocumentVersion) => (
            <tr key={v.version}>
              <td>{t("documents.vN", { n: v.version })}</td>
              <td>
                <span dir="auto">{v.filename}</span>
                <div className="muted">{fmt.bytes(v.bytes)}</div>
              </td>
              <td>
                <VersionStatusBadge status={v.status} />
              </td>
              <td>
                {fmt.dateTime(v.uploaded_at)}
                {v.uploaded_by && <div className="muted">{v.uploaded_by}</div>}
              </td>
              <td>{v.note ?? "—"}</td>
              <td>
                <span className="hash" title={v.sha256}>
                  {v.sha256.slice(0, 16)}…
                </span>
              </td>
              <td>{v.status === "stored" && <DownloadButton docId={doc.id} version={v.version} filename={v.filename} />}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UploadPanel({ doc, onDone }: { doc: OrgDocument; onDone: () => void }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const fmt = useFormat();
  const id = useId();
  const { state, start, pause, resume, cancel } = useDocumentUpload(org.id, doc);
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const busy = state.phase === "hashing" || state.phase === "uploading";

  function submit(e: SubmitEvent) {
    e.preventDefault();
    if (file) void start(file, note);
  }

  const fraction =
    state.phase === "hashing"
      ? state.total
        ? state.done / state.total
        : 1
      : "sent" in state && state.total
        ? state.sent / state.total
        : 0;

  return (
    <form className="upload" onSubmit={submit} aria-label={t("documents.uploadFor", { title: doc.title })}>
      <div className="form-grid">
        <Field id={`${id}-file`} label={t("documents.chooseFile")} hint={t(doc.kind === "safety_plan" ? "documents.typesPlan" : "documents.typesPdf")}>
          <input
            id={`${id}-file`}
            type="file"
            accept={acceptFor(doc.kind)}
            disabled={busy || state.phase === "paused"}
            aria-describedby={`${id}-file-hint`}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>
        <Field id={`${id}-note`} label={t("documents.note")} hint={t("documents.noteHint", { n: NOTE_MAX_LENGTH })}>
          <input
            id={`${id}-note`}
            maxLength={NOTE_MAX_LENGTH}
            value={note}
            disabled={busy}
            aria-describedby={`${id}-note-hint`}
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>
      </div>
      <div aria-live="polite" className="upload__status">
        {state.phase !== "idle" && state.phase !== "sent" && (
          <>
            <progress max={1} value={fraction} aria-label={t("documents.progress")} />
            <span>
              {state.phase === "hashing"
                ? t("documents.hashing", { p: fmt.percent(fraction) })
                : state.phase === "paused"
                  ? t("documents.paused", { p: fmt.percent(fraction) })
                  : state.phase === "uploading"
                    ? t("documents.uploading", { p: fmt.percent(fraction), sent: fmt.bytes(state.sent), total: fmt.bytes(state.total) })
                    : null}
            </span>
          </>
        )}
        {state.phase === "error" && <ErrorBox error={state.error} />}
        {state.phase === "sent" && <p className="alert alert--ok">{t("documents.sent")}</p>}
      </div>
      <div className="actions">
        {(state.phase === "idle" || state.phase === "sent" || (state.phase === "error" && !state.canResume)) && (
          <button type="submit" className="btn btn--primary" disabled={!file}>
            {t("documents.upload")}
          </button>
        )}
        {busy && (
          <button type="button" className="btn" onClick={pause}>
            {t("documents.pause")}
          </button>
        )}
        {state.phase === "paused" && (
          <button type="button" className="btn btn--primary" onClick={resume}>
            {t("documents.resume")}
          </button>
        )}
        {state.phase === "error" && state.canResume && (
          <button type="button" className="btn btn--primary" onClick={resume}>
            {t("common.retry")}
          </button>
        )}
        {(state.phase === "paused" || state.phase === "error" || busy) && (
          <button type="button" className="btn" onClick={cancel}>
            {t("common.cancel")}
          </button>
        )}
        {(state.phase === "idle" || state.phase === "sent") && (
          <button type="button" className="btn btn--ghost" onClick={onDone}>
            {t("common.close")}
          </button>
        )}
      </div>
    </form>
  );
}

function DocumentItem({ doc }: { doc: OrgDocument }) {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const [panel, setPanel] = useState<"none" | "upload" | "history">("none");
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [title, setTitle] = useState(doc.title);
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.documents(org.id) });
  const rename = useMutation({ mutationFn: () => api.renameDocument(org.id, doc.id, title.trim()), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: () => api.deleteDocument(org.id, doc.id),
    onSuccess: async () => {
      await refresh();
      void queryClient.invalidateQueries({ queryKey: queryKeys.org(org.id), exact: true });
    },
  });
  const v = doc.current_version;

  return (
    <li className="doc">
      <div className="doc__head">
        <h4 dir="auto">{doc.title}</h4>
        {v ? <VersionStatusBadge status={v.status} /> : <span className="muted">{t("documents.noStoredVersion")}</span>}
      </div>
      {v && (
        <p className="muted doc__meta">
          {t("documents.current", { n: v.version, file: v.filename, size: fmt.bytes(v.bytes), date: fmt.dateTime(v.uploaded_at) })}
          {v.uploaded_by && ` — ${v.uploaded_by}`}
          {v.note && ` — ${v.note}`}
        </p>
      )}
      <div className="actions">
        {can("uploadDocuments") && (
          <button type="button" className="btn btn--small btn--primary" aria-expanded={panel === "upload"} onClick={() => setPanel(panel === "upload" ? "none" : "upload")}>
            {t("documents.newVersion")}
          </button>
        )}
        <button type="button" className="btn btn--small" aria-expanded={panel === "history"} onClick={() => setPanel(panel === "history" ? "none" : "history")}>
          {t("documents.history", { n: doc.versions_count })}
        </button>
        {v?.status === "stored" && <DownloadButton docId={doc.id} version={v.version} filename={v.filename} />}
        {can("uploadDocuments") && (
          <button type="button" className="btn btn--small" onClick={() => setRenaming(true)}>
            {t("documents.rename")}
          </button>
        )}
        {can("deleteDocuments") && (
          <button type="button" className="btn btn--small btn--danger-ghost" onClick={() => setDeleting(true)}>
            {t("common.delete")}
          </button>
        )}
      </div>
      {panel === "upload" && <UploadPanel doc={doc} onDone={() => setPanel("none")} />}
      {panel === "history" && <Versions doc={doc} />}
      {renaming && (
        <Dialog title={t("documents.rename")} onClose={() => setRenaming(false)}>
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault();
              if (title.trim()) rename.mutate(undefined, { onSuccess: () => setRenaming(false) });
            }}
          >
            <Field id={`rename-${doc.id}`} label={t("documents.title")} required>
              <input id={`rename-${doc.id}`} value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            {rename.isError && <ErrorBox error={rename.error} />}
            <div className="actions actions--end">
              <button type="button" className="btn" onClick={() => setRenaming(false)}>
                {t("common.cancel")}
              </button>
              <button type="submit" className="btn btn--primary" disabled={rename.isPending}>
                {t("common.save")}
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {deleting && (
        <ConfirmDialog
          title={t("common.confirmDeleteTitle")}
          body={t("documents.confirmDelete", { title: doc.title })}
          confirmLabel={t("common.delete")}
          danger
          busy={remove.isPending}
          onConfirm={() => remove.mutate(undefined, { onSuccess: () => setDeleting(false) })}
          onClose={() => {
            remove.reset();
            setDeleting(false);
          }}
        >
          {remove.isError && <ErrorBox error={remove.error} />}
        </ConfirmDialog>
      )}
    </li>
  );
}

function NewDocumentForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<DocumentKind>("safety_file");
  const [title, setTitle] = useState("");
  const create = useMutation({
    mutationFn: () => api.createDocument(org.id, kind, title.trim()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.documents(org.id) });
      onClose();
    },
  });
  return (
    <Dialog title={t("documents.newTitle")} onClose={onClose}>
      <form
        className="form"
        onSubmit={(e: SubmitEvent) => {
          e.preventDefault();
          if (title.trim()) create.mutate();
        }}
      >
        <p className="muted">{t("documents.newHelp")}</p>
        <div className="form-grid">
          <Field id="doc-kind" label={t("documents.kind")}>
            <select id="doc-kind" value={kind} onChange={(e) => setKind(e.target.value as DocumentKind)}>
              {DOCUMENT_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`documentKinds.${k}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="doc-title" label={t("documents.title")} required>
            <input id="doc-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
        </div>
        {create.isError && <ErrorBox error={create.error} />}
        <div className="actions actions--end">
          <button type="button" className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn btn--primary" disabled={create.isPending || !title.trim()}>
            {t("documents.create")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/** Documents and versions (FR-B-004): safety file, safety plan, safety data sheets and others. */
export function DocumentsTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const [creating, setCreating] = useState(false);
  const query = useQuery({
    queryKey: queryKeys.documents(org.id),
    queryFn: ({ signal }) => api.documents(org.id, signal),
  });
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;

  return (
    <section className="card" aria-labelledby="documents-title">
      <div className="section-head">
        <h2 id="documents-title">{t("documents.sectionTitle")}</h2>
        {can("uploadDocuments") && (
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
            {t("documents.new")}
          </button>
        )}
      </div>
      <p className="muted">{t("documents.help")}</p>
      <BlockedNote action="uploadDocuments" />
      {DOCUMENT_KINDS.map((kind) => {
        const docs = query.data.filter((d) => d.kind === kind);
        return (
          <section key={kind} className="doc-group" aria-labelledby={`dk-${kind}`}>
            <h3 id={`dk-${kind}`}>{t(`documentKinds.${kind}`)}</h3>
            {docs.length === 0 ? (
              <p className="empty">{t("documents.noneOfKind")}</p>
            ) : (
              <ul className="docs">
                {docs.map((d) => (
                  <DocumentItem key={d.id} doc={d} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {creating && <NewDocumentForm onClose={() => setCreating(false)} />}
    </section>
  );
}
