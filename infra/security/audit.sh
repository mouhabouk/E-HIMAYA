#!/usr/bin/env bash
# قياس تحصين خادم ء-حماية. Security measurement of an e-Himaya host (review point 15, phase 4).
#
#   sudo infra/security/audit.sh <label> <host-ip> [tls-name]
#   e.g.  sudo infra/security/audit.sh before 192.168.1.10 api.ehimaya.lan
#         sudo infra/security/harden-host.sh --apply --profile demo
#         sudo infra/security/audit.sh after 192.168.1.10 api.ehimaya.lan
#         python3 infra/security/compare.py audit-before audit-after > docs/security/hardening-<date>.json
#
# Runs what is installed among: Lynis (host hardening index), nmap (open TCP ports and the UDP ports the platform
# uses), testssl.sh (TLS of the edge), OWASP ZAP baseline (passive scan of the edge, through Docker). Run Lynis on the
# host itself; run nmap from ANOTHER machine of the network for the real exposed surface (Docker bypasses ufw).
# Output: audit-<label>/ with the raw reports and summary.json (read by compare.py). Never against production with
# real data without the Office's written approval.
# TLS_CA=<root.crt>: the certificate authority the devices trust (CADDY_TLS=internal on the demonstration computer).
set -uo pipefail

LABEL="${1:?label (before, after…)}" HOST="${2:?host IP to scan}" TLS_NAME="${3:-}"
OUT="${AUDIT_OUT:-audit-$LABEL}"
mkdir -p "$OUT"
HERE=$(cd "$(dirname "$0")" && pwd)
echo "== e-Himaya audit '$LABEL' of $HOST ${TLS_NAME:+($TLS_NAME)} -> $OUT"

if command -v lynis >/dev/null; then
  echo "-- Lynis"
  lynis audit system --quick --no-colors --report-file "$OUT/lynis-report.dat" --log-file "$OUT/lynis.log" > "$OUT/lynis.txt" 2>&1
  grep -E "Hardening index|Tests performed" "$OUT/lynis.txt"
else echo "-- Lynis not installed (apt install lynis)"; fi

if command -v nmap >/dev/null; then
  echo "-- nmap TCP (1000 common ports + the platform's)"
  nmap -Pn -sT -sV --version-light --top-ports 1000 -p T:22,80,443,1080,1935,4222,5060,5061,5432,6379,8000,8025,8080,8088,8222,8333,8554,8888,8889,9090 \
    -oX "$OUT/nmap-tcp.xml" -oN "$OUT/nmap-tcp.txt" "$HOST" >/dev/null 2>&1
  grep -E "^[0-9]+/tcp" "$OUT/nmap-tcp.txt" || echo "   no open TCP port"
  if [ "$(id -u)" = 0 ]; then
    echo "-- nmap UDP (443 QUIC, 5060 SIP, 8189 WebRTC, 53, 123, 161)"
    nmap -Pn -sU -p 53,123,161,443,5060,8189 -oX "$OUT/nmap-udp.xml" -oN "$OUT/nmap-udp.txt" "$HOST" >/dev/null 2>&1
    grep -E "^[0-9]+/udp" "$OUT/nmap-udp.txt" || true
  fi
else echo "-- nmap not installed (apt install nmap)"; fi

TESTSSL=$(command -v testssl || command -v testssl.sh || true)
if [ -n "$TLS_NAME" ] && [ -n "$TESTSSL" ]; then
  echo "-- testssl.sh https://$TLS_NAME ($HOST)"
  # TLS_CA: the root the devices trust (demo: Caddy's local root, docs/demo.md), so the chain is judged as they see it.
  "$TESTSSL" --quiet --color 0 --ip "$HOST" ${TLS_CA:+--add-ca "$TLS_CA"} --jsonfile "$OUT/testssl.json" --logfile "$OUT/testssl.txt" \
    --protocols --server-defaults --headers --vulnerable --cipher-per-proto "https://$TLS_NAME" >/dev/null 2>&1
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('   findings:', len(d))" "$OUT/testssl.json" 2>/dev/null || true
elif [ -n "$TLS_NAME" ]; then echo "-- testssl.sh not installed (apt install testssl.sh)"; fi

if [ -n "$TLS_NAME" ] && command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  echo "-- ZAP baseline https://$TLS_NAME"
  docker run --rm --add-host "$TLS_NAME:$HOST" -v "$(cd "$OUT" && pwd):/zap/wrk:rw" "${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:2.16.1}" \
    zap-baseline.py -t "https://$TLS_NAME/" -J zap-baseline.json -r zap-baseline.html -I >/dev/null 2>&1 || true
  echo "   API scan with a staff token: infra/security/zap/run.sh"
else echo "-- ZAP skipped (needs Docker and a TLS name); API scan: infra/security/zap/run.sh"; fi

python3 "$HERE/compare.py" --summarize "$OUT" > "$OUT/summary.json" && echo "== summary: $OUT/summary.json"
