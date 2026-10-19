import { createContext, useContext, type ReactNode } from "react";
import type { AuthService } from "../auth/authService";
import type { PortalApi } from "../lib/portalApi";

export interface Services {
  auth: AuthService;
  api: PortalApi;
  /** tus creation endpoint for documents. */
  tusEndpoint: string;
  mapStyleUrl: string | null;
  /** fetch used by the tus client (injected in tests). */
  fetchImpl?: typeof fetch;
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
