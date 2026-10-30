import { AXIS_KINDS, type Axis, type AxisKind } from "./crisis";

/** Simulated axes (demonstrations, drills) carry "[SIM]" at the start of their name: the badge says it, not the name. */
const SIM = /^\s*\[SIM\]\s*/i;

export function isSimulated(axis: Pick<Axis, "name">): boolean {
  return SIM.test(axis.name);
}

export function displayName(axis: Pick<Axis, "name">): string {
  return axis.name.replace(SIM, "");
}

/** The same for any text (register titles, dispatch subjects, phase L3b). */
export function simText(text: string): { text: string; sim: boolean } {
  return { text: text.replace(SIM, ""), sim: SIM.test(text) };
}

/** The kind of disaster an intervention's category suggests (phase N); the room changes it in the form. */
const KIND_OF: Readonly<Record<string, AxisKind>> = {
  flood: "flood",
  drowning: "flood",
  landslide: "storm",
  fire: "forest_fire",
  chemical_leak: "technological",
};

/** A disaster prefilled from one intervention: what the axes screen opens with (phase N, design §4). */
export interface Promotion {
  incident: string;
  name: string;
  kind: AxisKind;
  gouvernorat: number | null;
}

export function promoteLink(incident: { id: string; category: string; title?: string | null; gouvernorat_code?: number | null }): string {
  const q = new URLSearchParams({ promote: incident.id, kind: KIND_OF[incident.category] ?? "other" });
  if (incident.title) q.set("name", incident.title.slice(0, 200));
  if (incident.gouvernorat_code) q.set("g", String(incident.gouvernorat_code));
  return `/axes?${q.toString()}`;
}

export function readPromotion(params: URLSearchParams): Promotion | null {
  const incident = params.get("promote");
  if (!incident) return null;
  const kind = params.get("kind") as AxisKind | null;
  const g = Number(params.get("g"));
  return {
    incident,
    name: params.get("name") ?? "",
    kind: kind && (AXIS_KINDS as readonly string[]).includes(kind) ? kind : "other",
    gouvernorat: Number.isInteger(g) && g > 0 ? g : null,
  };
}
