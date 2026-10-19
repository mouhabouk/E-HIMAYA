import { describe, expect, it } from "vitest";
import { allowedTransitions, canTransition, isFinal, statusChoices, TRANSITIONS } from "./status";
import { REPORT_STATUSES } from "./types";

describe("status transition table (contract §3)", () => {
  it("matches the contract exactly", () => {
    expect(TRANSITIONS).toEqual({
      received: ["in_progress", "rejected"],
      in_progress: ["intervened", "ongoing", "closed", "rejected"],
      intervened: ["ongoing", "closed"],
      ongoing: ["intervened", "closed"],
      closed: [],
      rejected: [],
    });
  });

  it("covers every status", () => {
    expect(Object.keys(TRANSITIONS).sort()).toEqual([...REPORT_STATUSES].sort());
  });

  it("treats closed and rejected as final", () => {
    expect(isFinal("closed")).toBe(true);
    expect(isFinal("rejected")).toBe(true);
    expect(isFinal("received")).toBe(false);
  });

  it("refuses transitions outside the table", () => {
    expect(canTransition("received", "closed")).toBe(false);
    expect(canTransition("received", "intervened")).toBe(false);
    expect(canTransition("intervened", "rejected")).toBe(false);
    expect(canTransition("ongoing", "intervened")).toBe(true);
    expect(canTransition("closed", "in_progress")).toBe(false);
    for (const s of REPORT_STATUSES) expect(canTransition(s, s)).toBe(false);
  });

  it("offers transitions only to roles allowed to change status", () => {
    expect(allowedTransitions("received", ["operator"])).toEqual(["in_progress", "rejected"]);
    expect(allowedTransitions("in_progress", ["field_commander"])).toHaveLength(4);
    expect(allowedTransitions("received", ["ops_manager"])).toEqual(["in_progress", "rejected"]);
    expect(allowedTransitions("received", ["local_committee"])).toEqual([]);
    expect(allowedTransitions("received", ["central_committee", "offline_access"])).toEqual([]);
    expect(allowedTransitions("closed", ["operator"])).toEqual([]);
  });
});

describe("statusChoices", () => {
  it("prefers the server's allowed_transitions", () => {
    expect(statusChoices({ status: "in_progress", allowed_transitions: ["closed"] }, ["operator"])).toEqual(["closed"]);
  });

  it("drops unknown values and the current status from the server list", () => {
    expect(
      statusChoices({ status: "received", allowed_transitions: ["received", "bogus", "rejected"] }, ["operator"]),
    ).toEqual(["rejected"]);
  });

  it("falls back to the contract table", () => {
    expect(statusChoices({ status: "ongoing" }, ["field_commander"])).toEqual(["intervened", "closed"]);
  });

  it("never offers anything to read-only roles, even if the server lists transitions", () => {
    expect(statusChoices({ status: "received", allowed_transitions: ["in_progress"] }, ["local_committee"])).toEqual([]);
  });
});
