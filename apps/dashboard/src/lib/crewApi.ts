import type { ApiClient } from "./api";
import type { CrewDevice, ShiftRow } from "./crewTypes";

const S = "/api/v1/staff";

export const crewKeys = {
  shifts: ["crew", "shifts"] as const,
  devices: (revoked: boolean) => ["crew", "devices", revoked] as const,
  devicesAll: ["crew", "devices"] as const,
};

/** The room's view of the staff app (phase P4a): teams on duty and the leaders' phones. */
export function crewApi(api: ApiClient) {
  return {
    shifts: (signal?: AbortSignal) => api.request<ShiftRow[]>(`${S}/shifts`, { signal }),
    crewDevices: (revoked: boolean, signal?: AbortSignal) =>
      api.request<CrewDevice[]>(`${S}/crew-devices`, { query: { revoked }, signal }),
    /** Remote wipe: the phone erases everything at its next call; an open shift on it ends. */
    revokeCrewDevice: (id: string) =>
      api.request<CrewDevice>(`${S}/crew-devices/${encodeURIComponent(id)}/revoke`, { method: "POST", body: {} }),
  };
}
