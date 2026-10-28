// covers: phase L5b (docs/phase-l/design-l5.md §3.3): the drones page. A room sees its drones as read-only sources
// (position, altitude, battery), acknowledges the open alerts of their zones and battery, and the operations manager
// registers a drone (publish token shown once) and draws work and no-fly zones. Nothing is ever sent to a drone.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { isFresh, type Drone } from "../lib/drones";
import type { Vertex } from "../lib/polygon";
import { canAcknowledgeDroneAlerts, canManageDrones, canOpenDrones } from "../lib/roles";
import { DRONE, DRONE_CREATED, DRONES, fakeDronesApi } from "../test/dronesFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { DronesPage } from "./DronesPage";

// MapLibre does not run in jsdom: a stand-in map adds the corners of a square, one per click.
const SQUARE: Vertex[] = [
  [8.64, 36.73],
  [8.74, 36.73],
  [8.74, 36.83],
  [8.64, 36.83],
];
vi.mock("../components/LazyPolygonMap", () => ({
  LazyPolygonDrawMap: ({
    vertices,
    onAddVertex,
    ariaLabel,
  }: {
    vertices: readonly Vertex[];
    onAddVertex?: (lon: number, lat: number) => void;
    ariaLabel: string;
  }) => (
    <div role="img" aria-label={ariaLabel}>
      {onAddVertex && (
        <button
          type="button"
          onClick={() => {
            const [lon, lat] = SQUARE[vertices.length % SQUARE.length] ?? [0, 0];
            onAddVertex(lon, lat);
          }}
        >
          fake-click
        </button>
      )}
    </div>
  ),
}));

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("drone rules", () => {
  it("opens the page to the rooms, the register and zones to the operations manager", () => {
    expect(canOpenDrones(["operator"])).toBe(true);
    expect(canOpenDrones(["citizen"])).toBe(false);
    expect(canManageDrones(["operator"])).toBe(false);
    expect(canManageDrones(["ops_manager"])).toBe(true);
    expect(canAcknowledgeDroneAlerts(["operator"])).toBe(true);
    expect(canAcknowledgeDroneAlerts(["central_committee"])).toBe(false);
  });

  it("calls a drone flying only while its position is fresh", () => {
    const now = Date.now();
    expect(isFresh(DRONE, now)).toBe(true);
    const old: Drone = { ...DRONE, last: DRONE.last && { ...DRONE.last, at: new Date(now - 600_000).toISOString() } };
    expect(isFresh(old, now)).toBe(false);
    expect(isFresh({ ...DRONE, last: null }, now)).toBe(false);
  });
});

describe("DronesPage", () => {
  it("lists the drones with the alerts first and lets an agent acknowledge one", async () => {
    const api = fakeDronesApi();
    api.drones = vi.fn(() => Promise.resolve({ items: [...DRONES].reverse(), can_register: false }));
    renderApp(<DronesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "32")), lang: "ar" });
    expect(await screen.findByText("لا ترسل المنظومة أي أمر إلى الدرون: الطيار وحده يقوده.")).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "الدرونات (2)" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("درون الحماية 1");
    expect(rows[0]).toHaveTextContent("في الجو الآن");
    expect(rows[0]).toHaveTextContent("ارتفاع 120 م · بطارية 24٪");
    expect(rows[0]).toHaveTextContent("2 تنبيه مفتوح");
    expect(rows[1]).toHaveTextContent("لا موقع بعد");
    expect(rows[1]).toHaveTextContent("لا يبث");
    expect(screen.queryByRole("button", { name: "تسجيل درون" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "رسم منطقة" })).not.toBeInTheDocument();
    const alerts = screen.getByRole("region", { name: "تنبيهات مفتوحة (2)" });
    expect(alerts).toHaveTextContent("يقترب من منطقة حظر");
    expect(alerts).toHaveTextContent("على بعد 1.668 م");
    expect(alerts).toHaveTextContent("بطارية منخفضة");
    expect(alerts).not.toHaveTextContent("خرج من منطقة العمل");
    fireEvent.click(within(alerts).getAllByRole("button", { name: "تمّ الاطلاع" })[0] as HTMLElement);
    await waitFor(() => expect(api.acknowledgeDroneAlert).toHaveBeenCalledWith(2));
    const zones = screen.getByRole("region", { name: "مناطق العمل والحظر" });
    expect(zones).toHaveTextContent("غابة عين دراهم");
    expect(zones).toHaveTextContent("منطقة حظر");
    expect(zones).toHaveTextContent("2.000 م");
  });

  it("lets the operations manager register a drone and shows its token once", async () => {
    const api = fakeDronesApi();
    renderApp(<DronesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "32")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "تسجيل درون" }));
    const form = screen.getByRole("form", { name: "تسجيل درون" });
    fireEvent.click(within(form).getByRole("button", { name: "تسجيل" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("الاسم إجباري.");
    fireEvent.change(within(form).getByLabelText("الاسم"), { target: { value: "درون جديد" } });
    fireEvent.click(within(form).getByRole("button", { name: "تسجيل" }));
    await waitFor(() => expect(api.registerDrone).toHaveBeenCalledWith({ label: "درون جديد", gouvernorat_code: null }));
    const panel = await screen.findByRole("region", { name: `عنوان بث ${DRONE_CREATED.drone.label}` });
    expect(panel).toHaveTextContent(DRONE_CREATED.publish_token);
    expect(panel).toHaveTextContent(DRONE_CREATED.publish_url_rtmp);
    fireEvent.click(within(panel).getByRole("button", { name: "تم، أخفِ المفتاح" }));
    expect(screen.queryByText(DRONE_CREATED.publish_token)).not.toBeInTheDocument();
  });

  it("lets the operations manager draw a no-fly zone with its margin", async () => {
    const api = fakeDronesApi();
    renderApp(<DronesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "32")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "رسم منطقة" }));
    const form = await screen.findByRole("form", { name: "منطقة جديدة" });
    fireEvent.click(within(form).getByRole("radio", { name: "منطقة حظر" }));
    fireEvent.change(within(form).getByLabelText("اسم المنطقة"), { target: { value: "مطار طبرقة" } });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("ارسم 3 نقاط على الأقل.");
    const map = await within(form).findByRole("img", { name: "خريطة رسم المنطقة" });
    for (let i = 0; i < 4; i += 1) fireEvent.click(within(map).getByRole("button", { name: "fake-click" }));
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    await waitFor(() =>
      expect(api.createZone).toHaveBeenCalledWith({
        kind: "no_fly",
        name: "مطار طبرقة",
        ring: SQUARE,
        margin_m: 500,
        gouvernorat_code: null,
      }),
    );
  });
});
