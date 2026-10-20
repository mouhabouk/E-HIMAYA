# ء-حماية / e-Himaya — AI inference service.
#   docker build --target runtime -t ehimaya/ai .   the service (no model inside; models are mounted on /models)
#   docker build --target models  -t ehimaya/ai-models .   one-shot job that downloads and converts the models
# Base images pinned by digest (tag kept for readability); Dependabot proposes the updates.
FROM ghcr.io/astral-sh/uv:0.13.3@sha256:bee0a2a458fd956c5df7b8b4c5fed2257b0af34866e3da7b51db0be3acb375d1 AS uv

# Dependencies exactly as locked in uv.lock (hashes checked), without the dev group, into /opt/venv.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --system --uid 10001 --home /app ehimaya

FROM base AS models
COPY models/requirements.txt /tmp/requirements.txt
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements.txt
COPY models/fetch_models.py ./
ENV HF_HOME=/tmp/hf
ENTRYPOINT ["python", "fetch_models.py"]

FROM base AS runtime
COPY --from=deps /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# GPU servers (NFR-01: 60 s of audio in under 20 s): docker build --build-arg GPU=1 adds the CUDA libraries
# CTranslate2 needs (cuBLAS 12, cuDNN 9). Run with the NVIDIA container toolkit (infra/compose.gpu.yml).
ARG GPU=0
RUN if [ "$GPU" = "1" ]; then pip install --python /opt/venv/bin/python nvidia-cublas-cu12==12.9.2.10 nvidia-cudnn-cu12==9.27.0.42; fi
ENV LD_LIBRARY_PATH=/opt/venv/lib/python3.12/site-packages/nvidia/cublas/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cudnn/lib
COPY app ./app
# The models are local files: never reach the Hugging Face hub at run time (NFR-10, NFR-11).
ENV HF_HUB_OFFLINE=1 AI_MODELS_DIR=/models
USER ehimaya
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health/live').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--no-server-header", "--no-access-log"]
