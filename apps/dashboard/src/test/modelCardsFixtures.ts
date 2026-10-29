import { vi } from "vitest";
import type { ModelCard, ModelCards, modelCardsApi } from "../lib/modelCards";

export const FIRE_CARD: ModelCard = {
  id: "fire_smoke",
  name: "كاشف النار والدخان",
  family: "vision",
  version: "ehimaya-fire-smoke-yolox-tiny 2.0.0",
  licences: ["Apache-2.0 (YOLOX)", "CC0-1.0 (FURG)"],
  simulated: false,
  status: "pending",
  status_label: "ينتظر اعتماد اللجنة",
  use: "يقترح «نار» أو «دخان» على المشغّل.",
  limits: "الدخان تلميح فقط.",
  data: "Open Images V7، FireNET، FURG.",
  measures: [
    {
      key: "conditions_fire",
      title: "النار التي فاتته حسب الظروف (عند 0.45)",
      measured_on: "2026-10-29",
      simulated: false,
      columns: ["الظرف", "الصور", "فاته", "مجال الثقة 95٪"],
      rows: [
        ["الكل", "123", "16/123 (13٪)", "8٪–20٪"],
        ["بعيد", "22", "7/22 (32٪)", "16٪–53٪"],
      ],
      small_rows: [1],
      note: "عينة صغيرة: الرقم لا يقول الكثير",
    },
  ],
  thresholds: [
    { key: "vision_min_confidence", label: "أدنى ثقة لاقتراح", value: 0.45 },
    { key: "vision_alert_confidence", label: "ثقة التنبيه (في 3 إطارات من 5)", value: 0.6 },
  ],
  decisions: [],
  can_decide: true,
  can_train: false,
};

export const DROWNING_CARD: ModelCard = {
  ...FIRE_CARD,
  id: "drowning",
  name: "نموذج خطر الغرق (في الظل)",
  family: "tabular",
  version: "v2",
  licences: ["BSD-3-Clause (scikit-learn)"],
  simulated: true,
  status: "shadow",
  status_label: "في الظل",
  measures: [
    {
      key: "drowning",
      title: "مقارنة بالقواعد على أيام [SIM] أخرى",
      measured_on: "2026-10-29",
      simulated: true,
      columns: ["المقياس", "النموذج", "القواعد"],
      rows: [["مساحة تحت المنحنى (AUC)", "0.828", "0.812"]],
      small_rows: [],
      note: null,
    },
  ],
  thresholds: [
    { key: "yellow", label: "احتمال المستوى الأصفر", value: 0.035 },
    { key: "red", label: "احتمال المستوى الأحمر", value: 0.159 },
  ],
  decisions: [
    {
      decision: "approved",
      version: "v1",
      thresholds: { yellow: 0.03, red: 0.15 },
      reference: "PV 2026/07",
      note: "",
      decided_by_name: "لجنة مركزية",
      decided_at: "2026-10-20T10:00:00Z",
    },
  ],
  can_decide: true,
  can_train: true,
};

export const CARDS: ModelCards = { items: [FIRE_CARD, DROWNING_CARD], generated_at: "2026-10-29T08:00:00Z" };

export function fakeModelCardsApi(cards: ModelCards = CARDS): ReturnType<typeof modelCardsApi> {
  return {
    modelCards: vi.fn(() => Promise.resolve(cards)),
    decideModel: vi.fn(() => Promise.resolve({ ...FIRE_CARD, status: "approved" as const })),
    trainDrowningModel: vi.fn(() => Promise.resolve(DROWNING_CARD)),
    modelCardPdf: vi.fn(() => Promise.resolve({ blob: new Blob(["%PDF"]), filename: "model-card.pdf" })),
  };
}
