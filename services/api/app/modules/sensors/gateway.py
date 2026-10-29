"""The guard of the internal routes the gateway beside MediaMTX calls (L5b, design-l5.md §3.0): sensor readings and
watch-tower events.

Never routed by Caddy. A route answers 404 while SENSOR_GATEWAY_TOKEN is unset, 403 to an address outside
SENSOR_GATEWAY_NETWORKS (the devices stay on the local network), and 401 without the gateway's token.
"""

import hmac
import ipaddress
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import get_settings

log = structlog.get_logger()


def _on_local_network(host: str | None) -> bool:
    if host is None:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(n, strict=False) for n in get_settings().sensor_gateway_networks)


def require_gateway(request: Request, x_gateway_token: Annotated[str, Header()] = "") -> None:
    expected = get_settings().sensor_gateway_token
    if expected is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    host = request.client.host if request.client else None
    if not _on_local_network(host):
        log.warning("gateway.outside_network")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "outside_local_network")
    if not x_gateway_token or not hmac.compare_digest(x_gateway_token.encode(), expected.get_secret_value().encode()):
        log.warning("gateway.bad_token")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad_token")


Gateway = Annotated[None, Depends(require_gateway)]
