# Base images pinned by digest (tag kept for readability); Dependabot proposes the updates (.github/dependabot.yml).
FROM ghcr.io/astral-sh/uv:0.13.3@sha256:bee0a2a458fd956c5df7b8b4c5fed2257b0af34866e3da7b51db0be3acb375d1 AS uv

# Dependencies exactly as locked in uv.lock (hashes checked), without the dev group, into /opt/venv.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
WORKDIR /app

RUN useradd --system --uid 10001 --home /app ehimaya
# Mount point of the terrain model volume (filled by the one-shot "terrain" service, docs/weather-forecast.md).
RUN install -d -o ehimaya -g ehimaya /terrain

# Text shaping and fonts for the certificate PDFs (WeasyPrint): Arabic and Latin from Noto.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

COPY --from=deps /opt/venv /opt/venv

COPY alembic.ini ./
COPY migrations ./migrations
COPY seed ./seed
COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

USER ehimaya
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live').status==200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header", "--no-access-log"]
