import type { ApiClient } from "./api";
import type { Download } from "./layersApi";

/**
 * The model cards (L5, docs/phase-l/design-l5.md §4.1, item 9): one card of the same shape per model, with what it is
 * for, its limits, data and licences, its figures (dated, small samples flagged), its thresholds and the committee's
 * decisions (AI-01). The API words and formats every figure in the reader's language, as the PDF prints them.
 */

export type ModelStatus = "approved" | "pending" | "changed" | "withdrawn" | "shadow";

export interface MeasureTable {
  key: string;
  title: string;
  measured_on: string | null;
  simulated: boolean;
  columns: string[];
  rows: string[][];
  small_rows: number[];
  note: string | null;
}

export interface ModelThreshold {
  key: string;
  label: string;
  value: number | boolean | null;
}

export interface ModelDecision {
  decision: "approved" | "withdrawn";
  version: string;
  thresholds: Record<string, number | boolean | null>;
  reference: string;
  note: string;
  decided_by_name: string;
  decided_at: string;
}

export interface ModelCard {
  id: string;
  name: string;
  family: "vision" | "language" | "tabular";
  version: string;
  licences: string[];
  simulated: boolean;
  status: ModelStatus;
  status_label: string;
  use: string;
  limits: string;
  data: string;
  measures: MeasureTable[];
  thresholds: ModelThreshold[];
  decisions: ModelDecision[];
  can_decide: boolean;
  can_train: boolean;
}

export interface ModelCards {
  items: ModelCard[];
  generated_at: string;
}

export interface DecisionIn {
  decision: "approved" | "withdrawn";
  version: string;
  reference: string;
  note: string;
}

export const MAX_REFERENCE = 200;
export const MAX_DECISION_NOTE = 500;

export const modelCardKeys = {
  all: (lang: string) => ["model-cards", lang] as const,
};

const M = "/api/v1/staff/ai/models";
const enc = encodeURIComponent;

export function modelCardsApi(api: ApiClient) {
  return {
    modelCards: (lang: string, signal?: AbortSignal) => api.request<ModelCards>(M, { query: { lang }, signal }),
    decideModel: (id: string, body: DecisionIn) =>
      api.request<ModelCard>(`${M}/${enc(id)}/decisions`, { method: "POST", body }),
    trainDrowningModel: (seed?: number) =>
      api.request<ModelCard>(`${M}/drowning/train`, { method: "POST", body: seed === undefined ? {} : { seed } }),
    modelCardPdf: async (id: string, lang: string): Promise<Download> => {
      const response = await api.requestRaw(`${M}/${enc(id)}/card.pdf`, { query: { lang }, accept: "application/pdf" });
      return { blob: await response.blob(), filename: `model-card-${id}.pdf` };
    },
  };
}
