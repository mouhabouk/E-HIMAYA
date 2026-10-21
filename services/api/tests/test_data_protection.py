"""Phase 5.5 data protection: field encryption at rest (A5), retention jobs and citizen rights (A6)."""

import base64
import os
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.config import Settings, get_settings, parse_keyring
from app.core.crypto import FieldCipher, get_cipher, search_terms
from app.core.db import get_system_sessionmaker
from app.modules.identity.models import DETACHED_ACCOUNT_ID, phone_index
from app.modules.privacy import cli, retention, rotation
from tests.conftest import (
    SFAX,
    FakeStore,
    TokenFactory,
    accept_charter,
    bearer,
    device_headers,
    report_body,
)

KEY_1 = os.urandom(32)
KEY_2 = os.urandom(32)
ROTATION_KEY = base64.b64encode(b"rotation-test-key-rotation-test!").decode()


def citizen_headers(make_token: TokenFactory) -> dict[str, str]:
    email = f"dp{secrets.token_hex(5)}@example.tn"
    return bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Amel Jaziri"))


def profile_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "first_name": "Amel",
        "last_name": "Jaziri",
        "cin": f"{secrets.randbelow(100_000_000):08d}",
        "phone": f"+2165{secrets.randbelow(10_000_000):07d}",
        "gouvernorat_code": 61,
        "delegation_id": 6101,
        "address": f"Impasse des Jasmins {secrets.token_hex(3)}",
        "locale": "fr",
        "medical": {"blood_group": "O-", "allergies": "pénicilline", "emergency_contact_phone": "+21698765432"},
    }
    body.update(overrides)
    return body


async def raw_row(session: AsyncSession, sql: str, **params: Any) -> str:
    """The whole row as PostgreSQL stores it (bytea as hex), to prove no clear text is at rest."""
    found = await session.scalar(text(sql), params)
    assert found is not None
    return str(found)


# ---------------------------------------------------------------- the cipher


def test_cipher_round_trip_and_context_binding() -> None:
    cipher = FieldCipher(KEY_1)
    blob = cipher.encrypt("+21698123456", context="identity.profile.phone")
    assert blob[0] == 1 and b"98123456" not in blob
    assert cipher.decrypt(blob, context="identity.profile.phone") == "+21698123456"
    with pytest.raises(Exception):  # noqa: B017 (InvalidTag: another column's ciphertext does not open)
        cipher.decrypt(blob, context="identity.profile.address")
    assert cipher.encrypt("x", context="c") != cipher.encrypt("x", context="c")  # random nonce


def test_key_rotation_reads_old_versions_and_keeps_blind_indexes() -> None:
    old = FieldCipher(KEY_1)
    new = FieldCipher({1: KEY_1, 2: KEY_2})
    assert new.active == 2 and new.versions == {1, 2}
    old_blob = old.encrypt("Rue de Marseille", context="ctx")
    new_blob = new.encrypt("Rue de Marseille", context="ctx")
    assert new_blob[0] == 2
    assert new.decrypt(old_blob, context="ctx") == new.decrypt(new_blob, context="ctx") == "Rue de Marseille"
    with pytest.raises(ValueError, match="version"):
        old.decrypt(new_blob, context="ctx")
    # Lookups do not move with rotation: the index sub-key comes from version 1.
    assert old.blind_index("+21698123456", context="p") == new.blind_index("+21698123456", context="p")
    assert FieldCipher({1: KEY_1, 2: KEY_2}, active=1).encrypt("a", context="c")[0] == 1
    with pytest.raises(ValueError):
        FieldCipher({2: KEY_2})
    with pytest.raises(ValueError):
        FieldCipher({1: KEY_1}, active=3)


def test_keyring_setting_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    good = base64.b64encode(KEY_2).decode()
    assert parse_keyring(f" 2:{good} , 3:{good}") == {2: KEY_2, 3: KEY_2}
    for bad in (
        f"1:{good}",
        f"2:{good},2:{good}",
        "2:not-base64!",
        f"x:{good}",
        "2:" + base64.b64encode(b"short").decode(),
    ):
        with pytest.raises(ValueError):
            parse_keyring(bad)
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", f"2:{good}")
    monkeypatch.setenv("FIELD_ENCRYPTION_ACTIVE_VERSION", "3")
    with pytest.raises(ValueError, match="ACTIVE_VERSION"):
        Settings()
    monkeypatch.setenv("FIELD_ENCRYPTION_ACTIVE_VERSION", "")
    assert Settings().field_encryption_active_version is None


def test_search_terms_fold_case_accents_and_arabic_variants() -> None:
    assert search_terms("Incendié à l'ÉCOLE, école!") == ["incendie", "ecole"]
    assert search_terms("أُمٌّ في المدرسةِ") == search_terms("ام في المدرسه")
    assert search_terms("a b") == []


# ---------------------------------------------------------------- encryption at rest


async def test_profile_fields_are_encrypted_at_rest(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = citizen_headers(make_token)
    body = profile_body()
    r = await client.put("/api/v1/me/profile", json=body, headers=headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["phone"] == body["phone"] and out["address"] == body["address"]
    assert out["medical"] == {
        "blood_group": "O-",
        "conditions": None,
        "allergies": "pénicilline",
        "medications": None,
        "emergency_contact_name": None,
        "emergency_contact_phone": "+21698765432",
    }
    assert (await client.get("/api/v1/me/profile", headers=headers)).json() == out

    row = await raw_row(
        session, "SELECT p::text FROM identity.profile p WHERE phone_hash = :h", h=phone_index(body["phone"])
    )
    for clear in (body["phone"], body["phone"][4:], body["address"], "pénicilline", "O-", body["cin"]):
        assert clear not in row
    assert "Amel" in row  # names stay in clear (partial search of volunteers), by design

    # Omitting "medical" keeps it; null erases it.
    again = profile_body(cin=body["cin"], phone=body["phone"])
    del again["medical"]
    assert (await client.put("/api/v1/me/profile", json=again, headers=headers)).json()["medical"] == out["medical"]
    erased = (await client.put("/api/v1/me/profile", json={**again, "medical": None}, headers=headers)).json()
    assert erased["medical"] is None
    r = await client.put("/api/v1/me/profile", json=profile_body(medical={"blood_group": "Z+"}), headers=headers)
    assert r.status_code == 422


async def test_report_text_is_encrypted_and_still_searchable(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, staff: Any
) -> None:
    headers = citizen_headers(make_token)
    await accept_charter(client, headers)
    word = f"Zarzis{secrets.token_hex(3)}"
    body = report_body(text=f"Incendie à l'école {word}, deux élèves bloqués", lang="fr")
    report = (await client.post("/api/v1/reports", json=body, headers=headers)).json()
    assert report["text"] == body["text"]

    row = await raw_row(session, "SELECT r::text FROM reports.report r WHERE id = :id", id=report["id"])
    assert word not in row and "école" not in row and "Incendie" not in row

    operator = staff(["operator"], gouvernorat=61)
    for q in (word.lower(), f"ECOLE {word}", report["tracking_code"]):
        items = (await client.get("/api/v1/staff/reports", params={"q": q}, headers=operator)).json()["items"]
        assert [i["text"] for i in items if i["id"] == report["id"]] == [body["text"]], q
    # Whole words only: a fragment of a word does not match the encrypted text.
    items = (await client.get("/api/v1/staff/reports", params={"q": word[:-2]}, headers=operator)).json()["items"]
    assert all(i["id"] != report["id"] for i in items)
    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=operator)).json()
    assert detail["text"] == body["text"]


async def test_volunteer_free_text_encrypted_and_phone_search(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, staff: Any
) -> None:
    headers = citizen_headers(make_token)
    body = profile_body()
    assert (await client.put("/api/v1/me/profile", json=body, headers=headers)).status_code == 200
    application = {
        "skills": ["first_aid", "other"],
        "other_skill": "plongée sous-marine",
        "availability": "continuous",
        "period_from": date.today().isoformat(),
        "notes": "Disponible le week-end, appeler mon frère",
    }
    r = await client.put("/api/v1/me/volunteer", json=application, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == application["notes"] and r.json()["other_skill"] == "plongée sous-marine"
    row = await raw_row(
        session,
        "SELECT v::text FROM identity.volunteer v JOIN identity.profile p USING (user_id) WHERE p.phone_hash = :h",
        h=phone_index(body["phone"]),
    )
    assert "frère" not in row and "plongée" not in row

    manager = staff(["ops_manager"], gouvernorat=61)
    local = body["phone"][4:]
    for q in (body["phone"], local, f"{local[:2]} {local[2:5]} {local[5:]}", "216" + local):
        items = (await client.get("/api/v1/staff/volunteers", params={"q": q}, headers=manager)).json()["items"]
        assert [i["phone"] for i in items] == [body["phone"]], q


async def test_ai_reads_clear_text_and_its_results_are_encrypted(
    client: httpx.AsyncClient,
    citizen: dict[str, str],
    staff: Any,
    fake_ai: Any,
    fake_store: FakeStore,
    session: AsyncSession,
) -> None:
    from tests.aihelpers import add_audio, analyse, create, detail, spot

    await accept_charter(client, citizen)
    marker = f"Kerkennah{secrets.token_hex(3)}"
    report = await create(client, citizen, text=f"Incendie au port de {marker}", lang="fr", location=spot())
    media_id = await add_audio(session, fake_store, report["id"])
    assert await analyse(report["id"], fake_ai, fake_store)

    # The API decrypts before calling the AI service.
    extract_input = next(arg for name, arg in fake_ai.calls if name == "extract")
    assert marker in extract_input and "deuxième étage" in extract_input
    d = await detail(client, staff, report["id"])
    [transcript] = d["analysis"]["transcripts"]
    assert transcript["text"] == "Il y a le feu au deuxième étage." and transcript["translation_ar"].startswith(
        "ترجمة:"
    )
    assert d["analysis"]["extraction"]["injured_count"] == 2 and d["text_ar"].startswith("ترجمة:")

    media_row = await raw_row(session, "SELECT m::text FROM reports.media m WHERE id = :id", id=media_id)
    assert "deuxième" not in media_row and "ترجمة" not in media_row and "translation_ar" not in media_row
    report_row = await raw_row(session, "SELECT r::text FROM reports.report r WHERE id = :id", id=report["id"])
    assert marker not in report_row and "ترجمة" not in report_row
    analysis_row = await raw_row(session, "SELECT a::text FROM ai.analysis a WHERE report_id = :id", id=report["id"])
    assert "summary_ar" not in analysis_row and "injured_count" not in analysis_row
    # The Arabic translation is searchable by word too.
    operator = staff(["operator"], gouvernorat=61)
    items = (await client.get("/api/v1/staff/reports", params={"q": "ترجمه"}, headers=operator)).json()["items"]
    assert any(i["id"] == report["id"] for i in items)


async def test_no_clear_text_in_encrypted_columns(session: AsyncSession) -> None:
    """Every encrypted column holds well-formed ciphertext of a configured key version."""
    versions = sorted(get_cipher().versions)
    for col in rotation.encrypted_columns():
        bad = await session.scalar(
            text(
                f"SELECT count(*) FROM {col.table} WHERE {col.column} IS NOT NULL "  # noqa: S608 (ORM identifiers)
                f"AND (octet_length({col.column}) < 29 OR NOT get_byte({col.column}, 0) = ANY(:v))"
            ),
            {"v": versions},
        )
        assert bad == 0, f"{col.table}.{col.column}"
    names = {f"{c.table}.{c.column}" for c in rotation.encrypted_columns()}
    assert {
        "identity.profile.cin_enc",
        "identity.profile.phone_enc",
        "identity.profile.address_enc",
        "identity.profile.medical_enc",
        "reports.report.text_original_enc",
        "reports.report.text_ar_enc",
        "reports.media.transcript_enc",
        "reports.media.translation_ar_enc",
        "identity.volunteer.other_skill_enc",
        "identity.volunteer.notes_enc",
        "ai.analysis.extraction_enc",
    } <= names
    plain = await session.scalar(
        text(
            "SELECT count(*) FROM information_schema.columns WHERE (table_schema, table_name, column_name) IN "
            "(('identity', 'profile', 'phone'), ('identity', 'profile', 'address'), "
            "('reports', 'report', 'text_original'), ('reports', 'report', 'text_ar'), "
            "('reports', 'media', 'transcript'), ('identity', 'volunteer', 'notes'))"
        )
    )
    assert plain == 0


async def test_reencrypt_moves_every_row_to_the_active_key(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = citizen_headers(make_token)
    body = profile_body()
    assert (await client.put("/api/v1/me/profile", json=body, headers=headers)).status_code == 200
    await accept_charter(client, headers)
    report = (await client.post("/api/v1/reports", json=report_body(), headers=headers)).json()

    sessionmaker = get_system_sessionmaker()

    settings = get_settings()  # patched in place: the app keeps its reference to this object

    def use(active: int | None) -> None:
        monkeypatch.setattr(settings, "field_encryption_keys", SecretStr(f"2:{ROTATION_KEY}"))
        monkeypatch.setattr(settings, "field_encryption_active_version", active)
        crypto.get_cipher.cache_clear()

    try:
        use(None)  # version 2 becomes active, version 1 still readable
        assert get_cipher().active == 2
        assert (await client.get("/api/v1/me/profile", headers=headers)).json()["phone"] == body["phone"]
        remaining = await rotation.reencrypt(sessionmaker, dry_run=True)
        assert remaining["identity.profile.phone_enc"] >= 1 and remaining["reports.report.text_original_enc"] >= 1
        done = await rotation.reencrypt(sessionmaker, batch=50)
        assert done == remaining or all(done[k] >= remaining[k] for k in remaining)
        assert all(v == 0 for v in (await rotation.reencrypt(sessionmaker, dry_run=True)).values())
        versions = await session.scalar(
            text("SELECT array_agg(DISTINCT get_byte(phone_enc, 0)) FROM identity.profile WHERE phone_enc IS NOT NULL")
        )
        assert versions == [2]
        # Still readable, blind-index lookups unchanged.
        assert (await client.get("/api/v1/me/profile", headers=headers)).json()["phone"] == body["phone"]
        mine = (await client.get("/api/v1/reports/mine", headers=headers)).json()
        assert mine["items"][0]["text"] == report["text"]
        found = await session.scalar(
            text("SELECT count(*) FROM identity.profile WHERE phone_hash = :h"), {"h": phone_index(body["phone"])}
        )
        assert found == 1
    finally:
        # Back to version 1 everywhere: the rest of the suite runs without key 2.
        use(1)
        await rotation.reencrypt(sessionmaker)
        monkeypatch.undo()
        crypto.get_cipher.cache_clear()
    assert (await client.get("/api/v1/me/profile", headers=headers)).json()["phone"] == body["phone"]


# ---------------------------------------------------------------- retention


async def test_retention_jobs(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, fake_store: FakeStore
) -> None:
    sessionmaker = get_system_sessionmaker()
    long_ago = datetime.now(UTC) - timedelta(days=6 * 365)
    headers = citizen_headers(make_token)
    await accept_charter(client, headers)
    report = (
        await client.post("/api/v1/reports", json=report_body(text="Fuite de gaz chez Mme Jaziri"), headers=headers)
    ).json()
    recent = (await client.post("/api/v1/reports", json=report_body(), headers=headers)).json()
    anon = device_headers()
    await accept_charter(client, anon)
    token = "fcm-" + secrets.token_urlsafe(40)
    r = await client.put(
        "/api/v1/devices",
        json={"token": token, "platform": "android", "locale": "ar", "location_alerts": True, **SFAX},
        headers=headers,
    )
    assert r.status_code == 204, r.text
    old_token = "fcm-" + secrets.token_urlsafe(40)
    await client.put("/api/v1/devices", json={"token": old_token, "platform": "ios", "locale": "fr"}, headers=headers)

    async with sessionmaker() as s, s.begin():
        user_id = await s.scalar(text("SELECT user_id FROM reports.report WHERE id = :id"), {"id": report["id"]})
        anon_id = await s.scalar(
            text("SELECT user_id FROM identity.consent ORDER BY id DESC LIMIT 1")
        )  # the anonymous device accepted the charter last
        await s.execute(
            text(
                "INSERT INTO reports.media (report_id, kind, object_key, sha256, status, transcript_enc) "
                "VALUES (:r, 'audio', :k, repeat('b', 64), 'stored', NULL)"
            ),
            {"r": report["id"], "k": f"reports/{report['id']}/voice.m4a"},
        )
        await s.execute(
            text("UPDATE reports.report SET status = 'closed', updated_at = :t WHERE id = :id"),
            {"t": long_ago, "id": report["id"]},
        )
        await s.execute(text("UPDATE reports.report SET status = 'closed' WHERE id = :id"), {"id": recent["id"]})
        await s.execute(
            text("UPDATE identity.account SET created_at = :t WHERE user_id = :u"), {"t": long_ago, "u": anon_id}
        )
        await s.execute(
            text("UPDATE notify.device SET updated_at = :t WHERE token = :k"), {"t": long_ago, "k": old_token}
        )
        await s.execute(
            text("UPDATE notify.device SET updated_at = :t WHERE token = :k"),
            {"t": datetime.now(UTC) - timedelta(days=40), "k": token},
        )
        old_event = await s.scalar(
            text(
                "INSERT INTO events.outbox (subject, payload, published_at) VALUES ('test.old', '{}', :t) RETURNING id"
            ),
            {"t": long_ago},
        )
        pending_event = await s.scalar(
            text("INSERT INTO events.outbox (subject, payload) VALUES ('test.pending', '{}') RETURNING id")
        )
        old_push = await s.scalar(
            text(
                "INSERT INTO notify.outbox (channel, user_id, payload, status, created_at) "
                "VALUES ('push', :u, '{}', 'sent', :t) RETURNING id"
            ),
            {"u": user_id, "t": long_ago},
        )
        await s.execute(
            text(
                "INSERT INTO identity.consent (user_id, charter_version, locale, accepted_at) "
                "VALUES (:u, '2020-01', 'ar', :t)"
            ),
            {"u": user_id, "t": long_ago},
        )
        erasure = await s.scalar(
            text("INSERT INTO identity.erasure_request (keycloak_sub, disabled_at) VALUES ('sub-x', :t) RETURNING id"),
            {"t": long_ago},
        )

    counts = await retention.run_all(sessionmaker)
    assert all(v >= 0 for v in counts.values()), counts
    assert counts["reports"] >= 1 and counts["events"] >= 1 and counts["devices"] >= 1

    async with sessionmaker() as s:
        row = (
            await s.execute(
                text(
                    "SELECT user_id, text_original_enc, cardinality(search_tokens) AS words, client_uuid, "
                    "anonymised_at, location_accuracy_m, category, status, ST_X(location::geometry) AS lon, "
                    "ST_Y(location::geometry) AS lat FROM reports.report WHERE id = :id"
                ),
                {"id": report["id"]},
            )
        ).one()
        assert row.user_id == DETACHED_ACCOUNT_ID and row.text_original_enc is None and row.words == 0
        assert row.client_uuid is None and row.anonymised_at is not None and row.location_accuracy_m is None
        assert (row.category, row.status) == ("fire", "closed")
        assert round(row.lon, 2) == pytest.approx(row.lon) and round(row.lat, 2) == pytest.approx(row.lat)
        assert (
            await s.scalar(text("SELECT count(*) FROM reports.media WHERE report_id = :id"), {"id": report["id"]}) == 0
        )
        assert f"reports/{report['id']}/voice.m4a" in fake_store.deleted
        kept = await s.scalar(
            text("SELECT user_id = :u AND anonymised_at IS NULL FROM reports.report WHERE id = :id"),
            {"u": user_id, "id": recent["id"]},
        )
        assert kept
        assert await s.scalar(text("SELECT count(*) FROM events.outbox WHERE id = :i"), {"i": old_event}) == 0
        assert await s.scalar(text("SELECT count(*) FROM events.outbox WHERE id = :i"), {"i": pending_event}) == 1
        assert await s.scalar(text("SELECT count(*) FROM notify.outbox WHERE id = :i"), {"i": old_push}) == 0
        devices = dict(
            (
                await s.execute(
                    text("SELECT token, location IS NOT NULL FROM notify.device WHERE token IN (:a, :b)"),
                    {"a": token, "b": old_token},
                )
            ).all()
        )
        assert devices == {token: False}
        consents = list(
            await s.scalars(text("SELECT charter_version FROM identity.consent WHERE user_id = :u"), {"u": user_id})
        )
        assert consents == ["2026-10"]
        assert await s.scalar(text("SELECT count(*) FROM identity.account WHERE user_id = :u"), {"u": anon_id}) == 0
        assert await s.scalar(text("SELECT count(*) FROM identity.erasure_request WHERE id = :i"), {"i": erasure}) == 0
        audited = await s.scalar(text("SELECT count(*) FROM audit.log WHERE action = 'retention.anonymise'"))
        assert audited >= 1

    # Idempotent: nothing left for these rows, and the anonymised report stays as it is.
    again = await retention.run_job(sessionmaker, "reports", retention.anonymise_reports)
    assert again == 0


async def test_retention_job_skips_when_another_process_holds_it() -> None:
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as holder, holder.begin():
        await holder.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": retention._lock_key("events")})
        assert await retention.run_job(sessionmaker, "events", retention.purge_events) == 0


# ---------------------------------------------------------------- citizen rights


async def test_export_registered_citizen(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = citizen_headers(make_token)
    body = profile_body()
    assert (await client.put("/api/v1/me/profile", json=body, headers=headers)).status_code == 200
    await accept_charter(client, headers)
    report = (await client.post("/api/v1/reports", json=report_body(text="Inondation rue 5"), headers=headers)).json()
    token = "fcm-" + secrets.token_urlsafe(40)
    await client.put("/api/v1/devices", json={"token": token, "platform": "android", "locale": "fr"}, headers=headers)

    r = await client.get("/api/v1/me/export", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers["cache-control"] == "no-store" and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["account"]["kind"] == "citizen"
    profile = data["profile"]
    assert profile["cin"] == body["cin"] and profile["phone"] == body["phone"] and profile["address"] == body["address"]
    assert profile["medical"]["allergies"] == "pénicilline"
    assert [c["charter_version"] for c in data["consents"]] == ["2026-10"]
    [exported] = data["reports"]
    assert exported["id"] == report["id"] and exported["text"] == "Inondation rue 5"
    assert exported["location"]["lat"] == pytest.approx(SFAX["lat"]) and exported["history"][0]["status"] == "received"
    assert data["devices"] == [
        {
            "platform": "android",
            "locale": "fr",
            "token_suffix": token[-8:],
            "gouvernorat_code": None,
            "has_location": False,
            "created_at": data["devices"][0]["created_at"],
            "updated_at": data["devices"][0]["updated_at"],
        }
    ]
    assert data["volunteer"] is None and data["messages"] == []

    user_id = data["account"]["user_id"]
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'user.export' AND target = :t"), {"t": f"account:{user_id}"}
    )
    assert audited == 1
    for _ in range(2):
        assert (await client.get("/api/v1/me/export", headers=headers)).status_code == 200
    limited = await client.get("/api/v1/me/export", headers=headers)
    assert limited.status_code == 429 and "retry-after" in limited.headers


async def test_export_anonymous_device(client: httpx.AsyncClient) -> None:
    headers = device_headers()
    await accept_charter(client, headers)
    await client.post("/api/v1/reports", json=report_body(), headers=headers)
    data = (await client.get("/api/v1/me/export", headers=headers)).json()
    assert data["account"]["kind"] == "anonymous" and data["profile"] is None
    assert len(data["reports"]) == 1 and data["reports"][0]["text"] == "دخان كثيف قرب المخزن"
    assert (await client.get("/api/v1/me/export")).status_code == 401


async def test_delete_registered_citizen(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, staff: Any
) -> None:
    sub = str(uuid.uuid4())
    headers = bearer(make_token(roles=["citizen"], sub=sub, email=f"del{secrets.token_hex(4)}@example.tn"))
    body = profile_body()
    assert (await client.put("/api/v1/me/profile", json=body, headers=headers)).status_code == 200
    await accept_charter(client, headers)
    report = (await client.post("/api/v1/reports", json=report_body(), headers=headers)).json()
    application = {"skills": ["first_aid"], "availability": "continuous", "period_from": date.today().isoformat()}
    assert (await client.put("/api/v1/me/volunteer", json=application, headers=headers)).status_code == 200
    token = "fcm-" + secrets.token_urlsafe(40)
    await client.put("/api/v1/devices", json={"token": token, "platform": "android", "locale": "ar"}, headers=headers)
    user_id = (await client.get("/api/v1/me/export", headers=headers)).json()["account"]["user_id"]

    assert (await client.post("/api/v1/me/delete", json={"confirm": "yes"}, headers=headers)).status_code == 422
    assert (await client.post("/api/v1/me/delete", json={}, headers=headers)).status_code == 422
    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202 and r.json() == {"status": "deleted"}

    account = (
        await session.execute(
            text("SELECT keycloak_sub, anon_pseudonym, deleted_at FROM identity.account WHERE user_id = :u"),
            {"u": user_id},
        )
    ).one()
    assert account.keycloak_sub is None and account.anon_pseudonym is None and account.deleted_at is not None
    for table in ("identity.profile", "notify.device"):
        assert await session.scalar(text(f"SELECT count(*) FROM {table} WHERE user_id = :u"), {"u": user_id}) == 0  # noqa: S608
    volunteer = (
        await session.execute(
            text("SELECT status, ready_until FROM identity.volunteer WHERE user_id = :u"), {"u": user_id}
        )
    ).one()
    assert volunteer.status == "withdrawn"
    # The report stays (legal retention), linked to an account that no longer identifies anyone.
    kept = await session.scalar(text("SELECT user_id FROM reports.report WHERE id = :id"), {"id": report["id"]})
    assert str(kept) == user_id
    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=staff())).json()
    assert detail["reporter"]["first_name"] is None and detail["reporter"]["phone"] is None
    assert (
        await session.scalar(text("SELECT count(*) FROM identity.erasure_request WHERE keycloak_sub = :s"), {"s": sub})
        == 1
    )
    entry = (
        await session.execute(
            text("SELECT actor, details FROM audit.log WHERE action = 'user.delete' AND target = :t"),
            {"t": f"account:{user_id}"},
        )
    ).one()
    assert (
        entry.actor == f"ehimaya-public:{sub}"
        and entry.details["reports_kept"] == 1
        and entry.details["profile"] is True
    )

    # The same sign-in now starts from scratch: a new, empty account.
    assert (await client.get("/api/v1/me/profile", headers=headers)).json()["first_name"] is None
    assert (await client.get("/api/v1/reports/mine", headers=headers)).json()["items"] == []

    # The administrator queue of identity-provider accounts to disable.
    listed = await cli._erasures([])
    pending = [p for p in listed["pending"] if p["keycloak_sub"] == sub]  # type: ignore[union-attr]
    assert len(pending) == 1
    await cli._erasures([pending[0]["id"]])
    assert await session.scalar(
        text("SELECT disabled_at IS NOT NULL FROM identity.erasure_request WHERE keycloak_sub = :s"), {"s": sub}
    )


async def test_delete_anonymous_device(client: httpx.AsyncClient, session: AsyncSession) -> None:
    headers = device_headers()
    await accept_charter(client, headers)
    report = (await client.post("/api/v1/reports", json=report_body(), headers=headers)).json()
    assert len((await client.get("/api/v1/reports/mine", headers=headers)).json()["items"]) == 1

    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202
    owner = await session.scalar(
        text(
            "SELECT a.anon_pseudonym IS NULL AND a.deleted_at IS NOT NULL FROM reports.report r "
            "JOIN identity.account a ON a.user_id = r.user_id WHERE r.id = :id"
        ),
        {"id": report["id"]},
    )
    assert owner
    # The device key no longer leads to that identity.
    assert (await client.get("/api/v1/reports/mine", headers=headers)).json()["items"] == []


async def test_last_admin_of_an_institution_must_hand_over(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    from tests.test_orgs import register

    email = f"adm{secrets.token_hex(4)}@example.tn"
    headers = bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Admin"))
    await register(client, headers)
    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"] == "last_admin"
