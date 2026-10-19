import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useLanguage } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import {
  TIP_HAZARDS,
  TIP_LANGUAGES,
  tipLanguageComplete,
  type SafetyTip,
  type TipHazard,
  type TipLanguage,
  type TipText,
} from "../lib/opsTypes";

export const MAX_ITEMS = 15;
export const MAX_ITEM_CHARS = 300;
export const MAX_TITLE_CHARS = 120;

type Content = Record<TipLanguage, TipText>;

interface Draft {
  id: string | null;
  hazard: TipHazard;
  position: number;
  content: Content;
  version: number | null;
  status: "draft" | "published";
}

const emptyText = (): TipText => ({ title: "", do: [], dont: [] });

function newDraft(position: number): Draft {
  return {
    id: null,
    hazard: "other",
    position,
    content: { ar: emptyText(), fr: emptyText(), en: emptyText() },
    version: null,
    status: "draft",
  };
}

function draftOf(tip: SafetyTip): Draft {
  return {
    id: tip.id,
    hazard: tip.hazard,
    position: tip.position,
    content: {
      ar: { ...tip.content.ar, do: [...tip.content.ar.do], dont: [...tip.content.ar.dont] },
      fr: { ...tip.content.fr, do: [...tip.content.fr.do], dont: [...tip.content.fr.dont] },
      en: { ...tip.content.en, do: [...tip.content.en.do], dont: [...tip.content.en.dont] },
    },
    version: tip.version,
    status: tip.status,
  };
}

/** Trimmed content, empty items dropped (what is sent and what the completeness rule sees). */
function cleanText(text: TipText): TipText {
  return {
    title: text.title.trim(),
    do: text.do.map((s) => s.trim()).filter(Boolean),
    dont: text.dont.map((s) => s.trim()).filter(Boolean),
  };
}

export function cleanContent(content: Content): Content {
  return { ar: cleanText(content.ar), fr: cleanText(content.fr), en: cleanText(content.en) };
}

export function allComplete(content: Content): boolean {
  return TIP_LANGUAGES.every((l) => tipLanguageComplete(content[l]));
}

/** Language names in their own script, as the app shows them. */
const LANGUAGE_NAMES: Record<TipLanguage, string> = { ar: "العربية", fr: "Français", en: "English" };

function CompletenessMarks({ content }: { content: Content }) {
  const { t } = useTranslation();
  return (
    <span className="tip-langs">
      {TIP_LANGUAGES.map((l) => {
        const ok = tipLanguageComplete(content[l]);
        return (
          <span key={l} className={`tag ${ok ? "tag--lang-ok" : "tag--lang-missing"}`}>
            {l.toUpperCase()} {ok ? "✓" : "✗"}
            <span className="visually-hidden"> {t(ok ? "tips.complete" : "tips.incomplete")}</span>
          </span>
        );
      })}
    </span>
  );
}

function ItemsEditor({
  legend,
  items,
  lang,
  onChange,
  disabled,
}: {
  legend: string;
  items: string[];
  lang: TipLanguage;
  onChange: (items: string[]) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const base = useId();
  const move = (i: number, delta: number) => {
    const next = [...items];
    const j = i + delta;
    const a = next[i];
    const b = next[j];
    if (a === undefined || b === undefined) return;
    next[i] = b;
    next[j] = a;
    onChange(next);
  };
  return (
    <fieldset className="tip-items" disabled={disabled}>
      <legend>
        {legend} ({items.length}/{MAX_ITEMS})
      </legend>
      {items.length === 0 && <p className="muted">{t("tips.noItems")}</p>}
      <ol>
        {items.map((item, i) => {
          const id = `${base}-${i}`;
          return (
            <li key={i}>
              <label htmlFor={id} className="visually-hidden">
                {t("tips.itemLabel", { list: legend, n: i + 1 })}
              </label>
              <input
                id={id}
                type="text"
                lang={lang}
                dir={lang === "ar" ? "rtl" : "ltr"}
                maxLength={MAX_ITEM_CHARS}
                value={item}
                onChange={(e) => onChange(items.map((s, k) => (k === i ? e.target.value : s)))}
              />
              <button
                type="button"
                className="btn btn--small btn--ghost"
                disabled={i === 0}
                aria-label={t("tips.moveUp", { n: i + 1 })}
                onClick={() => move(i, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn--small btn--ghost"
                disabled={i === items.length - 1}
                aria-label={t("tips.moveDown", { n: i + 1 })}
                onClick={() => move(i, 1)}
              >
                ↓
              </button>
              <button
                type="button"
                className="btn btn--small btn--ghost"
                aria-label={t("tips.remove", { n: i + 1 })}
                onClick={() => onChange(items.filter((_, k) => k !== i))}
              >
                ✕
              </button>
            </li>
          );
        })}
      </ol>
      <button
        type="button"
        className="btn btn--small"
        disabled={items.length >= MAX_ITEMS}
        onClick={() => onChange([...items, ""])}
      >
        {t("tips.addItem", { list: legend })}
      </button>
    </fieldset>
  );
}

/** What the app shows for one language (the same order and wording as the citizen sees offline). */
function TipPreview({ text, lang, hazard }: { text: TipText; lang: TipLanguage; hazard: TipHazard }) {
  const { t } = useTranslation();
  const clean = cleanText(text);
  return (
    <section className="card tip-preview" aria-label={t("tips.preview", { lang: LANGUAGE_NAMES[lang] })}>
      <p className="muted">{t("tips.preview", { lang: LANGUAGE_NAMES[lang] })}</p>
      <div lang={lang} dir={lang === "ar" ? "rtl" : "ltr"} className="tip-preview__body">
        <h3>{clean.title || t(`tips.hazard.${hazard}`)}</h3>
        {clean.do.length > 0 && (
          <ul className="tip-preview__do">
            {clean.do.map((s, i) => (
              <li key={i}>✓ {s}</li>
            ))}
          </ul>
        )}
        {clean.dont.length > 0 && (
          <ul className="tip-preview__dont">
            {clean.dont.map((s, i) => (
              <li key={i}>✗ {s}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function TipEditor({ initial, onClose }: { initial: Draft; onClose: (message?: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const base = useId();
  const [draft, setDraft] = useState<Draft>(initial);
  // Last saved state: publishing acts on the stored tip, so unsaved changes must be saved first.
  const [baseline, setBaseline] = useState<Draft>(initial);
  const [tab, setTab] = useState<TipLanguage>("ar");
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const content = useMemo(() => cleanContent(draft.content), [draft.content]);
  const complete = allComplete(content);
  const text = draft.content[tab];
  const setText = (patch: Partial<TipText>) =>
    setDraft((d) => ({ ...d, content: { ...d.content, [tab]: { ...d.content[tab], ...patch } } }));

  const apply = (tip: SafetyTip, message: string) => {
    setDraft(draftOf(tip));
    setBaseline(draftOf(tip));
    setNotice(message);
    qc.setQueryData<SafetyTip[]>(opsKeys.tips, (old) =>
      old ? (old.some((x) => x.id === tip.id) ? old.map((x) => (x.id === tip.id ? tip : x)) : [...old, tip]) : old,
    );
  };

  const save = useMutation({
    mutationFn: () => {
      const body = { hazard: draft.hazard, position: draft.position, content };
      return draft.id
        ? api.updateTip(draft.id, { ...body, version: draft.version ?? undefined })
        : api.createTip(body);
    },
    onSuccess: (tip) => apply(tip, t("tips.saved")),
    onError: (error) => {
      if (isApiError(error) && error.code === "version_conflict") void qc.invalidateQueries({ queryKey: opsKeys.tips });
    },
  });
  const publish = useMutation({
    mutationFn: (id: string) => api.publishTip(id),
    onSuccess: (tip) => apply(tip, t("tips.published")),
  });
  const unpublish = useMutation({
    mutationFn: (id: string) => api.unpublishTip(id),
    onSuccess: (tip) => apply(tip, t("tips.unpublished")),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteTip(id),
    onSuccess: (_r, id) => {
      qc.setQueryData<SafetyTip[]>(opsKeys.tips, (old) => old?.filter((x) => x.id !== id));
      onClose(t("tips.deleted"));
    },
  });
  const busy = save.isPending || publish.isPending || unpublish.isPending || remove.isPending;
  const error = save.error ?? publish.error ?? unpublish.error ?? remove.error;
  const dirty =
    JSON.stringify(cleanContent(baseline.content)) !== JSON.stringify(content) ||
    baseline.hazard !== draft.hazard ||
    baseline.position !== draft.position;

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setNotice(null);
    publish.reset();
    unpublish.reset();
    save.mutate();
  };

  const hazardId = `${base}-hazard`;
  const positionId = `${base}-position`;
  const titleId = `${base}-title`;
  return (
    <section className="card tip-editor" aria-labelledby={`${base}-heading`}>
      <h2 id={`${base}-heading`}>{draft.id ? t("tips.editTitle") : t("tips.newTitle")}</h2>
      <p>
        <span className={`tag tag--tip-${draft.status}`}>{t(`tips.status.${draft.status}`)}</span>{" "}
        <CompletenessMarks content={content} />
      </p>
      <div className="tip-editor__grid">
        <form onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor={hazardId}>{t("tips.hazardLabel")}</label>
            <select
              id={hazardId}
              value={draft.hazard}
              disabled={busy}
              onChange={(e) => setDraft((d) => ({ ...d, hazard: e.target.value as TipHazard }))}
            >
              {TIP_HAZARDS.map((h) => (
                <option key={h} value={h}>
                  {t(`tips.hazard.${h}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field field--number">
            <label htmlFor={positionId}>{t("tips.position")}</label>
            <input
              id={positionId}
              type="number"
              min={0}
              max={1000}
              value={draft.position}
              disabled={busy}
              onChange={(e) =>
                setDraft((d) => ({ ...d, position: Math.min(1000, Math.max(0, Math.round(Number(e.target.value) || 0))) }))
              }
            />
          </div>
          <div role="tablist" aria-label={t("tips.languages")} className="tabs">
            {TIP_LANGUAGES.map((l) => (
              <button
                key={l}
                type="button"
                role="tab"
                id={`${base}-tab-${l}`}
                aria-selected={tab === l}
                aria-controls={`${base}-panel`}
                className={`tabs__tab${tab === l ? " tabs__tab--active" : ""}`}
                onClick={() => setTab(l)}
              >
                <span lang={l}>{LANGUAGE_NAMES[l]}</span> {tipLanguageComplete(content[l]) ? "✓" : "✗"}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${tab}`} className="tabs__panel">
            <div className="field">
              <label htmlFor={titleId}>{t("tips.titleLabel")}</label>
              <input
                id={titleId}
                type="text"
                lang={tab}
                dir={tab === "ar" ? "rtl" : "ltr"}
                maxLength={MAX_TITLE_CHARS}
                value={text.title}
                disabled={busy}
                onChange={(e) => setText({ title: e.target.value })}
              />
            </div>
            <ItemsEditor
              legend={t("tips.do")}
              items={text.do}
              lang={tab}
              disabled={busy}
              onChange={(items) => setText({ do: items })}
            />
            <ItemsEditor
              legend={t("tips.dont")}
              items={text.dont}
              lang={tab}
              disabled={busy}
              onChange={(items) => setText({ dont: items })}
            />
          </div>
          {!complete && <p className="alert alert--info">{t("tips.completeHint")}</p>}
          {draft.status === "published" && !complete && (
            <p className="alert alert--warn">{t("tips.publishedIncomplete")}</p>
          )}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {save.isPending ? t("tips.saving") : t("tips.save")}
            </button>
            {draft.id && draft.status === "draft" && (
              <button
                type="button"
                className="btn"
                disabled={busy || !complete || dirty}
                onClick={() => draft.id && publish.mutate(draft.id)}
              >
                {t("tips.publish")}
              </button>
            )}
            {draft.id && draft.status === "published" && (
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => draft.id && unpublish.mutate(draft.id)}
              >
                {t("tips.unpublish")}
              </button>
            )}
            {draft.id && !deleting && (
              <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setDeleting(true)}>
                {t("tips.delete")}
              </button>
            )}
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => onClose()}>
              {t("tips.close")}
            </button>
          </div>
          {draft.id && draft.status === "draft" && dirty && complete && (
            <p className="muted">{t("tips.saveBeforePublish")}</p>
          )}
          {deleting && draft.id && (
            <div className="alert alert--warn" role="alert">
              <p>{draft.status === "published" ? t("tips.deleteConfirmPublished") : t("tips.deleteConfirm")}</p>
              <div className="actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={busy}
                  onClick={() => draft.id && remove.mutate(draft.id)}
                >
                  {t("tips.deleteConfirmAction")}
                </button>
                <button type="button" className="btn" onClick={() => setDeleting(false)}>
                  {t("common.cancel")}
                </button>
              </div>
            </div>
          )}
          <div role="status" aria-live="polite">
            {notice && <p className="alert alert--ok">{notice}</p>}
          </div>
          {error && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(error))}
            </p>
          )}
        </form>
        <TipPreview text={text} lang={tab} hazard={draft.hazard} />
      </div>
    </section>
  );
}

/** FR-C-19: safety tips shown in the app (offline), edited in Arabic, French and English, then published. */
export function SafetyTipsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const [editing, setEditing] = useState<Draft | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const query = useQuery({ queryKey: opsKeys.tips, queryFn: ({ signal }) => api.tips(signal) });
  const tips = useMemo(
    () => [...(query.data ?? [])].sort((a, b) => a.position - b.position || a.hazard.localeCompare(b.hazard)),
    [query.data],
  );
  const open = (draft: Draft) => {
    setMessage(null);
    setEditing(draft);
  };

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("tips.title")}</h1>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => open(newDraft((tips.at(-1)?.position ?? 0) + 10))}
        >
          {t("tips.new")}
        </button>
      </div>
      <p className="muted">{t("tips.intro")}</p>
      <div role="status" aria-live="polite">
        {message && <p className="alert alert--ok">{message}</p>}
      </div>
      {editing && (
        <TipEditor
          key={editing.id ?? "new"}
          initial={editing}
          onClose={(msg) => {
            setEditing(null);
            setMessage(msg ?? null);
          }}
        />
      )}
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && tips.length === 0 && <p className="empty">{t("tips.empty")}</p>}
      {tips.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("tips.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("tips.position")}</th>
                <th scope="col">{t("tips.hazardLabel")}</th>
                <th scope="col">{t("tips.titleLabel")}</th>
                <th scope="col">{t("tips.statusLabel")}</th>
                <th scope="col">{t("tips.languages")}</th>
                <th scope="col">{t("tips.updatedAt")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("tips.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {tips.map((tip) => (
                <tr key={tip.id}>
                  <td>{fmt.number(tip.position)}</td>
                  <td>{t(`tips.hazard.${tip.hazard}`)}</td>
                  <td dir="auto">{tip.content[lang].title || tip.content.ar.title}</td>
                  <td>
                    <span className={`tag tag--tip-${tip.status}`}>{t(`tips.status.${tip.status}`)}</span>
                  </td>
                  <td>
                    <CompletenessMarks content={tip.content} />
                  </td>
                  <td>
                    <time dateTime={tip.updated_at}>{fmt.dateTime(tip.updated_at)}</time>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--small"
                      aria-label={t("tips.editOne", { title: tip.content[lang].title || t(`tips.hazard.${tip.hazard}`) })}
                      onClick={() => open(draftOf(tip))}
                    >
                      {t("tips.edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
