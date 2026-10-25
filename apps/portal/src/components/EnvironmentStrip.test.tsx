import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/render";
import { EnvironmentStrip } from "./EnvironmentStrip";

describe("EnvironmentStrip (backlog G3)", () => {
  it("shows the amber [SIM] strip during an exercise", async () => {
    renderApp(<EnvironmentStrip />, { routes: { "GET /api/v1/app/environment": { body: { banner: "training" } } } });
    const strip = await screen.findByTestId("environment-strip");
    expect(strip).toHaveTextContent("SIM");
    expect(strip).toHaveTextContent("تمرين");
  });

  it("shows nothing in production", async () => {
    const { calls } = renderApp(<EnvironmentStrip />, {
      routes: { "GET /api/v1/app/environment": { body: { banner: null } } },
    });
    await waitFor(() => expect(calls("GET /api/v1/app/environment")).toHaveLength(1));
    expect(screen.queryByTestId("environment-strip")).toBeNull();
  });
});
