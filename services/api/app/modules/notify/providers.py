"""Delivery channels: FCM push (Android and iOS through APNs), SMS over an HTTP gateway, SMTP e-mail.

Each provider is optional (``configured``). Tests replace them with fakes through ``set_providers``.
Payloads never carry personal data beyond what the message itself says.
"""

import asyncio
import base64
import json
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
import jwt
import structlog
from anyio import to_thread

from app.core.config import get_settings

log = structlog.get_logger()

ANDROID_ALERT_CHANNEL = "ehimaya_alerts"
ANDROID_DEFAULT_CHANNEL = "ehimaya_default"
IOS_ALERT_SOUND = "alert.caf"


@dataclass(frozen=True, slots=True)
class Push:
    token: str
    platform: str
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)
    alert: bool = False


@dataclass(frozen=True, slots=True)
class Result:
    ok: bool
    # The token is no longer valid (app uninstalled): the device row must be deleted.
    unregistered: bool = False
    error: str | None = None


class PushProvider(Protocol):
    configured: bool

    async def send(self, push: Push) -> Result: ...


class SmsProvider(Protocol):
    configured: bool

    async def send(self, to: str, text: str) -> Result: ...


class EmailProvider(Protocol):
    configured: bool

    async def send(self, to: str, subject: str, text: str) -> Result: ...


class Unconfigured:
    configured = False

    async def send(self, *args: Any, **kwargs: Any) -> Result:
        return Result(ok=False, error="not_configured")


class FcmPush:
    """FCM HTTP v1 with a service-account OAuth token (cached until shortly before it expires)."""

    configured = True
    SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

    def __init__(
        self,
        service_account: dict[str, Any],
        client: httpx.AsyncClient | None = None,
        api_url: str = "https://fcm.googleapis.com",
    ) -> None:
        self._account = service_account
        self._project = service_account["project_id"]
        self._url = f"{api_url.rstrip('/')}/v1/projects/{self._project}/messages:send"
        self._client = client or httpx.AsyncClient(timeout=10)
        self._token: tuple[str, float] | None = None
        self._lock = asyncio.Lock()

    async def _access_token(self) -> str:
        async with self._lock:
            if self._token and self._token[1] > time.time() + 60:
                return self._token[0]
            now = int(time.time())
            assertion = jwt.encode(
                {
                    "iss": self._account["client_email"],
                    "scope": self.SCOPE,
                    "aud": self._account["token_uri"],
                    "iat": now,
                    "exp": now + 3600,
                },
                self._account["private_key"],
                algorithm="RS256",
            )
            response = await self._client.post(
                self._account["token_uri"],
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            )
            response.raise_for_status()
            body = response.json()
            self._token = (body["access_token"], now + int(body.get("expires_in", 3600)))
            return self._token[0]

    def message(self, push: Push) -> dict[str, Any]:
        android_notification: dict[str, Any] = {
            "channel_id": ANDROID_ALERT_CHANNEL if push.alert else ANDROID_DEFAULT_CHANNEL
        }
        aps: dict[str, Any] = {"sound": IOS_ALERT_SOUND if push.alert else "default"}
        if push.alert:
            # Shown through Focus modes; "critical" would need an Apple entitlement.
            aps["interruption-level"] = "time-sensitive"
        return {
            "message": {
                "token": push.token,
                "notification": {"title": push.title, "body": push.body},
                "data": push.data,
                "android": {"priority": "high", "notification": android_notification},
                "apns": {"headers": {"apns-priority": "10"}, "payload": {"aps": aps}},
            }
        }

    async def send(self, push: Push) -> Result:
        try:
            token = await self._access_token()
            response = await self._client.post(
                self._url,
                json=self.message(push),
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            return Result(ok=False, error=type(exc).__name__)
        if response.status_code == 200:
            return Result(ok=True)
        detail = response.text[:300]
        # Only FCM's UNREGISTERED error code means the token is gone; a bare 404 (wrong project, wrong URL)
        # must not delete devices.
        unregistered = "UNREGISTERED" in detail
        return Result(ok=False, unregistered=unregistered, error=f"http_{response.status_code}")


class HttpSms:
    configured = True

    def __init__(self, url: str, token: str | None, sender: str, client: httpx.AsyncClient | None = None) -> None:
        self._url, self._token, self._sender = url, token, sender
        self._client = client or httpx.AsyncClient(timeout=10)

    async def send(self, to: str, text: str) -> Result:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            response = await self._client.post(
                self._url, json={"to": to, "text": text, "sender": self._sender}, headers=headers
            )
        except httpx.HTTPError as exc:
            return Result(ok=False, error=type(exc).__name__)
        return Result(ok=True) if response.is_success else Result(ok=False, error=f"http_{response.status_code}")


class SmtpEmail:
    configured = True

    def __init__(
        self, host: str, port: int, username: str | None, password: str | None, sender: str, starttls: bool
    ) -> None:
        self._host, self._port, self._username, self._password = host, port, username, password
        self._sender, self._starttls = sender, starttls

    def _send(self, to: str, subject: str, text: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self._sender, to, subject
        message.set_content(text)
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            if self._starttls:
                smtp.starttls(context=ssl.create_default_context())
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)

    async def send(self, to: str, subject: str, text: str) -> Result:
        try:
            await to_thread.run_sync(self._send, to, subject, text)
        except (OSError, smtplib.SMTPException) as exc:
            return Result(ok=False, error=type(exc).__name__)
        return Result(ok=True)


@dataclass
class Providers:
    push: PushProvider
    sms: SmsProvider
    email: EmailProvider


_providers: Providers | None = None


GOOGLE_FCM_API_URL = "https://fcm.googleapis.com"


def _fcm_api_url(account: dict[str, Any], configured: str) -> str:
    """A real Google service account always talks to Google, whatever FCM_API_URL says.

    Guards against a production key left with the development FCM_API_URL (the simulator): its OAuth
    token would be sent to the simulator and no phone would receive anything.
    """
    token_host = urlsplit(str(account.get("token_uri", ""))).hostname or ""
    if token_host.endswith(".googleapis.com") and configured.rstrip("/") != GOOGLE_FCM_API_URL:
        log.warning("notify.fcm_api_url_ignored_for_google_account", configured=configured)
        return GOOGLE_FCM_API_URL
    return configured


def _build() -> Providers:
    settings = get_settings()
    push: PushProvider = Unconfigured()
    if settings.fcm_service_account:
        try:
            account = json.loads(base64.b64decode(settings.fcm_service_account.get_secret_value()))
            push = FcmPush(account, api_url=_fcm_api_url(account, settings.fcm_api_url))
        except (ValueError, KeyError):
            log.error("notify.fcm_service_account_invalid")
    elif settings.fcm_service_account_file:
        # In development compose: the account generated by services/notify-sim (SIMULATION, see config.py).
        try:
            account = json.loads(settings.fcm_service_account_file.read_text(encoding="utf-8"))
            push = FcmPush(account, api_url=_fcm_api_url(account, settings.fcm_api_url))
        except (OSError, ValueError, KeyError) as exc:
            log.error(
                "notify.fcm_service_account_file_invalid",
                path=str(settings.fcm_service_account_file),
                error=type(exc).__name__,
            )
    sms: SmsProvider = (
        HttpSms(
            settings.sms_http_url,
            settings.sms_http_token.get_secret_value() if settings.sms_http_token else None,
            settings.sms_sender,
        )
        if settings.sms_http_url
        else Unconfigured()
    )
    email: EmailProvider = (
        SmtpEmail(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            settings.smtp_from,
            settings.smtp_starttls,
        )
        if settings.smtp_host
        else Unconfigured()
    )
    return Providers(push=push, sms=sms, email=email)


def get_providers() -> Providers:
    global _providers
    if _providers is None:
        _providers = _build()
    return _providers


def set_providers(providers: Providers | None) -> None:
    global _providers
    _providers = providers
