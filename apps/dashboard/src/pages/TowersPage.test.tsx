// covers: phase L5b (docs/phase-l/design-l5.md §3.2): the watch towers page. A room sees its towers, the ones that saw
// fire or smoke in the last hour first, with the view in words and the latest detections; only the operations manager
// registers a tower, and the edge key and the camera's publish token are shown once.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canManageTowers, canOpenTowers } from "../lib/roles";
import { fakeTowersApi, TOWER_CREATED, TOWERS } from "../test/towersFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { compassOf } from "../lib/towers";
import { TowersPage } from "./TowersPage";

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("tower rules", () => {
  it("opens the page to the rooms and the register to the operations manager", () => {
    expect(canOpenTowers(["operator"])).toBe(true);
    expect(canOpenTowers(["citizen"])).toBe(false);
    expect(canManageTowers(["operator"])).toBe(false);
    expect(canManageTowers(["ops_manager"])).toBe(true);
  });

  it("names the bearing with a compass word", () => {
    expect([0, 44, 90, 225, 330, 359].map(compassOf)).toEqual(["n", "ne", "e", "sw", "nw", "n"]);
  });
});

describe("TowersPage", () => {
  it("lists the towers with a recent fire first and shows the detections of one", async () => {
    const api = fakeTowersApi();
    api.towers = vi.fn(() => Promise.resolve({ items: TOWERS, can_manage: false }));
    renderApp(<TowersPage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "32")), lang: "ar" });
    const table = await screen.findByRole("table", { name: "الأبراج (2)" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("برج عين دراهم");
    expect(rows[0]).toHaveTextContent("نار");
    expect(rows[0]).toHaveTextContent("شرقا (90°)، فتحة 60°، مدى 8 كم");
    expect(rows[0]).toHaveTextContent("تبث الآن");
    expect(rows[1]).toHaveTextContent("جنوب غرب");
    expect(rows[1]).toHaveTextContent("لا تبث");
    expect(screen.queryByRole("button", { name: "برج جديد" })).not.toBeInTheDocument();
    fireEvent.click(within(rows[0] as HTMLElement).getByRole("button", { name: "الكشوفات" }));
    const events = await screen.findByRole("table", { name: "آخر الكشوفات" });
    expect(within(events).getAllByRole("row")).toHaveLength(3);
    expect(events).toHaveTextContent("4 من 5");
    expect(api.towerEvents).toHaveBeenCalledWith("t-1", 24, expect.anything());
  });

  it("lets the operations manager register a tower and shows its keys once", async () => {
    const api = fakeTowersApi();
    renderApp(<TowersPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "32")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "برج جديد" }));
    const form = screen.getByRole("form", { name: "برج جديد" });
    fireEvent.change(within(form).getByLabelText("الرمز"), { target: { value: "JND-TWR-03" } });
    fireEvent.change(within(form).getByLabelText("الاسم"), { target: { value: "برج غار الدماء" } });
    fireEvent.change(within(form).getByLabelText("خط العرض"), { target: { value: "36.45" } });
    fireEvent.change(within(form).getByLabelText("خط الطول"), { target: { value: "8.43" } });
    const bearing = within(form).getByRole("spinbutton", { name: /اتجاه الكاميرا/ });
    fireEvent.change(bearing, { target: { value: "180" } });
    expect(within(form).getByText("جنوبا")).toBeInTheDocument();
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    await waitFor(() =>
      expect(api.createTower).toHaveBeenCalledWith({
        code: "JND-TWR-03",
        label: "برج غار الدماء",
        gouvernorat_code: null,
        lat: 36.45,
        lon: 8.43,
        bearing_deg: 180,
        fov_deg: 60,
        range_m: 8000,
        simulated: true,
      }),
    );
    const keys = await screen.findByRole("region", { name: `مفاتيح البرج ${TOWER_CREATED.tower.code}` });
    expect(keys).toHaveTextContent(TOWER_CREATED.edge_key);
    expect(keys).toHaveTextContent(TOWER_CREATED.publish_token);
    expect(keys).toHaveTextContent(TOWER_CREATED.publish_url_rtsp);
    fireEvent.click(within(keys).getByRole("button", { name: "تم، أخفِ المفتاح" }));
    expect(screen.queryByText(TOWER_CREATED.edge_key)).not.toBeInTheDocument();
  });

  it("requires the view and rotates a key after confirmation", async () => {
    const api = fakeTowersApi();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderApp(<TowersPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "32")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "برج جديد" }));
    const form = screen.getByRole("form", { name: "برج جديد" });
    fireEvent.change(within(form).getByLabelText("الرمز"), { target: { value: "JND-TWR-04" } });
    fireEvent.change(within(form).getByLabelText("الاسم"), { target: { value: "برج" } });
    fireEvent.change(within(form).getByLabelText("خط العرض"), { target: { value: "36.45" } });
    fireEvent.change(within(form).getByLabelText("خط الطول"), { target: { value: "8.43" } });
    fireEvent.change(within(form).getByRole("spinbutton", { name: /المدى/ }), { target: { value: "" } });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("الاتجاه والفتحة والمدى إجبارية.");
    expect(api.createTower).not.toHaveBeenCalled();
    fireEvent.click(within(form).getByRole("button", { name: "إلغاء" }));
    const buttons = await screen.findAllByRole("button", { name: "تجديد المفتاح" });
    fireEvent.click(buttons[0] as HTMLElement);
    expect(await screen.findByText("12".repeat(32))).toBeInTheDocument();
    expect(api.rotateTowerKey).toHaveBeenCalledTimes(1);
  });
});
