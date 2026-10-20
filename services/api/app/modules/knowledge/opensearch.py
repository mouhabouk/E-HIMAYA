"""OpenSearch 2 client of the events library (plain HTTPS + basic auth through httpx, no extra dependency).

Layout: one index per kind, ``<prefix>-<kind>-v<INDEX_VERSION>``, reached through the alias ``<prefix>-<kind>`` (writes)
and the alias ``<prefix>-library`` over every kind (searches). A mapping change bumps INDEX_VERSION; ``rebuild``
(``python -m app.modules.knowledge.cli backfill --rebuild``) fills new indices and moves the aliases at once.

Texts are analysed three ways: ``ehimaya_folded`` (case, accents and Arabic letter variants folded, no stemming),
``.ar`` (Arabic normalisation, stop words, light stemming) and ``.fr`` (elision, stop words, light French stemming).
The index never decides access: every hit is checked again against ``knowledge.search_doc`` before it is returned.
"""

import json
import ssl
from pathlib import Path
from typing import Any, Protocol

import httpx
import structlog

from app.core.config import get_settings
from app.modules.knowledge.domain import Kind
from app.modules.knowledge.text import HL_CLOSE, HL_OPEN

log = structlog.get_logger()

INDEX_VERSION = 1

ANALYSIS: dict[str, Any] = {
    "filter": {
        "ehimaya_ar_stop": {"type": "stop", "stopwords": "_arabic_"},
        "ehimaya_ar_stem": {"type": "stemmer", "language": "arabic"},
        "ehimaya_fr_elision": {
            "type": "elision",
            "articles_case": True,
            "articles": ["l", "m", "t", "qu", "n", "s", "j", "d", "c", "jusqu", "quoiqu", "lorsqu", "puisqu"],
        },
        "ehimaya_fr_stop": {"type": "stop", "stopwords": "_french_"},
        "ehimaya_fr_stem": {"type": "stemmer", "language": "light_french"},
    },
    "analyzer": {
        "ehimaya_folded": {
            "tokenizer": "standard",
            "filter": ["lowercase", "asciifolding", "decimal_digit", "arabic_normalization"],
        },
        "ehimaya_ar": {
            "tokenizer": "standard",
            "filter": ["lowercase", "decimal_digit", "ehimaya_ar_stop", "arabic_normalization", "ehimaya_ar_stem"],
        },
        "ehimaya_fr": {
            "tokenizer": "standard",
            "filter": ["ehimaya_fr_elision", "lowercase", "ehimaya_fr_stop", "asciifolding", "ehimaya_fr_stem"],
        },
    },
}

_TEXT = {
    "type": "text",
    "analyzer": "ehimaya_folded",
    "fields": {"ar": {"type": "text", "analyzer": "ehimaya_ar"}, "fr": {"type": "text", "analyzer": "ehimaya_fr"}},
}
MAPPINGS: dict[str, Any] = {
    "dynamic": "strict",
    "properties": {
        "kind": {"type": "keyword"},
        "ref_id": {"type": "keyword"},
        "title": _TEXT,
        "body": {**_TEXT, "term_vector": "with_positions_offsets"},
        "lang": {"type": "keyword"},
        "date": {"type": "date"},
        "gouvernorats": {"type": "short"},
        "access": {"type": "keyword"},
        "categories": {"type": "keyword"},
        "incident_id": {"type": "keyword"},
    },
}
SEARCH_FIELDS = ["title^3", "title.ar^3", "title.fr^3", "body", "body.ar", "body.fr"]


class SearchUnavailable(Exception):
    """OpenSearch is not configured, unreachable or answered an error: use the PostgreSQL fallback."""


class Engine(Protocol):
    async def ensure_indices(self) -> None: ...

    async def bulk(self, upserts: list[dict[str, Any]], deletes: list[tuple[str, str]]) -> None: ...

    async def search(self, body: dict[str, Any]) -> dict[str, Any]: ...

    async def health(self) -> str | None: ...


def doc_id(kind: str, ref_id: str) -> str:
    return f"{kind}:{ref_id}"


class OpenSearch:
    def __init__(
        self, base_url: str, user: str, password: str, ca_file: Path | None, prefix: str, timeout_s: float
    ) -> None:
        self.prefix = prefix
        verify: Any = ssl.create_default_context(cafile=str(ca_file)) if ca_file is not None else True
        self._http = httpx.AsyncClient(
            base_url=base_url, auth=(user, password), verify=verify, timeout=httpx.Timeout(timeout_s)
        )

    def alias(self, kind: str) -> str:
        return f"{self.prefix}-{kind}"

    @property
    def library(self) -> str:
        return f"{self.prefix}-library"

    def index(self, kind: str, suffix: str | None = None) -> str:
        """Physical index of a kind; ``suffix`` names the indices of a rebuild (``-v1-r20261020120000``)."""
        return f"{self.prefix}-{kind}-v{INDEX_VERSION}" + (f"-{suffix}" if suffix else "")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise SearchUnavailable(type(exc).__name__) from exc
        if response.status_code >= 500 or response.status_code in (401, 403):
            raise SearchUnavailable(f"HTTP {response.status_code}")
        return response

    async def health(self) -> str | None:
        """Cluster status (green/yellow/red), None when unreachable."""
        try:
            response = await self._request("GET", "/_cluster/health")
        except SearchUnavailable:
            return None
        status: str | None = response.json().get("status") if response.status_code == 200 else None
        return status

    async def _create(self, index: str, aliases: list[str]) -> None:
        body = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0, "analysis": ANALYSIS},
            "mappings": MAPPINGS,
            "aliases": {name: {} for name in aliases},
        }
        response = await self._request("PUT", f"/{index}", json=body)
        if response.status_code not in (200, 201) and "resource_already_exists" not in response.text:
            raise SearchUnavailable(f"create {index}: HTTP {response.status_code}")

    async def ensure_indices(self) -> None:
        """Create the current indices with their aliases when no index is behind a kind's alias yet."""
        for kind in Kind:
            response = await self._request("HEAD", f"/{self.alias(kind)}")
            if response.status_code == 200:
                continue
            await self._create(self.index(kind), [self.alias(kind), self.library])

    async def bulk(self, upserts: list[dict[str, Any]], deletes: list[tuple[str, str]]) -> None:
        """Index ``upserts`` (documents with "kind" and "ref_id") and delete ``deletes`` (kind, ref_id)."""
        await self.bulk_to(upserts, deletes, None)

    async def bulk_to(self, upserts: list[dict[str, Any]], deletes: list[tuple[str, str]], suffix: str | None) -> None:
        lines: list[str] = []
        for source in upserts:
            target = self.index(source["kind"], suffix) if suffix else self.alias(source["kind"])
            lines.append(json.dumps({"index": {"_index": target, "_id": doc_id(source["kind"], source["ref_id"])}}))
            lines.append(json.dumps(source, ensure_ascii=False))
        for kind, ref_id in deletes:
            target = self.index(kind, suffix) if suffix else self.alias(kind)
            lines.append(json.dumps({"delete": {"_index": target, "_id": doc_id(kind, ref_id)}}))
        if not lines:
            return
        response = await self._request(
            "POST",
            "/_bulk",
            content=("\n".join(lines) + "\n").encode(),
            headers={"Content-Type": "application/x-ndjson"},
        )
        if response.status_code != 200:
            raise SearchUnavailable(f"bulk: HTTP {response.status_code}")
        result = response.json()
        if result.get("errors"):
            failed = [
                item
                for entry in result.get("items", [])
                for item in entry.values()
                # A delete of a document that was never indexed is fine.
                if item.get("status", 200) >= 300 and not (item.get("status") == 404 and "delete" in entry)
            ]
            if failed:
                log.warning("knowledge.bulk_errors", count=len(failed), first=str(failed[0].get("error"))[:300])
                raise SearchUnavailable("bulk_item_errors")

    async def search(self, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", f"/{self.library}/_search", json=body)
        if response.status_code != 200:
            raise SearchUnavailable(f"search: HTTP {response.status_code}")
        data: dict[str, Any] = response.json()
        return data

    # ---------------------------------------------------------------- rebuild (backfill --rebuild)

    async def create_rebuild(self, suffix: str) -> None:
        for kind in Kind:
            await self._create(self.index(kind, suffix), [])

    async def switch_to(self, suffix: str) -> None:
        """Point every alias at the indices of a rebuild in one atomic call, then drop the older indices."""
        actions: list[dict[str, Any]] = []
        old: list[str] = []
        for kind in Kind:
            response = await self._request("GET", f"/{self.alias(kind)}/_alias/{self.alias(kind)}")
            current = list(response.json()) if response.status_code == 200 else []
            for index in current:
                if index != self.index(kind, suffix):
                    old.append(index)
                    actions.append({"remove": {"index": index, "alias": self.alias(kind)}})
                    actions.append({"remove": {"index": index, "alias": self.library}})
            actions.append({"add": {"index": self.index(kind, suffix), "alias": self.alias(kind)}})
            actions.append({"add": {"index": self.index(kind, suffix), "alias": self.library}})
        response = await self._request("POST", "/_aliases", json={"actions": actions})
        if response.status_code != 200:
            raise SearchUnavailable(f"aliases: HTTP {response.status_code}")
        for index in old:
            await self._request("DELETE", f"/{index}")

    async def close(self) -> None:
        await self._http.aclose()


def highlight_spec() -> dict[str, Any]:
    fragment = {"fragment_size": 220, "number_of_fragments": 1, "no_match_size": 0}
    return {
        "pre_tags": [HL_OPEN],
        "post_tags": [HL_CLOSE],
        "require_field_match": False,
        "fields": {"body": fragment, "body.ar": fragment, "body.fr": fragment},
    }


_engine: Engine | None = None
_default: OpenSearch | None = None
_override = False


_ca_warned = False


def get_engine() -> Engine | None:
    """None when the PostgreSQL backend is configured (SEARCH_BACKEND=postgres or no OPENSEARCH_URL)."""
    global _default
    if _override:
        return _engine
    settings = get_settings()
    if settings.search_engine != "opensearch":
        return None
    if _default is None:
        assert settings.opensearch_url is not None and settings.opensearch_password is not None
        ca_file = settings.opensearch_ca_file
        if ca_file is not None and not ca_file.is_file():
            # The node writes its CA on first start (infra/opensearch): until then, PostgreSQL answers.
            global _ca_warned
            if not _ca_warned:
                log.warning("opensearch_ca_missing", path=str(ca_file))
                _ca_warned = True
            return None
        _default = OpenSearch(
            settings.opensearch_url,
            settings.opensearch_user,
            settings.opensearch_password.get_secret_value(),
            ca_file,
            settings.opensearch_index_prefix,
            settings.opensearch_timeout_s,
        )
    return _default


def set_engine(engine: Engine | None, *, override: bool = True) -> None:
    """Used by tests: inject an engine (or None = PostgreSQL); ``override=False`` restores the configured one."""
    global _engine, _override
    _engine, _override = engine, override
