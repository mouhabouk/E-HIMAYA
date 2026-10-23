import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { RequiredNote } from "../components/PhaseASettings";
import { ReasonField } from "../components/Phase9Bits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useLanguage } from "../lib/hooks";
import {
  emptyText,
  GUIDE_ICON_PATHS,
  GUIDE_LANGS,
  guideKeys,
  linesOf,
  validateItem,
  type Guide,
  type GuideItem,
  type GuideLang,
  type GuideTopic,
  type ItemContent,
  type Titles,
} from "../lib/guide";
import { keyFrom } from "../lib/layers";
import { reasonValid } from "../lib/phase9";

function TopicIcon({ icon, colour }: { icon: string; colour: string }) {
  return (
    <span className="layer-swatch" style={{ background: colour }} aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path fill="currentColor" fillRule="evenodd" d={GUIDE_ICON_PATHS[icon] ?? GUIDE_ICON_PATHS.pin} />
      </svg>
    </span>
  );
}

/** The whole guide comes back from every change: put it in the cache. */
function useGuideMutation<A>(fn: (args: A) => Promise<Guide>, onDone?: () => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (guide) => {
      qc.setQueryData(guideKeys.staff, guide);
      onDone?.();
    },
  });
}

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

/** A button that asks for a reason before acting (hide, show, validate). */
function ReasonAction({
  label,
  confirm,
  onConfirm,
  pending,
  error,
  explain,
}: {
  label: string;
  confirm: string;
  onConfirm: (reason: string) => void;
  pending: boolean;
  error: unknown;
  explain?: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  if (!open) {
    return (
      <button type="button" className="btn btn--small" onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  }
  return (
    <form
      noValidate
      className="guide-reason"
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (reasonValid(reason)) onConfirm(reason.trim());
      }}
    >
      {explain && <p>{explain}</p>}
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={pending}>
          {confirm}
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </button>
      </div>
      <MutationError error={error} />
    </form>
  );
}

// ---------------------------------------------------------------- topic form

function TopicForm({ guide, topic, onDone }: { guide: Guide; topic: GuideTopic | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [title, setTitle] = useState<Titles>(() => (topic ? { ...topic.title } : { ar: "", fr: "", en: "" }));
  const [key, setKey] = useState(topic?.key ?? "");
  const [keyTouched, setKeyTouched] = useState(topic !== null);
  const [icon, setIcon] = useState(topic?.icon ?? "pin");
  const [colour, setColour] = useState(topic?.colour ?? guide.palette[0] ?? "#37474F");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const mutation = useGuideMutation(
    () =>
      topic
        ? api.updateTopic(topic.id, { version: topic.version, reason: reason.trim(), title, icon, colour })
        : api.createTopic({ key, title, icon, colour, reason: reason.trim() }),
    onDone,
  );
  const titlesOk = GUIDE_LANGS.every((l) => title[l].trim() !== "");
  const keyOk = /^[a-z][a-z0-9_]{1,39}$/.test(key);

  return (
    <form
      noValidate
      className="card"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (titlesOk && keyOk && reasonValid(reason)) mutation.mutate(undefined);
      }}
    >
      <h3 id={`${id}-title`}>{topic ? t("guide.topic.edit") : t("guide.topic.new")}</h3>
      <RequiredNote />
      <div className="settings-grid">
        {GUIDE_LANGS.map((lang) => (
          <div className="field" key={lang}>
            <label htmlFor={`${id}-${lang}`}>{t(`guide.topic.title_${lang}`)}</label>
            <input
              id={`${id}-${lang}`}
              lang={lang}
              dir={lang === "ar" ? "rtl" : "ltr"}
              aria-required="true"
              maxLength={120}
              value={title[lang]}
              aria-invalid={tried && !title[lang].trim() ? true : undefined}
              onChange={(e) => {
                setTitle({ ...title, [lang]: e.target.value });
                if (!keyTouched && lang === "en") setKey(keyFrom(e.target.value));
              }}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${id}-key`}>{t("layers.form.key")}</label>
          <input
            id={`${id}-key`}
            dir="ltr"
            aria-required="true"
            disabled={topic !== null}
            value={key}
            aria-invalid={tried && !keyOk ? true : undefined}
            onChange={(e) => {
              setKeyTouched(true);
              setKey(e.target.value.trim());
            }}
          />
        </div>
      </div>
      <fieldset className="layer-icons">
        <legend>{t("layers.form.icon")}</legend>
        {guide.icons.map((name) => (
          <label key={name} className="layer-choice">
            <input type="radio" name={`${id}-icon`} checked={icon === name} onChange={() => setIcon(name)} />
            <TopicIcon icon={name} colour={colour} />
            <span>{t(`guide.icons.${name}`, { defaultValue: name })}</span>
          </label>
        ))}
      </fieldset>
      <fieldset className="layer-colours">
        <legend>{t("layers.form.colour")}</legend>
        {guide.palette.map((c, i) => (
          <label key={c} className="layer-choice">
            <input type="radio" name={`${id}-colour`} checked={colour === c} onChange={() => setColour(c)} />
            <span className="layer-swatch" style={{ background: c }} aria-hidden="true" />
            <span className="visually-hidden">{t("layers.form.colourN", { n: i + 1, colour: c })}</span>
          </label>
        ))}
      </fieldset>
      {tried && (!titlesOk || !keyOk) && (
        <p className="field__error" role="alert">
          {!titlesOk ? t("guide.errors.title") : t("layers.form.errors.key")}
        </p>
      )}
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {topic ? t("aiSettings.save") : t("guide.topic.create")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

// ---------------------------------------------------------------- item form

type Lines = Record<GuideLang, { title: string; call: string; steps: string; dont: string }>;

function linesFrom(content: ItemContent | null): Lines {
  const out = {} as Lines;
  for (const lang of GUIDE_LANGS) {
    const c = content?.[lang] ?? emptyText();
    out[lang] = { title: c.title, call: c.call.join("\n"), steps: c.steps.join("\n"), dont: c.dont.join("\n") };
  }
  return out;
}

function contentFrom(lines: Lines): ItemContent {
  const out = {} as ItemContent;
  for (const lang of GUIDE_LANGS) {
    const l = lines[lang];
    out[lang] = { title: l.title.trim(), call: linesOf(l.call), steps: linesOf(l.steps), dont: linesOf(l.dont) };
  }
  return out;
}

function ItemForm({ topic, item, onDone }: { topic: GuideTopic; item: GuideItem | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [lines, setLines] = useState<Lines>(() => linesFrom(item?.content ?? null));
  const [call198, setCall198] = useState(item?.call_198 ?? false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const content = contentFrom(lines);
  const problem = validateItem(content);
  const mutation = useGuideMutation(
    () =>
      item
        ? api.updateItem(item.id, { version: item.version, reason: reason.trim(), content, call_198: call198 })
        : api.createItem(topic.id, { content, call_198: call198, reason: reason.trim() }),
    onDone,
  );
  const set = (lang: GuideLang, field: keyof Lines[GuideLang], value: string) =>
    setLines({ ...lines, [lang]: { ...lines[lang], [field]: value } });

  return (
    <form
      noValidate
      className="card guide-item-form"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (!problem && reasonValid(reason)) mutation.mutate(undefined);
      }}
    >
      <h4 id={`${id}-title`}>{item ? t("guide.item.edit") : t("guide.item.new")}</h4>
      <RequiredNote />
      {item?.validated && <p className="alert alert--info">{t("guide.item.revalidate")}</p>}
      <div className="guide-langs">
        {GUIDE_LANGS.map((lang) => (
          <fieldset key={lang} lang={lang} dir={lang === "ar" ? "rtl" : "ltr"}>
            <legend>{t(`languages.${lang}`)}</legend>
            <div className="field">
              <label htmlFor={`${id}-${lang}-title`}>{t("guide.item.title")}</label>
              <input
                id={`${id}-${lang}-title`}
                aria-required="true"
                maxLength={120}
                value={lines[lang].title}
                aria-invalid={tried && problem?.lang === lang && problem.error === "title" ? true : undefined}
                onChange={(e) => set(lang, "title", e.target.value)}
              />
            </div>
            {(["call", "steps", "dont"] as const).map((field) => (
              <div className="field" key={field}>
                <label htmlFor={`${id}-${lang}-${field}`}>{t(`guide.item.${field}`)}</label>
                <textarea
                  id={`${id}-${lang}-${field}`}
                  rows={field === "steps" ? 5 : 2}
                  aria-required={field === "steps" ? "true" : undefined}
                  aria-describedby={`${id}-lines-help`}
                  aria-invalid={tried && problem?.lang === lang && problem.error === field ? true : undefined}
                  value={lines[lang][field]}
                  onChange={(e) => set(lang, field, e.target.value)}
                />
              </div>
            ))}
          </fieldset>
        ))}
      </div>
      <p id={`${id}-lines-help`} className="muted">
        {t("guide.item.linesHelp")}
      </p>
      <label className="checkbox">
        <input type="checkbox" checked={call198} onChange={(e) => setCall198(e.target.checked)} />
        <span>{t("guide.item.call198")}</span>
      </label>
      {tried && problem && (
        <p className="field__error" role="alert">
          {t(`guide.errors.${problem.error}`, { lang: t(`languages.${problem.lang}`) })}
        </p>
      )}
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {item ? t("aiSettings.save") : t("guide.item.create")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

// ---------------------------------------------------------------- lists

function MoveButtons({
  label,
  first,
  last,
  onMove,
  pending,
}: {
  label: string;
  first: boolean;
  last: boolean;
  onMove: (d: "up" | "down") => void;
  pending: boolean;
}) {
  const { t } = useTranslation();
  return (
    <>
      <button
        type="button"
        className="btn btn--small"
        disabled={first || pending}
        aria-label={t("guide.moveUp", { name: label })}
        onClick={() => onMove("up")}
      >
        ↑
      </button>
      <button
        type="button"
        className="btn btn--small"
        disabled={last || pending}
        aria-label={t("guide.moveDown", { name: label })}
        onClick={() => onMove("down")}
      >
        ↓
      </button>
    </>
  );
}

function ItemRow({ topic, item, index }: { topic: GuideTopic; item: GuideItem; index: number }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const [editing, setEditing] = useState(false);
  const move = useGuideMutation((d: "up" | "down") => api.moveItem(item.id, d));
  const hide = useGuideMutation((reason: string) =>
    api.updateItem(item.id, { version: item.version, reason, hidden: !item.hidden }),
  );
  const validate = useGuideMutation((reason: string) => api.validateItem(item.id, item.version, reason));
  const text = item.content[lang];

  let body: ReactNode = (
    <div className="guide-item__actions">
      <MoveButtons
        label={text.title}
        first={index === 0}
        last={index === topic.items.length - 1}
        onMove={(d) => move.mutate(d)}
        pending={move.isPending}
      />
      <button type="button" className="btn btn--small" onClick={() => setEditing(true)}>
        {t("guide.edit")}
      </button>
      <ReasonAction
        label={item.hidden ? t("guide.show") : t("guide.hide")}
        confirm={item.hidden ? t("guide.show") : t("guide.hide")}
        onConfirm={(r) => hide.mutate(r)}
        pending={hide.isPending}
        error={hide.error}
      />
      {!item.validated && (
        <ReasonAction
          label={t("guide.item.validate")}
          confirm={t("guide.item.validateConfirm")}
          explain={t("guide.item.validateExplain")}
          onConfirm={(r) => validate.mutate(r)}
          pending={validate.isPending}
          error={validate.error}
        />
      )}
      <MutationError error={move.error} />
    </div>
  );
  if (editing) body = <ItemForm topic={topic} item={item} onDone={() => setEditing(false)} />;

  return (
    <li className={`guide-item${item.hidden ? " row--muted" : ""}`}>
      <div className="guide-item__head">
        <strong dir="auto">{text.title}</strong>
        {item.call_198 && <span className="chip">{t("guide.item.call198Chip")}</span>}
        {item.hidden && <span className="chip">{t("guide.hiddenChip")}</span>}
        {item.validated ? (
          <span className="chip chip--to-verify">
            {t("guide.item.validatedBy", { name: item.validated_by ?? "", at: fmt.date(item.validated_at ?? item.updated_at) })}
          </span>
        ) : (
          <span className="tag tag--sim">{t("guide.item.awaiting")}</span>
        )}
      </div>
      <ol className="guide-item__steps" dir="auto">
        {text.steps.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ol>
      {body}
    </li>
  );
}

function TopicCard({ guide, topic, index }: { guide: Guide; topic: GuideTopic; index: number }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const move = useGuideMutation((d: "up" | "down") => api.moveTopic(topic.id, d));
  const hide = useGuideMutation((reason: string) =>
    api.updateTopic(topic.id, { version: topic.version, reason, hidden: !topic.hidden }),
  );
  const name = topic.title[lang];
  return (
    <section className={`card guide-topic${topic.hidden ? " row--muted" : ""}`} aria-labelledby={`${id}-name`}>
      <h2 id={`${id}-name`}>
        <TopicIcon icon={topic.icon} colour={topic.colour} /> <span dir="auto">{name}</span>
        {topic.hidden && <span className="chip">{t("guide.hiddenChip")}</span>}
      </h2>
      <div className="actions">
        <MoveButtons
          label={name}
          first={index === 0}
          last={index === guide.topics.length - 1}
          onMove={(d) => move.mutate(d)}
          pending={move.isPending}
        />
        <button type="button" className="btn btn--small" onClick={() => setEditing(!editing)}>
          {t("guide.edit")}
        </button>
        <ReasonAction
          label={topic.hidden ? t("guide.show") : t("guide.hide")}
          confirm={topic.hidden ? t("guide.show") : t("guide.hide")}
          onConfirm={(r) => hide.mutate(r)}
          pending={hide.isPending}
          error={hide.error}
        />
      </div>
      <MutationError error={move.error} />
      {editing && <TopicForm guide={guide} topic={topic} onDone={() => setEditing(false)} />}
      {topic.items.length === 0 ? (
        <p className="muted">{t("guide.item.none")}</p>
      ) : (
        <ul className="guide-items" aria-label={t("guide.item.list", { name })}>
          {topic.items.map((item, i) => (
            <ItemRow key={`${item.id}-${item.version}`} topic={topic} item={item} index={i} />
          ))}
        </ul>
      )}
      {adding ? (
        <ItemForm topic={topic} item={null} onDone={() => setAdding(false)} />
      ) : (
        <button type="button" className="btn" onClick={() => setAdding(true)}>
          {t("guide.item.new")}
        </button>
      )}
    </section>
  );
}

/** Emergency hub editor (phase B1, design §2bis): topics and their items, added, changed, hidden, reordered. */
export function EmergencyGuidePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const [creating, setCreating] = useState(false);
  const query = useQuery({ queryKey: guideKeys.staff, queryFn: ({ signal }) => api.guide(signal) });
  const guide = query.data;
  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("guide.title")}</h1>
        <p className="muted">{t("guide.intro")}</p>
      </div>
      {/* Simulation notice (amber): first-aid texts are not official until the Office's medical staff validates them. */}
      <p className="sim-band" role="note">
        {t("guide.simNotice")}
      </p>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {guide && (
        <>
          {creating ? (
            <TopicForm guide={guide} topic={null} onDone={() => setCreating(false)} />
          ) : (
            <button type="button" className="btn" onClick={() => setCreating(true)}>
              {t("guide.topic.new")}
            </button>
          )}
          {guide.topics.map((topic, i) => (
            <TopicCard key={topic.id} guide={guide} topic={topic} index={i} />
          ))}
        </>
      )}
    </div>
  );
}
