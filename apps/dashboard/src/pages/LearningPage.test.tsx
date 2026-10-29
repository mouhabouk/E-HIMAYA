// covers: the training centre (docs/learning.md): the system administrator launches and schedules the trainings and
// reads their results; the central committee only reads; the operator confirms the reading of a final report.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LearningLabelSection } from "../components/LearningLabel";
import { makeDetail } from "../test/fixtures";
import { fakeLearningApi, OVERVIEW } from "../test/learningFixtures";
import {
  CENTRAL_COMMITTEE_CLAIMS,
  fakePhase9Api,
} from "../test/phase9Fixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { LearningPage } from "./LearningPage";

const SYSADMIN_CLAIMS = {
  sub: "u-sys",
  name: "Yamen Admin",
  realm_access: { roles: ["sysadmin"] },
  scope_level: "national",
};

const SCHEDULE = {
  key: "learning.schedule",
  value: Object.fromEntries(OVERVIEW.tasks.map((t) => [t.task, t.schedule])),
  version: 3,
  updated_by_name: null,
  updated_at: null,
  editable: true,
};

function section(name: string): HTMLElement {
  return screen
    .getByRole("heading", { name, level: 2 })
    .closest("section") as HTMLElement;
}

describe("LearningPage", () => {
  it("lets the system administrator launch a training and read its result", async () => {
    const learning = fakeLearningApi();
    const api = fakeApi({ ...learning });
    renderApp(<LearningPage />, {
      api,
      auth: fakeAuth(SYSADMIN_CLAIMS),
      lang: "ar",
    });
    await screen.findByRole("heading", { name: "صنف البلاغ" });
    const category = section("صنف البلاغ");
    expect(within(category).getByText(/اعتُمدت النسخة 2/)).toBeInTheDocument();
    expect(within(category).getByText("في الظل")).toBeInTheDocument();
    fireEvent.click(
      within(section("الحرائق والدخان")).getByRole("button", {
        name: "أطلق التدريب الآن",
      }),
    );
    await waitFor(() =>
      expect(learning.launchTraining).toHaveBeenCalledWith("fire_smoke"),
    );
    expect(
      within(section("الحرائق والدخان")).getByText("يحتاج بطاقة رسومية"),
    ).toBeInTheDocument();
    // New Derja words from the last run, for a person to review.
    expect(
      within(section("المرادفات الجديدة")).getByText("ta7rig"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "تصدير النصوص (CSV)" }));
    await waitFor(() =>
      expect(learning.learningDataset).toHaveBeenCalledWith("reports"),
    );
  });

  it("turns on a periodic training through the platform setting", async () => {
    const learning = fakeLearningApi();
    const phase9 = fakePhase9Api();
    phase9.platformSettings = vi.fn(() => Promise.resolve([SCHEDULE]));
    const api = fakeApi({ ...phase9, ...learning });
    renderApp(<LearningPage />, {
      api,
      auth: fakeAuth(SYSADMIN_CLAIMS),
      lang: "ar",
    });
    await screen.findByRole("heading", { name: "صنف البلاغ" });
    const toggle = within(section("أرواح في خطر")).getByRole("switch", {
      name: "تدريب دوري",
    });
    await waitFor(() => expect(toggle).toBeEnabled());
    fireEvent.click(toggle);
    await waitFor(() => expect(phase9.savePlatformSetting).toHaveBeenCalled());
    const [key, body] =
      vi.mocked(phase9.savePlatformSetting).mock.calls[0] ?? [];
    expect(key).toBe("learning.schedule");
    expect(body?.version).toBe(3);
    expect((body?.value as Record<string, unknown>).report_lives).toEqual({
      enabled: true,
      every_days: 7,
    });
  });

  it("is read-only for the central committee", async () => {
    renderApp(<LearningPage />, {
      api: fakeApi(),
      auth: fakeAuth(CENTRAL_COMMITTEE_CLAIMS),
      lang: "ar",
    });
    await screen.findByRole("heading", { name: "صنف البلاغ" });
    expect(
      screen.queryByRole("button", { name: "أطلق التدريب الآن" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "تصدير النصوص (CSV)" }),
    ).not.toBeInTheDocument();
  });
});

describe("LearningLabelSection", () => {
  it("lets the operator confirm the reading of a rejected report", async () => {
    const learning = fakeLearningApi();
    renderApp(
      <LearningLabelSection
        report={makeDetail({ id: "r1", status: "rejected" })}
      />,
      {
        api: fakeApi({ ...learning }),
        lang: "ar",
      },
    );
    const form = (
      await screen.findByRole("heading", { name: "تأكيد القراءة للتدريب" })
    ).closest("section") as HTMLElement;
    const lives = await within(form).findByRole("group", {
      name: "هل كانت هناك أرواح في خطر؟",
    });
    fireEvent.click(within(lives).getByRole("radio", { name: "نعم" }));
    fireEvent.click(within(form).getByRole("button", { name: "أكّد" }));
    await waitFor(() =>
      expect(learning.saveLearningLabel).toHaveBeenCalledWith("r1", {
        category: "fire",
        lives_at_risk: true,
        rejected: true,
      }),
    );
    expect(await within(form).findByText("مؤكَّد")).toBeInTheDocument();
  });

  it("is absent on an open report", () => {
    const learning = fakeLearningApi();
    renderApp(
      <LearningLabelSection
        report={makeDetail({ id: "r1", status: "in_progress" })}
      />,
      {
        api: fakeApi({ ...learning }),
      },
    );
    expect(screen.queryByText("تأكيد القراءة للتدريب")).not.toBeInTheDocument();
    expect(learning.learningLabel).not.toHaveBeenCalled();
  });
});
