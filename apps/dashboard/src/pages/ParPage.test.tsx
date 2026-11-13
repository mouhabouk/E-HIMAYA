// covers: OS7 (docs/phase-os7/design-os7.md): the board of the teams in a danger zone, the next-check time picker that
// blocks the past, the pause with a mandatory reason, and the menu entry for the rooms only.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { navGroups } from "../components/Navigation";
import { identityFromClaims } from "../auth/identity";
import type { ParBoard, ParIncidentRow, ParTeam } from "../lib/par";
import { mmss, nextAt } from "../lib/par";
import { fakeApi, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { ParPage } from "./ParPage";

const NOW = new Date().toISOString();
const INCIDENT = "11111111-1111-1111-1111-111111111111";

function team(over: Partial<ParTeam> = {}): ParTeam {
  return {
    id: "t1",
    assignment_id: "a1",
    incident_id: INCIDENT,
    label: "FPT 12",
    task: "إطفاء الطابق 3",
    zone: "hot",
    status: "ok",
    interval_s: 600,
    due_at: NOW,
    remaining_s: 405,
    last_confirmed_at: NOW,
    next_at: null,
    paused_at: null,
    pause_reason: null,
    out_at: null,
    out_count: null,
    entered_at: NOW,
    leader_name: "سامي الطرابلسي",
    members: [
      { key: "m0", name: "سامي", role: "رئيس الفريق", away_why: null, away_at: null },
      { key: "m1", name: "علي", role: "", away_why: "air", away_at: NOW },
    ],
    present: 1,
    away: 1,
    ...over,
  };
}

function board(teams: ParTeam[]): ParBoard {
  return {
    incident_id: INCIDENT,
    incident_kind: "fire",
    incident_status: "open",
    gouvernorat_code: 61,
    settings: { gouvernorat_code: 61, hot_s: 600, warm_s: 900, grace_s: 60, auto_events: [], remind_s: 60, updated_at: null, updated_by_name: null },
    kpis: { agents_in: 1, teams_in: teams.length, not_confirmed: teams.filter((x) => x.status === "alarm").length, missing_open: 0 },
    teams,
    missing: [],
    sitreps: [
      { id: 1, team_id: "t1", team_label: "FPT 12", at: NOW, situation: "progress", reinforcement: true, text: "الحريق محصور", voice_seconds: 12, edited: true, by_name: "سامي" },
    ],
    events: [{ at: NOW, kind: "enter", text: "FPT 12 دخل المنطقة الساخنة", by_name: "سامي", team_id: "t1" }],
    all_out: false,
    closure: null,
    now: NOW,
  };
}

const ROW: ParIncidentRow = {
  incident_id: INCIDENT,
  incident_kind: "fire",
  gouvernorat_code: 61,
  teams_in: 1,
  agents_in: 1,
  alarms: 1,
  missing_open: 0,
  last_sitrep: "progress",
  closed: false,
};

describe("ParPage", () => {
  it("shows the teams, the late alarm, the member away and the word from the scene", async () => {
    const late = team({ status: "alarm", remaining_s: -95 });
    renderApp(<ParPage />, {
      api: fakeApi({
        parIncidents: vi.fn(() => Promise.resolve([ROW])),
        parBoard: vi.fn(() => Promise.resolve(board([late]))),
      }),
    });
    expect(await screen.findByRole("heading", { name: "تفقّد الأعوان في منطقة الخطر" })).toBeInTheDocument();
    const alarm = await screen.findByRole("alert");
    expect(alarm).toHaveTextContent("FPT 12 لم يؤكّد الحضور");
    const card = screen.getByRole("article", { name: "FPT 12" });
    expect(within(card).getByText("لم يؤكّد")).toBeInTheDocument();
    expect(within(card).getByText("علي · تزوّد بالهواء")).toBeInTheDocument();
    expect(screen.getByText("صوتية محوّلة ثم مصحّحة")).toBeInTheDocument();
    expect(screen.getByText("طلب تعزيز")).toBeInTheDocument();
  });

  it("pauses with a reason only, and resumes", async () => {
    const parPause = vi.fn(() => Promise.resolve(board([team({ status: "paused", paused_at: NOW, pause_reason: "سبب آخر · تفقّد يدوي" })])));
    renderApp(<ParPage />, {
      api: fakeApi({
        parIncidents: vi.fn(() => Promise.resolve([ROW])),
        parBoard: vi.fn(() => Promise.resolve(board([team()]))),
        parPause,
      }),
    });
    const button = await screen.findByRole("button", { name: "إيقاف التفقّد" });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "سبب آخر" }));
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("اذكر السبب"), { target: { value: "تفقّد يدوي" } });
    fireEvent.click(button);
    await waitFor(() => expect(parPause).toHaveBeenCalledWith(INCIDENT, "other", "تفقّد يدوي", null));
    expect(await screen.findByRole("button", { name: "استئناف التفقّد" })).toBeInTheDocument();
  });

  it("blocks the past in the time picker", async () => {
    renderApp(<ParPage />, {
      api: fakeApi({
        parIncidents: vi.fn(() => Promise.resolve([ROW])),
        parBoard: vi.fn(() => Promise.resolve(board([team()]))),
      }),
    });
    fireEvent.click(await screen.findByRole("button", { name: /اختر الساعة والدقيقة/ }));
    const hours = screen.getByRole("listbox", { name: "الساعة" });
    const now = new Date();
    const past = (now.getHours() + 23) % 24;
    // The hour just gone is more than 12 hours away tomorrow: blocked.
    expect(within(hours).getByRole("option", { name: String(past).padStart(2, "0") })).toBeDisabled();
    expect(screen.getByRole("button", { name: "تطبيق التوقيت" })).toBeDisabled();
  });

  it("is in the menu of the rooms", () => {
    const t = ((k: string) => k) as never;
    const links = navGroups(identityFromClaims(OPERATOR_CLAIMS), t).flatMap((g) => g.items.map((i) => i.to));
    expect(links).toContain("/par");
  });
});

describe("par helpers", () => {
  it("formats the timer and never picks a past time", () => {
    expect(mmss(405)).toBe("06:45");
    expect(mmss(-95)).toBe("-01:35");
    const from = new Date(2026, 10, 12, 14, 21);
    expect(nextAt(14, 25, from).getDate()).toBe(12);
    expect(nextAt(14, 20, from).getDate()).toBe(13);
  });
});
