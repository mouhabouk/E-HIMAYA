#!/bin/sh
# ء-حماية / e-Himaya — MediaMTX path hooks → API (docs/api/phase-6-contract.md §3, docs/streaming.md).
# Called by MediaMTX (runOnAvailable / runOnUnavailable / runOnRecordSegmentComplete) as
#   sh /hooks/hook.sh ready|not_ready|segment_complete
# with MTX_PATH, MTX_SOURCE_TYPE, MTX_SOURCE_ID, MTX_SEGMENT_PATH, MTX_SEGMENT_DURATION from MediaMTX and
# MEDIAMTX_HOOK_TOKEN / EHIMAYA_HOOK_URL from the container environment. busybox sh + wget only (Alpine image).
# A lost call is not fatal: the API expires streams that never went live, ends overlong ones, and its worker picks up
# segments left on the recordings volume (orphan scan).
set -u

event="${1:-}"
case "$event" in
  ready | not_ready | segment_complete) ;;
  *) echo "hook: unknown event '$event'" >&2; exit 2 ;;
esac

url="${EHIMAYA_HOOK_URL:-http://api:8000/internal/mediamtx/hooks}"
token="${MEDIAMTX_HOOK_TOKEN:-}"
if [ -z "$token" ]; then
  echo "hook: MEDIAMTX_HOOK_TOKEN is not set" >&2
  exit 1
fi

# Values come from MediaMTX (path names are limited to live/<uuid> by the paths regex, segment paths are built from
# recordPath): anything that would need JSON escaping is refused rather than escaped.
safe() {
  case "$1" in
    *[!A-Za-z0-9._:/@+-]*) return 1 ;;
  esac
  return 0
}

for value in "${MTX_PATH:-}" "${MTX_SOURCE_TYPE:-}" "${MTX_SOURCE_ID:-}" "${MTX_SEGMENT_PATH:-}"; do
  safe "$value" || { echo "hook: refusing a value that would need escaping" >&2; exit 1; }
done

field() { # name value -> ,"name":"value" (nothing when empty)
  [ -z "$2" ] || printf ',"%s":"%s"' "$1" "$2"
}

path="${MTX_PATH:-}"
[ -n "$path" ] || { echo "hook: MTX_PATH is not set" >&2; exit 1; }

body="{\"event\":\"$event\",\"path\":\"$path\""
if [ "$event" = "segment_complete" ]; then
  body="$body$(field segment_path "${MTX_SEGMENT_PATH:-}")"
  duration="${MTX_SEGMENT_DURATION:-}"
  case "$duration" in
    "" | *[!0-9.]*) ;;
    *) body="$body,\"segment_duration_s\":$duration" ;;
  esac
else
  body="$body$(field source_type "${MTX_SOURCE_TYPE:-}")$(field source_id "${MTX_SOURCE_ID:-}")"
fi
body="$body}"

attempt=1
while [ "$attempt" -le 5 ]; do
  if wget -q -O /dev/null -T 5 \
      --header "Content-Type: application/json" \
      --header "X-Hook-Token: $token" \
      --post-data "$body" "$url" 2>/dev/null; then
    exit 0
  fi
  sleep "$attempt"
  attempt=$((attempt + 1))
done
echo "hook: $event for $path not delivered after 5 attempts" >&2
exit 1
