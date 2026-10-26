"""Proves that the staff realm puts the second factor in the token (phase 10, docs/api/phase-10-contract.md §1.1).

Against a Keycloak that imported infra/keycloak/realms (CI job "Keycloak · realm import", scripts/ci-local.sh):
creates a throwaway staff account, signs in through the dashboard's browser flow (authorization code + PKCE) and
checks the access token's ``amr`` claim:

1. first sign-in: password, forced password change, OTP enrolment. The token is issued during the enrolment and
   carries no ``otp`` (the API answers ``401 mfa_required`` and the dashboard signs in again);
2. second sign-in: password and OTP code. The token carries ``amr`` ⊇ {pwd, otp}.
3. phase P4a: the staff app signs in with the device grant (RFC 8628, client ``ehimaya-staff-app``): the phone shows
   a code, the user approves it in a browser with password and OTP, and the phone's token carries the same proof
   plus an offline session (``offline_access``).

Standard library only. Usage: python3 infra/keycloak/check_mfa.py http://localhost:8080
"""

import base64
import hashlib
import hmac
import html
import json
import re
import secrets
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

REALM, CLIENT, REDIRECT = "ehimaya-staff", "ehimaya-dashboard", "http://localhost:5173/callback"
DEVICE_CLIENT = "ehimaya-staff-app"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class Browser:
    """Follows the login pages by hand. Keycloak marks its cookies Secure, so they are kept here even over http."""

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}
        self._opener = urllib.request.build_opener(_NoRedirect)

    def request(self, url: str, data: dict[str, str] | None = None) -> tuple[int, str, str]:
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body)  # noqa: S310 (http(s) URL of the Keycloak under test)
        if self.cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()))
        try:
            resp = self._opener.open(req, timeout=20)
        except urllib.error.HTTPError as exc:  # 3xx (redirects are not followed) and errors
            resp = exc
        for header in resp.headers.get_all("Set-Cookie") or []:
            name, _, rest = header.partition("=")
            self.cookies[name.strip()] = rest.split(";", 1)[0]
        return resp.status, resp.headers.get("Location", ""), resp.read().decode("utf-8", "replace")


def totp(raw_key: str, at: float) -> str:
    # Keycloak's totpSecret form field is the raw HMAC key; the page shows its base32 form for authenticator apps.
    digest = hmac.new(raw_key.encode(), struct.pack(">Q", int(at // 30)), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f"{(struct.unpack('>I', digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def form_action(page: str) -> str:
    match = re.search(r'<form[^>]*action="([^"]+)"', page)
    if not match:
        sys.exit(f"check_mfa: no form on the page:\n{page[:2000]}")
    return html.unescape(match.group(1))


def claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    return dict(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))))


def sign_in(kc: str, username: str, password: str, new_password: str, otp_key: str | None) -> tuple[dict[str, Any], str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urllib.parse.urlencode(
        {
            "client_id": CLIENT,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": "openid",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    browser = Browser()
    _, _, page = browser.request(f"{kc}/realms/{REALM}/protocol/openid-connect/auth?{query}")
    status, location, page = browser.request(form_action(page), {"username": username, "password": password})
    for _ in range(10):
        if status in (302, 303) and location.startswith(REDIRECT):
            code = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)["code"][0]
            _, _, body = browser.request(
                f"{kc}/realms/{REALM}/protocol/openid-connect/token",
                {
                    "grant_type": "authorization_code",
                    "client_id": CLIENT,
                    "redirect_uri": REDIRECT,
                    "code": code,
                    "code_verifier": verifier,
                },
            )
            return claims(json.loads(body)["access_token"]), otp_key or ""
        if status in (302, 303):
            status, location, page = browser.request(urllib.parse.urljoin(kc, location))
            continue
        secret = re.search(r'name="totpSecret"[^>]*value="([^"]+)"', page) or re.search(
            r'value="([^"]+)"[^>]*name="totpSecret"', page
        )
        if secret:  # OTP enrolment
            otp_key = secret.group(1)
            hidden = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
            form = {**hidden, "totp": totp(otp_key, time.time()), "totpSecret": otp_key, "userLabel": "check_mfa"}
            status, location, page = browser.request(form_action(page), form)
        elif 'name="password-new"' in page:
            status, location, page = browser.request(
                form_action(page), {"password-new": new_password, "password-confirm": new_password}
            )
        elif 'name="otp"' in page:
            if not otp_key:
                sys.exit("check_mfa: OTP asked before any enrolment")
            status, location, page = browser.request(form_action(page), {"otp": totp(otp_key, time.time())})
        else:
            sys.exit(f"check_mfa: unexpected page (HTTP {status}):\n{page[:2000]}")
    sys.exit("check_mfa: the sign-in did not finish")


def sign_in_device(kc: str, username: str, password: str, otp_key: str) -> dict[str, Any]:
    """The staff app's sign-in (phase P4a): a device code approved in a browser, then the phone's token."""
    browser = Browser()
    _, _, body = browser.request(
        f"{kc}/realms/{REALM}/protocol/openid-connect/auth/device",
        {"client_id": DEVICE_CLIENT, "scope": "openid offline_access"},
    )
    grant = json.loads(body)
    status, location, page = browser.request(grant["verification_uri_complete"])

    def submit(form: dict[str, str]) -> tuple[int, str, str]:
        return browser.request(urllib.parse.urljoin(kc, form_action(page)), form)

    for _ in range(12):
        if status in (302, 303):
            status, location, page = browser.request(urllib.parse.urljoin(kc, location))
        elif 'name="username"' in page:
            status, location, page = submit({"username": username, "password": password})
        elif 'name="otp"' in page:
            status, location, page = submit({"otp": totp(otp_key, time.time())})
        elif 'name="accept"' in page:
            hidden = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
            status, location, page = submit({**hidden, "accept": "Yes"})
        else:
            break
    _, _, body = browser.request(
        f"{kc}/realms/{REALM}/protocol/openid-connect/token",
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": DEVICE_CLIENT,
            "device_code": grant["device_code"],
        },
    )
    tokens = json.loads(body)
    if "access_token" not in tokens:
        sys.exit(f"check_mfa: the device grant gave no token: {tokens}\n{page[:2000]}")
    if claims(tokens["refresh_token"]).get("typ") != "Offline":
        sys.exit("check_mfa: the staff app did not get an offline session")
    return claims(tokens["access_token"])


def admin_create_user(kc: str, username: str, password: str) -> None:
    browser = Browser()
    _, _, body = browser.request(
        f"{kc}/realms/master/protocol/openid-connect/token",
        {"grant_type": "password", "client_id": "admin-cli", "username": "admin", "password": "admin"},
    )
    token = json.loads(body)["access_token"]
    user = {
        "username": username,
        "enabled": True,
        "email": f"{username}@ehimaya.invalid",
        "emailVerified": True,
        "firstName": "Check",
        "lastName": "Mfa",
        "attributes": {"scope_level": ["national"]},
        "credentials": [{"type": "password", "value": password, "temporary": False}],
    }
    req = urllib.request.Request(  # noqa: S310
        f"{kc}/admin/realms/{REALM}/users",
        data=json.dumps(user).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        if resp.status != 201:
            sys.exit(f"check_mfa: user creation answered {resp.status}")


def main() -> None:
    kc = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
    username = f"check.mfa.{secrets.token_hex(3)}"
    password, new_password = "Check#Mfa1-" + secrets.token_hex(4), "Check#Mfa2-" + secrets.token_hex(4)
    admin_create_user(kc, username, password)

    first, otp_key = sign_in(kc, username, password, new_password, None)
    print("first sign-in (enrolment): amr =", first.get("amr"))
    if not otp_key:
        sys.exit("check_mfa: the first sign-in did not enrol an OTP device")
    if "otp" in (first.get("amr") or []):
        sys.exit("check_mfa: the enrolment token already claims otp")

    # A TOTP code is accepted once: wait for the next 30-second window.
    time.sleep(30 - time.time() % 30 + 1)
    second, _ = sign_in(kc, username, new_password, new_password, otp_key)
    print("second sign-in: amr =", second.get("amr"))
    if not {"pwd", "otp"} <= set(second.get("amr") or []):
        sys.exit("check_mfa: the token does not prove password and OTP")
    if "ehimaya-api" not in (second.get("aud") if isinstance(second.get("aud"), list) else [second.get("aud")]):
        sys.exit("check_mfa: the token is not for ehimaya-api")

    time.sleep(30 - time.time() % 30 + 1)
    phone = sign_in_device(kc, username, new_password, otp_key)
    print("staff app (device grant): amr =", phone.get("amr"))
    if not {"pwd", "otp"} <= set(phone.get("amr") or []):
        sys.exit("check_mfa: the staff app's token does not prove password and OTP")
    if "ehimaya-api" not in (phone.get("aud") if isinstance(phone.get("aud"), list) else [phone.get("aud")]):
        sys.exit("check_mfa: the staff app's token is not for ehimaya-api")
    print("check_mfa: OK")


if __name__ == "__main__":
    main()
