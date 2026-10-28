"""Proves the proof of work of the sign-in pages (phase L2, item 8, docs/phase-l/design-l2.md §3).

Against a Keycloak that imported infra/keycloak/realms (CI job "Keycloak · realm import", scripts/ci-local.sh):

1. staff realm, a real account: two wrong passwords show the plain form; the third one brings back the form with a
   challenge; the right password without the solution is refused before it is checked; with the solution (found
   here as the browser would) the sign-in goes on to the next step;
2. both realms, a name that has no account: the challenge appears after three attempts too, so it never tells
   whether an account exists;
3. the realms' temporary lockout starts at 10 failures (it was 3).

Standard library only. Usage: python3 infra/keycloak/check_login_guard.py http://localhost:8080
"""

import base64
import hashlib
import html
import json
import re
import secrets
import sys
import time
import urllib.parse
import urllib.request

from check_mfa import Browser, admin_create_user, form_action

STAFF = ("ehimaya-staff", "ehimaya-dashboard", "http://localhost:5173/callback")
PUBLIC = ("ehimaya-public", "ehimaya-portal", "http://localhost:5174/callback")


def fail(message: str, page: str = "") -> None:
    feedback = r"(?s)<(?:span|div)[^>]*(?:kc-feedback-text|pf-v5-c-alert__title)[^>]*>(.*?)</"
    alerts = re.findall(feedback, page)
    shown = " | ".join(" ".join(html.unescape(a).split()) for a in alerts) or page[:1500]
    sys.exit(f"check_login_guard: {message}\n{shown}")


def open_form(kc: str, realm: tuple[str, str, str]) -> tuple[Browser, str]:
    name, client, redirect = realm
    verifier = secrets.token_urlsafe(48)
    pkce = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urllib.parse.urlencode(
        {
            "client_id": client,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "openid",
            "code_challenge": pkce,
            "code_challenge_method": "S256",
        }
    )
    browser = Browser()
    status, _, page = browser.request(f"{kc}/realms/{name}/protocol/openid-connect/auth?{query}")
    if status != 200 or 'name="password"' not in page:
        fail(f"no sign-in form in {name} (HTTP {status})", page)
    return browser, page


def challenge(page: str) -> tuple[str, int] | None:
    match = re.search(r'id="ehimaya-pow" data-salt="([0-9a-f]+)" data-bits="(\d+)"', page)
    return (match.group(1), int(match.group(2))) if match else None


def solve(salt: str, bits: int) -> str:
    n = 0
    while True:
        digest = int.from_bytes(hashlib.sha256(f"{salt}:{n}".encode()).digest(), "big")
        if digest >> (256 - bits) == 0:
            return str(n)
        n += 1


def attempt(browser: Browser, page: str, username: str, password: str, solution: str | None = None) -> tuple[int, str]:
    # Slower than the realm's quick-login check (two failures within a second lock the account for a minute).
    time.sleep(1.2)
    form = {"username": username, "password": password}
    if solution is not None:
        form["pow_solution"] = solution
    status, location, page = browser.request(html.unescape(form_action(page)), form)
    return status, page if status == 200 else location


def staff_account(kc: str) -> None:
    username = f"guard-{secrets.token_hex(4)}"
    password = "Guard-" + secrets.token_urlsafe(12) + "1!"
    admin_create_user(kc, username, password)
    browser, page = open_form(kc, STAFF)
    for i in (1, 2):
        _, page = attempt(browser, page, username, "wrong-password")
        if challenge(page):
            fail(f"challenge after {i} failure(s)", page)
    _, page = attempt(browser, page, username, "wrong-password")
    if not challenge(page):
        fail("no challenge after the third failure", page)
    # The right password without the solution: refused, and the password is not even checked.
    _, page = attempt(browser, page, username, password)
    found = challenge(page)
    if not found or 'name="password"' not in page:
        fail("the right password without the proof was not refused", page)
    if "ehimaya-pow-status" not in page or "pow.js" not in page:
        fail("the challenge page has no solver or status line", page)
    salt, bits = found
    status, page = attempt(browser, page, username, password, solve(salt, bits))
    if status == 200 and challenge(page):
        fail("the solved proof was refused", page)
    if status == 200 and not ('name="password-new"' in page or "totpSecret" in page or 'name="otp"' in page):
        fail(f"unexpected page after the solved proof (HTTP {status})", page)
    print(f"check_login_guard: staff account challenged at the third failure and accepted with a {bits}-bit proof")


def unknown_name(kc: str, realm: tuple[str, str, str]) -> None:
    username = f"nobody-{secrets.token_hex(4)}@ehimaya.invalid"
    browser, page = open_form(kc, realm)
    for _ in range(3):
        _, page = attempt(browser, page, username, "wrong-password")
    if not challenge(page):
        fail(f"{realm[0]}: no challenge for a name without an account", page)
    print(f"check_login_guard: {realm[0]} challenges a name without an account the same way")


def lockout(kc: str) -> None:
    browser = Browser()
    _, _, body = browser.request(
        f"{kc}/realms/master/protocol/openid-connect/token",
        {"grant_type": "password", "client_id": "admin-cli", "username": "admin", "password": "admin"},
    )
    token = json.loads(body)["access_token"]
    for realm in (STAFF[0], PUBLIC[0]):
        req = urllib.request.Request(f"{kc}/admin/realms/{realm}", headers={"Authorization": f"Bearer {token}"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            settings = json.loads(resp.read())
        if settings.get("failureFactor") != 10 or not settings.get("bruteForceProtected"):
            fail(f"{realm}: lockout is not at 10 failures: {settings.get('failureFactor')}")
        if "length(8)" not in settings.get("passwordPolicy", ""):
            fail(f"{realm}: passwords of at least 8 characters are not required")
    print("check_login_guard: both realms lock at 10 failures and require 8 characters")


def main() -> None:
    kc = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
    staff_account(kc)
    unknown_name(kc, STAFF)
    unknown_name(kc, PUBLIC)
    lockout(kc)


if __name__ == "__main__":
    main()
