import { createContext, useContext, type ReactNode } from "react";
import type { AuthService } from "../auth/authService";
import type { WebSocketFactory } from "../lib/live";
import type { StaffApi } from "../lib/staffApi";

export interface Services {
  auth: AuthService;
  api: StaffApi;
  liveUrl: string;
  createSocket?: WebSocketFactory;
  mapStyleUrl: string | null;
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
