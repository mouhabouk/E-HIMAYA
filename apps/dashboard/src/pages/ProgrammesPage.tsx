// covers: phase L2 (docs/phase-l/design-l2.md §2.5, §2.7): the seasonal programmes, a new programme, the file import.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { ReasonField } from "../components/Phase9Bits";
import { DiffView, ProblemList, ProgrammeStatusPill } from "../components/ProgrammeBits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { reasonValid } from "../lib/phase9";
import {
  coverage,
  PROGRAMME_CODE,
  PROGRAMME_KINDS,
  programmeKeys,
  totalGaps,
  type ProgrammeBody,
  type ProgrammeImport,
  type ProgrammeKind,
} from "../lib/programmes";

const MAX_FILE = 10 * 1024 * 1024;

function NewProgramme({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = useId();
  const [form, setForm] = useState<ProgrammeBody>({
    code: "",
    kind: "road",
    title: "",
    valid_from: "",
    valid_to: "",
  });
  const [tried, setTried] = useState(false);
  const create = useMutation({
    mutationFn: () =>
      api.createProgramme({
        ...form,
        code: form.code.trim().toUpperCase(),
        title: form.title.trim(),
      }),
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: programmeKeys.all });
      void navigate(`/programmes/${d.programme.id}`);
    },
  });
  const codeOk = PROGRAMME_CODE.test(form.code.trim().toUpperCase());
  const datesOk = Boolean(form.valid_from && form.valid_to && form.valid_from <= form.valid_to);
  const ok = codeOk && form.title.trim().length >= 3 && datesOk;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (ok) create.mutate();
  };
  const set = (patch: Partial<ProgrammeBody>) => setForm((f) => ({ ...f, ...patch }));
  return (
    <form className="card programme-form" aria-labelledby={`${id}-title`} onSubmit={submit} noValidate>
      <h2 id={`${id}-title`}>{t("programmes.new.title")}</h2>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-code`}>{t("programmes.field.code")}</label>
          <input
            id={`${id}-code`}
            dir="ltr"
            value={form.code}
            aria-required="true"
            aria-invalid={(tried && !codeOk) || undefined}
            aria-describedby={`${id}-code-help`}
            onChange={(e) => set({ code: e.target.value })}
          />
          <p id={`${id}-code-help`} className={tried && !codeOk ? "field__error" : "muted"}>
            {t("programmes.new.codeHelp")}
          </p>
        </div>
        <div className="field">
          <label htmlFor={`${id}-kind`}>{t("programmes.field.kind")}</label>
          <select id={`${id}-kind`} value={form.kind} onChange={(e) => set({ kind: e.target.value as ProgrammeKind })}>
            {PROGRAMME_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`programmes.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-name`}>{t("programmes.field.title")}</label>
          <input
            id={`${id}-name`}
            value={form.title}
            maxLength={300}
            aria-required="true"
            aria-invalid={(tried && form.title.trim().length < 3) || undefined}
            onChange={(e) => set({ title: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-season`}>{t("programmes.field.season")}</label>
          <input
            id={`${id}-season`}
            value={form.season ?? ""}
            maxLength={80}
            onChange={(e) => set({ season: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-from`}>{t("programmes.field.valid_from")}</label>
          <input
            id={`${id}-from`}
            type="date"
            value={form.valid_from}
            aria-required="true"
            aria-invalid={(tried && !datesOk) || undefined}
            onChange={(e) => set({ valid_from: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-to`}>{t("programmes.field.valid_to")}</label>
          <input
            id={`${id}-to`}
            type="date"
            value={form.valid_to}
            aria-required="true"
            aria-invalid={(tried && !datesOk) || undefined}
            aria-describedby={`${id}-dates`}
            onChange={(e) => set({ valid_to: e.target.value })}
          />
          {tried && !datesOk && (
            <p id={`${id}-dates`} className="field__error">
              {t("programmes.new.datesHelp")}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor={`${id}-source`}>{t("programmes.field.source_document")}</label>
          <input
            id={`${id}-source`}
            value={form.source_document ?? ""}
            maxLength={300}
            onChange={(e) => set({ source_document: e.target.value })}
          />
        </div>
      </div>
      {create.isError && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(create.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={create.isPending}>
          {t("programmes.new.create")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function ImportPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ProgrammeImport | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const tooLarge = Boolean(file && file.size > MAX_FILE);
  const check = useMutation({
    mutationFn: (f: File) => api.importProgrammes(f, false),
    onSuccess: setPreview,
  });
  const apply = useMutation({
    mutationFn: (f: File) => api.importProgrammes(f, true, reason.trim()),
    onSuccess: (result) => {
      setPreview(result);
      void qc.invalidateQueries({ queryKey: programmeKeys.all });
    },
  });
  const blocked = !preview || preview.errors.length > 0 || preview.applied;
  return (
    <section className="card programme-import" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("programmes.import.title")}</h2>
      <p className="muted">{t("programmes.import.intro")}</p>
      <div className="field">
        <label htmlFor={`${id}-file`}>{t("programmes.import.file")}</label>
        <input
          id={`${id}-file`}
          type="file"
          accept=".xlsx,.csv,.json"
          aria-required="true"
          aria-describedby={`${id}-file-help`}
          aria-invalid={tooLarge || undefined}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setPreview(null);
            check.reset();
            apply.reset();
          }}
        />
        <p id={`${id}-file-help`} className={tooLarge ? "field__error" : "muted"}>
          {t(tooLarge ? "programmes.import.tooLarge" : "programmes.import.fileHelp")}
        </p>
      </div>
      <div className="actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!file || tooLarge || check.isPending}
          onClick={() => file && check.mutate(file)}
        >
          {t("programmes.import.check")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
      {(check.isError || apply.isError) && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(check.error ?? apply.error))}
        </p>
      )}
      {preview && (
        <div className="programme-import__preview" aria-live="polite">
          {preview.applied && (
            <p role="status" className="alert alert--ok">
              {t("programmes.import.applied")}
            </p>
          )}
          <ProblemList title={t("programmes.import.errors")} items={preview.errors} tone="error" />
          <ProblemList title={t("programmes.import.warnings")} items={preview.warnings} tone="warning" />
          <div className="table-wrap">
            <table className="table">
              <caption>
                {t("programmes.import.programmes", {
                  format: preview.format.toUpperCase(),
                })}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{t("programmes.field.code")}</th>
                  <th scope="col">{t("programmes.field.title")}</th>
                  <th scope="col">{t("programmes.import.what")}</th>
                  <th scope="col">{t("programmes.figures.points")}</th>
                  <th scope="col">{t("programmes.figures.unlocated")}</th>
                  <th scope="col">{t("programmes.import.totals")}</th>
                </tr>
              </thead>
              <tbody>
                {preview.programmes.map((p) => {
                  const gaps = totalGaps(p.declared, p.computed);
                  return (
                    <tr key={p.code}>
                      <th scope="row" dir="ltr">
                        {p.code}
                      </th>
                      <td dir="auto">{p.title ?? "—"}</td>
                      <td>
                        {p.exists ? t("programmes.import.newVersion") : t("programmes.import.newDraft")}
                        {p.diff && (
                          <details>
                            <summary>{t("programmes.import.showDiff")}</summary>
                            <DiffView diff={p.diff} />
                          </details>
                        )}
                      </td>
                      <td>{fmt.number(p.points)}</td>
                      <td>{fmt.number(p.unlocated)}</td>
                      <td>
                        {gaps.length === 0
                          ? t("programmes.import.totalsMatch")
                          : gaps
                              .map(([k, stated, computed]) =>
                                t("programmes.import.gap", {
                                  field: t(`programmes.totals.${k}`, {
                                    defaultValue: k,
                                  }),
                                  stated: fmt.number(stated),
                                  computed: fmt.number(computed),
                                }),
                              )
                              .join(t("common.listSeparator"))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!preview.applied && preview.errors.length > 0 && <p className="muted">{t("programmes.import.fixFirst")}</p>}
          {!blocked && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setTried(true);
                if (file && reasonValid(reason)) apply.mutate(file);
              }}
            >
              <ReasonField label={t("programmes.reason")} value={reason} onChange={setReason} showError={tried} />
              <button type="submit" className="btn btn--primary" disabled={apply.isPending}>
                {t("programmes.import.apply")}
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}

export function ProgrammesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [open, setOpen] = useState<"new" | "import" | null>(null);
  const list = useQuery({
    queryKey: programmeKeys.list,
    queryFn: ({ signal }) => api.programmes(signal),
  });
  const items = list.data?.items ?? [];
  return (
    <div className="page programmes-page">
      <PageTitle icon="schedule" tone="orange">
        {t("programmes.title")}
      </PageTitle>
      <p className="muted">{t("programmes.intro")}</p>
      {list.data?.can_create && (
        <div className="actions">
          <button type="button" className="btn btn--primary" onClick={() => setOpen("new")}>
            {t("programmes.new.open")}
          </button>
          <button type="button" className="btn" onClick={() => setOpen("import")}>
            {t("programmes.import.open")}
          </button>
        </div>
      )}
      {open === "new" && <NewProgramme onClose={() => setOpen(null)} />}
      {open === "import" && <ImportPanel onClose={() => setOpen(null)} />}
      {list.isLoading && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && (
        <div className="table-wrap">
          <table className="table">
            <caption>{t("programmes.listCaption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("programmes.field.title")}</th>
                <th scope="col">{t("programmes.field.kind")}</th>
                <th scope="col">{t("programmes.dates")}</th>
                <th scope="col">{t("programmes.field.status")}</th>
                <th scope="col">{t("programmes.figures.points")}</th>
                <th scope="col">{t("programmes.figures.gouvernorats")}</th>
                <th scope="col">{t("programmes.figures.coverage")}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    {t("programmes.empty")}
                  </td>
                </tr>
              )}
              {items.map((p) => {
                const c = coverage(p.figures.lifeguards_planned, p.figures.lifeguards_deployed);
                return (
                  <tr key={p.id}>
                    <th scope="row">
                      <Link to={`/programmes/${p.id}`} dir="auto">
                        {p.title}
                      </Link>
                      <div className="muted" dir="ltr">
                        {p.code} · v{p.version}
                      </div>
                    </th>
                    <td>{t(`programmes.kind.${p.kind}`)}</td>
                    <td>
                      {fmt.date(p.valid_from)} – {fmt.date(p.valid_to)}
                    </td>
                    <td>
                      <ProgrammeStatusPill status={p.status} live={p.live} />
                    </td>
                    <td>
                      {fmt.number(p.figures.points)}
                      {p.figures.unlocated > 0 && (
                        <div className="muted">
                          {t("programmes.unlocatedCount", {
                            count: p.figures.unlocated,
                          })}
                        </div>
                      )}
                    </td>
                    <td>{fmt.number(p.figures.gouvernorats)}</td>
                    <td>
                      {c === null
                        ? "—"
                        : `${fmt.percent(c)} (${fmt.number(p.figures.lifeguards_deployed)}/${fmt.number(p.figures.lifeguards_planned)})`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
