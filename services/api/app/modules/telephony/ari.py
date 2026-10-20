"""Asterisk REST Interface client (HTTP) used by the API and the worker (docs/telephony.md).

Every call-control action is an ARI request:

* operator endpoints: ``PUT/DELETE /ari/asterisk/config/dynamic/res_pjsip/{auth,aor,endpoint}/op-…`` (sorcery
  memory wizard, services/telephony/config/sorcery.conf);
* queue membership, scenario 2 transfer and closing a crisis room: a Local channel into ``[ehimaya-control]``
  (``POST /ari/channels``), a context no SIP endpoint can reach;
* outbound calls: an originated channel to the operator's softphone that continues into ``[ehimaya-outbound]``;
  invitations into a crisis room: a Local channel into ``[ehimaya-invite]`` bridged to ``[ehimaya-conference]``.

The event side (WebSocket ``/ari/events``) is in ``worker.py``. Tests replace the client with ``set_ari``.
"""

import base64
from typing import Any, Protocol
from urllib.parse import quote

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()

CONTROL_CONTEXT = "ehimaya-control"
OUTBOUND_CONTEXT = "ehimaya-outbound"
INVITE_CONTEXT = "ehimaya-invite"
CONFERENCE_CONTEXT = "ehimaya-conference"

# The values of the [operator-endpoint], [operator-aor] and [operator-auth] templates of
# services/telephony/config/pjsip.conf: keep both in step.
OPERATOR_ENDPOINT_FIELDS: dict[str, str] = {
    "context": "ehimaya-operators",
    "disallow": "all",
    "allow": "g722,ulaw,alaw",
    "webrtc": "yes",
    "dtls_auto_generate_cert": "yes",
    "transport": "transport-wss",
    "direct_media": "no",
    "device_state_busy_at": "1",
    "allow_transfer": "no",
    "allow_subscribe": "no",
    "rtp_timeout": "120",
    "send_pai": "yes",
    "trust_id_inbound": "no",
}
OPERATOR_AOR_FIELDS: dict[str, str] = {
    "max_contacts": "1",
    "remove_existing": "yes",
    "default_expiration": "300",
    "maximum_expiration": "3600",
}


class AriUnavailable(Exception):
    """Asterisk did not answer (down, network) or refused the request."""


class AriClient(Protocol):
    async def push_operator(self, endpoint: str, password: str, display_name: str) -> None: ...

    async def remove_operator(self, endpoint: str) -> None: ...

    async def control(self, action: str) -> None: ...

    async def originate_operator_call(self, endpoint: str, extension: str, channel_id: str, display: str) -> None: ...

    async def invite(self, extension: str, room: str) -> None: ...

    async def hangup(self, channel_id: str) -> None: ...

    async def channel_ids(self) -> set[str]: ...


def _fields(values: dict[str, str]) -> dict[str, Any]:
    return {"fields": [{"attribute": k, "value": v} for k, v in values.items()]}


class HttpAriClient:
    def __init__(self, base_url: str, user: str, password: str, app: str) -> None:
        self._app = app
        self._http = httpx.AsyncClient(base_url=f"{base_url}/ari", auth=(user, password), timeout=httpx.Timeout(5))

    async def _request(self, method: str, path: str, *, ok_missing: bool = False, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise AriUnavailable(type(exc).__name__) from exc
        if ok_missing and response.status_code == 404:
            return None
        if response.status_code >= 400:
            # ARI error bodies name the problem, never a secret.
            raise AriUnavailable(f"http_{response.status_code}:{response.text[:120]}")
        return response.json() if response.content else None

    async def _config(self, method: str, kind: str, name: str, values: dict[str, str] | None = None) -> None:
        path = f"/asterisk/config/dynamic/res_pjsip/{kind}/{quote(name, safe='')}"
        if values is None:
            await self._request(method, path, ok_missing=True)
        else:
            await self._request(method, path, json=_fields(values))

    async def push_operator(self, endpoint: str, password: str, display_name: str) -> None:
        await self._config(
            "PUT", "auth", endpoint, {"auth_type": "userpass", "username": endpoint, "password": password}
        )
        await self._config("PUT", "aor", endpoint, OPERATOR_AOR_FIELDS)
        caller = display_name.replace('"', "").replace("<", "").replace(">", "")[:60] or endpoint
        await self._config(
            "PUT",
            "endpoint",
            endpoint,
            {**OPERATOR_ENDPOINT_FIELDS, "auth": endpoint, "aors": endpoint, "callerid": f'"{caller}" <{endpoint}>'},
        )

    async def remove_operator(self, endpoint: str) -> None:
        for kind in ("endpoint", "aor", "auth"):
            await self._config("DELETE", kind, endpoint)

    async def control(self, action: str) -> None:
        """Run ``action`` (member-add-op-…, member-del-op-…, transfer-<channel>, confkick-<room>) in the dialplan."""
        params = {
            "endpoint": f"Local/{action}@{CONTROL_CONTEXT}",
            "context": CONTROL_CONTEXT,
            "extension": "done",
            "priority": "1",
            "timeout": "10",
        }
        await self._request("POST", "/channels", params=params)

    async def originate_operator_call(self, endpoint: str, extension: str, channel_id: str, display: str) -> None:
        """Ring the operator's softphone; once answered it continues into [ehimaya-outbound] to ``extension``."""
        params = {
            "endpoint": f"PJSIP/{endpoint}",
            "context": OUTBOUND_CONTEXT,
            "extension": extension,
            "priority": "1",
            "channelId": channel_id,
            "callerId": f'"{display}" <{extension}>',
            "timeout": "30",
        }
        await self._request("POST", "/channels", params=params, json={"variables": {"EH_SOURCE": "operator"}})

    async def invite(self, extension: str, room: str) -> None:
        """Call ``extension`` (216XXXXXXXX) and put the answering party into crisis room ``room``."""
        params = {
            "endpoint": f"Local/{extension}@{INVITE_CONTEXT}",
            "context": CONFERENCE_CONTEXT,
            "extension": f"conf-{room}",
            "priority": "1",
            "callerId": f'"e-Himaya" <{room}>',
            "timeout": "60",
        }
        await self._request("POST", "/channels", params=params)

    async def hangup(self, channel_id: str) -> None:
        await self._request("DELETE", f"/channels/{quote(channel_id, safe='')}", ok_missing=True)

    async def channel_ids(self) -> set[str]:
        channels = await self._request("GET", "/channels") or []
        return {str(c.get("id")) for c in channels if isinstance(c, dict)}

    def events_url(self) -> str:
        base = str(self._http.base_url).rstrip("/")
        ws = "wss" + base[5:] if base.startswith("https") else "ws" + base[4:]
        return f"{ws}/events?app={quote(self._app)}&subscribeAll=true"

    async def close(self) -> None:
        await self._http.aclose()


def basic_auth_header() -> str:
    settings = get_settings()
    password = settings.telephony_ari_password.get_secret_value() if settings.telephony_ari_password else ""
    raw = f"{settings.telephony_ari_user}:{password}".encode()
    return "Basic " + base64.b64encode(raw).decode()


_client: AriClient | None = None
_configured = False


def get_ari() -> AriClient | None:
    """The ARI client, or None when telephony is not configured (TELEPHONY_ARI_URL / TELEPHONY_ARI_PASSWORD)."""
    global _client, _configured
    if not _configured:
        settings = get_settings()
        if settings.telephony_ari_url and settings.telephony_ari_password:
            _client = HttpAriClient(
                settings.telephony_ari_url,
                settings.telephony_ari_user,
                settings.telephony_ari_password.get_secret_value(),
                settings.telephony_ari_app,
            )
        _configured = True
    return _client


def set_ari(client: AriClient | None) -> None:
    """Used by tests (a fake ARI) and to reset the cached client."""
    global _client, _configured
    _client = client
    _configured = client is not None
