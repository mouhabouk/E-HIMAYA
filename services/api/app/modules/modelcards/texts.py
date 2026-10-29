# ruff: noqa: E501 (prose of the cards, wrapped by hand)
"""The words of the model cards, in the three languages of the dashboard (the same words go into the PDF)."""

from typing import Literal

Lang = Literal["ar", "fr", "en"]

CARDS: dict[str, dict[Lang, dict[str, str]]] = {
    "fire_smoke": {
        "ar": {
            "name": "كاشف النار والدخان",
            "use": "يقرأ صور البلاغات وبث الكاميرات والدرون، ويقترح «نار» أو «دخان» على المشغّل. لا يفتح تدخلا وحده: "
            "يتأكد التنبيه في 3 إطارات من 5، والمشغّل يقرّر.",
            "limits": "الدخان تلميح فقط (نحو 60٪ استرجاع). مشاهد تشبه النار (غروب، شموع، أضواء برتقالية) تخدعه في نحو "
            "40٪ من الإطارات. الحرائق البعيدة والمشاهد المغطاة بالدخان أو الضباب يفوّتها أكثر. صور الكاميرات الحرارية "
            "والليلية بالأشعة تحت الحمراء قليلة في التدريب.",
            "data": "مدرَّب على صور Open Images V7 (رخصة CC BY 2.0، تسميات بشرية)، وFireNET (MIT)، وFURG (CC0). "
            "التقييم على 383 صورة لم تُستعمل في التدريب ولا في المعايرة.",
        },
        "fr": {
            "name": "Détecteur de feu et de fumée",
            "use": "Lit les photos des signalements et les flux des caméras et drones, et suggère « feu » ou « fumée » à "
            "l'opérateur. N'ouvre jamais d'intervention seul : l'alerte doit se confirmer sur 3 images sur 5, et "
            "l'opérateur décide.",
            "limits": "La fumée n'est qu'un indice (rappel d'environ 60 %). Les scènes qui ressemblent à un feu "
            "(couchers de soleil, bougies, éclairages orangés) le trompent sur environ 40 % des images. Il manque plus "
            "souvent les feux lointains et les scènes voilées de fumée ou de brouillard. Peu d'images thermiques ou "
            "infrarouges de nuit à l'entraînement.",
            "data": "Entraîné sur Open Images V7 (CC BY 2.0, étiquettes humaines), FireNET (MIT) et FURG (CC0). "
            "Évalué sur 383 images jamais vues à l'entraînement ni à la calibration.",
        },
        "en": {
            "name": "Fire and smoke detector",
            "use": "Reads the photos of reports and the camera and drone streams, and suggests “fire” or “smoke” to the "
            "operator. Never opens an intervention by itself: the alert must hold in 3 frames out of 5, and the "
            "operator decides.",
            "limits": "Smoke is a hint only (about 60 % recall). Fire-like scenes (sunsets, candles, orange lights) "
            "fool it on about 40 % of frames. It misses distant fires and scenes veiled by smoke or fog more often. "
            "Few thermal or night infrared pictures in training.",
            "data": "Trained on Open Images V7 (CC BY 2.0, human labels), FireNET (MIT) and FURG (CC0). Evaluated on "
            "383 images never used for training or calibration.",
        },
    },
    "person": {
        "ar": {
            "name": "كاشف الأشخاص",
            "use": "يعدّ الأشخاص الظاهرين في صور البلاغات والبث، ليعرف المشغّل هل في المكان ناس. لا يتعرّف على "
            "الوجوه ولا يحفظ هوية أحد.",
            "limits": "نموذج COCO العام كما نُشر، لم نعد تدريبه. يفوّت الأشخاص الصغار جدا في الصورة وفي الظلام "
            "وخلف الدخان.",
            "data": "أوزان YOLOX-Tiny الرسمية المدرَّبة على COCO 2017. التقييم على 100 صورة من Open Images.",
        },
        "fr": {
            "name": "Détecteur de personnes",
            "use": "Compte les personnes visibles sur les photos et les flux, pour que l'opérateur sache s'il y a du "
            "monde sur place. Ne reconnaît aucun visage et ne garde aucune identité.",
            "limits": "Modèle COCO public tel que publié, non réentraîné. Manque les personnes très petites dans "
            "l'image, dans le noir ou derrière la fumée.",
            "data": "Poids officiels YOLOX-Tiny entraînés sur COCO 2017. Évalué sur 100 images Open Images.",
        },
        "en": {
            "name": "Person detector",
            "use": "Counts the people visible in photos and streams, so the operator knows whether people are on site. "
            "Recognises no face and keeps no identity.",
            "limits": "The public COCO model as published, not retrained. Misses very small people in the picture, "
            "in the dark or behind smoke.",
            "data": "Official YOLOX-Tiny weights trained on COCO 2017. Evaluated on 100 Open Images pictures.",
        },
    },
    "report_reading": {
        "ar": {
            "name": "القراءة المهيكلة للبلاغ",
            "use": "يقرأ نص البلاغ (أو تفريغه الصوتي) ويقترح نوع الحادث، وهل الأرواح في خطر، وعدد المصابين والمخاطر "
            "وملخصا قصيرا. اقتراح يظهر بوسم الذكاء الاصطناعي، ولا يخفّض أولوية بلاغ أبدا.",
            "limits": "نموذج لغوي صغير محلي: قد يخطئ في الدارجة وخاصة المكتوبة بالحروف اللاتينية، وقد يفوّت خطرا "
            "على الأرواح لم يُذكر صراحة. حين يفشل الجواب في المخطط يبقى البلاغ بالقواعد وحدها.",
            "data": "نموذج Qwen3 (رخصة Apache-2.0) يعمل في خوادم الديوان عبر Ollama، دون أي إرسال إلى الخارج. "
            "التقييم على مجموعة معلنة من 60 بلاغا [SIM] بالفصحى والدارجة والفرنسية.",
        },
        "fr": {
            "name": "Lecture structurée du signalement",
            "use": "Lit le texte du signalement (ou sa transcription) et suggère le type d'incident, si des vies sont en "
            "danger, le nombre de blessés, les dangers et un court résumé. Suggestion marquée IA, qui ne baisse jamais "
            "la priorité d'un signalement.",
            "limits": "Petit modèle de langue local : il peut se tromper en derja, surtout écrite en lettres latines, et "
            "manquer un danger pour les vies qui n'est pas dit clairement. Quand la réponse ne respecte pas le schéma, "
            "le signalement garde les seules règles.",
            "data": "Modèle Qwen3 (Apache-2.0) exécuté sur les serveurs de l'Office via Ollama, sans aucun envoi à "
            "l'extérieur. Évalué sur un jeu déclaré de 60 signalements [SIM] en arabe standard, derja et français.",
        },
        "en": {
            "name": "Structured reading of a report",
            "use": "Reads the text of a report (or its transcript) and suggests the type of incident, whether lives are "
            "at risk, the injured, the hazards and a short summary. An AI-labelled suggestion that never lowers a "
            "report's priority.",
            "limits": "A small local language model: it can be wrong in Derja, above all written in Latin letters, and "
            "miss a danger to lives that is not said plainly. When its answer fails the schema, the report keeps the "
            "rules alone.",
            "data": "Qwen3 (Apache-2.0) running on the Office's servers through Ollama, nothing sent outside. Evaluated "
            "on a declared set of 60 [SIM] reports in Standard Arabic, Derja and French.",
        },
    },
    "written_summary": {
        "ar": {
            "name": "الملخص المكتوب",
            "use": "يكتب في نافذة أصحاب القرار ملخصا استشاريا لنتيجة بحث أو مقارنة، من الأرقام المجمَّعة المعروضة وحدها.",
            "limits": "إن ذكر رقما غير موجود في الأرقام المعطاة يُرفض الملخص ولا يُعرض. لا يرى أي بلاغ ولا اسم، "
            "ولا يعرف إلا ما في الجدول.",
            "data": "النموذج اللغوي المحلي نفسه (Qwen3، Apache-2.0). لا مجموعة تقييم: يُعدّ ما رُفض لأنه ذكر رقما "
            "غير موجود.",
        },
        "fr": {
            "name": "Résumé écrit",
            "use": "Écrit dans la fenêtre des décideurs un résumé consultatif d'une recherche ou d'une comparaison, à "
            "partir des seuls agrégats affichés.",
            "limits": "S'il cite un chiffre absent des chiffres fournis, le résumé est refusé et n'est pas affiché. Il "
            "ne voit aucun signalement ni aucun nom, seulement le tableau.",
            "data": "Le même modèle de langue local (Qwen3, Apache-2.0). Pas de jeu d'évaluation : on compte les résumés "
            "refusés pour un chiffre inventé.",
        },
        "en": {
            "name": "Written summary",
            "use": "Writes, in the decision makers' window, an advisory summary of a search or a comparison, from the "
            "aggregates shown only.",
            "limits": "If it cites a figure that is not among the figures given, the summary is refused and not shown. "
            "It sees no report and no name, only the table.",
            "data": "The same local language model (Qwen3, Apache-2.0). No evaluation set: the summaries refused for an "
            "invented figure are counted.",
        },
    },
    "plan_reading": {
        "ar": {
            "name": "قراءة المخطط",
            "use": "يقرأ مخطط التدخل (PDF) ويقترح قائمة مهام، لكل مهمة رقم صفحة واقتباس. يراجعها رئيس القاعة مهمة "
            "مهمة قبل اعتمادها.",
            "limits": "قد يفوّت مهمة أو يصوغها بغير دقة. الاقتباس يُبحث عنه في صفحته، فإن لم يوجد يظهر ذلك للمراجع. "
            "المخططات المصوَّرة بلا نص لا تُقرأ.",
            "data": "النموذج اللغوي المحلي نفسه (Qwen3، Apache-2.0). الأرقام من المراجعة الفعلية: ما قُبل وما عُدّل "
            "وما حُذف.",
        },
        "fr": {
            "name": "Lecture du plan",
            "use": "Lit le plan d'intervention (PDF) et suggère une liste de tâches, chacune avec sa page et une "
            "citation. Le chef de salle les revoit une à une avant d'approuver.",
            "limits": "Peut manquer une tâche ou la formuler mal. La citation est cherchée sur sa page, et le réviseur "
            "voit si elle n'y est pas. Les plans scannés sans texte ne se lisent pas.",
            "data": "Le même modèle de langue local (Qwen3, Apache-2.0). Les chiffres viennent de la revue réelle : "
            "tâches acceptées, modifiées, supprimées.",
        },
        "en": {
            "name": "Plan reading",
            "use": "Reads the intervention plan (PDF) and suggests a task list, each task with its page and a quote. "
            "The room manager reviews them one by one before approving.",
            "limits": "May miss a task or word it badly. The quote is looked for on its page, and the reviewer sees "
            "when it is not there. Scanned plans without text cannot be read.",
            "data": "The same local language model (Qwen3, Apache-2.0). The figures come from the actual review: tasks "
            "accepted, edited, deleted.",
        },
    },
    "commander": {
        "ar": {
            "name": "مساعد القائد",
            "use": "يقترح على القائد قرارات مرقّمة ومعلّلة لكل حادثة، ويقرأ ما يكتبه أو يمليه من أوامر (فصحى أو دارجة أو "
            "فرنسية) ليحوّلها إلى بطاقة قرار. القائد يعتمد أو يعدّل أو يرفض، والاعتماد يفتح المسار المعتاد ولا ينفّذ "
            "شيئا.",
            "limits": "قد يخطئ في قراءة أمر بكلمات لم يرها: تظهر القراءة على البطاقة ليصحّحها القائد. أرقام القراءة من "
            "نصوص [SIM] كتبت للمشروع، لا من أوامر حقيقية. ذاكرة القرارات تعدّ ما قرّره القادة ولا تحكم على صوابه "
            "قبل ربطه بنتيجة التدخل (AI5c).",
            "data": "النموذج اللغوي المحلي (Qwen3، Apache-2.0) ومعجم الدارجة والفصحى والفرنسية للوسائل والأعداد. "
            "قراءة الأوامر تقاس على 60 نصا محجوزا لم يُضبط عليها شيء. قرارات القادة تحفظ دون أسماء المبلّغين ولا "
            "أرقامهم.",
        },
        "fr": {
            "name": "Assistant du commandant",
            "use": "Propose au commandant des décisions numérotées et justifiées pour chaque incident, et lit les ordres "
            "qu'il tape ou dicte (arabe, derja ou français) pour en faire une carte de décision. Le commandant adopte, "
            "modifie ou rejette ; adopter ouvre le circuit habituel et n'exécute rien.",
            "limits": "Peut mal lire un ordre aux mots inconnus : la lecture est affichée sur la carte pour correction. "
            "Les chiffres de lecture viennent de textes [SIM] écrits pour le projet, pas d'ordres réels. La mémoire "
            "compte ce que les commandants ont décidé sans juger du résultat avant le lien au bilan (AI5c).",
            "data": "Le modèle de langue local (Qwen3, Apache-2.0) et un lexique derja, arabe et français des moyens et "
            "des nombres. La lecture est mesurée sur 60 textes réservés, jamais utilisés pour le réglage. Les "
            "décisions sont gardées sans nom ni numéro des signalants.",
        },
        "en": {
            "name": "Commander's assistant",
            "use": "Proposes numbered, reasoned decisions to the commander for each incident, and reads the orders they "
            "type or dictate (Arabic, Derja or French) into a decision card. The commander adopts, modifies or "
            "rejects; adopting opens the usual flow and executes nothing.",
            "limits": "May misread an order with words it has not seen: the reading is shown on the card to correct. "
            "The reading figures come from [SIM] texts written for the project, not from real orders. The memory "
            "counts what commanders decided and does not judge it before the link to the outcome (AI5c).",
            "data": "The local language model (Qwen3, Apache-2.0) and a Derja, Arabic and French lexicon of resources "
            "and numbers. The reading is measured on 60 held-out texts never used for tuning. Decisions are kept "
            "without reporters' names or numbers.",
        },
    },
    "drowning": {
        "ar": {
            "name": "نموذج خطر الغرق (في الظل)",
            "use": "يحسب كل يوم احتمال الغرق في كل شاطئ من المعطيات نفسها التي تستعملها القواعد المعلنة، ويُعرض "
            "للأعوان بجانب مستوى القاعدة للمقارنة. لا يُنشر للمواطن، ولا يفتح تنبيها، ولا يغيّر مستوى القاعدة.",
            "limits": "مدرَّب على أيام [SIM] من مسار معلن، لا على حوادث حقيقية: أرقامه تقيس قدرته على تعلّم ذلك "
            "المسار، لا الواقع. يبقى في الظل إلى أن تعتمده اللجنة (AI-01).",
            "data": "انحدار لوجستي (scikit-learn، رخصة BSD-3) على 30000 يوم-شاطئ [SIM]، ويُقاس على 10000 يوم أخرى. "
            "يُحفظ معاملات فقط، دون أي ملف تنفيذي.",
        },
        "fr": {
            "name": "Modèle de risque de noyade (en ombre)",
            "use": "Calcule chaque jour la probabilité de noyade sur chaque plage à partir des mêmes données que les "
            "règles déclarées, et l'affiche aux agents à côté du niveau de la règle, pour comparer. Jamais publié au "
            "citoyen, n'ouvre aucune alerte et ne change pas le niveau de la règle.",
            "limits": "Entraîné sur des journées [SIM] tirées d'un processus déclaré, pas sur des noyades réelles : ses "
            "chiffres mesurent sa capacité à apprendre ce processus, pas la réalité. Reste en ombre jusqu'à "
            "l'approbation du comité (AI-01).",
            "data": "Régression logistique (scikit-learn, BSD-3) sur 30 000 journées-plage [SIM], mesurée sur 10 000 "
            "autres. Seuls des coefficients sont gardés, aucun fichier exécutable.",
        },
        "en": {
            "name": "Drowning risk model (shadow)",
            "use": "Computes each day the chance of a drowning on each beach from the same inputs as the declared rules, "
            "and shows it to staff beside the rule's level, for comparison. Never published to citizens, opens no "
            "alert and never changes the rule's level.",
            "limits": "Trained on [SIM] days drawn from a declared process, not on real drownings: its figures measure "
            "how well it learns that process, not reality. Stays in shadow until the committee approves it (AI-01).",
            "data": "Logistic regression (scikit-learn, BSD-3) on 30,000 [SIM] beach-days, measured on 10,000 others. "
            "Only coefficients are kept, no executable file.",
        },
    },
}

LABELS: dict[Lang, dict[str, str]] = {
    "ar": {
        "title": "بطاقة النموذج",
        "use": "الاستعمال",
        "limits": "الحدود",
        "data": "البيانات والرخص",
        "version": "النسخة",
        "licence": "الرخصة",
        "measures": "الأرقام",
        "thresholds": "العتبات",
        "decision": "اعتماد اللجنة (AI-01)",
        "measured_on": "قيست في",
        "small": "عينة صغيرة: الرقم لا يقول الكثير",
        "not_measured": "لم يُقس بعد",
        "status.approved": "معتمد",
        "status.pending": "ينتظر اعتماد اللجنة",
        "status.changed": "تغيّر منذ اعتماده: ينتظر اعتمادا جديدا",
        "status.withdrawn": "سُحب الاعتماد",
        "status.shadow": "في الظل",
        "m.overall": "النتائج على مجموعة التقييم",
        "m.conditions_fire": "النار التي فاتته حسب الظروف (عند 0.45)",
        "m.conditions_smoke": "الدخان الذي فاته حسب الظروف (عند 0.45)",
        "m.hard_negatives": "إنذارات خاطئة على مشاهد تشبه النار",
        "m.reports": "ما فاته حسب لغة البلاغ",
        "m.summary": "الملخصات في آخر 90 يوما",
        "m.plan": "مراجعة المهام المقترحة",
        "m.drowning": "مقارنة بالقواعد على أيام [SIM] أخرى",
        "m.shadow": "مقارنة يوما بيوم على الشواطئ (آخر 30 يوما)",
        "c.label": "الفئة",
        "c.threshold": "العتبة",
        "c.precision": "الدقة",
        "c.recall": "الاسترجاع",
        "c.condition": "الظرف",
        "c.images": "الصور",
        "c.missed": "فاته",
        "c.interval": "مجال الثقة 95٪",
        "c.variety": "اللغة",
        "c.reports": "البلاغات",
        "c.lives_missed": "خطر على الأرواح فاته",
        "c.category_missed": "نوع لم يُصحَّح من «أخرى»",
        "c.invalid": "جواب مرفوض",
        "c.value": "القيمة",
        "c.model": "النموذج",
        "c.rules": "القواعد",
        "c.measure": "المقياس",
        "c.day": "اليوم",
        "c.same": "المستوى نفسه",
        "c.higher": "النموذج أعلى",
        "c.lower": "النموذج أدنى",
        "c.beaches": "الشواطئ",
        "r.fire": "نار",
        "r.smoke": "دخان",
        "r.person": "شخص",
        "r.light.day": "نهار",
        "r.light.night": "ليل",
        "r.visibility.clear": "رؤية صافية",
        "r.visibility.smoke_or_fog": "دخان أو ضباب",
        "r.distance.near": "قريب",
        "r.distance.far": "بعيد",
        "r.setting.indoor": "داخل",
        "r.setting.outdoor": "خارج",
        "r.all": "الكل",
        "r.ar_msa": "عربية فصحى",
        "r.derja": "دارجة",
        "r.ar_derja": "دارجة بالحروف العربية",
        "r.ar_latn": "دارجة بالحروف اللاتينية",
        "r.fr": "فرنسية",
        "r.supported": "عُرض",
        "r.refused": "رُفض لرقم غير موجود",
        "r.suggested": "مهام مقترحة",
        "r.accepted": "قُبلت كما هي",
        "r.edited": "عُدّلت",
        "r.deleted": "حُذفت",
        "r.waiting": "تنتظر المراجعة",
        "r.added": "أضافها المراجع بيده",
        "r.quote_found": "اقتباس وُجد في صفحته",
        "r.auc": "مساحة تحت المنحنى (AUC)",
        "r.missed_rate": "أيام غرق صنّفها أخضر",
        "r.flagged": "أيام صنّفها أصفر أو أحمر",
        "r.agreement": "اتفاق في المستوى",
        "t.vision_min_confidence": "أدنى ثقة لاقتراح",
        "t.vision_alert_confidence": "ثقة التنبيه (في 3 إطارات من 5)",
        "t.suggestion_min_confidence": "أدنى ثقة لرفع خطورة البلاغ",
        "t.yellow": "احتمال المستوى الأصفر",
        "t.red": "احتمال المستوى الأحمر",
        "t.plan_reading": "قراءة المخطط مفعّلة",
        "m.orders": "قراءة أوامر القائد (60 نصا محجوزا)",
        "m.commander": "قرارات القادة في آخر 90 يوما",
        "c.reader": "القارئ",
        "c.texts": "النصوص",
        "c.exact": "بطاقة صحيحة دون تعديل",
        "c.action": "الإجراء صحيح",
        "r.reader.rules": "المعجم وحده",
        "r.reader.model": "النموذج وحده",
        "r.reader.combined": "المعجم والنموذج (المعتمد)",
        "r.proposed": "اقتراحات عُرضت",
        "r.adopted": "اعتُمدت",
        "r.modified": "اعتُمدت معدّلة",
        "r.rejected": "رُفضت",
        "r.expired": "تجاوزها الوضع",
        "r.orders": "منها أوامر كتبها القادة",
        "t.commander": "مساعد القائد مفعّل",
        "t.none": "لا عتبة: يُرفض الملخص إن ذكر رقما غير موجود",
        "d.approved": "اعتمد",
        "d.withdrawn": "سحب الاعتماد",
        "d.none": "لم تتخذ اللجنة قرارا بعد",
        "d.reference": "المرجع",
        "sim": "[SIM] معطيات تجريبية",
        "generated": "صدرت في",
    },
    "fr": {
        "title": "Fiche du modèle",
        "use": "Usage",
        "limits": "Limites",
        "data": "Données et licences",
        "version": "Version",
        "licence": "Licence",
        "measures": "Chiffres",
        "thresholds": "Seuils",
        "decision": "Approbation du comité (AI-01)",
        "measured_on": "Mesuré le",
        "small": "Petit échantillon : le chiffre dit peu",
        "not_measured": "Pas encore mesuré",
        "status.approved": "Approuvé",
        "status.pending": "En attente du comité",
        "status.changed": "Modifié depuis l'approbation : nouvelle approbation attendue",
        "status.withdrawn": "Approbation retirée",
        "status.shadow": "En ombre",
        "m.overall": "Résultats sur le jeu d'évaluation",
        "m.conditions_fire": "Feux manqués selon les conditions (à 0,45)",
        "m.conditions_smoke": "Fumées manquées selon les conditions (à 0,45)",
        "m.hard_negatives": "Fausses alertes sur des scènes qui ressemblent à un feu",
        "m.reports": "Manqués selon la langue du signalement",
        "m.summary": "Résumés des 90 derniers jours",
        "m.plan": "Revue des tâches suggérées",
        "m.drowning": "Comparaison avec les règles sur d'autres journées [SIM]",
        "m.shadow": "Comparaison jour par jour sur les plages (30 derniers jours)",
        "c.label": "Classe",
        "c.threshold": "Seuil",
        "c.precision": "Précision",
        "c.recall": "Rappel",
        "c.condition": "Condition",
        "c.images": "Images",
        "c.missed": "Manqués",
        "c.interval": "Intervalle à 95 %",
        "c.variety": "Langue",
        "c.reports": "Signalements",
        "c.lives_missed": "Danger pour les vies manqué",
        "c.category_missed": "Type non corrigé depuis « autre »",
        "c.invalid": "Réponse rejetée",
        "c.value": "Valeur",
        "c.model": "Modèle",
        "c.rules": "Règles",
        "c.measure": "Mesure",
        "c.day": "Jour",
        "c.same": "Même niveau",
        "c.higher": "Modèle plus haut",
        "c.lower": "Modèle plus bas",
        "c.beaches": "Plages",
        "r.fire": "Feu",
        "r.smoke": "Fumée",
        "r.person": "Personne",
        "r.light.day": "Jour",
        "r.light.night": "Nuit",
        "r.visibility.clear": "Visibilité claire",
        "r.visibility.smoke_or_fog": "Fumée ou brouillard",
        "r.distance.near": "Proche",
        "r.distance.far": "Lointain",
        "r.setting.indoor": "Intérieur",
        "r.setting.outdoor": "Extérieur",
        "r.all": "Tous",
        "r.ar_msa": "Arabe standard",
        "r.derja": "Derja",
        "r.ar_derja": "Derja en lettres arabes",
        "r.ar_latn": "Derja en lettres latines",
        "r.fr": "Français",
        "r.supported": "Affichés",
        "r.refused": "Refusés pour un chiffre absent",
        "r.suggested": "Tâches suggérées",
        "r.accepted": "Acceptées telles quelles",
        "r.edited": "Modifiées",
        "r.deleted": "Supprimées",
        "r.waiting": "En attente de revue",
        "r.added": "Ajoutées à la main",
        "r.quote_found": "Citation trouvée sur sa page",
        "r.auc": "Aire sous la courbe (AUC)",
        "r.missed_rate": "Journées de noyade classées vertes",
        "r.flagged": "Journées classées jaune ou rouge",
        "r.agreement": "Même niveau",
        "t.vision_min_confidence": "Confiance minimale d'une suggestion",
        "t.vision_alert_confidence": "Confiance d'alerte (sur 3 images sur 5)",
        "t.suggestion_min_confidence": "Confiance minimale pour relever la gravité",
        "t.yellow": "Probabilité du niveau jaune",
        "t.red": "Probabilité du niveau rouge",
        "t.plan_reading": "Lecture du plan activée",
        "m.orders": "Lecture des ordres du commandant (60 textes réservés)",
        "m.commander": "Décisions des commandants sur 90 jours",
        "c.reader": "Lecteur",
        "c.texts": "Textes",
        "c.exact": "Carte juste sans retouche",
        "c.action": "Action juste",
        "r.reader.rules": "Lexique seul",
        "r.reader.model": "Modèle seul",
        "r.reader.combined": "Lexique et modèle (retenu)",
        "r.proposed": "Propositions affichées",
        "r.adopted": "Adoptées",
        "r.modified": "Adoptées modifiées",
        "r.rejected": "Rejetées",
        "r.expired": "Dépassées par la situation",
        "r.orders": "dont ordres tapés par les commandants",
        "t.commander": "Assistant du commandant activé",
        "t.none": "Pas de seuil : le résumé est refusé s'il cite un chiffre absent",
        "d.approved": "Approuvé",
        "d.withdrawn": "Approbation retirée",
        "d.none": "Le comité n'a pas encore décidé",
        "d.reference": "Référence",
        "sim": "[SIM] données simulées",
        "generated": "Édité le",
    },
    "en": {
        "title": "Model card",
        "use": "Use",
        "limits": "Limits",
        "data": "Data and licences",
        "version": "Version",
        "licence": "Licence",
        "measures": "Figures",
        "thresholds": "Thresholds",
        "decision": "Committee approval (AI-01)",
        "measured_on": "Measured on",
        "small": "Small sample: the figure says little",
        "not_measured": "Not measured yet",
        "status.approved": "Approved",
        "status.pending": "Waiting for the committee",
        "status.changed": "Changed since approved: waiting for a new approval",
        "status.withdrawn": "Approval withdrawn",
        "status.shadow": "In shadow",
        "m.overall": "Results on the evaluation set",
        "m.conditions_fire": "Fires missed by condition (at 0.45)",
        "m.conditions_smoke": "Smoke missed by condition (at 0.45)",
        "m.hard_negatives": "False alarms on fire-like scenes",
        "m.reports": "Misses by language of the report",
        "m.summary": "Summaries of the last 90 days",
        "m.plan": "Review of the suggested tasks",
        "m.drowning": "Against the rules on other [SIM] days",
        "m.shadow": "Day by day on the beaches (last 30 days)",
        "c.label": "Class",
        "c.threshold": "Threshold",
        "c.precision": "Precision",
        "c.recall": "Recall",
        "c.condition": "Condition",
        "c.images": "Images",
        "c.missed": "Missed",
        "c.interval": "95 % interval",
        "c.variety": "Language",
        "c.reports": "Reports",
        "c.lives_missed": "Danger to lives missed",
        "c.category_missed": "Type not corrected from “other”",
        "c.invalid": "Answer rejected",
        "c.value": "Value",
        "c.model": "Model",
        "c.rules": "Rules",
        "c.measure": "Measure",
        "c.day": "Day",
        "c.same": "Same level",
        "c.higher": "Model higher",
        "c.lower": "Model lower",
        "c.beaches": "Beaches",
        "r.fire": "Fire",
        "r.smoke": "Smoke",
        "r.person": "Person",
        "r.light.day": "Day",
        "r.light.night": "Night",
        "r.visibility.clear": "Clear view",
        "r.visibility.smoke_or_fog": "Smoke or fog",
        "r.distance.near": "Near",
        "r.distance.far": "Far",
        "r.setting.indoor": "Indoor",
        "r.setting.outdoor": "Outdoor",
        "r.all": "All",
        "r.ar_msa": "Standard Arabic",
        "r.derja": "Derja",
        "r.ar_derja": "Derja in Arabic letters",
        "r.ar_latn": "Derja in Latin letters",
        "r.fr": "French",
        "r.supported": "Shown",
        "r.refused": "Refused for a figure not given",
        "r.suggested": "Suggested tasks",
        "r.accepted": "Accepted as they were",
        "r.edited": "Edited",
        "r.deleted": "Deleted",
        "r.waiting": "Waiting for review",
        "r.added": "Added by hand",
        "r.quote_found": "Quote found on its page",
        "r.auc": "Area under the curve (AUC)",
        "r.missed_rate": "Drowning days rated green",
        "r.flagged": "Days rated yellow or red",
        "r.agreement": "Same level",
        "t.vision_min_confidence": "Lowest confidence of a suggestion",
        "t.vision_alert_confidence": "Alert confidence (in 3 frames out of 5)",
        "t.suggestion_min_confidence": "Lowest confidence to raise a report's severity",
        "t.yellow": "Probability of the yellow level",
        "t.red": "Probability of the red level",
        "t.plan_reading": "Plan reading switched on",
        "m.orders": "Reading of the commander's orders (60 held-out texts)",
        "m.commander": "Commanders' decisions over 90 days",
        "c.reader": "Reader",
        "c.texts": "Texts",
        "c.exact": "Card right without edit",
        "c.action": "Action right",
        "r.reader.rules": "Lexicon alone",
        "r.reader.model": "Model alone",
        "r.reader.combined": "Lexicon and model (used)",
        "r.proposed": "Proposals shown",
        "r.adopted": "Adopted",
        "r.modified": "Adopted modified",
        "r.rejected": "Rejected",
        "r.expired": "Overtaken by the situation",
        "r.orders": "of which orders typed by commanders",
        "t.commander": "Commander's assistant switched on",
        "t.none": "No threshold: the summary is refused if it cites a figure not given",
        "d.approved": "Approved",
        "d.withdrawn": "Approval withdrawn",
        "d.none": "The committee has not decided yet",
        "d.reference": "Reference",
        "sim": "[SIM] simulated data",
        "generated": "Issued on",
    },
}
