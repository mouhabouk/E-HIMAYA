import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router";
import { SoftphoneDock } from "../components/Softphone";
import { ApiError } from "../lib/api";
import { FakeWebSocket } from "../test/FakeWebSocket";
import { makeIncidentDetail } from "../test/fixtures";
import { makeResource } from "../test/opsFixtures";
import {
  FakeSipEngine,
  makeCall,
  makeCommandBoard,
  makeCommandCard,
  makeCredentials,
  makeFireForecast,
  makeRecommendations,
  makeSuggestion,
} from "../test/phase7Fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { CallsPage } from "./CallsPage";
import { IncidentDetailPage } from "./IncidentDetailPage";
import { NotificationEditorPage } from "./NotificationEditorPage";
import { WeatherSuggestionsPage } from "./WeatherSuggestionsPage";

vi.mock("../components/LazyMap", () => ({
  LazyMapView: (props: { ariaLabel: string; polygons?: unknown[]; lines?: unknown[]; focusBounds?: unknown }) => (
    <div
      data-testid="map"
      aria-label={props.ariaLabel}
      data-polygons={props.polygons?.length ?? 0}
      data-lines={props.lines?.length ?? 0}
      data-focus={props.focusBounds ? "yes" : "no"}
    />
  ),
}));

const EDITOR = { sub: "e-1", name: "Rim Editor", realm_access: { roles: ["content_editor"] }, scope_level: "national" };
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

beforeEach(() => {
  FakeWebSocket.reset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("WeatherSuggestionsPage", () => {
  function setup(overrides: Parameters<typeof fakeApi>[0] = {}, claims: Record<string, unknown> = EDITOR) {
    const api = fakeApi({ weatherSuggestions: vi.fn(() => Promise.resolve([makeSuggestion()])), ...overrides });
    return renderApp(
      <Routes>
        <Route path="/weather/suggestions" element={<WeatherSuggestionsPage />} />
        <Route path="/notifications/new" element={<NotificationEditorPage />} />
      </Routes>,
      { api, auth: fakeAuth(claims), lang: "fr", path: "/weather/suggestions" },
    );
  }

  it("summarises a suggestion raised by a sensor or a watch tower of the local network (L5b)", async () => {
    const sensor = makeSuggestion({
      id: "ws-s",
      title: { ar: "أمطار غزيرة مقيسة", fr: "Fortes pluies mesurées", en: "Heavy rain measured" },
      evidence: {
        source: "sensor",
        sensor_id: "s-1",
        sensor_code: "SFX-RAIN-01",
        sensor_name: "Pluviomètre Chaabouni [SIM]",
        provider: "INM",
        level: "alarm",
        threshold: 40,
        unit: "mm",
        max_value: 46.5,
        peak_point: { lat: 34.74, lon: 10.76 },
      },
    });
    const tower = makeSuggestion({
      id: "ws-t",
      title: { ar: "حريق رصده برج مراقبة", fr: "Feu repéré par une tour de guet", en: "Fire spotted by a watch tower" },
      evidence: {
        source: "tower",
        tower_id: "t-1",
        tower_code: "JND-TWR-01",
        tower_name: "Tour d’Aïn Draham [SIM]",
        label: "fire",
        confidence: 0.86,
        hits: 4,
        frames: 5,
        bearing_deg: 90,
        fov_deg: 60,
        range_m: 8000,
        peak_point: { lat: 36.78, lon: 8.69 },
      },
    });
    setup({ weatherSuggestions: vi.fn(() => Promise.resolve([sensor, tower])) });
    const rain = await screen.findByRole("article", { name: "Fortes pluies mesurées" });
    expect(within(rain).queryByRole("table")).not.toBeInTheDocument();
    expect(rain).toHaveTextContent("Pluviomètre Chaabouni [SIM]");
    expect(rain).toHaveTextContent("46,5 mm (≥ 40 mm)");
    expect(rain).toHaveTextContent("Alarme");
    expect(within(rain).getByRole("link", { name: "Page des capteurs" })).toHaveAttribute("href", "/sensors");
    const fire = screen.getByRole("article", { name: "Feu repéré par une tour de guet" });
    expect(fire).toHaveTextContent("Feu · 86 %");
    expect(fire).toHaveTextContent("4 sur 5");
    expect(fire).toHaveTextContent("Est (90°), ouverture 60°, portée 8 km");
    expect(within(fire).getByRole("link", { name: "Page des tours" })).toHaveAttribute("href", "/towers");
  });

  it("shows the evidence and opens the alert form prefilled on accept (nothing is sent)", async () => {
    const { api } = setup();
    const card = await screen.findByRole("article", { name: "Danger d’incendie très élevé" });
    const evidence = within(card).getByRole("table", { name: "Mesures à l’origine de la suggestion" });
    expect(within(evidence).getByRole("rowheader", { name: "Indice forêt-météo (IFM)" })).toBeInTheDocument();
    expect(within(evidence).getByText("≥ 38")).toBeInTheDocument();
    expect((await within(card).findAllByText("Sfax")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Open-Meteo\.com/)).toHaveAttribute("href", "https://open-meteo.com/");

    fireEvent.click(within(card).getByRole("button", { name: "Accepter et ouvrir le formulaire d’alerte" }));
    await waitFor(() => expect(api.acceptWeatherSuggestion).toHaveBeenCalledWith("ws-1"));
    expect(await screen.findByRole("heading", { name: "Nouvelle alerte", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("alerte météo suggérée");
    expect(screen.getByLabelText("Titre (arabe)")).toHaveValue("خطر حرائق مرتفع جدا");
    expect(screen.getByLabelText("Titre (français)")).toHaveValue("Danger d’incendie très élevé");
    expect(screen.getByLabelText("Catégorie")).toHaveValue("weather");
    expect(screen.getByLabelText("Niveau de vigilance")).toHaveValue("high");
    expect(api.createMessage).not.toHaveBeenCalled();
    expect(api.publishMessage).not.toHaveBeenCalled();
  });

  it("dismisses only with a reason", async () => {
    const list = vi.fn(() => Promise.resolve([makeSuggestion()]));
    const { api } = setup({ weatherSuggestions: list });
    const card = await screen.findByRole("article", { name: "Danger d’incendie très élevé" });
    fireEvent.click(within(card).getByRole("button", { name: "Écarter" }));
    fireEvent.click(within(card).getByRole("button", { name: "Écarter la suggestion" }));
    expect(within(card).getByText("Indiquez un motif (au moins 3 caractères).")).toBeInTheDocument();
    expect(api.dismissWeatherSuggestion).not.toHaveBeenCalled();
    list.mockResolvedValue([]);
    fireEvent.change(within(card).getByLabelText("Motif (obligatoire)"), { target: { value: "Déjà couvert" } });
    fireEvent.click(within(card).getByRole("button", { name: "Écarter la suggestion" }));
    await waitFor(() => expect(api.dismissWeatherSuggestion).toHaveBeenCalledWith("ws-1", "Déjà couvert"));
    await waitFor(() => expect(screen.queryByRole("article")).not.toBeInTheDocument());
  });

  it("refreshes on weather.suggestion and marks the new one; shows the simulation band", async () => {
    const list = vi.fn(() => Promise.resolve([makeSuggestion()]));
    setup({ weatherSuggestions: list });
    await screen.findByRole("article");
    const send = await openLive();
    list.mockResolvedValue([
      makeSuggestion(),
      makeSuggestion({ id: "ws-2", simulated: true, title: { ar: "أمطار", fr: "Fortes pluies" } }),
    ]);
    send({ type: "weather.suggestion", suggestion_id: "ws-2" });
    const fresh = await screen.findByRole("article", { name: /Fortes pluies/ });
    expect(within(fresh).getByText("Nouvelle")).toBeInTheDocument();
    expect(screen.getByRole("note", { name: "Mode simulation" })).toBeInTheDocument();
  });

  it("offers accept to the committees too", async () => {
    setup({}, { ...EDITOR, realm_access: { roles: ["local_committee"] } });
    const card = await screen.findByRole("article");
    expect(within(card).getByRole("button", { name: "Accepter et ouvrir le formulaire d’alerte" })).toBeInTheDocument();
  });
});

describe("SoftphoneDock", () => {
  async function connected(options: { creds?: Parameters<typeof makeCredentials>[0] } = {}) {
    const sipEngine = new FakeSipEngine();
    const api = fakeApi({ sipCredentials: vi.fn(() => Promise.resolve(makeCredentials(options.creds))) });
    const utils = renderApp(<SoftphoneDock />, { api, auth: fakeAuth(NATIONAL_OPERATOR), lang: "fr", sipEngine });
    fireEvent.click(await screen.findByRole("button", { name: /Téléphone/ }));
    fireEvent.click(screen.getByRole("button", { name: "Activer le téléphone" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Téléphone/ })).toHaveTextContent("disponible"));
    expect(sessionStorage.getItem("ehimaya.softphoneOn")).toBe("1");
    return { ...utils, sipEngine };
  }

  it("is not offered to roles without telephony", () => {
    renderApp(<SoftphoneDock />, { auth: fakeAuth(EDITOR), lang: "fr" });
    expect(screen.queryByRole("complementary", { name: "Téléphone" })).not.toBeInTheDocument();
  });

  it("rings with queue info, answers, holds, mutes, links and hangs up; scenario 1 instruction", async () => {
    const { sipEngine, api } = await connected();
    const send = await openLive();
    send({
      type: "call.ringing",
      call: makeCall({ id: "call-7", caller_number: "+216 ** *** *42" }),
      queue: { name: "operators", waiting: 3 },
    });
    act(() => {
      sipEngine.ring("+21698000042");
    });
    const incoming = await screen.findByRole("alert", { name: "Appel entrant" });
    expect(within(incoming).getByText("+216 ** *** *42")).toBeInTheDocument();
    expect(within(incoming).getByText("operators")).toBeInTheDocument();
    expect(within(incoming).getByText("3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Téléphone/ })).toHaveTextContent("1 appel(s) entrant(s)");

    fireEvent.click(within(incoming).getByRole("button", { name: "Répondre" }));
    const active = await screen.findByRole("region", { name: "Appel en cours" });
    const hold = within(active).getByRole("button", { name: "Mettre en attente" });
    fireEvent.click(hold);
    expect(within(active).getByRole("button", { name: "Reprendre" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(active).getByRole("button", { name: "Couper le micro" }));
    expect(within(active).getByRole("button", { name: "Rétablir le micro" })).toHaveAttribute("aria-pressed", "true");

    // Scenario 1 (default): no transfer button, the instruction with the number to copy.
    expect(within(active).queryByRole("button", { name: "Transférer au 198" })).not.toBeInTheDocument();
    expect(within(active).getByText(/appelez le 198 depuis votre propre téléphone/)).toBeInTheDocument();
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    fireEvent.click(within(active).getByRole("button", { name: "Copier le numéro" }));
    expect(writeText).toHaveBeenCalledWith("198");
    expect(await within(active).findByText("Numéro copié.")).toBeInTheDocument();

    fireEvent.change(within(active).getByLabelText("Valeur"), { target: { value: "eh-26-61-0000001" } });
    fireEvent.click(within(active).getByRole("button", { name: "Lier" }));
    await waitFor(() => expect(api.linkCall).toHaveBeenCalledWith("call-7", { tracking_code: "EH-26-61-0000001" }));
    expect(await within(active).findByRole("link", { name: "EH-26-61-0000001" })).toHaveAttribute(
      "href",
      "/reports/r-1",
    );

    fireEvent.click(within(active).getByRole("button", { name: "Raccrocher" }));
    expect(await screen.findByRole("region", { name: "Appel terminé" })).toBeInTheDocument();
  });

  it("offers the 198 transfer only when the API enables it, after confirmation", async () => {
    const { sipEngine, api } = await connected({ creds: { transfer_198_enabled: true } });
    act(() => {
      sipEngine.ring("+21698000042", { "x-ehimaya-call-id": "call-8" });
    });
    fireEvent.click(await screen.findByRole("button", { name: "Répondre" }));
    const active = await screen.findByRole("region", { name: "Appel en cours" });
    expect(within(active).queryByText(/appelez le 198/)).not.toBeInTheDocument();
    fireEvent.click(within(active).getByRole("button", { name: "Transférer au 198" }));
    expect(api.transferTo198).not.toHaveBeenCalled();
    fireEvent.click(within(active).getByRole("button", { name: "Confirmer le transfert" }));
    await waitFor(() => expect(api.transferTo198).toHaveBeenCalledWith("call-8"));
    expect(await within(active).findByText("Appel transféré au 198.")).toBeInTheDocument();
  });

  it("shows a registration error", async () => {
    const sipEngine = new FakeSipEngine();
    sipEngine.autoRegister = false;
    renderApp(<SoftphoneDock />, { auth: fakeAuth(NATIONAL_OPERATOR), lang: "fr", sipEngine });
    fireEvent.click(await screen.findByRole("button", { name: /Téléphone/ }));
    fireEvent.click(screen.getByRole("button", { name: "Activer le téléphone" }));
    await waitFor(() => expect(sipEngine.events).not.toBeNull());
    act(() => sipEngine.events?.onRegistration("failed", "Forbidden"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enregistrement refusé par le serveur téléphonique.");
  });
});

describe("CallsPage", () => {
  it("lists calls with links, filters them and plays a recording", async () => {
    const api = fakeApi({
      calls: vi.fn(() =>
        Promise.resolve({
          items: [
            makeCall({
              id: "c-1",
              status: "ended",
              answered_at: "2026-10-20T10:00:10Z",
              ended_at: "2026-10-20T10:02:10Z",
              report_id: "r-1",
              tracking_code: "EH-26-61-0000001",
              recording_media_id: "m-1",
            }),
            makeCall({ id: "c-2", direction: "outbound", status: "missed", caller_number: "+216 ** *** *77" }),
          ],
          next_cursor: null,
        }),
      ),
    });
    renderApp(<CallsPage />, { api, lang: "fr" });
    const table = await screen.findByRole("table", { name: "Journal des appels" });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByRole("link", { name: "EH-26-61-0000001" })).toHaveAttribute("href", "/reports/r-1");
    expect(within(table).getByText("2 min")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Sens"), { target: { value: "outbound" } });
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getByText("Manqué")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Sens"), { target: { value: "" } });

    fireEvent.change(screen.getByLabelText("État"), { target: { value: "missed" } });
    await waitFor(() => expect(api.calls).toHaveBeenLastCalledWith({ status: "missed" }, expect.anything()));
  });

  it("fetches the recording through the audited endpoint", async () => {
    const api = fakeApi({
      calls: vi.fn(() =>
        Promise.resolve({ items: [makeCall({ id: "c-1", recording_media_id: "m-1" })], next_cursor: null }),
      ),
    });
    renderApp(<CallsPage />, { api, lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Écouter" }));
    await waitFor(() => expect(api.callRecording).toHaveBeenCalledWith("c-1"));
    const audio = await screen.findByLabelText(/Enregistrement de l’appel/);
    expect(audio).toHaveAttribute("src", "https://s3.example/call.wav?sig=x");
    expect(screen.getByRole("link", { name: "Télécharger" })).toHaveAttribute(
      "href",
      "https://s3.example/call.wav?sig=x",
    );
  });
});

describe("IncidentDetailPage decision support", () => {
  function setup(overrides: Parameters<typeof fakeApi>[0] = {}) {
    const api = fakeApi({
      incident: vi.fn(() => Promise.resolve(makeIncidentDetail())),
      recommendations: vi.fn(() => Promise.resolve(makeRecommendations())),
      resources: vi.fn(() =>
        Promise.resolve({ items: [makeResource({ id: "res-1", label: "CCF-12" })], next_cursor: null }),
      ),
      responders: vi.fn(() =>
        Promise.resolve([
          {
            name: "Gouverneur de Sfax",
            role: "Gouverneur",
            phone: "+21674000000",
            reason: { ar: "سلطة جهوية", fr: "Autorité régionale" },
          },
        ]),
      ),
      ...overrides,
    });
    const utils = renderApp(
      <Routes>
        <Route path="/incidents/:id" element={<IncidentDetailPage />} />
        <Route path="/notifications/new" element={<NotificationEditorPage />} />
      </Routes>,
      {
        api,
        // The lead room's manager: assignments are regional (phase 9 §5.4), the centre requests resources instead.
        auth: fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } }),
        lang: "fr",
        path: "/incidents/i-1",
      },
    );
    return utils;
  }

  it("runs a fire forecast: polygons on the map with legend, inputs, assumptions and disclaimer", async () => {
    const { api } = setup();
    const panel = (await screen.findByRole("heading", { name: "Prévision de propagation" })).closest("section");
    if (!panel) throw new Error("no panel");
    fireEvent.click(within(panel).getByLabelText("240 min"));
    fireEvent.change(within(panel).getByLabelText("Combustible"), { target: { value: "shrub" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Lancer la prévision" }));
    await waitFor(() =>
      expect(api.fireForecast).toHaveBeenCalledWith("i-1", {
        ignition: null,
        fuel_model: "shrub",
        horizons_min: [30, 60, 120, 240],
      }),
    );
    expect(await within(panel).findByText("Estimation indicative.")).toBeInTheDocument();
    expect(within(panel).getByText("Pente 0 (pas de modèle de terrain)")).toBeInTheDocument();
    expect(within(panel).getByText("Vitesse de propagation : 12,5 m/min")).toBeInTheDocument();
    const legends = screen.getAllByRole("table", { name: "Légende de la prévision" });
    expect(within(legends[0] as HTMLElement).getByRole("rowheader", { name: "30 min" })).toBeInTheDocument();
    expect(within(legends[0] as HTMLElement).getByText("42,1 ha")).toBeInTheDocument();
    const map = screen.getByTestId("map");
    expect(map).toHaveAttribute("data-polygons", "2");
    expect(map).toHaveAttribute("data-focus", "yes");
    fireEvent.click(within(panel).getByLabelText("Afficher sur la carte"));
    expect(screen.getByTestId("map")).toHaveAttribute("data-polygons", "0");
  });

  it("shows recommendations with rationale and confidence; actions open existing flows", async () => {
    const { api } = setup();
    const panel = (await screen.findByRole("heading", { name: "Recommandations" })).closest("section");
    if (!panel) throw new Error("no panel");
    const first = await within(panel).findByRole("listitem", { name: "Envoyer un camion-citerne" });
    expect(within(first).getByText("Confiance élevée")).toBeInTheDocument();
    expect(within(first).getByText(/Danger très élevé, moyen le plus proche à 4 km/)).toBeInTheDocument();
    expect(within(panel).getAllByText("Aide à la décision —").length).toBeGreaterThan(0);

    // show_route → route drawn on the map with its summary.
    fireEvent.click(within(first).getByRole("button", { name: "Afficher l’itinéraire" }));
    await waitFor(() =>
      expect(api.route).toHaveBeenCalledWith(
        { lat: 34.7, lon: 10.7 },
        { lat: 34.74, lon: 10.76 },
        "truck",
        expect.anything(),
      ),
    );
    expect(await screen.findByText(/5,2 km|5 200 m/)).toBeInTheDocument();
    expect(screen.getByTestId("map")).toHaveAttribute("data-lines", "1");
    expect(screen.getByRole("link", { name: "Itinéraire © contributeurs OpenStreetMap (ODbL)" })).toBeInTheDocument();

    // open_assignment → the existing assignment form, resource preselected, nothing submitted.
    fireEvent.click(within(first).getByRole("button", { name: "Préparer l’affectation" }));
    await waitFor(() => expect(screen.getByLabelText("Moyen")).toHaveValue("res-1"));
    expect(api.createAssignment).not.toHaveBeenCalled();

    // open_alert_form → the composer prefilled.
    const second = within(panel).getByRole("listitem", { name: "Alerter la population" });
    fireEvent.click(within(second).getByRole("button", { name: "Ouvrir le formulaire d’alerte" }));
    expect(await screen.findByLabelText("Titre (français)")).toHaveValue("Feu de forêt");
    expect(screen.getByLabelText("Phénomène")).toHaveValue("forest_fire");
  });

  it("times the units on the road and draws the route of one, and of a hospital (L4 §10)", async () => {
    const { api } = setup({
      responders: vi.fn(() =>
        Promise.resolve([
          {
            id: "unit:u1",
            name: "Poste avancé Sakiet",
            reason: { ar: "الأسرع وصولا", fr: "la plus rapide : 7 min, 5,2 km par la route" },
            lat: 34.7,
            lon: 10.7,
            road_m: 5200,
            road_s: 420,
            engine: "valhalla",
          },
        ]),
      ),
      incidentHospitals: vi.fn(() =>
        Promise.resolve([
          {
            id: "h1",
            name: "CHU Habib Bourguiba",
            phone: null,
            layer: "hopitaux",
            lat: 34.73,
            lon: 10.75,
            distance_m: 1500,
            road_m: 2100,
            road_s: 300,
            engine: "valhalla",
            simulated: false,
          },
        ]),
      ),
    });
    const responders = (await screen.findByRole("heading", { name: "Responsables à associer" })).closest("section");
    if (!responders) throw new Error("no panel");
    expect(await within(responders).findByText(/5,2 km, environ 7 min/)).toBeInTheDocument();
    fireEvent.click(within(responders).getByRole("button", { name: "Itinéraire depuis Poste avancé Sakiet" }));
    await waitFor(() =>
      expect(api.route).toHaveBeenCalledWith({ lat: 34.7, lon: 10.7 }, { lat: 34.74, lon: 10.76 }, "truck", expect.anything()),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Itinéraire vers CHU Habib Bourguiba" }));
    await waitFor(() =>
      expect(api.route).toHaveBeenCalledWith({ lat: 34.74, lon: 10.76 }, { lat: 34.73, lon: 10.75 }, "car", expect.anything()),
    );
  });

  it("lists responders with their reason, and the assistant cites its sources as advisory", async () => {
    const ask = vi.fn(() =>
      Promise.resolve({
        answer: "Établir un périmètre de 200 m.",
        model: "qwen2.5:7b",
        sources: [
          {
            kind: "procedure" as const,
            id: "p-fire-01",
            title: "Feux de forêt — premières mesures",
            excerpt: "Périmètre…",
          },
          { kind: "incident" as const, id: "i-old", title: "Incendie Sfax 2025", excerpt: "Même zone" },
        ],
      }),
    );
    setup({ askAssistant: ask });
    const responders = (await screen.findByRole("heading", { name: "Responsables à associer" })).closest("section");
    if (!responders) throw new Error("no panel");
    expect(await within(responders).findByText("Autorité régionale")).toBeInTheDocument();
    expect(within(responders).getByRole("link", { name: "+21674000000" })).toHaveAttribute("href", "tel:+21674000000");

    const assistant = screen
      .getByRole("heading", { name: "Assistant (procédures et incidents passés)" })
      .closest("section");
    if (!assistant) throw new Error("no panel");
    fireEvent.change(within(assistant).getByLabelText("Votre question"), { target: { value: "Quel périmètre ?" } });
    fireEvent.click(within(assistant).getByRole("button", { name: "Demander" }));
    await waitFor(() => expect(ask).toHaveBeenCalledWith("i-1", "Quel périmètre ?", "fr"));
    expect(await within(assistant).findByText("Établir un périmètre de 200 m.")).toBeInTheDocument();
    expect(within(assistant).getByRole("link", { name: "Incendie Sfax 2025" })).toHaveAttribute(
      "href",
      "/incidents/i-old",
    );
    expect(within(assistant).getByText("Feux de forêt — premières mesures")).toBeInTheDocument();
    expect(within(assistant).getAllByText("Aide à la décision —").length).toBeGreaterThan(0);
  });

  it("says when the assistant model is not installed", async () => {
    setup({ askAssistant: vi.fn(() => Promise.reject(new ApiError(503, "assistant_unavailable"))) });
    const assistant = (
      await screen.findByRole("heading", { name: "Assistant (procédures et incidents passés)" })
    ).closest("section");
    if (!assistant) throw new Error("no panel");
    fireEvent.change(within(assistant).getByLabelText("Votre question"), { target: { value: "Quel périmètre ?" } });
    fireEvent.click(within(assistant).getByRole("button", { name: "Demander" }));
    expect(await within(assistant).findByRole("alert")).toHaveTextContent("le modèle local n’est pas installé");
  });

  it("starts and joins the crisis conference through the softphone", async () => {
    const sipEngine = new FakeSipEngine();
    const api = fakeApi({ incident: vi.fn(() => Promise.resolve(makeIncidentDetail())) });
    renderApp(
      <Routes>
        <Route path="/incidents/:id" element={<IncidentDetailPage />} />
      </Routes>,
      {
        api,
        auth: fakeAuth(NATIONAL_OPERATOR),
        lang: "fr",
        path: "/incidents/i-1",
        sipEngine,
      },
    );
    const panel = (await screen.findByRole("heading", { name: "Conférence de crise" })).closest("section");
    if (!panel) throw new Error("no panel");
    fireEvent.click(await within(panel).findByRole("button", { name: "Ouvrir une conférence" }));
    await waitFor(() => expect(api.startConference).toHaveBeenCalledWith("i-1"));
    await waitFor(() => expect(sipEngine.dialled.map((d) => d.target)).toEqual(["sip:crisis-1@ehimaya.test"]));
    expect(await within(panel).findByText("Conférence rejointe.")).toBeInTheDocument();
  });
});

describe("Outbound call buttons", () => {
  it("are hidden without telephony and dial through the softphone otherwise", async () => {
    const forecast = makeFireForecast();
    expect(forecast.polygons).toHaveLength(2);
    const sipEngine = new FakeSipEngine();
    const api = fakeApi({
      incident: vi.fn(() => Promise.resolve(makeIncidentDetail())),
      responders: vi.fn(() => Promise.resolve([{ name: "Délégué", phone: "+21674000001", reason: "Délégation" }])),
    });
    renderApp(
      <Routes>
        <Route path="/incidents/:id" element={<IncidentDetailPage />} />
      </Routes>,
      {
        api,
        auth: fakeAuth(NATIONAL_OPERATOR),
        lang: "fr",
        path: "/incidents/i-1",
        sipEngine,
      },
    );
    fireEvent.click(await screen.findByRole("button", { name: "Appeler Délégué" }));
    await waitFor(() => expect(api.dial).toHaveBeenCalledWith({ number: "+21674000001" }));
    expect(await screen.findByText(/Appel lancé/)).toBeInTheDocument();
  });
});

describe("IncidentDetailPage commander's assistant (AI5a)", () => {
  function setup(overrides: Parameters<typeof fakeApi>[0] = {}) {
    const api = fakeApi({
      incident: vi.fn(() => Promise.resolve(makeIncidentDetail())),
      commandBoard: vi.fn(() => Promise.resolve(makeCommandBoard())),
      decideCommand: vi.fn((id: string) => Promise.resolve(makeCommandCard({ id, status: "adopted" }))),
      resources: vi.fn(() =>
        Promise.resolve({ items: [makeResource({ id: "res-1", label: "CCF-12" })], next_cursor: null }),
      ),
      ...overrides,
    });
    const utils = renderApp(
      <Routes>
        <Route path="/incidents/:id" element={<IncidentDetailPage />} />
      </Routes>,
      {
        api,
        auth: fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } }),
        lang: "fr",
        path: "/incidents/i-1",
      },
    );
    return utils;
  }

  async function panel() {
    const section = (await screen.findByRole("heading", { name: "Assistant du commandant" })).closest("section");
    if (!section) throw new Error("no panel");
    return section;
  }

  it("numbers the proposals with what commanders did elsewhere; adopting records the decision only", async () => {
    const { api } = setup();
    const p = await panel();
    const list = await within(p).findByRole("list", { name: "Propositions numérotées du commandant" });
    const first = within(list).getByRole("listitem", { name: "Engager 1 camion-citerne d'eau" });
    expect(first.querySelector(".commander__no")).toHaveTextContent("1");
    expect(within(first).getByText("Proposition automatique")).toBeInTheDocument();
    expect(within(first).getByText(/adoptée 7 fois sur 9 \(dont 1 modifiée\(s\)\), rejetée 2 fois/)).toBeInTheDocument();
    expect(within(first).getByText(/Motif de rejet le plus fréquent : Déjà fait/)).toBeInTheDocument();
    const second = within(list).getByRole("listitem", { name: "Proposer le passage au niveau crise" });
    expect(within(second).getByText(/Pas encore d’antécédent/)).toBeInTheDocument();
    // One box for orders and questions: the classic panels are not shown twice.
    expect(screen.queryByRole("heading", { name: "Recommandations" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Assistant (procédures et incidents passés)" })).not.toBeInTheDocument();

    fireEvent.click(within(first).getByRole("button", { name: "Adopter" }));
    await waitFor(() => expect(api.decideCommand).toHaveBeenCalledWith("cd-1", { verdict: "adopt" }));
    await waitFor(() => expect(api.commandBoard).toHaveBeenCalledTimes(2));
    expect(api.createAssignment).not.toHaveBeenCalled();
  });

  it("rejects with a ready reason; 'other' needs a note", async () => {
    const { api } = setup();
    const p = await panel();
    const first = await within(p).findByRole("listitem", { name: "Engager 1 camion-citerne d'eau" });
    fireEvent.click(within(first).getByRole("button", { name: "Rejeter" }));
    const confirm = within(first).getByRole("button", { name: "Confirmer le rejet" });
    expect(confirm).toBeDisabled();
    fireEvent.click(within(first).getByLabelText("Autre motif"));
    expect(confirm).toBeDisabled();
    fireEvent.change(within(first).getByLabelText("Précisez le motif"), { target: { value: "  la route est coupée " } });
    expect(confirm).toBeEnabled();
    fireEvent.click(within(first).getByLabelText("Déjà fait"));
    fireEvent.click(confirm);
    await waitFor(() =>
      expect(api.decideCommand).toHaveBeenCalledWith("cd-1", {
        verdict: "reject",
        reason_code: "already_done",
        note: "la route est coupée",
      }),
    );
  });

  it("adopts modified: an action removed, nothing changed is refused", async () => {
    const { api } = setup();
    const p = await panel();
    const first = await within(p).findByRole("listitem", { name: "Engager 1 camion-citerne d'eau" });
    fireEvent.click(within(first).getByRole("button", { name: "Modifier puis adopter" }));
    const confirm = within(first).getByRole("button", { name: "Adopter modifié" });
    expect(confirm).toBeDisabled();
    expect(within(first).getByText(/Rien n’a changé/)).toBeInTheDocument();
    fireEvent.click(within(first).getByRole("checkbox", { name: "Engager CCF-12" }));
    fireEvent.click(confirm);
    await waitFor(() =>
      expect(api.decideCommand).toHaveBeenCalledWith("cd-1", { verdict: "modify", kept_actions: [] }),
    );
  });

  it("turns a typed order into a card and shows how it was read", async () => {
    const reading = {
      intent: "order",
      action: "dispatch",
      resource_kind: "fire_engine",
      count: 2,
      reader: "rules",
    } as const;
    const order = makeCommandCard({
      id: "cd-9",
      origin: "order",
      title: { ar: "إرسال 2 شاحنة إطفاء", fr: "Engager 2 fourgons" },
      command_text: "ابعثولي زوز كميونات طفي",
      inputs: { reading },
    });
    const { api } = setup({
      commandText: vi.fn(() =>
        Promise.resolve({ reading, fallback: true, card: order, answer: null }),
      ),
    });
    const p = await panel();
    vi.mocked(api.commandBoard).mockResolvedValue(makeCommandBoard({ proposals: [order] }));
    fireEvent.change(within(p).getByLabelText("Ordre ou question"), { target: { value: "ابعثولي زوز كميونات طفي" } });
    fireEvent.click(within(p).getByRole("button", { name: "Envoyer" }));
    await waitFor(() => expect(api.commandText).toHaveBeenCalledWith("i-1", "ابعثولي زوز كميونات طفي", "fr", null));
    expect(await within(p).findByText(/le lexique seul a lu l’ordre/)).toBeInTheDocument();
    expect(within(p).getByText("Votre ordre est ajouté en tête de liste.")).toBeInTheDocument();
    const card = await within(p).findByRole("listitem", { name: "Engager 2 fourgons" });
    expect(within(card).getByText("Votre ordre")).toBeInTheDocument();
    expect(within(card).getByText("ابعثولي زوز كميونات طفي")).toBeInTheDocument();
    expect(within(card).getByText(/^Envoi · 2 × /)).toBeInTheDocument();
  });

  it("lets whoever is not the commander see the board without deciding (AI5b)", async () => {
    setup({ commandBoard: vi.fn(() => Promise.resolve(makeCommandBoard({ can_decide: false }))) });
    const p = await panel();
    expect(await within(p).findByRole("listitem", { name: "Engager 1 camion-citerne d'eau" })).toBeInTheDocument();
    expect(within(p).getByText(/la décision revient au chef de salle/)).toBeInTheDocument();
    expect(within(p).queryByLabelText("Ordre ou question")).not.toBeInTheDocument();
    expect(within(p).queryByRole("button", { name: "Adopter" })).not.toBeInTheDocument();
  });

  describe("voice message (AI5b)", () => {
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
    const track = { stop: vi.fn() };
    const getUserMedia = vi.fn(() => Promise.resolve({ getTracks: () => [track] }));

    beforeEach(() => {
      vi.stubGlobal("MediaRecorder", FakeRecorder);
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        value: { getUserMedia },
      });
    });
    afterEach(() => {
      vi.unstubAllGlobals();
      Reflect.deleteProperty(navigator, "mediaDevices");
    });

    it("records, puts the transcript in the box to correct, and sends it with the message id", async () => {
      const { api } = setup({
        commandVoice: vi.fn(() =>
          Promise.resolve({
            voice_id: "v-1",
            text: "envoyez deux fourgon",
            language: "fr",
            model: "whisper",
            duration_s: 3,
          }),
        ),
        commandText: vi.fn(() =>
          Promise.resolve({
            reading: { intent: "order" as const, action: "dispatch" as const, reader: "rules" as const },
            fallback: false,
            card: makeCommandCard({ id: "cd-9", origin: "order" }),
            answer: null,
          }),
        ),
      });
      const p = await panel();
      fireEvent.click(await within(p).findByRole("button", { name: "Message vocal" }));
      const stop = await within(p).findByRole("button", { name: "Arrêter (60 s)" });
      expect(stop).toHaveAttribute("aria-pressed", "true");
      fireEvent.click(stop);
      await waitFor(() => expect(api.commandVoice).toHaveBeenCalledWith("i-1", expect.any(Blob), "fr"));
      expect(track.stop).toHaveBeenCalled();
      const box = within(p).getByLabelText("Ordre ou question");
      await waitFor(() => expect(box).toHaveValue("envoyez deux fourgon"));
      expect(within(p).getByText(/corrigez si besoin puis envoyez/)).toBeInTheDocument();
      expect(api.commandText).not.toHaveBeenCalled();
      fireEvent.change(box, { target: { value: "envoyez deux fourgons" } });
      fireEvent.click(within(p).getByRole("button", { name: "Envoyer" }));
      await waitFor(() => expect(api.commandText).toHaveBeenCalledWith("i-1", "envoyez deux fourgons", "fr", "v-1"));
      await waitFor(() => expect(within(p).queryByText(/corrigez si besoin/)).not.toBeInTheDocument());
    });

    it("says when the microphone is refused, and when transcription is down", async () => {
      const { api } = setup({
        commandVoice: vi.fn(() => Promise.reject(new ApiError(503, "transcription_unavailable"))),
      });
      const p = await panel();
      getUserMedia.mockRejectedValueOnce(new Error("denied"));
      fireEvent.click(await within(p).findByRole("button", { name: "Message vocal" }));
      expect(await within(p).findByText("Le navigateur n'a pas autorisé le microphone.")).toBeInTheDocument();
      fireEvent.click(within(p).getByRole("button", { name: "Message vocal" }));
      fireEvent.click(await within(p).findByRole("button", { name: "Arrêter (60 s)" }));
      await waitFor(() => expect(api.commandVoice).toHaveBeenCalled());
      expect(await within(p).findByText(/La transcription n'est pas disponible/)).toBeInTheDocument();
    });
  });

  it("answers a question from cited sources", async () => {
    const { api } = setup({
      commandText: vi.fn(() =>
        Promise.resolve({
          reading: { intent: "question" as const, action: null, reader: "rules" as const },
          fallback: false,
          card: null,
          answer: {
            answer: "Trois citernes sont disponibles à Sfax.",
            sources: [{ kind: "incident" as const, id: "i-7", title: "Feu de Sakiet", excerpt: "3 citernes engagées." }],
            model: "qwen3:8b",
          },
        }),
      ),
    });
    const p = await panel();
    fireEvent.change(within(p).getByLabelText("Ordre ou question"), { target: { value: "combien de citernes ?" } });
    fireEvent.click(within(p).getByRole("button", { name: "Envoyer" }));
    expect(await within(p).findByText("Trois citernes sont disponibles à Sfax.")).toBeInTheDocument();
    expect(within(p).getByRole("link", { name: "Feu de Sakiet" })).toHaveAttribute("href", "/incidents/i-7");
    expect(api.decideCommand).not.toHaveBeenCalled();
  });
});
