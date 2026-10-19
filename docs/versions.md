# الإصدارات المثبتة (المرحلة 1)

تُحدَّث هذه القائمة مع كل مرحلة. تُعتمد الإصدارات الدقيقة أدناه في الكود والحاويات.

## الحاويات

| المكون | الصورة | الرخصة |
|---|---|---|
| PostgreSQL + PostGIS | `postgres:17-bookworm` + `postgresql-17-postgis-3` + `postgresql-17-pgvector` (PGDG) | PostgreSQL / GPL-2.0 |
| Valkey | `valkey/valkey:8.1-alpine` | BSD-3 |
| NATS | `nats:2.10-alpine` | Apache-2.0 |
| SeaweedFS (S3) | `chrislusf/seaweedfs:3.97` | Apache-2.0 |
| Keycloak | `keycloak/keycloak:26.3` (اختُبر 26.3.5) | Apache-2.0 |
| الخلفية | `python:3.12-slim` | PSF |

## حزم Python (الخلفية)

مثبتة في `services/api/pyproject.toml`، وشجرة التبعيات كاملة في `services/api/uv.lock`.

| الحزمة | الإصدار |
|---|---|
| fastapi | 0.146.0 |
| uvicorn | 0.54.0 |
| sqlalchemy | 2.1.5 |
| asyncpg | 0.32.0 |
| alembic | 1.20.0 |
| pydantic-settings | 2.16.0 |
| geoalchemy2 | 0.20.0 |
| pgvector | 0.5.1 |
| pyjwt | 2.15.1 |
| redis | 8.1.0 |
| nats-py | 2.16.0 |
| structlog | 26.1.0 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |
| ruff / mypy | 0.17.1 / 2.4.0 |
