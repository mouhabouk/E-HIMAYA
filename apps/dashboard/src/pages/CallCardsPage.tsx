// covers: OS2 (Yamen 2026-11-10, docs/phase-os2/design-os2.md §3): the guided call-taking cards. Every version of
// each category's card, a trial of the card as the room sees it, and, for the Office: writing a new version as a
// draft, recording its medical validation (medical cards) and approving it (national room manager).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { CallCardPanel } from "../components/CallCardPanel";
import { ErrorBox, Loading } from "../components/Feedback";
import { IconTile } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { ReasonField } from "../components/Phase9Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  ANSWERS,
  CARD_BANDS,
  callCardKeys,
  checkContent,
  emptyContent,
  emptyEffect,
  emptyQuestion,
  type Answers,
  type CallCard,
  type CardAnswer,
  type CardBand,
  type CardContent,
  type CardEffect,
  type CardInstruction,
  type CardQuestion,
} from "../lib/callCards";
import { useFormat } from "../lib/hooks";
import { reasonValid } from "../lib/phase9";
import { callCardRights } from "../lib/roles";
import { CATEGORY_TILE } from "../lib/categoryIcons";
import { CATEGORIES, type Category } from "../lib/types";

const CATEGORY_ICON = CATEGORY_TILE;

const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

/** A list edited one item per line: the text is kept as typed, so an empty line being written is not lost. */
function LinesArea({ id, rows, value, onChange }: { id: string; rows: number; value: string[]; onChange: (v: string[]) => void }) {
  const [text, setText] = useState(() => value.join("\n"));
  return (
    <textarea
      id={id}
      rows={rows}
      value={lines(text).join("\n") === value.join("\n") ? text : value.join("\n")}
      onChange={(e) => {
        setText(e.target.value);
        onChange(lines(e.target.value));
      }}
    />
  );
}

function StatusPill({ card }: { card: CallCard }) {
  const { t } = useTranslation();
  const tone = card.status === "approved" ? "green" : card.status === "draft" ? "amber" : "slate";
  return <span className={`pill tone-${tone}`}>{t(`callCards.status.${card.status}`)}</span>;
}

/** One answer's effect: why, band, flag, resources, instruction, and whether it says a life or an injury. */
function EffectEditor({
  answer,
  effect,
  instructions,
  onChange,
}: {
  answer: CardAnswer;
  effect: CardEffect | undefined;
  instructions: string[];
  onChange: (e: CardEffect | undefined) => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  if (!effect) {
    return (
      <button type="button" className="btn btn--small" onClick={() => onChange(emptyEffect())}>
        {t("callCards.edit.addEffect", { answer: t(`callCards.answer.${answer}`) })}
      </button>
    );
  }
  const set = (patch: Partial<CardEffect>) => onChange({ ...effect, ...patch });
  return (
    <fieldset className="call-card-editor__effect">
      <legend>{t("callCards.edit.ifAnswer", { answer: t(`callCards.answer.${answer}`) })}</legend>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-why`}>{t("callCards.edit.why")}</label>
          <input id={`${id}-why`} value={effect.why} maxLength={200} onChange={(e) => set({ why: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-band`}>{t("callCards.edit.band")}</label>
          <select
            id={`${id}-band`}
            value={effect.band ?? ""}
            onChange={(e) => set({ band: (e.target.value || null) as CardBand | null })}
          >
            <option value="">{t("callCards.edit.noBand")}</option>
            {CARD_BANDS.map((b) => (
              <option key={b} value={b}>
                {t(`callCards.band.${b}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-flag`}>{t("callCards.edit.flag")}</label>
          <input
            id={`${id}-flag`}
            value={effect.flag ?? ""}
            maxLength={200}
            onChange={(e) => set({ flag: e.target.value || null })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-ins`}>{t("callCards.edit.instruction")}</label>
          <select
            id={`${id}-ins`}
            value={effect.instruction ?? ""}
            onChange={(e) => set({ instruction: e.target.value || null })}
          >
            <option value="">{t("callCards.edit.noInstruction")}</option>
            {instructions.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-means`}>{t("callCards.edit.means")}</label>
        <LinesArea id={`${id}-means`} rows={2} value={effect.means} onChange={(v) => set({ means: v })} />
      </div>
      <label className="call-card-editor__check">
        <input type="checkbox" checked={effect.lives} onChange={(e) => set({ lives: e.target.checked })} />
        {t("callCards.edit.lives")}
      </label>
      <label className="call-card-editor__check">
        <input type="checkbox" checked={effect.injured} onChange={(e) => set({ injured: e.target.checked })} />
        {t("callCards.edit.injured")}
      </label>
      <button type="button" className="btn btn--small btn--danger" onClick={() => onChange(undefined)}>
        {t("callCards.edit.removeEffect")}
      </button>
    </fieldset>
  );
}

function QuestionEditor({
  q,
  index,
  before,
  instructions,
  onChange,
  onRemove,
  onMove,
  last,
}: {
  q: CardQuestion;
  index: number;
  before: CardQuestion[];
  instructions: string[];
  onChange: (q: CardQuestion) => void;
  onRemove: () => void;
  onMove: (up: boolean) => void;
  last: boolean;
}) {
  const { t } = useTranslation();
  const id = useId();
  const set = (patch: Partial<CardQuestion>) => onChange({ ...q, ...patch });
  return (
    <li className="card call-card-editor__q">
      <div className="call-card-editor__qhead">
        <strong>{t("callCards.edit.question", { n: index + 1 })}</strong>
        <button type="button" className="btn btn--small" disabled={index === 0} onClick={() => onMove(true)}>
          {t("callCards.edit.up")}
        </button>
        <button type="button" className="btn btn--small" disabled={last} onClick={() => onMove(false)}>
          {t("callCards.edit.down")}
        </button>
        <button type="button" className="btn btn--small btn--danger" onClick={onRemove}>
          {t("callCards.edit.remove")}
        </button>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-text`}>{t("callCards.edit.text")}</label>
          <input id={`${id}-text`} value={q.text} maxLength={400} onChange={(e) => set({ text: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-help`}>{t("callCards.edit.help")}</label>
          <input
            id={`${id}-help`}
            value={q.help ?? ""}
            maxLength={200}
            onChange={(e) => set({ help: e.target.value || null })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-id`}>{t("callCards.edit.id")}</label>
          <input id={`${id}-id`} dir="ltr" value={q.id} maxLength={40} onChange={(e) => set({ id: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-when`}>{t("callCards.edit.when")}</label>
          <select
            id={`${id}-when`}
            value={q.when ? `${q.when.question}:${q.when.answer}` : ""}
            onChange={(e) => {
              const [question, answer] = e.target.value.split(":");
              set({ when: question ? { question, answer: answer as CardAnswer } : null });
            }}
          >
            <option value="">{t("callCards.edit.always")}</option>
            {before.flatMap((b) =>
              ANSWERS.map((a) => (
                <option key={`${b.id}:${a}`} value={`${b.id}:${a}`}>
                  {t("callCards.edit.after", { question: b.text || b.id, answer: t(`callCards.answer.${a}`) })}
                </option>
              )),
            )}
          </select>
        </div>
      </div>
      <label className="call-card-editor__check">
        <input type="checkbox" checked={q.key} onChange={(e) => set({ key: e.target.checked })} />
        {t("callCards.edit.key")}
      </label>
      {ANSWERS.map((a) => (
        <EffectEditor
          key={a}
          answer={a}
          effect={q.effects[a]}
          instructions={instructions}
          onChange={(e) => {
            const effects: CardQuestion["effects"] = {};
            for (const x of ANSWERS) {
              const kept = x === a ? e : q.effects[x];
              if (kept) effects[x] = kept;
            }
            set({ effects });
          }}
        />
      ))}
    </li>
  );
}

function ContentEditor({ content, onChange }: { content: CardContent; onChange: (c: CardContent) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const set = (patch: Partial<CardContent>) => onChange({ ...content, ...patch });
  const keys = Object.keys(content.instructions);
  const setQuestion = (i: number, q: CardQuestion) =>
    set({ questions: content.questions.map((x, j) => (j === i ? q : x)) });
  const move = (i: number, up: boolean) => {
    const qs = [...content.questions];
    const j = up ? i - 1 : i + 1;
    const a = qs[i];
    const b = qs[j];
    if (!a || !b) return;
    qs[i] = b;
    qs[j] = a;
    set({ questions: qs });
  };
  return (
    <div className="call-card-editor">
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-title`}>{t("callCards.edit.title")}</label>
          <input id={`${id}-title`} value={content.title} maxLength={200} onChange={(e) => set({ title: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-band`}>{t("callCards.edit.baseBand")}</label>
          <select id={`${id}-band`} value={content.base_band} onChange={(e) => set({ base_band: e.target.value as CardBand })}>
            {CARD_BANDS.map((b) => (
              <option key={b} value={b}>
                {t(`callCards.band.${b}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-means`}>{t("callCards.edit.baseMeans")}</label>
        <LinesArea id={`${id}-means`} rows={2} value={content.base_means} onChange={(v) => set({ base_means: v })} />
      </div>
      <h3>{t("callCards.edit.questions")}</h3>
      <ol className="call-card-editor__qs">
        {content.questions.map((q, i) => (
          <QuestionEditor
            key={i}
            q={q}
            index={i}
            before={content.questions.slice(0, i)}
            instructions={keys}
            last={i === content.questions.length - 1}
            onChange={(x) => setQuestion(i, x)}
            onRemove={() => set({ questions: content.questions.filter((_, j) => j !== i) })}
            onMove={(up) => move(i, up)}
          />
        ))}
      </ol>
      <button
        type="button"
        className="btn"
        onClick={() => set({ questions: [...content.questions, emptyQuestion(`q${content.questions.length + 1}`)] })}
      >
        {t("callCards.edit.addQuestion")}
      </button>
      <h3>{t("callCards.edit.instructions")}</h3>
      {Object.entries(content.instructions).map(([k, ins]) => {
        const setIns = (patch: Partial<CardInstruction>) =>
          set({ instructions: { ...content.instructions, [k]: { ...ins, ...patch } } });
        return (
          <fieldset key={k} className="card call-card-editor__ins">
            <legend dir="ltr">{k}</legend>
            <div className="form-grid">
              <div className="field">
                <label htmlFor={`${id}-${k}-t`}>{t("callCards.edit.insTitle")}</label>
                <input id={`${id}-${k}-t`} value={ins.title} onChange={(e) => setIns({ title: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor={`${id}-${k}-m`}>{t("callCards.edit.metronome")}</label>
                <input
                  id={`${id}-${k}-m`}
                  type="number"
                  min={60}
                  max={140}
                  value={ins.metronome ?? ""}
                  onChange={(e) => setIns({ metronome: e.target.value ? Number(e.target.value) : null })}
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor={`${id}-${k}-s`}>{t("callCards.edit.steps")}</label>
              <LinesArea id={`${id}-${k}-s`} rows={4} value={ins.steps} onChange={(v) => setIns({ steps: v })} />
            </div>
            <label className="call-card-editor__check">
              <input type="checkbox" checked={ins.medical} onChange={(e) => setIns({ medical: e.target.checked })} />
              {t("callCards.edit.medical")}
            </label>
            <button
              type="button"
              className="btn btn--small btn--danger"
              onClick={() => {
                set({ instructions: Object.fromEntries(Object.entries(content.instructions).filter(([x]) => x !== k)) });
              }}
            >
              {t("callCards.edit.removeInstruction")}
            </button>
          </fieldset>
        );
      })}
      <AddInstruction taken={keys} onAdd={(k) => set({ instructions: { ...content.instructions, [k]: { title: "", steps: [], medical: false, metronome: null } } })} />
    </div>
  );
}

function AddInstruction({ taken, onAdd }: { taken: string[]; onAdd: (key: string) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const [key, setKey] = useState("");
  const ok = /^[a-z][a-z0-9_]{0,39}$/.test(key) && !taken.includes(key);
  return (
    <div className="call-card-editor__add">
      <label htmlFor={id}>{t("callCards.edit.newInstruction")}</label>
      <input id={id} dir="ltr" value={key} maxLength={40} onChange={(e) => setKey(e.target.value.trim())} />
      <button
        type="button"
        className="btn btn--small"
        disabled={!ok}
        onClick={() => {
          onAdd(key);
          setKey("");
        }}
      >
        {t("callCards.edit.addInstruction")}
      </button>
    </div>
  );
}

/** A reason, then the action (validate, approve, save). */
function ReasonButton({
  label,
  explain,
  pending,
  onGo,
  primary,
}: {
  label: string;
  explain: string;
  pending: boolean;
  onGo: (reason: string) => void;
  primary?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  if (!open) {
    return (
      <button type="button" className={`btn${primary ? " btn--primary" : ""}`} onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  }
  return (
    <div className="card call-cards__reason">
      <p className="muted">{explain}</p>
      <ReasonField label={t("callCards.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <div className="form-actions">
        <button
          type="button"
          className={`btn${primary ? " btn--primary" : ""}`}
          disabled={pending}
          onClick={() => {
            setTried(true);
            if (reasonValid(reason)) onGo(reason.trim());
          }}
        >
          {label}
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </button>
      </div>
    </div>
  );
}

function CardDetail({ category, cards }: { category: Category; cards: CallCard[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const rights = callCardRights({
    roles: user?.identity.roles ?? [],
    gouvernoratCode: user?.identity.gouvernoratCode ?? null,
  });
  const approved = cards.find((c) => c.status === "approved") ?? null;
  const draft = cards.find((c) => c.status === "draft") ?? null;
  const [editing, setEditing] = useState<CardContent | null>(null);
  const [trial, setTrial] = useState<Answers>({});
  const [trialRead, setTrialRead] = useState<string[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const shown = draft ?? approved;
  const done = () => {
    setEditing(null);
    setProblem(null);
    void qc.invalidateQueries({ queryKey: callCardKeys.all });
  };
  const act = useMutation({ mutationFn: (fn: () => Promise<unknown>) => fn(), onSuccess: done });
  const save = (reason: string) => {
    if (!editing) return;
    const error = checkContent(editing);
    setProblem(error);
    if (error) return;
    act.mutate(() =>
      draft
        ? api.updateCardDraft(draft.id, editing, reason, draft.updated_at)
        : api.createCardDraft(category, editing, reason),
    );
  };
  return (
    <section className="card call-cards__detail" aria-label={t(`category.${category}`)}>
      <div className="call-cards__detail-head">
        <IconTile name={CATEGORY_ICON[category][0]} tone={CATEGORY_ICON[category][1]} />
        <h2>{shown?.content.title ?? t(`category.${category}`)}</h2>
        {shown && <StatusPill card={shown} />}
        {shown?.sim && <span className="tag tag--sim">[SIM]</span>}
      </div>
      {approved && (
        <p className="muted">
          {t("callCards.approvedLine", {
            version: approved.version,
            by: approved.approved_by ?? "—",
            at: approved.approved_at ? fmt.dateTime(approved.approved_at) : "—",
          })}
        </p>
      )}
      {draft && (
        <div className="alert alert--warn">
          {t("callCards.draftLine", { version: draft.version, by: draft.updated_by_name ?? draft.created_by_name ?? "—" })}
          {draft.medical && (
            <div>
              {draft.medical_validated_at
                ? t("callCards.medicalDone", { by: draft.medical_validated_by ?? "—", reason: draft.medical_reason ?? "" })
                : t("callCards.medicalPending")}
            </div>
          )}
        </div>
      )}
      {act.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(act.error))}
        </p>
      )}
      {problem && (
        <p className="alert alert--error" role="alert">
          {t(problem)}
        </p>
      )}

      {editing ? (
        <>
          <ContentEditor content={editing} onChange={setEditing} />
          <div className="form-actions">
            <ReasonButton
              primary
              label={t("callCards.saveDraft")}
              explain={t("callCards.saveExplain")}
              pending={act.isPending}
              onGo={save}
            />
            <button type="button" className="btn" onClick={() => setEditing(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </>
      ) : (
        <div className="form-actions call-cards__actions">
          {rights.edit && (
            <button
              type="button"
              className="btn"
              onClick={() =>
                setEditing(structuredClone((draft ?? approved)?.content ?? emptyContent(t(`category.${category}`))))
              }
            >
              {draft ? t("callCards.editDraft") : t("callCards.newVersion")}
            </button>
          )}
          {draft && rights.edit && (
            <button type="button" className="btn btn--danger" onClick={() => act.mutate(() => api.discardCardDraft(draft.id))}>
              {t("callCards.discard")}
            </button>
          )}
          {draft?.medical && !draft.medical_validated_at && rights.validate && (
            <ReasonButton
              label={t("callCards.validate")}
              explain={t("callCards.validateExplain")}
              pending={act.isPending}
              onGo={(r) => act.mutate(() => api.validateCardMedical(draft.id, r, draft.updated_at))}
            />
          )}
          {draft && rights.approve && (
            <ReasonButton
              primary
              label={t("callCards.approve")}
              explain={t("callCards.approveExplain")}
              pending={act.isPending}
              onGo={(r) => act.mutate(() => api.approveCard(draft.id, r, draft.updated_at))}
            />
          )}
        </div>
      )}

      {shown && !editing && (
        <>
          <h3>{draft ? t("callCards.trialDraft") : t("callCards.trial")}</h3>
          <p className="muted">{t("callCards.trialHint")}</p>
          <CallCardPanel card={shown} answers={trial} onAnswers={setTrial} read={trialRead} onRead={setTrialRead} />
        </>
      )}
    </section>
  );
}

export function CallCardsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const [include, setInclude] = useState<"current" | "all">("current");
  const [category, setCategory] = useState<Category>("medical");
  const q = useQuery({
    queryKey: callCardKeys.list(include),
    queryFn: ({ signal }) => api.callCards(include, signal),
  });
  const cards = q.data?.cards ?? [];
  return (
    <div className="page">
      <PageTitle print icon="call" tone="navy">
        {t("callCards.title")}
      </PageTitle>
      <p className="muted">{t("callCards.intro")}</p>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorBox error={q.error} />
      ) : (
        <div className="call-cards">
          <section className="card">
            <div className="call-cards__table-head">
              <h2>{t("callCards.list")}</h2>
              <label className="call-card-editor__check">
                <input
                  type="checkbox"
                  checked={include === "all"}
                  onChange={(e) => setInclude(e.target.checked ? "all" : "current")}
                />
                {t("callCards.history")}
              </label>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>{t("callCards.col.card")}</th>
                  <th>{t("callCards.col.version")}</th>
                  <th>{t("callCards.col.questions")}</th>
                  <th>{t("callCards.col.status")}</th>
                  <th>{t("callCards.col.used")}</th>
                </tr>
              </thead>
              <tbody>
                {CATEGORIES.flatMap((c) =>
                  cards
                    .filter((card) => card.category === c)
                    .map((card) => (
                      <tr key={card.id} className={c === category ? "row--selected" : undefined}>
                        <td>
                          <button type="button" className="call-cards__pick" onClick={() => setCategory(c)} aria-pressed={c === category}>
                            <IconTile name={CATEGORY_ICON[c][0]} tone={CATEGORY_ICON[c][1]} size="sm" />
                            {card.content.title}
                          </button>
                        </td>
                        <td>
                          {card.version} {card.sim && <span className="tag tag--sim">[SIM]</span>}
                        </td>
                        <td>
                          {card.content.questions.length} ({t("callCards.keyCount", { n: card.content.questions.filter((x) => x.key).length })})
                        </td>
                        <td>
                          <StatusPill card={card} />
                        </td>
                        <td>{card.used}</td>
                      </tr>
                    )),
                )}
              </tbody>
            </table>
          </section>
          <CardDetail key={category} category={category} cards={cards.filter((c) => c.category === category)} />
        </div>
      )}
    </div>
  );
}
