#!/bin/sh
# ء-حماية / e-Himaya — one-shot preparation of the routing graph (compose service "routing-prepare", profile "routing").
#
# Downloads the OpenStreetMap extract of Tunisia (Geofabrik, data © OpenStreetMap contributors, ODbL 1.0), refuses it
# unless its SHA-256 equals ROUTING_OSM_SHA256, then builds the Valhalla tiles into the "routingdata" volume:
#   /data/extract.osm.pbf            the verified extract (kept to rebuild without downloading again)
#   /data/build-<sha256>/            tiles.tar, admins.sqlite, valhalla.json of that extract
#   /data/current -> build-<sha256>  switched atomically once the build succeeded (the service reads current/)
# Re-running with the same checksum does nothing; a new checksum builds next to the old graph, then switches.
# Docs: docs/decision-support.md ("Routing engine").
set -eu

DATA=/data
URL="${ROUTING_OSM_URL:?set ROUTING_OSM_URL (a dated Geofabrik extract, e.g. .../africa/tunisia-260901.osm.pbf)}"
SHA="${ROUTING_OSM_SHA256:?set ROUTING_OSM_SHA256 (sha256 of that extract, see docs/decision-support.md)}"
THREADS="${ROUTING_BUILD_THREADS:-2}"

case "$SHA" in
  *[!0-9a-f]* | "") echo "ROUTING_OSM_SHA256 must be 64 lowercase hex characters" >&2; exit 2 ;;
esac
[ "${#SHA}" -eq 64 ] || { echo "ROUTING_OSM_SHA256 must be 64 lowercase hex characters" >&2; exit 2; }

BUILD="$DATA/build-$SHA"
if [ -f "$BUILD/.ready" ] && [ "$(readlink "$DATA/current" 2>/dev/null)" = "build-$SHA" ]; then
  echo "routing graph already built for $SHA"
  exit 0
fi

PBF="$DATA/extract.osm.pbf"
if [ ! -f "$PBF" ] || [ "$(sha256sum "$PBF" | cut -d' ' -f1)" != "$SHA" ]; then
  echo "downloading $URL"
  curl -fsSL --retry 3 --retry-delay 5 -o "$PBF.part" "$URL"
  GOT="$(sha256sum "$PBF.part" | cut -d' ' -f1)"
  if [ "$GOT" != "$SHA" ]; then
    rm -f "$PBF.part"
    echo "checksum mismatch: expected $SHA, got $GOT (refusing the extract)" >&2
    exit 1
  fi
  mv "$PBF.part" "$PBF"
fi

if [ ! -f "$BUILD/.ready" ]; then
  rm -rf "$BUILD"
  mkdir -p "$BUILD/tiles"
  valhalla_build_config \
    --mjolnir-tile-dir "$BUILD/tiles" \
    --mjolnir-tile-extract "$BUILD/tiles.tar" \
    --mjolnir-admin "$BUILD/admins.sqlite" \
    --mjolnir-timezone "$BUILD/timezones.sqlite" \
    --mjolnir-concurrency "$THREADS" \
    --httpd-service-listen "tcp://*:8002" \
    > "$BUILD/valhalla.json"
  # Country and region boundaries: driving side and default access rules of Tunisia.
  valhalla_build_admins -c "$BUILD/valhalla.json" "$PBF"
  valhalla_build_tiles -c "$BUILD/valhalla.json" "$PBF"
  # One tar file the service memory-maps; the loose tiles are then removed.
  valhalla_build_extract -c "$BUILD/valhalla.json" -v
  rm -rf "$BUILD/tiles"
  printf '%s\n' "$SHA" > "$BUILD/.ready"
fi

ln -sfn "build-$SHA" "$DATA/current.new"
mv -T "$DATA/current.new" "$DATA/current"
# Older graphs are no longer referenced.
for old in "$DATA"/build-*; do
  [ "$old" = "$BUILD" ] || rm -rf "$old"
done
echo "routing graph ready: $SHA"
