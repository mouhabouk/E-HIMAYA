"""The screens of the public portal, the citizen app and the staff app for the flowchart atlas (Yamen, 2026-11-13).

One entry per screen, in Arabic: where the user comes from, what they do there step by step, where they go next, who
opens it, and what it is for. The screenshot, its regions and the API requests the screen sent while it opened come
from the capture (scripts/atlas/capture_portal.mjs, apps/mobile/test/atlas); the tables behind each request from the
API's own routes (scripts/ui_reference/backend_dump.py). Keep each text short: it is read on a card.

A step is (kind, text, region): kind is "do" (an action), "in" (an entry), "ask" (a choice) or "see" (what the
screen shows); region is a few words of the label of the region the box points at on the screenshot, or None.
"from" and "next" are (screen id, how): the button or event that leads there.
"""

SURFACES = {
    "dashboard": "لوحة القيادة",
    "portal": "بوابة المؤسسات",
    "citizen": "تطبيق المواطن",
    "staff": "تطبيق الأعوان",
}

# Groups of each surface, in order (the sections of the app as the user meets them).
GROUPS = {
    "portal": {"public": "الصفحات العامة", "orgs": "فضاء المؤسسة"},
    "citizen": {"main": "الرئيسية والتبويبات", "report": "التبليغ"},
    "staff": {"start": "الدخول والمناوبة", "mission": "المهمة"},
}

WHO = {
    "visitor": "زائر دون حساب",
    "citizen": "مواطن بحساب",
    "org_admin": "مسؤول المؤسسة",
    "org_member": "عضو في المؤسسة",
    "anonymous": "مواطن دون حساب (مفتاح الجهاز)",
    "registered": "مواطن بحساب",
    "agent": "عون في المناوبة",
    "team_leader": "رئيس الفريق",
    "org_auditor": "مفتش مكتب الوقاية",
    "inspector": "مفتش التفقدات الدورية",
}

SCREENS: list[dict] = [
    # ── the public portal ──────────────────────────────────────────────────────────────────────────────────────────
    {
        "id": "p-home", "surface": "portal", "group": "public", "route": "/", "title": "الصفحة الأولى للبوابة",
        "page": "apps/portal/src/pages/LandingPage.tsx", "who": ["visitor", "citizen"],
        "purpose": "تعريف البوابة: تسجيل المؤسسة لدى الحماية المدنية، التحقق من شهادة سلامة، وأرقام الطوارئ.",
        "value": "باب واحد للمؤسسات وللعموم: تسجيل، تحقق من شهادة، ونداء الطوارئ دون حساب.",
        "from": [(None, "رابط البوابة أو رمز QR على شهادة")],
        "steps": [
            ("see", "يقرأ ما تقدمه البوابة", "بوابة المؤسسات"),
            ("ask", "له حساب؟", "تسجيل الدخول"),
            ("in", "أو يكتب رمز شهادة للتحقق منها", "رمز الشهادة"),
            ("see", "أرقام الطوارئ 198 و190 و197 و193", "في حالة الطوارئ"),
        ],
        "next": [("p-orgs-mine", "زر «تسجيل الدخول» ثم Keycloak"), ("p-verify", "زر «تحقّق»")],
    },
    {
        "id": "p-org-overview", "surface": "portal", "group": "orgs", "route": "/orgs/:orgId", "title": "نظرة عامة على المؤسسة",
        "page": "apps/portal/src/pages/org/OverviewTab.tsx", "who": ["org_admin", "org_member"], "signedIn": True,
        "purpose": "لوحة المؤسسة: حالة التسجيل، رسائل المكتب، التصنيف المحسوب، اكتمال ملف السلامة والتنبيهات.",
        "value": "المؤسسة تعرف في نظرة ما ينقص ملفها وما يطلبه المكتب منها قبل أي زيارة.",
        "from": [("p-orgs-mine", "اختيار المؤسسة من «مؤسساتي»"), ("p-org-card", "تبويب «نظرة عامة»")],
        "steps": [
            ("see", "حالة التسجيل: في انتظار الدراسة أو مفعّلة", "في انتظار الدراسة"),
            ("see", "رسائل مكتب الوقاية", "رسائل المكتب"),
            ("see", "التصنيف يحسبه النظام من البطاقة", "التصنيف"),
            ("do", "يستكمل العناصر الناقصة من ملف السلامة", "اكتمال ملف السلامة"),
            ("ask", "أي تبويب؟ البطاقة، الفريق، المواد الخطرة…", "نظرة عامة"),
        ],
        "next": [("p-org-card", "تبويب «البطاقة» أو رابط «استكمال»")],
    },
    {
        "id": "p-org-card", "surface": "portal", "group": "orgs", "route": "/orgs/:orgId/card", "title": "بطاقة المؤسسة",
        "page": "apps/portal/src/pages/org/CardTab.tsx", "who": ["org_admin"], "signedIn": True,
        "purpose": "بطاقة التعريف: الهوية والمعرّف، البناية وطاقة الاستيعاب، الموقع على الخريطة، المسؤول ووسائل الاتصال.",
        "value": "معطيات المؤسسة الصحيحة تصل إلى القاعة قبل الحادث: الموقع، الطاقة، المسؤول.",
        "from": [("p-org-overview", "تبويب «البطاقة» أو «استكمال»")],
        "steps": [
            ("in", "الهوية والمعرّف (RNE أو المعرف الجبائي)", "الهوية والمعرّف"),
            ("in", "البناية: الطوابق والارتفاع وطاقة الاستيعاب", "البناية وطاقة الاستيعاب"),
            ("do", "يضبط الموقع على الخريطة", "الخريطة"),
            ("in", "المسؤول ووسائل الاتصال", "المسؤول ووسائل الاتصال"),
            ("do", "حفظ: تغيير جوهري يعيد الملف إلى الدراسة", "حفظ"),
        ],
        "next": [("p-org-overview", "بعد الحفظ، تبويب «نظرة عامة»")],
    },
    # ── the citizen app ────────────────────────────────────────────────────────────────────────────────────────────
    {
        "id": "c-home", "surface": "citizen", "group": "main", "route": "/home", "title": "الرئيسية",
        "page": "apps/mobile/lib/features/home/home_screen.dart", "who": ["anonymous", "registered"],
        "purpose": "أول ما يراه المواطن: زر النجدة، التبليغ عن حادث، أرقام الطوارئ دون إنترنت، والطقس قربه.",
        "value": "من فتح التطبيق إلى نداء النجدة في نقرتين، حتى دون حساب ودون شبكة.",
        "from": [(None, "فتح التطبيق بعد الميثاق والترحيب"), ("c-report-queued", "زر «العودة إلى الرئيسية»")],
        "steps": [
            ("see", "حالة تحديد الموقع", "الموقع مفعّل"),
            ("do", "نقرتان أو ضغطة مطوّلة على «نجدة»: نداء بالموقع", "نجدة"),
            ("do", "«أبلغ عن حادث»: صورة أو صوت أو نص", "أبلغ عن حادث"),
            ("do", "أرقام الطوارئ: اتصال مباشر بالشريحة", "أرقام الطوارئ"),
            ("ask", "أي تبويب؟ الرئيسية، بلاغاتي، الإعدادات", "شريط التنقل السفلي"),
        ],
        "next": [("c-report-new", "بطاقة «أبلغ عن حادث»"), ("c-report-queued", "بعد نداء النجدة")],
    },
    {
        "id": "c-report-new", "surface": "citizen", "group": "report", "route": "/report/new", "title": "اختيار نوع البلاغ",
        "page": "apps/mobile/lib/features/report/category_screen.dart", "who": ["anonymous", "registered"],
        "purpose": "شبكة أصناف الحوادث: حريق، فيضان، حادث مرور، غرق، انزلاق أرضي، تسرّب، حالة صحية، أخرى.",
        "value": "صنف واضح من البداية يوجّه البلاغ إلى الفريق المناسب ويختار الأسئلة الصحيحة.",
        "from": [("c-home", "بطاقة «أبلغ عن حادث»")],
        "steps": [
            ("ask", "ما نوع الحادث؟", "حريق"),
            ("do", "حادث مرور أو غرق…", "حادث مرور"),
            ("do", "أخرى إن لم يجد الصنف", "أخرى"),
        ],
        "next": [("c-report-fire", "اختيار صنف (مثلا «حريق»)")],
    },
    {
        "id": "c-report-fire", "surface": "citizen", "group": "report", "route": "/report/new/:category", "title": "بلاغ جديد",
        "page": "apps/mobile/lib/features/report/new_report_screen.dart", "who": ["anonymous", "registered"],
        "purpose": "استمارة البلاغ: الموقع آليا مع دبوس على الخريطة، وصف اختياري، صور وفيديو، ورسالة صوتية.",
        "value": "البلاغ يُحفظ في الهاتف فورا برمز مؤقت ويُرسل عند توفر الشبكة: لا بلاغ يضيع.",
        "from": [("c-report-new", "اختيار الصنف")],
        "steps": [
            ("see", "الموقع يُحدَّد آليا، ويُضبط الدبوس عند الحاجة", None),
            ("in", "وصف اختياري: ماذا ترى؟ هل هناك مصابون؟", "الوصف"),
            ("do", "التقاط صورة أو اختيارها من المعرض", "التقاط صورة"),
            ("do", "رسالة صوتية حتى 5 دقائق", "رسالة صوتية"),
            ("do", "إرسال البلاغ: يدخل الطابور المشفّر برمز TMP", "إرسال البلاغ"),
        ],
        "next": [("c-report-queued", "زر «إرسال البلاغ»")],
    },
    # ── the staff app ──────────────────────────────────────────────────────────────────────────────────────────────
    {
        "id": "s-shift", "surface": "staff", "group": "start", "route": "ShiftScreen", "title": "بداية المناوبة",
        "page": "apps/mobile/lib/staff/screens/shift_screen.dart", "who": ["agent", "team_leader"],
        "purpose": "العون يختار الوسيلة التي يركبها ويعدّ أفراد الطاقم ثم يبدأ المناوبة.",
        "value": "القاعة تعرف من في الخدمة وعلى أي عربة منذ أول دقيقة، دون مكالمة.",
        "from": [("s-signin", "التفعيل ثم الرمز السري")],
        "steps": [
            ("see", "حالة الاتصال بالقاعة", "متصل"),
            ("ask", "أي وسيلة؟", "FPT 12"),
            ("do", "يختار أفراد الطاقم", "Mounir Haj"),
            ("in", "أسماء الطاقم (اختياري)", "أسماء الطاقم"),
            ("do", "ابدأ المناوبة", "ابدأ المناوبة"),
        ],
        "next": [("s-mission-alert", "عند وصول أمر مهمة"), ("s-mission", "قائمة المهام")],
    },
    {
        "id": "s-mission", "surface": "staff", "group": "mission", "route": "MissionScreen", "title": "المهمة",
        "page": "apps/mobile/lib/staff/screens/mission_screen.dart", "who": ["agent", "team_leader"],
        "purpose": "ملف المهمة في الميدان: الحادث وملاحظة القاعة، تحذيرات العنوان، مراحل التدخل بالزر الدائري، الطريق، والتعزيز.",
        "value": "كل مرحلة تُسجَّل بضغطة مطوّلة بالوقت والموقع، فترى القاعة التقدم دون نداء لاسلكي.",
        "from": [("s-mission-alert", "زر «تم الاستلام»"), ("s-shift", "قائمة المهام")],
        "steps": [
            ("see", "الحادث وأولويته وملاحظة القاعة", "Forest fire"),
            ("see", "تحذيرات العنوان قبل الوصول", "لا تحذير على هذا العنوان"),
            ("do", "التفقّد في منطقة الخطر (رئيس الفريق)", "التفقّد في منطقة الخطر"),
            ("do", "ضغطة مطوّلة: انطلقنا، وصلنا، غادرنا…", "انطلقنا من الوحدة"),
            ("do", "الطريق أو الاتصال بالقاعة", "الطريق"),
            ("do", "أمر المهمة PDF دون شبكة", "أمر المهمة"),
            ("ask", "خطر؟ طلب تعزيز أو خطر على الطاقم", "طلب تعزيز"),
        ],
        "next": [("s-record", "«محضر التدخل» بعد الوصول"), ("s-live", "«بث مباشر للقاعة»")],
    },
]
