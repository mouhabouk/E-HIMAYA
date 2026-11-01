import type { Prealert } from "./streamsApi";

/**
 * The words for a pre-alert's state (Yamen, 2026-11-01): who is being asked (the safety officer, then the owner),
 * who answered, or that a device the Civil Protection follows went to the room at once. Returns a key and its values.
 */
export function prealertState(
  p: Pick<Prealert, "stage" | "state" | "seconds_left">,
): [string, { seconds?: number }] {
  if (p.stage === "room") return ["cameras.states.room", {}];
  const officer = p.stage === "officer";
  if (p.state === "pending")
    return [
      officer ? "cameras.states.pendingOfficer" : "cameras.states.pending",
      { seconds: p.seconds_left },
    ];
  if (p.state === "confirmed")
    return [
      officer ? "cameras.states.confirmedOfficer" : "cameras.states.confirmed",
      {},
    ];
  return [`cameras.states.${p.state}`, {}];
}
