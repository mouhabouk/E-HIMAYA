"""The chapters of the atlas, in the order Yamen gave (2026-11-13), and the links between an app and the dashboard.

Each chapter takes the dashboard systems of the menu (apps/dashboard/src/menu/menu.json) and the groups of the apps
(apps_catalog.py) that work together, then ends with a «الترابط» card: what passes between the app and the dashboard,
told functionally here, and technically from the capture itself (the API routes each side calls and the tables one
side writes and the other reads). The technical half is recomputed on every run, so it follows the code.
"""

from __future__ import annotations

CHAPTERS: list[dict] = [
    {
        "key": "citizen", "title": "1. تطبيق المواطن",
        "members": [("citizen", "*"), ("dashboard", "citizens"), ("dashboard", "alerts")],
        "link": {
            "title": "الترابط: تطبيق المواطن ↔ فضاء المواطنين والتنبيهات في اللوحة",
            "functional": [
                "التنبيه الرسمي يُكتب في نظام «التنبيهات» باللوحة، فيصل إلى هواتف المنطقة المعنية حتى في وضع «عدم الإزعاج».",
                "المتطوع والطبيب يسجّلان من التطبيق، ويدرس طلبهما فضاء المواطنين في اللوحة؛ ثم يصلهما الاستنفار من القاعة.",
                "طلبات «اتصل بنا» والنفاذ إلى المعلومة تُعالَج في اللوحة ويعود جوابها إلى «طلباتي».",
                "النقاط والشارات والشهادات تُحسب في الخادم من البلاغات الصحيحة والتطوع، وتظهر في «مكافآتي».",
                "تحذيرات العنوان التي يكتبها المواطن تصل إلى الفريق المتجه إلى عنوانه.",
            ],
            "app": ["citizen"], "board": ["citizens", "alerts"],
        },
    },
    {
        "key": "ops", "title": "2. القاعة المركزية ولوحة القيادة وتطبيق الأعوان",
        "members": [("dashboard", "home"), ("dashboard", "reports"), ("dashboard", "opscentres"), ("dashboard", "par"),
                    ("dashboard", "decision"), ("staff", "start"), ("staff", "mission"), ("staff", "field")],
        "link": {
            "title": "الترابط: البلاغ من المواطن إلى القاعة إلى الفريق",
            "functional": [
                "المواطن يبلّغ أو يضغط «نجدة»: البلاغ يدخل قائمة القاعة بموقعه وصوره.",
                "القاعة تملأ بطاقة الاستقبال وتسند الوسيلة: أمر المهمة يرنّ في هاتف الطاقم.",
                "الطاقم يسجّل المراحل بضغطة مطوّلة (انطلقنا، وصلنا…)، فتتحرك المهمة على خريطة القاعة.",
                "من المكان: الحصيلة، تقرير الوضع، طلب التعزيز، الخطر على الطاقم والتفقد في منطقة الخطر تصل إلى لوحة القيادة فورا.",
                "المحضر والتقرير المفصّل يُختمان في الهاتف ويُحفظان مع البلاغ؛ والمواطن يرى في «بلاغاتي» أن بلاغه عولج.",
            ],
            "app": ["citizen:report", "citizen:main", "staff"], "board": ["home", "reports", "opscentres", "par", "decision"],
        },
    },
    {
        "key": "inspect", "title": "3. نظام التفقدات والوقاية والبوابة والتطبيق",
        "members": [("dashboard", "inspections"), ("dashboard", "orgs"), ("staff", "prevention"), ("staff", "inspect"),
                    ("portal", "*")],
        "link": {
            "title": "الترابط: المؤسسة والمفتش ونظام التفقدات",
            "functional": [
                "المؤسسة تسجّل ملفها من البوابة أو التطبيق: البطاقة، الفريق، المواد الخطرة، التجهيزات، الخريطة.",
                "مكتب الوقاية يدرس الملف في اللوحة ويبرمج زيارة، فتظهر في «زيارات الوقاية» على هاتف المفتش.",
                "المفتش يملأ الشبكة ويصوّر ويوقّع مع ممثل المؤسسة حتى دون شبكة، ثم يرسل القرار.",
                "القرار والشهادة يعودان إلى المؤسسة في البوابة، ويتحقق منها أي شخص برمزها.",
                "التفقد الدوري للمراكز: نظام التفقدات يبرمج المهمة، والمفتش يختم التقرير بتوقيعين من تطبيقه.",
            ],
            "app": ["portal", "staff:prevention", "staff:inspect", "citizen:institution"], "board": ["inspections", "orgs"],
        },
    },
    {
        "key": "fleet", "title": "4. نظام الأسطول والأفراد والتطبيق",
        "members": [("dashboard", "fleet"), ("dashboard", "hr")],
        "link": {
            "title": "الترابط: الأسطول والأفراد ↔ تطبيق الأعوان",
            "functional": [
                "الوسائل وحالتها تُدار في نظام الأسطول؛ عند بداية المناوبة يختار العون الوسيلة التي يركبها من القائمة نفسها.",
                "الأعوان ورتبهم وتوفرهم في نظام الأفراد؛ الطاقم المختار في الهاتف يصبح طاقم الوسيلة في القاعة.",
                "تفعيل هاتف العون وإلغاؤه يتمان من اللوحة: الهاتف الملغى يُمحى ما فيه.",
                "الموارد المستعملة في التدخل (السجل) تعود إلى الأسطول كاستهلاك وصيانة.",
            ],
            "app": ["staff:start", "staff:field"], "board": ["fleet", "hr"],
        },
    },
    {
        "key": "mother", "title": "5. النظام الأم لمدير النظام",
        "members": [("dashboard", "admin"), ("dashboard", "settings")],
        "link": {
            "title": "الترابط: النظام الأم وكل الواجهات",
            "functional": [
                "الأدوار والصلاحيات والمستخدمون تُضبط هنا، وتحدد ما تفتحه كل واجهة (اللوحة، البوابة، التطبيقان).",
                "الميزات المخفية وإصدارات التطبيق المسموح بها تُقرأ عند كل تشغيل للتطبيق (app/features و app/version).",
                "سجل التدقيق يحفظ كل كتابة من أي واجهة: من فعل ماذا ومتى.",
            ],
            "app": ["citizen", "staff", "portal"], "board": ["admin", "settings"],
        },
    },
    {
        "key": "others", "title": "6. التموقع وكشف الدخان والنوبات وبقية الأجزاء",
        "members": [("dashboard", "gis"), ("dashboard", "vision"), ("dashboard", "forecast"), ("dashboard", "coastal"),
                    ("dashboard", "strategies"), ("dashboard", "disasters"), ("dashboard", "partners"),
                    ("dashboard", "knowledge"), ("dashboard", "*")],
        "link": {
            "title": "الترابط: التموقع والرؤية والشواطئ ↔ التطبيقان",
            "functional": [
                "طبقات الخريطة التفاعلية تُنشر للتطبيق: «الأقرب إليّ» يقرأ المستشفيات والمراكز من الطبقات العامة.",
                "كاشف الدخان أو الكاميرا (نظام الرؤية) يطلق تنبيها مسبقا في فضاء المؤسسة قبل إعلام القاعة.",
                "حالة الشواطئ التي تكتبها الحراسة الشاطئية تظهر في «الشواطئ اليوم» عند المواطن.",
                "مواقع الأعوان والوسائل في الميدان تُرسم على خريطة القاعة من هواتفهم.",
            ],
            "app": ["citizen:emergency", "citizen:institution", "staff:mission"], "board": ["gis", "vision", "coastal"],
        },
    },
]


def chapter_of(surface: str, gkey: str) -> str:
    """The chapter of a card: its dashboard system, or its app group (an unlisted one goes to the last chapter)."""
    group = gkey.split(":", 1)[1] if ":" in gkey else gkey
    for ch in CHAPTERS:
        for s, g in ch["members"]:
            if s == surface and g == group:
                return ch["key"]
    for ch in CHAPTERS:
        for s, g in ch["members"]:
            if s == surface and g == "*":
                return ch["key"]
    return CHAPTERS[-1]["key"]


def _side_matches(card: dict, side: list[str], dashboard: bool) -> bool:
    if dashboard:
        return card["surface"] == "dashboard" and card["gkey"] in side
    return card["surface"] != "dashboard" and any(card["surface"] == x or card["gkey"] == x for x in side)


def link_cards(cards: list[dict]) -> list[dict]:
    """One «الترابط» card per chapter: the functional story, and the routes and tables both sides share."""
    out = []
    write = ("POST", "PUT", "PATCH", "DELETE")
    for ch in CHAPTERS:
        ln = ch["link"]
        app = [c for c in cards if _side_matches(c, ln["app"], False)]
        board = [c for c in cards if _side_matches(c, ln["board"], True)]
        app_w = {t for c in app for a in c["api"] if a["verb"] in write for t in a["tables"]}
        app_r = {t for c in app for a in c["api"] for t in a["tables"]}
        board_w = {t for c in board for a in c["api"] if a["verb"] in write for t in a["tables"]}
        board_r = {t for c in board for a in c["api"] for t in a["tables"]}
        shared = sorted(app_r & board_r)
        app_paths = sorted({(a["verb"], a["path"]) for c in app for a in c["api"]})
        board_paths = sorted({(a["verb"], a["path"]) for c in board for a in c["api"]})
        common_prefix = sorted({p for _, p in app_paths} & {p for _, p in board_paths})
        technical = []
        if shared:
            technical.append(f"جداول يشترك فيها الطرفان ({len(shared)}): " + "، ".join(shared[:24]))
        up = sorted(app_w & board_r)
        down = sorted(board_w & app_r)
        if up:
            technical.append("يكتبها التطبيق وتقرؤها اللوحة: " + "، ".join(up[:16]))
        if down:
            technical.append("تكتبها اللوحة ويقرؤها التطبيق: " + "، ".join(down[:16]))
        if common_prefix:
            technical.append("نداءات يستعملها الطرفان: " + " · ".join(common_prefix[:10]))
        technical.append(f"التطبيق: {len(app)} شاشة و{len(app_paths)} نداء · اللوحة: {len(board)} صفحة و{len(board_paths)} نداء، "
                         "كما سُجّلت عند فتح كل شاشة في الالتقاط.")
        flow = [{"t": "term", "l": "التطبيق", "s": " · ".join(sorted({c["group"].split(" · ")[-1] for c in app}))[:60], "r": None}]
        flow += [{"t": "proc", "l": f[:40], "s": "", "r": None} for f in ln["functional"]]
        flow.append({"t": "io", "l": "الخادم وقاعدة المعطيات", "s": f"{len(shared)} جدولا مشتركا", "r": None})
        flow.append({"t": "term", "l": "لوحة القيادة", "s": " · ".join(sorted({c['group'] for c in board}))[:60], "r": None})
        out.append({
            "id": f"link-{ch['key']}", "surface": "link", "chap": ch["key"], "phone": False, "route": "", "path": "",
            "shot": None, "height": 0, "group": ch["title"] + " · الترابط", "gkey": f"link:{ch['key']}",
            "item": ln["title"], "title": ln["title"], "detail": False, "locked": False,
            "purpose": "كيف يعمل التطبيق واللوحة معا في هذا الفصل.", "value": "", "lead": "", "page": "",
            "components": [], "api": [], "tables": shared, "regions": [], "access": {}, "scope": [],
            "functional": ln["functional"], "technical": technical,
            "appScreens": [{"id": c["id"], "label": c["title"]} for c in app][:40],
            "boardScreens": [{"id": c["id"], "label": c["title"]} for c in board][:40],
            "flow": flow,
        })
    return out
