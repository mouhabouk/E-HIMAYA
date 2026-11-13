// covers: OS2-4 (Yamen 2026-11-13, docs/phase-os2b/design-os2b.md §3): the review of the nine [SIM] call-taking cards.
// Each card goes from the Office (a draft, or the [SIM] text confirmed as it is, with a note per question) to the
// doctor (medical cards) and to the room manager, who approves it; the [SIM] badge goes with the approval. The
// doctor or the manager can send a draft back with a note. The reviewers are named per card, the changes are shown
// against the approved version with the statistics of each question (OS2-3), and a printable pack serves a review
// on paper. Nothing here changes a card's content by itself.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  ANSWERS,
  CARD_NOTE,
  callCardKeys,
  percent,
  questionChanges,
  stepChanges,
  type CallCard,
  type CardChange,
  type CardContent,
  type CardFigures,
  type ReviewItem,
  type ReviewStage,
} from "../lib/callCards";
import { CATEGORY_TILE } from "../lib/categoryIcons";
import { useFormat } from "../lib/hooks";
import { reasonValid } from "../lib/phase9";
import { callCardRights } from "../lib/roles";
import { ErrorBox, Loading } from "./Feedback";
import { IconTile } from "./Icon";
import { ReasonField } from "./Phase9Bits";

/** A reason, then the action (validate, approve, save, hand over, send back). */
export function ReasonButton({
  label,
  explain,
  pending,
  onGo,
  primary,
  danger,
}: {
  label: string;
  explain: string;
  pending: boolean;
  onGo: (reason: string) => void;
  primary?: boolean;
  danger?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const tone = primary ? " btn--primary" : danger ? " btn--danger" : "";
  if (!open) {
    return (
      <button type="button" className={`btn${tone}`} onClick={() => setOpen(true)}>
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
          className={`btn${tone}`}
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

const STAGE_TONE: Record<ReviewStage, string> = {
  not_started: "slate",
  office: "navy",
  doctor: "amber",
  approval: "purple",
  done: "green",
};

type Step = "office" | "doctor" | "approval";

/** The three steps of a card: done, current, to do, or not needed (the doctor of a card without medical text). */
function Steps({ item }: { item: ReviewItem }) {
  const { t } = useTranslation();
  const order: Step[] = ["office", "doctor", "approval"];
  const at = item.stage === "done" ? 3 : item.stage === "not_started" ? -1 : order.indexOf(item.stage);
  return (
    <ol className="cc-steps" aria-label={t("callCards.review.path")}>
      {order.map((s, i) => {
        const skipped = s === "doctor" && !item.medical;
        const state = skipped ? "na" : i < at ? "done" : i === at ? "now" : "todo";
        const label =
          s === "office" && state === "done" && (item.draft?.unchanged || item.approved?.unchanged)
            ? t("callCards.review.step.officeUnchanged")
            : t(`callCards.review.step.${s}`);
        return (
          <li key={s} className={`cc-step cc-step--${state}`}>
            <span className="visually-hidden">{t(`callCards.review.stepState.${state}`)} </span>
            {state === "done" ? "✓ " : state === "now" ? "● " : ""}
            {label}
          </li>
        );
      })}
    </ol>
  );
}

/** Names of who reviews a card (the Office's reviewer, the doctor). */
function Reviewers({ item, onClose }: { item: ReviewItem; onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [office, setOffice] = useState(item.office ?? "");
  const [doctor, setDoctor] = useState(item.doctor ?? "");
  const save = useMutation({
    mutationFn: (reason: string) =>
      api.setCardReviewers(item.category, office.trim() || null, doctor.trim() || null, reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: callCardKeys.review });
      onClose();
    },
  });
  return (
    <div className="card cc-reviewers">
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-o`}>{t("callCards.review.office")}</label>
          <input id={`${id}-o`} value={office} maxLength={200} onChange={(e) => setOffice(e.target.value)} />
        </div>
        {item.medical && (
          <div className="field">
            <label htmlFor={`${id}-d`}>{t("callCards.review.doctor")}</label>
            <input id={`${id}-d`} value={doctor} maxLength={200} onChange={(e) => setDoctor(e.target.value)} />
          </div>
        )}
      </div>
      {save.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="form-actions">
        <ReasonButton primary label={t("callCards.review.saveReviewers")} explain={t("callCards.review.reviewersExplain")} pending={save.isPending} onGo={(r) => save.mutate(r)} />
        <button type="button" className="btn" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
    </div>
  );
}

/** One question's figures, in a line (OS2-3), beside its change. */
function QuestionFigures({ figures, id }: { figures: CardFigures | undefined; id: string }) {
  const { t } = useTranslation();
  const q = figures?.questions.find((x) => x.id === id);
  if (!q) return null;
  const n = q.yes + q.no + q.unknown;
  if (n === 0) return <span className="muted small">{t("callCards.stats.notAsked")}</span>;
  const unknown = percent(q.unknown, n) ?? 0;
  return (
    <span className="cc-q__meta">
      <span className={`pill tone-${unknown >= 20 ? "red" : unknown >= 10 ? "amber" : "green"}`}>
        {t("callCards.stats.unknown", { p: unknown })}
      </span>
      {q.field_answered > 0 && <span>{t("callCards.stats.fieldChanged", { p: percent(q.field_changed, q.field_answered) })}</span>}
    </span>
  );
}

/** A question's text: struck when removed, marked when new, both texts when it changed. */
function QuestionText({ change }: { change: CardChange }) {
  if (change.kind === "changed") {
    if (!change.fields.includes("text")) return <>{change.question.text}</>;
    return (
      <>
        <del className="cc-del">{change.before.text}</del> <ins className="cc-ins">{change.question.text}</ins>
      </>
    );
  }
  return change.kind === "removed" ? <del className="cc-del">{change.question.text}</del> : <ins className="cc-ins">{change.question.text}</ins>;
}

/** The draft against the approved version: changed, new and removed questions, and the instructions' steps. */
function Changes({ before, after, notes, figures }: { before: CardContent; after: CardContent; notes: Record<string, string>; figures: CardFigures | undefined }) {
  const { t } = useTranslation();
  const changes = questionChanges(before, after);
  const instructions = Object.entries(after.instructions)
    .map(([k, ins]) => ({ k, ins, steps: stepChanges(before.instructions[k]?.steps ?? [], ins.steps) }))
    .filter((x) => !before.instructions[x.k] || x.steps.some((s) => s.mark !== "same"));
  return (
    <div className="cc-diff">
      <div>
        {changes.length === 0 && <p className="muted">{t("callCards.review.noQuestionChange")}</p>}
        {changes.map((c) => (
          <div key={`${c.kind}-${c.question.id}`} className={`cc-q${c.question.key ? " cc-q--key" : ""}`}>
            <div className="cc-q__text">
              <QuestionText change={c} />
              <span className={`pill tone-${c.kind === "added" ? "green" : c.kind === "removed" ? "red" : "navy"}`}>
                {t(`callCards.review.change.${c.kind}`)}
              </span>
            </div>
            {c.kind === "changed" && c.fields.includes("help") && (
              <p className="small">
                {t("callCards.edit.help")}: {c.before.help && <del className="cc-del">{c.before.help}</del>}{" "}
                {c.question.help && <ins className="cc-ins">{c.question.help}</ins>}
              </p>
            )}
            {c.kind === "changed" && c.fields.some((f) => f !== "text" && f !== "help") && (
              <p className="small muted">
                {t("callCards.review.alsoChanged", {
                  what: c.fields
                    .filter((f) => f !== "text" && f !== "help")
                    .map((f) => t(`callCards.review.field.${f}`))
                    .join("، "),
                })}
              </p>
            )}
            {c.kind !== "added" && <QuestionFigures figures={figures} id={c.question.id} />}
            {notes[c.question.id] && <p className="cc-note">{t("callCards.review.officeNote", { note: notes[c.question.id] })}</p>}
          </div>
        ))}
      </div>
      <div>
        {instructions.map(({ k, ins, steps }) => (
          <div key={k} className="cc-q cc-q--ins">
            <div className="cc-q__text">
              {ins.medical && <span aria-hidden="true">✚ </span>}
              {ins.title}
              {!before.instructions[k] && <span className="pill tone-green">{t("callCards.review.change.added")}</span>}
            </div>
            <ol className="small">
              {steps.map((s, i) => (
                <li key={i}>{s.mark === "added" ? <ins className="cc-ins">{s.text}</ins> : s.mark === "removed" ? <del className="cc-del">{s.text}</del> : s.text}</li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </div>
  );
}

/** The Office's notes on a draft, per question, saved with the draft (handing it over again afterwards). */
function NotesEditor({ draft }: { draft: CallCard }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [notes, setNotes] = useState<Record<string, string>>(draft.notes ?? {});
  const save = useMutation({
    mutationFn: (reason: string) => {
      const kept = Object.fromEntries(Object.entries(notes).filter(([, v]) => v.trim()).map(([k, v]) => [k, v.trim()]));
      return api.updateCardDraft(draft.id, draft.content, reason, draft.updated_at, kept);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: callCardKeys.all }),
  });
  const keys = [CARD_NOTE, ...draft.content.questions.map((q) => q.id)];
  return (
    <details className="cc-notes">
      <summary>{t("callCards.review.notes")}</summary>
      {keys.map((k) => {
        const q = draft.content.questions.find((x) => x.id === k);
        return (
          <div key={k} className="field">
            <label htmlFor={`${id}-${k}`}>{q ? q.text : t("callCards.review.cardNote")}</label>
            <textarea id={`${id}-${k}`} rows={2} maxLength={500} value={notes[k] ?? ""} onChange={(e) => setNotes({ ...notes, [k]: e.target.value })} />
          </div>
        );
      })}
      {save.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <ReasonButton label={t("callCards.review.saveNotes")} explain={t("callCards.review.saveNotesExplain")} pending={save.isPending} onGo={(r) => save.mutate(r)} />
    </details>
  );
}

function ReviewDetail({ item, figures, onWrite }: { item: ReviewItem; figures: CardFigures | undefined; onWrite: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const rights = callCardRights({ roles: user?.identity.roles ?? [], gouvernoratCode: user?.identity.gouvernoratCode ?? null });
  const roles = user?.identity.roles ?? [];
  const mayReturn = rights.approve || ((user?.identity.gouvernoratCode ?? null) === null && roles.includes("medical_coordinator"));
  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => void qc.invalidateQueries({ queryKey: callCardKeys.all }),
  });
  const { draft, approved } = item;
  const notes = draft?.notes ?? {};
  return (
    <section className="card cc-review-detail" aria-label={item.title}>
      <div className="call-cards__detail-head">
        <IconTile name={CATEGORY_TILE[item.category][0]} tone={CATEGORY_TILE[item.category][1]} />
        <h2>
          {item.title}
          {draft && ` · ${t("callCards.review.draftVersion", { version: draft.version })}`}
        </h2>
        <span className={`pill tone-${STAGE_TONE[item.stage]}`}>{t(`callCards.review.stage.${item.stage}`)}</span>
        {(draft ?? approved)?.sim && <span className="tag tag--sim">[SIM]</span>}
      </div>
      {draft && (
        <p className="muted">
          {t("callCards.review.writtenBy", {
            by: draft.updated_by_name ?? draft.created_by_name ?? "—",
            at: fmt.dateTime(draft.updated_at),
          })}
          {draft.unchanged && ` ${t("callCards.review.unchangedNote")}`}
        </p>
      )}
      {draft?.returned_reason && (
        <p className="alert alert--warn" role="status">
          {t("callCards.review.returned", { by: draft.returned_by_name ?? "—", reason: draft.returned_reason })}
        </p>
      )}
      {notes[CARD_NOTE] && <p className="cc-note">{t("callCards.review.officeNote", { note: notes[CARD_NOTE] })}</p>}
      {act.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(act.error))}
        </p>
      )}

      {draft && approved ? (
        <Changes before={approved.content} after={draft.content} notes={notes} figures={figures} />
      ) : (
        <p className="muted">{t(item.stage === "done" ? "callCards.review.doneHint" : "callCards.review.notStartedHint")}</p>
      )}

      {draft?.medical && draft.medical_validated_at && (
        <p className="alert alert--ok">
          {t("callCards.medicalDone", { by: draft.medical_validated_by ?? "—", reason: draft.medical_reason ?? "" })}
        </p>
      )}

      <div className="form-actions call-cards__actions">
        {!draft && rights.edit && approved?.sim && (
          <ReasonButton
            label={t("callCards.review.confirm")}
            explain={t("callCards.review.confirmExplain")}
            pending={act.isPending}
            onGo={(r) => act.mutate(() => api.confirmCard(item.category, r))}
          />
        )}
        {!draft && rights.edit && (
          <button type="button" className="btn" onClick={onWrite}>
            {t("callCards.review.write")}
          </button>
        )}
        {draft && item.stage === "office" && rights.edit && (
          <>
            <button type="button" className="btn" onClick={onWrite}>
              {t("callCards.editDraft")}
            </button>
            <ReasonButton
              primary
              label={t("callCards.review.submit")}
              explain={t(item.medical ? "callCards.review.submitExplainDoctor" : "callCards.review.submitExplain")}
              pending={act.isPending}
              onGo={(r) => act.mutate(() => api.submitCard(draft.id, r, draft.updated_at))}
            />
          </>
        )}
        {draft && item.stage === "doctor" && rights.validate && (
          <ReasonButton
            primary
            label={t("callCards.validate")}
            explain={t("callCards.validateExplain")}
            pending={act.isPending}
            onGo={(r) => act.mutate(() => api.validateCardMedical(draft.id, r, draft.updated_at))}
          />
        )}
        {draft && item.stage === "approval" && rights.approve && (
          <ReasonButton
            primary
            label={t("callCards.approve")}
            explain={t("callCards.review.approveExplain")}
            pending={act.isPending}
            onGo={(r) => act.mutate(() => api.approveCard(draft.id, r, draft.updated_at))}
          />
        )}
        {draft && draft.submitted_at && mayReturn && (
          <ReasonButton
            danger
            label={t("callCards.review.return")}
            explain={t("callCards.review.returnExplain")}
            pending={act.isPending}
            onGo={(r) => act.mutate(() => api.returnCard(draft.id, r, draft.updated_at))}
          />
        )}
      </div>
      {draft && item.stage === "office" && rights.edit && <NotesEditor key={draft.updated_at} draft={draft} />}
    </section>
  );
}

/** Every card on paper, with room for the reviewer's notes: printed for a review away from the screen. */
function PaperPack({ items }: { items: ReviewItem[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="cc-pack" aria-hidden="true">
      <h1>{t("callCards.review.packTitle")}</h1>
      <p>{t("callCards.review.packIntro", { date: fmt.dateTime(new Date().toISOString()) })}</p>
      {items.map((item) => {
        const card = item.draft ?? item.approved;
        if (!card) return null;
        const c = card.content;
        return (
          <section key={item.category} className="cc-pack__card">
            <h2>
              {c.title} · {t("callCards.version", { version: card.version })} {card.sim && "[SIM]"}
            </h2>
            <p>
              {t("callCards.review.packStart", { band: t(`callCards.band.${c.base_band}`) })}
              {c.base_means.length > 0 && ` · ${c.base_means.join("، ")}`}
            </p>
            <table>
              <thead>
                <tr>
                  <th>{t("callCards.edit.questions")}</th>
                  <th>{t("callCards.review.packEffects")}</th>
                  <th>{t("callCards.review.packNotes")}</th>
                </tr>
              </thead>
              <tbody>
                {c.questions.map((q) => (
                  <tr key={q.id}>
                    <td>
                      {q.text}
                      {q.key && ` (${t("callCards.key")})`}
                      {q.help && <div className="small">{q.help}</div>}
                    </td>
                    <td>
                      {ANSWERS.filter((a) => q.effects[a]).map((a) => {
                        const e = q.effects[a];
                        return e ? (
                          <div key={a}>
                            {t(`callCards.answer.${a}`)}: {e.why}
                            {e.band && ` · ${t(`callCards.band.${e.band}`)}`}
                            {e.means.length > 0 && ` · ${e.means.join("، ")}`}
                          </div>
                        ) : null;
                      })}
                    </td>
                    <td className="cc-pack__blank" />
                  </tr>
                ))}
              </tbody>
            </table>
            {Object.entries(c.instructions).map(([k, ins]) => (
              <div key={k}>
                <strong>
                  {ins.medical && "✚ "}
                  {ins.title}
                </strong>
                <ol>
                  {ins.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            ))}
            <p className="cc-pack__sign">
              {t("callCards.review.packSign", { office: item.office ?? "……", doctor: item.medical ? (item.doctor ?? "……") : "—" })}
            </p>
          </section>
        );
      })}
    </div>
  );
}

export function CallCardReview({ figures, onWrite }: { figures: CardFigures[] | undefined; onWrite: (category: ReviewItem["category"]) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const rights = callCardRights({ roles: user?.identity.roles ?? [], gouvernoratCode: user?.identity.gouvernoratCode ?? null });
  const q = useQuery({ queryKey: callCardKeys.review, queryFn: ({ signal }) => api.cardReview(signal) });
  const [open, setOpen] = useState<string | null>(null);
  const [naming, setNaming] = useState<string | null>(null);
  const [printing, setPrinting] = useState(false);
  useEffect(() => {
    if (!printing) return;
    const root = document.documentElement;
    root.classList.add("cc-printing-pack");
    const done = () => {
      root.classList.remove("cc-printing-pack");
      setPrinting(false);
    };
    window.addEventListener("afterprint", done);
    window.print();
    return () => {
      window.removeEventListener("afterprint", done);
      root.classList.remove("cc-printing-pack");
    };
  }, [printing]);
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} />;
  const review = q.data;
  const item = review.items.find((i) => i.category === open) ?? review.items.find((i) => i.stage !== "done" && i.stage !== "not_started") ?? null;
  const share = percent(review.done, review.total) ?? 0;
  return (
    <div className="cc-review">
      <section className="card">
        <div className="cc-review__head">
          <div className="cc-ring" role="img" aria-label={t("callCards.review.progress", { done: review.done, total: review.total })} style={{ ["--p" as string]: `${share}%` }}>
            <span>
              {review.done}/{review.total}
            </span>
          </div>
          <div>
            <h2>{t("callCards.review.title")}</h2>
            <p className="muted">{t("callCards.review.intro")}</p>
          </div>
          <button type="button" className="btn cc-review__pack" onClick={() => setPrinting(true)}>
            {t("callCards.review.pack")}
          </button>
        </div>
        <p className="alert alert--warn">{t("callCards.review.waiting")}</p>
      </section>

      <section className="card">
        <h2>{t("callCards.list")}</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("callCards.col.card")}</th>
                <th>{t("callCards.review.reviewers")}</th>
                <th>{t("callCards.review.path")}</th>
                <th>{t("callCards.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {review.items.map((i) => (
                <tr key={i.category} className={item?.category === i.category ? "row--selected" : undefined}>
                  <td>
                    <button type="button" className="call-cards__pick" aria-pressed={item?.category === i.category} onClick={() => setOpen(i.category)}>
                      <IconTile name={CATEGORY_TILE[i.category][0]} tone={CATEGORY_TILE[i.category][1]} size="sm" />
                      {i.title}
                    </button>
                  </td>
                  <td>
                    {[i.office, i.medical ? i.doctor : null].filter(Boolean).join("، ") || "—"}{" "}
                    {rights.edit && (
                      <button type="button" className="btn btn--small" onClick={() => setNaming(naming === i.category ? null : i.category)}>
                        {t("callCards.review.name")}
                      </button>
                    )}
                    {naming === i.category && <Reviewers item={i} onClose={() => setNaming(null)} />}
                  </td>
                  <td>
                    <Steps item={i} />
                  </td>
                  <td>
                    <span className={`pill tone-${STAGE_TONE[i.stage]}`}>
                      {t(`callCards.review.stage.${i.stage}`)}
                      {i.stage === "done" && i.approved && ` · ${t("callCards.version", { version: i.approved.version })}`}
                    </span>{" "}
                    {i.stage === "not_started" && <span className="tag tag--sim">[SIM]</span>}
                    {i.draft?.returned_reason && <span className="pill tone-red">{t("callCards.review.returnedShort")}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">{t("callCards.review.legend")}</p>
      </section>

      {item && <ReviewDetail key={item.category} item={item} figures={figures?.find((f) => f.category === item.category)} onWrite={() => onWrite(item.category)} />}
      {printing && <PaperPack items={review.items} />}
    </div>
  );
}
