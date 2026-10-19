import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { createOidcAuthService } from "./auth/authService";
import { config } from "./config";
import { createI18n } from "./i18n";
import { createApiClient } from "./lib/api";
import { portalApi } from "./lib/portalApi";
import "./styles/global.css";

const auth = createOidcAuthService({ issuer: config.oidcIssuer, clientId: config.oidcClientId });
const api = portalApi(createApiClient(config.apiBaseUrl, auth));
const i18n = createI18n();

const root = document.getElementById("root");
if (!root) throw new Error("#root missing");

createRoot(root).render(
  <StrictMode>
    <App services={{ auth, api, tusEndpoint: config.tusEndpoint, mapStyleUrl: config.mapStyleUrl }} i18n={i18n} />
  </StrictMode>,
);
