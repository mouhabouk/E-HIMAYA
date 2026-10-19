/** Runtime configuration, read once from Vite env with development defaults. */

function value(raw: string | undefined, fallback: string): string {
  const v = raw?.trim();
  return v ? v : fallback;
}

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

export interface AppConfig {
  apiBaseUrl: string;
  liveUrl: string;
  oidcIssuer: string;
  oidcClientId: string;
  mapStyleUrl: string | null;
}

export function toWebSocketUrl(apiBaseUrl: string, path: string): string {
  const url = new URL(path, `${stripTrailingSlash(apiBaseUrl)}/`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function loadConfig(env: ImportMetaEnv = import.meta.env): AppConfig {
  const apiBaseUrl = stripTrailingSlash(value(env.VITE_API_BASE_URL, "http://localhost:8000"));
  const style = env.VITE_MAP_STYLE_URL?.trim();
  return {
    apiBaseUrl,
    liveUrl: toWebSocketUrl(apiBaseUrl, "/api/v1/staff/live"),
    oidcIssuer: stripTrailingSlash(value(env.VITE_OIDC_ISSUER, "http://localhost:8080/realms/ehimaya-staff")),
    oidcClientId: value(env.VITE_OIDC_CLIENT_ID, "ehimaya-dashboard"),
    mapStyleUrl: style ? style : null,
  };
}

export const config: AppConfig = loadConfig();
