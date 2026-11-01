"""Damages and reference lists (Yamen, 2026-11-01).

* ``snacr.damage``: one line of the Office's damage tables, joined to the archive of interventions by NUM_SEQUENTIEL:
  ``forest`` (degat_forestieres: the place burnt and its surface in hectares) and ``agri`` (degat_Agriculteur: the
  place, the crop or fodder lost, the unit and the quantity). No name, no address: a surface or a quantity only.
* ``ops.assignment.damages``: what the team records of a fire: the place burnt and its surface in hectares, the crop
  or fodder lost in hectares, bales or bags (``[{kind, place, crop, unit, value}]``), read back in the SNACR studies
  through ``snacr.intervention.incident_id`` (the years drawn from the rooms' records).
* ``ref.list`` and ``ref.item``: the Office's reference lists (vehicle types with their CEE code, the agent's status and
  post, the vehicle's state and situation, the parties of a road accident, the nature of a fire, the crops lost and
  their units, the places of the damages, the places of the preventive programmes, the fields of intervention), kept
  by the central room: an item is renamed or retired, never deleted, so old records keep their meaning.

Revision ID: 0091_damage_refs
Revises: 0090_snacr_study
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0091_damage_refs"
down_revision: str | None = "0090_snacr_study"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"

# (key, Arabic, French, English, items); an item is a label, or (code, label) or (code, label, unit).
LISTS: list[tuple[str, str, str, str, list[str | tuple[str, ...]]]] = [
    (
        "vehicle_type",
        "أصناف الوسائل",
        "Types d'engins",
        "Vehicle types",
        [
            ("2", "سيارة إسعاف طبية"),
            ("3", "سيارة نقل أموات"),
            ("4", "مركز طبي مجهز"),
            ("5", "طائرة نقل صحي"),
            ("6", "سيارة إطفاء"),
            ("7", "شاحنة إطفاء"),
            ("8", "شاحنة إطفاء حرائق الغابات"),
            ("9", "شاحنة إطفاء حرائق المحروقات"),
            ("10", "شاحنة تزويد"),
            ("11", "شاحنة ناشلة"),
            ("12", "شاحنة رافعة"),
            ("13", "آلة كاسحة (Bulldozer)"),
            ("14", "آلة ماسحة (Motorgrader)"),
            ("15", "آلة حفر (Poclain)"),
            ("16", "تراكس"),
            ("17", "حاملة معدات ثقيلة (Porte-char)"),
            ("18", "شاحنة نقل"),
            ("19", "سيارة جبلية"),
            ("20", "جرار"),
            ("21", "حافلة صغيرة"),
            ("22", "حافلة كبيرة"),
            ("23", "طائرة نقل"),
            ("24", "شاحنة سلم"),
            ("25", "وسيلة مجابهة الأخطار الكيميائية"),
            ("26", "وسيلة مجابهة الأخطار البيولوجية"),
            ("27", "وسيلة مجابهة الأخطار الإشعاعية"),
            ("28", "خيمة إزالة التلوث"),
            ("29", "شاحنة مزدوجة"),
            ("30", "شاحنة إمتصاص"),
            ("31", "مضخة كبيرة الحجم"),
            ("32", "مضخة متوسطة الحجم"),
            ("33", "مضخة صغيرة الحجم"),
            ("34", "شاحنة رفع أوحال"),
            ("35", "شاحنة غاسلة"),
            ("36", "زورق نجدة"),
            ("37", "طائرة إستطلاع"),
            ("38", "مركز قيادة متنقل"),
            ("39", "شاحنة صيانة"),
            ("40", "مطبخ متنقل"),
        ],
    ),
    (
        "agent_status",
        "وضعية العون",
        "Situation de l'agent",
        "Agent status",
        ["إجازة سنوية", "إجازة مرض", "مهمة", "تربص", "غائب", "في تعزيز", "في تدخل"],
    ),
    (
        "agent_post",
        "خطة العون",
        "Poste de l'agent",
        "Agent post",
        [
            "سائق",
            "آمر فصيل",
            "عون نجدة وإنقاذ",
            "طبيب",
            "مساعد آمر فصيل",
            "مسعف",
            "إطفاء",
            "آمر حضيرة",
            "مسؤول على الوسيلة",
        ],
    ),
    (
        "vehicle_state",
        "حالة الوسيلة",
        "État de l'engin",
        "Vehicle state",
        ["معطبة", "بالوحدة", "في تدخل", "في حراسة وقائية", "في طور الصيانة", "معدة للطرح", "على ذمة وحدة أخرى"],
    ),
    (
        "vehicle_situation",
        "وضعية الوسيلة",
        "Situation de l'engin",
        "Vehicle situation",
        ["عطب عادي", "حادث مرور", "انفلاق عجلة", "صيانة"],
    ),
    (
        "accident_party",
        "طرف الحادث",
        "Partie de l'accident",
        "Accident party",
        [
            "سيارة خفيفة",
            "شاحنة",
            "شاحنة ثقيلة",
            "شاحنة نقل مواد خطرة",
            "حافلة صغيرة",
            "حافلة كبيرة",
            "قطار",
            "مترو",
            "دراجة نارية",
            "دراجة عادية",
        ],
    ),
    (
        "fire_nature",
        "طبيعة الحريق",
        "Nature de l'incendie",
        "Fire nature",
        ["غابات", "محاصيل زراعية", "مواد علفية", "أعشاب"],
    ),
    (
        "crop_loss",
        "خسائر المحاصيل الزراعية",
        "Pertes de cultures",
        "Crop losses",
        [
            ("1", "قمح", "ha"),
            ("2", "شعير", "ha"),
            ("3", "زراعات أخرى", "ha"),
            ("4", "حصيدة", "ha"),
            ("5", "قرط", "bale"),
            ("6", "تبن", "bale"),
        ],
    ),
    (
        "damage_unit",
        "وحدات قياس الأضرار",
        "Unités des dégâts",
        "Damage units",
        [("1", "هكتار"), ("2", "أكياس"), ("3", "حزم (بالات)")],
    ),
    (
        "forest_place",
        "أماكن الأضرار الغابية",
        "Lieux des dégâts forestiers",
        "Forest damage places",
        [("1", "غابة مورقة"), ("4", "أعشاب جافة"), ("82", "أرض بيضاء"), ("95", "غابة شعراء")],
    ),
    (
        "agri_place",
        "أماكن الأضرار الفلاحية",
        "Lieux des dégâts agricoles",
        "Agricultural damage places",
        [("2", "مواد علفية وفلاحية"), ("3", "مزرعة"), ("38", "منطقة فلاحية"), ("83", "ضيعة فلاحية")],
    ),
    (
        "programme_place",
        "أماكن وأصناف البرامج اليومية والأسبوعية والشهرية",
        "Lieux et types des programmes",
        "Programme places and types",
        [
            "مسيرة",
            "قاعة مغطاة",
            "ملعب ألعاب قوى",
            "ملعب رقبي",
            "مسرح",
            "مسرح هواء طلق",
            "معرض",
            "مدينة ألعاب",
            "منتزه",
            "شاطئ",
            "مسبح",
            "مصنع",
            "ميناء تجاري",
            "مسلك مسابقات",
            "فضاء ترفيهي",
            "نزل",
            "فضاء سياحي أو نزل",
            "مجلس النواب",
            "مطار الحجيج",
            "مسلك رئاسي",
            "مطار",
            "مسلك عطلة آمنة",
            "وزارة الداخلية والتنمية المحلية",
            "سوق السيارات",
            "قاعة العمليات المركزية",
            "جامع أو مكان إشغال",
            "مسلك نشاط",
            "مكان نشاط أو مسيرة",
            "قاعة اجتماعات",
            "معهد",
            "ملعب كرة القدم",
            "ألعاب ترفيهية (سيرك)",
            "حراسة وقائية",
            "بملاعب رياضية",
            "بساحات ثقافية وعمومية",
            "بمناطق سياحية وترفيهية",
            "بالشواطئ",
            "بمناطق صناعية",
            "بمناطق ريفية وغابية",
            "بالطرقات السيارة",
            "بالطرقات الوطنية والجهوية والمحلية",
            "بالسكك الحديدية",
            "مباريات رياضية",
            "ثقافية",
            "اجتماعات",
            "اختبارات رياضية",
            "نقل مواد خطرة",
            "حفلات فنية",
            "لتزويد باخرة بالمحروقات",
            "عملية لحام",
            "الحجيج",
            "نشاط رئاسي",
            "عطلة آمنة",
            "استقبال أفراد",
            "حراسة وقائية عملياتية",
            "ألعاب ترفيهية",
            "نشاط رئاسي/حكومي",
            "نشاط ثقافي",
            "نشاط رياضي",
            "دواعي أمنية",
            "نشاط ترفيهي",
            "طلب حضور وقائي لوسيلة تدخل بطاقمها",
            "طلب حضور وقائي لضباط وأعوان",
        ],
    ),
    (
        "intervention_field",
        "مجالات التدخل",
        "Domaines d'intervention",
        "Fields of intervention",
        [
            "حوادث بوسائل النقل البري",
            "تعطب بوسائل النقل البري",
            "حرائق بالبنايات",
            "حرائق بوسائل النقل",
            "توعك صحي",
            "اختناق من جراء الغازات",
            "محاولة انتحار",
            "الإصابة بمادة كيميائية أو سامة",
            "الاعتداء بالعنف",
            "إنقاذ الغرقى",
            "حرائق بالثروة الفلاحية والغابية",
            "حرائق بالفواضل",
            "الإنقاذ إثر التقلبات الجوية",
            "الإنقاذ إثر الحوادث الكيميائية",
            "الإنقاذ من تحت الأنقاض",
            "إنقاذ الغرقى بالشواطئ",
            "إنقاذ الغرقى بالمياه العميقة",
            "إنقاذ الغرقى خارج الشواطئ",
        ],
    ),
]


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _seeds() -> str:
    lists, items = [], []
    for order, (key, ar, fr, en, values) in enumerate(LISTS, start=1):
        lists.append(f"({_q(key)}, {_q(ar)}, {_q(fr)}, {_q(en)}, {order})")
        for i, v in enumerate(values, start=1):
            code, label, unit = (None, v, None) if isinstance(v, str) else (*v, None)[:3]
            items.append(
                f"({_q(key)}, {_q(code) if code else 'NULL'}, {_q(label)}, {_q(unit) if unit else 'NULL'}, {i * 10})"
            )
    return (
        "INSERT INTO ref.list (key, name_ar, name_fr, name_en, sort) VALUES\n" + ",\n".join(lists) + ";\n"
        "INSERT INTO ref.item (list_key, code, label_ar, unit, sort) VALUES\n" + ",\n".join(items) + ";\n"
    )


def _upgrade() -> str:
    return f"""
ALTER TABLE ops.assignment ADD COLUMN damages jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(damages) = 'array' AND jsonb_array_length(damages) <= 20);
ALTER TABLE snacr.intervention ADD COLUMN incident_id uuid;
CREATE INDEX ix_snacr_intervention_incident ON snacr.intervention (incident_id) WHERE incident_id IS NOT NULL;

CREATE TABLE snacr.damage (
    id              bigserial PRIMARY KEY,
    kind            text NOT NULL CHECK (kind IN ('forest', 'agri')),
    source_key      integer,
    seq_num         bigint NOT NULL,
    place_code      text,
    place_label     text,
    crop_code       text,
    crop_label      text,
    unit            text NOT NULL CHECK (unit IN ('ha', 'bale', 'bag')),
    value           double precision NOT NULL CHECK (value >= 0),
    file_name       text,
    imported_by     text NOT NULL,
    imported_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_snacr_damage_seq ON snacr.damage (seq_num);
CREATE INDEX ix_snacr_intervention_seq ON snacr.intervention (seq_num) WHERE seq_num IS NOT NULL;
ALTER TABLE snacr.damage ENABLE ROW LEVEL SECURITY;
CREATE POLICY damage_read ON snacr.damage FOR SELECT USING ({_STAFF});
CREATE POLICY damage_write ON snacr.damage FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());

CREATE SCHEMA IF NOT EXISTS ref;
CREATE TABLE ref.list (
    key       text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]{{1,40}}$'),
    name_ar   text NOT NULL,
    name_fr   text NOT NULL,
    name_en   text NOT NULL,
    sort      smallint NOT NULL DEFAULT 0
);
CREATE TABLE ref.item (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    list_key    text NOT NULL REFERENCES ref.list(key),
    code        text CHECK (char_length(code) <= 20),
    label_ar    text NOT NULL CHECK (char_length(label_ar) BETWEEN 1 AND 160),
    label_fr    text CHECK (char_length(label_fr) <= 160),
    unit        text CHECK (unit IN ('ha', 'bale', 'bag')),
    sort        integer NOT NULL DEFAULT 0,
    active      boolean NOT NULL DEFAULT true,
    updated_by  text NOT NULL DEFAULT 'system',
    updated_by_name text DEFAULT 'e-Himaya',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ref_item_label UNIQUE (list_key, label_ar)
);
CREATE UNIQUE INDEX uq_ref_item_code ON ref.item (list_key, code) WHERE code IS NOT NULL;
ALTER TABLE ref.list ENABLE ROW LEVEL SECURITY;
CREATE POLICY list_read ON ref.list FOR SELECT USING ({_STAFF});
ALTER TABLE ref.item ENABLE ROW LEVEL SECURITY;
CREATE POLICY item_read ON ref.item FOR SELECT USING ({_STAFF});
CREATE POLICY item_write ON ref.item FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());
{_seeds()}"""


DOWNGRADE = """
DROP SCHEMA ref CASCADE;
ALTER TABLE ops.assignment DROP COLUMN damages;
ALTER TABLE snacr.intervention DROP COLUMN incident_id;
DROP INDEX snacr.ix_snacr_intervention_seq;
DROP TABLE snacr.damage;
"""


def upgrade() -> None:
    run_script(_upgrade())


def downgrade() -> None:
    run_script(DOWNGRADE)
