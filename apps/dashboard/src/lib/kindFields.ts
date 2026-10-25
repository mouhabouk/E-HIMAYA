/**
 * The fields of each institution kind and who sees them (phase P2a, docs/phase-p2/design-institutions-app.md §2.2).
 * Mirror of `app.modules.orgs.domain.KIND_FIELDS` (also served at GET /public/org-kinds); the server validates the
 * answers and leaves out of each response what the reader may not see. Working list [SIM] until the Office approves it.
 */
/** Pill tone of each visibility level (design system §3: green public, navy institution, red on incident). */
type Tone = "green" | "navy" | "red";

export type Visibility = "public" | "org_office" | "incident";
export type KindFieldType = "int" | "bool" | "text";

export interface KindFieldSpec {
  key: string;
  type: KindFieldType;
  visibility: Visibility;
  /** int: largest value; text: longest length. */
  maximum: number;
}

const f = (key: string, type: KindFieldType, visibility: Visibility, maximum = 1_000_000): KindFieldSpec => ({
  key,
  type,
  visibility,
  maximum,
});

export const KIND_FIELDS: Readonly<Record<string, readonly KindFieldSpec[]>> = {
  health: [
    f("reception_phone", "text", "public", 20),
    f("beds", "int", "org_office", 10_000),
    f("icu", "bool", "org_office"),
    f("oxygen_hours", "int", "org_office", 10_000),
    f("generator", "bool", "org_office"),
    f("helipad", "bool", "org_office"),
    f("non_ambulatory", "int", "incident", 10_000),
  ],
  industrial: [
    f("workers_per_shift", "int", "org_office", 100_000),
    f("self_fire_fighting", "bool", "org_office"),
    f("tanks", "int", "incident", 1_000),
  ],
  energy: [
    f("fuel_types", "text", "org_office", 200),
    f("storage_m3", "int", "incident", 10_000_000),
    f("shutoff_valves", "bool", "incident"),
  ],
  tourism: [
    f("rooms", "int", "org_office", 10_000),
    f("guest_languages", "text", "org_office", 200),
    f("pool_or_beach", "bool", "org_office"),
    f("occupancy_pct", "int", "incident", 100),
  ],
  education: [
    f("students", "int", "org_office", 100_000),
    f("age_range", "text", "org_office", 50),
    f("boarding", "bool", "org_office"),
    f("students_special_needs", "int", "incident", 10_000),
  ],
  social_care: [
    f("residents", "int", "org_office", 10_000),
    f("night_watch", "bool", "org_office"),
    f("non_ambulatory", "int", "incident", 10_000),
  ],
  public_admin: [f("staff", "int", "org_office", 100_000), f("archive", "bool", "org_office")],
  culture_sport: [f("seated_capacity", "int", "org_office", 200_000), f("stands", "bool", "org_office")],
  commercial: [f("shops", "int", "org_office", 10_000), f("underground_parking", "bool", "incident")],
  transport: [f("daily_passengers", "int", "org_office", 10_000_000), f("emergency_exits", "int", "org_office", 1_000)],
  religious: [f("peak_times", "text", "org_office", 200)],
  other: [],
};

export const VISIBILITY_TONE: Readonly<Record<Visibility, Tone>> = { public: "green", org_office: "navy", incident: "red" };

export type KindFieldValue = number | boolean | string;

/** The answers in the order of the kind's fields, with their spec; unknown keys are left out. */
export function kindFieldRows(kind: string, values: Readonly<Record<string, KindFieldValue>> | null | undefined) {
  const specs = KIND_FIELDS[kind] ?? [];
  const rows: { spec: KindFieldSpec; value: KindFieldValue }[] = [];
  for (const spec of specs) {
    const value = values?.[spec.key];
    if (value !== undefined) rows.push({ spec, value });
  }
  return rows;
}
