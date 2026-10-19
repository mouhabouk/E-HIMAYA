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
  oidcIssuer: string;
  oidcClientId: string;
  /** tus creation endpoint, always with a trailing slash (tusd answers relative Location headers). */
  tusEndpoint: string;
  mapStyleUrl: string | null;
}

export function loadConfig(env: ImportMetaEnv = import.meta.env): AppConfig {
  const style = env.VITE_MAP_STYLE_URL?.trim();
  return {
    apiBaseUrl: stripTrailingSlash(value(env.VITE_API_BASE_URL, "http://localhost:8000")),
    oidcIssuer: stripTrailingSlash(value(env.VITE_OIDC_ISSUER, "http://localhost:8080/realms/ehimaya-public")),
    oidcClientId: value(env.VITE_OIDC_CLIENT_ID, "ehimaya-portal"),
    tusEndpoint: `${stripTrailingSlash(value(env.VITE_TUS_ENDPOINT, "http://localhost:1080/api/v1/uploads/"))}/`,
    mapStyleUrl: style ? style : null,
  };
}

export const config: AppConfig = loadConfig();
