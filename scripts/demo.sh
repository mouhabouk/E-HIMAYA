#!/usr/bin/env bash
# ء-حماية / e-Himaya — the demonstration before the committee (review point 16, docs/demo.md).
#
#   scripts/demo.sh up          start the stack on the demonstration computer (443 only, no Internet)
#   scripts/demo.sh users       create the demonstration accounts in Keycloak (passwords from .env.demo)
#   scripts/demo.sh seed        the [SIM] institution, the team leader's activation code, the camera link
#   scripts/demo.sh prealert    the institution's camera «sees» a fire: the owner's phone rings, 90 s countdown
#   scripts/demo.sh status      what the scenario has, and the containers
#   scripts/demo.sh ca          the certificate to install on the phones (Caddy's own CA), written to ./demo-ca.crt
#   scripts/demo.sh down        stop (the data stays; `down --volumes` erases it for a clean rehearsal)
#
# Every value comes from .env.demo (copy .env.demo.example, then fill it). Nothing is sent outside the computer.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE=${DEMO_ENV_FILE:-.env.demo}
[ -f "$ENV_FILE" ] || { echo "demo: $ENV_FILE is missing (cp .env.demo.example .env.demo, then fill it)" >&2; exit 1; }
COMPOSE=(docker compose --env-file "$ENV_FILE" -f infra/compose.yml -f infra/compose.prod.yml -f infra/compose.demo.yml
  --profile sim)
# The camera relay only when a real camera is configured (Tapo or any RTSP camera, docs/demo.md §4).
if grep -Eq '^CAMERA_RTSP_URL=.+' "$ENV_FILE"; then COMPOSE+=(--profile camera); fi

env_value() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2-; }

kcadm() { "${COMPOSE[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"; }

kc_login() {
  kcadm config credentials --server http://localhost:8080 --realm master \
    --user "$(env_value KEYCLOAK_ADMIN || echo admin)" --password "$(env_value KEYCLOAK_ADMIN_PASSWORD)" >/dev/null
}

# create_user <realm> <username> <password> <roles,comma> [attribute=value ...]
create_user() {
  local realm=$1 username=$2 password=$3 roles=$4
  shift 4
  if [ -z "$(kcadm get users -r "$realm" -q "username=$username" -q exact=true --fields id --format csv --noquotes)" ]; then
    local args=(-s "username=$username" -s enabled=true -s emailVerified=true -s "email=$username@ehimaya.demo"
      -s "firstName=[SIM]" -s "lastName=$username")
    for attr in "$@"; do args+=(-s "attributes.${attr%%=*}=[\"${attr#*=}\"]"); done
    kcadm create users -r "$realm" "${args[@]}" >/dev/null
  fi
  kcadm set-password -r "$realm" --username "$username" --new-password "$password" >/dev/null
  # No second factor and no password change on the day (demonstration accounts only, closed network).
  local id
  id=$(kcadm get users -r "$realm" -q "username=$username" -q exact=true --fields id --format csv --noquotes)
  kcadm update "users/$id" -r "$realm" -s 'requiredActions=[]' >/dev/null
  IFS=, read -ra list <<<"$roles"
  kcadm add-roles -r "$realm" --uusername "$username" "${list[@]/#/--rolename=}" >/dev/null
  echo "$id"
}

case "${1:-}" in
  up)
    "${COMPOSE[@]}" up -d --build --wait
    echo "demo: up. Next: scripts/demo.sh users, then scripts/demo.sh seed"
    ;;
  users)
    password=$(env_value DEMO_PASSWORD)
    [ ${#password} -ge 12 ] || { echo "demo: set DEMO_PASSWORD (12 characters or more) in $ENV_FILE" >&2; exit 1; }
    g=$(env_value DEMO_GOUVERNORAT); g=${g:-21}
    kc_login
    create_user ehimaya-staff demo-room "$password" operator,ops_manager,regional_account_admin "gouvernorat_code=$g" >/dev/null
    create_user ehimaya-staff demo-central "$password" operator,central_committee,sysadmin "scope_level=national" >/dev/null
    create_user ehimaya-staff demo-committee "$password" governor,local_committee "gouvernorat_code=$g" >/dev/null
    owner=$(create_user ehimaya-public demo-owner "$password" citizen,org_admin)
    create_user ehimaya-public demo-citizen "$password" citizen >/dev/null
    echo "$owner" >.demo-owner-id
    echo "demo: accounts demo-room, demo-central, demo-committee (staff) and demo-owner, demo-citizen (public)"
    ;;
  seed)
    [ -f .demo-owner-id ] || { echo "demo: run scripts/demo.sh users first" >&2; exit 1; }
    g=$(env_value DEMO_GOUVERNORAT); g=${g:-21}
    "${COMPOSE[@]}" exec -T worker python -m app.demo seed --owner-sub "$(cat .demo-owner-id)" --gouvernorat "$g"
    ;;
  prealert)
    "${COMPOSE[@]}" exec -T worker python -m app.demo prealert --label "${2:-fire}"
    ;;
  status)
    "${COMPOSE[@]}" exec -T worker python -m app.demo status
    "${COMPOSE[@]}" ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}'
    ;;
  ca)
    "${COMPOSE[@]}" exec -T caddy cat /data/caddy/pki/authorities/local/root.crt >demo-ca.crt
    echo "demo: demo-ca.crt written; install it on each phone (Settings > Security > Install a certificate > CA)"
    ;;
  down)
    shift
    "${COMPOSE[@]}" down "$@"
    ;;
  *)
    sed -n '2,13p' "$0"
    exit 1
    ;;
esac
