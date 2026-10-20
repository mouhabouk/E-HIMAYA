import { createContext, useContext, type ReactNode } from "react";
import type { AuthService } from "../auth/authService";
import type { WebSocketFactory } from "../lib/live";
import type { StaffApi } from "../lib/staffApi";
import type { StreamSessionOptions } from "../lib/streamSession";

export interface Services {
  auth: AuthService;
  api: StaffApi;
  liveUrl: string;
  createSocket?: WebSocketFactory;
  mapStyleUrl: string | null;
  /** Live stream viewers (phase 6); defaults to StreamSession (WHEP, then HLS). Tests inject a fake. */
  createStreamSession?: (options: StreamSessionOptions) => StreamSessionLike;
}

export interface StreamSessionLike {
  start(): void;
  stop(): void;
  suspend(): void;
  resume(): void;
  retryNow(): void;
}

const ServicesContext = createContext<Services | null>(null);

export function ServicesProvider({ services, children }: { services: Services; children: ReactNode }) {
  return <ServicesContext value={services}>{children}</ServicesContext>;
}

export function useServices(): Services {
  const s = useContext(ServicesContext);
  if (!s) throw new Error("ServicesProvider missing");
  return s;
}
