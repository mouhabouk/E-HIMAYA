"""Proves the phone sign-in of the mobile app on a real Keycloak (phase A, docs/phase-a/design.md §2.2).

Against a Keycloak that imported infra/keycloak/realms with the provider jar of infra/keycloak/providers/phone-otp
(CI job "Keycloak · realm import", scripts/ci-local.sh), started with OTP_SMS_SECRET and EHIMAYA_API_INTERNAL_URL
pointing at this script. The script plays the API's POST /internal/auth/otp-sms: it checks the HMAC signature and
keeps the code instead of sending an SMS.

1. phone number without code → 400 otp_sent, one signed SMS request; asking again at once → 429 otp_too_soon;
2. a wrong code → 401 invalid_grant with tries_left; the right code → tokens whose access token carries
   phone_number, phone_number_verified=true, the audience ehimaya-api and the role citizen;
3. the same number signs in again (same account); the used code is refused; an invalid number → 400 invalid_phone;
4. three wrong codes use the code up.

Standard library only. Usage: OTP_SMS_SECRET=... python3 infra/keycloak/check_phone_otp.py http://localhost:8080 8099
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

REALM, CLIENT = "ehimaya-public", "ehimaya-mobile"
SECRET = os.environ["OTP_SMS_SECRET"]
received: list[dict[str, Any]] = []


class FakeApi(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (http.server naming)
        body = self.rfile.read(int(self.headers["Content-Length"]))
        timestamp = self.headers.get("X-Timestamp", "")
        expected = "sha256=" + hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        if self.path != "/internal/auth/otp-sms" or not hmac.compare_digest(expected, self.headers.get("X-Signature", "")):
            self.send_response(401)
            self.end_headers()
            return
        received.append(json.loads(body))
        answer = b'{"sent":true,"simulated":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    def log_message(self, *args: Any) -> None:
        pass


def token_request(base: str, **form: str) -> tuple[int, dict[str, Any]]:
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": CLIENT, "scope": "openid", **form}).encode()
    request = urllib.request.Request(f"{base}/realms/{REALM}/protocol/openid-connect/token", data=data)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def check(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    print(f"ok   {message}")


def main(base: str, port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), FakeApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    phone = f"+2165{secrets.randbelow(10_000_000):07d}"

    status, body = token_request(base, phone=phone, ui_locales="fr")
    check(status == 400 and body.get("error") == "otp_sent", f"code sent: {status} {body}")
    check(body.get("sms_simulated") is True and body.get("expires_in") == 300, "expiry and [SIM] flag answered")
    check(len(received) == 1 and received[0]["phone"] == phone and received[0]["locale"] == "fr", "signed SMS request")
    code = received[0]["code"]

    status, body = token_request(base, phone=phone)
    check(status == 429 and body.get("error") == "otp_too_soon", f"second code at once refused: {status} {body}")

    wrong = "000000" if code != "000000" else "111111"
    status, body = token_request(base, phone=phone, otp=wrong)
    check(status == 401 and body.get("tries_left") == 2, f"wrong code: {status} {body}")

    status, body = token_request(base, phone=phone, otp=code)
    check(status == 200 and "access_token" in body and "refresh_token" in body, f"right code signs in: {status}")
    access = claims(body["access_token"])
    check(access.get("phone_number") == phone, f"phone_number claim: {access.get('phone_number')}")
    check(access.get("phone_number_verified") is True, "phone_number_verified claim")
    audience = access.get("aud")
    check("ehimaya-api" in (audience if isinstance(audience, list) else [audience]), "audience ehimaya-api")
    check("citizen" in access.get("realm_access", {}).get("roles", []), "role citizen")
    subject = access["sub"]

    status, body = token_request(base, phone=phone, otp=code)
    check(status == 400 and body.get("error") == "otp_expired", f"used code refused: {status} {body}")

    time.sleep(61)
    status, _ = token_request(base, phone=phone)
    check(status == 400, "new code after the resend delay")
    status, body = token_request(base, phone=phone, otp=received[-1]["code"])
    check(status == 200 and claims(body["access_token"])["sub"] == subject, "same account on the second sign-in")

    status, body = token_request(base, phone="+21612345678")
    check(status == 400 and body.get("error") == "invalid_phone", f"landline refused: {status} {body}")

    other = f"+2169{secrets.randbelow(10_000_000):07d}"
    token_request(base, phone=other)
    other_code = received[-1]["code"]
    wrong = "000000" if other_code != "000000" else "111111"
    for _ in range(3):
        token_request(base, phone=other, otp=wrong)
    status, body = token_request(base, phone=other, otp=other_code)
    check(status == 400 and body.get("error") == "otp_expired", "three wrong codes use the code up")

    server.shutdown()
    print("phone sign-in: all checks passed")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"), int(sys.argv[2]) if len(sys.argv) > 2 else 8099)
