#!/bin/sh
# DAST before a release (phase 10 §3): OWASP ZAP API scan of a running e-Himaya stack, driven by the exported
# OpenAPI document (docs/api/openapi.json), with a staff token so the staff endpoints are scanned too.
#
#   ZAP_TARGET=https://api.example.tn ZAP_TOKEN=<staff access token> infra/security/zap/run.sh
#
# Never against production with real data: use the staging stack. The HTML and JSON reports land in
# docs/security/zap-<date>.{html,json}; review them and record the decisions in docs/security/asvs-l2.md.
set -eu

: "${ZAP_TARGET:?set ZAP_TARGET (base URL of the API under test)}"
: "${ZAP_TOKEN:?set ZAP_TOKEN (a staff access token with MFA, valid for the scan)}"
IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:2.16.1}"
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
OUT="$REPO/docs/security"
STAMP=$(date -u +%Y%m%d)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# The OpenAPI document, with the server set to the target.
python3 - "$REPO/docs/api/openapi.json" "$ZAP_TARGET" "$WORK/openapi.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
doc["servers"] = [{"url": sys.argv[2]}]
json.dump(doc, open(sys.argv[3], "w", encoding="utf-8"))
PY
cp "$HERE/rules.tsv" "$WORK/rules.tsv"
chmod -R a+rwX "$WORK"

docker run --rm -v "$WORK:/zap/wrk:rw" "$IMAGE" zap-api-scan.py \
  -t /zap/wrk/openapi.json -f openapi \
  -c rules.tsv \
  -r "zap-$STAMP.html" -J "zap-$STAMP.json" \
  -z "-config replacer.full_list(0).description=auth \
      -config replacer.full_list(0).enabled=true \
      -config replacer.full_list(0).matchtype=REQ_HEADER \
      -config replacer.full_list(0).matchstr=Authorization \
      -config replacer.full_list(0).regex=false \
      -config replacer.full_list(0).replacement=Bearer\ $ZAP_TOKEN" \
  || status=$?
mkdir -p "$OUT"
cp "$WORK/zap-$STAMP.html" "$WORK/zap-$STAMP.json" "$OUT/" 2>/dev/null || true
echo "reports: docs/security/zap-$STAMP.html and .json (exit ${status:-0}: 0 clean, 1 failures, 2 warnings)"
exit "${status:-0}"
