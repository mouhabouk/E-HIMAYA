import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StreamAlertToasts } from "../components/StreamAlertToasts";
import { resetAlertSoundForTests } from "../lib/alertSound";
import { FakeWebSocket } from "../test/FakeWebSocket";
import { makeDetail } from "../test/fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { FakeStreamSession, makeStream, makeStreamDetail } from "../test/streamFixtures";
import { ReportDetailPage } from "./ReportDetailPage";
import { StreamArchivePage } from "./StreamArchivePage";
import { StreamDetailPage } from "./StreamDetailPage";
import { StreamsPage } from "./StreamsPage";
import { StreamWallPage } from "./StreamWallPage";

vi.mock("../components/LazyMap", () => ({
  LazyMapView: (props: { ariaLabel: string; pois?: unknown[]; lines?: { coordinates: unknown[] }[] }) => (
    <div data-testid="map" aria-label={props.ariaLabel} data-pois={props.pois?.length ?? 0} data-line={props.lines?.[0]?.coordinates.length ?? 0} />
  ),
}));

const NATIONAL_OPERATOR = { ...OPERATOR_CLAIMS, scope_level: "national" };

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

const page = (items: ReturnType<typeof makeStream>[], next: string | null = null) => Promise.resolve({ items, next_cursor: next });

beforeEach(() => {
  FakeWebSocket.reset();
  FakeStreamSession.reset();
  resetAlertSoundForTests();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StreamsPage (live list)", () => {
  it("lists live streams, strongest fire first, with badges and the simulation band", async () => {
    const api = fakeApi({
      streams: vi.fn(() =>
        page([
          makeStream({ id: "s-quiet", tracking_code: "EH-26-61-0000001", max_fire_confidence: null, max_smoke_confidence: null }),
          makeStream({ id: "s-sim", source: "sim", label: "[SIM] Simulateur Sfax", simulated: true, max_fire_confidence: 0.91 }),
        ]),
      ),
    });
    renderApp(<StreamsPage />, { api, lang: "fr" });
    const table = await screen.findByRole("table", { name: "Liste des diffusions en cours" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0] as HTMLElement).getByRole("link", { name: "Simulateur Sfax" })).toHaveAttribute("href", "/streams/s-sim");
    expect(within(rows[0] as HTMLElement).getByText("[SIM]")).toBeInTheDocument();
    expect(within(rows[0] as HTMLElement).getByText("Feu 91 %")).toHaveAttribute("title", "Confiance élevée (seuil d’alerte)");
    expect(within(rows[0] as HTMLElement).getByText("Source simulée")).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText("EH-26-61-0000001")).toBeInTheDocument();
    expect(screen.getByRole("note", { name: "Mode simulation" })).toHaveTextContent("وضع المحاكاة · Mode simulation");
    expect(api.streams).toHaveBeenCalledWith({ status: "live", gouvernorat: null }, expect.objectContaining({ cursor: null }));
  });

  it("follows stream.started / location / ended events", async () => {
    const api = fakeApi({ streams: vi.fn(() => page([makeStream({ id: "s-1", tracking_code: "EH-1" })])) });
    renderApp(<StreamsPage />, { api, lang: "fr" });
    await screen.findByText("EH-1");
    const send = await openLive();
    send({ type: "stream.started", stream: makeStream({ id: "s-2", tracking_code: "EH-2", last_location: null }) });
    expect(await screen.findByText("EH-2")).toBeInTheDocument();
    send({ type: "stream.location", stream_id: "s-2", lat: 36.80001, lon: 10.18 });
    expect(await screen.findByText("36.80001, 10.18000")).toBeInTheDocument();
    send({ type: "stream.ended", stream: makeStream({ id: "s-1", tracking_code: "EH-1", status: "ended" }) });
    await waitFor(() => expect(screen.queryByText("EH-1")).not.toBeInTheDocument());
  });

  it("offers a gouvernorat filter to national accounts and pins a stream to the wall", async () => {
    const api = fakeApi({ streams: vi.fn(() => page([makeStream({ id: "s-1", tracking_code: "EH-1" })])) });
    renderApp(<StreamsPage />, { api, auth: fakeAuth(NATIONAL_OPERATOR), lang: "fr" });
    await screen.findByText("EH-1");
    const select = await screen.findByLabelText("Gouvernorat");
    await screen.findByRole("option", { name: "Sfax" });
    fireEvent.change(select, { target: { value: "61" } });
    await waitFor(() => expect(api.streams).toHaveBeenCalledWith({ status: "live", gouvernorat: 61 }, expect.anything()));
    fireEvent.click(await screen.findByRole("button", { name: "Afficher EH-1 sur le mur d’écrans" }));
    expect(JSON.parse(localStorage.getItem("ehimaya.streamWall") ?? "{}")).toEqual({ layout: 4, pinned: ["s-1"] });
  });

  it("renders in Arabic", async () => {
    const api = fakeApi({ streams: vi.fn(() => page([makeStream()])) });
    renderApp(<StreamsPage />, { api, lang: "ar" });
    expect(await screen.findByRole("heading", { name: "البث المباشر" })).toBeInTheDocument();
    expect(await screen.findByText(/^حريق 82/)).toBeInTheDocument();
  });
});

describe("fire and smoke alerts", () => {
  function stubAudio() {
    const started = vi.fn();
    class FakeAudioContext {
      state = "running";
      currentTime = 0;
      destination = {};
      resume = () => Promise.resolve();
      createOscillator() {
        return { type: "", frequency: { value: 0 }, connect: (n: unknown) => n, start: started, stop: vi.fn() };
      }
      createGain() {
        return {
          gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
          connect: (n: unknown) => n,
        };
      }
    }
    vi.stubGlobal("AudioContext", FakeAudioContext);
    return started;
  }

  it("shows a toast with a sound, merges repeats, and never acts by itself", async () => {
    const tones = stubAudio();
    const api = fakeApi({ streams: vi.fn(() => page([makeStream({ id: "s-1", tracking_code: "EH-ALERT", simulated: true })])) });
    renderApp(
      <>
        <StreamAlertToasts />
        <StreamsPage />
      </>,
      { api, lang: "fr" },
    );
    await screen.findAllByText("EH-ALERT");
    const send = await openLive();
    send({ type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.83, report_id: "r-1" });
    const toast = await screen.findByRole("alert");
    expect(toast).toHaveTextContent("Feu détecté sur une diffusion en direct");
    expect(toast).toHaveTextContent("Confiance 83 % · EH-ALERT");
    expect(within(toast).getByText("[SIM]")).toBeInTheDocument();
    expect(within(toast).getByRole("link", { name: "Voir la diffusion" })).toHaveAttribute("href", "/streams/s-1");
    expect(within(toast).getByRole("link", { name: "Ouvrir le signalement" })).toHaveAttribute("href", "/reports/r-1");
    expect(tones).toHaveBeenCalledTimes(2); // two tones, one cue

    send({ type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.95, report_id: "r-1" });
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Confiance 95 %"));
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(tones).toHaveBeenCalledTimes(2);
    expect(api.stopStream).not.toHaveBeenCalled();
    expect(api.changeStatus).not.toHaveBeenCalled();

    // Sound off: a smoke alert still shows, silently.
    fireEvent.click(within(screen.getByRole("region", { name: "Alertes de l’analyse d’image" })).getByRole("button", { name: "Son des alertes : activé" }));
    send({ type: "stream.alert", stream_id: "s-1", label: "smoke", confidence: 0.7, report_id: null });
    expect(await screen.findByText("Fumée détectée sur une diffusion en direct")).toBeInTheDocument();
    expect(tones).toHaveBeenCalledTimes(2);
    expect(localStorage.getItem("ehimaya.streamAlertSound")).toBe("off");

    fireEvent.click(screen.getByRole("button", { name: "Fermer l’alerte Fumée : EH-ALERT" }));
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(1));
    fireEvent.keyDown(screen.getByRole("alert"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    // Dismissed: the same alert does not come straight back.
    send({ type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.9, report_id: "r-1" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("StreamDetailPage", () => {
  const route = "/streams/:id";

  it("shows the player, track, detections and recordings with SHA-256, and downloads one", async () => {
    const api = fakeApi({ stream: vi.fn(() => Promise.resolve(makeStreamDetail({ id: "s-1" }))) });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderApp(<StreamDetailPage />, { api, path: "/streams/s-1", route, lang: "fr" });

    expect(await screen.findByRole("heading", { name: /Diffusion EH-26-61-0004821/, level: 1 })).toBeInTheDocument();
    expect(screen.getByText("En direct", { selector: ".chip" })).toBeInTheDocument();
    expect(screen.getByLabelText("Vidéo en direct : EH-26-61-0004821")).toBeInTheDocument();
    await waitFor(() => expect(api.streamViewer).toHaveBeenCalledWith("s-1"));
    expect(FakeStreamSession.instances[0]?.started).toBe(true);
    expect(screen.getByTestId("map")).toHaveAttribute("data-line", "2");
    expect(screen.getByText("Points du trajet : 2")).toBeInTheDocument();
    const detections = screen.getByRole("heading", { name: "Chronologie des détections (2)" }).closest("section");
    expect(within(detections as HTMLElement).getByText("Feu 82 %")).toBeInTheDocument();
    expect(within(detections as HTMLElement).getByText("Fumée 40 %")).toBeInTheDocument();
    const recordings = screen.getByRole("table", { name: "Enregistrements de la diffusion avec leur empreinte" });
    expect(within(recordings).getByText("b".repeat(64))).toBeInTheDocument();
    expect(within(recordings).getByText("1 min")).toBeInTheDocument();
    fireEvent.click(within(recordings).getByRole("button", { name: /Télécharger l’enregistrement/ }));
    await waitFor(() => expect(api.recordingDownload).toHaveBeenCalledWith("s-1", "rec-1"));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: "EH-26-61-0004821" })).toHaveAttribute("href", "/reports/r-1");
  });

  it("stops the stream after confirmation (operator)", async () => {
    let stopped = false;
    const api = fakeApi({
      stream: vi.fn(() => Promise.resolve(makeStreamDetail({ id: "s-1", status: stopped ? "ended" : "live" }))),
      stopStream: vi.fn(() => {
        stopped = true;
        return Promise.resolve({});
      }),
    });
    renderApp(<StreamDetailPage />, { api, path: "/streams/s-1", route, lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Arrêter la diffusion" }));
    expect(screen.getByRole("alert")).toHaveTextContent("La diffusion sera arrêtée");
    expect(api.stopStream).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Arrêter la diffusion" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’arrêt" }));
    await waitFor(() => expect(api.stopStream).toHaveBeenCalledWith("s-1"));
    expect(await screen.findByText("Terminée", { selector: ".chip" })).toBeInTheDocument();
  });

  it("has no stop control for read-only roles nor for an ended stream", async () => {
    const api = fakeApi({ stream: vi.fn(() => Promise.resolve(makeStreamDetail({ id: "s-1" }))) });
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["local_committee"] } });
    renderApp(<StreamDetailPage />, { api, auth, path: "/streams/s-1", route, lang: "fr" });
    await screen.findByLabelText("Vidéo en direct : EH-26-61-0004821");
    expect(screen.queryByRole("button", { name: "Arrêter la diffusion" })).not.toBeInTheDocument();

    const ended = fakeApi({
      stream: vi.fn(() => Promise.resolve(makeStreamDetail({ id: "s-2", status: "ended", end_reason: "max_duration", duration_s: 900 }))),
    });
    renderApp(<StreamDetailPage />, { api: ended, path: "/streams/s-2", route, lang: "fr" });
    expect(await screen.findByText("Diffusion terminée.")).toBeInTheDocument();
    expect(screen.getByText("Durée maximale atteinte")).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: "Arrêter la diffusion" })).toHaveLength(0);
    expect(ended.streamViewer).not.toHaveBeenCalled();
  });
});

describe("StreamWallPage", () => {
  it("shows 1, 4 or 9 tiles, fills them with live streams and draws fresh detection boxes", async () => {
    const streams = [
      makeStream({ id: "s-1", tracking_code: "EH-1" }),
      makeStream({ id: "s-2", tracking_code: "EH-2", max_fire_confidence: null, simulated: true, source: "sim" }),
    ];
    const fresh = new Date().toISOString();
    const api = fakeApi({
      streams: vi.fn(() => page(streams)),
      stream: vi.fn((id: string) =>
        Promise.resolve(
          makeStreamDetail({
            ...streams.find((s) => s.id === id),
            detections: id === "s-1" ? [{ at: fresh, label: "fire", confidence: 0.9, boxes: [[0.1, 0.1, 0.5, 0.5, 0.9]] }] : [],
          }),
        ),
      ),
    });
    // jsdom does no layout: give the tiles a size so the boxes can be placed.
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(640);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(360);
    const { container } = renderApp(<StreamWallPage />, { api, lang: "fr" });
    expect(await screen.findByRole("heading", { name: /Écran 1/ })).toHaveTextContent("EH-1");
    expect(screen.getAllByRole("heading", { level: 2, name: /^Écran \d/ })).toHaveLength(4);
    expect(screen.getByRole("heading", { name: /Écran 2/ })).toHaveTextContent("[SIM]");
    expect(screen.getAllByText("Aucune diffusion pour cet écran.")).toHaveLength(2);
    expect(screen.getByRole("note", { name: "Mode simulation" })).toBeInTheDocument();
    await waitFor(() => expect(FakeStreamSession.instances.filter((s) => s.started && !s.stopped)).toHaveLength(2));
    expect(screen.getByTestId("map")).toHaveAttribute("data-pois", "2");
    await waitFor(() => expect(container.querySelectorAll("rect.det-box--fire")).toHaveLength(1));
    expect(screen.getByRole("img", { name: /^Feu 90/ })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("9"));
    expect(screen.getAllByRole("heading", { level: 2, name: /^Écran \d/ })).toHaveLength(9);
    fireEvent.click(screen.getByLabelText("1"));
    expect(screen.getAllByRole("heading", { level: 2, name: /^Écran \d/ })).toHaveLength(1);
    // The second stream's viewer was released with its tile.
    await waitFor(() => expect(FakeStreamSession.instances.filter((s) => s.started && !s.stopped)).toHaveLength(1));

    // Pin the simulated stream to the only screen.
    fireEvent.change(screen.getByLabelText("Diffusion affichée sur l’Écran 1"), { target: { value: "s-2" } });
    expect(await screen.findByRole("heading", { name: /Écran 1/ })).toHaveTextContent("EH-2");
    expect(JSON.parse(localStorage.getItem("ehimaya.streamWall") ?? "{}")).toEqual({ layout: 1, pinned: ["s-2"] });
  });
});

describe("StreamArchivePage", () => {
  it("lists ended streams, filters by detection and pages with the cursor", async () => {
    const first = [
      makeStream({ id: "e-1", tracking_code: "EH-FIRE", status: "ended", duration_s: 300, max_fire_confidence: 0.8 }),
      makeStream({ id: "e-2", tracking_code: "EH-CALM", status: "ended", duration_s: 60, max_fire_confidence: null, max_smoke_confidence: null }),
    ];
    const streams = vi.fn((_f: unknown, opts?: { cursor?: string | null }) =>
      opts?.cursor === "next" ? page([makeStream({ id: "e-3", tracking_code: "EH-OLD", status: "ended" })]) : page(first, "next"),
    );
    const api = fakeApi({ streams });
    renderApp(<StreamArchivePage />, { api, lang: "fr" });
    // Fewer rows than a screenful: the next page is loaded on its own.
    expect(await screen.findByText("EH-OLD")).toBeInTheDocument();
    expect(streams).toHaveBeenCalledWith({ status: "ended", gouvernorat: null }, expect.objectContaining({ cursor: "next" }));
    expect(screen.getByText("EH-FIRE").closest("tr")).toHaveTextContent("5 min");
    fireEvent.change(screen.getByLabelText("Détection"), { target: { value: "none" } });
    expect(screen.queryByText("EH-FIRE")).not.toBeInTheDocument();
    expect(screen.getByText("EH-CALM")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Détection"), { target: { value: "fire" } });
    expect(screen.getByText("EH-FIRE")).toBeInTheDocument();
    expect(screen.queryByText("EH-CALM")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Du"), { target: { value: "2099-01-01" } });
    expect(await screen.findByText("Aucune diffusion terminée ne correspond aux filtres.")).toBeInTheDocument();
  });
});

describe("ReportDetailPage (phase 6)", () => {
  it("shows the report's streams and the vision results of its images", async () => {
    const base = makeDetail({ id: "r-1" });
    const [image] = base.media;
    if (!image) throw new Error("fixture without media");
    const detail = makeDetail({
      id: "r-1",
      media: [
        {
          ...image,
          analysis: { vision: { model: "yolo-fire-v2", detections: [{ label: "smoke", confidence: 0.66, boxes: [[0.2, 0.2, 0.6, 0.7, 0.66]] }] } },
        },
        {
          id: "m-rec",
          kind: "recording",
          bytes: 1000,
          sha256: "c".repeat(64),
          status: "stored",
          url: "https://s3.example/rec?sig=1",
          content_type: "video/mp4",
          stream_id: "s-old",
          duration_s: 60,
        },
      ],
    });
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(detail)),
      streams: vi.fn(() => page([makeStream({ id: "s-live", report_id: "r-1" }), makeStream({ id: "s-other", report_id: "r-9" })])),
      stream: vi.fn(() => Promise.resolve(makeStreamDetail({ id: "s-old", status: "ended", duration_s: 120 }))),
    });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r-1", route: "/reports/:id", lang: "fr" });

    const section = (await screen.findByRole("heading", { name: /Diffusion en direct du signalement \(2\)/ })).closest("section") as HTMLElement;
    expect(within(section).getAllByRole("link", { name: "Diffusion (Application citoyenne)" }).map((a) => a.getAttribute("href"))).toEqual([
      "/streams/s-live",
      "/streams/s-old",
    ]);
    expect(api.stream).toHaveBeenCalledWith("s-old", expect.anything());
    // Watching is an explicit choice (each viewer token is audited).
    expect(api.streamViewer).not.toHaveBeenCalled();
    fireEvent.click(within(section).getByRole("button", { name: "Regarder" }));
    await waitFor(() => expect(api.streamViewer).toHaveBeenCalledWith("s-live"));

    expect(screen.getByText("Analyse d’image")).toBeInTheDocument();
    expect(screen.getByText("Modèle : yolo-fire-v2", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Fumée 66 %")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Image" })).toBeInTheDocument();
    expect(screen.getByLabelText("Enregistrement de diffusion")).toHaveAttribute("controls");
    expect(screen.getByRole("link", { name: "Ouvrir la diffusion" })).toHaveAttribute("href", "/streams/s-old");
  });
});
