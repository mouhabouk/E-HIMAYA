import { vi } from "vitest";
import type { ModelCards, modelCardsApi } from "../lib/modelCards";
import { CARDS, DROWNING_CARD, FIRE_CARD } from "./modelCardsData";

export * from "./modelCardsData";

export function fakeModelCardsApi(cards: ModelCards = CARDS): ReturnType<typeof modelCardsApi> {
  return {
    modelCards: vi.fn(() => Promise.resolve(cards)),
    decideModel: vi.fn(() => Promise.resolve({ ...FIRE_CARD, status: "approved" as const })),
    trainDrowningModel: vi.fn(() => Promise.resolve(DROWNING_CARD)),
    modelCardPdf: vi.fn(() => Promise.resolve({ blob: new Blob(["%PDF"]), filename: "model-card.pdf" })),
  };
}
