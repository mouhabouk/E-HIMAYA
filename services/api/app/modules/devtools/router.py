"""The «تطوير النظام» menu of the national system administrator (Yamen, 2026-11-09; docs/dev/repo-map.md).

The repository map: pages, mobile features, API modules, services and infrastructure, with the imports, the HTTP
calls and the settings that tie them. ``repo_map.json`` is generated from the repository by scripts/repo_map.py
(the image holds only ``app``), so the map is the one of the commit the API was built from.
"""

import json
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import Principal, Role, require_roles

router = APIRouter(prefix="/api/v1/admin/dev", tags=["devtools"])

Admin = Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]
MAP = Path(__file__).with_name("repo_map.json")


@cache
def _map() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(MAP.read_text(encoding="utf-8"))
    data["generated_at"] = datetime.fromtimestamp(MAP.stat().st_mtime, UTC).isoformat()
    return data


@router.get("/repo-map")
async def repo_map(principal: Admin) -> dict[str, Any]:
    """Nodes (id, label, group, files, loc, deg), edges (s, t, k, w, via) and the number of API routes."""
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    return _map()
