// covers: phase L3b (docs/phase-l/design-l3b.md §5, §6, §8): the register's advanced search and facets, recording a
// document, one document with its file, recommendations and links, the plan of an axis, the command screen's plans,
// and the directives of the centre with the private reply threads of the gouvernorats.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canOpenRegister } from "../lib/roles";
import { searchParams, DEFAULT_QUERY, fileSize } from "../lib/register";
import { fakeCrisisApi, overview } from "../test/crisisFixtures";
import { DIRECTIVE_ALL_NABEUL, fakeRegisterApi, NOTICE } from "../test/registerFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { AxisPage } from "./AxisPage";
import { CommandPage } from "./CommandPage";
import { DispatchesPage, DispatchPage } from "./DispatchPages";
import { RegisterDocumentPage } from "./RegisterDocumentPage";
import { RegisterPage } from "./RegisterPage";

vi.mock("../components/crisis/CommandMap", () => ({
  CommandMap: (props: { ariaLabel: string }) => <div role="img" aria-label={props.ariaLabel} />,
}));

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("register helpers", () => {
  it("opens the register to the rooms, committees, governor and minister", () => {
    expect(canOpenRegister(["governor"])).toBe(true);
    expect(canOpenRegister(["minister"])).toBe(true);
    expect(canOpenRegister(["citizen"])).toBe(false);
  });

  it("builds the search parameters and file sizes", () => {
    const p = searchParams({ ...DEFAULT_QUERY, q: " فيضانات ", topic: "floods", from: "2026-01-01" });
    expect(p).toMatchObject({ q: "فيضانات", status: ["in_force"], topic: ["floods"], date_field: "issued", from: "2026-01-01" });
    expect(searchParams(DEFAULT_QUERY).date_field).toBeNull();
    expect(fileSize(2_457_600)).toBe("2.3 MB");
    expect(fileSize(300)).toBe("1 KB");
  });
});

describe("RegisterPage", () => {
  it("searches with facets and the advanced filters", async () => {
    const api = fakeRegisterApi();
    renderApp(<RegisterPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "21")), lang: "ar" });
    expect(await screen.findByText("[SIM] المخطط الجهوي للنجدة عند الفيضانات بولاية نابل")).toBeInTheDocument();
    expect(screen.getByText("4 وثيقة")).toBeInTheDocument();
    // In force by default; ticking a kind narrows the search.
    expect(vi.mocked(api.registerSearch).mock.calls[0]?.[0].statuses).toEqual(["in_force"]);
    fireEvent.click(screen.getByRole("checkbox", { name: /منشور/ }));
    await waitFor(() => expect(vi.mocked(api.registerSearch).mock.lastCall?.[0].kinds).toEqual(["circular"]));
    fireEvent.click(screen.getByRole("button", { name: "بحث متقدم" }));
    fireEvent.change(screen.getByLabelText("نافذة في تاريخ"), { target: { value: "2025-07-01" } });
    await waitFor(() => expect(vi.mocked(api.registerSearch).mock.lastCall?.[0].inForceOn).toBe("2025-07-01"));
    // A regional room records regional documents only.
    fireEvent.click(screen.getByRole("button", { name: "تدوين وثيقة" }));
    const form = within(screen.getByRole("form", { name: "تدوين وثيقة في السجل" }));
    expect(form.getByLabelText("المستوى")).toBeDisabled();
    fireEvent.change(form.getByLabelText("العنوان"), { target: { value: "مخطط حرائق الغابات" } });
    fireEvent.change(form.getByLabelText("الجهة المصدرة"), { target: { value: "والي نابل" } });
    fireEvent.click(form.getByRole("button", { name: "تدوين ونشر" }));
    await waitFor(() => expect(api.createDocument).toHaveBeenCalled());
    expect(vi.mocked(api.createDocument).mock.calls[0]?.[0]).toMatchObject({ level: "regional", gouvernorat_code: 21, publish: true });
  });

  it("asks for the end date of a temporary instruction", async () => {
    const api = fakeRegisterApi();
    renderApp(<RegisterPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "21")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "تدوين وثيقة" }));
    fireEvent.change(screen.getByLabelText("النوع"), { target: { value: "temporary_instruction" } });
    fireEvent.change(screen.getByLabelText("العنوان"), { target: { value: "منع السباحة" } });
    fireEvent.change(screen.getByLabelText("الجهة المصدرة"), { target: { value: "المدير الجهوي" } });
    fireEvent.click(screen.getByRole("button", { name: "تدوين ونشر" }));
    expect(await screen.findByText("أكمل الحقول المعلّمة.")).toBeInTheDocument();
    expect(api.createDocument).not.toHaveBeenCalled();
  });
});

describe("RegisterDocumentPage", () => {
  it("shows the file, the recommendations and the links of a plan", async () => {
    const api = fakeRegisterApi();
    renderApp(<RegisterDocumentPage />, {
      api: fakeApi(api),
      auth: fakeAuth(claims(["ops_manager"], "21")),
      lang: "ar",
      path: "/register/reg-plan",
      route: "/register/:id",
    });
    expect(await screen.findByText("مخطط-النجدة-نابل-2026.pdf")).toBeInTheDocument();
    expect(screen.getByText("أهم التوصيات (2 مفتوحة من 3)")).toBeInTheDocument();
    expect(screen.getByText("متأخرة", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText("تلغي").length).toBeGreaterThan(0);
    expect(screen.getByText("مكمّلة بـ")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("التوصية"), { target: { value: "تركيز نقطة تجمع إضافية" } });
    fireEvent.click(screen.getByRole("button", { name: "إضافة توصية" }));
    await waitFor(() => expect(api.addRecommendation).toHaveBeenCalledWith("reg-plan", expect.objectContaining({ body: "تركيز نقطة تجمع إضافية" })));
    fireEvent.click(screen.getByRole("button", { name: "النسخ" }));
    expect(await screen.findByText(/إدراج مراكز إيواء جديدة/)).toBeInTheDocument();
  });

  it("lets nobody edit a decision recorded from an axis", async () => {
    const api = fakeRegisterApi();
    const detail = await api.registerDocument("x");
    api.registerDocument = vi.fn(() => Promise.resolve({ ...detail, document: { ...detail.document, can_edit: false, source: "axis" as const, signed: true } }));
    renderApp(<RegisterDocumentPage />, {
      api: fakeApi(api),
      auth: fakeAuth(claims(["governor"], "21")),
      lang: "ar",
      path: "/register/reg-plan",
      route: "/register/:id",
    });
    expect(await screen.findByText("قرار أو توصية محور، موقّع إلكترونيا")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تعديل" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "إضافة توصية" })).not.toBeInTheDocument();
  });
});

describe("register in the axis and the command screen", () => {
  it("links the plan of an axis and lists its documents", async () => {
    renderApp(<AxisPage />, {
      api: fakeApi({ ...fakeCrisisApi(), ...fakeRegisterApi() }),
      auth: fakeAuth(claims(["ops_manager"], "21")),
      lang: "ar",
      path: "/axes/ax-nabeul",
      route: "/axes/:id",
    });
    const plan = await screen.findByRole("link", { name: "[SIM] المخطط الجهوي للنجدة عند الفيضانات بولاية نابل" });
    expect(plan).toHaveAttribute("href", "/register/reg-plan");
    fireEvent.click(screen.getByRole("tab", { name: "الوثائق" }));
    expect(within(screen.getByRole("tabpanel")).getAllByRole("link")).toHaveLength(2);
  });

  it("shows the governor the plans and recommendations in force", async () => {
    const crisis = fakeCrisisApi();
    crisis.crisisCommand = vi.fn(() => Promise.resolve(overview("governor")));
    const register = fakeRegisterApi();
    renderApp(<CommandPage />, { api: fakeApi({ ...crisis, ...register }), auth: fakeAuth(claims(["governor"], "21")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "المخططات والتوصيات" }));
    expect(await screen.findByText("[SIM] منشور حول الاستعداد لموسم الأمطار 2026-2027")).toBeInTheDocument();
    expect(vi.mocked(register.registerSearch).mock.calls[0]?.[0]).toMatchObject({ sort: "newest", statuses: ["in_force"] });
  });
});

describe("directives and replies", () => {
  it("lets the centre follow a general directive and answer each gouvernorat", async () => {
    const api = fakeRegisterApi();
    renderApp(<DispatchPage />, {
      api: fakeApi(api),
      auth: fakeAuth(claims(["ops_manager"])),
      lang: "ar",
      path: "/register/dispatches/dsp-all",
      route: "/register/dispatches/:id",
    });
    expect(await screen.findByText("المتابعة: ردّت 14 واطّلعت 19 من 24")).toBeInTheDocument();
    expect(screen.getByText("خيط ولاية نابل")).toBeInTheDocument();
    expect(screen.getByText("خيط ولاية سوسة")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "نموذج-جرد-وسائل-الضخ.xlsx" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("رد إلى ولاية سوسة"), { target: { value: "وصل التقرير" } });
    const sousse = screen.getByRole("region", { name: "خيط ولاية سوسة" });
    fireEvent.click(within(sousse).getByRole("button", { name: "إرسال" }));
    await waitFor(() => expect(api.replyDispatch).toHaveBeenCalledWith("dsp-all", "وصل التقرير", 51));
  });

  it("shows a gouvernorat only its own thread and sends its reply with files", async () => {
    const api = fakeRegisterApi();
    api.dispatch = vi.fn(() => Promise.resolve(DIRECTIVE_ALL_NABEUL));
    renderApp(<DispatchPage />, {
      api: fakeApi(api),
      auth: fakeAuth(claims(["ops_manager"], "21")),
      lang: "ar",
      path: "/register/dispatches/dsp-all",
      route: "/register/dispatches/:id",
    });
    expect(await screen.findByText("خيط ولاية نابل")).toBeInTheDocument();
    expect(screen.queryByText("خيط ولاية سوسة")).not.toBeInTheDocument();
    expect(screen.queryByText(/المتابعة/)).not.toBeInTheDocument();
    const file = new File(["a,b\n1,2\n"], "جدول.csv", { type: "text/csv" });
    const [input] = screen.getAllByLabelText("إرفاق ملفات");
    if (input) fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "إرسال" }));
    await waitFor(() => expect(api.attachToDispatch).toHaveBeenCalledWith("dsp-all", file, "جدول.csv", "rp-new"));
    expect(api.replyDispatch).toHaveBeenCalledWith("dsp-all", "", null);
  });

  it("lists the inbox and lets a regional room raise an immediate notice", async () => {
    const api = fakeRegisterApi();
    api.dispatches = vi.fn(() => Promise.resolve({ items: [NOTICE], total: 1, unread: 0, can_direct: false, can_notify: true }));
    renderApp(<DispatchesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    expect(await screen.findByText("[SIM] انهيار جزئي لجسر وادي الشيوخ على الطريق 27")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "توجيه جديد" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "إشعار فوري" }));
    fireEvent.change(screen.getByLabelText("الموضوع"), { target: { value: "تسرب غاز بالمنطقة الصناعية" } });
    fireEvent.change(screen.getByLabelText("النص"), { target: { value: "إخلاء 3 مصانع" } });
    fireEvent.click(screen.getByRole("button", { name: "رفع الإشعار" }));
    await waitFor(() => expect(api.sendDispatch).toHaveBeenCalled());
    expect(vi.mocked(api.sendDispatch).mock.calls[0]?.[0]).toMatchObject({ kind: "notice", urgency: "flash" });
  });

  it("lets the centre send a directive to chosen gouvernorats only", async () => {
    const api = fakeRegisterApi();
    renderApp(<DispatchesPage />, { api: fakeApi(api), auth: fakeAuth(claims(["central_committee"])), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "توجيه جديد" }));
    fireEvent.click(screen.getByRole("radio", { name: "خاص بولاية أو أكثر" }));
    fireEvent.change(screen.getByLabelText("الموضوع"), { target: { value: "تأمين السدود" } });
    fireEvent.change(screen.getByLabelText("النص"), { target: { value: "تقرير كل ساعتين" } });
    fireEvent.click(screen.getByRole("button", { name: "إرسال التوجيه" }));
    expect(await screen.findByText(/واختر الولايات/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("checkbox", { name: "تونس" }));
    fireEvent.click(screen.getByRole("button", { name: "إرسال التوجيه" }));
    await waitFor(() => expect(api.sendDispatch).toHaveBeenCalled());
    expect(vi.mocked(api.sendDispatch).mock.calls[0]?.[0]).toMatchObject({ audience: "targeted", gouvernorats: [11] });
  });
});
