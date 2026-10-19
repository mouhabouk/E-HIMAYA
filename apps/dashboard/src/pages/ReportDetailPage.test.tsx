import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { StaffReportDetail } from "../lib/types";
import { makeAnalysis, makeDetail, makeOrganizationCard } from "../test/fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { ReportDetailPage } from "./ReportDetailPage";

vi.mock("../components/LazyMap", () => ({ LazyMapView: () => <div data-testid="map" /> }));

const route = "/reports/:id";

describe("ReportDetailPage", () => {
  it("shows fields, media hash, reporter and only the allowed transitions", async () => {
    const detail = makeDetail({ id: "r1", allowed_transitions: ["in_progress", "rejected"] });
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(detail)) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "fr" });

    expect(await screen.findByText("EH-26-61-0004821")).toBeInTheDocument();
    expect(screen.getByText("a".repeat(64))).toBeInTheDocument();
    expect(screen.getByText("Amira Ben Salah")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Image" })).toHaveAttribute("src", detail.media[0]?.url);
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(2);
    expect(screen.getByRole("radio", { name: "En cours de traitement" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Rejeté" })).toBeInTheDocument();
  });

  it("is read-only for committee roles", async () => {
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1" }))) });
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["local_committee"] } });
    renderApp(<ReportDetailPage />, { api, auth, path: "/reports/r1", route, lang: "fr" });
    expect(await screen.findByText(/consultation uniquement/)).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("applies the change optimistically and rolls back on 409", async () => {
    const detail = makeDetail({ id: "r1", allowed_transitions: ["in_progress", "rejected"] });
    let rejectChange: (e: unknown) => void = () => undefined;
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(detail)),
      changeStatus: vi.fn(
        () =>
          new Promise<StaffReportDetail>((_resolve, reject) => {
            rejectChange = reject;
          }),
      ),
    });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "fr" });

    fireEvent.click(await screen.findByRole("radio", { name: "En cours de traitement" }));
    fireEvent.change(screen.getByLabelText("Note (facultative)"), { target: { value: "équipe envoyée" } });
    fireEvent.click(screen.getByRole("button", { name: "Appliquer" }));

    await waitFor(() => expect(api.changeStatus).toHaveBeenCalledWith("r1", "in_progress", "équipe envoyée"));
    // Optimistic: the header chip and the history show the new status.
    await waitFor(() => expect(screen.getAllByText("En cours de traitement").length).toBeGreaterThan(1));
    expect(screen.getByText("équipe envoyée", { selector: ".timeline__note" })).toBeInTheDocument();

    rejectChange(new ApiError(409, "invalid_transition"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Le statut a changé entre-temps");
    await waitFor(() => expect(screen.queryByText("équipe envoyée", { selector: ".timeline__note" })).not.toBeInTheDocument());
    // The truth is refetched after a conflict.
    await waitFor(() => expect(vi.mocked(api.report).mock.calls.length).toBeGreaterThan(1));
  });

  it("shows the Arabic translation and the AI analysis panel", async () => {
    const detail = makeDetail({
      id: "r1",
      text: "Feu dans un immeuble",
      lang: "fr",
      text_ar: "حريق في عمارة",
      priority_score: 79,
      analysis: makeAnalysis(),
    });
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(detail)) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "fr" });

    expect(await screen.findByText("Feu dans un immeuble")).toBeInTheDocument();
    const textSection = screen.getByRole("region", { name: "Texte du signalement" });
    expect(within(textSection).getByText("Traduction automatique en arabe")).toBeInTheDocument();
    expect(within(textSection).getByText("حريق في عمارة")).toHaveAttribute("lang", "ar");
    expect(screen.getByRole("heading", { name: "Analyse automatique (IA)" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Regroupement en incident" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Nouvel incident" })).toBeInTheDocument();
  });

  it("renders a translated not-found error", async () => {
    const api = fakeApi({ report: vi.fn(() => Promise.reject(new ApiError(404, "not_found"))) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/x", route });
    expect(await screen.findByRole("alert")).toHaveTextContent("العنصر المطلوب غير موجود");
  });

  it("shows the reporting institution in the header and its card for responders (phase 4)", async () => {
    const detail = makeDetail({
      id: "r1",
      organization: { id: "o-1", name: "Société Chimique du Sud", kind: "industrial" },
      organization_card: makeOrganizationCard(),
    });
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(detail)) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "fr" });

    expect(await screen.findByRole("link", { name: "Signalement au nom de l’établissement Société Chimique du Sud" })).toHaveAttribute(
      "href",
      "/orgs/o-1",
    );
    const card = screen.getByRole("region", { name: "Fiche de l’établissement déclarant" });
    expect(within(card).getByText("420")).toBeInTheDocument();
    expect(within(card).getByText("Établissement industriel")).toBeInTheDocument();
    const call = within(card).getByRole("link", { name: "Appeler Sonia Gharbi au +21622000000" });
    expect(call).toHaveAttribute("href", "tel:+21622000000");

    const hazard = within(card).getByRole("group", { name: "Danger : matières dangereuses stockées sur le site" });
    expect(hazard).toHaveClass("hazard");
    expect(within(hazard).getByText("UN 1090")).toBeInTheDocument();
    expect(within(hazard).getByText("2,5 t")).toBeInTheDocument();
    expect(within(card).getByText(/Parking nord/)).toBeInTheDocument();
    // The features are drawn on the report's map, with a legend.
    expect(screen.getByRole("list", { name: "Légende" })).toHaveTextContent("Point d’évacuation et de rassemblement");
  });

  it("shows no institution card for an ordinary report", async () => {
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1" }))) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "fr" });
    await screen.findByText("EH-26-61-0004821");
    expect(screen.queryByRole("region", { name: "Fiche de l’établissement déclarant" })).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Légende" })).not.toBeInTheDocument();
  });

  it("says when the institution declared no hazardous material and has no representative", async () => {
    const detail = makeDetail({
      id: "r1",
      organization: { id: "o-1", name: "École X" },
      organization_card: makeOrganizationCard({ name: "École X", kind: "educational", hazmat: [], representative: null, features: [] }),
    });
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(detail)) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "ar" });
    const card = await screen.findByRole("region", { name: "بطاقة المؤسسة المُبلِّغة" });
    expect(within(card).getByText("لم تُصرّح المؤسسة بأي مادة خطرة.")).toBeInTheDocument();
    expect(within(card).getByText("لا يوجد ممثل مسجّل.")).toBeInTheDocument();
    expect(within(card).getByText("تعليمية")).toBeInTheDocument();
  });
});
