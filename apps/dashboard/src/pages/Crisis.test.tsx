// covers: phase L3 (docs/phase-l/design-l3.md §3, §6): the minister's and the governor's command screen, the field
// command of an axis, the axes list with the declaration requests, and the roles that open them.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canOpenAxes, canOpenCommand, landingPath } from "../lib/roles";
import { areaBounds } from "../lib/crisis";
import { displayName, isSimulated } from "../lib/crisisText";
import { fakeCrisisApi, NABEUL_AREA, overview } from "../test/crisisFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { AxesPage } from "./AxesPage";
import { AxisPage } from "./AxisPage";
import { CommandPage } from "./CommandPage";

vi.mock("../components/crisis/CommandMap", () => ({
  CommandMap: (props: { ariaLabel: string; levels?: Record<number, number> }) => (
    <div role="img" aria-label={props.ariaLabel} data-levels={JSON.stringify(props.levels ?? {})} />
  ),
}));

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("crisis roles and helpers", () => {
  it("opens the command screen for governors and ministers, the axes for the rooms", () => {
    expect(canOpenCommand(["governor"])).toBe(true);
    expect(canOpenCommand(["minister"])).toBe(true);
    expect(canOpenAxes(["governor"])).toBe(false);
    expect(canOpenAxes(["operator"])).toBe(true);
    expect(landingPath(["minister"])).toBe("/command");
  });

  it("reads the [SIM] mark and the area bounds", () => {
    expect(isSimulated({ name: "[SIM] فيضانات" })).toBe(true);
    expect(displayName({ name: "[SIM] فيضانات" })).toBe("فيضانات");
    expect(areaBounds([NABEUL_AREA])).toEqual([10.6, 36.36, 10.86, 36.6]);
  });
});

describe("CommandPage", () => {
  it("shows the minister the national picture, the ranking and his decisions", async () => {
    const api = fakeCrisisApi();
    renderApp(<CommandPage />, { api: fakeApi(api), auth: fakeAuth(claims(["minister"])), lang: "ar" });
    expect((await screen.findAllByText("لوحة الوزير: الوضع الوطني")).length).toBeGreaterThan(0);
    const ranking = screen.getByRole("table");
    expect(within(ranking).getAllByRole("row")).toHaveLength(4);
    expect(screen.getAllByText("[SIM] بيانات تجريبية").length).toBeGreaterThan(0);
    expect(screen.getByRole("img").dataset.levels).toBe(JSON.stringify({ 21: 3, 32: 2, 51: 1 }));
    // Clicking a gouvernorat narrows the crises to it.
    fireEvent.click(within(ranking).getByRole("button", { name: "جندوبة" }));
    expect(await screen.findByText("الأزمات النشطة في جندوبة")).toBeInTheDocument();
    // The minister issues a signed decision.
    fireEvent.click(screen.getByRole("button", { name: "توصية أو قرار" }));
    fireEvent.change(screen.getByLabelText("النص"), { target: { value: "إخلاء الأحياء المنخفضة" } });
    fireEvent.click(screen.getByRole("button", { name: "إصدار وتوقيع" }));
    await waitFor(() => expect(api.issueAxisDirective).toHaveBeenCalled());
    expect(vi.mocked(api.issueAxisDirective).mock.calls[0]?.[1]).toMatchObject({ kind: "decision", category: "evacuation" });
  });

  it("shows the governor his gouvernorat only, and the empty state without an axis", async () => {
    const api = fakeCrisisApi();
    api.crisisCommand = vi.fn(() => Promise.resolve(overview("governor")));
    renderApp(<CommandPage />, { api: fakeApi(api), auth: fakeAuth(claims(["governor"], "21")), lang: "ar" });
    expect(await screen.findByText(/فيضانات نابل، أكتوبر 2026/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText(/حرائق غابات عين دراهم/)).not.toBeInTheDocument();
  });

  it("says when no disaster is declared", async () => {
    const api = fakeCrisisApi();
    api.crisisCommand = vi.fn(() => Promise.resolve({ ...overview("governor"), axes: [], gouvernorats: [], needs: [] }));
    renderApp(<CommandPage />, { api: fakeApi(api), auth: fakeAuth(claims(["governor"], "21")), lang: "ar" });
    expect(await screen.findByText("لا كارثة أو أزمة معلنة في الولاية.")).toBeInTheDocument();
  });
});

describe("AxisPage", () => {
  it("shows the figures, the suggestions and the decisions of an axis to the room", async () => {
    const api = fakeCrisisApi();
    renderApp(<AxisPage />, {
      api: fakeApi(api),
      auth: fakeAuth(claims(["ops_manager"], "21")),
      lang: "fr",
      path: "/axes/ax-nabeul",
      route: "/axes/:id",
    });
    expect(await screen.findByText("Situation")).toBeInTheDocument();
    expect(screen.getByText("412")).toBeInTheDocument();
    expect(await screen.findByText(/Suggestions de rattachement \(2\)/)).toBeInTheDocument();
    const [attach] = screen.getAllByRole("button", { name: "Rattacher" });
    if (attach) fireEvent.click(attach);
    await waitFor(() => expect(api.attachAxisIncident).toHaveBeenCalledWith("ax-nabeul", "sg-1"));
    expect(screen.getByText("En conflit : la décision du ministre prévaut")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Points de situation" }));
    expect(await screen.findByText(/Point de situation 3/)).toBeInTheDocument();
  });
});

describe("AxesPage", () => {
  it("lets the commander accept a declaration request", async () => {
    const api = fakeCrisisApi();
    renderApp(<AxesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"])), lang: "ar" });
    expect(await screen.findByText(/طلبات إعلان بانتظار القائد/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "فتح محور" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "قبول وفتح المحور" }));
    await waitFor(() => expect(api.decideRequest).toHaveBeenCalledWith("rq-1", true, ""));
  });

  it("lets a regional manager request an axis, not open one", async () => {
    const api = fakeCrisisApi();
    renderApp(<AxesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "21")), lang: "ar" });
    expect(await screen.findByRole("button", { name: "طلب إعلان محور" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "فتح محور" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "قبول وفتح المحور" })).not.toBeInTheDocument();
  });
});
