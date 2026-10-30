// covers: phase N (docs/phase-n/design-n.md §6): a national account filters the map and the lists on several
// gouvernorats at once.
import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useFilters } from "../context/filters";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { FiltersBar } from "./FiltersBar";

function Probe() {
  const { filters } = useFilters();
  return <output data-testid="chosen">{filters.gouvernorats.join(",")}</output>;
}

describe("FiltersBar", () => {
  it("picks several gouvernorats and goes back to all of them", async () => {
    sessionStorage.clear();
    const national = { sub: "u-n", name: "N", realm_access: { roles: ["operator"] }, scope_level: "national" };
    renderApp(
      <>
        <FiltersBar showGouvernorat />
        <Probe />
      </>,
      { api: fakeApi(), auth: fakeAuth(national), lang: "ar" },
    );
    const group = screen.getByRole("group", { name: "الولاية" });
    fireEvent.click(await within(group).findByRole("checkbox", { name: "تونس" }));
    fireEvent.click(within(group).getByRole("checkbox", { name: "صفاقس" }));
    expect(screen.getByTestId("chosen")).toHaveTextContent("11,61");
    expect(screen.getByText(/الولاية: تونس، صفاقس/)).toBeInTheDocument();
    fireEvent.click(within(group).getByRole("button", { name: "كل الولايات" }));
    expect(screen.getByTestId("chosen")).toHaveTextContent("");
  });
});
