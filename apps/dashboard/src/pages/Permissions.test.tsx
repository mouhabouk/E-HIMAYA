// covers: phase L4 (docs/phase-l/design-l4.md §8): the administrator's permissions page (catalogue, rules, a new
// rule, a refusal by the fixed ceiling, the preview), and the dashboard following the rules (a hidden page refused, a
// granted page opened with the role its grants lend, the menu).
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Gate } from "../App";
import { navGroups } from "../components/Navigation";
import { useAuth } from "../context/auth";
import { ApiError } from "../lib/api";
import { allowed, featureOfPath, lentRoles } from "../lib/features";
import { canManagePermissions, canOpenSchedule } from "../lib/roles";
import { fakeFeaturesApi } from "../test/featuresFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { PermissionsPage } from "./PermissionsPage";

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

function Roles() {
  const { user } = useAuth();
  return <p>roles: {user?.identity.roles.join(",")}</p>;
}

describe("feature helpers", () => {
  it("maps paths to pages and applies the rules", () => {
    expect(featureOfPath("/")).toBe("home");
    expect(featureOfPath("/reports/late")).toBe("reports.late");
    expect(featureOfPath("/reports/123")).toBe("reports");
    expect(featureOfPath("/register/dispatches/9")).toBe("dispatches");
    expect(featureOfPath("/settings/ai")).toBe("ai_settings");
    expect(featureOfPath("/nowhere")).toBeNull();
    const access = { granted: new Set(["schedule.approve"]), hidden: new Set(["library"]), lent: { "schedule.approve": "ops_manager" } };
    expect(allowed(access, "schedule.approve", false)).toBe(true);
    expect(allowed(access, "library", true)).toBe(false);
    expect(allowed(access, "map", true)).toBe(true);
    expect(allowed(access, "map", false)).toBe(false);
    expect(lentRoles(access, "schedule")).toEqual(["ops_manager"]);
    expect(canManagePermissions({ roles: ["sysadmin"], national: true })).toBe(true);
    expect(canManagePermissions({ roles: ["sysadmin"], national: false })).toBe(false);
  });

  it("drops a hidden page from the menu and adds a granted one", () => {
    const identity = { subject: "s", name: "n", roles: ["operator"], gouvernoratCode: 21, national: false, hasScope: true, mfa: true };
    const t = ((k: string) => k) as never;
    const links = (access?: Parameters<typeof navGroups>[2]) =>
      navGroups(identity, t, access).flatMap((g) => g.items.map((i) => i.to));
    expect(links()).toContain("/map");
    expect(links()).not.toContain("/committee");
    const after = links({ granted: new Set(["committee"]), hidden: new Set(["map"]), lent: {} });
    expect(after).not.toContain("/map");
    expect(after).toContain("/committee");
  });
});

describe("Gate", () => {
  it("refuses a hidden page and opens a granted one with its lent role", async () => {
    const features = fakeFeaturesApi();
    features.myFeatures = vi.fn(() => Promise.resolve({ granted: [], hidden: ["schedule"], lent: {} }));
    renderApp(
      <Gate allow={canOpenSchedule}>
        <Roles />
      </Gate>,
      { api: fakeApi(features), auth: fakeAuth(claims(["operator"], "21")), path: "/schedule" },
    );
    await waitFor(() => expect(features.myFeatures).toHaveBeenCalled());
    expect(await screen.findByText(/حسابك لا يحمل/)).toBeInTheDocument();

    const granted = fakeFeaturesApi();
    granted.myFeatures = vi.fn(() =>
      Promise.resolve({ granted: ["schedule.approve"], hidden: [], lent: { "schedule.approve": "ops_manager" } }),
    );
    renderApp(
      <Gate allow={canOpenSchedule}>
        <Roles />
      </Gate>,
      { api: fakeApi(granted), auth: fakeAuth(claims(["operator"], "21")), path: "/schedule" },
    );
    expect(await screen.findByText("roles: operator,ops_manager")).toBeInTheDocument();
  });
});

describe("PermissionsPage", () => {
  it("lists the rules and the catalogue, saves a rule and explains a refusal", async () => {
    const features = fakeFeaturesApi();
    const api = fakeApi(features);
    renderApp(<PermissionsPage />, { api, auth: fakeAuth(claims(["sysadmin"])), path: "/permissions" });
    expect(await screen.findByText("[SIM] نيابة رئيس القاعة أثناء عطلته")).toBeInTheDocument();
    expect(screen.getByText("[SIM] نائب رئيس القاعة بنابل")).toBeInTheDocument();
    expect(screen.getAllByText("معطيات شخصية").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("الصفحة أو التبويب أو الزر"), { target: { value: "schedule.progress" } });
    fireEvent.click(screen.getByRole("radio", { name: "حجب" }));
    fireEvent.change(screen.getAllByLabelText("الدور")[0] as HTMLElement, { target: { value: "field_commander" } });
    fireEvent.change(screen.getByLabelText(/^السبب/), { target: { value: "[SIM] نسبة الإنجاز لرؤساء القاعات" } });
    fireEvent.click(screen.getByRole("button", { name: "حجب" }));
    await waitFor(() =>
      expect(features.createFeatureRule).toHaveBeenCalledWith(
        expect.objectContaining({
          feature_key: "schedule.progress",
          effect: "hide",
          target_kind: "role",
          target: "field_commander",
          gouvernorat_code: null,
        }),
      ),
    );

    api.createFeatureRule = vi.fn(() =>
      Promise.reject(new ApiError(422, "ceiling", "ceiling", null, { detail: "ceiling", reason: "personal_data" })),
    );
    fireEvent.click(screen.getByRole("radio", { name: "منح" }));
    fireEvent.change(screen.getByLabelText("الصفحة أو التبويب أو الزر"), { target: { value: "incidents" } });
    fireEvent.change(screen.getAllByLabelText("الدور")[0] as HTMLElement, { target: { value: "governor" } });
    fireEvent.change(screen.getByLabelText(/^السبب/), { target: { value: "[SIM] اطلاع الوالي" } });
    fireEvent.click(screen.getByRole("button", { name: "منح" }));
    expect(await screen.findByText(/فلا تُمنح للوالي ولا للوزير/)).toBeInTheDocument();
  });
});
