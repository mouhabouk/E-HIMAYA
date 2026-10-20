# ء-حماية / e-Himaya — central dashboard (staff), production image: static files served by Caddy as an unprivileged user,
# with a Content-Security-Policy computed from the build configuration (infra/web/csp.mjs).
#   docker build --build-context web=infra/web --build-arg VITE_API_BASE_URL=https://api.example.tn ... apps/dashboard
# infra/compose.prod.yml passes every argument. Base images pinned by digest; Dependabot proposes the updates.
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Public configuration baked into the bundle (see .env.example), plus the origins only the CSP needs.
ARG VITE_API_BASE_URL \
    VITE_OIDC_ISSUER \
    VITE_OIDC_CLIENT_ID \
    VITE_MAP_STYLE_URL
ARG CSP_MEDIA_SRC= CSP_MAP_SRC= CSP_STREAM_SRC= CSP_TELEPHONY_SRC=
# The softphone (phase 7) needs the microphone on the dashboard's own origin.
ARG CSP_MICROPHONE=self
RUN npm run build && find dist -name '*.map' -delete
COPY --from=web csp.mjs /tmp/csp.mjs
RUN node /tmp/csp.mjs dist /tmp/csp.caddy

FROM caddy:2.11-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
COPY --from=web Caddyfile /etc/caddy/Caddyfile
COPY --from=build /tmp/csp.caddy /etc/caddy/csp.caddy
COPY --from=build /app/dist /srv
ENV XDG_CONFIG_HOME=/tmp/caddy XDG_DATA_HOME=/tmp/caddy
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO /dev/null http://127.0.0.1:8080/healthz || exit 1
