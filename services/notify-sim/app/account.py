# ┏━━ SIMULATION ━━ fake Google service account (RSA key generated locally) for the emulated FCM OAuth flow
# ┃ PRODUCTION: use the real key from Firebase console > Project settings > Service accounts > Generate new private
# ┃   key, base64-encoded into the API's FCM_SERVICE_ACCOUNT (base64 -w0 key.json), which wins over the file.
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — the service account the API signs its OAuth assertions with.

Generated once and kept in ``SIM_DATA_DIR`` so tokens and the API's cached key survive restarts. It has the
exact shape of a Google service-account file, so the API reads it with the same code as a real one.
"""

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from .config import Settings

CLIENT_EMAIL = "notify@ehimaya-sim.iam.gserviceaccount.com"


@dataclass(frozen=True, slots=True)
class ServiceAccount:
    info: dict[str, Any]
    public_key: RSAPublicKey

    @property
    def client_email(self) -> str:
        return str(self.info["client_email"])

    @property
    def token_uri(self) -> str:
        return str(self.info["token_uri"])

    @property
    def project_id(self) -> str:
        return str(self.info["project_id"])


def _new_info(settings: Settings, key: RSAPrivateKey, key_id: str | None = None) -> dict[str, Any]:
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return {
        "type": "service_account",
        "project_id": settings.fcm_project,
        "private_key_id": key_id or secrets.token_hex(20),
        "private_key": pem,
        "client_email": CLIENT_EMAIL,
        "client_id": str(secrets.randbelow(10**21)).zfill(21),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": settings.token_uri,
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "universe_domain": "googleapis.com",
    }


def _write(path: Path, info: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # Readable by the owner only: the API container runs as the same uid (10001) and mounts the volume read-only.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(info, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def load_or_create(settings: Settings) -> ServiceAccount:
    """Return the persisted service account, creating it (RSA-2048) on first start.

    The key is kept across restarts; project id and token_uri follow the current settings.
    """
    path = settings.service_account_file
    info: dict[str, Any] | None = None
    if path.exists():
        info = json.loads(path.read_text(encoding="utf-8"))
    if info is None or info.get("type") != "service_account" or "private_key" not in info:
        info = _new_info(settings, rsa.generate_private_key(public_exponent=65537, key_size=2048))
        _write(path, info)
    elif info.get("project_id") != settings.fcm_project or info.get("token_uri") != settings.token_uri:
        info = {**info, "project_id": settings.fcm_project, "token_uri": settings.token_uri}
        _write(path, info)
    key = serialization.load_pem_private_key(info["private_key"].encode(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise ValueError(f"{path}: private_key is not an RSA key")
    return ServiceAccount(info=info, public_key=key.public_key())
