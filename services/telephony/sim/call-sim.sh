#!/bin/sh
# ┏━━ SIMULATION ━━ call-sim: starts its own Asterisk, then places a scripted call to 8000 every CALL_SIM_INTERVAL_S
# ┃   seconds (first one after CALL_SIM_FIRST_DELAY_S); each call plays the generated prompt for CALL_SIM_TALK_S.
# ┃   CALL_SIM_INTERVAL_S=0 places no automatic call: trigger one by hand with
# ┃   docker compose exec call-sim asterisk -C /run/asterisk/etc/asterisk.conf -rx "channel originate Local/call@sim-dial extension play@sim-caller"
# ┃ PRODUCTION: never deployed (compose profile "sim" only).
# ┗━━━━━━━━━━━━━━━━
set -eu
: "${CALL_SIM_INTERVAL_S:=300}"
: "${CALL_SIM_FIRST_DELAY_S:=30}"
: "${CALL_SIM_TALK_S:=20}"
CONF=/run/asterisk/etc/asterisk.conf
[ -n "${TELEPHONY_SIM_PASSWORD:-}" ] || { echo "[SIM] call-sim: TELEPHONY_SIM_PASSWORD is required" >&2; exit 1; }

asterisk -f -C "$CONF" &
AST=$!
trap 'kill "$AST" 2>/dev/null; wait "$AST"; exit 0' TERM INT
for _ in $(seq 1 60); do
  asterisk -C "$CONF" -rx "core waitfullybooted" >/dev/null 2>&1 && break
  sleep 1
done
asterisk -C "$CONF" -rx "dialplan set global EH_TALK_S $CALL_SIM_TALK_S" >/dev/null
echo "[SIM] call-sim ready: a call every ${CALL_SIM_INTERVAL_S}s (0 = manual only)" >&2

if [ "$CALL_SIM_INTERVAL_S" -gt 0 ]; then
  sleep "$CALL_SIM_FIRST_DELAY_S" & wait $!
  while kill -0 "$AST" 2>/dev/null; do
    echo "[SIM] call-sim: calling 8000" >&2
    asterisk -C "$CONF" -rx "channel originate Local/call@sim-dial extension play@sim-caller" >/dev/null || true
    sleep "$CALL_SIM_INTERVAL_S" & wait $!
  done
fi
wait "$AST"
