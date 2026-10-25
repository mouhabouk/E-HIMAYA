import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { Handler } from "../../test/fetch";
import { makeCertificate, makeOrg } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import type { Organization } from "../../lib/types";
import { ActivitiesTab, validateActivity } from "./ActivitiesTab";
import { CardTab } from "./CardTab";
import { CertificatesTab } from "./CertificatesTab";
import { MembersTab } from "./MembersTab";
import { OrgWorkspace } from "./OrgWorkspace";
import { OverviewTab } from "./OverviewTab";
import { NewReportPage, ReportsTab } from "./ReportsTab";
import { TeamTab } from "./TeamTab";

vi.mock("../../components/LazyMap", () => ({ MapPanel: () => <div data-testid="map" /> }));

const ORG = "GET /api/v1/orgs/o-1";

function open(path: string, org: Partial<Organization>, routes: Record<string, Handler | Handler[]> = {}) {
  return renderApp(<OrgWorkspace />, {
    path,
    route: "/orgs/:orgId",
    lang: "en",
    routes: { [ORG]: { body: makeOrg(org) }, ...routes },
    children: (
      <>
        <Route index element={<OverviewTab />} />
        <Route path="card" element={<CardTab />} />
        <Route path="team" element={<TeamTab />} />
        <Route path="members" element={<MembersTab />} />
        <Route path="reports" element={<ReportsTab />} />
        <Route path="reports/new" element={<NewReportPage />} />
        <Route path="certificate" element={<CertificatesTab />} />
        <Route path="activities" element={<ActivitiesTab />} />
      </>
    ),
  });
}

const TEAM = [
  {
    id: "t-1",
    full_name: "Sami Ali",
    team_role: "representative",
    position: "HSE",
    phone: "+21620000000",
    email: null,
    last_training_on: "2024-01-01",
    training_valid_months: 24,
    training_status: "expired",
    training_expires_on: "2026-01-01",
  },
];

const MEMBERS = [
  { user_id: "u-1", display_name: "Amira Ben Salah", email: "AMIRA@x.tn", role: "admin", joined_at: "2026-10-01T10:00:00Z" },
  { user_id: "u-2", display_name: "Nour", email: "nour@x.tn", role: "member", joined_at: "2026-10-02T10:00:00Z" },
];

describe("overview", () => {
  it("shows classification, the provisional notice, the checklist with fix links and the alerts", async () => {
    open("/orgs/o-1", {});
    expect(await screen.findByRole("heading", { name: "Société X" })).toBeInTheDocument();
    expect(screen.getByText(/Provisional classification/)).toBeInTheDocument();
    const checklist = screen.getByRole("heading", { name: "Safety file completeness" }).closest("section") as HTMLElement;
    expect(within(checklist).getAllByRole("link", { name: "Fix" })).toHaveLength(2);
    expect(within(checklist).getAllByRole("link", { name: "Fix" })[0]).toHaveAttribute("href", "/orgs/o-1/documents");
    expect(screen.getByText("Expired training in the safety team")).toBeInTheDocument();
    expect(screen.getByText("Equipment maintenance overdue")).toBeInTheDocument();
  });

  it("shows the rejection reason and lets an admin resubmit", async () => {
    const { calls } = open("/orgs/o-1", { status: "rejected", review: { reason: "Identifiant illisible", at: "2026-10-10T10:00:00Z" } }, {
      "POST /api/v1/orgs/o-1/resubmit": { body: makeOrg({ status: "pending_review" }) },
    });
    expect(await screen.findByText("Identifiant illisible")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resubmit for review" }));
    expect(await screen.findByRole("heading", { name: "Pending review" })).toBeInTheDocument();
    expect(calls("POST /api/v1/orgs/o-1/resubmit")).toHaveLength(1);
  });

  it("does not offer resubmission to a member", async () => {
    open("/orgs/o-1", { status: "rejected", my_role: "member", review: { reason: "x", at: null } });
    expect(await screen.findByText("Only an administrator can resubmit.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resubmit for review" })).not.toBeInTheDocument();
  });

  it("maps 404 org_not_found (not a member) to a translated page", async () => {
    renderApp(<OrgWorkspace />, { path: "/orgs/o-9", route: "/orgs/:orgId", lang: "en", routes: { "GET /api/v1/orgs/o-9": { status: 404, body: { detail: "org_not_found" } } } });
    expect(await screen.findByRole("heading", { name: "Institution not found" })).toBeInTheDocument();
  });
});

const MESSAGE = {
  id: "msg-1",
  topic: "other",
  title: { ar: "موجة حر", fr: "Vigilance canicule", en: "Heat wave watch" },
  body: { ar: "تحققوا من المطافئ", fr: "", en: "Check your extinguishers and water reserves." },
  published_at: "2026-10-24T08:00:00Z",
  ack_required: true,
  acked_at: null,
  acked_by: null,
};

describe("Office messages (P2b)", () => {
  it("shows the messages in the page language and lets an editor confirm reading one", async () => {
    const { calls } = open("/orgs/o-1", { my_role: "editor" }, {
      "GET /api/v1/orgs/o-1/messages": { body: [MESSAGE, { ...MESSAGE, id: "msg-2", ack_required: false, title: { ar: "للعلم" }, body: { ar: "نص" } }] },
      "POST /api/v1/orgs/o-1/messages/msg-1/ack": { body: { ...MESSAGE, acked_at: "2026-10-24T09:00:00Z", acked_by: "Amira" } },
    });
    const section = (await screen.findByRole("heading", { name: "Office messages" })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Heat wave watch")).toBeInTheDocument();
    expect(within(section).getByText("Check your extinguishers and water reserves.")).toBeInTheDocument();
    // An empty language falls back to Arabic.
    expect(within(section).getByText("للعلم")).toBeInTheDocument();
    expect(within(section).getByText("Awaiting acknowledgement: 1")).toBeInTheDocument();
    fireEvent.click(within(section).getByRole("button", { name: "I have read it" }));
    expect(await within(section).findByText(/Acknowledged on .*\(Amira\)/)).toBeInTheDocument();
    expect(calls("POST /api/v1/orgs/o-1/messages/msg-1/ack")).toHaveLength(1);
    expect(within(section).queryByRole("button", { name: "I have read it" })).not.toBeInTheDocument();
  });

  it("a member sees the request but cannot confirm", async () => {
    open("/orgs/o-1", { my_role: "member" }, { "GET /api/v1/orgs/o-1/messages": { body: [MESSAGE] } });
    const section = (await screen.findByRole("heading", { name: "Office messages" })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Acknowledgement requested")).toBeInTheDocument();
    expect(within(section).queryByRole("button", { name: "I have read it" })).not.toBeInTheDocument();
  });
});

describe("drills and events (P2b)", () => {
  it("checks dates and participants like the server", () => {
    const base = { kind: "drill" as const, title: "Évacuation", starts_on: "2026-10-20", ends_on: "", participants: "", notes: "" };
    expect(validateActivity(base, "2026-10-25")).toEqual({});
    expect(validateActivity({ ...base, starts_on: "2026-10-30" }, "2026-10-25")).toEqual({ starts_on: "activities.drillInFuture" });
    expect(validateActivity({ ...base, kind: "event", starts_on: "2026-10-30", ends_on: "2026-10-29" }, "2026-10-25")).toEqual({
      ends_on: "activities.endBeforeStart",
    });
    expect(validateActivity({ ...base, title: " ", participants: "-3" }, "2026-10-25")).toEqual({
      title: "validation.required",
      participants: "activities.participantsInvalid",
    });
  });

  it("lists, declares an event and deletes an entry", async () => {
    const DRILL = {
      id: "a-1",
      kind: "drill",
      title: "Workshop evacuation",
      starts_on: "2026-09-12",
      ends_on: null,
      participants: 48,
      notes: null,
      created_by: "Amira",
      created_at: "2026-09-12T10:00:00Z",
    };
    const { calls } = open("/orgs/o-1/activities", { my_role: "editor" }, {
      "GET /api/v1/orgs/o-1/activities": { body: [DRILL] },
      "POST /api/v1/orgs/o-1/activities": { status: 201, body: { ...DRILL, id: "a-2", kind: "event" } },
      "DELETE /api/v1/orgs/o-1/activities/a-1": { status: 204 },
    });
    const row = (await screen.findByRole("rowheader", { name: "Workshop evacuation" })).closest("tr") as HTMLElement;
    expect(within(row).getByText("Drill")).toBeInTheDocument();
    expect(within(row).getByText("48")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Type"), { target: { value: "event" } });
    fireEvent.change(within(dialog).getByLabelText(/Title/), { target: { value: "Open day" } });
    fireEvent.change(within(dialog).getByLabelText(/^Date/), { target: { value: "2099-05-01" } });
    fireEvent.change(within(dialog).getByLabelText("End date"), { target: { value: "2099-05-02" } });
    fireEvent.change(within(dialog).getByLabelText("Participants"), { target: { value: "300" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls("POST /api/v1/orgs/o-1/activities")).toHaveLength(1));
    expect(calls("POST /api/v1/orgs/o-1/activities")[0]?.body).toEqual({
      kind: "event",
      title: "Open day",
      starts_on: "2099-05-01",
      ends_on: "2099-05-02",
      participants: 300,
      notes: null,
    });

    fireEvent.click(await screen.findByRole("button", { name: "Delete “Workshop evacuation”" }));
    const confirm = await screen.findByRole("dialog");
    fireEvent.click(within(confirm).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls("DELETE /api/v1/orgs/o-1/activities/a-1")).toHaveLength(1));
  });

  it("is read-only for a member", async () => {
    open("/orgs/o-1/activities", { my_role: "member" }, { "GET /api/v1/orgs/o-1/activities": { body: [] } });
    expect(await screen.findByText("No drill or event recorded yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
  });
});

describe("card editor: optimistic version", () => {
  it("offers a reload on 409 version_conflict, then saves with the fresh version", async () => {
    const { calls } = open("/orgs/o-1/card", {}, {
      [ORG]: [{ body: makeOrg() }, { body: makeOrg({ version: 8, activity_type: "Peintures industrielles" }) }],
      "PUT /api/v1/orgs/o-1": [{ status: 409, body: { detail: "version_conflict" } }, { body: makeOrg({ version: 9 }) }],
    });
    const field = await screen.findByLabelText("Activity");
    fireEvent.change(field, { target: { value: "Vernis" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("The card was modified by someone else meanwhile.")).toBeInTheDocument();
    expect(calls("PUT /api/v1/orgs/o-1")[0]?.body).toMatchObject({ version: 7, activity_type: "Vernis", name: "Société X" });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Reload the latest version" }));
    await waitFor(() => expect(screen.getByLabelText("Activity")).toHaveValue("Peintures industrielles"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Card saved.")).toBeInTheDocument();
    expect(calls("PUT /api/v1/orgs/o-1")[1]?.body).toMatchObject({ version: 8 });
  });

  it("warns that renaming an active institution sends it back to review", async () => {
    open("/orgs/o-1/card", {});
    const name = await screen.findByLabelText(/^Institution name/);
    expect(screen.queryByText(/sends it back to review/)).not.toBeInTheDocument();
    fireEvent.change(name, { target: { value: "Société X SA" } });
    expect(screen.getByText(/sends it back to review/)).toBeInTheDocument();
  });

  it("is read-only for a member", async () => {
    open("/orgs/o-1/card", { my_role: "member" });
    expect(await screen.findByLabelText(/^Institution name/)).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.getByText(/your role \(Member\) does not allow this action/)).toBeInTheDocument();
  });
});

describe("role-based visibility", () => {
  it("team: editors can add, members only read", async () => {
    open("/orgs/o-1/team", { my_role: "member" }, { "GET /api/v1/orgs/o-1/team": { body: TEAM } });
    expect(await screen.findByText("Sami Ali")).toBeInTheDocument();
    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add a member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit Sami Ali" })).not.toBeInTheDocument();
  });

  it("team: still handles a 403 from the server and forbids a second representative", async () => {
    open("/orgs/o-1/team", { my_role: "editor" }, {
      "GET /api/v1/orgs/o-1/team": { body: TEAM },
      "POST /api/v1/orgs/o-1/team": { status: 403, body: { detail: "org_role_required" } },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Add a member" }));
    const dialog = screen.getByRole("dialog", { name: "New team member" });
    expect(within(dialog).getByLabelText("Representative")).toBeDisabled();
    expect(within(dialog).getByLabelText("Member")).toBeChecked();
    fireEvent.change(within(dialog).getByLabelText(/^Full name/), { target: { value: "Ines" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByText("Your role in the institution does not allow this action.")).toBeInTheDocument();
  });

  it("members: a member sees the list but no management, and can leave", async () => {
    open("/orgs/o-1/members", { my_role: "member" }, { "GET /api/v1/orgs/o-1/members": { body: MEMBERS } });
    expect(await screen.findByText("Nour")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Role of Nour" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Invitations" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Leave the institution" })).toBeEnabled();
  });

  it("members: an admin changes roles, invites (one-time link) and gets the last-admin error on leaving", async () => {
    const { calls } = open("/orgs/o-1/members", {}, {
      "GET /api/v1/orgs/o-1/members": { body: MEMBERS },
      "GET /api/v1/orgs/o-1/invitations": { body: [] },
      "PUT /api/v1/orgs/o-1/members/u-2": { body: { ...MEMBERS[1], role: "editor" } },
      "POST /api/v1/orgs/o-1/invitations": {
        status: 201,
        body: { id: "i-1", email: "new@x.tn", role: "member", expires_at: "2026-10-26T10:00:00Z", token: "tok", accept_url: "http://localhost:5174/invite/tok" },
      },
      "DELETE /api/v1/orgs/o-1/members/u-1": { status: 409, body: { detail: "last_admin" } },
    });
    fireEvent.change(await screen.findByRole("combobox", { name: "Role of Nour" }), { target: { value: "editor" } });
    await waitFor(() => expect(calls("PUT /api/v1/orgs/o-1/members/u-2")[0]?.body).toEqual({ role: "editor" }));
    // Self (matched by e-mail, case-insensitively) cannot be removed from the table.
    expect(screen.queryByRole("button", { name: "Remove Amira Ben Salah" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^E-mail of the person/), { target: { value: "new@x.tn" } });
    fireEvent.click(screen.getByRole("button", { name: "Create the invitation" }));
    const dialog = await screen.findByRole("dialog", { name: "Invitation link" });
    expect(within(dialog).getByDisplayValue("http://localhost:5174/invite/tok")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Copy the link" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Done" }));

    fireEvent.click(screen.getByRole("button", { name: "Leave the institution" }));
    const confirm = screen.getByRole("dialog", { name: "Leave the institution" });
    fireEvent.click(within(confirm).getByRole("button", { name: "Leave the institution" }));
    expect(await within(confirm).findByText(/The last administrator cannot leave or be demoted/)).toBeInTheDocument();
  });

  it("members: invitations need an active institution", async () => {
    open("/orgs/o-1/members", { status: "pending_review" }, {
      "GET /api/v1/orgs/o-1/members": { body: MEMBERS },
      "GET /api/v1/orgs/o-1/invitations": { body: [] },
    });
    expect(await screen.findByRole("button", { name: "Create the invitation" })).toBeDisabled();
    expect(screen.getByText("Not available while the institution is “Pending review”.")).toBeInTheDocument();
  });
});

describe("reports on behalf of the institution (FR-B-011)", () => {
  it("lists reports with the phase 2 status labels", async () => {
    open("/orgs/o-1/reports", {}, {
      "GET /api/v1/orgs/o-1/reports": {
        body: {
          items: [
            { id: "r-1", tracking_code: "EH-26-61-0004821", category: "fire", status: "in_progress", text: "Feu", received_at: "2026-10-19T10:00:00Z", updated_at: "2026-10-19T10:05:00Z", reporter_display_name: "Nour" },
          ],
          next_cursor: null,
        },
      },
    });
    expect(await screen.findByText("EH-26-61-0004821")).toBeInTheDocument();
    expect(screen.getByText("Being processed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New report" })).toHaveAttribute("href", "/orgs/o-1/reports/new");
  });

  it("asks for the charter on 428 consent_required, records consent (platform web) and resends with the same client_uuid", async () => {
    const { calls } = open("/orgs/o-1/reports/new", { my_role: "member" }, {
      "POST /api/v1/reports": [
        { status: 428, body: { detail: "consent_required" } },
        { status: 201, body: { id: "r-1", tracking_code: "EH-26-61-0004822", client_uuid: "x", category: "fire", status: "received", received_at: "2026-10-19T10:00:00Z", organization: { id: "o-1", name: "Société X" } } },
      ],
      "GET /api/v1/charter": { body: { version: "2026-11" } },
      "POST /api/v1/consents": { status: 201, body: { charter_version: "2026-11", accepted_at: "2026-10-19T10:00:00Z" } },
    });
    fireEvent.change(await screen.findByLabelText("Description"), { target: { value: "Fumée dans le dépôt B" } });
    fireEvent.click(screen.getByRole("button", { name: "Send the report" }));
    const dialog = await screen.findByRole("dialog", { name: "Charter" });
    // Version 2026-11 (phase A): the ten sections of the terms, no placeholder notice.
    expect(await within(dialog).findAllByRole("heading", { level: 3 })).toHaveLength(10);
    expect(within(dialog).getByText(/2004-63/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/PLACEHOLDER/)).not.toBeInTheDocument();
    const accept = within(dialog).getByRole("button", { name: "I accept" });
    expect(accept).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox"));
    fireEvent.click(accept);
    expect(await screen.findByText("EH-26-61-0004822")).toBeInTheDocument();

    expect(calls("POST /api/v1/consents")[0]?.body).toEqual({ charter_version: "2026-11", locale: "en", platform: "web" });
    const posts = calls("POST /api/v1/reports").map((c) => c.body as Record<string, unknown>);
    expect(posts).toHaveLength(2);
    expect(posts[0]).toMatchObject({ category: "fire", text: "Fumée dans le dépôt B", lang: "en", organization_id: "o-1", location: { lat: 34.7, lon: 10.72 } });
    expect(posts[1]?.client_uuid).toBe(posts[0]?.client_uuid);
  });

  it("is blocked while the institution is not active", async () => {
    open("/orgs/o-1/reports/new", { status: "pending_review" });
    expect(await screen.findByRole("button", { name: "Send the report" })).toBeDisabled();
  });
});

describe("certificate (FR-B-008)", () => {
  it("shows completeness.missing when submission answers 409 incomplete", async () => {
    open("/orgs/o-1/certificate", {}, {
      "GET /api/v1/orgs/o-1/certificates": { body: [makeCertificate()] },
      "POST /api/v1/orgs/o-1/certificates/c-1/submit": { status: 409, body: { detail: "incomplete" } },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Submit for review" }));
    const alert = await screen.findByText("The safety file is incomplete. Missing items:");
    const box = alert.closest("div") as HTMLElement;
    expect(within(box).getByText(/Safety plan \(stored\)/)).toBeInTheDocument();
    expect(within(box).getByText(/A safety data sheet for every hazardous material/)).toBeInTheDocument();
  });

  it("offers a new draft on 409 certificate_outdated", async () => {
    const { calls } = open("/orgs/o-1/certificate", { completeness: { ok: true, missing: [] } }, {
      "GET /api/v1/orgs/o-1/certificates": { body: [makeCertificate()] },
      "POST /api/v1/orgs/o-1/certificates/c-1/submit": { status: 409, body: { detail: "certificate_outdated" } },
      "POST /api/v1/orgs/o-1/certificate": { status: 201, body: makeCertificate({ id: "c-2" }) },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Submit for review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate a new draft" }));
    await waitFor(() => expect(calls("POST /api/v1/orgs/o-1/certificate")).toHaveLength(1));
  });

  it("says the approved certificate needs updating, with the differences, the stamps and a new certificate (P3a)", async () => {
    const soon = new Date(Date.now() + 40 * 86_400_000).toISOString().slice(0, 10);
    const { calls } = open("/orgs/o-1/certificate", { completeness: { ok: true, missing: [] } }, {
      "GET /api/v1/orgs/o-1/certificates": {
        body: [
          makeCertificate({
            status: "approved",
            reviewed_at: "2026-10-03T08:00:00Z",
            valid_until: soon,
            needs_update: true,
            changes: [{ section: "building", field: "capacity", certified: 300, current: 420 }],
            stamps: [
              {
                id: "s-1",
                place: "Regional administration of Sfax",
                gouvernorat_code: 61,
                stamped_on: "2026-10-20",
                note: null,
                stamped_by_name: "Leila Auditor",
                recorded_at: "2026-10-20T09:00:00Z",
                has_photo: false,
                changes: [],
              },
            ],
          }),
        ],
      },
      "POST /api/v1/orgs/o-1/certificate": { status: 201, body: makeCertificate({ id: "c-2" }) },
    });
    expect(await screen.findByText(/The certificate expires in 40 days/)).toBeInTheDocument();
    expect(screen.getByText("Needs updating.")).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /Building/ });
    expect(row).toHaveTextContent("Capacity");
    expect(row).toHaveTextContent("300");
    expect(row).toHaveTextContent("420");
    expect(screen.getByText("Regional administration of Sfax")).toBeInTheDocument();
    expect(screen.getByText(/Agent: Leila Auditor/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Generate a new certificate" }));
    await waitFor(() => expect(calls("POST /api/v1/orgs/o-1/certificate")).toHaveLength(1));
  });

  it("shows a current certificate that still matches the institution", async () => {
    open("/orgs/o-1/certificate", {}, {
      "GET /api/v1/orgs/o-1/certificates": {
        body: [makeCertificate({ status: "approved", valid_until: "2099-01-01", needs_update: false, changes: [], stamps: [] })],
      },
    });
    expect(await screen.findByText("Matches the institution")).toBeInTheDocument();
    expect(screen.queryByText(/The certificate expires in/)).not.toBeInTheDocument();
  });

  it("shows the public verification link of a submitted certificate; editors cannot submit", async () => {
    open("/orgs/o-1/certificate", { my_role: "editor" }, {
      "GET /api/v1/orgs/o-1/certificates": { body: [makeCertificate({ id: "c-3", status: "approved", valid_until: "2099-01-01" }), makeCertificate()] },
    });
    expect(await screen.findByRole("link", { name: "http://localhost:5174/verify/EHC-26-61-000123" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate a draft" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit for review" })).not.toBeInTheDocument();
  });
});
