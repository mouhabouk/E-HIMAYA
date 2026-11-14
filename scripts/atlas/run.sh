#!/usr/bin/env bash
# Rebuilds the flowchart atlas (Yamen, 2026-11-13) on a local copy of the stack: the dashboard with its tabs and windows,
# the public portal, and the citizen and staff apps (their widget tests, when Flutter is installed), in chapters.
# Standing rule (Yamen, 2026-11-13): the atlas follows development automatically; scripts/refresh-all.sh runs this.
# ATLAS_PREVIOUS=<published index.html> keeps the cards of detail screens an empty local database cannot open.
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
PORTAL_PORT=${ATLAS_PORTAL_PORT:-4175}
ISSUER="http://localhost:$JWKS_PORT/realms/ehimaya-staff"
PUBLIC="http://localhost:$JWKS_PORT/realms/ehimaya-public"
FLUTTER=${FLUTTER:-$(command -v flutter || true)}

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
for realm in ("ehimaya-staff", "ehimaya-public"):
    import os
    os.makedirs(f"{w}/jwks/realms/{realm}/protocol/openid-connect", exist_ok=True)
    open(f"{w}/jwks/realms/{realm}/protocol/openid-connect/certs", "w").write(json.dumps({"keys": [pub]}))
open(f"{w}/jwks/style.json", "w").write(json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#dfe6ee"}}]}))
EOF
(cd "$WORK/jwks" && python3 -m http.server "$JWKS_PORT" >/dev/null 2>&1) &

# 2. The API on the local database, trusting the local issuer only.
(cd "$ROOT/services/api" && OIDC_ISSUERS="$ISSUER,$PUBLIC" API_CORS_ORIGINS="http://localhost:$WEB_PORT,http://localhost:$PORTAL_PORT" BACKGROUND_WORKERS=false \
  .venv/bin/uvicorn app.main:app --port "$API_PORT" >"$WORK/api.log" 2>&1) &

# 3. The dashboard built against it.
(cd "$ROOT/apps/dashboard" && VITE_API_BASE_URL="http://localhost:$API_PORT" VITE_OIDC_ISSUER="$ISSUER" \
  VITE_OIDC_CLIENT_ID=ehimaya-dashboard VITE_MAP_STYLE_URL="http://localhost:$JWKS_PORT/style.json" \
  npx vite build --outDir "$WORK/dist" >"$WORK/build.log" 2>&1)
(cd "$ROOT/apps/dashboard" && npx vite preview --outDir "$WORK/dist" --port "$WEB_PORT" --strictPort >/dev/null 2>&1) &
# 3b. The portal, signed in as a citizen who registers an institution [SIM].
(cd "$ROOT/apps/portal" && VITE_API_BASE_URL="http://localhost:$API_PORT" VITE_OIDC_ISSUER="$PUBLIC" \
  VITE_OIDC_CLIENT_ID=ehimaya-portal VITE_MAP_STYLE_URL="http://localhost:$JWKS_PORT/style.json" \
  npx vite build --outDir "$WORK/portal" >"$WORK/portal-build.log" 2>&1)
(cd "$ROOT/apps/portal" && npx vite preview --outDir "$WORK/portal" --port "$PORTAL_PORT" --strictPort >/dev/null 2>&1) &
ATLAS_KEY="$WORK/key.pem" ATLAS_ISSUER="$PUBLIC" "$PY" -I - >"$WORK/citizen.jwt" <<'EOF'
import os, time, jwt
now = int(time.time())
c = {"iss": os.environ["ATLAS_ISSUER"], "sub": "atlas-citizen", "aud": "ehimaya-api", "azp": "ehimaya-portal", "exp": now + 3 * 3600,
     "iat": now, "name": "سامي بن علي [SIM]", "email": "sami@example.tn", "email_verified": True, "preferred_username": "sami",
     "realm_access": {"roles": ["citizen"]}}
print(jwt.encode(c, open(os.environ["ATLAS_KEY"]).read(), algorithm="RS256", headers={"kid": "atlas"}))
EOF
for _ in $(seq 60); do curl -sf "http://localhost:$API_PORT/health/live" >/dev/null && curl -sf "http://localhost:$WEB_PORT" >/dev/null && break; sleep 1; done

# 4. Inventory, capture, build.
(cd "$ROOT/services/api" && .venv/bin/python ../../scripts/ui_reference/backend_dump.py >"$WORK/backend.json")
python3 "$ROOT/scripts/atlas/inventory.py" --backend "$WORK/backend.json" --out "$WORK/inventory.json"
mkdir -p "$OUT"
ATLAS_KEY="$WORK/key.pem" ATLAS_ISSUER="$ISSUER" ATLAS_PYTHON="$PY" ATLAS_DASHBOARD_URL="http://localhost:$WEB_PORT" \
  node "$ROOT/scripts/atlas/capture.mjs" "$WORK/inventory.json" "$OUT"
mkdir -p "$WORK/portal-cap" "$WORK/mobile"
ATLAS_PORTAL_URL="http://localhost:$PORTAL_PORT" ATLAS_API_URL="http://localhost:$API_PORT" ATLAS_PUBLIC_ISSUER="$PUBLIC" \
  ATLAS_CITIZEN_TOKEN="$WORK/citizen.jwt" node "$ROOT/scripts/atlas/capture_portal.mjs" "$ROOT/scripts/atlas/portal_screens.json" "$WORK/portal-cap"
if [ -n "$FLUTTER" ]; then
  (cd "$ROOT/apps/mobile" && ATLAS_OUT="$WORK/mobile" "$FLUTTER" test test/atlas) || echo "mobile atlas: some captures failed"
else
  echo "mobile atlas skipped: Flutter is not installed (set FLUTTER=/path/to/flutter)"
fi
python3 "$ROOT/scripts/atlas/build.py" "$OUT/capture.json" "$OUT" --portal "$WORK/portal-cap" --mobile "$WORK/mobile" \
  --backend "$WORK/backend.json" ${ATLAS_PREVIOUS:+--previous "$ATLAS_PREVIOUS"}
# 5. The same atlas as a book: atlas.pdf (the shots of cards kept from the previous atlas are read beside it).
python3 "$ROOT/scripts/atlas/pdf.py" "$OUT" ${ATLAS_PREVIOUS:+--shots "$(dirname "$ATLAS_PREVIOUS")"}
