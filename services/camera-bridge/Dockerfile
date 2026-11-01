# Bridge of the fire-detecting cameras of an institution (docs/guides/camera-bridge.md). Python standard library only.
# This image relays the alarms and the heartbeats; the video after an alarm needs ffmpeg, so the native installation
# (systemd, guide §6) is the one that also sends the video.
# Base image pinned by digest (tag kept for readability); Dependabot proposes the updates.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN useradd --system --uid 10001 --home /app ehimaya \
 && mkdir /data && chown ehimaya:ehimaya /data

COPY bridge ./bridge

ENV BRIDGE_CONFIG=/config/bridge.json
VOLUME ["/data"]
USER ehimaya
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/health').status==200 else 1)"]
CMD ["python", "-m", "bridge", "serve"]
