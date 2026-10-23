"""Emergency hub: more first-aid items and the "other emergencies" topic (phase B1, Yamen 2026-10-23).

Twenty items in Arabic, French and English, written in our own words from open, widely recognised guidance
(sources per item in docs/phase-b/first-aid-sources.md: IFRC International First Aid, Resuscitation and Education
Guidelines 2020; European Resuscitation Council Guidelines 2021; WHO fact sheets). Like the first load (0033), every
item is **not validated**: the app shows the amber "[SIM] content awaiting medical validation" banner until the
Office's medical staff validates it. Items go after the existing ones of their topic; a topic an editor removed is
skipped. The guide's revision is bumped so the app fetches the new version.

Downgrade removes the items and the topic this migration added, unless an editor changed them since.

Revision ID: 0036_emergency_guide_more
Revises: 0035_layer_simulated
Create Date: 2026-10-23
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0036_emergency_guide_more"
down_revision: str | None = "0035_layer_simulated"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _text(title: str, call: list[str], steps: list[str], dont: list[str]) -> dict[str, Any]:
    return {"title": title, "call": call, "steps": steps, "dont": dont}


Item = tuple[bool, dict[str, Any], dict[str, Any], dict[str, Any]]

# New topics: key → (icon, colour, title ar/fr/en); they go after the existing ones.
NEW_TOPICS: dict[str, tuple[str, str, dict[str, str]]] = {
    "other": ("pin", "#00695C", {"ar": "حالات أخرى", "fr": "Autres situations", "en": "Other emergencies"}),
}

# topic key → items (call_198, ar, fr, en), appended to the topic.
MORE: list[tuple[str, list[Item]]] = [
    (
        "fire",
        [
            (
                False,
                _text(
                    "اشتعال الزيت في المقلاة",
                    ["النار تمتد خارج المقلاة أو إلى الخزائن"],
                    [
                        "أطفئ الموقد إن أمكن دون أن تمد يدك فوق اللهب",
                        "غطّ المقلاة بغطاء معدني أو بقطعة قماش مبللة جيدًا (غير مقطرة)",
                        "اتركها مغطاة حتى تبرد تمامًا",
                    ],
                    ["لا تصب الماء على الزيت المشتعل أبدًا", "لا تحمل المقلاة المشتعلة إلى الخارج"],
                ),
                _text(
                    "Feu d’huile dans une poêle",
                    ["Le feu dépasse la poêle ou gagne les placards"],
                    [
                        "Coupez le feu si vous le pouvez sans passer la main au-dessus des flammes",
                        "Couvrez la poêle avec un couvercle métallique ou un linge bien humide (essoré)",
                        "Laissez couvert jusqu’à refroidissement complet",
                    ],
                    ["Ne versez jamais d’eau sur de l’huile en feu", "Ne transportez pas la poêle en feu dehors"],
                ),
                _text(
                    "Oil fire in a pan",
                    ["The fire spreads beyond the pan or to the cupboards"],
                    [
                        "Turn off the heat if you can do it without reaching over the flames",
                        "Cover the pan with a metal lid or a well-wetted (wrung-out) cloth",
                        "Leave it covered until it has cooled completely",
                    ],
                    ["Never pour water on burning oil", "Do not carry the burning pan outside"],
                ),
            ),
            (
                True,
                _text(
                    "حريق غابة أو أعشاب قريب",
                    ["دخان أو لهب يقترب من منزلك أو من طريقك"],
                    [
                        "اتصل بـ198 وحدّد المكان بدقة",
                        "ابتعد عكس اتجاه الريح ونحو منطقة خالية أو مكان صخري أو طريق معبّد",
                        "إن كنت في المنزل: أغلق النوافذ والأبواب وأبعد ما يشتعل عن الجدران",
                        "اتبع تعليمات الحماية المدنية للإخلاء",
                    ],
                    ["لا تحاول عبور النار", "لا تصعد نحو أعلى المنحدر أمام النار", "لا تعد لأخذ أغراضك"],
                ),
                _text(
                    "Feu de forêt ou de broussailles proche",
                    ["Fumée ou flammes qui s’approchent de votre maison ou de votre chemin"],
                    [
                        "Appelez le 198 en donnant le lieu exact",
                        "Éloignez-vous dos au vent, vers une zone dégagée, rocheuse ou une route goudronnée",
                        "À la maison : fermez portes et fenêtres, éloignez des murs ce qui peut brûler",
                        "Suivez les consignes d’évacuation de la Protection civile",
                    ],
                    [
                        "N’essayez pas de traverser le feu",
                        "Ne montez pas une pente devant le feu",
                        "Ne retournez pas chercher vos affaires",
                    ],
                ),
                _text(
                    "Forest or brush fire nearby",
                    ["Smoke or flames coming towards your home or your way"],
                    [
                        "Call 198 and give the exact place",
                        "Move away with the wind at your back, towards open, rocky ground or a paved road",
                        "At home: close doors and windows, move anything that burns away from the walls",
                        "Follow the Civil Protection's evacuation instructions",
                    ],
                    [
                        "Do not try to cross the fire",
                        "Do not climb a slope ahead of the fire",
                        "Do not go back for belongings",
                    ],
                ),
            ),
        ],
    ),
    (
        "fracture",
        [
            (
                False,
                _text(
                    "التواء المفصل",
                    ["ألم شديد، تشوه ظاهر أو عدم القدرة على تحريك الطرف أو الوقوف عليه"],
                    [
                        "أرِح المفصل ولا تحمّل عليه",
                        "ضع ثلجًا ملفوفًا في قماش 20 دقيقة كل ساعتين تقريبًا",
                        "ارفع الطرف المصاب فوق مستوى القلب إن أمكن",
                    ],
                    ["لا تضع الثلج مباشرة على الجلد", "لا تدلّك المفصل المصاب"],
                ),
                _text(
                    "Entorse",
                    ["Douleur forte, déformation visible ou impossibilité de bouger ou de s’appuyer sur le membre"],
                    [
                        "Mettez l’articulation au repos, sans appui",
                        "Appliquez de la glace enveloppée dans un linge 20 minutes environ toutes les deux heures",
                        "Surélevez le membre au-dessus du cœur si possible",
                    ],
                    ["Ne posez pas la glace directement sur la peau", "Ne massez pas l’articulation blessée"],
                ),
                _text(
                    "Sprain",
                    ["Severe pain, visible deformity, or the limb cannot be moved or bear weight"],
                    [
                        "Rest the joint, no weight on it",
                        "Apply ice wrapped in a cloth for 20 minutes about every two hours",
                        "Raise the limb above the heart if possible",
                    ],
                    ["Do not put ice directly on the skin", "Do not massage the injured joint"],
                ),
            ),
            (
                True,
                _text(
                    "إصابة في الرأس",
                    [
                        "فقدان الوعي ولو لحظة، أو نعاس غير عادي أو تشوش",
                        "قيء متكرر، صداع يشتد، أو سيلان دم أو سائل من الأنف أو الأذن",
                    ],
                    [
                        "أبقِ المصاب ساكنًا وراقب وعيه وتنفسه",
                        "اضغط على الجرح النازف بقطعة قماش نظيفة",
                        "ضع كمادة باردة على الكدمة",
                        "إن فقد وعيه وهو يتنفس: ضعه على جنبه مع الحفاظ على استقامة الرأس والرقبة",
                    ],
                    ["لا تتركه وحده خلال الساعات الأولى", "لا تعطه أكلًا ولا شربًا ولا دواءً منوّمًا"],
                ),
                _text(
                    "Blessure à la tête",
                    [
                        "Perte de connaissance même brève, somnolence inhabituelle ou confusion",
                        "Vomissements répétés, mal de tête qui augmente, sang ou liquide qui coule du nez ou de l’oreille",
                    ],
                    [
                        "Gardez la victime immobile, surveillez sa conscience et sa respiration",
                        "Comprimez une plaie qui saigne avec un linge propre",
                        "Posez un linge froid sur la bosse",
                        "Si elle perd connaissance et respire : sur le côté, tête et cou bien alignés",
                    ],
                    [
                        "Ne la laissez pas seule pendant les premières heures",
                        "Ne lui donnez ni à manger, ni à boire, ni somnifère",
                    ],
                ),
                _text(
                    "Head injury",
                    [
                        "Loss of consciousness even briefly, unusual drowsiness or confusion",
                        "Repeated vomiting, worsening headache, blood or fluid from the nose or ear",
                    ],
                    [
                        "Keep the person still and watch their consciousness and breathing",
                        "Press on a bleeding wound with a clean cloth",
                        "Put a cold cloth on the bump",
                        "If they become unresponsive but breathe: on their side, keeping head and neck in line",
                    ],
                    ["Do not leave them alone in the first hours", "Do not give food, drink or sleeping pills"],
                ),
            ),
        ],
    ),
    (
        "first_aid",
        [
            (
                True,
                _text(
                    "علامات النوبة القلبية",
                    ["ألم أو ضغط في الصدر يدوم أكثر من بضع دقائق، قد يمتد إلى الذراع أو الفك أو الظهر"],
                    [
                        "اتصل بـ198 فورًا",
                        "أجلس المصاب في وضعية مريحة وفكّ ملابسه الضيقة",
                        "طمئنه وابقَ معه وراقب تنفسه",
                        "إن توقف عن التنفس: ابدأ الإنعاش القلبي الرئوي",
                    ],
                    ["لا تدعه يمشي أو يبذل جهدًا", "لا تقله بنفسك إن كان الإسعاف قادمًا"],
                ),
                _text(
                    "Signes de crise cardiaque",
                    [
                        "Douleur ou serrement dans la poitrine plus de quelques minutes, parfois vers le bras, la mâchoire ou le dos"
                    ],
                    [
                        "Appelez le 198 immédiatement",
                        "Installez la personne assise confortablement, desserrez ses vêtements",
                        "Rassurez-la, restez avec elle, surveillez sa respiration",
                        "Si elle cesse de respirer : commencez la réanimation cardio-pulmonaire",
                    ],
                    [
                        "Ne la laissez pas marcher ni faire d’effort",
                        "Ne la transportez pas vous-même si les secours arrivent",
                    ],
                ),
                _text(
                    "Signs of a heart attack",
                    [
                        "Chest pain or pressure lasting more than a few minutes, sometimes spreading to the arm, jaw or back"
                    ],
                    [
                        "Call 198 at once",
                        "Help the person sit comfortably and loosen tight clothing",
                        "Reassure them, stay with them and watch their breathing",
                        "If they stop breathing: start cardiopulmonary resuscitation",
                    ],
                    ["Do not let them walk or make an effort", "Do not drive them yourself if the ambulance is coming"],
                ),
            ),
            (
                True,
                _text(
                    "علامات السكتة الدماغية",
                    ["ميلان الوجه، ضعف ذراع أو ساق، اضطراب مفاجئ في الكلام"],
                    [
                        "اتصل بـ198 فورًا: كل دقيقة مهمة",
                        "سجّل ساعة ظهور العلامات الأولى",
                        "أبقِ المصاب مرتاحًا وراقب تنفسه",
                        "إن فقد وعيه وهو يتنفس: ضعه على جنبه",
                    ],
                    ["لا تعطه أكلًا ولا شربًا ولا دواءً", "لا تنتظر أن تزول العلامات"],
                ),
                _text(
                    "Signes d’accident vasculaire cérébral (AVC)",
                    ["Visage qui s’affaisse, faiblesse d’un bras ou d’une jambe, trouble soudain de la parole"],
                    [
                        "Appelez le 198 immédiatement : chaque minute compte",
                        "Notez l’heure d’apparition des premiers signes",
                        "Gardez la personne au calme, surveillez sa respiration",
                        "Si elle perd connaissance et respire : mettez-la sur le côté",
                    ],
                    [
                        "Ne lui donnez ni à manger, ni à boire, ni médicament",
                        "N’attendez pas que les signes disparaissent",
                    ],
                ),
                _text(
                    "Signs of a stroke",
                    ["Face drooping, weakness of an arm or a leg, sudden trouble speaking"],
                    [
                        "Call 198 at once: every minute counts",
                        "Note the time the first signs appeared",
                        "Keep the person calm and watch their breathing",
                        "If they become unresponsive but breathe: put them on their side",
                    ],
                    ["Do not give food, drink or medicine", "Do not wait for the signs to go away"],
                ),
            ),
            (
                False,
                _text(
                    "نوبة صرع (تشنجات)",
                    [
                        "أول نوبة، أو نوبة تدوم أكثر من 5 دقائق، أو نوبات متتالية",
                        "إصابة، صعوبة في التنفس بعد النوبة، أو حدوثها في الماء",
                    ],
                    [
                        "أبعد الأشياء الصلبة من حوله وضع شيئًا ليّنًا تحت رأسه",
                        "سجّل مدة النوبة",
                        "بعد توقف التشنجات: ضعه على جنبه وابقَ معه حتى يستعيد وعيه",
                    ],
                    ["لا تمسكه بالقوة", "لا تضع شيئًا في فمه"],
                ),
                _text(
                    "Crise d’épilepsie (convulsions)",
                    [
                        "Première crise, crise de plus de 5 minutes ou crises qui se suivent",
                        "Blessure, difficulté à respirer après la crise, ou crise dans l’eau",
                    ],
                    [
                        "Écartez les objets durs et glissez quelque chose de mou sous sa tête",
                        "Notez la durée de la crise",
                        "Quand les secousses s’arrêtent : sur le côté, restez jusqu’à son réveil complet",
                    ],
                    ["Ne la retenez pas de force", "Ne mettez rien dans sa bouche"],
                ),
                _text(
                    "Seizure (convulsions)",
                    [
                        "A first seizure, one lasting more than 5 minutes, or seizures one after another",
                        "An injury, trouble breathing afterwards, or a seizure in water",
                    ],
                    [
                        "Move hard objects away and put something soft under their head",
                        "Time the seizure",
                        "When the jerking stops: put them on their side and stay until they are fully awake",
                    ],
                    ["Do not hold them down", "Do not put anything in their mouth"],
                ),
            ),
            (
                False,
                _text(
                    "انخفاض السكر عند مريض السكري",
                    ["لا يستطيع البلع، أو فقد وعيه، أو لم يتحسن بعد 15 دقيقة"],
                    [
                        "إن كان واعيًا ويبلع: أعطه سكرًا سريعًا (عصير، مشروب محلّى، قطع سكر)",
                        "أجلسه وانتظر 15 دقيقة ثم أعد إن لم يتحسن",
                        "بعد التحسن: وجبة خفيفة",
                    ],
                    ["لا تعطِ شيئًا في الفم لشخص فاقد للوعي"],
                ),
                _text(
                    "Hypoglycémie chez une personne diabétique",
                    ["Ne peut pas avaler, perd connaissance, ou pas d’amélioration après 15 minutes"],
                    [
                        "Si elle est consciente et avale : sucre rapide (jus, boisson sucrée, morceaux de sucre)",
                        "Faites-la asseoir, attendez 15 minutes, recommencez si elle ne va pas mieux",
                        "Une fois rétablie : une collation",
                    ],
                    ["Ne donnez rien par la bouche à une personne inconsciente"],
                ),
                _text(
                    "Low blood sugar in a person with diabetes",
                    ["Cannot swallow, becomes unresponsive, or no better after 15 minutes"],
                    [
                        "If they are conscious and can swallow: give fast sugar (juice, sugary drink, sugar cubes)",
                        "Help them sit, wait 15 minutes, repeat if they are not better",
                        "Once better: a snack",
                    ],
                    ["Do not give anything by mouth to an unresponsive person"],
                ),
            ),
            (
                True,
                _text(
                    "حساسية شديدة",
                    ["صعوبة في التنفس، انتفاخ الوجه أو اللسان أو الحلق، دوار أو إغماء"],
                    [
                        "اتصل بـ198 فورًا",
                        "إن كان لديه حقنة أدرينالين ذاتية: ساعده على استعمالها في الفخذ",
                        "إن كان يتنفس بصعوبة: أجلسه؛ إن كان دائخًا: مدّده وارفع ساقيه",
                        "يمكن إعادة الحقنة بعد 5 دقائق إن لم يتحسن وتوفرت حقنة ثانية",
                    ],
                    ["لا تدعه يقف أو يمشي فجأة", "لا تنتظر زوال العلامات وحدها"],
                ),
                _text(
                    "Réaction allergique grave",
                    ["Difficulté à respirer, gonflement du visage, de la langue ou de la gorge, malaise"],
                    [
                        "Appelez le 198 immédiatement",
                        "Si elle a un stylo d’adrénaline : aidez-la à l’utiliser dans la cuisse",
                        "Si elle respire mal : assise ; si elle a un malaise : allongée, jambes surélevées",
                        "Une seconde dose après 5 minutes si pas d’amélioration et qu’un second stylo est disponible",
                    ],
                    ["Ne la faites pas se lever ni marcher brusquement", "N’attendez pas que cela passe seul"],
                ),
                _text(
                    "Severe allergic reaction",
                    ["Trouble breathing, swelling of the face, tongue or throat, feeling faint"],
                    [
                        "Call 198 at once",
                        "If they have an adrenaline auto-injector: help them use it in the thigh",
                        "If breathing is hard: sitting up; if faint: lying down with legs raised",
                        "A second dose after 5 minutes if no better and a second injector is available",
                    ],
                    ["Do not let them stand up or walk suddenly", "Do not wait for it to pass on its own"],
                ),
            ),
        ],
    ),
    (
        "breathing",
        [
            (
                True,
                _text(
                    "اختناق رضيع (أقل من سنة)",
                    ["لا يبكي ولا يسعل ولا يتنفس"],
                    [
                        "اطلب من شخص الاتصال بـ198",
                        "ضع الرضيع على ساعدك ووجهه إلى الأسفل والرأس أخفض من الصدر، وأسند الرأس",
                        "اضرب 5 ضربات بين لوحَي الكتف بكعب اليد",
                        "إن لم يخرج الجسم: اقلبه على ظهره واضغط 5 مرات بإصبعين وسط الصدر",
                        "كرر حتى يخرج الجسم أو يصل الإسعاف",
                    ],
                    ["لا تُدخل إصبعك في فمه بحثًا عن الجسم", "لا تقلبه رأسًا على عقب من قدميه"],
                ),
                _text(
                    "Étouffement d’un bébé (moins d’un an)",
                    ["Il ne pleure pas, ne tousse pas, ne respire pas"],
                    [
                        "Faites appeler le 198",
                        "Couchez le bébé à plat ventre sur votre avant-bras, tête plus basse que la poitrine, tête soutenue",
                        "Donnez 5 claques dans le dos, entre les omoplates, avec le talon de la main",
                        "Si l’objet ne sort pas : sur le dos, 5 compressions avec deux doigts au milieu de la poitrine",
                        "Recommencez jusqu’à la sortie de l’objet ou l’arrivée des secours",
                    ],
                    ["Ne cherchez pas l’objet avec le doigt dans sa bouche", "Ne le suspendez pas par les pieds"],
                ),
                _text(
                    "Choking baby (under one year)",
                    ["The baby cannot cry, cough or breathe"],
                    [
                        "Have someone call 198",
                        "Lay the baby face down along your forearm, head lower than the chest, head supported",
                        "Give 5 back blows between the shoulder blades with the heel of your hand",
                        "If the object does not come out: turn on the back, 5 chest thrusts with two fingers mid-chest",
                        "Repeat until the object comes out or help arrives",
                    ],
                    ["Do not sweep the mouth blindly with a finger", "Do not hold the baby upside down by the feet"],
                ),
            ),
            (
                True,
                _text(
                    "التسمم بأحادي أكسيد الكربون (الكانون، المدفأة، سخان الماء)",
                    ["صداع، دوار، غثيان أو نعاس لعدة أشخاص في نفس المكان، أو فقدان الوعي"],
                    [
                        "افتح النوافذ والأبواب فورًا",
                        "أطفئ الجهاز إن أمكن واخرج الجميع إلى الهواء الطلق",
                        "اتصل بـ198 من الخارج",
                        "إن فقد أحدهم وعيه وهو يتنفس: ضعه على جنبه؛ إن لم يتنفس: ابدأ الإنعاش",
                    ],
                    ["لا تعد إلى الداخل قبل التهوية الكاملة", "لا تستعمل الكانون أو الشواية داخل غرفة مغلقة"],
                ),
                _text(
                    "Intoxication au monoxyde de carbone (kanoun, chauffage, chauffe-eau)",
                    [
                        "Mal de tête, vertiges, nausées ou somnolence chez plusieurs personnes du même lieu, ou perte de connaissance"
                    ],
                    [
                        "Ouvrez portes et fenêtres immédiatement",
                        "Arrêtez l’appareil si possible et faites sortir tout le monde à l’air libre",
                        "Appelez le 198 depuis l’extérieur",
                        "Victime inconsciente qui respire : sur le côté ; qui ne respire pas : réanimation",
                    ],
                    [
                        "Ne retournez pas à l’intérieur avant aération complète",
                        "N’utilisez pas de kanoun ou de brasero dans une pièce fermée",
                    ],
                ),
                _text(
                    "Carbon monoxide poisoning (kanoun, heater, water heater)",
                    [
                        "Headache, dizziness, nausea or drowsiness in several people in the same place, or unresponsiveness"
                    ],
                    [
                        "Open doors and windows at once",
                        "Turn the appliance off if you can and get everyone out into fresh air",
                        "Call 198 from outside",
                        "Unresponsive but breathing: on their side; not breathing: start resuscitation",
                    ],
                    [
                        "Do not go back in before the place is fully aired",
                        "Never use a kanoun or brazier in a closed room",
                    ],
                ),
            ),
        ],
    ),
    (
        "burns",
        [
            (
                True,
                _text(
                    "حرق كيميائي",
                    ["حرق في العين أو الوجه أو مساحة واسعة، أو مادة مجهولة"],
                    [
                        "احمِ نفسك (قفازات) ونزع الملابس الملوثة",
                        "اغسل بالماء الجاري 20 دقيقة على الأقل",
                        "للعين: اغسلها بالماء الجاري مع إبقائها مفتوحة، من الداخل إلى الخارج",
                        "احتفظ بعلبة المادة لإعلام الإسعاف",
                    ],
                    ["لا تحاول تعديل المادة بمادة أخرى", "لا تفرك الجلد أو العين"],
                ),
                _text(
                    "Brûlure chimique",
                    ["Brûlure à l’œil, au visage ou étendue, ou produit inconnu"],
                    [
                        "Protégez-vous (gants) et retirez les vêtements souillés",
                        "Rincez à l’eau courante au moins 20 minutes",
                        "Pour l’œil : rincez à l’eau courante, œil ouvert, du coin interne vers l’extérieur",
                        "Gardez l’emballage du produit pour les secours",
                    ],
                    ["N’essayez pas de neutraliser avec un autre produit", "Ne frottez ni la peau ni l’œil"],
                ),
                _text(
                    "Chemical burn",
                    ["A burn to the eye or face, a large area, or an unknown product"],
                    [
                        "Protect yourself (gloves) and remove contaminated clothing",
                        "Rinse under running water for at least 20 minutes",
                        "For the eye: rinse under running water with the eye open, from the inner corner outwards",
                        "Keep the product's container for the ambulance crew",
                    ],
                    ["Do not try to neutralise it with another product", "Do not rub the skin or the eye"],
                ),
            ),
            (
                True,
                _text(
                    "حرق كهربائي",
                    ["كل حرق كهربائي يحتاج إلى فحص طبي، حتى لو بدا صغيرًا"],
                    [
                        "اقطع التيار الكهربائي قبل لمس المصاب",
                        "راقب تنفسه؛ إن لم يتنفس: ابدأ الإنعاش",
                        "برّد الحروق بالماء الجاري وغطّها بقماش نظيف",
                    ],
                    ["لا تلمس المصاب ما دام التيار موصولًا", "لا تقترب من خط كهربائي ساقط"],
                ),
                _text(
                    "Brûlure électrique",
                    ["Toute brûlure électrique doit être vue par un médecin, même petite"],
                    [
                        "Coupez le courant avant de toucher la victime",
                        "Surveillez sa respiration ; si elle ne respire pas : réanimation",
                        "Refroidissez les brûlures à l’eau courante puis couvrez d’un linge propre",
                    ],
                    [
                        "Ne touchez pas la victime tant que le courant passe",
                        "N’approchez pas d’une ligne électrique tombée",
                    ],
                ),
                _text(
                    "Electrical burn",
                    ["Every electrical burn needs a doctor, even a small one"],
                    [
                        "Switch off the power before touching the person",
                        "Watch their breathing; if they do not breathe: start resuscitation",
                        "Cool the burns under running water, then cover with a clean cloth",
                    ],
                    ["Do not touch the person while the current is on", "Do not go near a fallen power line"],
                ),
            ),
        ],
    ),
    (
        "bleeding",
        [
            (
                False,
                _text(
                    "جرح صغير أو خدش",
                    ["جرح عميق أو واسع، جسم مغروس، أو جرح ملوث أو ناتج عن عضة"],
                    [
                        "اغسل يديك ثم نظّف الجرح بالماء الجاري",
                        "اضغط بقطعة قماش نظيفة حتى يتوقف النزيف",
                        "غطّه بضمادة نظيفة",
                        "استشر طبيبًا بشأن التلقيح ضد الكزاز إن لم يكن محيّنًا",
                    ],
                    ["لا تنفخ على الجرح", "لا تضع عليه موادًا غير معقّمة (بن، تراب، معجون)"],
                ),
                _text(
                    "Petite plaie ou écorchure",
                    ["Plaie profonde ou large, objet planté, plaie sale ou due à une morsure"],
                    [
                        "Lavez-vous les mains puis nettoyez la plaie à l’eau courante",
                        "Comprimez avec un linge propre jusqu’à l’arrêt du saignement",
                        "Couvrez d’un pansement propre",
                        "Demandez conseil à un médecin pour le vaccin antitétanique s’il n’est pas à jour",
                    ],
                    ["Ne soufflez pas sur la plaie", "N’y mettez rien de non stérile (café, terre, dentifrice)"],
                ),
                _text(
                    "Small cut or graze",
                    ["A deep or wide wound, an object stuck in it, a dirty wound or a bite"],
                    [
                        "Wash your hands, then clean the wound under running water",
                        "Press with a clean cloth until the bleeding stops",
                        "Cover with a clean dressing",
                        "Ask a doctor about a tetanus shot if yours is not up to date",
                    ],
                    ["Do not blow on the wound", "Do not put anything unsterile on it (coffee, soil, toothpaste)"],
                ),
            ),
        ],
    ),
    (
        "other",
        [
            (
                True,
                _text(
                    "الغرق",
                    ["كل شخص أُخرج من الماء بعد صعوبة، حتى لو بدا بخير"],
                    [
                        "لا تنزل إلى الماء إلا إن كنت قادرًا؛ ارمِ له شيئًا يطفو أو مدّ له عصا",
                        "خارج الماء: إن لم يتنفس، أعطِ 5 نفخات ثم ابدأ الإنعاش القلبي الرئوي",
                        "إن كان يتنفس: ضعه على جنبه وغطّه",
                    ],
                    ["لا تحاول إخراج الماء من بطنه", "لا تتركه وحده حتى وصول الإسعاف"],
                ),
                _text(
                    "Noyade",
                    ["Toute personne sortie de l’eau en difficulté, même si elle semble aller bien"],
                    [
                        "N’entrez dans l’eau que si vous en êtes capable ; lancez un objet qui flotte ou tendez une perche",
                        "Hors de l’eau : si elle ne respire pas, 5 insufflations puis réanimation cardio-pulmonaire",
                        "Si elle respire : sur le côté, couverte",
                    ],
                    [
                        "N’essayez pas de lui faire rejeter l’eau",
                        "Ne la laissez pas seule jusqu’à l’arrivée des secours",
                    ],
                ),
                _text(
                    "Drowning",
                    ["Anyone taken out of the water after struggling, even if they seem fine"],
                    [
                        "Only go into the water if you can; throw something that floats or reach out with a pole",
                        "Out of the water: if they do not breathe, give 5 rescue breaths, then start CPR",
                        "If they breathe: on their side, keep them warm",
                    ],
                    ["Do not try to get the water out of their stomach", "Do not leave them alone until help arrives"],
                ),
            ),
            (
                True,
                _text(
                    "ضربة الشمس",
                    ["تشوش، كلام غير مفهوم، جلد ساخن، أو فقدان الوعي"],
                    [
                        "انقله إلى مكان ظليل أو بارد",
                        "برّده بسرعة: ماء بارد على الجسم، كمادات مبللة، تهوية",
                        "إن كان واعيًا ويبلع: اسقه ماءً باردًا على جرعات",
                    ],
                    ["لا تعطه دواء خافضًا للحرارة", "لا تعطِ شيئًا في الفم لشخص فاقد للوعي"],
                ),
                _text(
                    "Coup de chaleur",
                    ["Confusion, propos incohérents, peau brûlante, ou perte de connaissance"],
                    [
                        "Mettez la personne à l’ombre ou au frais",
                        "Refroidissez-la vite : eau fraîche sur le corps, linges mouillés, ventilation",
                        "Si elle est consciente et avale : de l’eau fraîche par petites gorgées",
                    ],
                    [
                        "Ne donnez pas de médicament contre la fièvre",
                        "Ne donnez rien par la bouche à une personne inconsciente",
                    ],
                ),
                _text(
                    "Heatstroke",
                    ["Confusion, slurred speech, hot skin, or unresponsiveness"],
                    [
                        "Move the person to shade or a cool place",
                        "Cool them quickly: cool water on the body, wet cloths, fanning",
                        "If conscious and able to swallow: cool water in small sips",
                    ],
                    ["Do not give fever medicine", "Do not give anything by mouth to an unresponsive person"],
                ),
            ),
            (
                True,
                _text(
                    "لدغة عقرب",
                    ["كل لدغة لطفل أو لمسنّ أو لمريض، أو ظهور تعرق، قيء، صعوبة في التنفس أو تشنجات"],
                    [
                        "اتصل بـ198 أو توجه إلى أقرب مركز صحي",
                        "أبقِ المصاب هادئًا والطرف الملدوغ ساكنًا",
                        "نظّف مكان اللدغة وضع عليه كمادة باردة",
                        "انزع الخواتم والأساور قبل الانتفاخ",
                    ],
                    ["لا تجرح مكان اللدغة ولا تمصّه", "لا تربط الطرف برباط ضاغط", "لا تضع عليه موادًا تقليدية"],
                ),
                _text(
                    "Piqûre de scorpion",
                    [
                        "Toute piqûre d’un enfant, d’une personne âgée ou malade, ou sueurs, vomissements, gêne respiratoire, convulsions"
                    ],
                    [
                        "Appelez le 198 ou rendez-vous au centre de santé le plus proche",
                        "Gardez la personne calme et le membre piqué immobile",
                        "Nettoyez la piqûre et posez un linge froid",
                        "Retirez bagues et bracelets avant le gonflement",
                    ],
                    [
                        "N’incisez pas et ne sucez pas la piqûre",
                        "Ne posez pas de garrot",
                        "Ne mettez pas de produits traditionnels",
                    ],
                ),
                _text(
                    "Scorpion sting",
                    [
                        "Any sting in a child, an older or ill person, or sweating, vomiting, trouble breathing, seizures"
                    ],
                    [
                        "Call 198 or go to the nearest health centre",
                        "Keep the person calm and the stung limb still",
                        "Clean the sting and put a cold cloth on it",
                        "Remove rings and bracelets before swelling starts",
                    ],
                    ["Do not cut or suck the sting", "Do not put on a tourniquet", "Do not apply traditional remedies"],
                ),
            ),
            (
                False,
                _text(
                    "عضة كلب أو قط أو حيوان آخر",
                    ["نزيف قوي أو جرح عميق أو في الوجه"],
                    [
                        "اغسل الجرح بالماء والصابون 15 دقيقة",
                        "غطّه بضمادة نظيفة",
                        "توجه في نفس اليوم إلى مركز صحي: قد يلزم التلقيح ضد داء الكلب",
                        "إن أمكن دون خطر: لاحظ الحيوان ولا تقتله",
                    ],
                    ["لا تهمل العضة ولو كانت صغيرة", "لا تخِط الجرح أو تغلقه بنفسك"],
                ),
                _text(
                    "Morsure de chien, de chat ou d’un autre animal",
                    ["Saignement important, plaie profonde ou au visage"],
                    [
                        "Lavez la plaie à l’eau et au savon pendant 15 minutes",
                        "Couvrez d’un pansement propre",
                        "Allez le jour même dans un centre de santé : la vaccination antirabique peut être nécessaire",
                        "Si possible sans danger : faites surveiller l’animal, ne le tuez pas",
                    ],
                    ["Ne négligez pas une morsure, même petite", "Ne fermez pas la plaie vous-même"],
                ),
                _text(
                    "Dog, cat or other animal bite",
                    ["Heavy bleeding, a deep wound or a wound on the face"],
                    [
                        "Wash the wound with soap and water for 15 minutes",
                        "Cover it with a clean dressing",
                        "Go to a health centre the same day: rabies vaccination may be needed",
                        "If safely possible: have the animal observed, do not kill it",
                    ],
                    ["Do not ignore a bite, even a small one", "Do not close the wound yourself"],
                ),
            ),
            (
                True,
                _text(
                    "تسمم بابتلاع مادة",
                    ["فقدان الوعي، صعوبة في التنفس، تشنجات، أو ابتلاع مادة كاوية (جافيل، مزيل الكلس)"],
                    [
                        "اتصل بـ198 أو بالمركز الوطني لمكافحة التسمم والإسعاف الطبي",
                        "احتفظ بالعلبة أو الدواء لمعرفة المادة والكمية",
                        "إن فقد وعيه وهو يتنفس: ضعه على جنبه",
                    ],
                    ["لا تحاول جعله يتقيأ", "لا تعطه حليبًا ولا ماءً ولا أي شيء دون نصيحة طبية"],
                ),
                _text(
                    "Intoxication par ingestion",
                    [
                        "Perte de connaissance, gêne respiratoire, convulsions, ou produit corrosif avalé (javel, détartrant)"
                    ],
                    [
                        "Appelez le 198 ou le Centre national anti-poison",
                        "Gardez l’emballage ou le médicament pour connaître le produit et la quantité",
                        "Si elle perd connaissance et respire : mettez-la sur le côté",
                    ],
                    ["N’essayez pas de la faire vomir", "Ne donnez ni lait, ni eau, ni rien sans avis médical"],
                ),
                _text(
                    "Swallowed poison",
                    [
                        "Unresponsiveness, trouble breathing, seizures, or a corrosive product swallowed (bleach, descaler)"
                    ],
                    [
                        "Call 198 or the National Poison Centre",
                        "Keep the container or medicine to know the product and the amount",
                        "If they become unresponsive but breathe: put them on their side",
                    ],
                    ["Do not try to make them vomit", "Do not give milk, water or anything without medical advice"],
                ),
            ),
            (
                True,
                _text(
                    "حادث مرور",
                    ["كل حادث فيه مصاب أو شخص عالق أو تسرب وقود"],
                    [
                        "احمِ نفسك: أركن بعيدًا، شغّل أضواء التنبيه، ارتدِ السترة العاكسة وضع المثلث",
                        "أطفئ محرك السيارة المتضررة إن أمكن",
                        "اتصل بـ198: المكان، عدد المصابين، حالتهم",
                        "تحدث إلى المصابين وأبقِهم ساكنين وغطّهم",
                    ],
                    [
                        "لا تُخرج المصاب من السيارة إلا لخطر مباشر (نار)",
                        "لا تنزع خوذة سائق الدراجة النارية",
                        "لا تدخّن قرب السيارات",
                    ],
                ),
                _text(
                    "Accident de la route",
                    ["Tout accident avec un blessé, une personne coincée ou une fuite de carburant"],
                    [
                        "Protégez-vous : garez-vous à distance, feux de détresse, gilet et triangle",
                        "Coupez le contact du véhicule accidenté si possible",
                        "Appelez le 198 : lieu, nombre de blessés, leur état",
                        "Parlez aux blessés, gardez-les immobiles et couverts",
                    ],
                    [
                        "Ne sortez pas un blessé du véhicule sauf danger immédiat (feu)",
                        "N’enlevez pas le casque d’un motard",
                        "Ne fumez pas près des véhicules",
                    ],
                ),
                _text(
                    "Road accident",
                    ["Any accident with an injured person, someone trapped, or leaking fuel"],
                    [
                        "Protect yourself: park away, hazard lights on, wear the vest and set the triangle",
                        "Turn off the ignition of the crashed vehicle if possible",
                        "Call 198: place, number of injured, their condition",
                        "Talk to the injured, keep them still and warm",
                    ],
                    [
                        "Do not move an injured person out of the vehicle unless there is immediate danger (fire)",
                        "Do not remove a motorcyclist's helmet",
                        "Do not smoke near the vehicles",
                    ],
                ),
            ),
        ],
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    last = bind.scalar(sa.text("SELECT coalesce(max(position), 0) FROM content.guide_topic")) or 0
    for n, (key, (icon, colour, title)) in enumerate(NEW_TOPICS.items(), start=1):
        bind.execute(
            sa.text(
                "INSERT INTO content.guide_topic (key, title, icon, colour, position) "
                "VALUES (:k, CAST(:t AS jsonb), :i, :c, :p) ON CONFLICT (key) DO NOTHING"
            ),
            {"k": key, "t": json.dumps(title, ensure_ascii=False), "i": icon, "c": colour, "p": last + n * 10},
        )
    for key, items in MORE:
        topic_id = bind.scalar(sa.text("SELECT id FROM content.guide_topic WHERE key = :k"), {"k": key})
        if topic_id is None:  # removed by an editor
            continue
        start = bind.scalar(
            sa.text("SELECT coalesce(max(position), -10) FROM content.guide_item WHERE topic_id = :t"), {"t": topic_id}
        )
        for n, (call, ar, fr, en) in enumerate(items, start=1):
            bind.execute(
                sa.text(
                    "INSERT INTO content.guide_item (topic_id, position, content, call_198) "
                    "VALUES (:t, :p, CAST(:c AS jsonb), :call)"
                ),
                {
                    "t": topic_id,
                    "p": start + n * 10,
                    "c": json.dumps({"ar": ar, "fr": fr, "en": en}, ensure_ascii=False),
                    "call": call,
                },
            )
    bind.execute(sa.text("UPDATE content.revision SET value = value + 1 WHERE name = 'emergency_guide'"))


def downgrade() -> None:
    bind = op.get_bind()
    titles = [fr["title"] for _, items in MORE for _, _, fr, _ in items]
    bind.execute(
        sa.text(
            "DELETE FROM content.guide_item WHERE version = 1 AND updated_by = 'system' "
            "AND content->'fr'->>'title' = ANY(:titles)"
        ),
        {"titles": titles},
    )
    for key in NEW_TOPICS:
        bind.execute(
            sa.text(
                "DELETE FROM content.guide_topic t WHERE key = :k AND version = 1 AND updated_by = 'system' "
                "AND NOT EXISTS (SELECT 1 FROM content.guide_item i WHERE i.topic_id = t.id)"
            ),
            {"k": key},
        )
    bind.execute(sa.text("UPDATE content.revision SET value = value + 1 WHERE name = 'emergency_guide'"))
