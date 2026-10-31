import { vi } from "vitest";
import { ApiError } from "../lib/api";
import type { CommandBoard, CommandCard, ForecastRun, Recommendations } from "../lib/decisionTypes";
import type { Phase7Api } from "../lib/phase7Api";
import type { SipCall, SipCallHandlers, SipEngine, SipEngineEvents } from "../lib/softphone";
import type { SipCredentials, StaffCall } from "../lib/telephonyTypes";
import type { WeatherGrid, WeatherPointDetail, WeatherSuggestion } from "../lib/weatherTypes";

const empty = { items: [], next_cursor: null };

export function makeCredentials(overrides: Partial<SipCredentials> = {}): SipCredentials {
  return {
    ws_url: "wss://sip.example/ws",
    sip_uri: "sip:op-1@ehimaya.test",
    username: "op-1",
    password: "secret-1",
    expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
    ice_servers: [{ urls: "stun:stun.example:3478" }],
    ...overrides,
  };
}

export function makeCall(overrides: Partial<StaffCall> = {}): StaffCall {
  return {
    id: "call-1",
    direction: "inbound",
    caller_number: "+216 ** *** *42",
    started_at: new Date(Date.now() - 30_000).toISOString(),
    answered_at: null,
    ended_at: null,
    operator_user_id: null,
    queue: "operators",
    status: "ringing",
    report_id: null,
    incident_id: null,
    tracking_code: null,
    recording_media_id: null,
    transferred_to: null,
    end_reason: null,
    ...overrides,
  };
}

export function makeSuggestion(overrides: Partial<WeatherSuggestion> = {}): WeatherSuggestion {
  return {
    id: "ws-1",
    status: "pending",
    gouvernorat_codes: [61],
    category: "weather",
    severity: "high",
    hazard: "forest_fire",
    title: { ar: "خطر حرائق مرتفع جدا", fr: "Danger d’incendie très élevé", en: "Very high fire danger" },
    body: { ar: "تجنبوا إشعال النار.", fr: "Évitez tout feu.", en: "Avoid any fire." },
    evidence: [{ metric: "fwi", value: 42.5, threshold: 38, unit: null, gouvernorat_code: 61, lat: 34.74, lon: 10.76 }],
    rule: "fire_danger>=very_high",
    valid_until: new Date(Date.now() + 12 * 3_600_000).toISOString(),
    created_at: new Date(Date.now() - 600_000).toISOString(),
    simulated: false,
    ...overrides,
  };
}

export function makeGrid(overrides: Partial<WeatherGrid> = {}): WeatherGrid {
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [10.75, 34.75] },
        properties: {
          wind_speed_kmh: 35,
          wind_gust_kmh: 62,
          wind_direction_deg: 315,
          temperature_c: 31,
          humidity_pct: 18,
          precipitation_mm_h: 0,
          rain_24h_mm: 0,
          fwi: 41,
          fire_danger: "very_high",
          rain_level: "none",
        },
      },
    ],
    generated_at: new Date().toISOString(),
    simulated: false,
    attribution: { text: "Open-Meteo.com", url: "https://open-meteo.com/", licence: "CC BY 4.0" },
    ...overrides,
  };
}

export function makePointDetail(overrides: Partial<WeatherPointDetail> = {}): WeatherPointDetail {
  return {
    lat: 34.75,
    lon: 10.75,
    current: makeGrid().features[0]?.properties ?? {},
    hourly: [],
    alerts: [],
    attribution: { text: "Open-Meteo.com", url: "https://open-meteo.com/", licence: "CC BY 4.0" },
    simulated: false,
    ...overrides,
  };
}

export function makeFireForecast(overrides: Partial<ForecastRun> = {}): ForecastRun {
  const square = (d: number) => ({
    type: "Polygon" as const,
    coordinates: [
      [
        [10.76, 34.74],
        [10.76 + d, 34.74],
        [10.76 + d, 34.74 + d],
        [10.76, 34.74 + d],
        [10.76, 34.74],
      ],
    ],
  });
  return {
    forecast_id: "f-1",
    model: "rothermel-elliptical-v1",
    inputs: { wind_kmh: 35, rh: 18, temp: 31, slope_pct: 0, fuel: "mixed" },
    polygons: [
      { minutes: 60, geojson: square(0.02), area_ha: 42.1 },
      { minutes: 30, geojson: square(0.01), area_ha: 10.4 },
    ],
    rate_of_spread_m_min: 12.5,
    assumptions: [{ ar: "الانحدار 0 (لا يوجد نموذج تضاريس)", fr: "Pente 0 (pas de modèle de terrain)" }],
    disclaimer: { ar: "تقدير استرشادي.", fr: "Estimation indicative." },
    generated_at: new Date().toISOString(),
    simulated: false,
    ...overrides,
  };
}

export function makeRecommendations(overrides: Partial<Recommendations> = {}): Recommendations {
  return {
    generated_at: new Date().toISOString(),
    items: [
      {
        kind: "resources",
        title: { ar: "إرسال شاحنة إطفاء", fr: "Envoyer un camion-citerne" },
        rationale: {
          ar: "خطر حرائق مرتفع جدا وأقرب وسيلة على 4 كم",
          fr: "Danger très élevé, moyen le plus proche à 4 km",
        },
        inputs: { fire_danger: "very_high", distance_km: 4.2 },
        confidence: "high",
        actions: [
          { type: "open_assignment", resource_id: "res-1" },
          { type: "show_route", from: { lat: 34.7, lon: 10.7 }, to: { lat: 34.74, lon: 10.76 }, profile: "truck" },
        ],
      },
      {
        kind: "alert",
        title: { ar: "تنبيه السكان", fr: "Alerter la population" },
        rationale: { ar: "مساحة متوقعة كبيرة", fr: "Grande surface prévue" },
        inputs: { area_ha: 42 },
        confidence: "medium",
        actions: [
          {
            type: "open_alert_form",
            prefill: {
              title: { ar: "حريق غابة", fr: "Feu de forêt", en: "Forest fire" },
              body: { ar: "ابتعدوا عن المنطقة.", fr: "Éloignez-vous.", en: "Stay away." },
              severity: "high",
              category: "hazard",
              hazard: "forest_fire",
              area: { gouvernorat_codes: [61] },
            },
          },
          { type: "call", number: "+21671000000" },
        ],
      },
    ],
    ...overrides,
  };
}

export function makeCommandCard(overrides: Partial<CommandCard> = {}): CommandCard {
  return {
    id: "cd-1",
    incident_id: "i-1",
    origin: "rules",
    kind: "resources",
    key: "resources:water_tanker",
    title: { ar: "إرسال 1 شاحنة صهريج ماء", fr: "Engager 1 camion-citerne d'eau" },
    rationale: { ar: "الحاجة: 1، الأقرب زمنيا: CCF-12 (8 min).", fr: "Besoin : 1. Le plus proche : CCF-12 (8 min)." },
    confidence: "high",
    inputs: { resource_kind: "water_tanker", needed: 1 },
    actions: [{ type: "open_assignment", resource_id: "res-1", label: { ar: "تكليف CCF-12", fr: "Engager CCF-12" } }],
    status: "proposed",
    command_text: null,
    model: null,
    simulated: false,
    track: { decided: 9, adopted: 6, modified: 1, rejected: 2, top_reason: "already_done" },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makeCommandBoard(overrides: Partial<CommandBoard> = {}): CommandBoard {
  return {
    incident_id: "i-1",
    generated_at: new Date().toISOString(),
    proposals: [
      makeCommandCard(),
      makeCommandCard({
        id: "cd-2",
        kind: "escalation",
        key: "escalation:crisis",
        title: { ar: "اقتراح رفع المستوى إلى الأزمة", fr: "Proposer le passage au niveau crise" },
        rationale: { ar: "خطر حرائق أقصى.", fr: "Danger d'incendie extrême." },
        confidence: "medium",
        inputs: { proposed_level: "crisis" },
        actions: [],
        track: { decided: 0, adopted: 0, modified: 0, rejected: 0, top_reason: null },
      }),
    ],
    decided: [],
    simulated: false,
    ...overrides,
  };
}

/** Phase 7 calls of the fake API: empty or ready answers by default, override per test. */
export function fakePhase7Api(): Phase7Api {
  return {
    weatherGrid: vi.fn(() => Promise.resolve(makeGrid())),
    weatherAt: vi.fn(() => Promise.resolve(makePointDetail())),
    weatherSuggestions: vi.fn(() => Promise.resolve([])),
    acceptWeatherSuggestion: vi.fn(() => Promise.resolve({})),
    dismissWeatherSuggestion: vi.fn(() => Promise.resolve({})),
    fireForecast: vi.fn(() => Promise.resolve(makeFireForecast())),
    floodForecast: vi.fn(() => Promise.resolve(makeFireForecast({ model: "rain-advisory-v1", polygons: [] }))),
    recommendations: vi.fn(() => Promise.resolve({ generated_at: new Date().toISOString(), items: [] })),
    route: vi.fn(() =>
      Promise.resolve({
        distance_m: 5200,
        duration_s: 480,
        geometry: {
          type: "LineString" as const,
          coordinates: [
            [10.7, 34.7],
            [10.76, 34.74],
          ] as [number, number][],
        },
        engine: "osrm" as const,
        simulated: false,
      }),
    ),
    responders: vi.fn(() => Promise.resolve([])),
    askAssistant: vi.fn(),
    // Off by default: the classic recommendations panel shows (tests of the commander's assistant switch it on).
    commandBoard: vi.fn(() => Promise.reject(new ApiError(409, "commander_off"))),
    commandText: vi.fn(),
    commandVoice: vi.fn(),
    decideCommand: vi.fn(),
    sipCredentials: vi.fn(() => Promise.resolve(makeCredentials())),
    calls: vi.fn(() => Promise.resolve(empty)),
    call: vi.fn(),
    linkCall: vi.fn((id: string) =>
      Promise.resolve(makeCall({ id, report_id: "r-1", tracking_code: "EH-26-61-0000001" })),
    ),
    transferTo198: vi.fn((id: string) =>
      Promise.resolve(makeCall({ id, status: "transferred", transferred_to: "198" })),
    ),
    dial: vi.fn(() => Promise.resolve({ id: "call-out-1" })),
    callRecording: vi.fn(() => Promise.resolve({ kind: "link" as const, url: "https://s3.example/call.wav?sig=x" })),
    conferences: vi.fn(() => Promise.resolve([])),
    startConference: vi.fn(() => Promise.resolve({ room: "crisis-1", join_uri: "sip:crisis-1@ehimaya.test" })),
    endConference: vi.fn(() => Promise.resolve({})),
    // Phase D: the incident's media gallery (review point 21) and the dictation (review point 19).
    incidentMedia: vi.fn(() => Promise.resolve({ counts: {}, live_streams: 0, items: [] })),
    dictate: vi.fn(() => Promise.resolve({ dictation_id: "d-1", text: "", language: "ar", duration_s: 0, model: "whisper" })),
    dictationKept: vi.fn(() => Promise.resolve({ words: 0, word_errors: 0, wer: null })),
  };
}

/** A SIP dialog driven by the test. */
export class FakeSipCall implements SipCall {
  handlers: SipCallHandlers = {};
  answered = false;
  hungUp = false;
  holds: boolean[] = [];
  mutes: boolean[] = [];
  readonly direction: "incoming" | "outgoing";
  readonly remote: string;
  readonly headers: Readonly<Record<string, string>>;
  constructor(direction: "incoming" | "outgoing", remote: string, headers: Readonly<Record<string, string>> = {}) {
    this.direction = direction;
    this.remote = remote;
    this.headers = headers;
  }
  setHandlers(h: SipCallHandlers): void {
    this.handlers = h;
  }
  answer(): void {
    this.answered = true;
    this.handlers.onAccepted?.();
  }
  hangup(): void {
    this.hungUp = true;
    this.handlers.onEnded?.("Terminated");
  }
  hold(on: boolean): void {
    this.holds.push(on);
    this.handlers.onHold?.(on);
  }
  mute(on: boolean): void {
    this.mutes.push(on);
  }
}

/** A SIP stack that registers at once and lets the test ring the softphone. */
export class FakeSipEngine implements SipEngine {
  events: SipEngineEvents | null = null;
  started: SipCredentials[] = [];
  updated: SipCredentials[] = [];
  dialled: { target: string; call: FakeSipCall }[] = [];
  stopped = false;
  autoRegister = true;
  start(credentials: SipCredentials, events: SipEngineEvents): void {
    this.started.push(credentials);
    this.events = events;
    if (this.autoRegister) queueMicrotask(() => events.onRegistration("registered"));
  }
  updateCredentials(credentials: SipCredentials): void {
    this.updated.push(credentials);
  }
  call(target: string): FakeSipCall {
    const call = new FakeSipCall("outgoing", target);
    this.dialled.push({ target, call });
    return call;
  }
  stop(): void {
    this.stopped = true;
  }
  ring(remote: string, headers: Record<string, string> = {}): FakeSipCall {
    const call = new FakeSipCall("incoming", remote, headers);
    this.events?.onIncoming(call);
    return call;
  }
}
