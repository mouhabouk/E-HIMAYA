// covers: phase N (docs/phase-n/design-n.md §3): the disaster view for the committees, ongoing and closed, with the
// choice of disasters and gouvernorats and the map of the chosen disasters' places only.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GOUVERNORAT_BOUNDS, TUNISIA_BOUNDS } from "../lib/mapStyle";
import { canOpenAxes, canOpenDisasters } from "../lib/roles";
import { NABEUL_AXIS } from "../test/crisisData";
import { fakeCrisisApi } from "../test/crisisFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { promoteLink, readPromotion } from "../lib/crisisText";
import { AxesPage } from "./AxesPage";
import { DisastersPage, gouvernoratsBounds } from "./DisastersPage";

vi.mock("../components/crisis/CommandMap", () => ({
  CommandMap: (props: { ariaLabel: string; incidents?: unknown[]; focus?: number[] }) => (
    <div role="img" aria-label={props.ariaLabel} data-incidents={props.incidents?.length ?? 0} data-focus={JSON.stringify(props.focus ?? [])} />
  ),
}));

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

const GOUVERNORATS = [
  { code: 21, iso_code: "TN-21", name: "نابل", name_ar: "نابل", name_fr: "Nabeul", delegation_count: 16 },
  { code: 32, iso_code: "TN-32", name: "جندوبة", name_ar: "جندوبة", name_fr: "Jendouba", delegation_count: 9 },
  { code: 51, iso_code: "TN-51", name: "سوسة", name_ar: "سوسة", name_fr: "Sousse", delegation_count: 16 },
];
const gouvernorats = vi.fn(() => Promise.resolve(GOUVERNORATS));

describe("DisastersPage", () => {
  it("opens for the rooms, the commander and both committees, not for the other accounts", () => {
    for (const r of ["operator", "ops_manager", "governor", "minister", "local_committee", "central_committee"]) expect(canOpenDisasters([r])).toBe(true);
    expect(canOpenDisasters(["doctor_reviewer"])).toBe(false);
    expect(canOpenAxes(["central_committee"])).toBe(false);
    expect(gouvernoratsBounds([])).toEqual(TUNISIA_BOUNDS);
    const both = gouvernoratsBounds([21, 51]);
    expect(both[3]).toBe(GOUVERNORAT_BOUNDS[21]?.[3]);
    expect(both[1]).toBe(Math.min(GOUVERNORAT_BOUNDS[21]?.[1] ?? 0, GOUVERNORAT_BOUNDS[51]?.[1] ?? 0));
  });

  it("shows the national committee the summary and the map of the chosen disasters", async () => {
    const api = fakeCrisisApi();
    renderApp(<DisastersPage />, { api: fakeApi({ ...api, gouvernorats }), auth: fakeAuth(claims(["central_committee"])), lang: "ar" });
    expect(await screen.findByText("اللجنة الوطنية برئاسة السيد وزير الداخلية")).toBeInTheDocument();
    expect(await screen.findByText("حوصلة الكوارث المختارة: 3")).toBeInTheDocument();
    await waitFor(() => expect(api.disasterMap).toHaveBeenCalled());
    expect(vi.mocked(api.disasterMap).mock.calls.at(-1)?.[0]).toHaveLength(3);
    // A committee reads the disasters but does not open the room's axis screen.
    expect(screen.queryByRole("link", { name: "فيضانات نابل، أكتوبر 2026" })).not.toBeInTheDocument();

    // Narrowing to one gouvernorat narrows the disasters and the map.
    const picker = screen.getByRole("group", { name: "الولايات المعروضة" });
    fireEvent.click(within(picker).getByRole("button", { name: "إلغاء التحديد" }));
    fireEvent.click(within(picker).getByRole("checkbox", { name: "نابل" }));
    expect(await screen.findByText("حوصلة الكوارث المختارة: 1")).toBeInTheDocument();
    await waitFor(() => expect(vi.mocked(api.disasterMap).mock.calls.at(-1)?.[0]).toEqual([NABEUL_AXIS.id]));
    expect(screen.getByRole("img").dataset.focus).toBe("[21]");
    // Unticking the last disaster asks for one.
    fireEvent.click(screen.getByRole("checkbox", { name: "عرض فيضانات نابل، أكتوبر 2026 على الخريطة" }));
    expect(await screen.findByText("اختر كارثة واحدة على الأقل.")).toBeInTheDocument();
  });

  it("lists the closed disasters with their final summary", async () => {
    const api = fakeCrisisApi();
    vi.mocked(api.crisisAxes).mockImplementation((status) =>
      Promise.resolve(
        status === "closed"
          ? [{ ...NABEUL_AXIS, status: "closed" as const, closed_at: "2026-10-20T18:00:00Z", closing: { ...NABEUL_AXIS.figures, hours: 52.5, summary: "عادت الحياة إلى طبيعتها في الأحياء المنكوبة." } }]
          : [],
      ),
    );
    renderApp(<DisastersPage />, { api: fakeApi({ ...api, gouvernorats }), auth: fakeAuth(claims(["local_committee"], "21")), lang: "ar" });
    expect(await screen.findByText("لا كارثة جارية.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "المغلقة" }));
    expect(await screen.findByText("عادت الحياة إلى طبيعتها في الأحياء المنكوبة.")).toBeInTheDocument();
    expect(screen.getByText(/بعد 52[.,٫]5 ساعة/)).toBeInTheDocument();
  });
});

describe("promoting an intervention to a disaster", () => {
  it("carries the intervention, its gouvernorat and the kind its category suggests", () => {
    const link = promoteLink({ id: "inc-7", category: "fire", title: "حريق غابة جبل عبد الرحمان", gouvernorat_code: 21 });
    expect(readPromotion(new URL(link, "http://x").searchParams)).toEqual({
      incident: "inc-7",
      name: "حريق غابة جبل عبد الرحمان",
      kind: "forest_fire",
      gouvernorat: 21,
    });
    expect(readPromotion(new URLSearchParams("promote=i&kind=poem"))?.kind).toBe("other");
    expect(readPromotion(new URLSearchParams(""))).toBeNull();
  });

  it("opens the commander's form with the intervention attached", async () => {
    const api = fakeCrisisApi();
    const link = promoteLink({ id: "inc-7", category: "flood", title: "فيضان وادي سوحيل", gouvernorat_code: 21 });
    renderApp(<AxesPage />, { api: fakeApi({ ...api, gouvernorats }), auth: fakeAuth(claims(["ops_manager"])), lang: "ar", path: link });
    expect(await screen.findByText("هذه الكارثة مرفوعة من تدخل: يُلحق بها منذ فتحها.")).toBeInTheDocument();
    expect(screen.getByLabelText("اسم المحور")).toHaveValue("فيضان وادي سوحيل");
    fireEvent.click(screen.getByRole("button", { name: "فتح المحور وإشعار اللجنة الجهوية واللجنة الوطنية" }));
    await waitFor(() => expect(api.openAxis).toHaveBeenCalled());
    expect(vi.mocked(api.openAxis).mock.calls[0]?.[0]).toMatchObject({ kind: "flood", gouvernorat_code: 21, incident_ids: ["inc-7"] });
  });

  it("opens a regional manager's declaration request with the intervention", async () => {
    const api = fakeCrisisApi();
    const link = promoteLink({ id: "inc-8", category: "chemical_leak", title: "تسرب غاز بالمنطقة الصناعية", gouvernorat_code: 21 });
    renderApp(<AxesPage />, { api: fakeApi({ ...api, gouvernorats }), auth: fakeAuth(claims(["ops_manager"], "21")), lang: "ar", path: link });
    expect(await screen.findByText("هذه الكارثة مرفوعة من تدخل: يُلحق بها منذ فتحها.")).toBeInTheDocument();
    expect(api.requestDeclaration).not.toHaveBeenCalled();
  });
});
