import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { createOidcAuthService } from "./auth/authService";
import { config } from "./config";
import { createI18n } from "./i18n";
import { createApiClient } from "./lib/api";
import { staffApi } from "./lib/staffApi";
import "./styles/global.css";

const auth = createOidcAuthService({ issuer: config.oidcIssuer, clientId: config.oidcClientId });
const api = staffApi(createApiClient(config.apiBaseUrl, auth));
const i18n = createI18n();

const root = document.getElementById("root");
if (!root) throw new Error("#root missing");

createRoot(root).render(
  <StrictMode>
    <App services={{ auth, api, liveUrl: config.liveUrl, mapStyleUrl: config.mapStyleUrl }} i18n={i18n} />
  </StrictMode>,
);
