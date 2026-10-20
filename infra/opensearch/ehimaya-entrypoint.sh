#!/bin/bash
# محرّك البحث في مكتبة الأحداث — تهيئة آمنة لـ OpenSearch (عقدة واحدة، إضافة الأمان مفعّلة).
# OpenSearch 2 for the events library (docs/api/phase-8-contract.md §2): single node, security plugin ON, never the
# demo configuration (its certificates and users are public). On every start this script:
#   1. refuses to start without OPENSEARCH_ADMIN_PASSWORD and OPENSEARCH_PASSWORD (random, >= 16 characters, distinct,
#      never "admin");
#   2. on first start, creates this installation's own CA, node certificate (TLS on HTTP and transport) and admin
#      client certificate with keytool, in the opensearch-certs volume (private keys never leave it), and copies the
#      CA certificate to the opensearch-ca volume the API mounts read-only to verify the node;
#   3. writes the security configuration: HTTP basic auth against the internal users only, two users — "admin"
#      (all_access, operations) and the API's user (OPENSEARCH_USER, role ehimaya_api: its own indices only);
#   4. starts OpenSearch; once it answers, re-applies that configuration with securityadmin (admin certificate), so a
#      password changed in .env takes effect on the next restart.
set -euo pipefail

OS_HOME=/usr/share/opensearch
CONF="$OS_HOME/config"
CERTS="$CONF/certs"
SECURITY="$CONF/opensearch-security"
CA_OUT=${OPENSEARCH_CA_DIR:-/opensearch-ca}
KEYTOOL="$OS_HOME/jdk/bin/keytool"
TOOLS="$OS_HOME/plugins/opensearch-security/tools"
API_USER=${OPENSEARCH_USER:-ehimaya}
PREFIX=${OPENSEARCH_INDEX_PREFIX:-ehimaya}
NODE_DN="CN=opensearch,OU=node,O=ehimaya"
ADMIN_DN="CN=admin,OU=ops,O=ehimaya"

fail() { echo "opensearch: $*" >&2; exit 1; }
check_password() {
  local name=$1 value=$2
  [ -n "$value" ] || fail "$name is required (openssl rand -hex 24)"
  [ "${#value}" -ge 16 ] || fail "$name must be at least 16 characters"
  [ "$value" != "admin" ] || fail "$name must not be the default password"
  case "$value" in *change-me*|*changeme*) fail "$name still holds the example value";; esac
}
check_password OPENSEARCH_ADMIN_PASSWORD "${OPENSEARCH_ADMIN_PASSWORD:-}"
check_password OPENSEARCH_PASSWORD "${OPENSEARCH_PASSWORD:-}"
[ "$OPENSEARCH_ADMIN_PASSWORD" != "$OPENSEARCH_PASSWORD" ] || fail "the admin and API passwords must differ"
[[ "$API_USER" =~ ^[a-z][a-z0-9_-]{2,30}$ ]] && [ "$API_USER" != admin ] || fail "invalid OPENSEARCH_USER"
[[ "$PREFIX" =~ ^[a-z][a-z0-9-]{0,30}$ ]] || fail "invalid OPENSEARCH_INDEX_PREFIX"

# ---------------------------------------------------------------- certificates (first start)
mkdir -p "$CERTS"
if [ ! -s "$CERTS/node.p12" ]; then
  echo "opensearch: creating this installation's CA and certificates"
  umask 077
  rm -f "$CERTS"/*.p12 "$CERTS"/*.pem "$CERTS"/keystore.pass
  head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40 > "$CERTS/keystore.pass"
  pass=$(cat "$CERTS/keystore.pass")
  kt() { "$KEYTOOL" -noprompt -storetype PKCS12 -storepass "$pass" "$@" >/dev/null 2>&1; }
  kt -genkeypair -alias ca -keyalg RSA -keysize 3072 -validity 3650 -dname "CN=ehimaya-opensearch-ca,O=ehimaya" \
     -ext "BC:c=ca:true" -ext "KU:c=keyCertSign,cRLSign" -keystore "$CERTS/ca.p12"
  "$KEYTOOL" -exportcert -rfc -alias ca -keystore "$CERTS/ca.p12" -storetype PKCS12 -storepass "$pass" \
     -file "$CERTS/ca.pem" >/dev/null 2>&1
  kt -importcert -alias ca -file "$CERTS/ca.pem" -keystore "$CERTS/truststore.p12"
  issue() {  # alias dn extensions...
    local alias=$1 dn=$2; shift 2
    kt -genkeypair -alias "$alias" -keyalg RSA -keysize 2048 -validity 825 -dname "$dn" -keystore "$CERTS/$alias.p12"
    "$KEYTOOL" -certreq -alias "$alias" -keystore "$CERTS/$alias.p12" -storetype PKCS12 -storepass "$pass" \
      | "$KEYTOOL" -gencert -rfc -alias ca -keystore "$CERTS/ca.p12" -storetype PKCS12 -storepass "$pass" \
          -validity 825 "$@" > "$CERTS/$alias.pem"
    kt -importcert -alias ca -file "$CERTS/ca.pem" -keystore "$CERTS/$alias.p12"
    kt -importcert -alias "$alias" -file "$CERTS/$alias.pem" -keystore "$CERTS/$alias.p12"
  }
  issue node "$NODE_DN" -ext "SAN=dns:opensearch,dns:localhost,ip:127.0.0.1" -ext "EKU=serverAuth,clientAuth" \
    -ext "KU=digitalSignature,keyEncipherment"
  issue admin "$ADMIN_DN" -ext "EKU=clientAuth" -ext "KU=digitalSignature,keyEncipherment"
  rm -f "$CERTS/ca.p12.old"
  umask 022
fi
pass=$(cat "$CERTS/keystore.pass")
if [ ! -s "$CERTS/salt" ]; then
  (umask 077; head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16 > "$CERTS/salt")
fi
salt=$(cat "$CERTS/salt")
if [ -d "$CA_OUT" ] && [ -w "$CA_OUT" ]; then
  cp "$CERTS/ca.pem" "$CA_OUT/ca.pem.tmp" && chmod 644 "$CA_OUT/ca.pem.tmp" && mv "$CA_OUT/ca.pem.tmp" "$CA_OUT/ca.pem"
fi

# ---------------------------------------------------------------- node configuration
cat > "$CONF/opensearch.yml" <<EOF
cluster.name: ehimaya-library
node.name: opensearch
network.host: 0.0.0.0
discovery.type: single-node
bootstrap.memory_lock: false
# Index names are explicit: no index is ever created by a write to a missing name.
action.auto_create_index: false
action.destructive_requires_name: false
plugins.security.ssl.transport.keystore_type: PKCS12
plugins.security.ssl.transport.keystore_filepath: certs/node.p12
plugins.security.ssl.transport.keystore_password: "$pass"
plugins.security.ssl.transport.truststore_type: PKCS12
plugins.security.ssl.transport.truststore_filepath: certs/truststore.p12
plugins.security.ssl.transport.truststore_password: "$pass"
plugins.security.ssl.transport.enforce_hostname_verification: false
plugins.security.ssl.http.enabled: true
plugins.security.ssl.http.keystore_type: PKCS12
plugins.security.ssl.http.keystore_filepath: certs/node.p12
plugins.security.ssl.http.keystore_password: "$pass"
plugins.security.ssl.http.truststore_type: PKCS12
plugins.security.ssl.http.truststore_filepath: certs/truststore.p12
plugins.security.ssl.http.truststore_password: "$pass"
plugins.security.nodes_dn: ["$NODE_DN"]
plugins.security.authcz.admin_dn: ["$ADMIN_DN"]
plugins.security.allow_default_init_securityindex: true
plugins.security.restapi.roles_enabled: ["all_access"]
plugins.security.system_indices.enabled: true
plugins.security.audit.type: noop
plugins.security.compliance.salt: "$salt"
EOF
chmod 600 "$CONF/opensearch.yml"

# ---------------------------------------------------------------- security configuration
hash() { OPENSEARCH_HASH_SECRET="$1" "$TOOLS/hash.sh" -env OPENSEARCH_HASH_SECRET 2>/dev/null | tail -n 1; }
admin_hash=$(hash "$OPENSEARCH_ADMIN_PASSWORD")
api_hash=$(hash "$OPENSEARCH_PASSWORD")
[[ "$admin_hash" == \$2* && "$api_hash" == \$2* ]] || fail "could not hash the passwords"
cat > "$SECURITY/internal_users.yml" <<EOF
_meta:
  type: "internalusers"
  config_version: 2
admin:
  hash: "$admin_hash"
  reserved: true
  backend_roles: ["admin"]
  description: "e-Himaya operations (all_access)"
$API_USER:
  hash: "$api_hash"
  reserved: true
  description: "e-Himaya API: events library indices only"
EOF
cat > "$SECURITY/roles_mapping.yml" <<EOF
_meta:
  type: "rolesmapping"
  config_version: 2
all_access:
  reserved: true
  backend_roles: ["admin"]
  users: ["admin"]
ehimaya_api:
  reserved: true
  users: ["$API_USER"]
EOF
# Demo roles of the image stay unused (no user is mapped to them); the API's role is appended once.
if ! grep -q '^ehimaya_api:' "$SECURITY/roles.yml"; then
  cat >> "$SECURITY/roles.yml" <<EOF

ehimaya_api:
  reserved: true
  cluster_permissions: ["cluster_monitor", "cluster_composite_ops", "indices:admin/aliases/get"]
  index_permissions:
    - index_patterns: ["$PREFIX-*"]
      allowed_actions: ["indices_all"]
EOF
fi
cat > "$SECURITY/config.yml" <<'EOF'
_meta:
  type: "config"
  config_version: 2
config:
  dynamic:
    http:
      anonymous_auth_enabled: false
    authc:
      basic_internal_auth_domain:
        description: "HTTP basic against the internal users only"
        http_enabled: true
        transport_enabled: true
        order: 0
        http_authenticator:
          type: basic
          challenge: true
        authentication_backend:
          type: intern
EOF

# ---------------------------------------------------------------- start, then re-apply the security configuration
(
  status() { curl -s --cacert "$CERTS/ca.pem" -o /dev/null -w '%{http_code}' -u "$1" https://127.0.0.1:9200/_cluster/health; }
  for _ in $(seq 1 90); do
    sleep 5
    admin=$(status "admin:$OPENSEARCH_ADMIN_PASSWORD" 2>/dev/null || true)
    api=$(status "$API_USER:$OPENSEARCH_PASSWORD" 2>/dev/null || true)
    if [ "$admin" = 200 ] && [ "$api" = 200 ]; then
      exit 0  # the stored security configuration already holds these users and passwords
    fi
    if [ "$admin" = 401 ] || [ "$api" = 401 ]; then
      echo "opensearch: applying the security configuration (users or passwords changed)"
      "$TOOLS/securityadmin.sh" -cd "$SECURITY" -icl -nhnv -h 127.0.0.1 \
        -ks "$CERTS/admin.p12" -kspass "$pass" -kst PKCS12 \
        -ts "$CERTS/truststore.p12" -tspass "$pass" -tst PKCS12 >/dev/null 2>&1 || sleep 25
    fi
  done
  echo "opensearch: could not verify the security configuration" >&2
) &

export DISABLE_INSTALL_DEMO_CONFIG=true
unset OPENSEARCH_ADMIN_PASSWORD OPENSEARCH_PASSWORD
exec "$OS_HOME/opensearch-docker-entrypoint.sh" opensearch
