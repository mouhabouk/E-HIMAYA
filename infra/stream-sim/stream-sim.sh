#!/bin/sh
# ┏━━ SIMULATION ━━ stream-sim (compose profile "sim"): a fake drone/camera for development and demos.
# ┃   Registers a source=sim stream with the API (POST /internal/sim/streams, X-Sim-Token), then publishes a looped
# ┃   sample clip over RTSP to live/<id> with the returned token, so the dashboard, recording, hashing and vision
# ┃   paths run end to end without a phone. Every stream it creates is marked "simulated": true and "[SIM] ".
# ┃ PRODUCTION: never run it (no "sim" profile; APP_ENV=production refuses STREAM_SIM_TOKEN). Real drones and
# ┃   cameras are registered by an ops manager (POST /api/v1/staff/streams) and publish with their own token
# ┃   (docs/streaming.md, "Switching to real cameras and drones").
# ┗━━━━━━━━━━━━━━━━
#
# Clip: SIM_CLIP_URL, verified against SIM_CLIP_SHA256 before use (a mismatch is refused, never played). Default:
# "people-detection.mp4" of intel-iot-devkit/sample-videos, licence CC-BY-4.0 (attribution: Intel Corporation),
# see docs/streaming.md. Without network access the simulator falls back to an ffmpeg test pattern.
# Runs in the MediaMTX "-ffmpeg" image (Alpine: busybox sh, wget, sha256sum, sed; ffmpeg).
set -u

log() { echo "[SIM] $*"; }
fail() { echo "[SIM] ERROR: $*" >&2; exit 1; }

cat <<'BANNER'
┏━━ SIMULATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ stream-sim: simulated camera publishing a looped sample clip ("[SIM]" streams)
┃ PRODUCTION: not used; register real drones/cameras in the dashboard instead
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BANNER

API_URL="${SIM_API_URL:-http://api:8000}"
RTSP_HOST="${SIM_RTSP_HOST:-mediamtx:8554}"
TOKEN="${STREAM_SIM_TOKEN:-}"
LABEL="${SIM_LABEL:-SIM camera}"
GOUVERNORAT="${SIM_GOUVERNORAT_CODE:-11}"
LAT="${SIM_LAT:-36.8065}"
LON="${SIM_LON:-10.1815}"
CLIP_URL="${SIM_CLIP_URL:-}"
CLIP_SHA256="${SIM_CLIP_SHA256:-}"
CLIP_DIR="${SIM_CLIP_DIR:-/clips}"

[ -n "$TOKEN" ] || fail "STREAM_SIM_TOKEN is not set (the API must have the same value)"
case "$LABEL$GOUVERNORAT$LAT$LON" in
  *[\"\\]*) fail "SIM_LABEL / SIM_* values must not contain quotes or backslashes" ;;
esac

# ---------------------------------------------------------------- clip (pinned by SHA-256)
CLIP=""
if [ -n "$CLIP_URL" ]; then
  echo "$CLIP_SHA256" | grep -Eq '^[0-9a-f]{64}$' || fail "SIM_CLIP_SHA256 must be the 64-hex SHA-256 of SIM_CLIP_URL"
  mkdir -p "$CLIP_DIR"
  cached="$CLIP_DIR/$CLIP_SHA256.mp4"
  if [ -f "$cached" ] && echo "$CLIP_SHA256  $cached" | sha256sum -c >/dev/null 2>&1; then
    CLIP="$cached"
    log "clip found in cache ($CLIP_SHA256)"
  else
    log "downloading clip $CLIP_URL"
    if wget -q -T 60 -O "$cached.part" "$CLIP_URL"; then
      if echo "$CLIP_SHA256  $cached.part" | sha256sum -c >/dev/null 2>&1; then
        mv "$cached.part" "$cached"
        CLIP="$cached"
        log "clip verified ($CLIP_SHA256)"
      else
        rm -f "$cached.part"
        fail "clip SHA-256 mismatch: refusing to play $CLIP_URL (check SIM_CLIP_URL / SIM_CLIP_SHA256)"
      fi
    else
      rm -f "$cached.part"
      log "clip download failed: falling back to the ffmpeg test pattern"
    fi
  fi
fi

if [ -n "$CLIP" ]; then
  set -- -re -stream_loop -1 -i "$CLIP"
  log "source: looped clip $CLIP"
else
  set -- -re -f lavfi -i "testsrc2=size=1280x720:rate=15"
  log "source: ffmpeg test pattern"
fi
# H.264 Baseline (plays everywhere: WebRTC/WHEP, HLS, the vision reader); audio dropped (none is needed).
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264; then
  set -- "$@" -an -c:v libx264 -preset veryfast -tune zerolatency -profile:v baseline -pix_fmt yuv420p -g 30 -b:v 1500k
else
  set -- "$@" -an -c:v copy
fi

# ---------------------------------------------------------------- register, publish, repeat
wait_api() {
  i=0
  until wget -q -T 5 -O /dev/null "$API_URL/health/live"; do
    i=$((i + 1))
    [ "$i" -le 60 ] || fail "API not reachable at $API_URL"
    sleep 2
  done
}

register() {
  body="{\"label\":\"$LABEL\",\"gouvernorat_code\":$GOUVERNORAT,\"lat\":$LAT,\"lon\":$LON}"
  response="$(wget -q -T 10 -O - --header "Content-Type: application/json" --header "X-Sim-Token: $TOKEN" \
    --post-data "$body" "$API_URL/internal/sim/streams")" || return 1
  STREAM_ID="$(echo "$response" | sed -n 's/.*"id":"\([0-9a-f-]*\)".*/\1/p')"
  PUBLISH_TOKEN="$(echo "$response" | sed -n 's/.*"publish_token":"\([A-Za-z0-9_-]*\)".*/\1/p')"
  [ -n "$STREAM_ID" ] && [ -n "$PUBLISH_TOKEN" ]
}

while true; do
  wait_api
  if ! register; then
    log "registration refused (is STREAM_SIM_TOKEN the same in the API, and APP_ENV not production?); retry in 15 s"
    sleep 15
    continue
  fi
  log "stream registered: id=$STREAM_ID path=live/$STREAM_ID (dashboard: Live streams)"
  failures=0
  while [ "$failures" -lt 3 ]; do
    started="$(date +%s)"
    log "publishing to rtsp://$RTSP_HOST/live/$STREAM_ID"
    # The token goes in the RTSP password (never logged by MediaMTX or the API, masked below).
    ffmpeg -hide_banner -loglevel warning -nostdin "$@" -f rtsp -rtsp_transport tcp \
      "rtsp://sim:$PUBLISH_TOKEN@$RTSP_HOST/live/$STREAM_ID" 2>&1 |
      while IFS= read -r line; do
        # ffmpeg errors repeat the URL: the token is masked before anything reaches the log.
        printf '[SIM] ffmpeg: %s\n' "$line" | sed "s/$PUBLISH_TOKEN/<token>/g"
      done
    if [ $(($(date +%s) - started)) -lt 20 ]; then
      failures=$((failures + 1))
    else
      failures=0
    fi
    log "publisher stopped; reconnecting in 5 s"
    sleep 5
  done
  # Repeated quick failures: the stream was stopped by staff (token retired) or MediaMTX refuses it. Start over.
  log "giving up on stream $STREAM_ID; registering a new one"
done
