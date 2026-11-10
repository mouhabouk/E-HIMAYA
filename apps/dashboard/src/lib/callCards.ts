/**
 * Guided call-taking cards (OS2, docs/phase-os2/design-os2.md): types and calls of `/api/v1/staff/call-cards`, and
 * the same rules as the server (`services/api/app/modules/reports/callcards.py`) so the room sees the band, the
 * flags, the suggested resources and the instructions while the call goes on. The server checks them again.
 */

import type { ApiClient } from "./api";
import type { Category } from "./types";

export const CARD_BANDS = ["low", "normal", "high", "critical"] as const;
export type CardBand = (typeof CARD_BANDS)[number];
export const ANSWERS = ["yes", "no", "unknown"] as const;
export type CardAnswer = (typeof ANSWERS)[number];
/** A decisive question answered «unknown» keeps the band at this level at least. */
export const UNKNOWN_KEY_FLOOR: CardBand = "high";

export interface CardEffect {
  why: string;
  band: CardBand | null;
  flag: string | null;
  means: string[];
  instruction: string | null;
  lives: boolean;
  injured: boolean;
}

export interface CardQuestion {
  id: string;
  text: string;
  help: string | null;
  key: boolean;
  when: { question: string; answer: CardAnswer } | null;
  effects: Partial<Record<CardAnswer, CardEffect>>;
}

export interface CardInstruction {
  title: string;
  steps: string[];
  medical: boolean;
  metronome: number | null;
}

export interface CardContent {
  title: string;
  base_band: CardBand;
  base_means: string[];
  questions: CardQuestion[];
  instructions: Record<string, CardInstruction>;
}

export type CardStatus = "draft" | "approved" | "retired";

export interface CallCard {
  id: string;
  category: Category;
  version: number;
  status: CardStatus;
  content: CardContent;
  sim: boolean;
  medical: boolean;
  medical_validated_by: string | null;
  medical_validated_at: string | null;
  medical_reason: string | null;
  approved_by: string | null;
  approved_at: string | null;
  approval_reason: string | null;
  created_by_name: string | null;
  updated_by_name: string | null;
  updated_at: string;
  used: number;
}

export interface CardOutcome {
  band: CardBand;
  flags: string[];
  reasons: string[];
  means: string[];
  instructions: string[];
  lives: boolean;
  injured: boolean;
  answered: number;
  asked: number;
}

export interface ReportCallCard {
  card_id: string;
  category: Category;
  card_version: number;
  sim: boolean;
  title: string;
  answers: Record<string, CardAnswer>;
  outcome: CardOutcome;
  questions: CardQuestion[];
  instructions: Record<string, CardInstruction>;
  created_at: string;
}

/** What the intake form sends with the report. */
export interface CallCardBody {
  card_id: string;
  version: number;
  answers: Record<string, CardAnswer>;
  read: string[];
}

export type Answers = Partial<Record<string, CardAnswer>>;

const rank = (b: CardBand) => CARD_BANDS.indexOf(b);
export const higher = (a: CardBand, b: CardBand | null | undefined): CardBand => (b && rank(b) > rank(a) ? b : a);

/** The questions shown for these answers: a follow-up only once the question it follows got its answer. */
export function askedQuestions(content: CardContent, answers: Answers): CardQuestion[] {
  return content.questions.filter((q) => !q.when || answers[q.when.question] === q.when.answer);
}

/** Answers of the questions still shown (a follow-up whose condition went away loses its answer). */
export function shownAnswers(content: CardContent, answers: Answers): Record<string, CardAnswer> {
  const out: Record<string, CardAnswer> = {};
  for (const q of askedQuestions(content, answers)) {
    const a = answers[q.id];
    if (a) out[q.id] = a;
  }
  return out;
}

/** Reasons are returned as keys the page translates: `start`, `effect` (with the card's own words) or `unknown`. */
export type Reason =
  | { kind: "start"; band: CardBand }
  | { kind: "effect"; why: string; band: CardBand | null }
  | { kind: "unknown"; band: CardBand };

export interface Evaluation extends Omit<CardOutcome, "reasons"> {
  reasons: Reason[];
}

export function evaluate(content: CardContent, answers: Answers): Evaluation {
  let band = content.base_band;
  const reasons: Reason[] = [{ kind: "start", band }];
  const flags: string[] = [];
  const means = [...content.base_means];
  const instructions: string[] = [];
  let lives = false;
  let injured = false;
  const shown = askedQuestions(content, answers);
  for (const q of shown) {
    const a = answers[q.id];
    const effect = a ? q.effects[a] : undefined;
    if (!effect) continue;
    band = higher(band, effect.band);
    reasons.push({ kind: "effect", why: effect.why, band: effect.band });
    if (effect.flag && !flags.includes(effect.flag)) flags.push(effect.flag);
    for (const m of effect.means) if (!means.includes(m)) means.push(m);
    if (effect.instruction && !instructions.includes(effect.instruction)) instructions.push(effect.instruction);
    lives ||= effect.lives;
    injured ||= effect.injured;
  }
  if (shown.some((q) => q.key && answers[q.id] === "unknown") && rank(UNKNOWN_KEY_FLOOR) > rank(band)) {
    band = UNKNOWN_KEY_FLOOR;
    reasons.push({ kind: "unknown", band });
  }
  return {
    band,
    flags,
    reasons,
    means,
    instructions,
    lives,
    injured,
    answered: shown.filter((q) => answers[q.id]).length,
    asked: shown.length,
  };
}

/** An empty card of a category, for the first version the Office writes. */
export function emptyContent(title: string): CardContent {
  return {
    title,
    base_band: "normal",
    base_means: [],
    questions: [emptyQuestion("q1")],
    instructions: {},
  };
}

export function emptyQuestion(id: string): CardQuestion {
  return { id, text: "", help: null, key: false, when: null, effects: {} };
}

export function emptyEffect(): CardEffect {
  return { why: "", band: null, flag: null, means: [], instruction: null, lives: false, injured: false };
}

/** First problem of a card being edited, as an i18n key, or null when the server should accept it. */
export function checkContent(content: CardContent): string | null {
  if (!content.title.trim()) return "callCards.errors.title";
  if (content.questions.length === 0) return "callCards.errors.noQuestion";
  const seen = new Set<string>();
  for (const q of content.questions) {
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(q.id) || seen.has(q.id)) return "callCards.errors.questionId";
    if (!q.text.trim()) return "callCards.errors.questionText";
    if (q.when && !seen.has(q.when.question)) return "callCards.errors.followUp";
    for (const e of Object.values(q.effects)) {
      if (!e.why.trim()) return "callCards.errors.why";
      if (e.instruction && !content.instructions[e.instruction]) return "callCards.errors.instruction";
    }
    seen.add(q.id);
  }
  for (const [key, ins] of Object.entries(content.instructions)) {
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(key)) return "callCards.errors.instructionKey";
    if (!ins.title.trim() || ins.steps.length === 0) return "callCards.errors.instructionText";
  }
  return null;
}

export const callCardKeys = {
  all: ["call-cards"] as const,
  list: (include: "current" | "all") => ["call-cards", include] as const,
  report: (id: string) => ["call-cards", "report", id] as const,
};

const C = "/api/v1/staff/call-cards";
const cardPath = (id: string) => `${C}/${encodeURIComponent(id)}`;

export function callCardsApi(api: ApiClient) {
  return {
    callCards: (include: "current" | "all" = "current", signal?: AbortSignal) =>
      api.request<{ cards: CallCard[] }>(C, { query: { include }, signal }),
    createCardDraft: (category: Category, content: CardContent, reason: string) =>
      api.request<CallCard>(`${C}/${encodeURIComponent(category)}/draft`, {
        method: "POST",
        body: { content, reason },
      }),
    updateCardDraft: (id: string, content: CardContent, reason: string, updatedAt: string) =>
      api.request<CallCard>(cardPath(id), { method: "PUT", body: { content, reason, updated_at: updatedAt } }),
    discardCardDraft: (id: string) => api.request<undefined>(cardPath(id), { method: "DELETE" }),
    validateCardMedical: (id: string, reason: string, updatedAt: string) =>
      api.request<CallCard>(`${cardPath(id)}/medical-validation`, {
        method: "POST",
        body: { reason, updated_at: updatedAt },
      }),
    approveCard: (id: string, reason: string, updatedAt: string) =>
      api.request<CallCard>(`${cardPath(id)}/approve`, { method: "POST", body: { reason, updated_at: updatedAt } }),
    reportCallCard: (reportId: string, signal?: AbortSignal) =>
      api.request<ReportCallCard>(`/api/v1/staff/reports/${encodeURIComponent(reportId)}/call-card`, { signal }),
  };
}
