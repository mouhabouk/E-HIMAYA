// covers: phase L5b (docs/phase-l/design-l5.md §3.1): the sensors page. A room sees its sensors by urgency with their
// level in words, reads the last readings, and only the operations manager registers a sensor; the signing key is
// shown once after creation and after a rotation.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canManageSensors, canOpenSensors } from "../lib/roles";
import { fakeSensorsApi, SENSOR_KEY, SENSORS } from "../test/sensorsFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { SensorsPage } from "./SensorsPage";

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("sensor roles", () => {
  it("opens the page to the rooms and the register to the operations manager", () => {
    expect(canOpenSensors(["operator"])).toBe(true);
    expect(canOpenSensors(["citizen"])).toBe(false);
    expect(canManageSensors(["operator"])).toBe(false);
    expect(canManageSensors(["ops_manager"])).toBe(true);
  });
});

describe("SensorsPage", () => {
  it("lists the sensors by urgency and shows the readings of one", async () => {
    const api = fakeSensorsApi();
    // The fixtures are not in the page's order: the page sorts by urgency.
    api.sensors = vi.fn(() => Promise.resolve({ items: SENSORS, can_manage: false }));
    renderApp(<SensorsPage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "61")), lang: "ar" });
    const table = await screen.findByRole("table", { name: "الحساسات (3)" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getByRole("rowheader").textContent)).toEqual([
      expect.stringContaining("مقياس مطر وادي الشعبوني"),
      expect.stringContaining("منسوب وادي الشعبوني"),
      expect.stringContaining("حرارة صفاقس المدينة"),
    ]);
    expect(rows[0]).toHaveTextContent("إنذار");
    expect(rows[1]).toHaveTextContent("صامت");
    expect(screen.queryByRole("button", { name: "حساس جديد" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تجديد المفتاح" })).not.toBeInTheDocument();
    fireEvent.click(within(rows[0] as HTMLElement).getByRole("button", { name: "القراءات" }));
    const readings = await screen.findByRole("table", { name: "آخر القراءات" });
    expect(within(readings).getAllByRole("row")).toHaveLength(4);
    expect(api.sensorReadings).toHaveBeenCalledWith("s-1", 24, expect.anything());
  });

  it("lets the operations manager register a sensor and shows its key once", async () => {
    const api = fakeSensorsApi();
    renderApp(<SensorsPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "حساس جديد" }));
    const form = screen.getByRole("form", { name: "حساس جديد" });
    fireEvent.click(within(form).getByRole("radio", { name: "منسوب مياه" }));
    expect(within(form).getByRole("spinbutton", { name: /عتبة الانتباه/ })).toHaveValue(2);
    fireEvent.change(within(form).getByLabelText("الرمز"), { target: { value: "SFX-WADI-02" } });
    fireEvent.change(within(form).getByLabelText("الاسم"), { target: { value: "منسوب وادي الزيتون" } });
    fireEvent.change(within(form).getByLabelText("خط العرض"), { target: { value: "34.7" } });
    fireEvent.change(within(form).getByLabelText("خط الطول"), { target: { value: "10.7" } });
    fireEvent.change(within(form).getByLabelText("المزوّد"), { target: { value: "وزارة الفلاحة" } });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    await waitFor(() =>
      expect(api.createSensor).toHaveBeenCalledWith({
        code: "SFX-WADI-02",
        name: "منسوب وادي الزيتون",
        kind: "water_level",
        gouvernorat_code: null,
        lat: 34.7,
        lon: 10.7,
        provider: "وزارة الفلاحة",
        watch_threshold: 2,
        alarm_threshold: 3.5,
        silent_after_min: 30,
        simulated: true,
      }),
    );
    const key = await screen.findByRole("region", { name: `مفتاح الحساس ${SENSOR_KEY.sensor.code}` });
    expect(key).toHaveTextContent(SENSOR_KEY.key);
    fireEvent.click(within(key).getByRole("button", { name: "تم، أخفِ المفتاح" }));
    expect(screen.queryByText(SENSOR_KEY.key)).not.toBeInTheDocument();
  });

  it("refuses an alarm threshold below the watch threshold", async () => {
    const api = fakeSensorsApi();
    renderApp(<SensorsPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "حساس جديد" }));
    const form = screen.getByRole("form", { name: "حساس جديد" });
    fireEvent.change(within(form).getByLabelText("الرمز"), { target: { value: "SFX-R-9" } });
    fireEvent.change(within(form).getByLabelText("الاسم"), { target: { value: "مطر" } });
    fireEvent.change(within(form).getByLabelText("خط العرض"), { target: { value: "34.7" } });
    fireEvent.change(within(form).getByLabelText("خط الطول"), { target: { value: "10.7" } });
    fireEvent.change(within(form).getByLabelText("المزوّد"), { target: { value: "الديوان" } });
    fireEvent.change(within(form).getByRole("spinbutton", { name: /عتبة الإنذار/ }), { target: { value: "5" } });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("عتبة الإنذار لا تقل عن عتبة الانتباه.");
    expect(api.createSensor).not.toHaveBeenCalled();
  });

  it("rotates a key after confirmation and shows the new one", async () => {
    const api = fakeSensorsApi();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderApp(<SensorsPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    const buttons = await screen.findAllByRole("button", { name: "تجديد المفتاح" });
    fireEvent.click(buttons[0] as HTMLElement);
    expect(await screen.findByText("cd".repeat(32))).toBeInTheDocument();
    expect(api.rotateSensorKey).toHaveBeenCalledTimes(1);
  });
});
