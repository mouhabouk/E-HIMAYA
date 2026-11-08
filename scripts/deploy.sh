#!/usr/bin/env bash
# Deploys a released version on this server (docs/cicd.md). Run from the checkout of the tag:
#
#   git fetch --tags && git checkout v1.2.0 && scripts/deploy.sh v1.2.0
#
# The release workflow calls it the same way over SSH. Steps:
#   1. checks that every image of the release carries this repository's Sigstore signature (cosign, when installed);
#   2. backs up the database (pg_dump, kept in backups/predeploy-<version>.dump);
#   3. pulls the signed images, builds the dashboard and the portal from this server's .env;
#   4. migrates the database (migrate service), starts everything and waits for the health checks;
#   5. if the stack is not healthy, starts the previous version again (images only: a migration is never undone
#      automatically; the dump of step 2 is there for that, docs/cicd.md §5).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:?usage: scripts/deploy.sh vX.Y.Z}
ENV_FILE=${ENV_FILE:-.env}
REGISTRY=${EHIMAYA_REGISTRY:-ghcr.io/mouhabouk}
REPO=${EHIMAYA_REPOSITORY:-mouhabouk/E-HIMAYA}
STATE=.deployed-version
PROFILES=${DEPLOY_PROFILES:---profile monitoring --profile logs}
[ -f "$ENV_FILE" ] || { echo "deploy: $ENV_FILE is missing (docs/deploy-production.md §3)" >&2; exit 1; }
echo "$VERSION" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$' || { echo "deploy: not a version: $VERSION" >&2; exit 1; }

compose() {
  # shellcheck disable=SC2086
  EHIMAYA_VERSION="$1" EHIMAYA_REGISTRY="$REGISTRY" docker compose --env-file "$ENV_FILE" \
    -f infra/compose.yml -f infra/compose.prod.yml -f infra/compose.release.yml $PROFILES "${@:2}"
}

images() { compose "$1" config --images | grep "^$REGISTRY/ehimaya-" | sort -u; }

previous=$(cat "$STATE" 2>/dev/null || true)
echo "deploy: $previous -> $VERSION"

if command -v cosign >/dev/null; then
  for image in $(images "$VERSION"); do
    cosign verify "$image" \
      --certificate-identity-regexp "^https://github.com/$REPO/.github/workflows/release.yml@" \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com >/dev/null
    echo "signed: $image"
  done
else
  echo "deploy: cosign not installed, signatures not checked (docs/cicd.md §4)" >&2
fi

mkdir -p backups
if compose "$VERSION" ps --status running postgres | grep -q postgres; then
  compose "$VERSION" exec -T postgres pg_dump -U postgres -Fc "${EHIMAYA_DB_NAME:-ehimaya}" > "backups/predeploy-$VERSION.dump"
  echo "deploy: database saved in backups/predeploy-$VERSION.dump"
fi

compose "$VERSION" pull --ignore-buildable --quiet
compose "$VERSION" build dashboard portal
compose "$VERSION" run --rm migrate
if compose "$VERSION" up -d --remove-orphans --wait --wait-timeout 600; then
  echo "$VERSION" > "$STATE"
  echo "deploy: $VERSION is running"
  exit 0
fi

echo "deploy: $VERSION did not become healthy" >&2
compose "$VERSION" ps >&2 || true
if [ -n "$previous" ] && [ "$previous" != "$VERSION" ]; then
  echo "deploy: starting $previous again" >&2
  git checkout -q "$previous"
  compose "$previous" build dashboard portal
  compose "$previous" up -d --remove-orphans --wait --wait-timeout 600 || true
fi
exit 1
