FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN useradd --system --uid 10001 --home /app ehimaya

# Text shaping and fonts for the certificate PDFs (WeasyPrint): Arabic and Latin from Noto.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN python - <<'PY' > /tmp/req.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml","rb"))["project"]["dependencies"]))
PY
RUN pip install -r /tmp/req.txt

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
