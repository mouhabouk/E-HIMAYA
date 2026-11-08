#!/bin/bash
# Keeps the secret of the confidential client ehimaya-account-admin (realm ehimaya-staff) equal to
# KEYCLOAK_ADMIN_CLIENT_SECRET from .env. Run by the one-shot compose service keycloak-sync at every `up`.
#
# Why: the realm file says "secret": "${KEYCLOAK_ADMIN_CLIENT_SECRET}", but --import-realm only applies a realm that
# does not exist yet, and Keycloak keeps an unresolved ${...} placeholder as the literal value. A realm imported
# before the variable reached the keycloak container therefore had the placeholder text, published in the
# repository, as the secret of a client that can manage every staff account. This script corrects it, and makes
# a rotation one step: change the value in .env, then `docker compose up -d`.
#
# Uses kcadm with the master admin of .env (KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD). If that password was changed
# in Keycloak, put the new one in .env too, otherwise this service stops with a message saying so.
# Never prints a secret. Exit 0 = in sync.
set -uo pipefail

: "${KC_URL:=http://keycloak:8080}"
: "${KEYCLOAK_ADMIN:=admin}"
: "${KEYCLOAK_ADMIN_PASSWORD:?set KEYCLOAK_ADMIN_PASSWORD}"
: "${KEYCLOAK_ADMIN_CLIENT_SECRET:?set KEYCLOAK_ADMIN_CLIENT_SECRET}"
REALM=ehimaya-staff
CLIENT=ehimaya-account-admin
KCADM=/opt/keycloak/bin/kcadm.sh
export HOME=/tmp # kcadm keeps its session in ~/.keycloak

say() { echo "keycloak-sync: $*"; }

# shellcheck disable=SC2016 # a literal ${ is what is looked for
case "$KEYCLOAK_ADMIN_CLIENT_SECRET" in
  *'${'*) say "KEYCLOAK_ADMIN_CLIENT_SECRET is a placeholder; set it in .env (openssl rand -hex 32)"; exit 1 ;;
esac
if ! [[ $KEYCLOAK_ADMIN_CLIENT_SECRET =~ ^[A-Za-z0-9._~+/=-]+$ ]]; then
  say "KEYCLOAK_ADMIN_CLIENT_SECRET may only hold letters, digits and ._~+/=- (openssl rand -hex 32)"
  exit 1
fi
if [ "${#KEYCLOAK_ADMIN_CLIENT_SECRET}" -lt 16 ]; then
  say "KEYCLOAK_ADMIN_CLIENT_SECRET must be at least 16 characters (openssl rand -hex 32)"
  exit 1
fi

# Keycloak may still be starting (first start: database schema, realm import): retry for about four minutes.
logged_in=false
for _ in $(seq 1 120); do
  if err=$("$KCADM" config credentials --server "$KC_URL" --realm master \
    --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" 2>&1 >/dev/null); then
    logged_in=true
    break
  fi
  if grep -qiE 'invalid_grant|invalid user credentials|401' <<<"$err"; then
    say "Keycloak refused KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD of .env. If the master admin password was changed"
    say "in Keycloak, write the new one in .env, then run: docker compose ... up -d keycloak-sync"
    exit 1
  fi
  sleep 2
done
$logged_in || { say "Keycloak did not answer at $KC_URL"; exit 1; }

id=$("$KCADM" get clients -r "$REALM" -q "clientId=$CLIENT" --fields id --format csv --noquotes 2>/dev/null)
if [ -z "$id" ]; then
  say "client $CLIENT not found in realm $REALM (realm not imported yet?)"
  exit 1
fi

current=$("$KCADM" get "clients/$id/client-secret" -r "$REALM" --fields value --format csv --noquotes 2>/dev/null)
if [ "$current" = "$KEYCLOAK_ADMIN_CLIENT_SECRET" ]; then
  say "$CLIENT secret already in sync"
  exit 0
fi

# The secret goes through stdin, never the command line (visible in the process list).
if printf '{"secret":"%s"}' "$KEYCLOAK_ADMIN_CLIENT_SECRET" | "$KCADM" update "clients/$id" -r "$REALM" -f - >/dev/null; then
  say "$CLIENT secret updated from .env"
else
  say "could not update the secret of $CLIENT"
  exit 1
fi
