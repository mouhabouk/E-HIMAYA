// covers: phase L4 (docs/phase-l/design-l4.md §3 and §5): the decision window (the situation now, the quick search
// read back, small counts shown "<5", the comparison, an audited export), the delegated view on its events only, the
// grant of a delegation, and the menu entry.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { navGroups } from "../components/Navigation";
import { canOpenWindowFull } from "../lib/roles";
import { WINDOW_ACCESS_DELEGATED } from "../test/windowData";
import { fakeWindowApi } from "../test/windowFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { WindowPage } from "./WindowPage";

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("WindowPage", () => {
  it("shows the situation now, then a search read back with small counts hidden, and exports it", async () => {
    const win = fakeWindowApi();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => undefined }));
    renderApp(<WindowPage />, { api: fakeApi(win), auth: fakeAuth(claims(["ops_manager"], "21")), path: "/window" });
    expect(await screen.findByText(/AX-2026-004 · \[SIM\] حرائق غابات نابل/)).toBeInTheDocument();
    expect(screen.getByText("[SIM] إخلاء المنازل المحاذية لغابة دار شيشو")).toBeInTheDocument();
    expect(screen.getByText("المخطط الساري: [SIM] مخطط مجابهة حرائق الغابات")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "البحث" }));
    fireEvent.change(await screen.findByLabelText("بحث سريع"), { target: { value: "حرايق نابل" } });
    fireEvent.click(screen.getByRole("button", { name: "ابحث" }));
    await waitFor(() => expect(win.windowSearch).toHaveBeenLastCalledWith(expect.objectContaining({ q: "حرايق نابل" }), expect.anything()));
    expect(await screen.findByText(/حرايق → حريق/)).toBeInTheDocument();
    const byCategory = screen.getByRole("table", { name: "حسب النوع" });
    expect(within(byCategory).getByText(/<5/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "7d1f5a2e" })).toHaveAttribute("href", "/incidents/7d1f5a2e-0c4b-4c55-9f0e-2a6c1b9e8d01");

    fireEvent.click(screen.getByRole("button", { name: "اكتب ملخصا (ذكاء اصطناعي)" }));
    expect(await screen.findByText(/\[SIM\] سُجّل 42 تدخلا/)).toBeInTheDocument();
    expect(win.windowSummary).toHaveBeenCalledWith(expect.objectContaining({ kind: "search", lang: "ar" }));
    expect(screen.getAllByText("ملخص آلي استشاري").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "تقرير PDF" }));
    await waitFor(() => expect(win.windowExport).toHaveBeenCalledWith(expect.objectContaining({ kind: "search", format: "pdf", lang: "ar" })));
    vi.unstubAllGlobals();
  });

  it("compares two periods side by side", async () => {
    const win = fakeWindowApi();
    renderApp(<WindowPage />, { api: fakeApi(win), auth: fakeAuth(claims(["ops_manager"], "21")), path: "/window" });
    fireEvent.click(await screen.findByRole("tab", { name: "المقارنة" }));
    fireEvent.click(screen.getByRole("button", { name: "قارن" }));
    await waitFor(() => expect(win.windowCompare).toHaveBeenCalled());
    const [, query] = vi.mocked(win.windowCompare).mock.calls[0] ?? [];
    expect(query?.mode).toBe("periods");
    expect(query?.a_from).toMatch(/-07-01$/);
    expect(query?.b_to).toMatch(/-08-31$/);
    expect(await screen.findByRole("rowheader", { name: "التدخلات" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "الوفيات" }).closest("tr")).toHaveTextContent("<5");
  });

  it("opens to a delegate on the delegated events only, and refuses without a delegation", async () => {
    const win = fakeWindowApi();
    win.windowAccess = vi.fn(() => Promise.resolve(WINDOW_ACCESS_DELEGATED));
    renderApp(<WindowPage />, { api: fakeApi(win), auth: fakeAuth(claims(["governor"], "21")), path: "/window" });
    expect(await screen.findByText(/تفويض ساري إلى/)).toBeInTheDocument();
    expect(screen.getAllByText("AX-2026-004 · [SIM] حرائق غابات نابل").length).toBeGreaterThan(0);
    expect(screen.queryByRole("tab", { name: "التفويضات" })).not.toBeInTheDocument();

    const none = fakeWindowApi();
    none.windowAccess = vi.fn(() =>
      Promise.resolve({ full: false, delegated: false, may_delegate: false, keeps_dictionary: false, delegations: [] }),
    );
    renderApp(<WindowPage />, { api: fakeApi(none), auth: fakeAuth(claims(["minister"])), path: "/window" });
    expect(await screen.findByText(/لا يوجد تفويض ساري لحسابك/)).toBeInTheDocument();
    expect(none.windowNow).not.toHaveBeenCalled();
  });

  it("grants a delegation on a chosen axis, with its period and reason", async () => {
    const win = fakeWindowApi();
    renderApp(<WindowPage />, { api: fakeApi(win), auth: fakeAuth(claims(["ops_manager"], "21")), path: "/window" });
    fireEvent.click(await screen.findByRole("tab", { name: "التفويضات" }));
    const form = (await screen.findByRole("heading", { name: "تفويض جديد" })).closest("form") as HTMLFormElement;
    await within(form).findByRole("option", { name: /\[SIM\] والي نابل/ });
    fireEvent.change(within(form).getByLabelText("الحساب"), { target: { value: "gov-nabeul" } });
    fireEvent.change(within(form).getByLabelText("ينتهي في"), { target: { value: "2026-11-03T16:00" } });
    fireEvent.click(await within(form).findByRole("checkbox", { name: /AX-2026-004/ }));
    fireEvent.change(within(form).getByLabelText(/^السبب/), { target: { value: "[SIM] متابعة حرائق الغابات" } });
    fireEvent.click(within(form).getByRole("button", { name: "منح التفويض" }));
    await waitFor(() =>
      expect(win.grantDelegation).toHaveBeenCalledWith(
        expect.objectContaining({
          grantee: "gov-nabeul",
          events: [{ kind: "axis", id: "0b6f3c1d-4e2a-4b8f-9a7d-5c3e2f1a0b9c" }],
        }),
      ),
    );
    expect(await screen.findByText("[SIM] متابعة حرائق الغابات")).toBeInTheDocument();
  });
});

describe("window menu entry", () => {
  it("shows for the rooms, and for others only through a delegation", () => {
    const t = ((k: string) => k) as never;
    const links = (roles: string[], national: boolean, open?: boolean) =>
      navGroups({ subject: "s", name: "n", roles, gouvernoratCode: national ? null : 21, national, hasScope: true, mfa: true }, t, undefined, open)
        .flatMap((g) => g.items.map((i) => i.to));
    expect(canOpenWindowFull({ roles: ["operator"], national: true })).toBe(true);
    expect(canOpenWindowFull({ roles: ["operator"], national: false })).toBe(false);
    expect(canOpenWindowFull({ roles: ["ops_manager"], national: false })).toBe(true);
    expect(links(["ops_manager"], false)).toContain("/window");
    expect(links(["governor"], false)).not.toContain("/window");
    expect(links(["governor"], false, true)).toContain("/window");
  });
});
