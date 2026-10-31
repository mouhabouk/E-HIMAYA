// covers: review point 19 (phase D, docs/phase-d/design-d.md §5)
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fakeApi, renderApp } from "../test/render";
import { DictatedTextarea } from "./Dictation";

class FakeRecorder {
  state: "inactive" | "recording" = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  readonly stream: MediaStream;
  constructor(stream: MediaStream) {
    this.stream = stream;
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["voice"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

function Note({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState("Sur place:");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSend(text);
      }}
    >
      <label htmlFor="n">Note</label>
      <DictatedTextarea field="report.note" id="n" value={text} onText={setText} />
      <button type="submit">Envoyer</button>
    </form>
  );
}

describe("dictation of a free-text field", () => {
  const track = { stop: vi.fn() };
  beforeEach(() => {
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [track] })) },
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, "mediaDevices");
  });

  it("adds the text heard to the field, then sends the text kept once with the form", async () => {
    const api = fakeApi({
      dictate: vi.fn(() =>
        Promise.resolve({ dictation_id: "d-1", text: "feu de foret", language: "fr", model: "whisper", duration_s: 2 }),
      ),
      dictationKept: vi.fn(() => Promise.resolve({ words: 3, word_errors: 1, wer: 0.33 })),
    });
    const sent = vi.fn();
    renderApp(<Note onSend={sent} />, { api, lang: "fr" });
    fireEvent.click(screen.getByRole("button", { name: "Dicter" }));
    const stop = await screen.findByRole("button", { name: "Arrêter (60 s)" });
    fireEvent.click(stop);
    await waitFor(() => expect(api.dictate).toHaveBeenCalledWith("report.note", expect.any(Blob), "fr"));
    const box = screen.getByLabelText("Note");
    await waitFor(() => expect(box).toHaveValue("Sur place: feu de foret"));
    fireEvent.change(box, { target: { value: "Sur place: feu de forêt" } });
    fireEvent.click(screen.getByRole("button", { name: "Envoyer" }));
    await waitFor(() => expect(api.dictationKept).toHaveBeenCalledWith("d-1", "Sur place: feu de forêt"));
    expect(sent).toHaveBeenCalledWith("Sur place: feu de forêt");
    fireEvent.click(screen.getByRole("button", { name: "Envoyer" }));
    expect(api.dictationKept).toHaveBeenCalledTimes(1);
  });

  it("no microphone in the browser: a plain field", () => {
    vi.unstubAllGlobals();
    renderApp(<Note onSend={vi.fn()} />, { lang: "fr" });
    expect(screen.queryByRole("button", { name: "Dicter" })).not.toBeInTheDocument();
  });
});
