# Gateway of the sensors (L5b, docs/sensor-gateway.md): runs on the MediaMTX server of the local network. Python
# standard library only, so the image holds nothing but the interpreter and the gateway.
# Base image pinned by digest (tag kept for readability); Dependabot proposes the updates.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN useradd --system --uid 10001 --home /app ehimaya \
 && mkdir /data && chown ehimaya:ehimaya /data

COPY gateway ./gateway

ENV GATEWAY_QUEUE=/data/queue.sqlite3
VOLUME ["/data"]
USER ehimaya
EXPOSE 8088
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8088/health').status==200 else 1)"]
CMD ["python", "-m", "gateway", "serve"]
