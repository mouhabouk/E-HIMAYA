"""Guided call-taking cards for the operations rooms (OS2, Yamen 2026-11-10; docs/phase-os2/design-os2.md).

* ``reports.call_card``: one row per version of the card of a report category. A version is a ``draft`` while the
  Office writes it, ``approved`` once a national room manager approves it (at most one per category), ``retired``
  when a newer version replaces it. The content (questions, effects of each answer, instructions read to the caller)
  is JSON checked by ``app.modules.reports.callcards``. ``sim`` marks the demonstration text written before the
  Office's own: the dashboard shows it under the amber [SIM] badge.
* ``reports.call_card_answer``: the answers given on one report, the version of the card used and what they gave
  (band, flags, resources suggested, instructions read). Readable with its report (row-level security).
* ``reports.report.call_card_floor``: the band the answers call for; the claim deadline never goes below it.

The nine cards seeded here are demonstration drafts [SIM], approved so the rooms can try them, until the Office and,
for the medical cards, the medical staff replace them from the dashboard.

Revision ID: 0100_call_cards
Revises: 0099_field_news_stream
Create Date: 2026-11-10
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.sqlutil import run_script

revision: str = "0100_call_cards"
down_revision: str | None = "0099_field_news_stream"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE TABLE reports.call_card (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category             text NOT NULL CHECK (category IN ('sos', 'fire', 'flood', 'traffic_accident', 'drowning',
                                                           'landslide', 'chemical_leak', 'medical', 'other')),
    version              integer NOT NULL CHECK (version >= 1),
    status               text NOT NULL CHECK (status IN ('draft', 'approved', 'retired')),
    content              jsonb NOT NULL,
    sim                  boolean NOT NULL DEFAULT false,
    medical              boolean NOT NULL DEFAULT false,
    medical_validated_by text CHECK (char_length(medical_validated_by) <= 200),
    medical_validated_at timestamptz,
    medical_reason       text CHECK (char_length(medical_reason) <= 500),
    approved_by          text CHECK (char_length(approved_by) <= 200),
    approved_at          timestamptz,
    approval_reason      text CHECK (char_length(approval_reason) <= 500),
    retired_at           timestamptz,
    created_by           text NOT NULL,
    created_by_name      text,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_by_name      text,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_call_card_version UNIQUE (category, version),
    CONSTRAINT ck_call_card_approved CHECK (status = 'draft' OR approved_at IS NOT NULL)
);
CREATE UNIQUE INDEX ux_call_card_approved ON reports.call_card (category) WHERE status = 'approved';
CREATE UNIQUE INDEX ux_call_card_draft ON reports.call_card (category) WHERE status = 'draft';

CREATE TABLE reports.call_card_answer (
    report_id    uuid PRIMARY KEY REFERENCES reports.report(id) ON DELETE CASCADE,
    card_id      uuid NOT NULL REFERENCES reports.call_card(id),
    category     text NOT NULL,
    card_version integer NOT NULL,
    answers      jsonb NOT NULL,
    outcome      jsonb NOT NULL,
    entered_by   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_call_card_answer_card ON reports.call_card_answer (card_id);

ALTER TABLE reports.call_card_answer ENABLE ROW LEVEL SECURITY;
CREATE POLICY call_card_answer_select ON reports.call_card_answer FOR SELECT
    USING (EXISTS (SELECT 1 FROM reports.report r WHERE r.id = report_id));
CREATE POLICY call_card_answer_insert ON reports.call_card_answer FOR INSERT
    WITH CHECK (ehimaya.scope() <> 'none' AND EXISTS (SELECT 1 FROM reports.report r WHERE r.id = report_id));
CREATE POLICY call_card_answer_delete ON reports.call_card_answer FOR DELETE
    USING (ehimaya.scope() = 'system');
CREATE POLICY call_card_answer_update ON reports.call_card_answer FOR UPDATE
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');

ALTER TABLE reports.report
    ADD COLUMN call_card_floor text CHECK (call_card_floor IN ('critical', 'high', 'normal', 'low'));

-- The change journal (migration 0097), like every table of the reports schema.
SELECT audit.journal_attach('reports.call_card'::regclass, false);
SELECT audit.journal_attach('reports.call_card_answer'::regclass, false);
"""

DOWNGRADE = r"""
ALTER TABLE reports.report DROP COLUMN call_card_floor;
DROP TABLE reports.call_card_answer;
DROP TABLE reports.call_card;
"""


def _q(
    qid: str,
    text: str,
    *,
    key: bool = False,
    help: str | None = None,
    when: tuple[str, str] | None = None,
    **effects: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": qid,
        "text": text,
        "help": help,
        "key": key,
        "when": {"question": when[0], "answer": when[1]} if when else None,
        "effects": effects,
    }


def _e(
    why: str,
    band: str | None = None,
    flag: str | None = None,
    means: Sequence[str] = (),
    instruction: str | None = None,
    lives: bool = False,
    injured: bool = False,
) -> dict[str, Any]:
    return {
        "why": why,
        "band": band,
        "flag": flag,
        "means": list(means),
        "instruction": instruction,
        "lives": lives,
        "injured": injured,
    }


AMB, SMUR = "سيارة إسعاف", "طلب SMUR عبر 190 (طبيب على متن الإسعاف)"
FIRE, LADDER, RESCUE = "شاحنة إطفاء", "سلّم آلي", "آلية إنقاذ وتخليص"
DIVE, BOAT = "فرقة الغوص", "زورق إنقاذ"
GAS, HAZMAT = "إعلام STEG لقطع الغاز", "وحدة المخاطر الكيميائية"
POLICE, OFFICER = "إعلام الحرس أو الشرطة", "إعلام ضابط القاعة"
LIFE, ARREST = "حياة في خطر", "توقف قلبي محتمل"

CPR = {
    "title": "الإنعاش القلبي بالهاتف",
    "medical": True,
    "metronome": 110,
    "steps": [
        "ضع الهاتف على مكبّر الصوت وابقَ مع المريض.",
        "مدّده على ظهره فوق أرض صلبة.",
        "ضع كفّيك فوق بعض في وسط الصدر.",
        "اضغط بقوة وبسرعة، 5 سم، مع الإيقاع الذي أعدّه لك.",
        "لا تتوقف حتى يصل الفريق أو يأخذ المريض نفَسا طبيعيا.",
    ],
}

SEED: list[tuple[str, dict[str, Any]]] = [
    (
        "medical",
        {
            "title": "إسعاف: شخص مريض أو مصاب",
            "base_band": "normal",
            "base_means": [AMB],
            "questions": [
                _q(
                    "conscious",
                    "هل المريض فاقد للوعي؟",
                    key=True,
                    help="هل يجيب إن ناديته أو هززت كتفه؟",
                    yes=_e("فاقد للوعي", band="high", flag=LIFE, lives=True),
                ),
                _q(
                    "breathing",
                    "هل يتنفس تنفسا طبيعيا؟",
                    key=True,
                    help="انظر إلى صدره 10 ثوان",
                    when=("conscious", "yes"),
                    no=_e(
                        "فاقد للوعي ولا يتنفس طبيعيا",
                        band="critical",
                        flag=ARREST,
                        means=[SMUR],
                        instruction="cpr",
                        lives=True,
                    ),
                    yes=_e("يتنفس: وضعية الأمان", instruction="recovery"),
                ),
                _q(
                    "chest",
                    "هل يشكو من ألم في الصدر أو ضيق في التنفس؟",
                    key=True,
                    yes=_e("ألم صدري أو ضيق تنفس", band="high", means=[SMUR], lives=True),
                ),
                _q(
                    "bleeding",
                    "هل يوجد نزيف قوي لا يتوقف؟",
                    key=True,
                    yes=_e("نزيف قوي", band="critical", flag=LIFE, instruction="bleeding", lives=True, injured=True),
                ),
                _q("child", "هل المريض رضيع أو طفل دون 8 سنوات؟", yes=_e("طفل: تُجهَّز معدات الأطفال")),
                _q("labour", "هل هي امرأة حامل في المخاض؟", yes=_e("ولادة جارية", band="high")),
            ],
            "instructions": {
                "cpr": CPR,
                "recovery": {
                    "title": "وضعية الأمان",
                    "medical": True,
                    "steps": [
                        "أمِل المريض على جانبه، والرأس مائل قليلا إلى الخلف.",
                        "راقب تنفسه، وأخبرني فورا إن توقف.",
                        "لا تعطه أكلا ولا شربا.",
                    ],
                },
                "bleeding": {
                    "title": "إيقاف النزيف",
                    "medical": True,
                    "steps": [
                        "اضغط مباشرة على الجرح بقطعة قماش نظيفة.",
                        "لا ترفع القماش، وأضف فوقه إن تبلّل.",
                        "إن كان في الذراع أو الساق، ارفعها إن أمكن.",
                    ],
                },
            },
        },
    ),
    (
        "fire",
        {
            "title": "حريق",
            "base_band": "high",
            "base_means": [FIRE],
            "questions": [
                _q(
                    "trapped",
                    "هل يوجد أشخاص محاصرون أو لا يستطيعون الخروج؟",
                    key=True,
                    yes=_e(
                        "أشخاص محاصرون",
                        band="critical",
                        flag=LIFE,
                        means=[LADDER, AMB],
                        instruction="evacuate",
                        lives=True,
                    ),
                ),
                _q(
                    "high_floor",
                    "هل الحريق في الطابق الثالث فما فوق؟",
                    when=("trapped", "yes"),
                    yes=_e("طابق عالٍ: السلّم الآلي ضروري", means=[LADDER]),
                ),
                _q(
                    "gas",
                    "هل توجد قوارير غاز أو مواد قابلة للانفجار قرب النار؟",
                    key=True,
                    yes=_e("خطر انفجار", band="critical", flag="خطر انفجار", means=[GAS, POLICE]),
                ),
                _q(
                    "injured",
                    "هل يوجد مصابون أو حروق؟",
                    key=True,
                    yes=_e("مصابون", band="critical", means=[AMB], injured=True),
                ),
                _q(
                    "spreading",
                    "هل النار تنتشر إلى مبانٍ أو غابة مجاورة؟",
                    yes=_e("انتشار النار", band="critical", means=[OFFICER]),
                ),
                _q("public", "هل هو مبنى عام (مدرسة، مستشفى، سوق)؟", yes=_e("مبنى عام", band="critical")),
            ],
            "instructions": {
                "evacuate": {
                    "title": "الخروج من الحريق",
                    "steps": [
                        "اخرجوا فورا إن كان الطريق آمنا، ولا تعودوا لأخذ شيء.",
                        "إن كان الدخان في الدرج: أغلقوا الباب وسدّوا أسفله بقماش مبلل.",
                        "اقتربوا من نافذة وأشيروا للفريق.",
                        "لا تستعملوا المصعد.",
                    ],
                }
            },
        },
    ),
    (
        "traffic_accident",
        {
            "title": "حادث مرور",
            "base_band": "normal",
            "base_means": [AMB, POLICE],
            "questions": [
                _q(
                    "stuck",
                    "هل يوجد شخص عالق داخل سيارة؟",
                    key=True,
                    yes=_e(
                        "عالق داخل سيارة",
                        band="critical",
                        flag=LIFE,
                        means=[RESCUE],
                        instruction="crash",
                        lives=True,
                    ),
                ),
                _q(
                    "unconscious",
                    "هل يوجد مصاب لا يتحرك أو لا يجيب؟",
                    key=True,
                    yes=_e("مصاب فاقد للوعي", band="critical", flag=LIFE, means=[SMUR], lives=True, injured=True),
                ),
                _q(
                    "burning",
                    "هل تحترق سيارة أو يتسرب منها وقود؟",
                    key=True,
                    yes=_e("حريق أو تسرب وقود", band="critical", means=[FIRE]),
                ),
                _q(
                    "heavy",
                    "هل في الحادث حافلة أو شاحنة مواد خطرة؟",
                    yes=_e("مركبة ثقيلة أو مواد خطرة", band="high", means=[HAZMAT, OFFICER]),
                ),
                _q(
                    "many",
                    "هل المصابون أكثر من 3؟",
                    yes=_e("إصابات متعددة", band="high", means=[OFFICER], injured=True),
                ),
            ],
            "instructions": {
                "crash": {
                    "title": "حادث مرور",
                    "steps": [
                        "أشعل أضواء التنبيه وضع المثلث إن أمكن.",
                        "لا تُخرج المصاب من السيارة إلا إن كانت تحترق.",
                        "أطفئ محرّك السيارة ولا تدخّن قربها.",
                    ],
                }
            },
        },
    ),
    (
        "drowning",
        {
            "title": "غرق",
            "base_band": "critical",
            "base_means": [AMB],
            "questions": [
                _q(
                    "in_water",
                    "هل الشخص ما زال في الماء أو اختفى تحته؟",
                    key=True,
                    yes=_e("الضحية في الماء", flag=LIFE, means=[DIVE, BOAT], instruction="drowning", lives=True),
                    no=_e("أُخرج من الماء", instruction="drowning"),
                ),
                _q(
                    "breathing",
                    "بعد إخراجه: هل يتنفس؟",
                    key=True,
                    when=("in_water", "no"),
                    no=_e("لا يتنفس بعد الإخراج", flag=ARREST, means=[SMUR], instruction="cpr", lives=True),
                ),
                _q("guarded", "هل الشاطئ محروس؟", yes=_e("يُعلَم مركز الحراسة")),
            ],
            "instructions": {
                "drowning": {
                    "title": "الغريق",
                    "medical": True,
                    "steps": [
                        "لا تنزل إلى الماء إن لم تكن سبّاحا ماهرا؛ ارمِ له شيئا يطفو.",
                        "عند إخراجه: إن لم يتنفس، أعطه 5 نفخات ثم ابدأ الضغط على الصدر.",
                        "أشِر لأقرب حارس شاطئ.",
                    ],
                },
                "cpr": CPR,
            },
        },
    ),
    (
        "flood",
        {
            "title": "فيضان",
            "base_band": "normal",
            "base_means": [FIRE],
            "questions": [
                _q(
                    "stranded",
                    "هل يوجد أشخاص عالقون في الماء أو فوق سطح؟",
                    key=True,
                    yes=_e(
                        "أشخاص عالقون",
                        band="critical",
                        flag=LIFE,
                        means=[BOAT, RESCUE],
                        instruction="flood",
                        lives=True,
                    ),
                ),
                _q("car", "هل جرف الماء سيارة؟", key=True, yes=_e("سيارة في الماء", band="critical", means=[BOAT])),
                _q("rising", "هل منسوب الماء يرتفع الآن؟", yes=_e("منسوب يرتفع", band="high", means=[OFFICER])),
                _q("vulnerable", "هل يوجد مسنّون أو أطفال أو ذوو إعاقة؟", yes=_e("أشخاص هشّون", band="high")),
            ],
            "instructions": {
                "flood": {
                    "title": "الفيضان",
                    "steps": [
                        "اصعدوا إلى أعلى مكان في المبنى.",
                        "لا تعبروا الوادي ولا الماء الجاري، ولو بالسيارة.",
                        "افصلوا الكهرباء إن كان ذلك آمنا.",
                    ],
                }
            },
        },
    ),
    (
        "chemical_leak",
        {
            "title": "تسرب غاز أو مادة كيميائية",
            "base_band": "high",
            "base_means": [FIRE, HAZMAT],
            "questions": [
                _q(
                    "household",
                    "هل هو غاز منزلي (قارورة أو قنوات)؟",
                    yes=_e("غاز منزلي", means=[GAS], instruction="gas"),
                    no=_e("مادة غير الغاز المنزلي", instruction="chemical"),
                ),
                _q(
                    "symptoms",
                    "هل يشكو أحد من دوار أو ضيق تنفس أو إغماء؟",
                    key=True,
                    yes=_e("أعراض تسمم", band="critical", flag=LIFE, means=[AMB, SMUR], lives=True, injured=True),
                ),
                _q(
                    "crowd",
                    "هل المكان عام أو فيه عدد كبير من الناس؟",
                    yes=_e("عدد كبير معرّض", band="critical", means=[POLICE, OFFICER]),
                ),
            ],
            "instructions": {
                "gas": {
                    "title": "تسرب الغاز",
                    "steps": [
                        "لا تشعل ولا تطفئ أي ضوء أو جهاز كهربائي.",
                        "أغلق صمّام الغاز إن أمكن دون خطر.",
                        "افتح النوافذ واخرج من المكان.",
                        "اتصل بنا من خارج المبنى.",
                    ],
                },
                "chemical": {
                    "title": "تسرب كيميائي",
                    "steps": [
                        "ابتعد عكس اتجاه الريح.",
                        "أغلق النوافذ والتكييف إن كنت داخل مبنى.",
                        "لا تلمس المادة ولا تقترب لمعرفتها.",
                    ],
                },
            },
        },
    ),
    (
        "landslide",
        {
            "title": "انزلاق تربة أو انهيار مبنى",
            "base_band": "high",
            "base_means": [RESCUE],
            "questions": [
                _q(
                    "buried",
                    "هل يوجد أشخاص تحت الأنقاض؟",
                    key=True,
                    yes=_e("أشخاص تحت الأنقاض", band="critical", flag=LIFE, means=[AMB, OFFICER], lives=True),
                ),
                _q("road", "هل الطريق مقطوع؟", yes=_e("طريق مقطوع", means=[POLICE])),
            ],
            "instructions": {},
        },
    ),
    (
        "sos",
        {
            "title": "نجدة عامة",
            "base_band": "high",
            "base_means": [AMB],
            "questions": [
                _q(
                    "life",
                    "هل حياة شخص في خطر الآن؟",
                    key=True,
                    yes=_e("حياة في خطر", band="critical", flag=LIFE, lives=True),
                )
            ],
            "instructions": {},
        },
    ),
    (
        "other",
        {
            "title": "أخرى",
            "base_band": "low",
            "base_means": [OFFICER],
            "questions": [
                _q(
                    "life",
                    "هل حياة شخص في خطر الآن؟",
                    key=True,
                    yes=_e("حياة في خطر", band="critical", flag=LIFE, means=[AMB], lives=True),
                )
            ],
            "instructions": {},
        },
    ),
]

MEDICAL_CATEGORIES = ("medical", "drowning")


def upgrade() -> None:
    run_script(UPGRADE)
    bind = op.get_bind()
    for category, content in SEED:
        bind.execute(
            sa.text(
                "INSERT INTO reports.call_card (category, version, status, content, sim, medical, approved_by, "
                "approved_at, approval_reason, created_by, created_by_name) "
                "VALUES (:c, 1, 'approved', CAST(:x AS jsonb), true, :m, '[SIM]', now(), :r, 'system', '[SIM]')"
            ),
            {
                "c": category,
                "x": json.dumps(content, ensure_ascii=False),
                "m": category in MEDICAL_CATEGORIES,
                "r": "نص تجريبي [SIM] للعرض، ينتظر نص الديوان ومصادقة اللجنة الطبية للبطاقات الطبية",
            },
        )


def downgrade() -> None:
    run_script(DOWNGRADE)
