import { vi } from "vitest";
import type { FeatureRule, featuresApi } from "../lib/features";
import { FEATURE_RULES, FEATURES, NO_FEATURES, PREVIEW } from "./featuresData";

const [FIRST] = FEATURE_RULES as [FeatureRule, ...FeatureRule[]];

export function fakeFeaturesApi(): ReturnType<typeof featuresApi> {
  return {
    myFeatures: vi.fn(() => Promise.resolve(NO_FEATURES)),
    featureCatalogue: vi.fn(() => Promise.resolve(FEATURES)),
    featureRules: vi.fn(() => Promise.resolve(FEATURE_RULES)),
    createFeatureRule: vi.fn(() => Promise.resolve(FIRST)),
    revokeFeatureRule: vi.fn(() => Promise.resolve({ ...FIRST, state: "revoked" as const })),
    featurePreview: vi.fn(() => Promise.resolve(PREVIEW)),
  };
}
