import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { decidedVisit, inspectedVisit, makeReservation, makeVisit } from "../test/preventionFixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { counterCode } from "./CounterPage";
import { addDays, addMonths, PreventionPage, VisitPage } from "./PreventionPages";

const route = "/orgs/prevention/:id";
const auditor = () => fakeAuth(AUDITOR_CLAIMS);

describe("date helpers", () => {
  it("adds months without overflowing the month, and days", () => {
    expect(addMonths("2026-01-31", 1)).toBe("2026-02-28");
    expect(addMonths("2026-10-25", 12)).toBe("2027-10-25");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });

  it("reads a prevention certificate code at the counter", () => {
    expect(counterCode("https://portail.example/verify/EHP-26-61-000009")).toBe("EHP-26-61-000009");
  });
});

describe("PreventionPage", () => {
  it("lists the open visits by default, with overdue reservations", async () => {
    const visits = [
      makeVisit(),
      decidedVisit({ id: "v-2", reservations: [makeReservation({ state: "overdue" })] }),
    ];
    const api = fakeApi({ preventionVisits: vi.fn(() => Promise.resolve({ items: visits, next_cursor: null })) });
    renderApp(<PreventionPage />, { api, lang: "fr", path: "/orgs/prevention", auth: auditor() });
    const list = await screen.findByRole("list", { name: "Visites de prévention" });
    expect(api.preventionVisits).toHaveBeenCalledWith(
      expect.objectContaining({ status: ["requested", "scheduled", "inspected"] }),
    );
    expect(within(list).getAllByRole("link", { name: "Société Chimique du Sud" })[0]).toHaveAttribute(
      "href",
      "/orgs/prevention/v-1",
    );
    expect(within(list).getByText("Demandée")).toBeInTheDocument();
    expect(within(list).getByText("Réserves en retard : 1")).toBeInTheDocument();
  });
});

describe("VisitPage", () => {
  it("shows the visit on the inspector's phone, its signatures and its photos by item", async () => {
    const visit = inspectedVisit({
      inspector_name: "Leila Inspectrice",
      inspector_on_phone: true,
      signatures: {
        inspector_name: "Leila Inspectrice",
        inspector_url: "https://s3.example/sig-i.png",
        representative_name: "Sami Trabelsi",
        representative_role: "Directeur",
        representative_url: "https://s3.example/sig-r.png",
      },
      photos: [
        {
          id: "p-1",
          item_key: "site.exits",
          content_type: "image/jpeg",
          bytes: 1200,
          created_by_name: "Leila Inspectrice",
          device_at: "2026-10-27T09:30:00Z",
          created_at: "2026-10-27T10:00:00Z",
          url: "https://s3.example/p-1.jpg",
        },
        {
          id: "p-2",
          item_key: null,
          content_type: "image/jpeg",
          bytes: 900,
          created_by_name: "Leila Inspectrice",
          device_at: null,
          created_at: "2026-10-27T10:01:00Z",
          url: "https://s3.example/p-2.jpg",
        },
      ],
    });
    const api = fakeApi({ preventionVisit: vi.fn(() => Promise.resolve(visit)) });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route, auth: auditor() });
    const field = await screen.findByRole("region", { name: "Sur site : signatures et photos" });
    expect(screen.getByText("Sur le téléphone")).toBeInTheDocument();
    expect(within(field).getByRole("img", { name: "Signature du représentant" })).toHaveAttribute(
      "src",
      "https://s3.example/sig-r.png",
    );
    expect(within(field).getByText("Sami Trabelsi · Directeur")).toBeInTheDocument();
    expect(within(field).getByRole("heading", { name: "Photos (2)" })).toBeInTheDocument();
    expect(within(field).getByRole("img", { name: "Photo prise sur site : Issues de secours dégagées" })).toHaveAttribute(
      "src",
      "https://s3.example/p-1.jpg",
    );
    expect(within(field).getByRole("heading", { name: "Photos générales" })).toBeInTheDocument();
  });

  it("schedules a requested visit", async () => {
    const api = fakeApi({
      preventionVisit: vi.fn(() => Promise.resolve(makeVisit())),
      scheduleVisit: vi.fn(() => Promise.resolve(makeVisit({ status: "scheduled", scheduled_on: "2030-01-10" }))),
    });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route, auth: auditor() });
    const form = await screen.findByRole("form", { name: "Programmer la visite" });
    fireEvent.change(within(form).getByLabelText("Date de visite"), { target: { value: "2030-01-10" } });
    fireEvent.change(within(form).getByLabelText("Inspecteur"), { target: { value: "Cdt Ben Salah" } });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer la date" }));
    await waitFor(() =>
      expect(api.scheduleVisit).toHaveBeenCalledWith("v-1", { scheduled_on: "2030-01-10", inspector_name: "Cdt Ben Salah" }),
    );
    expect(await screen.findByText("Date enregistrée, l’établissement est prévenu.")).toBeInTheDocument();
  });

  it("records the inspection grid and asks for a detail on each non-conformity", async () => {
    const visit = makeVisit({ status: "scheduled", scheduled_on: "2026-10-01", inspector_name: "Cdt Ben Salah" });
    const api = fakeApi({
      preventionVisit: vi.fn(() => Promise.resolve(visit)),
      recordInspection: vi.fn(() => Promise.resolve(inspectedVisit())),
    });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route, auth: auditor() });
    const form = await screen.findByRole("form", { name: "Grille d’inspection sur site" });
    expect(within(form).getByRole("rowheader", { name: /Issues de secours dégagées/ })).toHaveTextContent("[SIM]");
    expect(within(form).getByRole("row", { name: /Matière dangereuse 1/ })).toHaveTextContent("Chlore (UN 1017): 200 kg");
    fireEvent.click(within(form).getByRole("button", { name: "Marquer les points non vérifiés conformes" }));
    fireEvent.change(within(form).getByLabelText("Résultat : Issues de secours dégagées"), {
      target: { value: "nonconform" },
    });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer et comparer" }));
    expect(within(form).getByText(/Chaque point non conforme/)).toBeInTheDocument();
    expect(api.recordInspection).not.toHaveBeenCalled();

    fireEvent.change(within(form).getByLabelText("Remarque : Issues de secours dégagées"), {
      target: { value: "Issue B encombrée" },
    });
    fireEvent.change(within(form).getByLabelText("Présents"), { target: { value: "Directeur" } });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer et comparer" }));
    await waitFor(() => expect(api.recordInspection).toHaveBeenCalled());
    const body = vi.mocked(api.recordInspection).mock.calls[0]?.[1];
    expect(body?.attendees).toBe("Directeur");
    expect(body?.items).toContainEqual({ key: "site.exits", result: "nonconform", observed: null, note: "Issue B encombrée" });
    expect(body?.items.filter((i) => i.result === "conform")).toHaveLength(3);
  });

  it("shows the comparison and decides with reservations proposed from the non-conformities", async () => {
    const api = fakeApi({
      preventionVisit: vi.fn(() => Promise.resolve(inspectedVisit())),
      decideVisit: vi.fn(() => Promise.resolve(decidedVisit())),
    });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route, auth: auditor() });
    const report = await screen.findByRole("region", { name: "Rapport de comparaison" });
    expect(within(report).getByText("Non conformes : 2")).toBeInTheDocument();
    expect(within(report).getByText(/Suggestion non contraignante : Avis favorable avec réserves/)).toBeInTheDocument();
    expect(within(report).getByRole("row", { name: /Capacité d’accueil/ })).toHaveTextContent("420");

    const form = screen.getByRole("form", { name: "Décision" });
    expect(within(form).getByLabelText("Avis favorable avec réserves")).toBeChecked();
    expect(within(form).getByLabelText("Réserve 1")).toHaveValue("Capacité d’accueil — 420");
    expect(within(form).getByLabelText("Réserve 2")).toHaveValue("Issues de secours dégagées — Issue B encombrée");
    fireEvent.click(within(form).getByRole("button", { name: "Rendre la décision" }));
    await waitFor(() => expect(api.decideVisit).toHaveBeenCalled());
    const body = vi.mocked(api.decideVisit).mock.calls[0]?.[1];
    expect(body?.decision).toBe("approved_with_reservations");
    expect(body?.reservations.map((r) => r.item_key)).toEqual(["building.capacity", "site.exits"]);
    expect(body?.valid_until).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(await screen.findByText("Décision rendue, l’établissement est prévenu.")).toBeInTheDocument();
  });

  it("refuses only with a reason, and sends no reservation", async () => {
    const api = fakeApi({
      preventionVisit: vi.fn(() => Promise.resolve(inspectedVisit())),
      decideVisit: vi.fn(() => Promise.resolve(decidedVisit({ decision: "refused", certificate: null, reservations: [] }))),
    });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route, auth: auditor() });
    const form = await screen.findByRole("form", { name: "Décision" });
    fireEvent.click(within(form).getByLabelText("Avis défavorable motivé"));
    fireEvent.click(within(form).getByRole("button", { name: "Rendre la décision" }));
    expect(within(form).getByText("Un motif est obligatoire pour cette décision.")).toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText("Motif du refus (obligatoire)"), { target: { value: "Issues encombrées" } });
    fireEvent.click(within(form).getByRole("button", { name: "Rendre la décision" }));
    await waitFor(() =>
      expect(api.decideVisit).toHaveBeenCalledWith("v-1", {
        decision: "refused",
        reason: "Issues encombrées",
        valid_until: null,
        reservations: [],
      }),
    );
  });

  it("shows the decision, the certificate and lifts a reservation", async () => {
    const api = fakeApi({
      preventionVisit: vi.fn(() => Promise.resolve(decidedVisit())),
      liftReservation: vi.fn(() => Promise.resolve(makeReservation({ state: "lifted" }))),
    });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route, auth: auditor() });
    const decision = await screen.findByRole("region", { name: "Décision" });
    expect(within(decision).getByText("EHP-26-61-000009")).toBeInTheDocument();
    expect(within(decision).getByText("En retard")).toBeInTheDocument();
    const lifts = within(decision).getAllByRole("button", { name: "Lever la réserve" });
    fireEvent.click(lifts[0] as HTMLElement);
    await waitFor(() => expect(api.liftReservation).toHaveBeenCalledWith("r-1", null));
    expect(screen.queryByRole("form", { name: "Décision" })).not.toBeInTheDocument();
  });

  it("is read only for other readers", async () => {
    const api = fakeApi({ preventionVisit: vi.fn(() => Promise.resolve(makeVisit({ status: "scheduled", scheduled_on: "2026-10-30" }))) });
    renderApp(<VisitPage />, { api, lang: "fr", path: "/orgs/prevention/v-1", route });
    expect(await screen.findByText(/Lecture seule/)).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Grille d’inspection sur site" })).not.toBeInTheDocument();
  });
});
