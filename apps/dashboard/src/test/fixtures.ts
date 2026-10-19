import type {
  AiSettings,
  AiStatus,
  Analysis,
  IncidentDetail,
  IncidentSummary,
  Kpis,
  StaffReport,
  StaffReportDetail,
} from "../lib/types";

export function makeReport(overrides: Partial<StaffReport> = {}): StaffReport {
  const now = new Date().toISOString();
  return {
    id: "r-1",
    tracking_code: "EH-26-61-0004821",
    category: "fire",
    status: "received",
    text: "حريق في مستودع",
    lang: "ar",
    location: { lat: 34.74, lon: 10.76, accuracy_m: 12.5 },
    gouvernorat_code: 61,
    delegation_id: null,
    created_at: now,
    received_at: now,
    updated_at: now,
    reporter_kind: "citizen",
    media_count: 1,
    text_ar: null,
    priority_score: 55,
    credibility_score: 65,
    analysis_state: "done",
    lives_at_risk: false,
    suggested_category: null,
    incident_id: null,
    has_suggestion: false,
    ...overrides,
  };
}

export function makeDetail(overrides: Partial<StaffReportDetail> = {}): StaffReportDetail {
  const base = makeReport(overrides);
  return {
    ...base,
    history: [{ status: "received", at: base.received_at }],
    media: [
      {
        id: "m-1",
        kind: "image",
        bytes: 123456,
        sha256: "a".repeat(64),
        status: "stored",
        url: "https://s3.example/m-1?sig=x",
      },
    ],
    reporter: { kind: "citizen", first_name: "Amira", last_name: "Ben Salah", phone: "+21620000000" },
    ...overrides,
  };
}

export const KPIS: Kpis = {
  since: "2026-10-18T10:00:00Z",
  total: 12,
  by_status: { received: 3, in_progress: 4, intervened: 1, ongoing: 1, closed: 2, rejected: 1 },
  by_category: { fire: 5, flood: 2, medical: 5 },
  by_gouvernorat: [
    { code: 61, count: 7 },
    { code: 11, count: 5 },
  ],
  avg_first_response_s: 312.5,
  high_priority: 4,
  analysis_pending: 2,
};

/** The analysis example of phase-3-contract.md §2. */
export function makeAnalysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    state: "done",
    attempts: 1,
    language: "fr",
    steps: { transcribe: "done", extract: "done", translate: "done", embed: "done" },
    extraction: {
      language: "fr",
      category: "fire",
      lives_at_risk: true,
      people_trapped: true,
      injured_count: 2,
      deaths_reported: false,
      hazards: ["gas"],
      keywords: ["incendie"],
      summary_ar: "حريق في عمارة مع أشخاص عالقين",
      confidence: 0.9,
    },
    priority: {
      score: 79,
      components: [
        { key: "severity", value: 0.9, weight: 35, points: 35.0, detail: { category: "fire", hazards: ["gas"] } },
        { key: "lives", value: 1.0, weight: 25, points: 27.8, detail: { source: "model", people_trapped: true } },
        { key: "casualties", value: 0.4, weight: 10, points: 4.4, detail: { source: "model", injured: 2, deaths: false } },
        { key: "reporters", value: 0.3, weight: 10, points: 3.3, detail: { reporters: 2 } },
        { key: "credibility", value: 0.8, weight: 10, points: 8.9, detail: { score: 80 } },
        { key: "sensitive_sites", value: null, weight: 5, points: 0, detail: { reason: "no_data_yet" } },
        { key: "weather", value: null, weight: 5, points: 0, detail: { reason: "no_data_yet" } },
      ],
    },
    credibility: {
      score: 80,
      components: [
        { key: "base", points: 50, detail: {} },
        { key: "registered", points: 15, detail: { kind: "citizen" } },
        { key: "media", points: 10, detail: { count: 1 } },
        { key: "precise_location", points: 5, detail: { accuracy_m: 8 } },
      ],
    },
    suggestion: null,
    transcripts: [
      {
        media_id: "m-2",
        kind: "audio",
        text: "Il y a le feu au deuxième étage",
        language: "fr",
        language_probability: 0.93,
        duration_s: 41.2,
        translation_ar: "هناك حريق في الطابق الثاني",
        error: null,
        model: "faster-whisper-large-v3",
      },
    ],
    models: { transcribe: "faster-whisper-large-v3", extract: "qwen3:8b", translate_fr: "opus-mt-fr-ar", embed: "e5-base" },
    updated_at: "2026-10-19T10:20:00Z",
    ...overrides,
  };
}

export function makeIncident(overrides: Partial<IncidentSummary> = {}): IncidentSummary {
  return {
    id: "i-1",
    category: "fire",
    status: "open",
    gouvernorat_code: 61,
    centroid: { lat: 34.74, lon: 10.76 },
    severity: 79,
    report_count: 2,
    reporter_count: 2,
    opened_at: "2026-10-19T10:00:00Z",
    updated_at: "2026-10-19T10:05:00Z",
    closed_at: null,
    merged_into: null,
    ...overrides,
  };
}

export function makeIncidentDetail(overrides: Partial<IncidentDetail> = {}): IncidentDetail {
  return {
    ...makeIncident(overrides),
    reports: [
      makeReport({ id: "r-1", incident_id: "i-1", priority_score: 79 }),
      makeReport({ id: "r-2", tracking_code: "EH-26-61-0004822", incident_id: "i-1", priority_score: 45 }),
    ],
    timeline: [
      { at: "2026-10-19T10:00:00Z", kind: "created", actor: "ehimaya-staff:u-1", payload: { report_id: "r-1" } },
      {
        at: "2026-10-19T10:05:00Z",
        kind: "report_linked",
        actor: "ehimaya-staff:u-1",
        payload: { report_id: "r-2", via: "suggestion" },
      },
    ],
    ...overrides,
  };
}

export const AI_SETTINGS: AiSettings = {
  priority: {
    weights: { severity: 35, lives: 25, casualties: 10, reporters: 10, credibility: 10, sensitive_sites: 5, weather: 5 },
    category_severity: {
      sos: 0.9,
      fire: 0.8,
      flood: 0.75,
      traffic_accident: 0.6,
      drowning: 0.9,
      landslide: 0.7,
      chemical_leak: 0.85,
      medical: 0.7,
      other: 0.3,
    },
    suggestion_min_confidence: 0.7,
  },
  grouping: {
    window_min: 60,
    radius_m: {
      sos: 300,
      fire: 500,
      flood: 2000,
      traffic_accident: 200,
      drowning: 500,
      landslide: 1000,
      chemical_leak: 1000,
      medical: 100,
      other: 300,
    },
    semantic_min_similarity: 0.88,
    semantic_radius_m: 5000,
    semantic_window_min: 180,
  },
};

export const AI_STATUS_READY: AiStatus = {
  configured: true,
  capabilities: {
    transcribe: { ready: true, model: "faster-whisper-large-v3", detail: null },
    translate_fr: { ready: true, model: "opus-mt-fr-ar", detail: null },
    translate_en: { ready: true, model: "opus-mt-en-ar", detail: null },
    embed: { ready: true, model: "e5-base", detail: null },
    extract: { ready: true, model: "qwen3:8b", detail: null },
  },
};

/** Unsigned JWT with the given claims (the dashboard never verifies signatures). */
export function fakeJwt(claims: Record<string, unknown>): string {
  const enc = (o: unknown) =>
    btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(o))))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${enc({ alg: "none", typ: "JWT" })}.${enc(claims)}.sig`;
}
