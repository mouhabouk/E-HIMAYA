"""Dump the API's routes and the database tables as JSON, for the UI reference (scripts/ui_reference/build.py).

Run with the API's own interpreter, from services/api:  .venv/bin/python ../../scripts/ui_reference/backend_dump.py
Reads code only: no database, no network.
"""

import inspect
import json
import os
import sys
from pathlib import Path

# Import-only placeholders, the same as the API's tests use (tests/conftest.py): nothing connects to anything.
for _name, _value in {
    "DATABASE_URL": "postgresql+asyncpg://ehimaya:ehimaya@localhost:5432/ehimaya",
    "OIDC_ISSUERS": "http://localhost:8080/realms/ehimaya-public,http://localhost:8080/realms/ehimaya-staff",
    "OIDC_AUDIENCE": "ehimaya-api",
    "ANON_PSEUDONYM_SECRET": "ui-reference-placeholder-secret-0001",
    "FIELD_ENCRYPTION_KEY": "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzJieXQ=",
    "TUSD_HOOK_SECRET": "ui-reference-placeholder-0001",
    "MEDIAMTX_HOOK_TOKEN": "ui-reference-placeholder-0001",
    "MEDIAMTX_API_PASSWORD": "ui-reference-placeholder-0001",
    "VISION_CALLBACK_TOKEN": "ui-reference-placeholder-0001",
    "VISION_READ_PASSWORD": "ui-reference-placeholder-0001",
    "SENSOR_GATEWAY_TOKEN": "ui-reference-placeholder-0001",
    "STREAM_SIM_TOKEN": "ui-reference-placeholder-0001",
    "TELEPHONY_ARI_PASSWORD": "ui-reference-placeholder-0001",
    "SMS_INBOUND_SECRET": "ui-reference-placeholder-0001",
    "TELEPHONY_SIM_TOKEN": "ui-reference-placeholder-0001",
    "BACKGROUND_WORKERS": "false",
}.items():
    os.environ.setdefault(_name, _value)
sys.path.insert(0, os.getcwd())

import app.modules.models  # noqa: E402,F401  (registers every table)
from app.core.db import Base  # noqa: E402

ROOT = Path(os.getcwd()).resolve().parents[1]


def rel(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return path


def tables() -> list[dict]:
    out = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = mapper.local_table
        if table is None or not hasattr(table, "columns"):
            continue
        file = inspect.getsourcefile(cls) or ""
        try:
            line = inspect.getsourcelines(cls)[1]
        except (OSError, TypeError):
            line = 0
        cols = []
        for col in table.columns:
            cols.append({"name": col.name, "type": str(col.type), "nullable": bool(col.nullable)})
        out.append(
            {
                "schema": table.schema or "public",
                "table": table.name,
                "model": cls.__name__,
                "module": cls.__module__,
                "file": rel(file),
                "line": line,
                "columns": cols,
            }
        )
    return out


def routes() -> list[dict]:
    from fastapi.routing import APIRoute

    from app.main import app

    def flat(items):
        # FastAPI 0.162 keeps included routers as one entry each; their effective routes carry the full path.
        for item in items:
            if isinstance(item, APIRoute):
                yield item
            elif hasattr(item, "effective_candidates"):
                for ctx in item.effective_candidates():
                    if getattr(ctx, "methods", None) and getattr(ctx, "endpoint", None):
                        yield ctx

    import re
    from pathlib import Path

    models = {m.class_.__name__: f"{m.local_table.schema}.{m.local_table.name}" for m in Base.registry.mappers}
    word = re.compile(r"\b(" + "|".join(sorted(models, key=len, reverse=True)) + r")\b")
    package_cache: dict[str, list[str]] = {}

    def package_tables(file: str) -> list[str]:
        # Tables named anywhere in the route's module package (router, service, models), when the handler
        # itself names none.
        folder = str(Path(file).parent)
        if folder not in package_cache:
            text = "".join(p.read_text(encoding="utf-8") for p in Path(folder).glob("*.py"))
            package_cache[folder] = sorted({models[n] for n in word.findall(text)})
        return package_cache[folder]

    func_cache: dict[str, dict[str, str]] = {}

    def package_functions(file: str) -> dict[str, str]:
        folder = str(Path(file).parent)
        if folder not in func_cache:
            found: dict[str, str] = {}
            for path in Path(folder).glob("*.py"):
                text = path.read_text(encoding="utf-8")
                for m in re.finditer(
                    r"^(?:async )?def (\w+)\(.*?(?=^(?:async )?def |^class |^@|\Z)", text, re.M | re.S
                ):
                    found.setdefault(m.group(1), m.group(0))
            func_cache[folder] = found
        return func_cache[folder]

    def handler_tables(source: str, file: str) -> list[str]:
        # The handler's own text plus the package functions it calls (one level).
        functions = package_functions(file) if file else {}
        text = source + "".join(functions.get(n, "") for n in set(re.findall(r"(\w+)\(", source)))
        return sorted({models[n] for n in word.findall(text)})

    out = []
    for route in flat(app.routes):
        fn = route.endpoint
        file = inspect.getsourcefile(fn) or ""
        try:
            line = inspect.getsourcelines(fn)[1]
        except (OSError, TypeError):
            line = 0
        body: list[str] = []
        if route.body_field is not None:
            model = getattr(route.body_field, "type_", None) or getattr(route.body_field.field_info, "annotation", None)
            fields = getattr(model, "model_fields", None)
            if fields:
                body = list(fields)
        try:
            source = inspect.getsource(fn)
        except (OSError, TypeError):
            source = ""
        direct = handler_tables(source, file)
        out.append(
            {
                "tables": direct,
                "package_tables": package_tables(file) if file else [],
                "path": route.path,
                "methods": sorted(route.methods or []),
                "module": fn.__module__,
                "function": fn.__name__,
                "file": rel(file),
                "line": line,
                "body": body,
            }
        )
    return out


if __name__ == "__main__":
    found = routes()  # first: importing the app registers the few tables app.modules.models leaves out
    json.dump({"tables": tables(), "routes": found}, sys.stdout, ensure_ascii=False)
