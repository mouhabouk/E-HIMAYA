# ┏━━ SIMULATION ━━ Google OAuth 2.0 token endpoint (JWT bearer grant) and FCM HTTP v1 messages:send
# ┃ PRODUCTION: set the API's FCM_SERVICE_ACCOUNT=<base64 of the key from Firebase console > Project settings >
# ┃   Service accounts > Generate new private key>, FCM_API_URL=https://fcm.googleapis.com;
# ┃   the real token_uri (oauth2.googleapis.com) comes from that key file, which wins over FCM_SERVICE_ACCOUNT_FILE.
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — the parts of Google OAuth and FCM HTTP v1 the API uses, with the same checks and error shapes."""

import secrets
import threading
from dataclasses import dataclass, field
from typing import Any

import jwt

from .account import ServiceAccount

JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
ACCESS_TOKEN_TTL = 3600
MAX_ASSERTION_LIFETIME = 3600
CLOCK_SKEW = 60
UNREGISTERED_PREFIX = "sim-unregistered"

MESSAGE_FIELDS = frozenset(
    {"name", "data", "notification", "android", "webpush", "apns", "fcm_options", "token", "topic", "condition"}
)
TARGETS = ("token", "topic", "condition")
# Keys FCM refuses in the data payload.
RESERVED_DATA_KEYS = frozenset({"from", "notification", "message_type"})
RESERVED_DATA_PREFIXES = ("google", "gcm")
ANDROID_PRIORITIES = frozenset({"normal", "high"})


class InvalidGrant(Exception):
    """The assertion is refused: answered as 400 invalid_grant."""


def verify_assertion(assertion: str, account: ServiceAccount, now: float) -> None:
    """Check a JWT-bearer assertion like Google's token endpoint does (signature, iss, aud, scope, lifetime)."""
    try:
        claims: dict[str, Any] = jwt.decode(
            assertion,
            account.public_key,
            algorithms=["RS256"],
            audience=account.token_uri,
            issuer=account.client_email,
            # Times are checked below against the simulator's clock.
            options={"require": ["iss", "aud", "iat", "exp"], "verify_exp": False, "verify_iat": False},
        )
    except jwt.InvalidSignatureError as exc:
        raise InvalidGrant("Invalid JWT Signature.") from exc
    except jwt.InvalidAudienceError as exc:
        raise InvalidGrant(f"Invalid JWT: aud must be {account.token_uri}.") from exc
    except jwt.InvalidIssuerError as exc:
        raise InvalidGrant("Invalid JWT: iss is not the service account's client_email.") from exc
    except jwt.PyJWTError as exc:
        raise InvalidGrant(f"Invalid JWT: {exc}.") from exc
    scope = claims.get("scope")
    if not isinstance(scope, str) or FCM_SCOPE not in scope.split():
        raise InvalidGrant(f"Invalid JWT: scope must include {FCM_SCOPE}.")
    iat, exp = claims["iat"], claims["exp"]
    if not isinstance(iat, int | float) or not isinstance(exp, int | float):
        raise InvalidGrant("Invalid JWT: iat and exp must be numbers.")
    if exp <= now:
        raise InvalidGrant("Invalid JWT: Token must be a short-lived token (60 minutes) and in a reasonable timeframe.")
    if iat > now + CLOCK_SKEW or exp - iat > MAX_ASSERTION_LIFETIME or exp <= iat:
        raise InvalidGrant("Invalid JWT: Token must be a short-lived token (60 minutes) and in a reasonable timeframe.")


@dataclass
class AccessTokens:
    """Access tokens handed out by the token endpoint, with their expiry time."""

    _tokens: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def issue(self, now: float) -> str:
        token = f"sim-at-{secrets.token_urlsafe(32)}"
        with self._lock:
            for old in [t for t, expiry in self._tokens.items() if expiry <= now]:
                del self._tokens[old]
            self._tokens[token] = now + ACCESS_TOKEN_TTL
        return token

    def valid(self, token: str, now: float) -> bool:
        with self._lock:
            expiry = self._tokens.get(token)
        return expiry is not None and expiry > now


def google_error(code: int, status: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "status": status}
    if details:
        error["details"] = details
    return {"error": error}


class InvalidArgument(Exception):
    """A message FCM would refuse with 400 INVALID_ARGUMENT."""

    def __init__(self, field_path: str, description: str) -> None:
        super().__init__(description)
        self.field_path, self.description = field_path, description

    def body(self) -> dict[str, Any]:
        return google_error(
            400,
            "INVALID_ARGUMENT",
            self.description,
            [
                {
                    "@type": "type.googleapis.com/google.rpc.BadRequest",
                    "fieldViolations": [{"field": self.field_path, "description": self.description}],
                },
                {"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "INVALID_ARGUMENT"},
            ],
        )


def unregistered_body() -> dict[str, Any]:
    return google_error(
        404,
        "NOT_FOUND",
        "Requested entity was not found.",
        [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}],
    )


def _object(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidArgument(path, f"Invalid value at '{path}': expected an object.")
    return value


def _string_map(value: object, path: str) -> dict[str, str]:
    mapping = _object(value, path)
    for index, item in enumerate(mapping.values()):
        if not isinstance(item, str):
            raise InvalidArgument(
                f"{path}[{index}].value", f"Invalid value at '{path}[{index}].value' (TYPE_STRING), {item!r}"
            )
    return mapping


def _string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise InvalidArgument(path, f"Invalid value at '{path}' (TYPE_STRING), {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ParsedMessage:
    token: str | None
    title: str | None
    body: str | None
    data: dict[str, str] | None
    android_channel: str | None
    priority: str | None
    validate_only: bool


def parse_send_request(payload: object) -> ParsedMessage:
    """Validate a messages:send body the way FCM HTTP v1 does for the fields the API uses."""
    request = _object(payload, "")
    unknown = set(request) - {"message", "validate_only"}
    if unknown:
        raise InvalidArgument(sorted(unknown)[0], f'Invalid JSON payload received. Unknown name "{sorted(unknown)[0]}"')
    validate_only = request.get("validate_only", False)
    if not isinstance(validate_only, bool):
        raise InvalidArgument("validate_only", "Invalid value at 'validate_only' (TYPE_BOOL)")
    if "message" not in request:
        raise InvalidArgument("message", "Request contains an invalid argument: message is required.")
    message = _object(request["message"], "message")
    unknown = set(message) - MESSAGE_FIELDS
    if unknown:
        name = sorted(unknown)[0]
        raise InvalidArgument(f"message.{name}", f"Invalid JSON payload received. Unknown name \"{name}\" at 'message'")

    targets = [name for name in TARGETS if name in message]
    if len(targets) != 1:
        raise InvalidArgument("message", "Exactly one of token, topic or condition must be set.")
    target = targets[0]
    target_value = _string(message[target], f"message.{target}")
    if not target_value.strip():
        raise InvalidArgument(f"message.{target}", f"The {target} must not be empty.")

    title = body = None
    if "notification" in message:
        notification = _object(message["notification"], "message.notification")
        for key in notification:
            if key not in {"title", "body", "image"}:
                raise InvalidArgument(
                    f"message.notification.{key}", f"Unknown name \"{key}\" at 'message.notification'"
                )
            _string(notification[key], f"message.notification.{key}")
        title, body = notification.get("title"), notification.get("body")

    data = None
    if "data" in message:
        data = _string_map(message["data"], "message.data")
        for key in data:
            if key in RESERVED_DATA_KEYS or key.startswith(RESERVED_DATA_PREFIXES):
                raise InvalidArgument("message.data", f"Invalid data payload key: {key}")

    android_channel = priority = None
    if "android" in message:
        android = _object(message["android"], "message.android")
        if "priority" in android:
            raw = _string(android["priority"], "message.android.priority")
            if raw.lower() not in ANDROID_PRIORITIES:
                raise InvalidArgument(
                    "message.android.priority",
                    f"Invalid value at 'message.android.priority' (type.googleapis.com/"
                    f'google.firebase.fcm.v1.AndroidMessagePriority), "{raw}"',
                )
            priority = raw.lower()
        if "data" in android:
            _string_map(android["data"], "message.android.data")
        if "notification" in android:
            android_notification = _object(android["notification"], "message.android.notification")
            if "channel_id" in android_notification:
                android_channel = _string(android_notification["channel_id"], "message.android.notification.channel_id")

    if "apns" in message:
        apns = _object(message["apns"], "message.apns")
        if "headers" in apns:
            _string_map(apns["headers"], "message.apns.headers")
        if "payload" in apns:
            apns_payload = _object(apns["payload"], "message.apns.payload")
            if "aps" in apns_payload:
                _object(apns_payload["aps"], "message.apns.payload.aps")

    return ParsedMessage(
        token=target_value if target == "token" else None,
        title=title,
        body=body,
        data=data,
        android_channel=android_channel,
        priority=priority,
        validate_only=validate_only,
    )
