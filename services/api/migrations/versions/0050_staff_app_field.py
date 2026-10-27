"""Staff app, the field side (phase P4b, docs/phase-p4/design-staff.md §5): situation reports, alerts from the field,
attachments, hospitals picked from the map and detailed reports built from templates the Office approves.

* ``ops.field_report`` takes three kinds: ``first`` (the first situation report), ``update`` (a later one) and
  ``detailed`` (F-STF-05, answers to a template, no severity). Backup is asked with chips (``backup_kinds``).
* ``ops.casualty_count``: ``injured`` splits into ``injured_light`` (the former values) and ``injured_serious``.
* ``ops.casualty_transport``: finer age bands (the former ones stay readable) and the hospital picked on the map
  (``hospital_ref``, a place of a map layer).
* ``ops.crew_alert``: "backup" or "danger to the crew", sent at any moment of a mission, seen by the room.
* ``ops.field_attachment``: a photo, a voice note or a short text from the scene.
* ``ops.report_template``: the detailed report of a category (and optionally a classification), versioned; one
  approved version at a time. The first versions are a model [SIM] until the Office approves its own.
* ``ops.assignment.contact_phone``: a number the room gives the team for the scene ("المبلّغ" on the phone).

Row-level security: the new tables follow their incident; templates are read by every staff account.

Revision ID: 0050_staff_app_field
Revises: 0049_staff_app_shifts
Create Date: 2026-10-27
"""

import json
from collections.abc import Sequence
from typing import Any

from migrations.sqlutil import run_script

revision: str = "0050_staff_app_field"
down_revision: str | None = "0049_staff_app_shifts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _l(ar: str, fr: str, en: str) -> dict[str, str]:
    return {"ar": ar, "fr": fr, "en": en}


def _opt(key: str, ar: str, fr: str, en: str) -> dict[str, Any]:
    return {"key": key, "label": _l(ar, fr, en)}


def _single(key: str, label: dict[str, str], *options: dict[str, Any], required: bool = True) -> dict[str, Any]:
    return {"key": key, "type": "single", "label": label, "options": list(options), "required": required}


def _multi(key: str, label: dict[str, str], *options: dict[str, Any]) -> dict[str, Any]:
    return {"key": key, "type": "multi", "label": label, "options": list(options), "required": False}


def _yesno(key: str, label: dict[str, str]) -> dict[str, Any]:
    return {"key": key, "type": "yesno", "label": label, "required": True}


def _count(key: str, label: dict[str, str], unit: dict[str, str] | None = None, maximum: int = 1000) -> dict[str, Any]:
    field: dict[str, Any] = {"key": key, "type": "count", "label": label, "required": False, "max": maximum}
    if unit is not None:
        field["unit"] = unit
    return field


EVACUATED = _count("people_evacuated", _l("أشخاص تم إجلاؤهم", "Personnes évacuées", "People evacuated"))
STATE = _single(
    "state",
    _l("الوضع عند المغادرة", "Situation au départ", "Situation when leaving"),
    _opt("controlled", "تحت السيطرة", "Maîtrisée", "Under control"),
    _opt("partial", "جزئيا", "Partiellement", "Partly"),
    _opt("ongoing", "ما زال مستمرا", "En cours", "Still ongoing"),
)

# The first templates, a model [SIM] until the Office approves its own (design §5.7).
TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "fire": [
        _single(
            "place",
            _l("مكان الحريق", "Lieu du feu", "Where it burns"),
            _opt("dwelling", "مسكن", "Habitation", "Dwelling"),
            _opt("vegetation", "غابة أو أعشاب", "Forêt ou végétation", "Forest or vegetation"),
            _opt("vehicle", "عربة", "Véhicule", "Vehicle"),
            _opt("industrial", "منشأة صناعية", "Site industriel", "Industrial site"),
            _opt("commercial", "محل أو مؤسسة", "Commerce ou établissement", "Shop or business"),
            _opt("other", "أخرى", "Autre", "Other"),
        ),
        _single(
            "extent",
            _l("الامتداد", "Étendue", "Extent"),
            _opt("starting", "في بدايته", "Naissant", "Starting"),
            _opt("partial", "جزئي", "Partiel", "Partial"),
            _opt("general", "شامل", "Généralisé", "General"),
        ),
        _single(
            "cause",
            _l("السبب المرجّح", "Cause probable", "Probable cause"),
            _opt("electrical", "كهربائي", "Électrique", "Electrical"),
            _opt("gas", "غاز", "Gaz", "Gas"),
            _opt("cooking", "طبخ", "Cuisson", "Cooking"),
            _opt("smoking", "تدخين", "Cigarette", "Smoking"),
            _opt("arson", "عمل متعمّد محتمل", "Acte volontaire possible", "Possible arson"),
            _opt("natural", "طبيعي", "Naturelle", "Natural"),
            _opt("unknown", "غير معروف", "Inconnue", "Unknown"),
        ),
        _count("area_ha", _l("المساحة المحترقة", "Surface brûlée", "Area burnt"), _l("هك", "ha", "ha"), 100_000),
        _count("water_m3", _l("الماء المستعمل", "Eau utilisée", "Water used"), _l("م³", "m³", "m³"), 10_000),
        _yesno("spread_risk", _l("خطر الانتشار", "Risque de propagation", "Risk of spreading")),
        EVACUATED,
        STATE,
    ],
    "traffic_accident": [
        _count("vehicles", _l("عدد العربات", "Véhicules impliqués", "Vehicles involved"), maximum=100),
        _multi(
            "vehicle_types",
            _l("أنواع العربات", "Types de véhicules", "Kinds of vehicles"),
            _opt("car", "سيارة", "Voiture", "Car"),
            _opt("truck", "شاحنة", "Camion", "Truck"),
            _opt("bus", "حافلة", "Bus", "Bus"),
            _opt("motorcycle", "دراجة نارية", "Moto", "Motorcycle"),
            _opt("bicycle", "دراجة", "Vélo", "Bicycle"),
            _opt("pedestrian", "مترجّل", "Piéton", "Pedestrian"),
        ),
        _single(
            "collision",
            _l("نوع الاصطدام", "Type de collision", "Kind of collision"),
            _opt("frontal", "أمامي", "Frontale", "Head-on"),
            _opt("rear", "خلفي", "Arrière", "Rear-end"),
            _opt("side", "جانبي", "Latérale", "Side"),
            _opt("rollover", "انقلاب", "Renversement", "Rollover"),
            _opt("pedestrian", "دهس", "Piéton heurté", "Pedestrian hit"),
            _opt("single", "عربة وحدها", "Véhicule seul", "Single vehicle"),
        ),
        _yesno("extrication", _l("قص الحديد", "Désincarcération", "Extrication")),
        _multi(
            "hazards",
            _l("مخاطر إضافية", "Dangers supplémentaires", "Further hazards"),
            _opt("fuel_leak", "تسرّب وقود", "Fuite de carburant", "Fuel leak"),
            _opt("fire", "حريق", "Incendie", "Fire"),
            _opt("hazmat", "مواد خطرة", "Matières dangereuses", "Hazardous materials"),
        ),
        _single(
            "road",
            _l("حالة الطريق", "État de la route", "Road"),
            _opt("open", "مفتوحة", "Ouverte", "Open"),
            _opt("partly_blocked", "مغلقة جزئيا", "Partiellement fermée", "Partly blocked"),
            _opt("blocked", "مغلقة", "Fermée", "Blocked"),
        ),
    ],
    "flood": [
        _single(
            "water_height",
            _l("ارتفاع الماء", "Hauteur d'eau", "Water height"),
            _opt("lt_half", "أقل من نصف متر", "Moins de 0,5 m", "Under 0.5 m"),
            _opt("half_to_one", "من نصف متر إلى متر", "De 0,5 à 1 m", "0.5 to 1 m"),
            _opt("gt_one", "أكثر من متر", "Plus de 1 m", "Over 1 m"),
        ),
        _count("buildings", _l("مبان غمرتها المياه", "Bâtiments inondés", "Buildings flooded")),
        _count("roads_cut", _l("طرق مقطوعة", "Routes coupées", "Roads cut"), maximum=100),
        _yesno("pumping", _l("ضخّ المياه", "Pompage", "Pumping")),
        _yesno("electric_risk", _l("خطر كهربائي", "Risque électrique", "Electrical risk")),
        EVACUATED,
        STATE,
    ],
    "drowning": [
        _single(
            "place",
            _l("المكان", "Lieu", "Place"),
            _opt("beach", "شاطئ", "Plage", "Beach"),
            _opt("dam", "سد أو بحيرة", "Barrage ou lac", "Dam or lake"),
            _opt("well", "بئر", "Puits", "Well"),
            _opt("pool", "مسبح", "Piscine", "Pool"),
            _opt("river", "وادي", "Oued", "River"),
        ),
        _count("victims_out", _l("أشخاص أُخرجوا من الماء", "Personnes sorties de l'eau", "People taken out")),
        _yesno("resuscitation", _l("إنعاش", "Réanimation", "Resuscitation")),
        _yesno("divers", _l("نحتاج غطاسين", "Plongeurs nécessaires", "Divers needed")),
        _single(
            "outcome",
            _l("النتيجة", "Issue", "Outcome"),
            _opt("alive", "أُنقذ حيا", "Sauvé vivant", "Rescued alive"),
            _opt("deceased", "متوفى", "Décédé", "Deceased"),
            _opt("missing", "مفقود", "Disparu", "Missing"),
        ),
    ],
    "landslide": [
        _single(
            "kind",
            _l("النوع", "Nature", "Kind"),
            _opt("landslide", "انزلاق أرضي", "Glissement de terrain", "Landslide"),
            _opt("rockfall", "سقوط صخور", "Chute de pierres", "Rockfall"),
            _opt("collapse", "انهيار مبنى", "Effondrement de bâtiment", "Building collapse"),
        ),
        _count("buildings", _l("مبان متضرّرة", "Bâtiments touchés", "Buildings affected")),
        _count("under_debris", _l("أشخاص تحت الأنقاض", "Personnes sous les décombres", "People under debris")),
        _yesno("road_cut", _l("طريق مقطوعة", "Route coupée", "Road cut")),
        _yesno("new_risk", _l("خطر انهيار جديد", "Risque de nouvel effondrement", "Risk of a new collapse")),
        EVACUATED,
    ],
    "chemical_leak": [
        _single(
            "form",
            _l("حالة المادة", "État du produit", "Form of the product"),
            _opt("gas", "غاز", "Gaz", "Gas"),
            _opt("liquid", "سائل", "Liquide", "Liquid"),
            _opt("solid", "صلب", "Solide", "Solid"),
            _opt("unknown", "غير معروف", "Inconnu", "Unknown"),
        ),
        _count(
            "perimeter_m", _l("محيط الأمان", "Périmètre de sécurité", "Safety perimeter"), _l("م", "m", "m"), 10_000
        ),
        _single(
            "leak",
            _l("التسرّب", "Fuite", "Leak"),
            _opt("stopped", "توقف", "Arrêtée", "Stopped"),
            _opt("reduced", "تقلّص", "Réduite", "Reduced"),
            _opt("ongoing", "مستمر", "En cours", "Ongoing"),
        ),
        _yesno("specialists", _l("نحتاج فريقا مختصا", "Équipe spécialisée nécessaire", "Specialist team needed")),
        EVACUATED,
    ],
    "medical": [
        _single(
            "condition",
            _l("الحالة", "État", "Condition"),
            _opt("cardiac", "قلبية", "Cardiaque", "Cardiac"),
            _opt("trauma", "إصابة", "Traumatisme", "Trauma"),
            _opt("respiratory", "تنفسية", "Respiratoire", "Respiratory"),
            _opt("unconscious", "فاقد للوعي", "Inconscient", "Unconscious"),
            _opt("other", "أخرى", "Autre", "Other"),
        ),
        _yesno("conscious", _l("واع عند الوصول", "Conscient à l'arrivée", "Conscious on arrival")),
        _yesno("cpr", _l("إنعاش قلبي رئوي", "RCP", "CPR")),
        _yesno("defibrillator", _l("مزيل الرجفان", "Défibrillateur", "Defibrillator")),
    ],
    "other": [
        _single(
            "intervention",
            _l("نوع التدخل", "Type d'intervention", "Kind of intervention"),
            _opt("rescue", "إنقاذ", "Sauvetage", "Rescue"),
            _opt("animal", "حيوان", "Animal", "Animal"),
            _opt("opening", "فتح باب", "Ouverture de porte", "Opening a door"),
            _opt("water", "تزويد بالماء", "Approvisionnement en eau", "Water supply"),
            _opt("cleanup", "تنظيف الطريق", "Nettoyage de chaussée", "Road clean-up"),
            _opt("other", "أخرى", "Autre", "Other"),
        ),
        _count("people_helped", _l("أشخاص تمت مساعدتهم", "Personnes aidées", "People helped")),
        STATE,
    ],
}


def _seed() -> str:
    rows = []
    for category, fields in TEMPLATES.items():
        payload = json.dumps(fields, ensure_ascii=False).replace("'", "''")
        rows.append(f"('{category}', NULL, 1, 'approved', '{payload}'::jsonb, true, 'system', 'system', now())")
    return (
        "INSERT INTO ops.report_template "
        "(category, classification, version, status, fields, simulated, created_by, approved_by, approved_at) VALUES\n"
        + ",\n".join(rows)
        + ";"
    )


UPGRADE = r"""
ALTER TABLE ops.field_report
    DROP CONSTRAINT field_report_kind_check,
    ALTER COLUMN severity DROP NOT NULL,
    ADD COLUMN backup_kinds text[] NOT NULL DEFAULT '{}',
    ADD COLUMN template_id uuid,
    ADD COLUMN template_version integer,
    ADD COLUMN answers jsonb,
    ADD COLUMN note text CHECK (char_length(note) <= 1000),
    ADD CONSTRAINT field_report_kind_check CHECK (kind IN ('first', 'update', 'detailed')),
    ADD CONSTRAINT ck_field_report_shape CHECK (
        (kind = 'detailed') = (answers IS NOT NULL) AND (kind = 'detailed' OR severity IS NOT NULL));

ALTER TABLE ops.casualty_count RENAME COLUMN injured TO injured_light;
ALTER TABLE ops.casualty_count RENAME CONSTRAINT casualty_count_injured_check TO casualty_count_injured_light_check;
ALTER TABLE ops.casualty_count
    ADD COLUMN injured_serious integer NOT NULL DEFAULT 0 CHECK (injured_serious BETWEEN 0 AND 10000);

ALTER TABLE ops.casualty_transport
    DROP CONSTRAINT casualty_transport_age_band_check,
    ADD CONSTRAINT casualty_transport_age_band_check CHECK (age_band IN (
        'under_12', '12_17', '18_29', '30_44', '45_59', '60_plus', 'unknown', 'child', 'adult', 'elderly')),
    ADD COLUMN hospital_ref uuid REFERENCES geo.layer_feature(id) ON DELETE SET NULL;

ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN (
    'ack', 'status', 'first_report', 'casualties', 'transport', 'alert', 'attachment', 'detailed_report'));

ALTER TABLE ops.assignment ADD COLUMN contact_phone text CHECK (char_length(contact_phone) <= 20);

CREATE TABLE ops.crew_alert (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    assignment_id    uuid NOT NULL REFERENCES ops.assignment(id) ON DELETE CASCADE,
    kind             text NOT NULL CHECK (kind IN ('backup', 'danger')),
    items            text[] NOT NULL DEFAULT '{}',
    created_by       text NOT NULL,
    created_by_name  text,
    device_at        timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    seen_by          text,
    seen_by_name     text,
    seen_at          timestamptz
);
CREATE INDEX ix_crew_alert_incident ON ops.crew_alert (incident_id, created_at DESC);
CREATE INDEX ix_crew_alert_unseen ON ops.crew_alert (created_at) WHERE seen_at IS NULL;

CREATE TABLE ops.field_attachment (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    assignment_id    uuid NOT NULL REFERENCES ops.assignment(id) ON DELETE CASCADE,
    kind             text NOT NULL CHECK (kind IN ('photo', 'voice', 'text')),
    body             text CHECK (char_length(body) <= 500),
    object_key       text UNIQUE,
    content_type     text,
    sha256           text CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    bytes            integer CHECK (bytes > 0),
    duration_s       real CHECK (duration_s > 0 AND duration_s <= 90),
    created_by       text NOT NULL,
    created_by_name  text,
    device_at        timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind = 'text') = (body IS NOT NULL) AND (kind = 'text') = (object_key IS NULL))
);
CREATE INDEX ix_field_attachment_incident ON ops.field_attachment (incident_id, created_at);

CREATE TABLE ops.report_template (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category          text NOT NULL,
    classification    text,
    version           integer NOT NULL CHECK (version >= 1),
    status            text NOT NULL CHECK (status IN ('draft', 'approved', 'retired')),
    fields            jsonb NOT NULL,
    simulated         boolean NOT NULL DEFAULT false,
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    approved_by       text,
    approved_by_name  text,
    approved_at       timestamptz,
    retired_at        timestamptz,
    UNIQUE (category, classification, version)
);
CREATE UNIQUE INDEX ux_report_template_approved ON ops.report_template (category, coalesce(classification, ''))
    WHERE status = 'approved';
CREATE UNIQUE INDEX ux_report_template_draft ON ops.report_template (category, coalesce(classification, ''))
    WHERE status = 'draft';

ALTER TABLE ops.field_report
    ADD CONSTRAINT fk_field_report_template FOREIGN KEY (template_id) REFERENCES ops.report_template(id);

ALTER TABLE ops.crew_alert ENABLE ROW LEVEL SECURITY;
CREATE POLICY crew_alert_select ON ops.crew_alert FOR SELECT USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id));
CREATE POLICY crew_alert_insert ON ops.crew_alert FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY crew_alert_update ON ops.crew_alert FOR UPDATE USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id)) WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.field_attachment ENABLE ROW LEVEL SECURITY;
CREATE POLICY field_attachment_select ON ops.field_attachment FOR SELECT USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id));
CREATE POLICY field_attachment_insert ON ops.field_attachment FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.report_template ENABLE ROW LEVEL SECURITY;
CREATE POLICY report_template_select ON ops.report_template FOR SELECT USING (ehimaya.scope() <> 'none');
CREATE POLICY report_template_insert ON ops.report_template FOR INSERT WITH CHECK (ehimaya.sees_all());
CREATE POLICY report_template_update ON ops.report_template FOR UPDATE USING (ehimaya.sees_all())
    WITH CHECK (ehimaya.sees_all());
CREATE POLICY report_template_delete ON ops.report_template FOR DELETE USING (
    ehimaya.sees_all() AND status = 'draft');
"""

DOWNGRADE = r"""
ALTER TABLE ops.field_report DROP CONSTRAINT fk_field_report_template;
DROP TABLE ops.report_template;
DROP TABLE ops.field_attachment;
DROP TABLE ops.crew_alert;
ALTER TABLE ops.assignment DROP COLUMN contact_phone;
DELETE FROM ops.crew_event WHERE kind IN ('alert', 'attachment', 'detailed_report');
ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN (
    'ack', 'status', 'first_report', 'casualties', 'transport'));
UPDATE ops.casualty_transport SET age_band = CASE
    WHEN age_band IN ('under_12', '12_17') THEN 'child'
    WHEN age_band = '60_plus' THEN 'elderly'
    WHEN age_band IN ('18_29', '30_44', '45_59') THEN 'adult'
    ELSE age_band END;
ALTER TABLE ops.casualty_transport
    DROP COLUMN hospital_ref,
    DROP CONSTRAINT casualty_transport_age_band_check,
    ADD CONSTRAINT casualty_transport_age_band_check CHECK (age_band IN ('child', 'adult', 'elderly', 'unknown'));
UPDATE ops.casualty_count SET injured_light = injured_light + injured_serious;
ALTER TABLE ops.casualty_count DROP COLUMN injured_serious;
ALTER TABLE ops.casualty_count RENAME CONSTRAINT casualty_count_injured_light_check TO casualty_count_injured_check;
ALTER TABLE ops.casualty_count RENAME COLUMN injured_light TO injured;
DELETE FROM ops.field_report WHERE kind = 'detailed';
UPDATE ops.field_report SET kind = 'first' WHERE kind = 'update';
ALTER TABLE ops.field_report
    DROP CONSTRAINT ck_field_report_shape,
    DROP CONSTRAINT field_report_kind_check,
    DROP COLUMN note,
    DROP COLUMN answers,
    DROP COLUMN template_version,
    DROP COLUMN template_id,
    DROP COLUMN backup_kinds,
    ALTER COLUMN severity SET NOT NULL,
    ADD CONSTRAINT field_report_kind_check CHECK (kind IN ('first'));
"""


def upgrade() -> None:
    run_script(UPGRADE)
    run_script(_seed())


def downgrade() -> None:
    run_script(DOWNGRADE)
