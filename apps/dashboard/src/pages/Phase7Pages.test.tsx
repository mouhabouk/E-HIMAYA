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
