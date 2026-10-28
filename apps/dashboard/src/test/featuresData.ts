import type { Feature, FeatureRule, MyFeatures, PreviewRow } from "../lib/featureTypes";

/**
 * A simulated part of the permissions catalogue and two rules ([SIM], phase L4 §8): the data of the unit tests, the
 * accessibility check and the screenshots. No test runner import here, so Playwright loads it too.
 */
const f = (over: Partial<Feature> & Pick<Feature, "key" | "kind" | "names">): Feature => ({
  parent: null,
  group: null,
  nav: null,
  flags: [],
  roles: ["operator", "ops_manager"],
  act_as: "operator",
  grantable: true,
  routes: [],
  ...over,
});

export const FEATURES: Feature[] = [
  f({ key: "schedule", kind: "page", group: "ops", nav: "/schedule", names: { ar: "البرمجة", fr: "Programme", en: "Programme" } }),
  f({
    key: "schedule.progress",
    kind: "tab",
    parent: "schedule",
    names: { ar: "نسبة الإنجاز", fr: "Taux de réalisation", en: "Completion" },
  }),
  f({
    key: "schedule.approve",
    kind: "button",
    parent: "schedule",
    act_as: "ops_manager",
    roles: ["ops_manager"],
    names: { ar: "الاعتماد والإرجاع", fr: "Approuver ou renvoyer", en: "Approve or return" },
    routes: ["POST /schedule/periods/{period_id}/approve"],
  }),
  f({
    key: "schedule.follow",
    kind: "button",
    parent: "schedule",
    names: { ar: "متابعة الأنشطة", fr: "Suivi des activités", en: "Follow activities up" },
  }),
  f({
    key: "incidents",
    kind: "page",
    group: "ops",
    nav: "/incidents",
    flags: ["personal"],
    names: { ar: "الحوادث", fr: "Incidents", en: "Incidents" },
  }),
  f({
    key: "layers",
    kind: "page",
    group: "system",
    nav: "/layers",
    flags: ["fixed"],
    roles: ["sysadmin"],
    act_as: null,
    grantable: false,
    names: { ar: "الطبقات", fr: "Couches", en: "Layers" },
  }),
];

export const FEATURE_RULES: FeatureRule[] = [
  {
    id: "rule-1",
    feature_key: "schedule.approve",
    effect: "grant",
    target_kind: "user",
    target: "sub-nabeul-1",
    target_name: "[SIM] نائب رئيس القاعة بنابل",
    gouvernorat_code: null,
    reason: "[SIM] نيابة رئيس القاعة أثناء عطلته",
    starts_at: "2026-10-26T00:00:00Z",
    ends_at: "2026-11-09T00:00:00Z",
    created_by_name: "[SIM] مدير النظام",
    created_at: "2026-10-25T09:00:00Z",
    revoked_at: null,
    revoked_by_name: null,
    revoke_reason: null,
    state: "active",
  },
  {
    id: "rule-2",
    feature_key: "schedule.progress",
    effect: "hide",
    target_kind: "role",
    target: "field_commander",
    target_name: null,
    gouvernorat_code: 21,
    reason: "[SIM] نسبة الإنجاز لرؤساء القاعات فقط",
    starts_at: null,
    ends_at: null,
    created_by_name: "[SIM] مدير النظام",
    created_at: "2026-10-27T11:00:00Z",
    revoked_at: null,
    revoked_by_name: null,
    revoke_reason: null,
    state: "active",
  },
];

export const NO_FEATURES: MyFeatures = { granted: [], hidden: [], lent: {} };

export const PREVIEW: PreviewRow[] = FEATURES.map((x) => ({
  key: x.key,
  default: x.key !== "layers" && x.key !== "schedule.approve",
  hidden: x.key === "schedule.progress",
  granted: false,
  refused: null,
  open: x.key !== "layers" && x.key !== "schedule.approve" && x.key !== "schedule.progress",
}));
