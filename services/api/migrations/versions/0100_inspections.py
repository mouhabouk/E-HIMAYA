"""Periodic inspections of the units, phase I1 (Yamen, 2026-11-11; docs/phase-i/design-i.md).

The general inspectorate plans inspections of the civil protection units, issues the mission orders, activates the
inspectors' app accounts and decides what each operations room reads of the results:

* ``insp.inspector``: an inspector's app account, registered from the app and activated by the inspector general with
  a one-time code sent by SMS or e-mail (the pattern of the field agents, phase F). One phone per account.
* ``insp.profile``: the calculation model (items, weights, values, thresholds, levels). One active version; every
  inspection keeps a copy of the model it was scored with.
* ``insp.order_note`` and ``insp.policy``: the general recommendations printed on every mission order, and the
  disclosure applied to every new inspection.
* ``insp.mission`` and ``insp.mission_site``: a mission order for one inspector, with one or more units.
* ``insp.inspection`` and ``insp.recommendation``: the report of one unit, sealed once signed and sent.

``notify.outbox`` gains the ``sms`` channel (one SMS to one number) for the activation codes.

Only the inspections of the operations rooms can be disclosed to the rooms (Yamen, 2026-11-11): the regional room reads
what is disclosed of its own room's inspections, the central room what is disclosed of every room's. The inspections of
the other units stay in the inspections system.

Row level security: the inspections and their recommendations follow their gouvernorat (a regional room reads its own
room's; the central room's have none); every other table is national only (a regional room never sees a planned
inspection).

Revision ID: 0100_inspections
Revises: 0099_field_news_stream
Create Date: 2026-11-11
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0100_inspections"
down_revision: str | None = "0099_field_news_stream"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_ALL = "ehimaya.sees_all()"

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS insp;

CREATE TABLE insp.inspector (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind               text NOT NULL CHECK (kind IN ('internal', 'external')),
    matricule          text NOT NULL CHECK (char_length(matricule) BETWEEN 2 AND 40),
    name               text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 120),
    organisation       text CHECK (char_length(organisation) <= 160),
    phone              text CHECK (char_length(phone) <= 32),
    email              text CHECK (char_length(email) <= 254),
    via                text NOT NULL CHECK (via IN ('sms', 'email')),
    status             text NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'code_sent', 'active', 'blocked', 'rejected', 'closed')),
    expires_on         date,
    agent_id           uuid REFERENCES inv.agent(id) ON DELETE SET NULL,
    requested_device   text CHECK (char_length(requested_device) <= 120),
    requested_at       timestamptz NOT NULL DEFAULT now(),
    decided_at         timestamptz,
    decided_by_name    text,
    reject_reason      text CHECK (char_length(reject_reason) <= 500),
    code_hash          text,
    code_expires_at    timestamptz,
    code_attempts      smallint NOT NULL DEFAULT 0,
    activated_at       timestamptz,
    device_model       text CHECK (char_length(device_model) <= 120),
    device_platform    text CHECK (device_platform IN ('android', 'ios')),
    device_ref         text CHECK (char_length(device_ref) <= 120),
    push_token         text CHECK (char_length(push_token) <= 4096),
    refresh_hash       text,
    refresh_expires_at timestamptz,
    last_seen_at       timestamptz,
    lost_at            timestamptz,
    closed_at          timestamptz,
    version            integer NOT NULL DEFAULT 1,
    CONSTRAINT ck_inspector_contact CHECK ((via = 'sms' AND phone IS NOT NULL) OR (via = 'email' AND email IS NOT NULL)),
    CONSTRAINT ck_inspector_external CHECK (kind = 'internal' OR organisation IS NOT NULL)
);
-- One open account per professional number; a rejected or closed one may register again.
CREATE UNIQUE INDEX ux_inspector_matricule ON insp.inspector (lower(matricule))
    WHERE status NOT IN ('rejected', 'closed');
CREATE UNIQUE INDEX ux_inspector_code ON insp.inspector (code_hash) WHERE code_hash IS NOT NULL;
CREATE UNIQUE INDEX ux_inspector_refresh ON insp.inspector (refresh_hash) WHERE refresh_hash IS NOT NULL;

CREATE TABLE insp.profile (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 120),
    version         integer NOT NULL CHECK (version >= 1),
    active          boolean NOT NULL DEFAULT false,
    config          jsonb NOT NULL,
    created_by_name text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version)
);
CREATE UNIQUE INDEX ux_profile_active ON insp.profile (active) WHERE active;

CREATE TABLE insp.order_note (
    id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    position smallint NOT NULL,
    text     text NOT NULL CHECK (char_length(text) BETWEEN 2 AND 400)
);

CREATE TABLE insp.policy (
    id              smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    config          jsonb NOT NULL,
    updated_by_name text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE SEQUENCE insp.mission_seq;
CREATE TABLE insp.mission (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ref             text NOT NULL UNIQUE CHECK (ref ~ '^OM-[0-9]{4}-[0-9]{4,}$'),
    on_date         date NOT NULL,
    at_time         time NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('periodic', 'surprise')),
    inspector_id    uuid NOT NULL REFERENCES insp.inspector(id),
    status          text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'cancelled')),
    cancel_reason   text CHECK (char_length(cancel_reason) <= 500),
    published       boolean NOT NULL DEFAULT false,
    created_by      text NOT NULL,
    created_by_name text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_mission_cancel CHECK (status <> 'cancelled' OR cancel_reason IS NOT NULL)
);
CREATE INDEX ix_mission_inspector ON insp.mission (inspector_id, on_date);
CREATE INDEX ix_mission_date ON insp.mission (on_date);

CREATE TABLE insp.mission_site (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id       uuid NOT NULL REFERENCES insp.mission(id) ON DELETE CASCADE,
    position         smallint NOT NULL,
    -- A unit (centre, post...) or an operations room: only the inspections of the rooms can be disclosed to the rooms
    -- (Yamen 2026-11-11); the others stay in the inspections system.
    target           text NOT NULL CHECK (target IN ('unit', 'room')),
    -- A unit is named by the planner (Yamen 2026-11-11): its gouvernorat, its kind, then its name typed in;
    -- the link to the register of units is optional.
    unit_kind        text CHECK (unit_kind IN ('regional_directorate', 'brigade', 'centre', 'advanced_centre', 'guard_post', 'beach', 'other')),
    unit_name        text CHECK (char_length(btrim(unit_name)) BETWEEN 2 AND 160),
    unit_id          uuid REFERENCES ops.unit(id),
    room             text CHECK (room IN ('central', 'regional')),
    -- The gouvernorat of the unit or of the regional room; none for the central room.
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    sections         text[] NOT NULL DEFAULT '{}',
    CONSTRAINT ck_site_target CHECK (
        (target = 'unit' AND unit_kind IS NOT NULL AND unit_name IS NOT NULL AND room IS NULL
            AND gouvernorat_code IS NOT NULL)
        OR (target = 'room' AND unit_kind IS NULL AND unit_name IS NULL AND unit_id IS NULL AND room = 'central'
            AND gouvernorat_code IS NULL)
        OR (target = 'room' AND unit_kind IS NULL AND unit_name IS NULL AND unit_id IS NULL AND room = 'regional'
            AND gouvernorat_code IS NOT NULL))
);
CREATE UNIQUE INDEX ux_mission_site_place ON insp.mission_site (mission_id, coalesce(
    'unit:' || gouvernorat_code::text || ':' || unit_kind || ':' || lower(btrim(unit_name)),
    room || ':' || coalesce(gouvernorat_code::text, '-')));

CREATE SEQUENCE insp.receipt_seq;
CREATE TABLE insp.inspection (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id        uuid NOT NULL REFERENCES insp.mission(id),
    site_id           uuid NOT NULL UNIQUE REFERENCES insp.mission_site(id),
    target            text NOT NULL CHECK (target IN ('unit', 'room')),
    unit_kind         text CHECK (unit_kind IN ('regional_directorate', 'brigade', 'centre', 'advanced_centre', 'guard_post', 'beach', 'other')),
    unit_name         text,
    unit_id           uuid REFERENCES ops.unit(id),
    room              text CHECK (room IN ('central', 'regional')),
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    inspector_id      uuid NOT NULL REFERENCES insp.inspector(id),
    kind              text NOT NULL CHECK (kind IN ('periodic', 'surprise')),
    profile_id        uuid NOT NULL REFERENCES insp.profile(id),
    profile           jsonb NOT NULL,
    status            text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'submitted')),
    started_at        timestamptz NOT NULL,
    location          geography(POINT, 4326),
    answers           jsonb NOT NULL DEFAULT '{}',
    present           smallint CHECK (present >= 0),
    expected          smallint CHECK (expected > 0),
    exit_seconds      integer CHECK (exit_seconds BETWEEN 0 AND 3600),
    score             smallint CHECK (score BETWEEN 0 AND 100),
    verdict           text,
    summary           text CHECK (char_length(summary) <= 4000),
    head_name         text CHECK (char_length(head_name) <= 120),
    inspector_sig     bytea,
    head_sig          bytea,
    signed_at         timestamptz,
    submitted_at      timestamptz,
    client_id         uuid UNIQUE,
    receipt           text UNIQUE,
    disclosure        jsonb NOT NULL DEFAULT '{}',
    updated_at        timestamptz NOT NULL DEFAULT now(),
    deleted_at        timestamptz,
    deleted_by_name   text,
    delete_reason     text CHECK (char_length(delete_reason) <= 500),
    CONSTRAINT ck_inspection_sealed CHECK (status <> 'submitted' OR (
        signed_at IS NOT NULL AND submitted_at IS NOT NULL AND receipt IS NOT NULL AND score IS NOT NULL
        AND inspector_sig IS NOT NULL AND head_sig IS NOT NULL AND head_name IS NOT NULL)),
    -- A unit's report is never disclosed to a room.
    CONSTRAINT ck_inspection_disclosure CHECK (target = 'room' OR disclosure = '{}'::jsonb),
    CONSTRAINT ck_inspection_sig_size CHECK (octet_length(inspector_sig) <= 200000 AND octet_length(head_sig) <= 200000)
);
CREATE INDEX ix_inspection_unit ON insp.inspection (gouvernorat_code, unit_kind, lower(unit_name), submitted_at DESC)
    WHERE target = 'unit';
CREATE INDEX ix_inspection_gouvernorat ON insp.inspection (gouvernorat_code, submitted_at DESC);
CREATE INDEX ix_inspection_live ON insp.inspection (started_at) WHERE status = 'in_progress' AND deleted_at IS NULL;

CREATE TABLE insp.recommendation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id    uuid NOT NULL REFERENCES insp.inspection(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    position         smallint NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('detailed', 'general')),
    item_key         text CHECK (char_length(item_key) <= 40),
    text             text NOT NULL CHECK (char_length(text) BETWEEN 2 AND 600),
    priority         text CHECK (priority IN ('high', 'medium', 'low')),
    to_central       boolean NOT NULL DEFAULT false,
    to_regional      boolean NOT NULL DEFAULT false,
    CONSTRAINT ck_recommendation_priority CHECK ((kind = 'detailed') = (priority IS NOT NULL))
);
CREATE INDEX ix_recommendation_inspection ON insp.recommendation (inspection_id, position);

-- A signed report is sealed: only its disclosure, the bin and the update time change after it was sent.
CREATE FUNCTION insp.sealed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'submitted' AND (
        NEW.status IS DISTINCT FROM OLD.status OR NEW.answers IS DISTINCT FROM OLD.answers
        OR NEW.score IS DISTINCT FROM OLD.score OR NEW.verdict IS DISTINCT FROM OLD.verdict
        OR NEW.summary IS DISTINCT FROM OLD.summary OR NEW.present IS DISTINCT FROM OLD.present
        OR NEW.exit_seconds IS DISTINCT FROM OLD.exit_seconds OR NEW.inspector_sig IS DISTINCT FROM OLD.inspector_sig
        OR NEW.head_sig IS DISTINCT FROM OLD.head_sig OR NEW.head_name IS DISTINCT FROM OLD.head_name
        OR NEW.signed_at IS DISTINCT FROM OLD.signed_at OR NEW.profile IS DISTINCT FROM OLD.profile
        OR NEW.unit_id IS DISTINCT FROM OLD.unit_id OR NEW.room IS DISTINCT FROM OLD.room
        OR NEW.unit_kind IS DISTINCT FROM OLD.unit_kind OR NEW.unit_name IS DISTINCT FROM OLD.unit_name
        OR NEW.receipt IS DISTINCT FROM OLD.receipt) THEN
        RAISE EXCEPTION 'inspection_sealed' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_inspection_sealed BEFORE UPDATE ON insp.inspection FOR EACH ROW EXECUTE FUNCTION insp.sealed();

CREATE FUNCTION insp.recommendation_sealed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.text IS DISTINCT FROM OLD.text OR NEW.priority IS DISTINCT FROM OLD.priority
        OR NEW.kind IS DISTINCT FROM OLD.kind OR NEW.item_key IS DISTINCT FROM OLD.item_key THEN
        RAISE EXCEPTION 'inspection_sealed' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_recommendation_sealed BEFORE UPDATE ON insp.recommendation
    FOR EACH ROW EXECUTE FUNCTION insp.recommendation_sealed();

ALTER TABLE insp.inspector ENABLE ROW LEVEL SECURITY;
CREATE POLICY inspector_all ON insp.inspector USING (__ALL__) WITH CHECK (__ALL__);
ALTER TABLE insp.profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY profile_all ON insp.profile USING (__ALL__) WITH CHECK (__ALL__);
ALTER TABLE insp.order_note ENABLE ROW LEVEL SECURITY;
CREATE POLICY order_note_all ON insp.order_note USING (__ALL__) WITH CHECK (__ALL__);
ALTER TABLE insp.policy ENABLE ROW LEVEL SECURITY;
CREATE POLICY policy_all ON insp.policy USING (__ALL__) WITH CHECK (__ALL__);
ALTER TABLE insp.mission ENABLE ROW LEVEL SECURITY;
CREATE POLICY mission_all ON insp.mission USING (__ALL__) WITH CHECK (__ALL__);
ALTER TABLE insp.mission_site ENABLE ROW LEVEL SECURITY;
CREATE POLICY mission_site_all ON insp.mission_site USING (__ALL__) WITH CHECK (__ALL__);
ALTER TABLE insp.inspection ENABLE ROW LEVEL SECURITY;
CREATE POLICY inspection_own ON insp.inspection USING (__OWN__) WITH CHECK (__ALL__);
ALTER TABLE insp.recommendation ENABLE ROW LEVEL SECURITY;
CREATE POLICY recommendation_own ON insp.recommendation USING (__OWN__) WITH CHECK (__ALL__);

-- The first calculation model and the defaults (the approved prototype, 2026-11-11). The inspector general edits them.
INSERT INTO insp.profile (name, version, active, config, created_by_name) VALUES (
    'النموذج العام: المراكز والفرق', 1, true,
    '{"axes": [
        {"key": "p", "name": "الأفراد", "weight": 35},
        {"key": "r", "name": "الموارد", "weight": 40}],
      "items": [
        {"key": "p0", "axis": "p", "text": "الهندام والانضباط", "weight": 3},
        {"key": "p1", "axis": "p", "text": "معدات الحماية الفردية: الخوذة، البدلة، القفازات", "weight": 8},
        {"key": "p2", "axis": "p", "text": "الشهادات سارية المفعول (إسعاف، تنفس)", "weight": 10},
        {"key": "p3", "axis": "p", "text": "اللياقة البدنية: اختبار سريع", "weight": 7},
        {"key": "p4", "axis": "p", "text": "معرفة الأعوان لإجراءات المركز", "weight": 7},
        {"key": "r0", "axis": "r", "text": "جاهزية الآليات للخروج", "weight": 10},
        {"key": "r1", "axis": "r", "text": "أجهزة التنفس واختبار الضغط", "weight": 8},
        {"key": "r2", "axis": "r", "text": "معدات الإطفاء والإنقاذ", "weight": 7},
        {"key": "r3", "axis": "r", "text": "معدات الإسعاف وصلاحية المستهلكات", "weight": 6},
        {"key": "r4", "axis": "r", "text": "المخزون وسجل الصيانة", "weight": 5},
        {"key": "r5", "axis": "r", "text": "وسائل الاتصال (اللاسلكي)", "weight": 4}],
      "values": {"ok": 100, "note": 60, "ko": 20},
      "weights": {"items": 75, "presence": 15, "exit": 10},
      "exit": {"fast": 120, "ok": 180, "fast_value": 100, "ok_value": 75, "slow_value": 50},
      "levels": [
        {"name": "جاهز", "min": 85, "colour": "green"},
        {"name": "جاهز بتحفّظ", "min": 70, "colour": "amber"},
        {"name": "غير جاهز", "min": 0, "colour": "red"}],
      "sections": ["القيادة والإدارة", "العمليات والتدخّل", "التجهيز والآليات", "الأفراد والتكوين", "الإسعاف",
                   "الاتصالات والقاعة", "المخزن والصيانة"]}'::jsonb,
    'المنظومة');

INSERT INTO insp.order_note (position, text) VALUES
    (1, 'الاستظهار بأمر المهمة لدى رئيس الوحدة عند الوصول.'),
    (2, 'التفقّد يشمل الأقسام المذكورة في أمر المهمة دون غيرها.'),
    (3, 'تحرير تقرير مستقلّ لكل مقرّ، يوقّعه المتفقّد ومسؤول الوحدة.'),
    (4, 'إرسال التقرير من التطبيق في اليوم نفسه، أو عند عودة الشبكة.'),
    (5, 'المحافظة على سرّية المعطيات وعدم إطلاع غير المعنيين عليها.');

INSERT INTO insp.policy (config) VALUES ('{
    "central": {"inspection": true, "verdict": true, "score": true},
    "regional": {"inspection": true, "verdict": true, "score": false},
    "recommendations": {"high": "both", "medium": "both", "low": "central", "general": "none"},
    "publish_programme": false}'::jsonb);

ALTER TABLE notify.outbox
    DROP CONSTRAINT outbox_channel_check,
    DROP CONSTRAINT ck_outbox_target,
    ADD CONSTRAINT outbox_channel_check CHECK (channel IN ('push', 'email', 'staff_push', 'sms')),
    ADD CONSTRAINT ck_outbox_target CHECK (
        (channel = 'push') = (user_id IS NOT NULL)
        AND (channel IN ('email', 'staff_push', 'sms')) = (address IS NOT NULL));

-- The change journal (migration 0097): the accounts and the reports keep no value (names, phones, signatures).
SELECT audit.journal_attach('insp.inspector', true);
SELECT audit.journal_attach('insp.inspection', true);
SELECT audit.journal_attach('insp.profile', false);
SELECT audit.journal_attach('insp.order_note', false);
SELECT audit.journal_attach('insp.policy', false);
SELECT audit.journal_attach('insp.mission', false);
SELECT audit.journal_attach('insp.mission_site', false);
SELECT audit.journal_attach('insp.recommendation', false);
""".replace("__OWN__", _OWN).replace("__ALL__", _ALL)

DOWNGRADE = """
DELETE FROM notify.outbox WHERE channel = 'sms';
ALTER TABLE notify.outbox
    DROP CONSTRAINT outbox_channel_check,
    DROP CONSTRAINT ck_outbox_target,
    ADD CONSTRAINT outbox_channel_check CHECK (channel IN ('push', 'email', 'staff_push')),
    ADD CONSTRAINT ck_outbox_target CHECK (
        (channel = 'push') = (user_id IS NOT NULL) AND (channel IN ('email', 'staff_push')) = (address IS NOT NULL));
DROP SCHEMA insp CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
