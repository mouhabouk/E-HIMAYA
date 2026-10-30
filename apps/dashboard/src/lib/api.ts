/**
 * Fetch wrapper for the e-Himaya API: adds the bearer token, retries once after a token renewal on 401,
 * and turns every failure into an ApiError carrying a stable machine code (contract `detail` codes).
 */

/** Machine codes the dashboard knows how to translate (`errors.<code>` in the i18n files). */
export const ERROR_CODES = [
  "authentication_required",
  // Phase 10 §1: the token does not prove a second factor, or its session was revoked.
  "mfa_required",
  "session_revoked",
  "account_suspended",
  "forbidden",
  "no_scope",
  "not_found",
  "invalid_transition",
  "invalid_filter",
  "incident_not_open",
  "no_suggestion",
  "not_in_incident",
  "suggestion_outdated",
  "incident_id_required",
  "same_incident",
  "national_scope_required",
  // Institutions (phase 4 §9, §11).
  "insufficient_role",
  "reason_required",
  "invalid_valid_until",
  "org_not_found",
  "org_not_active",
  "document_not_found",
  "incomplete",
  "signing_key_missing",
  "certificate_outdated",
  "realm_not_allowed",
  "version_conflict",
  // Operations, volunteers, notifications and safety tips (phase 5 §11).
  "level_not_allowed",
  "out_of_scope",
  "already_acknowledged",
  // Phase 10 §5.1: an alert is published by a second person (or alone with an emergency reason).
  "second_reviewer_required",
  "unit_in_use",
  "label_taken",
  "resource_in_history",
  "resource_busy",
  "incident_without_location",
  "invalid_classification",
  "assignments_active",
  "eta_required",
  "invalid_skill",
  "volunteer_not_approved",
  "callout_closed",
  "no_volunteer_available",
  "invalid_area",
  "invalid_gouvernorat",
  "invalid_user",
  "user_not_found",
  "ambiguous_email",
  "invalid_expiry",
  "severity_category_expiry_required",
  "topic_and_audience_required",
  "kind_change",
  "not_draft",
  "not_published",
  "suspended_by_level",
  "translation_missing",
  // Live streams (phase 6 §2, §4).
  "stream_not_active",
  // Weather, forecast, decision support and telephony (phase 7).
  "suggestion_not_pending",
  "assistant_unavailable",
  "transfer_disabled",
  "invalid_number",
  "no_active_call",
  "softphone_not_registered",
  "telephony_unavailable",
  "forecast_unavailable",
  // Analytics, reports library, national memory and rewards (phase 8).
  "invalid_period",
  "period_too_long",
  "invalid_filters",
  "incident_required",
  "scenario_required",
  "unknown_resource",
  "no_capacity",
  "invalid_recipients",
  "invalid_cron",
  "report_not_ready",
  "entry_in_review",
  "entry_archived",
  "entry_published_once",
  "self_review_forbidden",
  "note_required",
  "rule_exists",
  "default_rule",
  "invalid_subject",
  "duplicate_nomination",
  "same_reviewer",
  "not_eligible",
  "already_revoked",
  "invalid_rule",
  "invalid_evidence",
  "nothing_to_revoke",
  // Central and regional rooms, settings, break-glass, accounts (phase 9).
  "action_not_allowed",
  "anon_quota_exhausted",
  "claim_required",
  "already_claimed",
  "not_claimable",
  "referral_pending",
  "referral_not_pending",
  "geo_not_pending",
  "field_action_regional_only",
  "possible_duplicate",
  "participant_active",
  "request_not_pending",
  "resource_not_owned",
  "invalid_setting",
  "requires_formal_approval",
  "breakglass_justification_required",
  "invalid_target",
  "breakglass_self_review",
  "already_reviewed",
  "role_not_grantable",
  "self_edit",
  "identity_provider_error",
  "username_taken",
  // Map data layers (phase B1).
  "key_taken",
  "file_too_large",
  "empty_file",
  "format_unknown",
  "required_columns_missing",
  "too_many_rows",
  "too_many_columns",
  "json_invalid",
  "json_not_array",
  "geojson_not_collection",
  "xlsx_unreadable",
  "not_a_preview",
  "preview_expired",
  "layer_changed",
  "not_last_import",
  "duplicate_id",
  "outside_tunisia",
  // Map layers managed by the administrator (phase L1a).
  "crs_unsupported",
  "kml_invalid",
  "shp_incomplete",
  "shp_invalid",
  "gpkg_invalid",
  "gpkg_no_features",
  "zip_unreadable",
  "layer_deleted",
  "group_not_found",
  "group_not_empty",
  "group_kept",
  "group_sensitivity_mismatch",
  "icon_unknown",
  "tone_unknown",
  // Satellite background (phase R).
  "basemap_url_https",
  "basemap_url_placeholders",
  "basemap_key_unused",
  "basemap_key_missing",
  // Phase PL1: intervention plans by hazard.
  "hazard_unknown",
  "hazard_only_for_plans",
  "viewer_pdf_only",
  // Phase PL2: daily, weekly and monthly programmes.
  "period_not_found",
  "period_exists",
  "period_not_draft",
  "no_items",
  "period_locked",
  "approved_head_only",
  "date_outside_period",
  "hours_reversed",
  "plan_not_found",
  "too_many_items",
  "no_previous_period",
  "period_not_approved",
  "not_due_yet",
  "item_not_found",
  "template_not_found",
  "template_name_taken",
  "template_mismatch",
  // Phase R1: the resources register.
  "counts_only",
  "category_unknown",
  "category_inactive",
  "category_taken",
  "category_not_found",
  "family_mismatch",
  "spec_unknown",
  "spec_invalid",
  "unit_not_found",
  "vehicle_not_found",
  "stock_not_found",
  "stock_exists",
  "agent_not_found",
  "matricule_taken",
  "skill_level_invalid",
  "entity_required",
  "import_has_errors",
  "file_too_many_rows",
  "not_deleted",
  "already_deleted",
  "merge_target_invalid",
  "name_required",
  "cannot_move",
  "text_required",
  "rate_limited",
  "validation_error",
  "bad_request",
  "conflict",
  "server_error",
  "idp_unavailable",
  "network_error",
  // Phase B2: personal safety.
  "feature_off",
  "no_medical_file",
  "invalid_phone",
  "unknown",
  // The medical committee (design §11).
  "self_appointment",
  "committee_full",
  "not_civil_protection_doctor",
  "not_committee_member",
  // The counter of a regional administration (phase P3a).
  "invalid_code",
  "invalid_stamp_date",
  "place_required",
  "certificate_not_valid",
  "photo_too_large",
  "unsupported_media_type",
  // Prevention visits (phase P3b).
  "visit_open",
  "invalid_scheduled_on",
  "invalid_inspected_on",
  "unknown_item",
  "finding_detail_required",
  "reservations_required",
  "reservations_not_allowed",
  "invalid_due_on",
  "reservation_text_required",
  "reservation_lifted",
  "invalid_year",
  // Coastal safety and incident hospitals (phase L1b).
  "layer_not_found",
  "beach_not_found",
  "alert_not_found",
  "rule_unknown",
  "rule_invalid",
  "national_only",
  "settings_missing",
  "hospital_not_offered",
  // Seasonal programmes (phase L2).
  "code_taken",
  "dates_reversed",
  "programme_closed",
  "cancel_instead",
  "programme_not_draft",
  "no_points",
  "not_live",
  "ref_taken",
  "point_not_found",
  "follow_up_only",
  "nothing_to_change",
  "close_instead",
  "revision_not_found",
  "bad_coordinates",
  "file_format",
  "file_encoding",
  "file_unreadable",
  "file_sheet_missing",
  "file_schema",
  "file_too_many_points",
  // Disaster and crisis axes (phase L3).
  "axis_not_found",
  "axis_closed",
  "incident_not_found",
  "incident_not_attachable",
  "incident_out_of_axis",
  "incident_in_other_axis",
  "incident_not_attached",
  "close_the_national_axis",
  "gouvernorats_required",
  "gouvernorat_required",
  "request_decided",
  "request_not_found",
  "executor_name_required",
  "due_in_past",
  "directive_overridden",
  "directive_not_found",
  "sitrep_sent",
  "sitrep_not_found",
  "shelter_not_found",
  "evacuation_not_found",
  "need_not_found",
  "occupants_over_capacity",
  // Phase L4 §8: the administrator's rules.
  "feature_hidden",
  "ceiling",
  "self_lockout",
  "unknown_feature",
  "unknown_role",
  "user_rule_has_no_gouvernorat",
  // Phase L4 §3 and §5: the decision window and its delegations.
  "window_delegation_required",
  "delegate_not_allowed",
  "event_out_of_scope",
  "unknown_event",
  "self_delegation",
  "already_full_view",
  "account_not_found",
  "delegation_closed",
  "two_gouvernorats_required",
  "too_many_saved",
  "query_too_long",
  "no_words",
  // Phase N: reports entered by a room, the disaster view.
  "outside_gouvernorat",
  "outside_tunisia",
  "invalid_selection",
  // Phase L5a: the digital dry run.
  "already_withdrawn",
  "not_a_draft",
  "not_approved",
  "not_now",
  "not_over",
  "not_participating",
  "not_running",
  "not_started",
  "not_submitted",
  "resource_not_free",
  "too_many_active",
  "not_the_evaluator",
  "gouvernorat_not_in_drill",
  "inconsistent_results",
  "no_evaluator",
  "no_injects",
  "offset_after_end",
  "resources_need_dispatch",
  "too_many_injects",
  "unknown_kind",
  // Phase R3: transfers between gouvernorats, equipment carried by a vehicle.
  "same_gouvernorat",
  "transfer_pending",
  "transfer_not_found",
  "transfer_decided",
  "transfer_outdated",
  "unit_not_in_gouvernorat",
  // Phase R4b: a JSON file and the mapping of its columns.
  "file_json_shape",
  "mapping_invalid",
  "mapping_duplicate",
  "profile_name_taken",
  "sensor_code_taken",
  "tower_code_taken",
  "threshold_out_of_range",
  "outside_local_network",
  "profile_not_found",
  "vehicle_not_in_unit",
  // L5 (AI2): the task list read from an intervention plan.
  "plan_reading_off",
  "suggestion_gone",
  "suggestions_off",
  "plan_not_offered",
  "checklist_approved",
  "reading_in_progress",
  "checklist_not_in_review",
  "task_not_found",
  "task_required",
  "too_many_tasks",
  "tasks_not_reviewed",
  "checklist_empty",
  "model_changed",
  "model_not_found",
  "model_not_trained",
  "checklist_not_approved",
  "task_deleted",
  // AI5a: the commander's assistant.
  "commander_off",
  "already_decided",
  "invalid_action_index",
  "nothing_modified",
  // AI5b: the commander and the voice messages.
  "commander_only",
  "transcription_unavailable",
  "audio_undecodable",
  "nothing_heard",
  "audio_too_long",
  "media_too_large",
  "voice_not_found",
  "voice_already_sent",
  // The training centre (docs/learning.md).
  "training_in_progress",
  "report_not_final",
  "report_without_text",
  "not_waiting_trainer",
  // SNACR and the strategies menu (docs/phase-s/design-s.md).
  "alias_empty",
  "alias_exists",
  "body_or_link_required",
  "delegation_not_in_gouvernorat",
  "no_dataset",
  "plan_not_draft",
  "years_not_loaded",
  "file_columns_missing",
  // The record of a mission (docs/phase-s/design-s2.md).
  "time_needs_previous",
  "time_without_zone",
  "time_in_future",
  "times_out_of_order",
  "mission_too_long",
  "return_before_departure",
  "consumable_unknown",
  "consumable_out_of_range",
  "assignment_cancelled",
  "record_closed",
  "time_required",
  "correction_reason_required",
] as const;
export type ErrorCode = (typeof ERROR_CODES)[number];

/**
 * Free-text `detail` values the API emits today that are not machine codes yet
 * (services/api/app/core/security.py). Mapped here so they are never shown raw.
 */
const DETAIL_ALIASES: Readonly<Record<string, ErrorCode>> = {
  "staff account has no geographic scope": "no_scope",
  "identity provider unavailable": "idp_unavailable",
  "invalid token": "authentication_required",
  "authentication required": "authentication_required",
  "insufficient role": "forbidden",
  invalid_bbox: "invalid_filter",
  invalid_cursor: "invalid_filter",
  invalid_status: "invalid_filter",
  invalid_category: "invalid_filter",
  unknown_gouvernorat: "invalid_filter",
  "unknown gouvernorat": "not_found",
  "unknown issuer": "authentication_required",
  "Not authenticated": "authentication_required",
  "Not Found": "not_found",
};

function codeFromStatus(status: number): ErrorCode {
  if (status === 400) return "bad_request";
  if (status === 401) return "authentication_required";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation_error";
  if (status === 429) return "rate_limited";
  if (status === 503 || status >= 500) return "server_error";
  return "unknown";
}

export function errorCodeFrom(status: number, detail: unknown): ErrorCode {
  if (typeof detail === "string") {
    if ((ERROR_CODES as readonly string[]).includes(detail)) return detail as ErrorCode;
    const alias = DETAIL_ALIASES[detail];
    if (alias) return alias;
  }
  return codeFromStatus(status);
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly detail: unknown;
  readonly retryAfterS: number | null;
  /** Whole JSON error body: some errors carry more than `detail` (phase 9: `already_claimed`, `possible_duplicate`). */
  readonly body: Record<string, unknown> | null;

  constructor(
    status: number,
    code: ErrorCode,
    detail: unknown = null,
    retryAfterS: number | null = null,
    body: Record<string, unknown> | null = null,
  ) {
    super(`API error ${status}: ${code}`);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.retryAfterS = retryAfterS;
    this.body = body;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

/** i18n key for any thrown value. */
export function errorMessageKey(e: unknown): `errors.${ErrorCode}` {
  if (isApiError(e)) return `errors.${e.code}`;
  if (e instanceof TypeError) return "errors.network_error";
  return "errors.unknown";
}

export type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[];

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, QueryValue>;
  body?: unknown;
  /** A file sent as the request body as it is (map layer imports); `body` is ignored. */
  rawBody?: Blob;
  /** The type sent with `rawBody` (a recording, AI5b); `application/octet-stream` when left out. */
  rawType?: string;
  signal?: AbortSignal;
  /** Skip the Authorization header (public endpoints). */
  anonymous?: boolean;
}

export interface TokenSource {
  /** Current access token, or null when signed out. */
  getAccessToken(): string | null;
  /** Renew the access token; resolves with the new token or null when renewal is impossible. */
  renew(): Promise<string | null>;
  /**
   * The API refused the session itself (phase 10 §1): `mfa_required` (sign in again with the second factor) or
   * `session_revoked` (signed out by an administrator or from another device). Renewing the token cannot help.
   */
  rejected?(reason: "mfa_required" | "session_revoked"): void;
}

export interface ApiClient {
  request<T>(path: string, options?: RequestOptions): Promise<T>;
  /**
   * Same authentication, renewal and error mapping as `request`, but resolves with the successful raw Response
   * (binary downloads, redirects to pre-signed links).
   */
  requestRaw(path: string, options?: RequestOptions & { accept?: string }): Promise<Response>;
  /** The absolute address of an API path (map tiles fetched by the map library itself). */
  resolve?(path: string): string;
}

export function buildUrl(baseUrl: string, path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
  if (query) {
    for (const [key, raw] of Object.entries(query)) {
      if (raw === undefined || raw === null || raw === "") continue;
      if (Array.isArray(raw)) {
        if (raw.length === 0) continue;
        url.searchParams.set(key, raw.join(","));
      } else {
        url.searchParams.set(key, String(raw));
      }
    }
  }
  return url.toString();
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return seconds;
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, Math.round((date - Date.now()) / 1000));
}

async function readBody(response: Response): Promise<Record<string, unknown> | null> {
  try {
    const body: unknown = await response.json();
    return body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function createApiClient(
  baseUrl: string,
  tokens: TokenSource,
  fetchImpl: typeof fetch = (...args) => globalThis.fetch(...args),
): ApiClient {
  async function send(
    url: string,
    options: RequestOptions & { accept?: string },
    token: string | null,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: options.accept ?? "application/json" };
    if (token && !options.anonymous) headers.Authorization = `Bearer ${token}`;
    let body: string | Blob | undefined;
    if (options.rawBody !== undefined) {
      headers["Content-Type"] = options.rawType ?? "application/octet-stream";
      body = options.rawBody;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
    try {
      return await fetchImpl(url, { method: options.method ?? "GET", headers, body, signal: options.signal });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new ApiError(0, "network_error", null);
    }
  }

  async function requestRaw(path: string, options: RequestOptions & { accept?: string } = {}): Promise<Response> {
    const url = buildUrl(baseUrl, path, options.query);
    let response = await send(url, options, tokens.getAccessToken());
    if (response.status === 401 && !options.anonymous) {
      const detail = (await readBody(response.clone()))?.detail;
      if (detail === "mfa_required" || detail === "session_revoked") {
        tokens.rejected?.(detail);
      } else {
        const renewed = await tokens.renew().catch(() => null);
        if (renewed) response = await send(url, options, renewed);
      }
    }
    if (!response.ok) {
      const body = await readBody(response);
      const detail = body && "detail" in body ? body.detail : null;
      throw new ApiError(
        response.status,
        errorCodeFrom(response.status, detail),
        detail,
        parseRetryAfter(response.headers.get("Retry-After")),
        body,
      );
    }
    return response;
  }

  return {
    requestRaw,
    resolve: (path: string) => buildUrl(baseUrl, path),
    async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
      const response = await requestRaw(path, options);
      if (response.status === 204) return undefined as T;
      return (await response.json()) as T;
    },
  };
}
