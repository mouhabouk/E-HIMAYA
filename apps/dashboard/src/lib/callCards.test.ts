// covers: OS2 (docs/phase-os2/design-os2.md §2): the room's copy of the card rules matches the server's.
import { describe, expect, it } from "vitest";
import { SIM_CALL_CARDS } from "../test/callCardsData";
import { askedQuestions, checkContent, emptyContent, evaluate, shownAnswers, type CardContent } from "./callCards";

const medical = SIM_CALL_CARDS.find((c) => c.category === "medical")?.content as CardContent;

describe("call-taking cards", () => {
  it("starts at the category's band and shows a follow-up only after its answer", () => {
    const r = evaluate(medical, {});
    expect(r.band).toBe("normal");
    expect(r.reasons).toEqual([{ kind: "start", band: "normal" }]);
    expect(askedQuestions(medical, {}).map((q) => q.id)).not.toContain("breathing");
    expect(askedQuestions(medical, { conscious: "yes" }).map((q) => q.id)).toContain("breathing");
  });

  it("raises the band, gathers the flags and offers CPR for an unconscious person who does not breathe", () => {
    const r = evaluate(medical, { conscious: "yes", breathing: "no" });
    expect(r.band).toBe("critical");
    expect(r.flags).toEqual(["حياة في خطر", "توقف قلبي محتمل"]);
    expect(r.instructions).toEqual(["cpr"]);
    expect(r.lives).toBe(true);
    expect(r.answered).toBe(2);
  });

  it("never lowers the band, and an unknown decisive answer keeps it high at least", () => {
    expect(evaluate(medical, { bleeding: "yes", child: "yes" }).band).toBe("critical");
    const r = evaluate(medical, { chest: "unknown" });
    expect(r.band).toBe("high");
    expect(r.reasons.at(-1)).toEqual({ kind: "unknown", band: "high" });
  });

  it("drops the answer of a follow-up whose condition went away", () => {
    expect(shownAnswers(medical, { conscious: "no", breathing: "no" })).toEqual({ conscious: "no" });
  });

  it("checks a card being written before the server does", () => {
    expect(checkContent(medical)).toBeNull();
    expect(checkContent(emptyContent(""))).toBe("callCards.errors.title");
    expect(checkContent(emptyContent("بطاقة"))).toBe("callCards.errors.questionText");
    const follow: CardContent = {
      ...medical,
      questions: [...medical.questions].reverse(),
    };
    expect(checkContent(follow)).toBe("callCards.errors.followUp");
  });
});
