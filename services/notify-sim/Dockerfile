# ┏━━ SIMULATION ━━ container of the channels simulator (FCM HTTP v1 + OAuth, Tunisian SMS gateway), dev/test only
# ┃ PRODUCTION: never build or deploy this image; remove the notify-sim service from infra/compose.yml and set the
# ┃   API's FCM_SERVICE_ACCOUNT, FCM_API_URL, SMS_HTTP_URL, SMS_HTTP_TOKEN (docs/api/notify-sim.md).
# ┗━━━━━━━━━━━━━━━━
# Base images pinned by digest (tag kept for readability); Dependabot proposes the updates.
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

# Dependencies exactly as locked in uv.lock (hashes checked), without the dev group, into /opt/venv.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
WORKDIR /app

# Same uid as the API image (10001): the API reads the generated service account from the shared volume.
RUN useradd --system --uid 10001 --home /app ehimaya \
 && mkdir /data && chown ehimaya:ehimaya /data

COPY --from=deps /opt/venv /opt/venv

COPY app ./app

ENV SIM_DATA_DIR=/data
VOLUME ["/data"]
USER ehimaya
EXPOSE 8090
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/healthz').status==200 else 1)"
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8090", "--no-server-header", "--no-access-log"]
