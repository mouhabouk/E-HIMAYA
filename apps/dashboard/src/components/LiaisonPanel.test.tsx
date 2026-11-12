// covers: OS20 (design-os20.md): the level of a report, the engine's suggestions, the picker (search first, several at
// once, back to the report) and the record of a call dialled by hand.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ContactBody, IncidentLiaison, Party } from "../lib/liaison";
import { rankBodies } from "../lib/liaison";
import { makeIncidentDetail } from "../test/fixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { LiaisonPanel } from "./LiaisonPanel";

const body = (id: string, name: string, extra: Partial<ContactBody> = {}): ContactBody => ({
  id,
  gouvernorat_code: 61,
  category: "security",
  kind: "external",
  agency: null,
  name,
  domain: "الأمن",
  address: null,
  location: null,
  public_phone: null,
  status: "active",
  created_by_name: null,
  updated_at: "2026-11-12T08:00:00Z",
  updated_by_name: "عون",
  version: 1,
  editable: true,
  officials: [
    {
      id: `${id}-o1`,
      body_id: id,
      name: `رئيس ${name}`,
      role: "رئيس",
      phones: ["74 000 197"],
      email: null,
      duty: "24/24",
      position: 1,
      status: "active",
      updated_at: "2026-11-12T08:00:00Z",
      updated_by_name: null,
    },
  ],
  ...extra,
});

const party = (extra: Partial<Party> = {}): Party => ({
  id: "p1",
  body_id: "b-police",
  official_id: "b-police-o1",
  body_name: "إقليم الأمن بصفاقس",
  official_name: "رئيس الإقليم",
  official_role: "رئيس",
  phones: ["74 000 197"],
  public_phone: "197",
  agency: "police",
  category: "security",
  suggested: true,
  reason: "تأمين الطوق",
  added_by_name: "عون",
  added_at: "2026-11-12T08:00:00Z",
  removed_at: null,
  last_result: null,
  calls: [],
  ...extra,
});

function setup(state: Partial<IncidentLiaison> = {}, claims?: Record<string, unknown>) {
  const incident = makeIncidentDetail();
  const view: IncidentLiaison = {
    incident_id: incident.id,
    gouvernorat_code: 61,
    level: null,
    parties: [],
    suggestions: [
      {
        agency: "police",
        kind: "external",
        body_id: "b-police",
        name: "إقليم الأمن بصفاقس",
        public_phone: "197",
        reason: { ar: "تأمين الطوق وتنظيم المرور", fr: "périmètre" },
        missing: false,
        in_report: false,
      },
      {
        agency: "steg",
        kind: "external",
        body_id: null,
        name: "الشركة التونسية للكهرباء والغاز",
        public_phone: null,
        reason: { ar: "قطع الغاز والكهرباء", fr: "coupure" },
        missing: true,
        in_report: false,
      },
    ],
    ...state,
  };
  const level2 = { ...view, level: { level: 2 as const, note: null, set_by_name: "عون", set_at: "2026-11-12T08:00:00Z" } };
  const api = fakeApi({
    liaisonIncident: vi.fn(() => Promise.resolve(view)),
    liaisonSetLevel: vi.fn(() => Promise.resolve(level2)),
    liaisonBodies: vi.fn(() =>
      Promise.resolve([
        body("b-police", "إقليم الأمن بصفاقس"),
        body("b-gov", "ولاية صفاقس", { category: "regional", domain: "الإدارة الجهوية" }),
        body("b-hosp", "المستشفى الجامعي الحبيب بورقيبة", { category: "public", domain: "الصحة" }),
      ]),
    ),
    liaisonAddParties: vi.fn(() => Promise.resolve({ ...level2, parties: [party()] })),
    liaisonBody: vi.fn(() => Promise.resolve(body("b-police", "إقليم الأمن بصفاقس"))),
    liaisonAddCall: vi.fn(() => Promise.resolve({} as never)),
  });
  const r = renderApp(<LiaisonPanel incident={incident} />, { api, ...(claims ? { auth: fakeAuth(claims) } : {}) });
  return { ...r, incident };
}

describe("rankBodies", () => {
  it("puts the matches of the search first, then the suggested ones", () => {
    const list = [body("a", "ولاية صفاقس"), body("b", "المستشفى الجهوي"), body("c", "إقليم الأمن")];
    expect(rankBodies(list, "", new Set(["c"])).map((b) => b.id)).toEqual(["c", "a", "b"]);
    expect(rankBodies(list, "المستشفى", new Set()).map((b) => b.id)).toEqual(["b"]);
    // An official's phone matches too.
    expect(rankBodies(list, "000 197", new Set()).map((b) => b.id)).toEqual(["a", "b", "c"]);
  });
});

describe("LiaisonPanel", () => {
  it("sets level 2 and shows the engine's suggestions, a missing body flagged", async () => {
    const { api, incident } = setup();
    fireEvent.click(await screen.findByRole("radio", { name: /المستوى 2/ }));
    await waitFor(() => expect(api.liaisonSetLevel).toHaveBeenCalledWith(incident.id, 2));
    expect(await screen.findByText("مقترحات محرك القرار")).toBeInTheDocument();
    expect(screen.getByText("غير موجودة في نظام الاتصال")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "أضف" }));
    await waitFor(() =>
      expect(api.liaisonAddParties).toHaveBeenCalledWith(incident.id, [
        { body_id: "b-police", suggested: true, reason: "تأمين الطوق وتنظيم المرور" },
      ]),
    );
  });

  it("picks several bodies, the search first, and returns to the report", async () => {
    const level = { level: 2 as const, note: null, set_by_name: "عون", set_at: "2026-11-12T08:00:00Z" };
    const { api, incident } = setup({ level });
    fireEvent.click(await screen.findByRole("button", { name: "اختيار المشاركين" }));
    const dialog = await screen.findByRole("dialog", { name: "اختيار المشاركين في البلاغ" });
    fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "المستشفى" } });
    expect(await within(dialog).findByText(/نتائج البحث عن «المستشفى» \(1\)/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /رئيس المستشفى/ }));
    fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "" } });
    fireEvent.click(await within(dialog).findByRole("checkbox", { name: /رئيس ولاية صفاقس/ }));
    expect(within(dialog).getByText("2 مختار")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /تمّ الاختيار/ }));
    await waitFor(() =>
      expect(api.liaisonAddParties).toHaveBeenCalledWith(incident.id, [
        { body_id: "b-hosp", official_id: "b-hosp-o1", suggested: false, reason: null },
        { body_id: "b-gov", official_id: "b-gov-o1", suggested: false, reason: null },
      ]),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await screen.findByText("رئيس الإقليم · رئيس ·", { exact: false })).toBeInTheDocument();
  });

  it("records a call dialled by hand: no answer and a reminder", async () => {
    const level = { level: 2 as const, note: null, set_by_name: "عون", set_at: "2026-11-12T08:00:00Z" };
    const { api, incident } = setup({ level, parties: [party()] });
    fireEvent.click(await screen.findByRole("button", { name: "اتصال يدوي ثم تسجيل" }));
    fireEvent.click(await screen.findByRole("radio", { name: "لا رد" }));
    fireEvent.click(screen.getByRole("radio", { name: "بعد 10 د" }));
    fireEvent.click(screen.getByRole("button", { name: "سجّل المكالمة" }));
    await waitFor(() =>
      expect(api.liaisonAddCall).toHaveBeenCalledWith(
        incident.id,
        "p1",
        expect.objectContaining({ via: "manual", result: "no_answer", number: "74 000 197", follow_up_min: 10 }),
      ),
    );
  });

  it("gives a reader no button", async () => {
    const level = { level: 2 as const, note: null, set_by_name: "عون", set_at: "2026-11-12T08:00:00Z" };
    setup({ level, parties: [party()] }, AUDITOR_CLAIMS);
    expect(await screen.findAllByText("إقليم الأمن بصفاقس", { selector: "strong" })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "اختيار المشاركين" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "اتصال يدوي ثم تسجيل" })).not.toBeInTheDocument();
  });
});
