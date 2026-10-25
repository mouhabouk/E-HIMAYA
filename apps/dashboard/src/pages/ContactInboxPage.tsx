import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  allowedActions,
  CONTACT_KINDS,
  CONTACT_STATUSES,
  contactKeys,
  NEEDS_TEXT,
  TEXT_MAX,
  TEXT_MIN,
  type ContactAction,
  type ContactDetail,
  type ContactKind,
  type InboxFilters,
  type StatusFilter,
} from "../lib/contact";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { useDraft } from "../lib/drafts";
import { PageTitle } from "../components/PageTitle";

const DEFAULT_FILTERS: InboxFilters = { kind: "", status: "open", gouvernorat: "", overdue: false };

function Filters({
  value,
  onChange,
  openByKind,
  overdue,
}: {
  value: InboxFilters;
  onChange: (f: InboxFilters) => void;
  openByKind: Record<ContactKind, number> | undefined;
  overdue: number;
}) {
  const { t } = useTranslation();
  const id = useId();
  const gouvernorats = useGouvernorats();
  return (
    <div className="filters">
      <div className="field">
        <label htmlFor={`${id}-kind`}>{t("contact.kind")}</label>
        <select
          id={`${id}-kind`}
          value={value.kind}
          onChange={(e) => onChange({ ...value, kind: e.target.value as ContactKind | "" })}
        >
          <option value="">{t("contact.allKinds")}</option>
          {CONTACT_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`contact.kinds.${k}`)}
              {openByKind?.[k] ? ` (${openByKind[k]})` : ""}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-status`}>{t("contact.status")}</label>
        <select
          id={`${id}-status`}
          value={value.status}
          onChange={(e) => onChange({ ...value, status: e.target.value as StatusFilter })}
        >
          <option value="open">{t("contact.openOnly")}</option>
          <option value="all">{t("contact.allStatuses")}</option>
          {CONTACT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`contact.statuses.${s}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-gov`}>{t("contact.gouvernorat")}</label>
        <select
          id={`${id}-gov`}
          value={value.gouvernorat}
          onChange={(e) => onChange({ ...value, gouvernorat: e.target.value })}
        >
          <option value="">{t("contact.allGouvernorats")}</option>
          <option value="0">{t("contact.national")}</option>
          {gouvernorats.list.map((g) => (
            <option key={g.code} value={String(g.code)}>
              {gouvernorats.nameOf(g.code)}
            </option>
          ))}
        </select>
      </div>
      <label className="field field--inline">
        <input
          type="checkbox"
          checked={value.overdue}
          onChange={(e) => onChange({ ...value, overdue: e.target.checked })}
        />{" "}
        {t("contact.overdueOnly", { count: overdue })}
      </label>
    </div>
  );
}

function ActionForm({ request, onDone }: { request: ContactDetail; onDone: (d: ContactDetail) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [action, setAction] = useState<ContactAction | null>(null);
  const [text, setText, clearText] = useDraft(`contact:${request.id}:text`);
  const [target, setTarget] = useState("");
  const [tried, setTried] = useState(false);
  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof api.contactAct>[1]) => api.contactAct(request.id, body),
    onSuccess: (d) => {
      setAction(null);
      clearText();
      setTried(false);
      onDone(d);
    },
  });
  const actions = allowedActions(request.status);
  const run = (a: ContactAction) => {
    if (NEEDS_TEXT.includes(a) || a === "move") {
      setAction(a);
      setTarget("");
      return;
    }
    mutation.mutate({ version: request.version, action: a });
  };
  const textOk = text.trim().length >= TEXT_MIN && text.length <= TEXT_MAX;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (action === null) return;
    if (action === "move") {
      const code = target === "" ? null : Number(target);
      if (code === request.gouvernorat_code) return;
      mutation.mutate({ version: request.version, action, gouvernorat_code: code });
      return;
    }
    if (!textOk) return;
    mutation.mutate({ version: request.version, action, text: text.trim() });
  };
  return (
    <div className="contact-actions">
      <div className="actions">
        {actions.map((a) => (
          <button
            key={a}
            type="button"
            className={a === "answer" ? "btn btn--primary" : "btn"}
            disabled={mutation.isPending}
            onClick={() => run(a)}
          >
            {t(`contact.actions.${a}`)}
          </button>
        ))}
      </div>
      {action !== null && (
        <form onSubmit={submit} noValidate>
          {action === "move" ? (
            <div className="field">
              <label htmlFor={`${id}-to`}>{t("contact.moveTo")}</label>
              <select id={`${id}-to`} value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="">{t("contact.national")}</option>
                {gouvernorats.list.map((g) => (
                  <option key={g.code} value={String(g.code)}>
                    {gouvernorats.nameOf(g.code)}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="field">
              <label htmlFor={`${id}-text`}>{t(`contact.textLabel.${action}`)}</label>
              <textarea
                id={`${id}-text`}
                rows={action === "answer" ? 6 : 3}
                value={text}
                maxLength={TEXT_MAX}
                aria-invalid={tried && !textOk}
                onChange={(e) => setText(e.target.value)}
              />
              <p className="hint">
                {action === "note" ? t("contact.noteHint") : t("contact.visibleHint")}
              </p>
              {tried && !textOk && (
                <p className="field__error" role="alert">
                  {t("contact.textRange", { min: TEXT_MIN, max: TEXT_MAX })}
                </p>
              )}
            </div>
          )}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
              {t("contact.confirm")}
            </button>
            <button type="button" className="btn" onClick={() => setAction(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
      {mutation.error && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </div>
  );
}

function Detail({ id, onChanged }: { id: string; onChanged: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: contactKeys.detail(id),
    queryFn: ({ signal }) => api.contactRequest(id, signal),
  });
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorBox error={query.error} />;
  const r = query.data;
  if (!r) return null;
  return (
    <section className="card contact-detail" aria-labelledby={`contact-${r.id}`}>
      <h2 id={`contact-${r.id}`}>
        {r.number} · {t(`contact.kinds.${r.kind}`)}
      </h2>
      <p>
        <span className={`chip chip--${r.status}`}>{t(`contact.statuses.${r.status}`)}</span>{" "}
        {r.overdue && <span className="chip chip--overdue">{t("contact.overdue")}</span>}{" "}
        {r.due_at && t("contact.dueOn", { date: fmt.date(r.due_at) })}
      </p>
      <dl className="contact-facts">
        <dt>{t("contact.gouvernorat")}</dt>
        <dd>{gouvernorats.nameOf(r.gouvernorat_code) ?? t("contact.national")}</dd>
        <dt>{t("contact.received")}</dt>
        <dd>{fmt.dateTime(r.created_at)}</dd>
        <dt>{t("contact.requester")}</dt>
        <dd>
          {r.anonymous ? (
            t("contact.anonymous")
          ) : (
            <>
              {r.name && <span>{r.name}</span>}
              {r.phone && (
                <>
                  {" "}
                  · <a href={`tel:${r.phone}`} dir="ltr">{r.phone}</a>
                </>
              )}
              {r.email && (
                <>
                  {" "}
                  · <a href={`mailto:${r.email}`}>{r.email}</a>
                </>
              )}
            </>
          )}
        </dd>
        {r.assigned_name && (
          <>
            <dt>{t("contact.assigned")}</dt>
            <dd>{r.assigned_name}</dd>
          </>
        )}
      </dl>
      <h3>{r.subject}</h3>
      <p className="contact-message">{r.message}</p>
      {r.answer && (
        <>
          <h3>{r.status === "rejected" ? t("contact.rejectReason") : t("contact.answer")}</h3>
          <p className="contact-message">{r.answer}</p>
        </>
      )}
      <ActionForm
        request={r}
        onDone={(d) => {
          qc.setQueryData(contactKeys.detail(d.id), d);
          onChanged();
        }}
      />
      <h3>{t("contact.history")}</h3>
      <ol className="contact-history">
        {r.events.map((e) => (
          <li key={e.id}>
            <time dateTime={e.at}>{fmt.dateTime(e.at)}</time> · {t(`contact.events.${e.action}`)}
            {e.status && ` → ${t(`contact.statuses.${e.status}`)}`}
            {e.action === "move" && ` → ${gouvernorats.nameOf(e.gouvernorat_code) ?? t("contact.national")}`}
            {e.actor_name && ` · ${e.actor_name}`}
            {!e.visible && <span className="tag">{t("contact.internal")}</span>}
            {e.note && <p className="contact-message">{e.note}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Contact us inbox (phase B1, design §2ter): one list by kind, status and gouvernorat, with the legal deadlines. */
export function ContactInboxPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const [filters, setFilters] = useState<InboxFilters>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const inbox = useQuery({
    queryKey: contactKeys.inbox(filters),
    queryFn: ({ signal }) => api.contactInbox(filters, signal),
  });
  return (
    <div className="page contact-page">
      <PageTitle icon="mail" tone="sky">{t("contact.title")}</PageTitle>
      <p>{t("contact.intro")}</p>
      <Filters
        value={filters}
        onChange={setFilters}
        openByKind={inbox.data?.open_by_kind}
        overdue={inbox.data?.overdue ?? 0}
      />
      {inbox.isLoading && <Loading />}
      {inbox.error && <ErrorBox error={inbox.error} />}
      {inbox.data && (
        <div className="contact-layout">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("contact.number")}</th>
                <th scope="col">{t("contact.kind")}</th>
                <th scope="col">{t("contact.subject")}</th>
                <th scope="col">{t("contact.gouvernorat")}</th>
                <th scope="col">{t("contact.received")}</th>
                <th scope="col">{t("contact.due")}</th>
                <th scope="col">{t("contact.status")}</th>
              </tr>
            </thead>
            <tbody>
              {inbox.data.items.length === 0 && (
                <tr>
                  <td colSpan={7}>{t("contact.empty")}</td>
                </tr>
              )}
              {inbox.data.items.map((r) => (
                <tr key={r.id} className={r.id === selected ? "row--selected" : undefined}>
                  <td>
                    <button type="button" className="link" onClick={() => setSelected(r.id)}>
                      {r.number}
                    </button>
                  </td>
                  <td>{t(`contact.kinds.${r.kind}`)}</td>
                  <td>{r.subject}</td>
                  <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? t("contact.national")}</td>
                  <td>{fmt.dateTime(r.created_at)}</td>
                  <td>
                    {r.due_at ? fmt.date(r.due_at) : "—"}
                    {r.overdue && <span className="chip chip--overdue">{t("contact.overdue")}</span>}
                  </td>
                  <td>{t(`contact.statuses.${r.status}`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {inbox.data.truncated && <p className="hint">{t("contact.truncated")}</p>}
          {selected && (
            <Detail
              key={selected}
              id={selected}
              onChanged={() => void qc.invalidateQueries({ queryKey: ["contact", "inbox"] })}
            />
          )}
        </div>
      )}
    </div>
  );
}
