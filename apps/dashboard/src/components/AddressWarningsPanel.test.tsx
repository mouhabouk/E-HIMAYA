// covers: OS8 (design-os8.md): the address warnings of an incident, their reading and the name of a personal mark.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AwCategory, AwIncident, AwWarning } from "../lib/addressWarnings";
import { makeIncidentDetail } from "../test/fixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { AddressWarningsPanel } from "./AddressWarningsPanel";

const category = (key: string, name: string, personal = false): AwCategory => ({
  key,
  name,
  icon: personal ? "wheel" : "flame",
  colour: personal ? "green" : "amber",
  personal,
  radius_m: 150,
  review_months: 12,
  team: true,
  critical_with: ["fire"],
  examples: [],
  updated_by_name: null,
});

const warning = (id: string, extra: Partial<AwWarning> = {}): AwWarning => ({
  marker_id: id,
  category: "gas",
  personal: false,
  location: { lat: 34.95, lon: 10.4 },
  address: "نهج الحبيب بورقيبة 12",
  description: "مخزن قوارير غاز في الطابق الأرضي",
  source: "room",
  source_ref: null,
  team_visible: true,
  distance_m: 40,
  critical: true,
  off_hours: false,
  hours: null,
  review_on: "2027-06-01",
  room_ack_at: null,
  room_ack_by: null,
  team_ack_at: null,
  team_ack_by: null,
  revealed: false,
  ...extra,
});

function setup(claims = undefined as Record<string, unknown> | undefined) {
  const incident = makeIncidentDetail();
  const page: AwIncident = {
    incident_id: incident.id,
    incident_kind: "fire",
    location: { lat: 34.95, lon: 10.4 },
    items: [
      warning("m1"),
      warning("m2", { category: "mob", personal: true, critical: false, description: "مسنّ على كرسي متحرك", distance_m: 55 }),
    ],
    unread: 2,
  };
  const api = fakeApi({
    awCategories: vi.fn(() => Promise.resolve([category("gas", "مخزن غاز"), category("mob", "يحتاج مساعدة على الإخلاء", true)])),
    awIncident: vi.fn(() => Promise.resolve(page)),
    awAck: vi.fn((_id: string, ids: string[] = []) =>
      Promise.resolve({
        ...page,
        items: page.items.map((w) =>
          ids.length === 0 || ids.includes(w.marker_id)
            ? { ...w, room_ack_at: "2026-11-12T08:00:00Z", room_ack_by: "Ali" }
            : w,
        ),
        unread: ids.length === 0 ? 0 : 1,
      }),
    ),
    awReveal: vi.fn(() => Promise.resolve({ name: "Hédi Ben Salah", phone: "+21698000000" })),
  });
  const r = renderApp(<AddressWarningsPanel incident={incident} />, {
    api,
    ...(claims ? { auth: fakeAuth(claims) } : {}),
  });
  return { ...r, incident };
}

describe("AddressWarningsPanel", () => {
  it("shows the critical mark first and marks one read", async () => {
    const { api, incident } = setup();
    expect(await screen.findByText("مخزن غاز")).toBeInTheDocument();
    expect(screen.getByText("يحتاج مساعدة على الإخلاء")).toBeInTheDocument();
    expect(screen.getByText("1 حرج")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "اطّلعت" })[0] as HTMLElement);
    await waitFor(() => expect(api.awAck).toHaveBeenCalledWith(incident.id, ["m1"]));
    expect(await screen.findAllByRole("button", { name: "اطّلعت" })).toHaveLength(1);
  });

  it("reveals the owner's name of a personal mark with a reason", async () => {
    const { api, incident } = setup();
    fireEvent.click(await screen.findByRole("button", { name: "الاسم والهاتف" }));
    fireEvent.click(screen.getByRole("button", { name: "لإبلاغ الفريق باسمه للمناداة" }));
    fireEvent.click(screen.getByRole("button", { name: "اكشف" }));
    await waitFor(() =>
      expect(api.awReveal).toHaveBeenCalledWith(incident.id, "m2", "لإبلاغ الفريق باسمه للمناداة"),
    );
    expect(await screen.findByText(/Hédi Ben Salah/)).toBeInTheDocument();
  });

  it("gives a reader no button", async () => {
    setup(AUDITOR_CLAIMS);
    expect(await screen.findByText("مخزن غاز")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "اطّلعت" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "الاسم والهاتف" })).not.toBeInTheDocument();
  });
});
