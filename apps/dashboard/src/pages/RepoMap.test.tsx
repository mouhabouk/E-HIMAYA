// covers: NFR-13 (docs/dev/repo-map.md): the «تطوير النظام» menu and its system map.
import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { navGroups } from "../components/Navigation";
import { canUseDevTools, layout, type RepoMap } from "../lib/repoMap";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { identityFromClaims } from "../auth/identity";
import { RepoMapPage } from "./RepoMapPage";

const MAP: RepoMap = {
  nodes: [
    { id: "dashboard:SqlConsolePage", label: "SqlConsole", group: "dashboard", files: 1, loc: 1100, deg: 1 },
    { id: "api:sqlconsole", label: "sqlconsole", group: "api", files: 5, loc: 900, deg: 3 },
    { id: "api:audit", label: "audit", group: "api", files: 6, loc: 800, deg: 1 },
    { id: "infra:postgres", label: "PostgreSQL", group: "infra", files: 0, loc: 0, deg: 1 },
  ],
  edges: [
    { s: "dashboard:SqlConsolePage", t: "api:sqlconsole", k: "http", w: 9, via: ["/api/v1/admin/sql/query"] },
    { s: "api:sqlconsole", t: "api:audit", k: "import", w: 1, via: [] },
    { s: "api:sqlconsole", t: "infra:postgres", k: "calls", w: 1, via: [] },
  ],
  routes: 882,
  generated_at: "2026-11-09T22:00:00Z",
};

describe("system development", () => {
  it("is a menu of the national system administrator with the SQL window and the system map", () => {
    expect(canUseDevTools({ roles: ["sysadmin"], national: true })).toBe(true);
    expect(canUseDevTools({ roles: ["sysadmin"], national: false })).toBe(false);
    const t = ((k: string) => k) as never;
    const admin = identityFromClaims({ sub: "a", realm_access: { roles: ["sysadmin"] }, scope_level: "national" });
    const dev = navGroups(admin, t).find((g) => g.key === "dev");
    expect(dev?.items.map((i) => i.to)).toEqual(["/sql", "/dev/map"]);
    expect(navGroups(admin, t).find((g) => g.key === "system")?.items.some((i) => i.to === "/sql")).toBe(false);
    const ops = identityFromClaims({ sub: "b", realm_access: { roles: ["ops_manager"] }, scope_level: "national" });
    expect(navGroups(ops, t).some((g) => g.key === "dev")).toBe(false);
  });

  it("places every node once, the same way on every visit", () => {
    const a = layout(MAP.nodes, MAP.edges, 60);
    const b = layout(MAP.nodes, MAP.edges, 60);
    expect([...a.keys()]).toEqual(MAP.nodes.map((n) => n.id));
    expect(a.get("api:audit")).toEqual(b.get("api:audit"));
    expect(Number.isFinite(a.get("infra:postgres")?.x)).toBe(true);
  });

  it("shows the map, finds a page and lists what it uses with the API paths", async () => {
    renderApp(<RepoMapPage />, {
      api: fakeApi({ repoMap: vi.fn().mockResolvedValue(MAP) }),
      auth: fakeAuth({ sub: "a", realm_access: { roles: ["sysadmin"] }, scope_level: "national" }),
      lang: "ar",
      path: "/dev/map",
    });
    expect(await screen.findByText("مسارات API: 882")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("بحث عن صفحة أو وحدة"), { target: { value: "sql" } });
    expect(screen.getByText("النتائج: 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /SqlConsole \(لوحة القيادة\)/ }));
    const side = screen.getByRole("heading", { name: "SqlConsole" }).closest("aside");
    if (!side) throw new Error("no details");
    expect(within(side).getByText("/api/v1/admin/sql/query")).toBeInTheDocument();
    fireEvent.click(within(side).getByRole("button", { name: "sqlconsole" }));
    expect(within(side).getByText("PostgreSQL")).toBeInTheDocument();
    expect(within(side).getByText("audit")).toBeInTheDocument();
  });
});
