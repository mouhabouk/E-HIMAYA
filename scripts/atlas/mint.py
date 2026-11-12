"""Signs a staff token for the atlas capture (scripts/atlas/capture.mjs) with the local key of scripts/atlas/run.sh.

SIMULATION: only the API instance started by run.sh trusts this key (its OIDC_ISSUERS points at the local JWKS).
    python3 mint.py <role,role> '{"name": "...", "scope_level": "regional", "gouvernorat_code": 61}'
"""

import json
import os
import sys
import time

import jwt

roles = sys.argv[1].split(",")
extra = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
now = int(time.time())
claims = {
    "iss": os.environ.get("ATLAS_ISSUER", "http://localhost:8099/realms/ehimaya-staff"),
    "sub": "atlas-" + "-".join(sorted(roles))[:40],
    "aud": "ehimaya-api",
    "azp": "ehimaya-dashboard",
    "exp": now + 3 * 3600,
    "iat": now,
    "amr": ["pwd", "otp"],
    "preferred_username": "atlas",
    "realm_access": {"roles": roles},
    "scope_level": "national",
    **extra,
}
with open(os.environ["ATLAS_KEY"], encoding="utf-8") as f:
    print(jwt.encode(claims, f.read(), algorithm="RS256", headers={"kid": "atlas"}))
