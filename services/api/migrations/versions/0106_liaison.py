"""Informing the partner bodies by phone, OS20 (Yamen, 2026-11-12; docs/phase-os20/design-os20.md).

When a report is opened the room sets its level: 1, handled in the room and closed without informing anyone; 2, one or
more bodies are informed, internal (the head of the central room, the Director General) or external (190, 193, 197,
STEG, forests ...). The link with the bodies is the phone only: the agent calls from the room's softphone or dials by
hand, then records the result of the call.

* ``liaison.body``: the contact system, central and regional. A body (a unit, a ministry, a regional structure, a public
  institution) with its field of activity, address and place. ``gouvernorat_code`` empty: a national body, kept by the
  central room; otherwise kept by the regional room of its gouvernorat. ``agency`` ties a body to a service the decision
  engine suggests (``samu``, ``garde_nationale`` ...) or to an internal body (``central_room``, ``director_general``).
* ``liaison.official``: the officials of a body, with their role, phones, email and duty hours, in calling order.
* ``liaison.incident_level``: the level of a report (1 or 2) and who set it.
* ``liaison.party``: a body (and the official chosen) informed of a report. It stays in the report's history; the names
  are copied so the history reads the same after the contact system changes.
* ``liaison.call``: each call made to a party: result, what was asked, what was promised, the expected arrival, a note
  and a follow-up reminder.

Row level security: a regional room reads the bodies of its gouvernorat and the national bodies, the central room every
body. A regional room writes the bodies of its gouvernorat; the central room writes the national bodies and may add a
missing body of any gouvernorat from a report (the app keeps edits to the owning room). The report tables follow the
report's gouvernorat.

Revision ID: 0106_liaison
Revises: 0105_mission_alerts
Create Date: 2026-11-12
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0106_liaison"
down_revision: str | None = "0105_mission_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_READ = f"gouvernorat_code IS NULL OR {_OWN}"

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS liaison;

CREATE TABLE liaison.body (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    category         text NOT NULL CHECK (category IN ('civil', 'security', 'ministry', 'regional', 'public')),
    kind             text NOT NULL DEFAULT 'external' CHECK (kind IN ('internal', 'external')),
    agency           text CHECK (agency ~ '^[a-z_]{{2,30}}$'),
    name             text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 160),
    domain           text CHECK (char_length(domain) <= 160),
    address          text CHECK (char_length(address) <= 200),
    location         geography(POINT, 4326),
    public_phone     text CHECK (public_phone ~ '^[0-9+ ]{{3,20}}$'),
    status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    origin_incident_id uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    created_by_name  text CHECK (char_length(created_by_name) <= 200),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by_name  text CHECK (char_length(updated_by_name) <= 200),
    version          integer NOT NULL DEFAULT 1
);
CREATE INDEX ix_body_gouvernorat ON liaison.body (gouvernorat_code, status);
-- One active body per service and gouvernorat (the national one has no gouvernorat).
CREATE UNIQUE INDEX uq_body_agency ON liaison.body (coalesce(gouvernorat_code, 0), agency)
    WHERE agency IS NOT NULL AND status = 'active';

CREATE TABLE liaison.official (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    body_id          uuid NOT NULL REFERENCES liaison.body(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    name             text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 120),
    role             text CHECK (char_length(role) <= 120),
    phones           text[] NOT NULL CHECK (cardinality(phones) BETWEEN 1 AND 4),
    email            text CHECK (char_length(email) <= 200),
    duty             text CHECK (char_length(duty) <= 120),
    position         smallint NOT NULL DEFAULT 1,
    status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by_name  text CHECK (char_length(updated_by_name) <= 200)
);
CREATE INDEX ix_official_body ON liaison.official (body_id, position);
-- An official follows the gouvernorat of their body (row level security reads it).
CREATE FUNCTION liaison.official_gouvernorat() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    SELECT gouvernorat_code INTO NEW.gouvernorat_code FROM liaison.body WHERE id = NEW.body_id;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_official_gouvernorat BEFORE INSERT OR UPDATE OF body_id ON liaison.official
    FOR EACH ROW EXECUTE FUNCTION liaison.official_gouvernorat();

CREATE TABLE liaison.incident_level (
    incident_id      uuid PRIMARY KEY REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    level            smallint NOT NULL CHECK (level IN (1, 2)),
    note             text CHECK (char_length(note) <= 300),
    set_by_name      text CHECK (char_length(set_by_name) <= 200),
    set_at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE liaison.party (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    body_id          uuid NOT NULL REFERENCES liaison.body(id),
    official_id      uuid REFERENCES liaison.official(id) ON DELETE SET NULL,
    body_name        text NOT NULL,
    official_name    text,
    official_role    text,
    suggested        boolean NOT NULL DEFAULT false,
    reason           text CHECK (char_length(reason) <= 300),
    added_by_name    text CHECK (char_length(added_by_name) <= 200),
    added_at         timestamptz NOT NULL DEFAULT now(),
    removed_at       timestamptz,
    removed_by_name  text CHECK (char_length(removed_by_name) <= 200)
);
CREATE INDEX ix_party_incident ON liaison.party (incident_id);
CREATE INDEX ix_party_body ON liaison.party (body_id);
CREATE UNIQUE INDEX uq_party ON liaison.party (incident_id, body_id) WHERE removed_at IS NULL;

CREATE TABLE liaison.call (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    party_id         uuid NOT NULL REFERENCES liaison.party(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    official_id      uuid REFERENCES liaison.official(id) ON DELETE SET NULL,
    official_name    text,
    number           text NOT NULL CHECK (number ~ '^[0-9+ ]{{3,20}}$'),
    via              text NOT NULL CHECK (via IN ('softphone', 'manual')),
    telephony_call_id uuid REFERENCES telephony.call(id) ON DELETE SET NULL,
    duration_s       integer CHECK (duration_s BETWEEN 0 AND 86400),
    result           text NOT NULL CHECK (result IN ('answered', 'no_answer', 'busy', 'wrong_number')),
    asked            text CHECK (char_length(asked) <= 500),
    promised         text CHECK (char_length(promised) <= 500),
    eta_min          smallint CHECK (eta_min BETWEEN 0 AND 1440),
    note             text CHECK (char_length(note) <= 500),
    follow_up_at     timestamptz,
    follow_up_done_at timestamptz,
    follow_up_done_by_name text CHECK (char_length(follow_up_done_by_name) <= 200),
    by_subject       text NOT NULL,
    by_name          text CHECK (char_length(by_name) <= 200),
    at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_call_incident ON liaison.call (incident_id, at);
CREATE INDEX ix_call_follow_up ON liaison.call (follow_up_at)
    WHERE follow_up_at IS NOT NULL AND follow_up_done_at IS NULL;

ALTER TABLE liaison.body ENABLE ROW LEVEL SECURITY;
CREATE POLICY body_read ON liaison.body FOR SELECT USING ({_READ});
CREATE POLICY body_insert ON liaison.body FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY body_update ON liaison.body FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE liaison.official ENABLE ROW LEVEL SECURITY;
CREATE POLICY official_read ON liaison.official FOR SELECT USING ({_READ});
CREATE POLICY official_insert ON liaison.official FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY official_update ON liaison.official FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE liaison.incident_level ENABLE ROW LEVEL SECURITY;
CREATE POLICY incident_level_own ON liaison.incident_level USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE liaison.party ENABLE ROW LEVEL SECURITY;
CREATE POLICY party_own ON liaison.party USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE liaison.call ENABLE ROW LEVEL SECURITY;
CREATE POLICY call_own ON liaison.call USING ({_OWN}) WITH CHECK ({_OWN});

-- The two national internal bodies of the approved prototype. Their officials (names, phones) are entered by the
-- central room: no personal number is seeded.
INSERT INTO liaison.body (category, kind, agency, name, domain, created_by_name, updated_by_name) VALUES
 ('civil', 'internal', 'central_room', 'القاعة المركزية للعمليات', 'قيادة العمليات على المستوى الوطني',
  'إعداد المنظومة', 'إعداد المنظومة'),
 ('civil', 'internal', 'director_general', 'المدير العام للديوان الوطني للحماية المدنية', 'الإدارة العامة',
  'إعداد المنظومة', 'إعداد المنظومة');

-- The change journal (migration 0097): officials and calls keep no value (names, phones, notes).
SELECT audit.journal_attach('liaison.body', false);
SELECT audit.journal_attach('liaison.official', true);
SELECT audit.journal_attach('liaison.incident_level', false);
SELECT audit.journal_attach('liaison.party', false);
SELECT audit.journal_attach('liaison.call', true);
"""

DOWNGRADE = """
DROP SCHEMA liaison CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
