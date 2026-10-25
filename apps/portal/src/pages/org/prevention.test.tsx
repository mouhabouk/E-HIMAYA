import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { Handler } from "../../test/fetch";
import { makeCertificate, makeOrg } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import type { Organization, Visit } from "../../lib/types";
import { OrgWorkspace } from "./OrgWorkspace";
import { PreventionTab } from "./PreventionTab";

vi.mock("../../components/LazyMap", () => ({ MapPanel: () => <div data-testid="map" /> }));

const VISITS = "GET /api/v1/orgs/o-1/prevention/visits";
const ANNUAL = "GET /api/v1/orgs/o-1/annual-report";

function visit(overrides: Partial<Visit> = {}): Visit {
  return {
    id: "v-1",
    org_id: "o-1",
    origin: "request",
    status: "requested",
    request_note: null,
    requested_by_name: "Amira",
    requested_at: "2026-10-20T08:00:00Z",
    scheduled_on: null,
    inspector_name: null,
    inspected_on: null,
    attendees: null,
    comparison: null,
    decision: null,
    decision_reason: null,
    decided_by_name: null,
    decided_at: null,
    certificate: null,
    reservations: [],
    has_report: false,
    cancel_reason: null,
    cancelled_at: null,
    created_at: "2026-10-20T08:00:00Z",
    ...overrides,
  };
}

const DECIDED = visit({
  status: "decided",
  scheduled_on: "2026-10-24",
  inspector_name: "Cdt Ben Salah",
  inspected_on: "2026-10-24",
  decision: "approved_with_reservations",
  decided_at: "2026-10-25T10:00:00Z",
  has_report: true,
  comparison: {
    items: [
      { key: "building.capacity", section: "building", declared: 300, result: "nonconform", observed: "420", note: null },
      { key: "site.exits", section: "site", declared: null, result: "conform", observed: null, note: null },
    ],
    conform: 1,
    nonconform: 1,
    not_checked: 0,
    missing: [],
    changes: [],
    suggested: "approved_with_reservations",
  },
  certificate: makeCertificate({
    id: "c-9",
    kind: "prevention",
    code: "EHP-26-61-000009",
    status: "approved",
    valid_until: "2027-10-25",
  }),
  reservations: [
    {
      id: "r-1",
      visit_id: "v-1",
      item_key: "building.capacity",
      text: "Mettre à jour la capacité",
      due_on: "2026-11-25",
      state: "open",
      response_note: null,
      responded_by_name: null,
      responded_at: null,
      lifted_by_name: null,
      lift_note: null,
      lifted_at: null,
    },
  ],
});

const ANNUAL_REPORT = {
  year: new Date().getFullYear(),
  org_id: "o-1",
  org_name: "Société X",
  generated_on: "2026-10-25",
  drills: [{ id: "a-1", kind: "drill", title: "Évacuation", starts_on: "2026-03-01", ends_on: null, participants: 40, notes: null, created_by: null, created_at: "2026-03-01T08:00:00Z" }],
  events: [],
  participants: 40,
  maintenance: 3,
  training: { valid: 2, expiring: 0, expired: 1, unknown: 0 },
  visits: [DECIDED],
  reservations: { opened: 1, lifted: 0, open: 1, overdue: 0 },
  certificates: [DECIDED.certificate],
  stamps: 1,
  reports: 2,
};

function open(org: Partial<Organization>, routes: Record<string, Handler | Handler[]> = {}) {
  return renderApp(<OrgWorkspace />, {
    path: "/orgs/o-1/prevention",
    route: "/orgs/:orgId",
    lang: "en",
    routes: { "GET /api/v1/orgs/o-1": { body: makeOrg(org) }, [ANNUAL]: { body: ANNUAL_REPORT }, ...routes },
    children: <Route path="prevention" element={<PreventionTab />} />,
  });
}

describe("prevention tab (F-POR-08)", () => {
  it("lets an admin ask for a visit, then shows it waiting to be scheduled", async () => {
    const { calls } = open({}, {
      [VISITS]: [{ body: [] }, { body: [visit()] }],
      "POST /api/v1/orgs/o-1/prevention/visits": { status: 201, body: visit() },
    });
    expect(await screen.findByText("No visits yet.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Request note"), { target: { value: "Before summer" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask for a prevention visit" }));
    await waitFor(() => expect(calls("POST /api/v1/orgs/o-1/prevention/visits")[0]?.body).toEqual({ note: "Before summer" }));
    expect(await screen.findByText(/Waiting for the regional administration/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask for a prevention visit" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Withdraw the request" })).toBeInTheDocument();
  });

  it("a member cannot ask for a visit", async () => {
    open({ my_role: "member" }, { [VISITS]: { body: [] } });
    expect(await screen.findByText("No visits yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask for a prevention visit" })).not.toBeInTheDocument();
  });

  it("shows the decision, the comparison, the certificate and answers a reservation", async () => {
    const { calls } = open({}, {
      [VISITS]: { body: [DECIDED] },
      "POST /api/v1/orgs/o-1/prevention/reservations/r-1/response": { body: { ...DECIDED.reservations[0], state: "responded" } },
    });
    const card = await screen.findByRole("article", { name: /Requested by the institution/ });
    expect(within(card).getByText("Approved with reservations")).toBeInTheDocument();
    expect(within(card).getByText("EHP-26-61-000009")).toBeInTheDocument();
    expect(within(card).getByText(/Comparison report: 1 conforming · 1 non-conforming/)).toBeInTheDocument();
    expect(within(card).getByRole("row", { name: /Capacity/ })).toHaveTextContent("420");
    expect(within(card).getByRole("button", { name: "Visit report (PDF)" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Prevention certificate (PDF)" })).toBeInTheDocument();

    fireEvent.click(within(card).getByRole("button", { name: "Send the answer" }));
    expect(within(card).getByText("This field is required.")).toBeInTheDocument();
    fireEvent.change(within(card).getByLabelText("How did you address this reservation?"), {
      target: { value: "Declaration updated" },
    });
    fireEvent.click(within(card).getByRole("button", { name: "Send the answer" }));
    await waitFor(() =>
      expect(calls("POST /api/v1/orgs/o-1/prevention/reservations/r-1/response")[0]?.body).toEqual({
        note: "Declaration updated",
      }),
    );
  });

  it("shows the annual report of the year", async () => {
    const { calls } = open({}, { [VISITS]: { body: [DECIDED] } });
    const section = await screen.findByRole("region", { name: "Annual report" });
    expect(await within(section).findByText("1 drill(s), 40 participant(s)")).toBeInTheDocument();
    expect(within(section).getByText("1 issued · 0 lifted · 0 overdue")).toBeInTheDocument();
    expect(within(section).getByText("EHP-26-61-000009")).toBeInTheDocument();
    expect(calls(ANNUAL)[0]?.url.searchParams.get("year")).toBe(String(new Date().getFullYear()));
  });
});
