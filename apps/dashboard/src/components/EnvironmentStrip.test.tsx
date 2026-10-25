import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, renderApp } from "../test/render";
import { EnvironmentStrip } from "./EnvironmentStrip";

describe("EnvironmentStrip (backlog G3)", () => {
  it("shows the amber [SIM] strip on a field pilot", async () => {
    const api = fakeApi({ environment: vi.fn(() => Promise.resolve({ banner: "pilot" as const })) });
    renderApp(<EnvironmentStrip />, { api });
    const strip = await screen.findByTestId("environment-strip");
    expect(strip).toHaveTextContent("SIM");
    expect(strip).toHaveTextContent("بيئة التجربة الميدانية");
  });

  it("shows nothing in production", async () => {
    const api = fakeApi();
    renderApp(<EnvironmentStrip />, { api });
    await vi.waitFor(() => expect(api.environment).toHaveBeenCalled());
    expect(screen.queryByTestId("environment-strip")).toBeNull();
  });
});
