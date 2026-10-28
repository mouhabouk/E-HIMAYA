// covers: phase L3b (docs/phase-l/design-l3b.md §2, §6): pieces shared by the register pages, the axis and the command
// screens: the status pill, the document card and the form that records or edits a document.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { simText } from "../lib/crisisText";
import { useFormat, useGouvernorats } from "../lib/hooks";
import {
  DOCUMENT_ACCESS,
  DOCUMENT_KINDS,
  registerKeys,
  STATUS_TONE,
  TOPICS,
  type DocumentBody,
  type DocumentDetail,
  type DocumentStatus,
  type RegisterDocument,
} from "../lib/register";
import { Excerpt } from "./Phase8Bits";
import { SimBadge } from "./crisis/CrisisBits";

export function DocStatus({ status }: { status: DocumentStatus }) {
  const { t } = useTranslation();
  return <span className={`pill tone-${STATUS_TONE[status]}`}>{t(`register.status.${status}`)}</span>;
}

/** "From 15/03/2026 to 30/09/2026", "Since 15/03/2026". */
export function Validity({ d }: { d: Pick<RegisterDocument, "issued_on" | "effective_from" | "effective_to"> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const from = fmt.date(d.effective_from ?? d.issued_on);
  return <>{d.effective_to ? t("register.validity.between", { from, to: fmt.date(d.effective_to) }) : t("register.validity.since", { from })}</>;
}

export function DocumentCard({ d }: { d: RegisterDocument }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <li className={`card register-card register-card--${d.status}`}>
      <p className="hit__meta">
        <span className="tag">{t(`register.kind.${d.kind}`)}</span>
        <DocStatus status={d.status} />
        <span>{d.level === "central" ? t("register.level.central") : d.gouvernorat_name}</span>
        <span className="register-card__no">
          <bdi dir="ltr">{d.number}</bdi>
        </span>
        {simText(d.title).sim && <SimBadge />}
      </p>
      <h3>
        <Link to={`/register/${encodeURIComponent(d.id)}`} dir="auto">
          {simText(d.title).text}
        </Link>
      </h3>
      {d.reference && (
        <p className="register-card__ref">
          <bdi>{d.reference}</bdi>
        </p>
      )}
      {d.excerpt ? <Excerpt text={d.excerpt} /> : d.summary && <p className="register-card__summary">{simText(d.summary).text}</p>}
      <p className="muted register-card__foot">
        {d.issuer} · {t("register.issuedOn", { date: fmt.date(d.issued_on) })} · <Validity d={d} />
        {d.file_name && <> · {t("register.hasFile")}</>}
        {d.recommendations > 0 && <> · {t("register.recommendationsOpen", { open: d.recommendations_open, n: d.recommendations })}</>}
        {d.source === "axis" && <> · {t("register.fromAxis")}</>}
      </p>
    </li>
  );
}

/** A plain list of documents with their status (axis, command screens, links). */
export function DocumentRefs({ items }: { items: { id: string; number: string; title: string; kind: string; status: DocumentStatus }[] }) {
  const { t } = useTranslation();
  return (
    <ul className="doc-refs">
      {items.map((d) => (
        <li key={d.id}>
          <span className="tag">{t(`register.kind.${d.kind}`)}</span>
          <Link to={`/register/${encodeURIComponent(d.id)}`} dir="auto">
            {simText(d.title).text}
          </Link>
          <DocStatus status={d.status} />
        </li>
      ))}
    </ul>
  );
}

const today = () => new Date().toISOString().slice(0, 10);

function emptyBody(gouvernorat: number | null, national: boolean): DocumentBody {
  return {
    reference: "",
    kind: "plan",
    level: national ? "central" : "regional",
    gouvernorat_code: national ? null : gouvernorat,
    issuer: "",
    signatory: "",
    title: "",
    summary: "",
    body: "",
    topics: [],
    issued_on: today(),
    effective_from: null,
    effective_to: null,
    access: "all",
    axis_ids: [],
    publish: true,
  };
}

function fromDetail(d: DocumentDetail): DocumentBody {
  const x = d.document;
  return {
    reference: x.reference,
    kind: x.kind,
    level: x.level,
    gouvernorat_code: x.gouvernorat_code,
    issuer: x.issuer,
    signatory: x.signatory,
    title: x.title,
    summary: x.summary,
    body: d.body,
    topics: x.topics,
    issued_on: x.issued_on,
    effective_from: x.effective_from,
    effective_to: x.effective_to,
    access: x.access,
    axis_ids: d.axes.map((a) => a.id),
    publish: x.status === "draft" ? false : true,
  };
}

/** Records a document (``existing`` absent) or saves a new version of one, with the reason. */
export function DocumentForm({ existing, canCentral, onClose }: { existing?: DocumentDetail; canCentral: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const { list } = useGouvernorats();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const id = useId();
  const home = user?.identity.gouvernoratCode ?? null;
  const [f, setF] = useState<DocumentBody>(() => (existing ? fromDetail(existing) : emptyBody(home, canCentral)));
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const set = (patch: Partial<DocumentBody>) => setF((x) => ({ ...x, ...patch }));
  const save = useMutation({
    mutationFn: (publish: boolean) => {
      const body = { ...f, publish, effective_from: f.effective_from || null, effective_to: f.effective_to || null };
      return existing
        ? api.updateDocument(existing.document.id, { ...body, version: existing.document.version, reason: reason.trim() })
        : api.createDocument(body);
    },
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: registerKeys.all });
      if (existing) onClose();
      else void navigate(`/register/${encodeURIComponent(d.document.id)}`);
    },
  });
  const problems = {
    title: f.title.trim().length < 3,
    issuer: f.issuer.trim().length < 2,
    gouvernorat: f.level === "regional" && f.gouvernorat_code === null,
    end: f.kind === "temporary_instruction" && !f.effective_to,
    order: Boolean(f.effective_to && f.effective_to < (f.effective_from || f.issued_on)),
    reason: Boolean(existing) && reason.trim().length < 5,
  };
  const ok = !Object.values(problems).some(Boolean) && Boolean(f.issued_on);
  const submit = (publish: boolean) => (e?: SyntheticEvent) => {
    e?.preventDefault();
    setTried(true);
    if (ok) save.mutate(publish);
  };
  const draft = !existing || existing.document.status === "draft";
  const invalid = (k: keyof typeof problems) => (tried && problems[k]) || undefined;
  return (
    <form className="card ops-form register-form" onSubmit={submit(true)} noValidate aria-labelledby={`${id}-t`}>
      <h2 id={`${id}-t`}>{existing ? t("register.form.edit", { number: existing.document.number }) : t("register.form.new")}</h2>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-k`}>{t("register.field.kind")}</label>
          <select id={`${id}-k`} value={f.kind} onChange={(e) => set({ kind: e.target.value as DocumentBody["kind"] })}>
            {DOCUMENT_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`register.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-l`}>{t("register.field.level")}</label>
          <select
            id={`${id}-l`}
            value={f.level}
            disabled={!canCentral}
            onChange={(e) =>
              e.target.value === "central"
                ? set({ level: "central", gouvernorat_code: null })
                : set({ level: "regional", gouvernorat_code: home })
            }
          >
            <option value="central">{t("register.level.central")}</option>
            <option value="regional">{t("register.level.regional")}</option>
          </select>
        </div>
        {f.level === "regional" && (
          <div className="field">
            <label htmlFor={`${id}-g`}>{t("register.field.gouvernorat")}</label>
            <select
              id={`${id}-g`}
              value={f.gouvernorat_code ?? ""}
              disabled={!canCentral}
              aria-invalid={invalid("gouvernorat")}
              onChange={(e) => set({ gouvernorat_code: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">—</option>
              {list.map((g) => (
                <option key={g.code} value={g.code}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="field">
          <label htmlFor={`${id}-a`}>{t("register.field.access")}</label>
          <select id={`${id}-a`} value={f.access} onChange={(e) => set({ access: e.target.value as DocumentBody["access"] })}>
            {DOCUMENT_ACCESS.map((a) => (
              <option key={a} value={a}>
                {t(`register.access.${a}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-ti`}>{t("register.field.title")}</label>
        <input id={`${id}-ti`} value={f.title} dir="auto" maxLength={300} aria-invalid={invalid("title")} onChange={(e) => set({ title: e.target.value })} />
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-r`}>{t("register.field.reference")}</label>
          <input
            id={`${id}-r`}
            value={f.reference}
            dir="auto"
            maxLength={300}
            placeholder={t("register.field.referencePlaceholder")}
            onChange={(e) => set({ reference: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-is`}>{t("register.field.issuer")}</label>
          <input
            id={`${id}-is`}
            value={f.issuer}
            dir="auto"
            maxLength={200}
            placeholder={t("register.field.issuerPlaceholder")}
            aria-invalid={invalid("issuer")}
            onChange={(e) => set({ issuer: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-si`}>{t("register.field.signatory")}</label>
          <input id={`${id}-si`} value={f.signatory} dir="auto" maxLength={200} onChange={(e) => set({ signatory: e.target.value })} />
        </div>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-d1`}>{t("register.field.issuedOn")}</label>
          <input id={`${id}-d1`} type="date" value={f.issued_on} onChange={(e) => set({ issued_on: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-d2`}>{t("register.field.effectiveFrom")}</label>
          <input id={`${id}-d2`} type="date" value={f.effective_from ?? ""} onChange={(e) => set({ effective_from: e.target.value || null })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-d3`}>
            {t("register.field.effectiveTo")}
            {f.kind === "temporary_instruction" ? ` (${t("register.field.required")})` : ""}
          </label>
          <input
            id={`${id}-d3`}
            type="date"
            value={f.effective_to ?? ""}
            aria-invalid={invalid("end") ?? invalid("order")}
            onChange={(e) => set({ effective_to: e.target.value || null })}
          />
        </div>
      </div>
      {tried && problems.order && <p className="field__error">{t("register.form.datesOutOfOrder")}</p>}
      <fieldset className="chips">
        <legend>{t("register.field.topics")}</legend>
        {TOPICS.map((k) => (
          <label key={k}>
            <input
              type="checkbox"
              checked={f.topics.includes(k)}
              onChange={(e) => set({ topics: e.target.checked ? [...f.topics, k] : f.topics.filter((x) => x !== k) })}
            />
            {t(`register.topic.${k}`)}
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor={`${id}-su`}>{t("register.field.summary")}</label>
        <textarea id={`${id}-su`} rows={3} dir="auto" maxLength={4000} value={f.summary} onChange={(e) => set({ summary: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor={`${id}-b`}>{t("register.field.body")}</label>
        <textarea id={`${id}-b`} rows={6} dir="auto" value={f.body} onChange={(e) => set({ body: e.target.value })} />
        <p className="hint">{t("register.field.bodyHint")}</p>
      </div>
      {existing && (
        <div className="field">
          <label htmlFor={`${id}-why`}>{t("register.form.reason")}</label>
          <input id={`${id}-why`} value={reason} aria-invalid={invalid("reason")} onChange={(e) => setReason(e.target.value)} />
        </div>
      )}
      {save.isError && <p role="alert" className="field__error">{t(errorMessageKey(save.error))}</p>}
      {tried && !ok && <p role="alert" className="field__error">{t("register.form.incomplete")}</p>}
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {draft ? t("register.form.publish") : t("register.form.save")}
        </button>
        {draft && (
          <button type="button" className="btn" disabled={save.isPending} onClick={submit(false)}>
            {t("register.form.saveDraft")}
          </button>
        )}
        <button type="button" className="btn btn--ghost" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}
