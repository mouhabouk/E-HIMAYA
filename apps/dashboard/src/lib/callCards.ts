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
  /** The review (OS2-4): handed over by the Office, sent back with a note, the [SIM] text confirmed as it is. */
  submitted_at?: string | null;
  submitted_by_name?: string | null;
  returned_at?: string | null;
  returned_by_name?: string | null;
  returned_reason?: string | null;
  unchanged?: boolean;
  /** The Office's note per question id, `_card` for the whole card. */
  notes?: Record<string, string>;
}

/** The key of the Office's note on the whole card. */
export const CARD_NOTE = "_card";

// ---------------------------------------------------------------- review of the [SIM] cards (OS2-4)

export const REVIEW_STAGES = ["not_started", "office", "doctor", "approval", "done"] as const;
export type ReviewStage = (typeof REVIEW_STAGES)[number];

export interface ReviewItem {
  category: Category;
  title: string;
  stage: ReviewStage;
  medical: boolean;
  approved: CallCard | null;
  draft: CallCard | null;
  office: string | null;
  doctor: string | null;
}

export interface CardReview {
  items: ReviewItem[];
  done: number;
  total: number;
}

/** One change between two versions of a card, for the reviewers. */
export type CardChange =
  | { kind: "added" | "removed"; question: CardQuestion }
  | { kind: "changed"; question: CardQuestion; before: CardQuestion; fields: ("text" | "help" | "key" | "when" | "effects")[] };

const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/** What a draft changes in the questions of the approved version (matched by question id). */
export function questionChanges(before: CardContent, after: CardContent): CardChange[] {
  const old = new Map(before.questions.map((q) => [q.id, q]));
  const changes: CardChange[] = [];
  for (const q of after.questions) {
    const b = old.get(q.id);
    if (!b) {
      changes.push({ kind: "added", question: q });
      continue;
    }
    const fields = (["text", "help", "key", "when", "effects"] as const).filter((f) => !same(q[f], b[f]));
    if (fields.length) changes.push({ kind: "changed", question: q, before: b, fields: [...fields] });
  }
  const now = new Set(after.questions.map((q) => q.id));
  for (const q of before.questions) if (!now.has(q.id)) changes.push({ kind: "removed", question: q });
  return changes;
}

/** Steps of an instruction, each marked kept, added or removed (a simple line comparison). */
export function stepChanges(before: string[], after: string[]): { text: string; mark: "same" | "added" | "removed" }[] {
  const out: { text: string; mark: "same" | "added" | "removed" }[] = [];
  for (const s of after) out.push({ text: s, mark: before.includes(s) ? "same" : "added" });
  for (const s of before) if (!after.includes(s)) out.push({ text: s, mark: "removed" });
  return out;
}

// ---------------------------------------------------------------- statistics (OS2-3)

export const INTAKE_CHANNELS = ["phone", "radio", "in_person", "other"] as const;
export type StatsChannel = (typeof INTAKE_CHANNELS)[number];
export const STATS_DAYS = [7, 30, 90] as const;
export const STATS_CHECKS = [
  "confirmed",
  "nature_differs",
  "lives_not_on_card",
  "injured_not_on_card",
  "band_below_toll",
] as const;

export interface StatsFigures {
  entered: number;
  with_card: number;
  median_with_s: number | null;
  median_without_s: number | null;
  p90_s: number | null;
  field_checked: number;
  field_confirmed: number;
}

export interface RoomFigures extends StatsFigures {
  room: string;
}

export interface QuestionFigures {
  id: string;
  text: string;
  key: boolean;
  yes: number;
  no: number;
  unknown: number;
  field_changed: number;
  field_answered: number;
}

export interface CardFigures {
  category: Category;
  title: string;
  used: number;
  median_s: number | null;
  key_unknown: number;
  key_answered: number;
  field_checked: number;
  checks: Record<(typeof STATS_CHECKS)[number], number>;
  questions: QuestionFigures[];
  read: Record<string, number>;
  instruction_titles: Record<string, string>;
}

export interface CardStats {
  days: number;
  since: string;
  room: string | null;
  total: StatsFigures;
  national: StatsFigures;
  rooms: RoomFigures[];
  cards: CardFigures[];
}

/** A whole percentage, or null when there is nothing to divide. */
export const percent = (part: number, whole: number): number | null =>
  whole > 0 ? Math.round((100 * part) / whole) : null;

/** Seconds as m:ss (the call times). */
export function minutes(seconds: number | null): string {
  if (seconds === null) return "—";
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** The statistics as CSV: one line per room, then one per card (opened in a spreadsheet). */
export function statsCsv(stats: CardStats, roomName: (room: string) => string): string {
  const cell = (v: string | number | null) => {
    const s = v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    ["room", "entered", "with_card", "median_with_s", "median_without_s", "p90_s", "field_checked", "field_confirmed"],
    ...stats.rooms.map((r) => [
      roomName(r.room),
      r.entered,
      r.with_card,
      r.median_with_s,
      r.median_without_s,
      r.p90_s,
      r.field_checked,
      r.field_confirmed,
    ]),
    [],
    ["card", "used", "median_s", "key_unknown", "key_answered", "field_checked", ...STATS_CHECKS],
    ...stats.cards.map((c) => [
      c.title,
      c.used,
      c.median_s,
      c.key_unknown,
      c.key_answered,
      c.field_checked,
      ...STATS_CHECKS.map((k) => c.checks[k]),
    ]),
  ];
  return lines.map((l) => l.map(cell).join(",")).join("\n");
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

/** What the teams found on the incident, set beside the card by the server (`callcards.compare`). */
export const SCENE_CHECKS = [
  "nature_differs",
  "lives_not_on_card",
  "injured_not_on_card",
  "band_below_toll",
  "confirmed",
] as const;
export type SceneCheck = (typeof SCENE_CHECKS)[number];

export interface CardScene {
  nature: string | null;
  injured: number;
  serious: number;
  deceased: number;
  trapped: number;
  checks: SceneCheck[];
}

export interface ReportCallCard {
  report_id: string;
  card_id: string;
  category: Category;
  card_version: number;
  sim: boolean;
  title: string;
  /** The caller's answers, and what they gave. */
  answers: Record<string, CardAnswer>;
  outcome: CardOutcome;
  read: string[];
  /** The team's answers from the scene (they replace the caller's question by question; the band never goes down). */
  field_answers: Record<string, CardAnswer> | null;
  field_outcome: CardOutcome | null;
  field_by_name: string | null;
  field_at: string | null;
  scene: CardScene | null;
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
  reportAll: ["call-cards", "report"] as const,
  review: ["call-cards", "review"] as const,
  stats: (days: number, channels: string, room: string | null) => ["call-cards", "stats", days, channels, room] as const,
  report: (id: string) => ["call-cards", "report", id] as const,
};

const C = "/api/v1/staff/call-cards";
const cardPath = (id: string) => `${C}/${encodeURIComponent(id)}`;

export function callCardsApi(api: ApiClient) {
  return {
    callCards: (include: "current" | "all" = "current", signal?: AbortSignal) =>
      api.request<{ cards: CallCard[] }>(C, { query: { include }, signal }),
    createCardDraft: (category: Category, content: CardContent, reason: string, notes: Record<string, string> = {}) =>
      api.request<CallCard>(`${C}/${encodeURIComponent(category)}/draft`, {
        method: "POST",
        body: { content, reason, notes },
      }),
    updateCardDraft: (
      id: string,
      content: CardContent,
      reason: string,
      updatedAt: string,
      notes: Record<string, string> = {},
    ) =>
      api.request<CallCard>(cardPath(id), {
        method: "PUT",
        body: { content, reason, updated_at: updatedAt, notes },
      }),
    cardReview: (signal?: AbortSignal) => api.request<CardReview>(`${C}/review`, { signal }),
    setCardReviewers: (category: Category, office: string | null, doctor: string | null, reason: string) =>
      api.request<ReviewItem>(`${C}/${encodeURIComponent(category)}/reviewers`, {
        method: "PUT",
        body: { office, doctor, reason },
      }),
    confirmCard: (category: Category, reason: string) =>
      api.request<CallCard>(`${C}/${encodeURIComponent(category)}/confirm`, { method: "POST", body: { reason } }),
    submitCard: (id: string, reason: string, updatedAt: string) =>
      api.request<CallCard>(`${cardPath(id)}/submit`, { method: "POST", body: { reason, updated_at: updatedAt } }),
    returnCard: (id: string, reason: string, updatedAt: string) =>
      api.request<CallCard>(`${cardPath(id)}/return`, { method: "POST", body: { reason, updated_at: updatedAt } }),
    cardStats: (days: number, channels: readonly string[], room: string | null, signal?: AbortSignal) =>
      api.request<CardStats>(`${C}/stats`, {
        query: { days, channel: channels.join(","), ...(room ? { room } : {}) },
        signal,
      }),
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
