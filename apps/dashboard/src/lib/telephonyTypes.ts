/**
 * Types mirroring docs/api/phase-7-contract.md §4 (telephony, scenarios 1 and 2 of ADR-10). Scenario 1 (default):
 * the operator calls 198 from their own phone; scenario 2: a blind transfer through the SIP trunk, only when the API
 * says it is enabled.
 */

/** The national civil protection number (scenario 0/1). */
export const CIVIL_PROTECTION_NUMBER = "198";

/** `POST /api/v1/staff/telephony/credentials`: short-lived SIP credentials of the operator's WebRTC endpoint. */
export interface SipCredentials {
  ws_url: string;
  sip_uri: string;
  username: string;
  password: string;
  expires_at: string;
  ice_servers: RTCIceServer[];
  /** Scenario 2 is configured (TELEPHONY_TRANSFER_198_ENABLED and a trunk); absent means scenario 1. */
  transfer_198_enabled?: boolean;
  simulated?: boolean;
}

export const CALL_DIRECTIONS = ["inbound", "outbound", "conference"] as const;
export type CallDirection = (typeof CALL_DIRECTIONS)[number];

export const CALL_STATUSES = [
  "queued",
  "ringing",
  "answered",
  "ended",
  "missed",
  "abandoned",
  "transferred",
  "failed",
] as const;
export type CallStatus = (typeof CALL_STATUSES)[number];

/** One `telephony.call` row (`GET /api/v1/staff/calls`). The number is masked for roles without call access. */
export interface StaffCall {
  id: string;
  /** One of CALL_DIRECTIONS (kept open: an unknown value is shown as sent). */
  direction: string;
  caller_number: string | null;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  operator_user_id: string | null;
  operator_name?: string | null;
  queue: string | null;
  /** One of CALL_STATUSES (kept open: an unknown value is shown as sent). */
  status: string;
  report_id: string | null;
  incident_id: string | null;
  tracking_code: string | null;
  recording_media_id: string | null;
  transferred_to: string | null;
  end_reason: string | null;
  simulated?: boolean;
}

export type CallLinkBody = { report_id: string } | { tracking_code: string } | { incident_id: string };

export type DialBody = { number: string } | { report_id: string } | { volunteer_id: string };

/** `POST …/calls/dial`: the API rings the operator's softphone, then bridges the callee. */
export interface DialResult {
  id: string;
  status?: string;
}

export interface Conference {
  room: string;
  join_uri: string;
  started_at?: string | null;
  participants?: number | null;
}

/** Queue state carried by `call.ringing` (all optional: the contract does not fix it). */
export interface QueueInfo {
  name: string | null;
  waiting: number | null;
}

export interface CallFilters {
  status: CallStatus | "";
}
