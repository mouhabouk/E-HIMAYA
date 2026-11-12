"""Address warnings, OS8 (Yamen, 2026-11-12; docs/phase-os8/design-os8.md).

A warning is a mark on an address or a building: a gas store, hazardous materials, a fuel tank, batteries, a building
at risk of collapse, a difficult access, a dangerous animal, many people at given hours, or a resident who needs help
and agreed to be shown. When a report falls within the circle of a mark, the room and the team see it at once.

* ``aw.category``: the categories, with the circle, the review period, whether the team sees it and the kinds of
  incident with which it becomes critical. National settings, changed by the central room.
* ``aw.marker``: one mark. Personal marks (``personal`` categories) only come from their owner's citizen app
  (``owner_id``), with consent, and are withdrawn by the owner at any time. The others come from the room, from a
  team's proposal (pending until the room approves it), from the institutions register (pending) or from a
  municipality's decision. A mark past its review date is not shown until it is confirmed.
* ``aw.ack``: who read which warning of which incident, the room or the team.
* ``aw.reveal``: every time a room showed the name and phone of a personal mark, with the reason. The owner reads it.

Row level security: a mark follows its gouvernorat (a regional room reads its own; the central room every one), and
its owner reads their own. The categories are read by everyone and written by the national scope only.

Revision ID: 0103_address_warnings
Revises: 0102_inspections
Create Date: 2026-11-12
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0103_address_warnings"
down_revision: str | None = "0102_inspections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_MINE = "(ehimaya.scope() = 'public' AND CAST(owner_id AS text) = ehimaya.subject())"
_ALL = "ehimaya.sees_all()"

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS aw;

CREATE TABLE aw.category (
    key            text PRIMARY KEY CHECK (key ~ '^[a-z_]{{2,20}}$'),
    name           text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 80),
    icon           text NOT NULL CHECK (char_length(icon) <= 40),
    colour         text NOT NULL CHECK (colour IN ('amber', 'orange', 'navy', 'slate', 'purple', 'green', 'teal')),
    personal       boolean NOT NULL DEFAULT false,
    radius_m       integer NOT NULL CHECK (radius_m BETWEEN 20 AND 1000),
    review_months  smallint NOT NULL CHECK (review_months BETWEEN 1 AND 36),
    team           boolean NOT NULL DEFAULT true,
    critical_with  text[] NOT NULL DEFAULT '{{}}',
    examples       text[] NOT NULL DEFAULT '{{}}',
    position       smallint NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    updated_by_name text
);

CREATE TABLE aw.marker (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category         text NOT NULL REFERENCES aw.category(key),
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    location         geography(POINT, 4326) NOT NULL,
    address          text NOT NULL CHECK (char_length(address) BETWEEN 2 AND 200),
    description      text NOT NULL CHECK (char_length(description) BETWEEN 2 AND 500),
    source           text NOT NULL CHECK (source IN ('room', 'team', 'org', 'municipality', 'report', 'citizen')),
    source_ref       text CHECK (char_length(source_ref) <= 200),
    org_id           uuid REFERENCES org.organization(id) ON DELETE SET NULL,
    incident_id      uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    owner_id         uuid REFERENCES identity.account(user_id) ON DELETE CASCADE,
    team_visible     boolean NOT NULL DEFAULT true,
    active_from      smallint CHECK (active_from BETWEEN 0 AND 1440),
    active_to        smallint CHECK (active_to BETWEEN 0 AND 1440),
    review_on        date NOT NULL,
    status           text NOT NULL DEFAULT 'active'
                     CHECK (status IN ('pending', 'active', 'archived', 'rejected', 'withdrawn')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    created_by       text NOT NULL,
    created_by_name  text CHECK (char_length(created_by_name) <= 200),
    decided_at       timestamptz,
    decided_by_name  text CHECK (char_length(decided_by_name) <= 200),
    decision_reason  text CHECK (char_length(decision_reason) <= 500),
    confirmed_at     timestamptz,
    version          integer NOT NULL DEFAULT 1,
    CONSTRAINT ck_marker_owner CHECK ((source = 'citizen') = (owner_id IS NOT NULL)),
    CONSTRAINT ck_marker_hours CHECK ((active_from IS NULL) = (active_to IS NULL))
);
CREATE INDEX ix_marker_location ON aw.marker USING gist (location) WHERE status = 'active';
CREATE INDEX ix_marker_status ON aw.marker (gouvernorat_code, status);
CREATE INDEX ix_marker_owner ON aw.marker (owner_id) WHERE owner_id IS NOT NULL;
-- One pending or active mark per institution and category from the register import.
CREATE UNIQUE INDEX uq_marker_org ON aw.marker (org_id, category) WHERE org_id IS NOT NULL
    AND status IN ('pending', 'active');
-- A personal category can only be held by its owner's mark, and only a personal category has an owner.
CREATE FUNCTION aw.marker_personal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT personal FROM aw.category WHERE key = NEW.category) IS DISTINCT FROM (NEW.owner_id IS NOT NULL) THEN
        RAISE EXCEPTION 'personal_marker_owner' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_marker_personal BEFORE INSERT OR UPDATE OF category, owner_id ON aw.marker
    FOR EACH ROW EXECUTE FUNCTION aw.marker_personal();

CREATE TABLE aw.ack (
    id           bigserial PRIMARY KEY,
    marker_id    uuid NOT NULL REFERENCES aw.marker(id) ON DELETE CASCADE,
    incident_id  uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    by_kind      text NOT NULL CHECK (by_kind IN ('room', 'team')),
    by_subject   text NOT NULL,
    by_name      text CHECK (char_length(by_name) <= 200),
    at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ack UNIQUE (marker_id, incident_id, by_kind)
);
CREATE INDEX ix_ack_incident ON aw.ack (incident_id);

CREATE TABLE aw.reveal (
    id           bigserial PRIMARY KEY,
    marker_id    uuid NOT NULL REFERENCES aw.marker(id) ON DELETE CASCADE,
    owner_id     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    incident_id  uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    by_subject   text NOT NULL,
    by_name      text CHECK (char_length(by_name) <= 200),
    reason       text NOT NULL CHECK (char_length(reason) BETWEEN 2 AND 300),
    at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_reveal_owner ON aw.reveal (owner_id);

ALTER TABLE aw.category ENABLE ROW LEVEL SECURITY;
CREATE POLICY category_read ON aw.category FOR SELECT USING (ehimaya.scope() <> 'none');
CREATE POLICY category_write ON aw.category FOR UPDATE USING ({_ALL}) WITH CHECK ({_ALL});
ALTER TABLE aw.marker ENABLE ROW LEVEL SECURITY;
CREATE POLICY marker_own ON aw.marker USING ({_OWN} OR {_MINE}) WITH CHECK ({_OWN} OR {_MINE});
ALTER TABLE aw.ack ENABLE ROW LEVEL SECURITY;
CREATE POLICY ack_own ON aw.ack USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE aw.reveal ENABLE ROW LEVEL SECURITY;
CREATE POLICY reveal_own ON aw.reveal USING ({_OWN} OR {_MINE}) WITH CHECK ({_OWN});

-- The categories of the approved prototype (2026-11-11). Incident kinds: fire, chemical_leak, landslide, sos ...
INSERT INTO aw.category (key, name, icon, colour, personal, radius_m, review_months, team, critical_with, examples,
                         position) VALUES
 ('gas', 'مخزن غاز', 'flame', 'amber', false, 150, 12, true, '{{fire,chemical_leak}}',
  '{{"قوارير غاز للبيع أو التخزين","خزان غاز سائل","فرن يعمل بالغاز"}}', 1),
 ('chem', 'مواد خطرة', 'flask', 'amber', false, 250, 12, true, '{{fire,chemical_leak}}',
  '{{"مذيبات قابلة للاشتعال","أسمدة أو مبيدات","مواد أكّالة"}}', 2),
 ('fuel', 'خزان وقود', 'drop', 'amber', false, 200, 12, true, '{{fire}}',
  '{{"محطة وقود","خزان مازوط للتدفئة","مستودع زيوت"}}', 3),
 ('batt', 'بطاريات وكهرباء', 'bolt', 'amber', false, 100, 12, true, '{{fire,flood}}',
  '{{"بطاريات ليثيوم لتخزين الطاقة الشمسية","محوّل كهربائي","شاحن سيارات كهربائية"}}', 4),
 ('coll', 'مبنى آيل للسقوط', 'crack', 'orange', false, 80, 6, true, '{{fire,landslide,flood,sos}}',
  '{{"قرار بلدي بالإخلاء","سقف متداع","جدار مائل"}}', 5),
 ('acc', 'صعوبة الوصول', 'road', 'navy', false, 120, 12, true, '{{fire}}',
  '{{"نهج لا تمر منه الشاحنة الثقيلة","باب حديدي مغلق ليلا","مدخل من نهج آخر"}}', 6),
 ('dog', 'حيوان خطر', 'paw', 'slate', false, 80, 6, true, '{{}}',
  '{{"كلب حراسة طليق","كلاب سائبة","حيوان خطر في الحديقة"}}', 7),
 ('occ', 'أشخاص كثيرون', 'people', 'purple', false, 150, 12, true, '{{fire,chemical_leak}}',
  '{{"روضة أطفال","دار مسنين","قاعة أفراح"}}', 8),
 ('mob', 'يحتاج مساعدة على الإخلاء', 'wheel', 'green', true, 60, 12, true, '{{fire,flood}}', '{{}}', 9),
 ('oxy', 'جهاز أكسجين منزلي', 'o2', 'green', true, 60, 12, true, '{{fire}}', '{{}}', 10),
 ('deaf', 'لا يسمع الإنذار', 'ear', 'green', true, 60, 12, true, '{{fire,flood}}', '{{}}', 11);

-- The change journal (migration 0097): the marks keep no value (addresses, personal needs).
SELECT audit.journal_attach('aw.marker', true);
SELECT audit.journal_attach('aw.category', false);
"""

DOWNGRADE = """
DROP SCHEMA aw CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
