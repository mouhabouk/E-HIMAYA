"""Emergency hub: topics and items (phase B1, docs/phase-b/design.md §2bis, Yamen 2026-10-23).

* ``content.guide_topic`` — a topic of the hub (fires, fractures, first aid, breathing problems…): title ar/fr/en,
  icon, colour, position, ``hidden``, medical validation (who, when), version.
* ``content.guide_item`` — an item of a topic: title and, per language, "call 198 now if…", numbered steps and
  "do not"; ``call_198`` shows the call button; ``hidden``; medical validation; version.
* ``content.revision`` row ``emergency_guide``: bumped at every visible change, the app's ``ETag``.

First load: six topics with a few items each, written from widely published first-aid guidance and **not
validated**: the app shows them under the amber "[SIM] content awaiting medical validation" banner until the Office's
medical staff validates each item. Downgrade drops the tables and the revision row.

Revision ID: 0033_emergency_guide
Revises: 0032_map_layers
Create Date: 2026-10-23
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.sqlutil import run_script

revision: str = "0033_emergency_guide"
down_revision: str | None = "0032_map_layers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE TABLE content.guide_topic (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key            text NOT NULL UNIQUE,
    title          jsonb NOT NULL,
    icon           text NOT NULL,
    colour         text NOT NULL,
    position       integer NOT NULL DEFAULT 0,
    hidden         boolean NOT NULL DEFAULT false,
    version        integer NOT NULL DEFAULT 1,
    updated_by     text NOT NULL DEFAULT 'system',
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_guide_topic_key CHECK (key ~ '^[a-z][a-z0-9_]{1,39}$'),
    CONSTRAINT ck_guide_topic_colour CHECK (colour ~ '^#[0-9A-F]{6}$')
);

CREATE TABLE content.guide_item (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id       uuid NOT NULL REFERENCES content.guide_topic(id) ON DELETE CASCADE,
    position       integer NOT NULL DEFAULT 0,
    content        jsonb NOT NULL,
    call_198       boolean NOT NULL DEFAULT false,
    hidden         boolean NOT NULL DEFAULT false,
    validated_by   text,
    validated_at   timestamptz,
    version        integer NOT NULL DEFAULT 1,
    updated_by     text NOT NULL DEFAULT 'system',
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_guide_item_validated CHECK ((validated_by IS NULL) = (validated_at IS NULL))
);
CREATE INDEX ix_guide_item_topic ON content.guide_item (topic_id, position);

INSERT INTO content.revision (name, value) VALUES ('emergency_guide', 1) ON CONFLICT (name) DO NOTHING;
"""


def _text(title: str, call: list[str], steps: list[str], dont: list[str]) -> dict[str, Any]:
    return {"title": title, "call": call, "steps": steps, "dont": dont}


# (key, icon, colour, title ar/fr/en, items: (call_198, ar, fr, en))
SEED: list[tuple[str, str, str, dict[str, str], list[tuple[bool, dict[str, Any], dict[str, Any], dict[str, Any]]]]] = [
    (
        "fire",
        "fire",
        "#BF360C",
        {"ar": "الحرائق", "fr": "Incendies", "en": "Fires"},
        [
            (
                True,
                _text(
                    "حريق في المنزل",
                    ["دخان أو لهب لا يمكن إطفاؤه في ثوانٍ"],
                    ["أخرج الجميع وأغلق الأبواب خلفك", "انخفض تحت الدخان", "اتصل بـ198 من الخارج"],
                    ["لا تستعمل المصعد", "لا تعد إلى الداخل"],
                ),
                _text(
                    "Feu dans la maison",
                    ["Fumée ou flammes impossibles à éteindre en quelques secondes"],
                    [
                        "Faites sortir tout le monde, fermez les portes derrière vous",
                        "Baissez-vous sous la fumée",
                        "Appelez le 198 depuis l’extérieur",
                    ],
                    ["N’utilisez pas l’ascenseur", "Ne retournez pas à l’intérieur"],
                ),
                _text(
                    "Fire at home",
                    ["Smoke or flames you cannot put out within seconds"],
                    [
                        "Get everyone out, close the doors behind you",
                        "Stay low under the smoke",
                        "Call 198 from outside",
                    ],
                    ["Do not use the lift", "Do not go back inside"],
                ),
            ),
            (
                False,
                _text(
                    "اشتعال الملابس",
                    ["حروق واسعة بعد الإطفاء"],
                    ["توقف، انبطح أرضًا، غطّ وجهك وتدحرج", "برّد الحرق بماء جارٍ"],
                    ["لا تركض"],
                ),
                _text(
                    "Vêtements en feu",
                    ["Brûlures étendues après l’extinction"],
                    [
                        "Arrêtez-vous, couchez-vous, couvrez votre visage et roulez",
                        "Refroidissez la brûlure à l’eau courante",
                    ],
                    ["Ne courez pas"],
                ),
                _text(
                    "Clothes on fire",
                    ["Large burns once the fire is out"],
                    ["Stop, drop to the ground, cover your face and roll", "Cool the burn under running water"],
                    ["Do not run"],
                ),
            ),
            (
                True,
                _text(
                    "تسرب الغاز",
                    ["رائحة غاز قوية أو شخص فاقد للوعي"],
                    ["افتح النوافذ", "أغلق صمام الغاز إن أمكن دون خطر", "غادر واتصل بـ198 من الخارج"],
                    ["لا تشعل نارًا ولا تشغّل أو تطفئ أي مفتاح كهربائي"],
                ),
                _text(
                    "Fuite de gaz",
                    ["Forte odeur de gaz ou personne inconsciente"],
                    [
                        "Ouvrez les fenêtres",
                        "Fermez le robinet de gaz si c’est sans danger",
                        "Sortez et appelez le 198 depuis l’extérieur",
                    ],
                    ["N’allumez pas de flamme, ne touchez à aucun interrupteur"],
                ),
                _text(
                    "Gas leak",
                    ["Strong smell of gas or someone unconscious"],
                    ["Open the windows", "Close the gas valve if it is safe", "Leave and call 198 from outside"],
                    ["No flame, do not touch any electric switch"],
                ),
            ),
        ],
    ),
    (
        "fracture",
        "bone",
        "#5D4037",
        {"ar": "الكسور", "fr": "Fractures", "en": "Fractures"},
        [
            (
                False,
                _text(
                    "اشتباه في كسر",
                    ["عضو مشوَّه أو جرح مفتوح أو عجز عن الحركة"],
                    ["ثبّت العضو في وضعه", "اسنده بقطعة قماش", "ضع بردًا ملفوفًا في قماش"],
                    ["لا تحاول تقويم العضو"],
                ),
                _text(
                    "Fracture suspectée",
                    ["Membre déformé, plaie ouverte ou impossibilité de bouger"],
                    [
                        "Gardez le membre immobile dans sa position",
                        "Calez-le avec un tissu",
                        "Appliquez du froid enveloppé dans un linge",
                    ],
                    ["N’essayez pas de remettre le membre droit"],
                ),
                _text(
                    "Suspected fracture",
                    ["Deformed limb, open wound or unable to move"],
                    ["Keep the limb still as found", "Support it with padding", "Apply cold wrapped in a cloth"],
                    ["Do not try to straighten the limb"],
                ),
            ),
            (
                True,
                _text(
                    "إصابة الظهر أو الرقبة",
                    ["سقوط من علو أو حادث مرور"],
                    ["لا تحرّك المصاب إلا في حالة خطر", "ثبّت الرأس والرقبة", "أبقِه دافئًا وطمئنه"],
                    ["لا تعطه أكلًا ولا شربًا"],
                ),
                _text(
                    "Blessure au dos ou au cou",
                    ["Chute de hauteur ou accident de la route"],
                    [
                        "Ne déplacez pas la victime sauf danger",
                        "Maintenez la tête et le cou",
                        "Couvrez-la, rassurez-la",
                    ],
                    ["Ne lui donnez ni à manger ni à boire"],
                ),
                _text(
                    "Back or neck injury",
                    ["Fall from a height or road accident"],
                    [
                        "Do not move the person unless in danger",
                        "Keep the head and neck still",
                        "Keep them warm and reassure them",
                    ],
                    ["Give no food or drink"],
                ),
            ),
        ],
    ),
    (
        "first_aid",
        "first_aid",
        "#C62828",
        {"ar": "الإسعافات الأولية", "fr": "Premiers secours", "en": "First aid"},
        [
            (
                True,
                _text(
                    "شخص لا يستجيب ولا يتنفس",
                    ["دائمًا: اتصل بـ198 فورًا"],
                    [
                        "اتصل بـ198 وشغّل مكبر الصوت",
                        "اضغط بقوة وسرعة وسط الصدر (100 إلى 120 في الدقيقة)",
                        "واصل حتى وصول النجدة",
                    ],
                    ["لا تتوقف إلا إذا تنفس الشخص أو تولى غيرك"],
                ),
                _text(
                    "Personne qui ne répond pas et ne respire pas",
                    ["Toujours : appelez le 198 immédiatement"],
                    [
                        "Appelez le 198, mettez le haut-parleur",
                        "Appuyez fort et vite au centre de la poitrine (100 à 120 par minute)",
                        "Continuez jusqu’à l’arrivée des secours",
                    ],
                    ["N’arrêtez pas sauf si la personne respire ou qu’on vous relaie"],
                ),
                _text(
                    "Unresponsive and not breathing",
                    ["Always: call 198 at once"],
                    [
                        "Call 198, put the phone on speaker",
                        "Push hard and fast in the centre of the chest (100 to 120 a minute)",
                        "Keep going until help arrives",
                    ],
                    ["Do not stop unless the person breathes or someone takes over"],
                ),
            ),
            (
                True,
                _text(
                    "شخص فاقد للوعي يتنفس",
                    ["فقدان الوعي"],
                    ["ضعه على جنبه والرأس مائل إلى الخلف", "راقب تنفسه باستمرار"],
                    ["لا تتركه وحده"],
                ),
                _text(
                    "Personne inconsciente qui respire",
                    ["Perte de connaissance"],
                    ["Mettez-la sur le côté, tête basculée en arrière", "Surveillez sa respiration"],
                    ["Ne la laissez pas seule"],
                ),
                _text(
                    "Unconscious but breathing",
                    ["Loss of consciousness"],
                    ["Turn them on their side, head tilted back", "Keep checking their breathing"],
                    ["Do not leave them alone"],
                ),
            ),
        ],
    ),
    (
        "breathing",
        "lungs",
        "#1565C0",
        {"ar": "المشاكل التنفسية", "fr": "Problèmes respiratoires", "en": "Breathing problems"},
        [
            (
                True,
                _text(
                    "الاختناق بجسم غريب",
                    ["لا يستطيع الكلام ولا السعال"],
                    ["شجّعه على السعال", "حتى 5 ضربات بين الكتفين", "حتى 5 ضغطات على البطن"],
                    ["لا تُدخل أصابعك في فمه دون رؤية الجسم"],
                ),
                _text(
                    "Étouffement",
                    ["Ne peut ni parler ni tousser"],
                    [
                        "Encouragez-la à tousser",
                        "Jusqu’à 5 tapes dans le dos entre les omoplates",
                        "Jusqu’à 5 compressions abdominales",
                    ],
                    ["Ne mettez pas les doigts dans la bouche à l’aveugle"],
                ),
                _text(
                    "Choking",
                    ["Cannot speak or cough"],
                    [
                        "Encourage them to cough",
                        "Up to 5 back blows between the shoulder blades",
                        "Up to 5 abdominal thrusts",
                    ],
                    ["Do not sweep the mouth blindly"],
                ),
            ),
            (
                False,
                _text(
                    "نوبة ربو",
                    ["لا تحسّن بعد البخاخ أو شفاه زرقاء"],
                    ["أجلسه مستقيمًا", "استعمل بخاخ الإسعاف", "حافظ على هدوئه"],
                    ["لا تجعله يستلقي"],
                ),
                _text(
                    "Crise d’asthme",
                    ["Pas d’amélioration après l’inhalateur ou lèvres bleues"],
                    ["Asseyez-la bien droite", "Utilisez son inhalateur de secours", "Gardez-la calme"],
                    ["Ne l’allongez pas"],
                ),
                _text(
                    "Asthma attack",
                    ["No better after the inhaler, or blue lips"],
                    ["Sit them upright", "Use their reliever inhaler", "Keep them calm"],
                    ["Do not lay them down"],
                ),
            ),
            (
                True,
                _text(
                    "استنشاق الدخان",
                    ["سعال شديد أو ضيق تنفس أو صداع"],
                    ["انقله إلى الهواء الطلق", "أجلسه وراقبه"],
                    ["لا تدخل مكانًا مليئًا بالدخان"],
                ),
                _text(
                    "Inhalation de fumée",
                    ["Toux forte, gêne respiratoire ou maux de tête"],
                    ["Amenez-la à l’air libre", "Asseyez-la et surveillez-la"],
                    ["N’entrez pas dans un local enfumé"],
                ),
                _text(
                    "Smoke inhalation",
                    ["Heavy cough, short of breath or headache"],
                    ["Move them to fresh air", "Sit them down and watch them"],
                    ["Do not enter a smoke-filled place"],
                ),
            ),
        ],
    ),
    (
        "burns",
        "burn",
        "#AD1457",
        {"ar": "الحروق", "fr": "Brûlures", "en": "Burns"},
        [
            (
                False,
                _text(
                    "حرق حراري",
                    ["حرق واسع أو في الوجه أو اليدين أو لدى طفل"],
                    ["برّد الحرق بماء جارٍ 20 دقيقة", "انزع الخواتم والملابس غير الملتصقة", "غطّه بقطعة قماش نظيفة"],
                    ["لا ثلج ولا معجون ولا زبدة", "لا تفقأ الفقاعات"],
                ),
                _text(
                    "Brûlure thermique",
                    ["Brûlure étendue, au visage, aux mains ou chez un enfant"],
                    [
                        "Refroidissez 20 minutes à l’eau courante",
                        "Retirez bagues et vêtements non collés",
                        "Couvrez d’un linge propre",
                    ],
                    ["Ni glace, ni dentifrice, ni beurre", "Ne percez pas les cloques"],
                ),
                _text(
                    "Heat burn",
                    ["Large burn, on the face or hands, or a child"],
                    [
                        "Cool for 20 minutes under running water",
                        "Remove rings and clothing that is not stuck",
                        "Cover with a clean cloth",
                    ],
                    ["No ice, toothpaste or butter", "Do not burst blisters"],
                ),
            ),
        ],
    ),
    (
        "bleeding",
        "drop",
        "#6A1B9A",
        {"ar": "النزيف", "fr": "Saignements", "en": "Bleeding"},
        [
            (
                True,
                _text(
                    "نزيف حاد",
                    ["دم يتدفق بغزارة"],
                    ["اضغط بقوة على الجرح بقماش نظيف", "واصل الضغط دون توقف", "مدّد المصاب"],
                    ["لا تنزع جسمًا مغروسًا في الجرح"],
                ),
                _text(
                    "Saignement abondant",
                    ["Le sang coule en abondance"],
                    [
                        "Appuyez fort sur la plaie avec un linge propre",
                        "Maintenez la pression sans relâcher",
                        "Allongez la victime",
                    ],
                    ["Ne retirez pas un objet planté dans la plaie"],
                ),
                _text(
                    "Severe bleeding",
                    ["Blood is flowing heavily"],
                    [
                        "Press hard on the wound with a clean cloth",
                        "Keep pressing without letting go",
                        "Lay the person down",
                    ],
                    ["Do not remove an object stuck in the wound"],
                ),
            ),
            (
                False,
                _text(
                    "نزيف الأنف",
                    ["لا يتوقف بعد 20 دقيقة"],
                    ["اجلس وأمِل الرأس إلى الأمام", "اضغط على الجزء اللين من الأنف 10 دقائق"],
                    ["لا تُمِل الرأس إلى الخلف"],
                ),
                _text(
                    "Saignement de nez",
                    ["Ne s’arrête pas après 20 minutes"],
                    ["Asseyez-vous, penchez la tête en avant", "Pincez la partie molle du nez 10 minutes"],
                    ["Ne basculez pas la tête en arrière"],
                ),
                _text(
                    "Nosebleed",
                    ["Does not stop after 20 minutes"],
                    ["Sit down, lean the head forward", "Pinch the soft part of the nose for 10 minutes"],
                    ["Do not tilt the head back"],
                ),
            ),
        ],
    ),
]


def upgrade() -> None:
    run_script(UPGRADE)
    bind = op.get_bind()
    for position, (key, icon, colour, title, items) in enumerate(SEED):
        topic_id = bind.execute(
            sa.text(
                "INSERT INTO content.guide_topic (key, title, icon, colour, position) "
                "VALUES (:k, CAST(:t AS jsonb), :i, :c, :p) RETURNING id"
            ),
            {"k": key, "t": json.dumps(title, ensure_ascii=False), "i": icon, "c": colour, "p": position * 10},
        ).scalar_one()
        for item_position, (call, ar, fr, en) in enumerate(items):
            bind.execute(
                sa.text(
                    "INSERT INTO content.guide_item (topic_id, position, content, call_198) "
                    "VALUES (:t, :p, CAST(:c AS jsonb), :call)"
                ),
                {
                    "t": topic_id,
                    "p": item_position * 10,
                    "c": json.dumps({"ar": ar, "fr": fr, "en": en}, ensure_ascii=False),
                    "call": call,
                },
            )


def downgrade() -> None:
    run_script(
        """
        DROP TABLE content.guide_item;
        DROP TABLE content.guide_topic;
        DELETE FROM content.revision WHERE name = 'emergency_guide';
        """
    )
