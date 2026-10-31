#!/bin/sh
# Camera relay (compose profile "camera", review point 25, docs/phase-d/design-d.md §2).
#
# A home or office IP camera such as the TP-Link Tapo C200/C310 offers its picture over RTSP only
# (rtsp://<user>:<password>@<ip>:554/stream1, the "camera account" set in the Tapo app). It cannot publish to
# MediaMTX with a token by itself, so this relay pulls the camera's stream on the local network and publishes it,
# without re-encoding, to the path the API gave when the camera was registered (dashboard «كاميرات المؤسسات»).
# The camera's password stays on this computer: it is never sent to the API.
#
#   CAMERA_RTSP_URL     the camera's own RTSP address (with its camera-account user and password)
#   CAMERA_PUBLISH_URL  the publish address shown once by the dashboard, ending with ?token=<publish token>
#
# Runs in the MediaMTX "-ffmpeg" image (busybox sh and ffmpeg). On a lost connection it waits and starts again.
set -u

[ -n "${CAMERA_RTSP_URL:-}" ] || { echo "camera-relay: CAMERA_RTSP_URL is not set" >&2; exit 1; }
[ -n "${CAMERA_PUBLISH_URL:-}" ] || { echo "camera-relay: CAMERA_PUBLISH_URL is not set" >&2; exit 1; }
case "$CAMERA_PUBLISH_URL" in
  *token=*) ;;
  *) echo "camera-relay: CAMERA_PUBLISH_URL must carry the publish token (?token=...)" >&2; exit 1 ;;
esac

# Logged without the camera's credentials.
SAFE_SOURCE=$(echo "$CAMERA_RTSP_URL" | sed -E 's#//[^@/]*@#//***@#')
echo "camera-relay: $SAFE_SOURCE -> ${CAMERA_PUBLISH_URL%%\?*}"

while true; do
  # -c copy: the camera's H.264 goes through untouched (no CPU load); audio dropped (none is needed).
  ffmpeg -hide_banner -loglevel warning -rtsp_transport tcp -timeout 10000000 -i "$CAMERA_RTSP_URL" \
    -an -c:v copy -f rtsp -rtsp_transport tcp "$CAMERA_PUBLISH_URL"
  echo "camera-relay: stream ended (code $?), retrying in 5 s"
  sleep 5
done
