# ┏━━ SIMULATION ━━ container of the channels simulator (FCM HTTP v1 + OAuth, Tunisian SMS gateway), dev/test only
# ┃ PRODUCTION: never build or deploy this image; remove the notify-sim service from infra/compose.yml and set the
# ┃   API's FCM_SERVICE_ACCOUNT, FCM_API_URL, SMS_HTTP_URL, SMS_HTTP_TOKEN (docs/api/notify-sim.md).
# ┗━━━━━━━━━━━━━━━━
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Same uid as the API image (10001): the API reads the generated service account from the shared volume.
RUN useradd --system --uid 10001 --home /app ehimaya \
 && mkdir /data && chown ehimaya:ehimaya /data

COPY pyproject.toml ./
RUN python - <<'PY' > /tmp/req.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml","rb"))["project"]["dependencies"]))
PY
RUN pip install -r /tmp/req.txt

COPY app ./app

ENV SIM_DATA_DIR=/data
VOLUME ["/data"]
USER ehimaya
EXPOSE 8090
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/healthz').status==200 else 1)"
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8090", "--no-server-header", "--no-access-log"]
