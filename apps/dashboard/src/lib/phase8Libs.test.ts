import { describe, expect, it } from "vitest";
import { libraryParams, libraryQueryFromParams, treeNodeFilter } from "../pages/EventsLibraryPage";
import { allowedTransitions, emptyMemoryBody, memoryErrors } from "../pages/MemoryEntryPage";
import { reportBody, reportFormFromParams } from "../pages/ReportsLibraryPage";
import { scheduleBody, type ScheduleFormState } from "../pages/ReportSchedulesPage";
import { nominationErrors, ruleValueError } from "../pages/RewardsPages";
import { validateScenario } from "../pages/ScenariosPage";
import {
  analyticsSearch,
  defaultAnalyticsFilters,
  exportSearch,
  HEX_COLOURS,
  hexBreaks,
  hexClass,
  hexLegend,
  parseAnalyticsFilters,
} from "./analytics";
import { diffLines } from "./diff";
import { localized } from "./localized";
import { excerptParts, renderMarkdown } from "./markdown";
import {
  canAuthorMemory,
  canEditRewardRules,
  canManageRewards,
  canManageSchedules,
  canReadAnalytics,
  canReadKnowledge,
  canReadRewards,
  canReviewMemory,
  canRunScenarios,
  canSeeRewardActivity,
} from "./roles";

const TODAY = new Date(2026, 9, 20, 12, 0, 0);

describe("analytics filters in the URL", () => {
  it("defaults to the last 90 days, weekly reports", () => {
    expect(defaultAnalyticsFilters(TODAY)).toEqual({
      from: "2026-07-23",
      to: "2026-10-20",
      gouvernorat: null,
      category: null,
      metric: "reports",
      interval: "week",
    });
  });

  it("reads valid values and repairs the rest", () => {
    const f = parseAnalyticsFilters(
      new URLSearchParams("from=2026-01-01&to=2026-03-31&gouvernorat=61&category=fire&metric=response_time&interval=month"),
      true,
      TODAY,
    );
    expect(f).toMatchObject({ from: "2026-01-01", to: "2026-03-31", gouvernorat: 61, category: "fire", metric: "response_time", interval: "month" });
    const bad = parseAnalyticsFilters(new URLSearchParams("from=2026-02-31&to=nope&category=x&metric=y&gouvernorat=-1"), true, TODAY);
    expect(bad).toEqual(defaultAnalyticsFilters(TODAY));
    // Reversed range: the end wins; too long: clipped.
    expect(parseAnalyticsFilters(new URLSearchParams("from=2026-05-01&to=2026-04-01"), true, TODAY).from).toBe("2026-04-01");
    expect(parseAnalyticsFilters(new URLSearchParams("from=2010-01-01&to=2026-01-01"), true, TODAY).from).toBe("2022-12-30");
  });

  it("ignores the gouvernorat of a regional user (the API applies the token's scope)", () => {
    expect(parseAnalyticsFilters(new URLSearchParams("gouvernorat=61"), false, TODAY).gouvernorat).toBeNull();
  });

  it("writes only what differs from the defaults and round-trips", () => {
    expect(analyticsSearch(defaultAnalyticsFilters(TODAY), TODAY).toString()).toBe("");
    const f = { ...defaultAnalyticsFilters(TODAY), gouvernorat: 11, metric: "interventions" as const };
    const p = analyticsSearch(f, TODAY);
    expect(p.toString()).toBe("gouvernorat=11&metric=interventions");
    expect(parseAnalyticsFilters(p, true, TODAY)).toEqual(f);
  });

  it("prefills the report form from the filters", () => {
    const f = { ...defaultAnalyticsFilters(TODAY), gouvernorat: 61, category: "flood" as const };
    expect(exportSearch(f)).toBe("?new=1&kind=gouvernorat_summary&from=2026-07-23&to=2026-10-20&gouvernorat=61&category=flood");
    const form = reportFormFromParams(new URLSearchParams(exportSearch(f).slice(1)), "fr", TODAY);
    expect(form).toMatchObject({ kind: "gouvernorat_summary", from: "2026-07-23", to: "2026-10-20", gouvernorats: [61], category: "flood" });
  });
});

describe("hexagon colour classes", () => {
  it("uses quantile breaks of the non-zero counts", () => {
    const counts = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 100];
    const breaks = hexBreaks(counts);
    expect(breaks).toEqual([3, 5, 7, 9]);
    expect(hexClass(1, breaks)).toBe(0);
    expect(hexClass(5, breaks)).toBe(2);
    expect(hexClass(100, breaks)).toBe(HEX_COLOURS.length - 1);
    expect(hexBreaks([0, 0])).toEqual([]);
  });

  it("builds a legend without empty ranges", () => {
    expect(hexLegend([3, 5], 12)).toEqual([
      { colour: HEX_COLOURS[0], from: 1, to: 2 },
      { colour: HEX_COLOURS[1], from: 3, to: 4 },
      { colour: HEX_COLOURS[2], from: 5, to: 12 },
    ]);
    expect(hexLegend([1, 4], 4).map((r) => r.from)).toEqual([1, 4]);
  });
});

describe("Markdown rendering is safe", () => {
  it("renders Markdown", () => {
    const html = renderMarkdown("# Titre\n\n- **un**\n- deux\n\n[site](https://example.tn)");
    expect(html).toContain("<h1>Titre</h1>");
    expect(html).toContain("<strong>un</strong>");
    expect(html).toContain('href="https://example.tn"');
    expect(html).toContain('rel="noopener noreferrer nofollow"');
    expect(html).toContain('target="_blank"');
  });

  it("never passes raw HTML, script URLs or images through", () => {
    const html = renderMarkdown(
      '<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[x](javascript:alert(1)) [y](data:text/html,hi)\n\n![i](https://evil.example/p.png)\n\n<a href="https://e.x" onclick="alert(1)">a</a>',
    );
    const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
    expect(doc.querySelector("script, img, iframe, style")).toBeNull();
    expect(doc.querySelectorAll("[onerror], [onclick], [style]")).toHaveLength(0);
    for (const a of doc.querySelectorAll("a")) {
      const href = a.getAttribute("href");
      if (href !== null) expect(href).toMatch(/^https?:|^mailto:/);
    }
    // Raw HTML shows as text.
    expect(doc.body.textContent).toContain("<script>alert(1)</script>");
  });

  it("splits search excerpts into text and marks without HTML", () => {
    expect(excerptParts("Les <mark>feux</mark> &lt;b&gt; du <mark>Kef</mark>")).toEqual([
      { text: "Les ", marked: false },
      { text: "feux", marked: true },
      { text: " <b> du ", marked: false },
      { text: "Kef", marked: true },
    ]);
  });
});

describe("line diff", () => {
  it("finds added, removed and kept lines", () => {
    expect(diffLines("a\nb\nc", "a\nx\nc\nd")).toEqual([
      { kind: "same", text: "a" },
      { kind: "del", text: "b" },
      { kind: "add", text: "x" },
      { kind: "same", text: "c" },
      { kind: "add", text: "d" },
    ]);
    expect(diffLines("", "a")).toEqual([{ kind: "add", text: "a" }]);
    expect(diffLines("same", "same")).toEqual([{ kind: "same", text: "same" }]);
  });

  it("stays bounded on very large inputs", () => {
    const a = Array.from({ length: 1500 }, (_, i) => `a${i}`).join("\n");
    const b = Array.from({ length: 1500 }, (_, i) => `b${i}`).join("\n");
    const ops = diffLines(a, b);
    expect(ops.filter((o) => o.kind === "del")).toHaveLength(1500);
    expect(ops.filter((o) => o.kind === "add")).toHaveLength(1500);
  });
});

describe("forms", () => {
  it("validates a what-if scenario", () => {
    const ok = validateScenario({
      name: " Test ",
      gouvernorats: [61],
      category: "fire",
      factor: "2.5",
      horizon: "24",
      weather: "heavy_rain",
      unavailable: { fire_engine: "2", ambulance: "", boat: "0" },
    });
    expect(ok.body).toEqual({
      name: "Test",
      gouvernorats: [61],
      category: "fire",
      demand_factor: 2.5,
      unavailable_resources: { fire_engine: 2 },
      horizon_hours: 24,
      weather: "heavy_rain",
    });
    const bad = validateScenario({ name: "", gouvernorats: [], category: "fire", factor: "11", horizon: "5", weather: "as_forecast", unavailable: { boat: "-1" } });
    expect(bad.body).toBeNull();
    expect(Object.keys(bad.errors).sort()).toEqual(["factor", "gouvernorats", "horizon", "name", "unavailable"]);
  });

  it("builds a report request with the linked object its kind needs", () => {
    const base = reportFormFromParams(new URLSearchParams("kind=after_action&title=RETEX"), "ar", TODAY);
    expect(reportBody(base).errors).toEqual({ incident: true });
    const body = reportBody({ ...base, incidentId: "inc-1" }).body;
    expect(body).toMatchObject({ kind: "after_action", title: "RETEX", lang: "ar", filters: { incident_id: "inc-1" } });
    const scenario = reportFormFromParams(new URLSearchParams("kind=scenario&scenario=sc-1&title=S"), "fr", TODAY);
    expect(reportBody(scenario).body?.filters).toEqual({ scenario_id: "sc-1" });
  });

  it("builds a schedule with the cron fields of its frequency", () => {
    const f: ScheduleFormState = {
      title: "Hebdo",
      kind: "period_summary",
      gouvernorat: null,
      category: "fire",
      format: "xlsx",
      lang: "fr",
      frequency: "monthly",
      time: "06:30",
      weekday: 3,
      day: 5,
      recipients: ["5f0c8e4a-1b2c-4d3e-8f90-a1b2c3d4e5f6"],
      enabled: true,
    };
    expect(scheduleBody(f).body).toMatchObject({ cron: { frequency: "monthly", time: "06:30", day: 5 }, filters: { category: "fire" }, gouvernorats: [] });
    expect(scheduleBody(f).body?.cron).not.toHaveProperty("weekday");
    expect(scheduleBody({ ...f, time: "25:00", recipients: [] }).errors).toEqual({ time: true, recipients: true });
  });

  it("checks a memory entry and offers only the allowed transitions", () => {
    const b = emptyMemoryBody(61);
    expect(memoryErrors(b)).toEqual(["title", "started_at"]);
    expect(memoryErrors({ ...b, title: { ar: "", fr: "x" }, started_at: "2026-08-02T00:00:00Z", incident_ids: ["nope"] })).toEqual(["incident_ids"]);
    expect(allowedTransitions({ status: "draft", can_edit: true, can_review: false }).map((x) => x.action)).toEqual(["submit"]);
    expect(allowedTransitions({ status: "in_review", can_edit: true, can_review: true }).map((x) => x.action)).toEqual(["publish", "requestChanges"]);
    expect(allowedTransitions({ status: "in_review", can_edit: true, can_review: false })).toEqual([]);
    expect(allowedTransitions({ status: "archived", can_edit: false, can_review: true }).map((x) => x.to)).toEqual(["draft"]);
  });

  it("checks rule values and nominations", () => {
    expect(ruleValueError("accurate_category", "1.5")).toBe(false);
    expect(ruleValueError("accurate_category", "3.5")).toBe(true);
    expect(ruleValueError("report_verified", "50")).toBe(false);
    expect(ruleValueError("report_verified", "50.5")).toBe(true);
    expect(ruleValueError("report_verified", "")).toBe(true);
    expect(nominationErrors({ subjectId: "", year: "1999", reason: "court", reportIds: "x", interventionIds: "" })).toEqual([
      "subject",
      "year",
      "reason",
      "evidence",
    ]);
  });
});

describe("events library state", () => {
  it("round-trips the search state through the URL", () => {
    const q = libraryQueryFromParams(new URLSearchParams("q=feux&kinds=memory,bogus,report&gouvernorat=61&from=2026-01-01&view=tree"));
    expect(q).toEqual({ q: "feux", kinds: ["memory", "report"], from: "2026-01-01", to: undefined, gouvernorat: 61, category: null, view: "tree" });
    expect(libraryParams(q).toString()).toBe("q=feux&kinds=memory%2Creport&from=2026-01-01&gouvernorat=61&view=tree");
  });

  it("turns a tree node into filters", () => {
    expect(treeNodeFilter("period", ["2024"])).toEqual({ from: "2024-01-01", to: "2024-12-31" });
    expect(treeNodeFilter("period", ["2024", "2"])).toEqual({ from: "2024-02-01", to: "2024-02-29" });
    expect(treeNodeFilter("period", ["2024", "2024-11"])).toEqual({ from: "2024-11-01", to: "2024-11-30" });
    expect(treeNodeFilter("type", ["memory", "fire"])).toEqual({ kinds: ["memory"], category: "fire" });
    expect(treeNodeFilter("gouvernorat", ["61", "transcript"])).toEqual({ gouvernorat: 61, kinds: ["transcript"] });
  });

  it("falls back to the other language", () => {
    expect(localized({ ar: "", fr: "Bonjour" }, "ar")).toBe("Bonjour");
    expect(localized({ ar: "مرحبا", fr: "" }, "fr")).toBe("مرحبا");
    expect(localized(null, "fr")).toBe("");
  });
});

describe("phase 8 roles", () => {
  it("opens analytics to the read roles and scenarios, schedules to the managers", () => {
    expect(canReadAnalytics(["operator"])).toBe(true);
    expect(canReadAnalytics(["content_editor"])).toBe(false);
    expect(canRunScenarios(["operator"])).toBe(false);
    expect(canRunScenarios(["field_commander"])).toBe(true);
    expect(canManageSchedules(["field_commander"])).toBe(false);
    expect(canManageSchedules(["local_committee"])).toBe(true);
  });

  it("opens the memory to content editors, reviews to managers and committees", () => {
    expect(canReadKnowledge(["content_editor"])).toBe(true);
    expect(canReadKnowledge(["org_auditor"])).toBe(false);
    expect(canAuthorMemory(["operator"])).toBe(false);
    expect(canAuthorMemory(["content_editor"])).toBe(true);
    expect(canReviewMemory(["content_editor"])).toBe(false);
    expect(canReviewMemory(["ops_manager"])).toBe(true);
  });

  it("limits reward rules to national central committee or sysadmin", () => {
    expect(canReadRewards(["sysadmin"])).toBe(true);
    expect(canSeeRewardActivity(["sysadmin"])).toBe(false);
    expect(canManageRewards(["operator"])).toBe(false);
    expect(canManageRewards(["central_committee"])).toBe(true);
    expect(canEditRewardRules({ roles: ["central_committee"], national: true })).toBe(true);
    expect(canEditRewardRules({ roles: ["central_committee"], national: false })).toBe(false);
    expect(canEditRewardRules({ roles: ["ops_manager"], national: true })).toBe(false);
  });
});
