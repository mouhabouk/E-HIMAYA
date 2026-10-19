# ء-حماية / e-Himaya — AI inference service.
#   docker build --target runtime -t ehimaya/ai .   the service (no model inside; models are mounted on /models)
#   docker build --target models  -t ehimaya/ai-models .   one-shot job that downloads and converts the models
FROM python:3.12-slim AS base
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
COPY pyproject.toml ./
RUN python - <<'PY' > /tmp/req.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml","rb"))["project"]["dependencies"]))
PY
RUN pip install -r /tmp/req.txt
# GPU servers (NFR-01: 60 s of audio in under 20 s): docker build --build-arg GPU=1 adds the CUDA libraries
# CTranslate2 needs (cuBLAS 12, cuDNN 9). Run with the NVIDIA container toolkit (infra/compose.gpu.yml).
ARG GPU=0
RUN if [ "$GPU" = "1" ]; then pip install nvidia-cublas-cu12==12.9.2.10 nvidia-cudnn-cu12==9.27.0.42; fi
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib
COPY app ./app
# The models are local files: never reach the Hugging Face hub at run time (NFR-10, NFR-11).
ENV HF_HUB_OFFLINE=1 AI_MODELS_DIR=/models
USER ehimaya
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health/live').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--no-server-header", "--no-access-log"]
