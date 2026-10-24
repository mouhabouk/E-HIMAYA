// covers: phase C1-a (docs/phase-c/design-medical-axis.md §2): doctors' registrations checked by staff.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StaffDoctor, StaffDoctorDetail } from "../lib/doctorsApi";
import { canReviewDoctors, landingPath } from "../lib/roles";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { DoctorDetailPage } from "./DoctorDetailPage";
import { DoctorsPage } from "./DoctorsPage";

const COORDINATOR = {
  ...OPERATOR_CLAIMS,
  realm_access: { roles: ["medical_coordinator"] },
};

function doctor(overrides: Partial<StaffDoctorDetail> = {}): StaffDoctorDetail {
  return {
    id: "d-1",
    full_name: "Salma Trabelsi",
    kind: "civil_protection",
    specialties: ["emergency_medicine", "toxicology"],
    workplace: "Hôpital Habib Bourguiba",
    gouvernorat_code: 61,
    cp_unit: "Direction régionale de Sfax",
    status: "pending",
    available: false,
    submitted_at: "2026-10-24T08:00:00Z",
    phone: "+21698123456",
    email: "salma@example.tn",
    licence_no: "TN-12345",
    cp_staff_no: "PC/4521",
    review_reason: null,
    reviews: [],
    ...overrides,
  };
}

describe("Doctors", () => {
  it("lists the registrations without their numbers and filters by specialty", async () => {
    const item: StaffDoctor = doctor();
    const doctors = vi.fn(() => Promise.resolve({ items: [item], next_cursor: null }));
    const api = fakeApi({ doctors });
    renderApp(<DoctorsPage />, {
      api,
      auth: fakeAuth(COORDINATOR),
      lang: "fr",
    });

    const link = await screen.findByRole("link", { name: "Salma Trabelsi" });
    expect(link).toHaveAttribute("href", "/doctors/d-1");
    const row = link.closest("tr");
    if (!row) throw new Error("no row");
    expect(within(row).getByText("Médecin de la Protection civile")).toBeInTheDocument();
    expect(within(row).getByText("Toxicologie")).toBeInTheDocument();
    expect(within(row).getByText("Direction régionale de Sfax")).toBeInTheDocument();
    expect(screen.queryByText("TN-12345")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Spécialités" }), {
      target: { value: "cardiology" },
    });
    await waitFor(() =>
      expect(doctors).toHaveBeenLastCalledWith(expect.objectContaining({ specialty: "cardiology" }), expect.anything()),
    );
  });

  it("shows the numbers to check and verifies the doctor", async () => {
    const api = fakeApi({
      doctor: vi.fn(() => Promise.resolve(doctor())),
      reviewDoctor: vi.fn(() =>
        Promise.resolve(
          doctor({
            status: "approved",
            reviews: [{ decision: "approve", reason: null, at: "2026-10-24T09:00:00Z" }],
          }),
        ),
      ),
    });
    renderApp(<DoctorDetailPage />, {
      api,
      auth: fakeAuth(COORDINATOR),
      lang: "fr",
      route: "/doctors/:id",
      path: "/doctors/d-1",
    });

    expect(await screen.findByRole("heading", { level: 1, name: "Salma Trabelsi" })).toBeInTheDocument();
    expect(screen.getByText("TN-12345")).toBeInTheDocument();
    expect(screen.getByText("PC/4521")).toBeInTheDocument();
    expect(screen.getByText(/inscrite au journal d'audit/)).toBeInTheDocument();
    const group = screen.getByRole("group", { name: "Choisir la décision" });
    expect(
      within(group)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["Vérifier", "Refuser"]);

    fireEvent.click(within(group).getByRole("button", { name: "Refuser" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la décision" }));
    expect(screen.getByText("Le motif est requis pour cette décision.")).toBeInTheDocument();
    expect(api.reviewDoctor).not.toHaveBeenCalled();

    fireEvent.click(within(group).getByRole("button", { name: "Vérifier" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la décision" }));
    await waitFor(() => expect(api.reviewDoctor).toHaveBeenCalledWith("d-1", "approve", ""));
    expect(await screen.findByText("Décision enregistrée.")).toBeInTheDocument();
    expect(await screen.findByText("Validé", { selector: ".chip" })).toBeInTheDocument();
  });

  it("is open to the medical coordinator and the volunteer reviewers only", () => {
    expect(canReviewDoctors(["medical_coordinator"])).toBe(true);
    expect(canReviewDoctors(["ops_manager"])).toBe(true);
    expect(canReviewDoctors(["operator"])).toBe(false);
    expect(canReviewDoctors(["sysadmin"])).toBe(false);
    expect(landingPath(["medical_coordinator"])).toBe("/doctors");
  });
});
