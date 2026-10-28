"""Settings of the gateway, read from the environment (docs/sensor-gateway.md lists them)."""

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path

LOCAL_NETWORKS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128")


class ConfigError(ValueError):
    pass


def _networks(raw: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    try:
        nets = tuple(ipaddress.ip_network(item.strip(), strict=False) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise ConfigError(f"GATEWAY_ALLOW: {exc}") from exc
    for net in nets:
        if not (net.is_private or net.is_loopback):
            # The sensors stay on the local network (Yamen, 2026-10-28): a public range is refused outright.
            raise ConfigError(f"GATEWAY_ALLOW: {net} is not a local network")
    return nets


@dataclass(frozen=True)
class Settings:
    api_url: str
    token: str
    bind: str = "0.0.0.0"  # noqa: S104 (the local interface of the MediaMTX server; see GATEWAY_ALLOW)
    port: int = 8088
    allow: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = field(
        default_factory=lambda: _networks(",".join(LOCAL_NETWORKS))
    )
    queue_path: Path = Path("/data/queue.sqlite3")
    queue_max: int = 100_000
    flush_every_s: float = 2.0
    batch: int = 500
    timeout_s: float = 10.0
    max_body: int = 65_536
    # A tower event carries one JPEG (~2 MB at most, base64): its own body limit and a smaller queue.
    max_event_body: int = 3_000_000
    events_max: int = 200

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ) if env is None else env
        api_url = env.get("GATEWAY_API_URL", "").rstrip("/")
        token = env.get("GATEWAY_TOKEN", "")
        if not api_url.startswith(("http://", "https://")):
            raise ConfigError("GATEWAY_API_URL must be the API's address on the local network (http://… or https://…)")
        if len(token) < 24:
            raise ConfigError("GATEWAY_TOKEN must be the API's SENSOR_GATEWAY_TOKEN (24 characters or more)")
        return cls(
            api_url=api_url,
            token=token,
            bind=env.get("GATEWAY_BIND", cls.bind),
            port=int(env.get("GATEWAY_PORT", cls.port)),
            allow=_networks(env.get("GATEWAY_ALLOW", ",".join(LOCAL_NETWORKS))),
            queue_path=Path(env.get("GATEWAY_QUEUE", str(cls.queue_path))),
            queue_max=int(env.get("GATEWAY_QUEUE_MAX", cls.queue_max)),
            flush_every_s=float(env.get("GATEWAY_FLUSH_S", cls.flush_every_s)),
            events_max=int(env.get("GATEWAY_EVENTS_MAX", cls.events_max)),
        )
