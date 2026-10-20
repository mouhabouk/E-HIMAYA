# ء-حماية / e-Himaya — computer vision service (fire, smoke and person detection).
#   docker build --target runtime -t ehimaya/vision .          the service (no model inside; models are mounted on /models)
#   docker build --target models  -t ehimaya/vision-models .   one-shot job that installs the pinned models (SHA-256)
# Base images pinned by digest (tag kept for readability); Dependabot proposes the updates.
FROM ghcr.io/astral-sh/uv:0.13.3@sha256:bee0a2a458fd956c5df7b8b4c5fed2257b0af34866e3da7b51db0be3acb375d1 AS uv

# Dependencies exactly as locked in uv.lock (hashes checked), without the dev group, into /opt/venv.
# Every runtime dependency ships manylinux wheels (ONNX Runtime, PyAV with its FFmpeg, Pillow): no compiler needed.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# /models belongs to the service user so that a new named volume mounted there is writable by the models job.
RUN useradd --system --uid 10001 --home /app ehimaya && mkdir /models && chown ehimaya:ehimaya /models

# Standard library only: downloads the ONNX files and checks their SHA-256.
FROM base AS models
COPY models/fetch_models.py ./
COPY models/weights ./weights
USER ehimaya
ENTRYPOINT ["python", "fetch_models.py"]
CMD ["--out", "/models"]

FROM base AS runtime
COPY --from=deps /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY app ./app
ENV VISION_MODELS_DIR=/models
USER ehimaya
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/healthz').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--no-server-header", "--no-access-log"]
