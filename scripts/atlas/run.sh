#!/usr/bin/env bash
# Rebuilds the flowchart atlas of the dashboard (Yamen, 2026-11-13) on a local copy of the stack.
#
#   scripts/atlas/run.sh <out-dir>
#
# Needs: a migrated local database whose URLs are in DATABASE_URL and MIGRATION_DATABASE_URL (and the other API
# variables, as for the API tests), services/api/.venv, apps/dashboard/node_modules and Playwright's Chromium.
# SIMULATION: a throw-away RSA key signs the personas' tokens; the API instance started here trusts only that key
# through a local JWKS. Nothing here talks to Keycloak or to a production API.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:?usage: run.sh <out-dir>}
WORK=$(mktemp -d)
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "$WORK"' EXIT
PY="$ROOT/services/api/.venv/bin/python"
JWKS_PORT=${ATLAS_JWKS_PORT:-8099}; API_PORT=${ATLAS_API_PORT:-8000}; WEB_PORT=${ATLAS_WEB_PORT:-4174}
ISSUER="http://localhost:$JWKS_PORT/realms/ehimaya-staff"

# 1. Local key and JWKS, plus a plain map style (the screenshots do not need tiles).
mkdir -p "$WORK/jwks/realms/ehimaya-staff/protocol/openid-connect"
"$PY" -I - "$WORK" <<'EOF'
import json, sys, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
w = sys.argv[1]
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open(f"{w}/key.pem", "wb").write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
pub = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(k.public_key())); pub.update(kid="atlas", use="sig", alg="RS256")
open(f"{w}/jwks/realms/ehimaya-staff/protocol/openid-connect/certs", "w").write(json.dumps({"keys": [pub]}))
open(f"{w}/jwks/style.json", "w").write(json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#dfe6ee"}}]}))
EOF
(cd "$WORK/jwks" && python3 -m http.server "$JWKS_PORT" >/dev/null 2>&1) &

# 2. The API on the local database, trusting the local issuer only.
(cd "$ROOT/services/api" && OIDC_ISSUERS="$ISSUER" API_CORS_ORIGINS="http://localhost:$WEB_PORT" BACKGROUND_WORKERS=false \
  .venv/bin/uvicorn app.main:app --port "$API_PORT" >"$WORK/api.log" 2>&1) &

# 3. The dashboard built against it.
(cd "$ROOT/apps/dashboard" && VITE_API_BASE_URL="http://localhost:$API_PORT" VITE_OIDC_ISSUER="$ISSUER" \
  VITE_OIDC_CLIENT_ID=ehimaya-dashboard VITE_MAP_STYLE_URL="http://localhost:$JWKS_PORT/style.json" \
  npx vite build --outDir "$WORK/dist" >"$WORK/build.log" 2>&1)
(cd "$ROOT/apps/dashboard" && npx vite preview --outDir "$WORK/dist" --port "$WEB_PORT" --strictPort >/dev/null 2>&1) &
for _ in $(seq 60); do curl -sf "http://localhost:$API_PORT/health/live" >/dev/null && curl -sf "http://localhost:$WEB_PORT" >/dev/null && break; sleep 1; done

# 4. Inventory, capture, build.
(cd "$ROOT/services/api" && .venv/bin/python ../../scripts/ui_reference/backend_dump.py >"$WORK/backend.json")
python3 "$ROOT/scripts/atlas/inventory.py" --backend "$WORK/backend.json" --out "$WORK/inventory.json"
mkdir -p "$OUT"
ATLAS_KEY="$WORK/key.pem" ATLAS_ISSUER="$ISSUER" ATLAS_PYTHON="$PY" ATLAS_DASHBOARD_URL="http://localhost:$WEB_PORT" \
  node "$ROOT/scripts/atlas/capture.mjs" "$WORK/inventory.json" "$OUT"
python3 "$ROOT/scripts/atlas/build.py" "$OUT/capture.json" "$OUT"
