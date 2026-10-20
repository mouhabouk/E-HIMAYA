#!/bin/sh
# Renders the Asterisk configuration from /etc/ehimaya-asterisk/templates into /run/asterisk/etc (mode 0600), then runs
# the command (Asterisk in the foreground by default). Placeholders are @@NAME@@; every value comes from the
# environment (docs/telephony.md lists them). Optional parts (TLS, trunk, simulator) are rendered only when configured.
set -eu

TEMPLATES=/etc/ehimaya-asterisk/templates
OUT=/run/asterisk/etc
CERTS=/etc/ehimaya-asterisk/certs

fail() { echo "telephony: $*" >&2; exit 1; }

# ---------------------------------------------------------------- settings and their defaults
: "${TELEPHONY_ARI_USER:=ehimaya-api}"
: "${TELEPHONY_ARI_PASSWORD:=}"
: "${TELEPHONY_EXTERNAL_HOST:=127.0.0.1}"
: "${TELEPHONY_RTP_START:=10000}"
: "${TELEPHONY_RTP_END:=10099}"
: "${TELEPHONY_LOCAL_NETS:=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"
: "${TELEPHONY_QUEUE_TIMEOUT_S:=300}"
: "${TELEPHONY_TRANSFER_198_ENABLED:=false}"
: "${TELEPHONY_TRUNK_HOST:=}"
: "${TELEPHONY_TRUNK_PORT:=5060}"
: "${TELEPHONY_TRUNK_TRANSPORT:=udp}"
: "${TELEPHONY_TRUNK_USERNAME:=}"
: "${TELEPHONY_TRUNK_PASSWORD:=}"
: "${TELEPHONY_TRUNK_DOMAIN:=${TELEPHONY_TRUNK_HOST}}"
: "${TELEPHONY_TRUNK_MATCH:=${TELEPHONY_TRUNK_HOST}}"
: "${TELEPHONY_TRUNK_REGISTER:=false}"
: "${TELEPHONY_TRUNK_CODECS:=alaw,ulaw}"
: "${TELEPHONY_TRUNK_MEDIA_ENCRYPTION:=no}"
: "${TELEPHONY_TRUNK_NUMBER_FORMAT:=e164}"
: "${TELEPHONY_TRUNK_CALLER_ID:=}"
: "${TELEPHONY_TRUNK_198_NUMBER:=198}"
: "${TELEPHONY_SIM_PASSWORD:=}"
: "${CALL_SIM_TARGET:=telephony}"

# ---------------------------------------------------------------- checks (fail fast, never print a secret)
if [ -f "$TEMPLATES/ari.conf" ]; then
  [ -n "$TELEPHONY_ARI_PASSWORD" ] || fail "TELEPHONY_ARI_PASSWORD is required (openssl rand -hex 24)"
  [ "${#TELEPHONY_ARI_PASSWORD}" -ge 16 ] || fail "TELEPHONY_ARI_PASSWORD must be at least 16 characters"
fi
case "$TELEPHONY_ARI_USER" in *[!A-Za-z0-9_-]*|"") fail "TELEPHONY_ARI_USER: letters, digits, - and _ only" ;; esac
case "$TELEPHONY_RTP_START$TELEPHONY_RTP_END" in *[!0-9]*) fail "TELEPHONY_RTP_START/END must be port numbers" ;; esac
[ "$TELEPHONY_RTP_START" -ge 1024 ] && [ "$TELEPHONY_RTP_END" -gt "$TELEPHONY_RTP_START" ] \
  && [ "$TELEPHONY_RTP_END" -le 65535 ] || fail "TELEPHONY_RTP_START..END must be a range within 1024-65535"
case "$TELEPHONY_QUEUE_TIMEOUT_S" in *[!0-9]*|"") fail "TELEPHONY_QUEUE_TIMEOUT_S must be a number of seconds" ;; esac
case "$TELEPHONY_TRUNK_TRANSPORT" in udp|tcp|tls) ;; *) fail "TELEPHONY_TRUNK_TRANSPORT must be udp, tcp or tls" ;; esac
case "$TELEPHONY_TRUNK_NUMBER_FORMAT" in e164|00|national) ;; *) fail "TELEPHONY_TRUNK_NUMBER_FORMAT: e164, 00 or national" ;; esac
case "$TELEPHONY_TRUNK_MEDIA_ENCRYPTION" in no|sdes) ;; *) fail "TELEPHONY_TRUNK_MEDIA_ENCRYPTION: no or sdes" ;; esac
case "$TELEPHONY_TRUNK_198_NUMBER" in *[!0-9+]*|"") fail "TELEPHONY_TRUNK_198_NUMBER: digits only" ;; esac
case "$TELEPHONY_TRUNK_CALLER_ID" in *[!0-9+]*) fail "TELEPHONY_TRUNK_CALLER_ID: digits only" ;; esac

# Up to three local networks (addresses that are not NATed).
LOCAL_1=$(echo "$TELEPHONY_LOCAL_NETS" | cut -d, -f1)
LOCAL_2=$(echo "$TELEPHONY_LOCAL_NETS" | cut -s -d, -f2)
LOCAL_3=$(echo "$TELEPHONY_LOCAL_NETS" | cut -s -d, -f3)
export TELEPHONY_LOCAL_NET_1="$LOCAL_1" TELEPHONY_LOCAL_NET_2="${LOCAL_2:-$LOCAL_1}" TELEPHONY_LOCAL_NET_3="${LOCAL_3:-$LOCAL_1}"

# WebRTC ICE: the container's own address is replaced by the external one in the candidates sent to browsers.
CONTAINER_IP=$(awk -v host="$(cat /etc/hostname 2>/dev/null)" '$2 == host { print $1; exit }' /etc/hosts 2>/dev/null || true)
case "$TELEPHONY_EXTERNAL_HOST" in
  *[!0-9.]*) fail "TELEPHONY_EXTERNAL_HOST must be an IPv4 address (ICE candidates)" ;;
esac
if [ -n "$CONTAINER_IP" ] && [ "$CONTAINER_IP" != "$TELEPHONY_EXTERNAL_HOST" ]; then
  export EH_ICE_HOST_CANDIDATE="$CONTAINER_IP => $TELEPHONY_EXTERNAL_HOST"
else
  export EH_ICE_HOST_CANDIDATE=""
fi

TRUNK=0
if [ -n "$TELEPHONY_TRUNK_HOST" ]; then
  TRUNK=1
  [ -n "$TELEPHONY_TRUNK_USERNAME" ] || fail "TELEPHONY_TRUNK_USERNAME is required with TELEPHONY_TRUNK_HOST"
  if [ "$TELEPHONY_TRUNK_TRANSPORT" = tls ] && { [ ! -r "$CERTS/tls.crt" ] || [ ! -r "$CERTS/tls.key" ]; }; then
    fail "TELEPHONY_TRUNK_TRANSPORT=tls needs $CERTS/tls.crt and tls.key"
  fi
fi
case "$TELEPHONY_TRANSFER_198_ENABLED" in true|1|yes) TRANSFER=1 ;; *) TRANSFER=0 ;; esac
if [ "$TRUNK" = 1 ]; then OUTBOUND=trunk
elif [ -n "$TELEPHONY_SIM_PASSWORD" ]; then OUTBOUND=call-sim
else OUTBOUND=none
fi
export EH_TRUNK="$TRUNK" EH_TRANSFER_198="$TRANSFER" EH_OUTBOUND="$OUTBOUND"
export TELEPHONY_ARI_USER TELEPHONY_ARI_PASSWORD TELEPHONY_EXTERNAL_HOST TELEPHONY_RTP_START TELEPHONY_RTP_END \
  TELEPHONY_QUEUE_TIMEOUT_S TELEPHONY_TRUNK_HOST TELEPHONY_TRUNK_PORT TELEPHONY_TRUNK_TRANSPORT \
  TELEPHONY_TRUNK_USERNAME TELEPHONY_TRUNK_PASSWORD TELEPHONY_TRUNK_DOMAIN TELEPHONY_TRUNK_MATCH \
  TELEPHONY_TRUNK_CODECS TELEPHONY_TRUNK_MEDIA_ENCRYPTION TELEPHONY_TRUNK_NUMBER_FORMAT TELEPHONY_TRUNK_CALLER_ID \
  TELEPHONY_TRUNK_198_NUMBER TELEPHONY_SIM_PASSWORD CALL_SIM_TARGET

# ---------------------------------------------------------------- rendering
# @@NAME@@ is replaced by the environment value; a ";" (comment in Asterisk files) is escaped, a line break refused.
render() {
  awk '
    {
      rest = $0; out = ""
      while (match(rest, /@@[A-Z0-9_]+@@/)) {
        name = substr(rest, RSTART + 2, RLENGTH - 4)
        if (!(name in ENVIRON)) { printf "telephony: %s is not set\n", name > "/dev/stderr"; exit 2 }
        value = ENVIRON[name]
        if (value ~ /[\r\n]/) { printf "telephony: %s contains a line break\n", name > "/dev/stderr"; exit 2 }
        escaped = ""
        while ((i = index(value, ";")) > 0) { escaped = escaped substr(value, 1, i - 1) "\\;"; value = substr(value, i + 1) }
        out = out substr(rest, 1, RSTART - 1) escaped value
        rest = substr(rest, RSTART + RLENGTH)
      }
      print out rest
    }' "$1" > "$2"
}

umask 077
mkdir -p "$OUT"
rm -f "$OUT"/*.conf
for template in "$TEMPLATES"/*.conf; do
  render "$template" "$OUT/$(basename "$template")"
done
if [ -r "$CERTS/tls.crt" ] && [ -r "$CERTS/tls.key" ] && [ -f "$TEMPLATES/pjsip_tls.conf.tmpl" ]; then
  render "$TEMPLATES/pjsip_tls.conf.tmpl" "$OUT/pjsip_tls.conf"
fi
if [ "$TRUNK" = 1 ] && [ -f "$TEMPLATES/pjsip_trunk.conf.tmpl" ]; then
  render "$TEMPLATES/pjsip_trunk.conf.tmpl" "$OUT/pjsip_trunk.conf"
  case "$TELEPHONY_TRUNK_REGISTER" in
    true|1|yes) render "$TEMPLATES/pjsip_trunk_registration.conf.tmpl" "$OUT/pjsip_trunk_registration.conf"
                echo "#include pjsip_trunk_registration.conf" >> "$OUT/pjsip_trunk.conf" ;;
  esac
fi
# ┏━━ SIMULATION ━━ the call-sim endpoint and the sim entry context exist only with TELEPHONY_SIM_PASSWORD.
# ┃ PRODUCTION: leave TELEPHONY_SIM_PASSWORD empty (infra/compose.prod.yml forces it empty).
# ┗━━━━━━━━━━━━━━━━
if [ -n "$TELEPHONY_SIM_PASSWORD" ]; then
  for part in pjsip_sim extensions_sim; do
    [ -f "$TEMPLATES/$part.conf.tmpl" ] && render "$TEMPLATES/$part.conf.tmpl" "$OUT/$part.conf"
  done
  echo "[SIM] telephony: call-sim endpoint enabled" >&2
fi

echo "telephony: configuration rendered (trunk=$TRUNK, outbound=$OUTBOUND, transfer_198=$TRANSFER," \
  "rtp=$TELEPHONY_RTP_START-$TELEPHONY_RTP_END)" >&2
exec "$@"
