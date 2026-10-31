// covers: review point 9 (phase D, docs/phase-d/design-d.md §7)
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { NavGroup } from "../components/Navigation";
import { applyMenuOrder, menuOrderOf, moved } from "../lib/menuOrder";
import type { PlatformSetting } from "../lib/phase9Types";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { MenuOrderPage } from "./MenuOrderPage";

const SYSADMIN = {
  ...OPERATOR_CLAIMS,
  realm_access: { roles: ["sysadmin", "operator"] },
  scope_level: "national",
};

const entry = (to: string) => ({
  to,
  icon: "home" as const,
  tone: "navy" as const,
  label: to,
});
const GROUPS: NavGroup[] = [
  {
    key: "ops",
    icon: "dashboard",
    tone: "red",
    label: "Ops",
    items: [entry("/"), entry("/reports"), entry("/map")],
  },
  {
    key: "alerts",
    icon: "campaign",
    tone: "red",
    label: "Alerts",
    items: [entry("/alerts")],
  },
  {
    key: "system",
    icon: "settings",
    tone: "slate",
    label: "System",
    items: [entry("/settings")],
  },
];

describe("the order of the menu", () => {
  it("sorts the named groups and links first, the others keep their place; nothing is added", () => {
    const out = applyMenuOrder(GROUPS, {
      groups: ["system", "nowhere"],
      items: { ops: ["/map", "/secret"] },
    });
    expect(out.map((g) => g.key)).toEqual(["system", "ops", "alerts"]);
    expect(out[1]?.items.map((i) => i.to)).toEqual(["/map", "/", "/reports"]);
    expect(applyMenuOrder(GROUPS, menuOrderOf(null))).toEqual(GROUPS);
    expect(
      menuOrderOf({ groups: ["ops", 3], items: { ops: ["/", null] } }),
    ).toEqual({ groups: ["ops"], items: { ops: ["/"] } });
    expect(moved(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
  });

  it("the system administrator moves a group and saves the order with a reason", async () => {
    const setting: PlatformSetting = {
      key: "menu.order",
      value: { groups: [], items: {} },
      version: 2,
      updated_by_name: null,
      updated_at: null,
      editable: true,
    };
    const save = vi.fn(
      (_key: string, body: { value: unknown; version: number }) =>
        Promise.resolve({ ...setting, value: body.value, version: 3 }),
    );
    const api = fakeApi({
      platformSettings: vi.fn(() => Promise.resolve([setting])),
      savePlatformSetting: save,
    });
    renderApp(<MenuOrderPage />, { api, auth: fakeAuth(SYSADMIN), lang: "en" });
    const groups = await screen.findByRole("list", { name: "Groups" });
    const first = within(groups).getAllByRole("listitem")[0];
    expect(first).toHaveAttribute("data-testid", "sortable-ops");
    const firstName = within(first as HTMLElement).getByText(/./, {
      selector: ".sortable__label",
    }).textContent;
    fireEvent.click(
      within(groups).getByRole("button", { name: `Move ${firstName} down` }),
    );
    const save1 = screen.getByRole("button", { name: "Save the order" });
    expect(save1).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Reason for the change/), {
      target: { value: "Order for the demonstration" },
    });
    fireEvent.click(save1);
    await waitFor(() => expect(save).toHaveBeenCalled());
    const [key, body] = save.mock.calls[0] as [
      string,
      { value: { groups: string[] }; version: number; reason: string },
    ];
    expect(key).toBe("menu.order");
    expect(body.version).toBe(2);
    expect(body.reason).toBe("Order for the demonstration");
    // The operations group, first in the built-in order, is now second.
    expect(body.value.groups[1]).toBe("ops");
    expect(await screen.findByText(/Order saved/)).toBeInTheDocument();
  });

  it("read-only for the others", async () => {
    const api = fakeApi({
      platformSettings: vi.fn(() =>
        Promise.resolve([
          {
            key: "menu.order",
            value: {},
            version: 0,
            updated_by_name: null,
            updated_at: null,
            editable: false,
          },
        ]),
      ),
    });
    renderApp(<MenuOrderPage />, { api, lang: "en" });
    expect(
      await screen.findByText(
        "Only the system administrator changes the menu order.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save the order" }),
    ).toBeDisabled();
  });
});
