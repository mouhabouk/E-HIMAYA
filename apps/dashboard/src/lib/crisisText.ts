import type { Axis } from "./crisis";

/** Simulated axes (demonstrations, drills) carry "[SIM]" at the start of their name: the badge says it, not the name. */
const SIM = /^\s*\[SIM\]\s*/i;

export function isSimulated(axis: Pick<Axis, "name">): boolean {
  return SIM.test(axis.name);
}

export function displayName(axis: Pick<Axis, "name">): string {
  return axis.name.replace(SIM, "");
}
