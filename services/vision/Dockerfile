# ء-حماية / e-Himaya — computer vision service (fire, smoke and person detection).
#   docker build --target runtime -t ehimaya/vision .          the service (no model inside; models are mounted on /models)
#   docker build --target models  -t ehimaya/vision-models .   one-shot job that installs the pinned models (SHA-256)
# Base images pinned by digest (tag kept for readability); Dependabot proposes the updates.
FROM ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b AS uv

# Dependencies exactly as locked in uv.lock (hashes checked), without the dev group, into /opt/venv.
# Every runtime dependency ships manylinux wheels (ONNX Runtime, PyAV with its FFmpeg, Pillow): no compiler needed.
FROM python:3.15-slim@sha256:2da676046630d7bf14c6764ae1143dc7fa0377a53f94bf5a642f0b214aca5bce AS deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

FROM python:3.15-slim@sha256:2da676046630d7bf14c6764ae1143dc7fa0377a53f94bf5a642f0b214aca5bce AS base
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
