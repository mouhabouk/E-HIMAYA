#!/bin/bash
# ء-حماية / e-Himaya — تشغيل فحوص CI محليا عندما لا تعمل GitHub Actions (مثلا حد الفوترة على المستودع الخاص).
# Runs the checks of .github/workflows/*.yml on a developer machine with Docker, job by job, with the same commands
# and the same environment values. Differences, all on purpose:
#   - the code under test is a clean checkout (git worktree) of one commit (--ref, default HEAD), like
#     actions/checkout: uncommitted changes are NOT tested, and the stack job's throwaway .env never touches yours;
#   - every container, volume, network and image is throwaway: unique names ("cil-<run>-..."), label
#     ehimaya.ci-local=<run>, image tags ehimaya/<name>:cil-<run>, host ports picked at random on 127.0.0.1;
#     all of it is removed when a job ends and again on exit (trap), Ctrl-C included;
#   - a job whose tools are missing here (Flutter/Android SDK, Node 22, disk for the AI models, internet from inside
#     containers, ...) is reported SKIPPED with the reason, never PASS;
#   - steps that only make sense on a hosted runner are not run: the "free disk space" steps (they delete system
#     directories) and actions/cache (local caches live in $CI_LOCAL_CACHE instead).
# Usage: scripts/ci-local.sh [--only job[,job]] [--skip job[,job]] [--keep-going] [--ref <commit>] [--list]
# Result: a summary table on the terminal, ci-local-report.md (Markdown, to paste into a PR) and one log per job in
# ci-local-logs/ (both git-ignored). Exit status 1 when a job failed.
set -euo pipefail

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
REPORT="$ROOT/ci-local-report.md"
LOGS="$ROOT/ci-local-logs"
CACHE=${CI_LOCAL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ehimaya-ci-local}

# The image trivy-action 0.35.0 (pinned in ci.yml) installs: its default Trivy version is v0.69.3.
TRIVY_IMAGE=aquasec/trivy:0.69.3@sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c
# Same pins as the workflows.
OPENSEARCH_IMAGE=opensearchproject/opensearch:2.19.6@sha256:be67c71b8d0e5edf1e9825145501c0136c3b8221206e1ce782ce17b04d0280b5
OLLAMA_IMAGE=ollama/ollama:0.40.1@sha256:69f27594d8127cb43db1edcafa5e2d3cd8f88bdbc54a2cf3ceb11b8d138a24b1
FLUTTER_VERSION=3.47.7
NODE_MAJOR=22
JAVA_MAJOR=17

# Job ids, in the order they run: <id>|<workflow>|<name in the workflow>.
JOB_TABLE=(
  "api|ci.yml|API · lint, types, migrations, tests"
  "api-image|ci.yml|API · container image"
  "image-scan|ci.yml|Images · build and Trivy scan (one row per matrix entry)"
  "telephony|ci.yml|Telephony · Asterisk image"
  "notify-sim|ci.yml|Notify simulator · lint, types, tests"
  "notify-sim-image|ci.yml|Notify simulator · container image"
  "keycloak-realms|ci.yml|Keycloak · realm import"
  "ai|ci.yml|AI · lint, types, tests"
  "ai-images|ci.yml|AI · container images"
  "ai-models|ci.yml|AI · real models"
  "vision|ci.yml|Vision · lint, types, tests"
  "vision-models|ci.yml|Vision · real models"
  "quality|ci.yml|Quality · traceability and alert rules"
  "backup-drill|ci.yml|Backup · restore drill"
  "supply-chain|ci.yml|Supply chain · audit, SBOM and licences"
  "stack|ci.yml|Stack · compose smoke test"
  "dashboard|dashboard.yml|Dashboard · lint, types, tests, build, browser tests"
  "portal|portal.yml|Portal · lint, types, tests, build, browser tests"
  "mobile|mobile.yml|Mobile · analyze, test, build"
)
# image-scan matrix (ci.yml): <name>|<context>|<docker build args>.
IMAGE_SCAN=(
  "api|services/api|"
  "notify-sim|services/notify-sim|"
  "ai|services/ai|--target runtime"
  "vision|services/vision|--target runtime"
  "postgres|infra/postgres|"
  "dashboard|apps/dashboard|--build-context web=infra/web"
  "portal|apps/portal|--build-context web=infra/web"
  "telephony|services/telephony|--target runtime"
  "call-sim|services/telephony|--target call-sim"
)

usage() {
  sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'
  exit "${1:-0}"
}

list_jobs() {
  local row id workflow name
  printf '%-18s %-14s %s\n' JOB WORKFLOW NAME
  for row in "${JOB_TABLE[@]}"; do
    IFS='|' read -r id workflow name <<< "$row"
    printf '%-18s %-14s %s\n' "$id" "$workflow" "$name"
  done
  printf '\nimage-scan entries (also selectable one by one, e.g. --only image-scan:api):'
  for row in "${IMAGE_SCAN[@]}"; do printf ' %s' "${row%%|*}"; done
  echo
}

fail() { echo "ci-local: $*" >&2; exit 2; }

# ── Options ──────────────────────────────────────────────────────────────────────────────────────────────────────
ONLY=() SKIP=() KEEP_GOING=0 REF=HEAD
while [ $# -gt 0 ]; do
  case $1 in
    --only) [ $# -ge 2 ] || fail "--only needs a job"; IFS=, read -r -a more <<< "$2"; ONLY+=("${more[@]}"); shift 2 ;;
    --skip) [ $# -ge 2 ] || fail "--skip needs a job"; IFS=, read -r -a more <<< "$2"; SKIP+=("${more[@]}"); shift 2 ;;
    --keep-going) KEEP_GOING=1; shift ;;
    --ref) [ $# -ge 2 ] || fail "--ref needs a commit"; REF=$2; shift 2 ;;
    --list) list_jobs; exit 0 ;;
    -h|--help) usage 0 ;;
    *) echo "ci-local: unknown option $1" >&2; usage 2 ;;
  esac
done

# Every runnable unit: the jobs, with image-scan expanded into its matrix entries.
ALL_UNITS=()
for row in "${JOB_TABLE[@]}"; do
  id=${row%%|*}
  if [ "$id" = image-scan ]; then
    for entry in "${IMAGE_SCAN[@]}"; do ALL_UNITS+=("image-scan:${entry%%|*}"); done
  else
    ALL_UNITS+=("$id")
  fi
done
# "image-scan" selects every entry, "image-scan:api" one of them.
matches() {
  local unit=$1 pattern
  shift
  for pattern in "$@"; do
    if [ "$unit" = "$pattern" ] || [ "${unit%%:*}" = "$pattern" ]; then return 0; fi
  done
  return 1
}
for pattern in ${ONLY[@]+"${ONLY[@]}"} ${SKIP[@]+"${SKIP[@]}"}; do
  known=0
  for unit in "${ALL_UNITS[@]}"; do
    if matches "$unit" "$pattern"; then known=1; fi
  done
  [ "$known" = 1 ] || fail "unknown job '$pattern' (see --list)"
done
UNITS=()
for unit in "${ALL_UNITS[@]}"; do
  if [ ${#ONLY[@]} -gt 0 ] && ! matches "$unit" "${ONLY[@]}"; then continue; fi
  if [ ${#SKIP[@]} -gt 0 ] && matches "$unit" "${SKIP[@]}"; then continue; fi
  UNITS+=("$unit")
done
[ ${#UNITS[@]} -gt 0 ] || fail "no job selected"

COMMIT=$(git -C "$ROOT" rev-parse --verify "$REF^{commit}") || fail "unknown commit $REF"

# ── Throwaway workspace and Docker resources ─────────────────────────────────────────────────────────────────────
RUN_ID="cil-$(date +%s)-$$"
LABEL="ehimaya.ci-local=$RUN_ID"
STACK_PROJECT="$RUN_ID-stack"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ehimaya-ci-local.XXXXXX")
SRC="$WORK/src"

img() { echo "ehimaya/$1:$RUN_ID"; }     # image tag
free_port() {
  python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'
}

docker_cleanup() {
  docker info >/dev/null 2>&1 || return 0
  local filter
  for filter in "label=$LABEL" "label=com.docker.compose.project=$STACK_PROJECT"; do
    docker ps -aq --filter "$filter" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker volume ls -q --filter "$filter" | xargs -r docker volume rm -f >/dev/null 2>&1 || true
    docker network ls -q --filter "$filter" | xargs -r docker network rm >/dev/null 2>&1 || true
  done
  docker images --format '{{.Repository}}:{{.Tag}}' --filter "reference=ehimaya/*:$RUN_ID" \
    | xargs -r docker rmi -f >/dev/null 2>&1 || true
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  docker_cleanup
  # rm then prune: "git worktree remove" walks every untracked file (node_modules, .venv) and is much slower.
  rm -rf "$WORK" 2>/dev/null || true
  git -C "$ROOT" worktree prune 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT
trap 'echo "ci-local: interrupted" >&2; exit 130' INT TERM

# ── Requirements: each prints why a job cannot run here and returns 1 ────────────────────────────────────────────
have_root() { [ "$(id -u)" = 0 ] || sudo -n true 2>/dev/null; }
as_root() { if [ "$(id -u)" = 0 ]; then "$@"; else sudo "$@"; fi; }

need_cmds() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "'$cmd' is not installed"; return 1; }
  done
}

need_docker() {
  need_cmds docker || return 1
  docker info >/dev/null 2>&1 || { echo "the Docker daemon is not reachable"; return 1; }
}

free_gb() { df -Pk "$1" 2>/dev/null | awk 'NR == 2 { print int($4 / 1048576) }'; }
need_disk() {
  local want=$1 path free least=""
  for path in "$WORK" "$(dirname "$CACHE")" "$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || true)"; do
    [ -n "$path" ] || continue
    free=$(free_gb "$path")
    [ -n "$free" ] || continue
    if [ -z "$least" ] || [ "$free" -lt "$least" ]; then least=$free; fi
  done
  [ -z "$least" ] || [ "$least" -ge "$want" ] || { echo "needs about $want GB of free disk, $least GB free"; return 1; }
}

# Image builds (apt, pip, uv, go) and Trivy's database download happen inside containers: without internet there,
# or behind a TLS-intercepting proxy the images do not trust, those jobs cannot pass, so they are skipped up front.
# The probe uses the python base image of services/*/Dockerfile. CI_LOCAL_SKIP_NET_CHECK=1 runs them anyway (for
# example when every layer is already in the build cache).
need_container_net() {
  [ "${CI_LOCAL_SKIP_NET_CHECK:-0}" = 1 ] && return 0
  if [ ! -f "$WORK/container-net" ]; then
    local image
    image=$(grep -m1 -o 'python:3\.12-slim@sha256:[0-9a-f]*' "$ROOT/services/api/Dockerfile")
    if docker run --rm --label "$LABEL" "$image" python -c \
        "import urllib.request; urllib.request.urlopen('https://pypi.org/simple/pip/', timeout=20)" >/dev/null 2>&1; then
      echo ok > "$WORK/container-net"
    else
      echo "containers cannot reach the internet over HTTPS (probe: pypi.org from the python:3.12-slim base" \
        "image), so image builds would fail here" > "$WORK/container-net"
    fi
  fi
  [ "$(cat "$WORK/container-net")" = ok ] || { cat "$WORK/container-net"; return 1; }
}

need_node() {
  need_cmds node npm npx || return 1
  local major
  major=$(node -p 'process.versions.node.split(".")[0]')
  [ "$major" = "$NODE_MAJOR" ] || { echo "the workflow uses Node $NODE_MAJOR, this machine has Node $major"; return 1; }
}

need_pyyaml() { python3 -c 'import yaml' 2>/dev/null || { echo "python3 has no PyYAML (pip install pyyaml)"; return 1; }; }

need_espeak() {
  command -v espeak-ng >/dev/null 2>&1 || have_root \
    || { echo "espeak-ng is not installed (and no root/passwordless sudo to apt-get it like CI)"; return 1; }
}

# promtool on PATH, or Docker to run it from the pinned Prometheus image (as the workflow does).
need_promtool() {
  command -v promtool >/dev/null && return 0
  docker info >/dev/null 2>&1 && return 0
  echo "neither promtool nor Docker is available"
  return 1
}
# The restore drill starts its own clusters: PostgreSQL 16 server binaries with PostGIS and pgvector, run as root
# (or as the user owning them).
need_pg_server() {
  local bin=${PG_BIN:-/usr/lib/postgresql/16/bin} share
  [ -x "$bin/postgres" ] || { echo "no PostgreSQL 16 server in $bin (set PG_BIN)"; return 1; }
  share=$("$bin/pg_config" --sharedir 2>/dev/null || echo /usr/share/postgresql/16)
  [ -f "$share/extension/postgis.control" ] || { echo "PostGIS is not installed for $bin"; return 1; }
  [ -f "$share/extension/vector.control" ] || { echo "pgvector is not installed for $bin"; return 1; }
}

need_flutter() {
  need_cmds flutter dart java || return 1
  local version java_major
  version=$(flutter --version --machine 2>/dev/null | python3 -c 'import json, sys; print(json.load(sys.stdin)["frameworkVersion"])' || true)
  [ "$version" = "$FLUTTER_VERSION" ] \
    || { echo "the workflow uses Flutter $FLUTTER_VERSION, this machine has Flutter ${version:-unknown}"; return 1; }
  java_major=$(java -XshowSettings:properties -version 2>&1 | awk -F' = ' '/java.specification.version/ { print $2 }')
  [ "$java_major" = "$JAVA_MAJOR" ] \
    || { echo "the workflow uses Java $JAVA_MAJOR (Temurin), this machine has Java ${java_major:-unknown}"; return 1; }
  [ -n "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ] && [ -d "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ] \
    || { echo "no Android SDK (ANDROID_HOME / ANDROID_SDK_ROOT) for 'flutter build apk'"; return 1; }
  ldconfig -p 2>/dev/null | grep -q 'libsqlite3\.so ' || have_root \
    || { echo "libsqlite3-dev is not installed (and no root/passwordless sudo to apt-get it like CI)"; return 1; }
}

# Prints the reason a unit cannot run on this machine; prints nothing when it can.
skip_reason() {
  case ${1%%:*} in
    api)              need_cmds uv curl openssl python3 && need_docker && need_disk 6 && need_container_net ;;
    api-image)        need_docker && need_disk 4 && need_container_net ;;
    image-scan)       need_docker && need_disk 8 && need_container_net ;;
    telephony)        need_cmds curl && need_docker && need_disk 4 && need_container_net ;;
    notify-sim|ai|vision) need_cmds uv ;;
    notify-sim-image) need_docker && need_disk 2 && need_container_net ;;
    keycloak-realms)  need_cmds curl python3 && need_docker && need_disk 2 ;;
    ai-images)        need_docker && need_disk 8 && need_container_net ;;
    ai-models)        need_cmds uv curl python3 && need_docker && need_espeak && need_disk 25 && need_container_net ;;
    vision-models)    need_cmds uv curl python3 && need_docker && need_disk 6 && need_container_net ;;
    stack)            need_cmds openssl python3 && need_pyyaml && need_docker && need_disk 10 && need_container_net ;;
    dashboard)        need_node && need_disk 3 ;;
    portal)           need_node && need_disk 3 ;;
    quality)          need_cmds python3 && need_promtool ;;
    backup-drill)     need_cmds uv && need_pg_server ;;
    supply-chain)     need_cmds uv python3 && need_node && need_disk 3 ;;
    mobile)           need_flutter && need_disk 15 ;;
  esac
}

# ── Step helpers (used inside the jobs) ──────────────────────────────────────────────────────────────────────────
step() {
  echo "$1" > "$WORK/step"
  printf '\n━━ %s\n' "$1"
}
# setup-uv with python-version sets UV_PYTHON; uv downloads that Python when the machine lacks it.
setup_uv() { export UV_PYTHON=3.12; }
# Background processes a job starts (uvicorn, http.server) are stopped when it ends, whatever the outcome.
stop_background() { jobs -p | xargs -r kill 2>/dev/null || true; }

# ── Jobs: one function per workflow job, steps in the workflow's order, run from the checkout root ──────────────

job_api() {
  local db_port api_port os_port pg=$RUN_ID-pg opensearch=$RUN_ID-opensearch
  db_port=$(free_port)
  export DATABASE_URL="postgresql+asyncpg://ehimaya:ehimaya-ci@localhost:$db_port/ehimaya"
  export RUNTIME_DATABASE_URL="postgresql+asyncpg://ehimaya_app:ehimaya-app-ci@localhost:$db_port/ehimaya"
  export DB_RUNTIME_ROLE=ehimaya_app
  export ANON_PSEUDONYM_SECRET=ci-only-secret-ci-only-secret-ci-only-01
  export FIELD_ENCRYPTION_KEY=Y2ktb25seS1rZXktY2ktb25seS1rZXktY2ktb25seTE=

  step "Build database image (PostgreSQL + PostGIS + pgvector)"
  (cd infra/postgres && docker build -t "$(img postgres)" .)

  step "Start database"
  docker run -d --name "$pg" --label "$LABEL" -p "127.0.0.1:$db_port:5432" \
    -e POSTGRES_PASSWORD=postgres-ci \
    -e EHIMAYA_DB_NAME=ehimaya -e EHIMAYA_DB_USER=ehimaya -e EHIMAYA_DB_PASSWORD=ehimaya-ci \
    -e EHIMAYA_DB_RUNTIME_USER=ehimaya_app -e EHIMAYA_DB_RUNTIME_PASSWORD=ehimaya-app-ci \
    -e KEYCLOAK_DB_NAME=keycloak -e KEYCLOAK_DB_USER=keycloak -e KEYCLOAK_DB_PASSWORD=keycloak-ci \
    "$(img postgres)"
  local i ready=0
  for i in $(seq 1 60); do
    if docker exec "$pg" psql -U ehimaya -d ehimaya -tAc "SELECT extname FROM pg_extension WHERE extname='vector'" 2>/dev/null | grep -q vector; then
      echo "database ready"; ready=1; break
    fi
    sleep 2
  done
  [ "$ready" = 1 ] || { docker logs "$pg"; return 1; }

  cd services/api
  setup_uv
  step "Install dependencies"
  uv sync --locked

  step "Lint"
  uv run ruff check .
  uv run ruff format --check .

  step "Type check"
  uv run mypy app

  step "OpenAPI drift"
  uv run python -m app.openapi --check

  step "ERD drift"
  uv run python -m app.erd --check

  step "Validate procedures library"
  uv run python -m app.modules.decision.cli check ../../docs/procedures

  step "Migrate as the owner (up, down, up)"
  (
    export MIGRATION_DATABASE_URL=$DATABASE_URL DATABASE_URL=$RUNTIME_DATABASE_URL
    uv run alembic upgrade head
    uv run alembic downgrade base
    uv run alembic upgrade head
  )

  step "Runtime role cannot migrate"
  if DATABASE_URL=$RUNTIME_DATABASE_URL uv run alembic downgrade -1; then
    echo "the runtime role was able to change the schema"; return 1
  fi

  step "API on the runtime role (anonymous consent + report)"
  api_port=$(free_port)
  (
    export DATABASE_URL=$RUNTIME_DATABASE_URL BACKGROUND_WORKERS=false
    uv run uvicorn app.main:app --port "$api_port" > api.log 2>&1 &
    API_PID=$!
    trap 'kill $API_PID 2>/dev/null || true' EXIT
    for i in $(seq 1 30); do curl -fs "http://127.0.0.1:$api_port/health/ready" && break; sleep 1; done
    KEY=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '=')
    curl -fsS -X POST "http://127.0.0.1:$api_port/api/v1/consents" -H "X-Device-Key: $KEY" -H 'Content-Type: application/json' \
      -d '{"charter_version":"2026-11","locale":"ar","platform":"android"}'
    curl -fsS -X POST "http://127.0.0.1:$api_port/api/v1/reports" -H "X-Device-Key: $KEY" -H 'Content-Type: application/json' \
      -d "{\"client_uuid\":\"$(cat /proc/sys/kernel/random/uuid)\",\"category\":\"sos\",\"location\":{\"lat\":36.8,\"lon\":10.18},\"created_at\":\"$(date -u +%FT%TZ)\"}"
    kill $API_PID; tail -20 api.log
  )

  step "Tests"
  uv run pytest -q

  step "Events library tests against OpenSearch"
  os_port=$(free_port)
  (
    export OPENSEARCH_URL="https://localhost:$os_port" OPENSEARCH_USER=ehimaya
    export OPENSEARCH_CA_FILE="$WORK/opensearch-ca/ca.pem"
    OPENSEARCH_ADMIN_PASSWORD=$(openssl rand -hex 24); OPENSEARCH_PASSWORD=$(openssl rand -hex 24)
    export OPENSEARCH_PASSWORD
    local certs=$RUN_ID-os-certs ca=$RUN_ID-os-ca
    docker volume create --label "$LABEL" "$certs" && docker volume create --label "$LABEL" "$ca"
    docker run --rm --label "$LABEL" --user 0:0 -v "$certs:/certs" -v "$ca:/ca" --entrypoint /bin/sh "$OPENSEARCH_IMAGE" \
      -c "chown 1000:1000 /certs /ca && chmod 0700 /certs"
    docker run -d --name "$opensearch" --label "$LABEL" -p "127.0.0.1:$os_port:9200" \
      -v "$SRC/infra/opensearch/ehimaya-entrypoint.sh:/usr/local/bin/ehimaya-entrypoint.sh:ro" \
      -v "$certs:/usr/share/opensearch/config/certs" -v "$ca:/opensearch-ca" \
      -e OPENSEARCH_ADMIN_PASSWORD="$OPENSEARCH_ADMIN_PASSWORD" -e OPENSEARCH_PASSWORD="$OPENSEARCH_PASSWORD" \
      -e OPENSEARCH_USER=ehimaya -e OPENSEARCH_JAVA_OPTS="-Xms512m -Xmx512m" \
      -e DISABLE_PERFORMANCE_ANALYZER_AGENT_CLI=true -e cluster.routing.allocation.disk.threshold_enabled=false \
      --entrypoint /bin/bash "$OPENSEARCH_IMAGE" /usr/local/bin/ehimaya-entrypoint.sh
    mkdir -p "$(dirname "$OPENSEARCH_CA_FILE")"
    for i in $(seq 1 60); do
      if docker cp "$opensearch:/opensearch-ca/ca.pem" "$OPENSEARCH_CA_FILE" 2>/dev/null \
        && curl -fs --cacert "$OPENSEARCH_CA_FILE" -u "ehimaya:$OPENSEARCH_PASSWORD" \
          "$OPENSEARCH_URL/_cluster/health?wait_for_status=yellow&timeout=4s" >/dev/null; then
        echo "opensearch ready"; break
      fi
      if [ "$i" = 60 ]; then docker logs "$opensearch" | tail -50; exit 1; fi
      sleep 5
    done
    uv run pytest -q tests/test_knowledge.py
  )
}

job_api_image() {
  step "docker build services/api"
  docker build -t "$(img api)" services/api
}

# Inputs of aquasecurity/trivy-action, as the environment its entrypoint gives Trivy (TRIVY_* variables).
trivy() {
  local socket=/var/run/docker.sock
  case ${DOCKER_HOST:-} in unix://*) socket=${DOCKER_HOST#unix://} ;; esac
  mkdir -p "$CACHE/trivy"
  docker run --rm --label "$LABEL" -v "$socket:/var/run/docker.sock" -v "$CACHE/trivy:/cache" \
    -v "$SRC/.github/trivy-secret.yaml:/trivy-secret.yaml:ro" \
    -e TRIVY_CACHE_DIR=/cache -e TRIVY_SECRET_CONFIG=/trivy-secret.yaml "$@"
}

job_image_scan() {
  local entry scan_name context args rc=0
  for entry in "${IMAGE_SCAN[@]}"; do
    if [ "${entry%%|*}" = "$1" ]; then IFS='|' read -r scan_name context args <<< "$entry"; fi
  done
  step "Build"
  # shellcheck disable=SC2086 # the matrix args are several words, as in the workflow
  docker build $args -t "$(img "$scan_name")" "$context"

  step "Trivy (fail on CRITICAL)"
  trivy -e TRIVY_EXIT_CODE=1 -e TRIVY_IGNORE_UNFIXED=true -e TRIVY_SEVERITY=CRITICAL \
    "$TRIVY_IMAGE" image "$(img "$scan_name")" || rc=$?

  step "Trivy report (HIGH and CRITICAL, informational)"
  trivy -e TRIVY_EXIT_CODE=0 -e TRIVY_SEVERITY=HIGH,CRITICAL "$TRIVY_IMAGE" image "$(img "$scan_name")"
  if [ "$rc" != 0 ]; then echo "Trivy found a fixable CRITICAL vulnerability (or failed, exit $rc)"; echo "Trivy (fail on CRITICAL)" > "$WORK/step"; fi
  return "$rc"
}

job_telephony() {
  local telephony=$RUN_ID-telephony call_sim=$RUN_ID-call-sim norec=$RUN_ID-norec net=$RUN_ID-tel ari_port i
  step "Build (runtime and call-sim)"
  docker build --target runtime -t "$(img telephony)" services/telephony
  docker build --target call-sim -t "$(img call-sim)" services/telephony

  step "Refuses to start without an ARI password"
  if docker run --rm --label "$LABEL" "$(img telephony)" true 2> err.txt; then echo "started without TELEPHONY_ARI_PASSWORD"; return 1; fi
  grep -q "TELEPHONY_ARI_PASSWORD is required" err.txt

  step "Start Asterisk and call-sim"
  ari_port=$(free_port)
  docker network create --label "$LABEL" "$net"
  # The alias keeps the host name call-sim dials ("telephony") although the container name is unique.
  docker run -d --name "$telephony" --label "$LABEL" --network "$net" --network-alias telephony -p "127.0.0.1:$ari_port:8088" \
    -e TELEPHONY_ARI_PASSWORD=ci-ari-password-0123456789 -e TELEPHONY_SIM_PASSWORD=ci-sim-password-0123456789 \
    "$(img telephony)"
  for i in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$telephony")" = healthy ] && break; sleep 2
  done
  docker inspect -f '{{.State.Health.Status}}' "$telephony" | grep -qx healthy

  step "Version, user, modules, dialplan, ARI"
  ast() { docker exec "$telephony" asterisk -C /run/asterisk/etc/asterisk.conf -rx "$1"; }
  ast "core show version" | tee version.txt
  grep -q "^Asterisk 22\." version.txt
  [ "$(docker exec "$telephony" id -u)" = 10001 ]
  local module notice monitor queue
  for module in chan_pjsip res_pjsip_transport_websocket res_srtp app_queue app_mixmonitor app_confbridge \
                res_ari res_ari_channels res_ari_asterisk res_stasis res_pjsip_header_funcs \
                res_clioriginate codec_alaw format_wav; do
    ast "module show like $module" | grep -q "^$module.so .*Running" || { echo "module $module not running"; return 1; }
  done
  if ast "module show" | grep -E "^(chan_sip|chan_iax2|cdr_|cel_|res_config_)"; then return 1; fi
  ast "pjsip show transports" | grep -q "transport-wss"
  ast "dialplan show 8000@ehimaya-entry" > entry.txt
  notice=$(grep -n "notice-ar&ehimaya/notice-fr" entry.txt | cut -d: -f1)
  monitor=$(grep -n "MixMonitor" entry.txt | cut -d: -f1)
  queue=$(grep -n "Queue(operators" entry.txt | head -1 | cut -d: -f1)
  [ -n "$notice" ] && [ "$notice" -lt "$monitor" ] && [ "$monitor" -lt "$queue" ]
  docker exec "$telephony" test -s /var/lib/asterisk/sounds/ehimaya/notice-ar.wav
  docker exec "$telephony" test -s /var/lib/asterisk/sounds/ehimaya/notice-fr.wav
  curl -fsS -u ehimaya-api:ci-ari-password-0123456789 "http://127.0.0.1:$ari_port/ari/asterisk/info" | grep -q '"version":"22\.'
  [ "$(curl -s -o /dev/null -w '%{http_code}' -u ehimaya-api:wrong-password-0000 "http://127.0.0.1:$ari_port/ari/asterisk/info")" = 401 ]

  step "Recording can be switched off"
  docker run -d --name "$norec" --label "$LABEL" -e TELEPHONY_ARI_PASSWORD=ci-ari-password-0123456789 \
    -e TELEPHONY_RECORDING_ENABLED=false "$(img telephony)"
  sleep 8
  docker logs "$norec" 2>&1 | grep -q "recording=0"
  docker rm -f "$norec"

  step "A simulated call reaches the operators queue after the notice"
  docker run -d --name "$call_sim" --label "$LABEL" --network "$net" -e TELEPHONY_SIM_PASSWORD=ci-sim-password-0123456789 \
    -e CALL_SIM_FIRST_DELAY_S=2 -e CALL_SIM_TALK_S=40 -e CALL_SIM_INTERVAL_S=600 "$(img call-sim)"
  for i in $(seq 1 45); do
    ast "queue show operators" | grep -q "PJSIP/call-sim" && break
    sleep 1
  done
  ast "queue show operators" | tee queue.txt
  grep -q "PJSIP/call-sim" queue.txt
  docker exec "$telephony" sh -c 'ls /var/spool/asterisk/ehimaya/*.wav'
}
on_failure_telephony() {
  docker logs "$RUN_ID-telephony" 2>&1 | tail -100 || true
  docker logs "$RUN_ID-call-sim" 2>&1 | tail -50 || true
}

# lint, types, tests of a uv project (notify-sim, ai, vision: identical steps).
uv_checks() {
  cd "$1"
  setup_uv
  step "uv sync --locked"
  uv sync --locked
  step "Lint"
  uv run ruff check .
  uv run ruff format --check .
  step "Type check"
  uv run mypy app
  step "Tests"
  uv run pytest -q
}

job_notify_sim() { uv_checks services/notify-sim; }

job_notify_sim_image() {
  local sim=$RUN_ID-sim i
  step "docker build services/notify-sim"
  docker build -t "$(img notify-sim)" services/notify-sim
  step "Starts healthy and writes the service account"
  docker run -d --name "$sim" --label "$LABEL" "$(img notify-sim)"
  for i in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$sim")" = healthy ] && break
    sleep 2
  done
  docker inspect -f '{{.State.Health.Status}}' "$sim" | grep -q healthy
  docker exec "$sim" python -c "import json; a = json.load(open('/data/fcm-service-account.json')); assert a['type'] == 'service_account', a"
}

job_keycloak_realms() {
  local kc=$RUN_ID-kc port http_port otp_port i
  port=$(free_port)
  http_port=$(free_port)
  otp_port=$(free_port)
  step "Build Keycloak with the e-Himaya providers (phase A: ehimaya-phone-otp and its unit tests)"
  docker build -t "$(img keycloak)" infra/keycloak
  step "Import both realms into a throwaway Keycloak"
  docker run -d --name "$kc" --label "$LABEL" -p "127.0.0.1:$port:9000" -p "127.0.0.1:$http_port:8080" \
    --add-host=host.docker.internal:host-gateway \
    -e KC_HEALTH_ENABLED=true -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
    -e OTP_SMS_SECRET=ci-only-otp-secret-ci-only-otp-0001 -e EHIMAYA_API_INTERNAL_URL="http://host.docker.internal:$otp_port" \
    -v "$PWD/infra/keycloak/realms:/opt/keycloak/data/import:ro" \
    "$(img keycloak)" start-dev --import-realm
  for i in $(seq 1 60); do
    if curl -fs "http://localhost:$port/health/ready" >/dev/null; then break; fi
    sleep 3
  done
  docker logs "$kc" 2>&1 | tee kc.log | tail -20
  grep -q "Realm 'ehimaya-public' imported" kc.log
  grep -q "Realm 'ehimaya-staff' imported" kc.log
  step "Staff tokens prove the second factor (amr)"
  python3 infra/keycloak/check_mfa.py "http://localhost:$http_port"
  step "Phone sign-in with an SMS code (phase A)"
  OTP_SMS_SECRET=ci-only-otp-secret-ci-only-otp-0001 python3 infra/keycloak/check_phone_otp.py "http://localhost:$http_port" "$otp_port"
}

job_ai() {
  export AI_SERVICE_TOKEN=ci-only-token-ci-only-token-0001
  uv_checks services/ai
}

job_ai_images() {
  step "docker build --target runtime services/ai"
  docker build --target runtime -t "$(img ai)" services/ai
  step "docker build --target models services/ai"
  docker build --target models -t "$(img ai-models)" services/ai
}

job_ai_models() {
  local ollama=$RUN_ID-ollama ollama_port ai_port media_port python i
  export MODELS="$CACHE/ai-models" OLLAMA_DIR="$CACHE/ollama" SAMPLES="$WORK/samples"
  export AI_SERVICE_TOKEN=ci-only-token-ci-only-token-0001
  ollama_port=$(free_port)
  export AI_OLLAMA_URL="http://localhost:$ollama_port" AI_LLM_MODEL=qwen3:1.7b

  step "Free disk space for the models"
  echo "not run locally: it deletes toolchains of the hosted runner image"
  setup_uv
  uv python install 3.12
  python=$(uv python find 3.12)   # actions/setup-python 3.12

  step "Start Ollama"
  mkdir -p "$OLLAMA_DIR"
  docker run -d --name "$ollama" --label "$LABEL" -p "127.0.0.1:$ollama_port:11434" -v "$OLLAMA_DIR:/root/.ollama" "$OLLAMA_IMAGE"
  for i in $(seq 1 30); do curl -fs "$AI_OLLAMA_URL/api/tags" >/dev/null && break; sleep 2; done

  step "Download, convert and check the models (profile ci)"
  "$python" -m venv "$WORK/convert"
  "$WORK/convert/bin/pip" install -q --extra-index-url https://download.pytorch.org/whl/cpu -r services/ai/models/requirements.txt
  "$WORK/convert/bin/python" services/ai/models/fetch_models.py --profile ci --out "$MODELS" --ollama "$AI_OLLAMA_URL"

  step "Speech samples (espeak-ng)"
  if ! command -v espeak-ng >/dev/null; then as_root apt-get update -q && as_root apt-get install -y -q espeak-ng; fi
  mkdir -p "$SAMPLES"
  espeak-ng -v fr -s 115 -w "$SAMPLES/fr.wav" "Bonjour, il y a un incendie dans la forêt près de la maison."
  espeak-ng -v en -s 140 -w "$SAMPLES/en.wav" "Hello, there is a fire in the building and two people are trapped."
  espeak-ng -v ar -s 130 -w "$SAMPLES/ar.wav" "يوجد حريق كبير في الغابة قرب الطريق"
  head -c 20000 /dev/urandom > "$SAMPLES/garbage.wav"

  step "Tests against the real models"
  (
    cd services/ai
    uv sync --locked
    AI_MODELS_DIR="$MODELS" AI_TEST_AUDIO_DIR="$SAMPLES" uv run pytest -o addopts="" -m models -v -s
  )

  step "API ↔ AI service contract"
  ai_port=$(free_port)
  media_port=$(free_port)
  (
    cd services/ai
    AI_MODELS_DIR="$MODELS" AI_MEDIA_URL_PREFIX="http://127.0.0.1:$media_port/" uv run uvicorn app.main:app --port "$ai_port" &
    (cd "$SAMPLES" && exec "$python" -m http.server "$media_port" --bind 127.0.0.1) &
    trap stop_background EXIT
    for i in $(seq 1 30); do curl -fs "http://127.0.0.1:$ai_port/health/live" >/dev/null && break; sleep 1; done
    cd ../api && uv sync --locked
    DATABASE_URL=postgresql+asyncpg://unused:unused@localhost/unused \
    ANON_PSEUDONYM_SECRET=ci-only-secret-ci-only-secret-ci-only-01 \
    FIELD_ENCRYPTION_KEY=Y2ktb25seS1rZXktY2ktb25seS1rZXktY2ktb25seTE= \
    PYTHONPATH="$PWD" uv run python ../ai/tests/api_contract_check.py "http://127.0.0.1:$ai_port" "$AI_SERVICE_TOKEN" "http://127.0.0.1:$media_port/fr.wav"
  )
}
on_finish_ai_models() {
  # "Make the model cache readable": Ollama writes as root into the cache.
  [ "$(id -u)" = 0 ] || sudo -n chown -R "$(id -u)" "$CACHE/ollama" 2>/dev/null || true
}

job_vision() {
  export VISION_API_TOKEN=ci-only-token-ci-only-token-0001
  export VISION_CALLBACK_TOKEN=ci-only-callback-ci-only-callback-01
  uv_checks services/vision
}

job_vision_models() {
  local vision=$RUN_ID-vision volume=$RUN_ID-visionmodels port i SAMPLE
  export MODELS="$CACHE/vision-models"
  export VISION_API_TOKEN=ci-only-token-ci-only-token-0001
  export VISION_CALLBACK_TOKEN=ci-only-callback-ci-only-callback-01
  setup_uv
  # actions/cache of services/vision/eval/cache: kept between runs in $CACHE.
  mkdir -p "$CACHE/vision-eval"
  ln -sfn "$CACHE/vision-eval" services/vision/eval/cache

  step "Download and check the models"
  python3 services/vision/models/fetch_models.py --out "$MODELS"

  step "Tests against the real models"
  (cd services/vision && uv sync --locked && VISION_MODELS_DIR="$MODELS" uv run pytest -o addopts="" -m models -v -s)

  step "Evaluation on the held-out sample (frame-level precision/recall, CPU latency)"
  (cd services/vision && VISION_MODELS_DIR="$MODELS" uv run python eval/evaluate.py --threads 2 --json eval/results.json)

  step "Images work together (models job → volume → healthy service)"
  port=$(free_port)
  docker build --target models -t "$(img vision-models)" services/vision
  docker build --target runtime -t "$(img vision)" services/vision
  docker volume create --label "$LABEL" "$volume"
  docker run --rm --label "$LABEL" -v "$volume:/models" "$(img vision-models)"
  docker run -d --name "$vision" --label "$LABEL" -v "$volume:/models:ro" \
    -e VISION_API_TOKEN -e VISION_CALLBACK_TOKEN -p "127.0.0.1:$port:8100" "$(img vision)"
  for i in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$vision")" = healthy ] && break
    sleep 2
  done
  curl -fsS "http://127.0.0.1:$port/healthz" | tee health.json
  python3 -c "import json; h=json.load(open('health.json')); assert h['status'] == 'ok', h"
  curl -fsS -H "Authorization: Bearer $VISION_API_TOKEN" "http://127.0.0.1:$port/v1/model"
  SAMPLE=$(python3 -c "import json; print(json.load(open('services/vision/eval/samples.json'))['samples'][0]['id'])")
  curl -fsS -H "Authorization: Bearer $VISION_API_TOKEN" -F "image=@services/vision/eval/cache/$SAMPLE.jpg;type=image/jpeg" \
    "http://127.0.0.1:$port/v1/detect"
}
on_failure_vision_models() { docker logs "$RUN_ID-vision" 2>&1 | tail -100 || true; }

# The stack runs under its own compose project with an override file (written here, outside the repository) that
# (1) tags the images it builds ehimaya/<name>:<run> instead of :dev, so your development images are untouched, and
# (2) publishes only the ports the smoke test calls, on random host ports, so a running development stack does not
# collide. The smoke test reads those URLs from its documented environment variables.
stack_compose() {
  docker compose -p "$STACK_PROJECT" --env-file .env -f infra/compose.yml -f "$WORK/stack-override.yml" "$@"
}

job_stack() {
  step "Generate a throwaway .env"
  cp .env.example .env
  sed -i "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)|" .env
  sed -i "s|^ANON_PSEUDONYM_SECRET=.*|ANON_PSEUDONYM_SECRET=$(openssl rand -hex 32)|" .env
  sed -i "s|^TUSD_HOOK_SECRET=.*|TUSD_HOOK_SECRET=$(openssl rand -hex 24)|" .env
  sed -i "s|^AI_SERVICE_TOKEN=.*|AI_SERVICE_TOKEN=$(openssl rand -hex 24)|" .env
  sed -i "s|^CERTIFICATE_SIGNING_KEY=.*|CERTIFICATE_SIGNING_KEY=$(openssl rand -base64 32)|" .env
  sed -i "s|^MEDIAMTX_HOOK_TOKEN=.*|MEDIAMTX_HOOK_TOKEN=$(openssl rand -hex 24)|" .env
  sed -i "s|^MEDIAMTX_API_PASSWORD=.*|MEDIAMTX_API_PASSWORD=$(openssl rand -hex 24)|" .env
  sed -i "s|^TELEPHONY_ARI_PASSWORD=.*|TELEPHONY_ARI_PASSWORD=$(openssl rand -hex 24)|" .env
  sed -i "s|^TELEPHONY_SIM_PASSWORD=.*|TELEPHONY_SIM_PASSWORD=$(openssl rand -hex 24)|" .env
  sed -i "s|^TELEPHONY_SIM_TOKEN=.*|TELEPHONY_SIM_TOKEN=$(openssl rand -hex 24)|" .env
  sed -i "s|^SMS_INBOUND_SECRET=.*|SMS_INBOUND_SECRET=$(openssl rand -hex 32)|" .env
  sed -i "s|^OTP_SMS_SECRET=.*|OTP_SMS_SECRET=$(openssl rand -hex 32)|" .env

  step "Production overlay renders (Caddy, Keycloak start, no host ports but 80/443, streaming and telephony)"
  cat > prod.env <<EOF
API_HOST=api.ehimaya.test
DASHBOARD_HOST=dashboard.ehimaya.test
PORTAL_HOST=portal.ehimaya.test
AUTH_HOST=auth.ehimaya.test
MEDIA_HOST=media.ehimaya.test
EHIMAYA_DB_RUNTIME_PASSWORD=$(openssl rand -hex 24)
TUSD_CORS_ORIGIN_REGEX=^https://(dashboard|portal)\.ehimaya\.test\$
OPENSEARCH_ADMIN_PASSWORD=$(openssl rand -hex 24)
OPENSEARCH_PASSWORD=$(openssl rand -hex 24)
ALERT_EMAIL_TO=ops@ehimaya.test
EOF
  cat .env prod.env > prod-full.env
  docker compose --env-file prod-full.env -f infra/compose.yml -f infra/compose.prod.yml config > prod.yml
  python3 -c "import yaml; s=yaml.safe_load(open('prod.yml'))['services']; p={n:sorted(str(x.get('published'))+'/'+x.get('protocol','tcp') for x in v.get('ports',[])) for n,v in s.items() if v.get('ports')}; print(p); assert set(p)=={'caddy','mediamtx','telephony'}, p; assert p['mediamtx']==['1935/tcp','8189/udp','8554/tcp'], p; assert set(p['telephony'])=={'5060/tcp','5060/udp','5061/tcp'}|{f'{n}/udp' for n in range(10000,10100)}, p['telephony']; assert all('8088' not in x for x in p['telephony']); assert 'notify-sim' not in s and 'mailpit' not in s and 'stream-sim' not in s and 'call-sim' not in s; e=s['worker']['environment']; assert e['TELEPHONY_RECORDING_ENABLED']=='false' and e['TELEPHONY_SIM_TOKEN']=='' and e['TELEPHONY_WS_PUBLIC_URL']=='wss://api.ehimaya.test/telephony/ws', e"

  step "Terrain one-shot service renders (opt-in profile)"
  docker compose --env-file .env -f infra/compose.yml --profile terrain config -q

  step "Start the stack"
  local api_port tus_port sim_port hls_port
  api_port=$(free_port); tus_port=$(free_port); sim_port=$(free_port); hls_port=$(free_port)
  docker compose --env-file .env -f infra/compose.yml config --format json | python3 -c '
import json, sys
run, published = sys.argv[1], {}
for arg in sys.argv[2:]:  # <service>:<container port>=<host port>
    service, rest = arg.split(":")
    target, host = rest.split("=")
    published.setdefault(service, []).append(f"127.0.0.1:{host}:{target}")
print("services:")
for name, service in json.load(sys.stdin)["services"].items():
    lines = []
    repository = service.get("image", "").split(":")[0]
    if repository.startswith("ehimaya/"):
        lines.append(f"    image: {repository}:{run}")
    if service.get("ports"):
        ports = published.get(name)
        lines.append(f"    ports: !override {json.dumps(ports)}" if ports else "    ports: !reset []")
    if lines:
        print(f"  {name}:", *lines, sep="\n")
' "$RUN_ID" "api:8000=$api_port" "tusd:1080=$tus_port" "notify-sim:8090=$sim_port" "mediamtx:8888=$hls_port" \
    > "$WORK/stack-override.yml"
  cat "$WORK/stack-override.yml"
  stack_compose up -d --build

  step "Anonymous report, resumable upload, integrity check, notify-sim health"
  API_URL="http://127.0.0.1:$api_port" TUS_URL="http://127.0.0.1:$tus_port/api/v1/uploads/" \
    NOTIFY_SIM_URL="http://127.0.0.1:$sim_port" MEDIAMTX_HLS_URL="http://127.0.0.1:$hls_port" \
    SMOKE_COMPOSE="docker compose -p $STACK_PROJECT --env-file .env -f infra/compose.yml -f $WORK/stack-override.yml" \
    python3 infra/smoke/smoke_test.py

  step "Certificate PDFs render in the API image (Arabic shaping, fonts)"
  stack_compose exec -T api python -c "
from weasyprint import HTML
pdf = HTML(string='<html dir=rtl><body><h1>شهادة السلامة الرقمية</h1><p>Certificat</p></body></html>').write_pdf()
assert pdf.startswith(b'%PDF') and len(pdf) > 2000, len(pdf)
print('pdf ok', len(pdf))"
}
on_failure_stack() { stack_compose logs --tail=200 2>&1 || true; }
on_finish_stack() { [ -f "$WORK/stack-override.yml" ] && stack_compose down -v --remove-orphans >/dev/null 2>&1 || true; }

# npm ci, lint, typecheck, test, build of a Vite app (dashboard, portal).
npm_checks() {
  cd "$1"
  step "Install dependencies"
  npm ci
  step "Lint"
  npm run lint
  step "Type check"
  npm run typecheck
  step "Tests"
  npm test
  step "Build"
  npm run build
}

job_dashboard() {
  npm_checks apps/dashboard
  step "Install Playwright Chromium"
  if [ -n "${PLAYWRIGHT_CHROMIUM_EXECUTABLE:-}" ]; then
    echo "using the preinstalled Chromium $PLAYWRIGHT_CHROMIUM_EXECUTABLE (PLAYWRIGHT_CHROMIUM_EXECUTABLE)"
  elif have_root; then
    npx playwright install --with-deps chromium
  else
    echo "no root/passwordless sudo: browser system libraries (--with-deps) are assumed to be installed"
    npx playwright install chromium
  fi
  step "Browser tests"
  npm run test:e2e
}

job_portal() {
  npm_checks apps/portal
  step "Install Playwright Chromium"
  if [ -n "${PLAYWRIGHT_CHROMIUM_EXECUTABLE:-}" ]; then
    echo "using the preinstalled Chromium $PLAYWRIGHT_CHROMIUM_EXECUTABLE (PLAYWRIGHT_CHROMIUM_EXECUTABLE)"
  elif have_root; then
    npx playwright install --with-deps chromium
  else
    echo "no root/passwordless sudo: browser system libraries (--with-deps) are assumed to be installed"
    npx playwright install chromium
  fi
  step "Browser tests"
  npm run test:e2e
}

promtool_run() {
  if command -v promtool >/dev/null; then
    (cd infra/monitoring && promtool "$@")
  else
    docker run --rm -v "$PWD/infra/monitoring:/m:ro" -w /m --entrypoint promtool prom/prometheus:v3.5.0@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996 "$@"
  fi
}

job_quality() {
  step "Traceability up to date"
  python3 scripts/traceability.py --check
  step "Alert rules (promtool check and unit tests)"
  promtool_run check config prometheus.yml --syntax-only
  promtool_run check rules alerts.yml
  promtool_run test rules alerts.test.yml
}

job_backup_drill() {
  setup_uv
  step "Install API dependencies (migrations)"
  (cd services/api && uv sync --locked)
  step "Restore drill"
  PG_BIN=${PG_BIN:-/usr/lib/postgresql/16/bin} sh infra/backup/drill.sh
}

job_supply_chain() {
  setup_uv
  step "Install web dependencies"
  (cd apps/dashboard && npm ci --ignore-scripts)
  (cd apps/portal && npm ci --ignore-scripts)
  step "Dependency audit (pip-audit, npm audit)"
  python3 scripts/dep_audit.py
  step "Licences"
  mkdir -p "$WORK/sbom"
  local svc app
  for svc in api ai vision notify-sim; do
    (cd "services/$svc" && uv export --frozen --no-dev --no-hashes --no-emit-project -o "$WORK/sbom/$svc-requirements.txt" >/dev/null)
  done
  python3 scripts/licences.py python "$WORK"/sbom/*-requirements.txt
  python3 scripts/licences.py npm apps/dashboard apps/portal
  step "SBOMs (CycloneDX)"
  for svc in api ai vision notify-sim; do
    uvx --from cyclonedx-bom==7.5.0 cyclonedx-py requirements "$WORK/sbom/$svc-requirements.txt" -o "$WORK/sbom/$svc.cdx.json"
  done
  for app in dashboard portal; do
    (cd "apps/$app" && npx --yes @cyclonedx/cyclonedx-npm@6.0.1 --omit dev --output-file "$WORK/sbom/$app.cdx.json")
  done
  mkdir -p "$LOGS/sbom" && cp "$WORK"/sbom/*.cdx.json "$LOGS/sbom/"
  echo "SBOMs in ${LOGS#"$ROOT"/}/sbom/"
}

job_mobile() {
  cd apps/mobile
  step "System SQLite for host tests"
  if ldconfig -p | grep -q 'libsqlite3\.so '; then
    echo "libsqlite3-dev already installed"
  else
    as_root apt-get update && as_root apt-get install -y --no-install-recommends libsqlite3-dev
  fi
  step "Dependencies"
  flutter pub get
  step "Format"
  dart format --output=none --set-exit-if-changed .
  step "Analyze"
  flutter analyze
  step "Test"
  flutter test
  step "Free runner disk space"
  echo "not run locally: it deletes toolchains of the hosted runner image"
  step "Build debug APK"
  flutter build apk --debug
}

# ── Runner ───────────────────────────────────────────────────────────────────────────────────────────────────────
RESULTS=()   # "<unit>|<PASS|FAIL|SKIPPED>|<seconds>|<note>"
record() { RESULTS+=("$1|$2|$3|$4"); }
duration() { printf '%d:%02d' $(($1 / 60)) $(($1 % 60)); }

run_unit() {
  local unit=$1 base=${1%%:*} arg="" reason start rc log
  [ "$unit" = "$base" ] || arg=${unit#*:}
  reason=$(skip_reason "$unit") || true
  if [ -n "$reason" ]; then
    printf '\n▶ %s: SKIPPED (%s)\n' "$unit" "$reason"
    record "$unit" SKIPPED 0 "$reason"
    return 0
  fi
  log="$LOGS/${unit//:/-}.log"
  printf '\n▶ %s (log: %s)\n' "$unit" "${log#"$ROOT"/}"
  : > "$WORK/step"
  start=$SECONDS
  # The caller runs this with set +e (see the main loop), so a failing job does not stop the script here.
  (
    set -euo pipefail
    export CI=true
    cd "$SRC"
    trap stop_background EXIT
    "job_${base//-/_}" ${arg:+"$arg"}
  ) 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  if [ "$rc" != 0 ] && declare -F "on_failure_${base//-/_}" >/dev/null; then
    (cd "$SRC" && "on_failure_${base//-/_}") 2>&1 | tee -a "$log" || true
  fi
  if declare -F "on_finish_${base//-/_}" >/dev/null; then (cd "$SRC" && "on_finish_${base//-/_}") || true; fi
  docker_cleanup
  if [ "$rc" = 0 ]; then
    record "$unit" PASS $((SECONDS - start)) ""
  else
    record "$unit" FAIL $((SECONDS - start)) "failed at step: $(cat "$WORK/step") (exit $rc, see ${log#"$ROOT"/})"
  fi
  return "$rc"
}

summary() {
  local row unit status seconds note failed=0
  printf '\n%-24s %-8s %8s  %s\n' JOB RESULT DURATION NOTE
  for row in "${RESULTS[@]}"; do
    IFS='|' read -r unit status seconds note <<< "$row"
    printf '%-24s %-8s %8s  %s\n' "$unit" "$status" "$(duration "$seconds")" "$note"
    [ "$status" != FAIL ] || failed=1
  done
  {
    echo "## Local CI run (scripts/ci-local.sh)"
    echo
    echo "- Commit: \`$COMMIT\`"
    echo "- Date: $(date -u '+%Y-%m-%d %H:%M UTC')"
    echo "- Machine: $(uname -sm), $(nproc 2>/dev/null || echo '?') CPUs, Docker $(docker version -f '{{.Server.Version}}' 2>/dev/null || echo 'not available')"
    echo
    echo "| Job | Result | Duration | Notes |"
    echo "|---|---|---|---|"
    for row in "${RESULTS[@]}"; do
      IFS='|' read -r unit status seconds note <<< "$row"
      echo "| \`$unit\` | $status | $(duration "$seconds") | ${note//|/\\|} |"
    done
    echo
    echo "SKIPPED means the check did not run on this machine (reason given): it is not a pass."
  } > "$REPORT"
  printf '\nReport written to %s\n' "${REPORT#"$ROOT"/}"
  return "$failed"
}

mkdir -p "$LOGS" "$CACHE"
rm -f "$LOGS"/*.log
echo "ci-local: testing commit $COMMIT ($(git -C "$ROOT" log -1 --format=%s "$COMMIT"))"
[ -z "$(git -C "$ROOT" status --porcelain)" ] || echo "ci-local: note: uncommitted changes are not tested (clean checkout of the commit)"
git -C "$ROOT" worktree add --detach --quiet "$SRC" "$COMMIT"

stopped=""
for unit in "${UNITS[@]}"; do
  if [ -n "$stopped" ]; then
    record "$unit" SKIPPED 0 "not run: $stopped failed (use --keep-going to run every job)"
    continue
  fi
  # Not "if run_unit": bash would then ignore set -e inside the job.
  set +e
  run_unit "$unit"
  rc=$?
  set -e
  if [ "$rc" != 0 ] && [ "$KEEP_GOING" = 0 ]; then stopped=$unit; fi
done
summary
