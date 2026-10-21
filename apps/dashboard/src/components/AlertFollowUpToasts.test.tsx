import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { FakeWebSocket } from "../test/FakeWebSocket";
import { makeMessage } from "../test/opsFixtures";
import { renderApp } from "../test/render";
import { AlertFollowUpToasts } from "./AlertFollowUpToasts";

async function openLive() {
  await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
  const ws = FakeWebSocket.last();
  act(() => {
    ws.serverOpen();
    ws.serverSend({ type: "ready" });
  });
  return (msg: unknown) =>
    act(() => {
      ws.serverSend(msg);
    });
}

describe("AlertFollowUpToasts (phase 10 §5)", () => {
  afterEach(() => {
    FakeWebSocket.reset();
  });

  it("keeps a failed delivery and an emergency publication on screen until dismissed", async () => {
    renderApp(<AlertFollowUpToasts />, { lang: "fr" });
    const send = await openLive();
    const message = makeMessage({ id: "m-7", status: "published", single_reviewer: true, emergency_reason: "Crue soudaine" });
    send({ type: "alert.delivery_degraded", message, channel: "sms", reason: "failures", sent: 40, failed: 9 });
    const toast = await screen.findByRole("alert");
    expect(toast).toHaveTextContent("Alerte mal diffusée");
    expect(toast).toHaveTextContent("Canal SMS : 9 échecs pour 40 envois réussis.");
    expect(within(toast).getByRole("link", { name: "Ouvrir l’alerte" })).toHaveAttribute("href", "/notifications/m-7");

    send({ type: "alert.review_needed", message });
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
    expect(screen.getByText(/Motif de l’urgence : Crue soudaine/)).toBeInTheDocument();

    // The same follow-up again replaces the earlier one.
    send({ type: "alert.delivery_degraded", message, channel: "sms", reason: "failures", sent: 41, failed: 10 });
    await waitFor(() => expect(screen.getByText("Canal SMS : 10 échecs pour 41 envois réussis.")).toBeInTheDocument());
    expect(screen.getAllByRole("alert")).toHaveLength(2);

    fireEvent.click(screen.getAllByRole("button", { name: "Masquer" })[0] as HTMLElement);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });
});
