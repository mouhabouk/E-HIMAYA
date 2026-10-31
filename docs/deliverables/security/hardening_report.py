"""Before/after hardening report (review point 15, phase 4), in Arabic, from compare.py's output.

    python3 docs/deliverables/security/hardening_report.py hardening.json [ca-testssl.json] > docs/security/hardening-report.html

The classification of the Lynis items still open after hardening is kept here (REMAINING), so a new run only needs
new items explained.
"""

import html
import json
import sys
from datetime import date
from pathlib import Path

ENV = {
    "where": "حاوية البناء (Ubuntu 24.04.5 LTS) دون systemd ودون نواة خاصة بها",
    "edge": "Caddy 2.6.2 من حزم Ubuntu بملف infra/caddy/Caddyfile نفسه (حُذف منه trusted_proxies غير المعروف في 2.6)، وCADDY_TLS=internal كما في العرض",
    "api": "الواجهة البرمجية بـ APP_ENV=production وأسرار مولّدة بـ openssl، على قاعدة مرحَّلة إلى 0088",
}

# Lynis items still open: why, and where they are handled.
REMAINING = {
    "AUTH-9284": (
        "حسابات مقفلة",
        "حسابات النظام (daemon، nobody…) مقفلة عمدا ولا تُحذف.",
        "مقبول",
    ),
    "BOOT-5180": (
        "مستوى التشغيل",
        "لا systemd في الحاوية؛ على الخادم يُفحص بـ systemctl get-default.",
        "بيئة القياس",
    ),
    "BOOT-5264": (
        "تحصين الخدمات",
        "systemd-analyze security لكل خدمة على الخادم الفعلي؛ الحاويات نفسها مقيدة (no-new-privileges، read_only حيث أمكن).",
        "الخادم",
    ),
    "DEB-0810": ("apt-listbugs", "أداة Debian لا تخدم Ubuntu.", "مقبول"),
    "FILE-6310": (
        "أقسام منفصلة",
        "‎/home و ‎/tmp و ‎/var على أقسام مستقلة يُختار عند تنصيب الخادم (الدليل التقني §2.4)، ولا يمكن في حاوية.",
        "التنصيب",
    ),
    "FINT-4350": (
        "سلامة الملفات",
        "AIDE اختياري (تهيئته تستغرق دقائق)؛ debsums و rkhunter مثبّتان، وسلامة الأدلة في المنظومة نفسها بشجرة Merkle.",
        "اختياري",
    ),
    "HOME-9304": (
        "صلاحيات المجلدات الشخصية",
        "مجلدات الحاوية (/ و /bin مسجلة كمجلدات شخصية لحسابات النظام).",
        "بيئة القياس",
    ),
    "KRNL-5788": ("النواة", "لا نواة خاصة بالحاوية.", "بيئة القياس"),
    "KRNL-6000": (
        "قيم sysctl",
        "الملف ‎/etc/sysctl.d/60-ehimaya.conf مكتوب، لكن ‎/proc/sys للقراءة فقط في الحاوية؛ يُطبَّق عند إقلاع الخادم.",
        "بيئة القياس",
    ),
    "LOGG-2130": (
        "syslog",
        "rsyslog مثبّت ومفعّل بـ systemd على الخادم؛ لا يُشغَّل دون systemd هنا.",
        "بيئة القياس",
    ),
    "LOGG-2138": ("klogd", "يتبع rsyslog وsystemd-journald على الخادم.", "بيئة القياس"),
    "LOGG-2190": ("ملفات محذوفة مفتوحة", "ملفات مؤقتة لعمليات القياس نفسها.", "مقبول"),
    "LYNIS": (
        "إصدار Lynis",
        "Lynis 3.0.9 من حزم Ubuntu؛ الإصدار الأحدث يضيف اختبارات ولا يغيّر هذه النتائج.",
        "مقبول",
    ),
    "MACF-6208": (
        "AppArmor",
        "مفعّل في نواة الخادم (Ubuntu افتراضيا)، وغير متاح داخل الحاوية.",
        "بيئة القياس",
    ),
    "NAME-4028": (
        "نطاق DNS",
        "الحاوية بلا نطاق؛ على الخادم يُضبط اسم النطاق الداخلي للديوان.",
        "بيئة القياس",
    ),
    "TOOL-5002": (
        "أدوات الأتمتة",
        "التنصيب والتحديث بسكريبتات المستودع وملفات compose، لا Ansible.",
        "مقبول",
    ),
    "FIRE-4513": (
        "قواعد غير مستعملة",
        "قواعد ufw لـ 22 و 80 بلا حركة أثناء القياس؛ 22 يُقيَّد بـ ADMIN_NET على الخادم.",
        "مقبول",
    ),
}
TLS_EXPLAIN = {
    "cert_chain_of_trust": "الشهادة صادرة عن السلطة المحلية لـ Caddy (العرض دون إنترنت)؛ تُثبَّت جذرها على الأجهزة كما في docs/demo.md، وبعدها تنجح السلسلة (القياس الثاني).",
    "cert_expirationStatus": "شهادات السلطة المحلية قصيرة العمر (12 ساعة) ويجددها Caddy آليا؛ في الإنتاج شهادة الديوان أو ACME.",
    "cert_notAfter": "كالسابق: تجديد آلي.",
    "cert_revocation": "لا CRL ولا OCSP في السلطة المحلية؛ في الإنتاج من بنية مفاتيح الديوان.",
    "intermediate_cert_notAfter <#1>": "الشهادة الوسيطة المحلية (7 أيام) يجددها Caddy.",
    "intermediate_cert_expiration <#1>": "كالسابق.",
    "TLS_session_ticket": "مدة تذاكر الجلسة الافتراضية في Caddy (يدورها كل 12 ساعة)، ملاحظة منخفضة.",
    "DNS_CAArecord": "سجل CAA يُضاف عند اعتماد اسم نطاق عمومي، لا في الشبكة المحلية.",
}
CLASS_FILL = {
    "مقبول": "#EEF0F4",
    "بيئة القياس": "#E8EDFA",
    "الخادم": "#FFF3D6",
    "التنصيب": "#FFF3D6",
    "اختياري": "#E0F3EF",
}


def esc(s: object) -> str:
    return html.escape(str(s))


def table(head: list[str], rows: list[list[str]], raw: bool = False) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    tr = "".join(
        "<tr>" + "".join(f"<td>{c if raw else esc(c)}</td>" for c in r) + "</tr>"
        for r in rows
    )
    return f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def ports(p: list[dict] | None) -> str:
    if not p:
        return "لا شيء"
    return "، ".join(
        f"<code>{x['port']}/{x['proto']}</code> {esc(x['service'])}" for x in p
    )


def main() -> None:
    d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    ca = (
        json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        if len(sys.argv) > 2
        else None
    )
    b, a, lyn = d["before"], d["after"], d["lynis"]
    i0, i1 = lyn["index"]
    sev = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    tls_b, tls_a = b["testssl"], a["testssl"]
    ca_counts = (
        {s: sum(1 for x in ca if x.get("severity") == s) for s in sev} if ca else None
    )

    out = [
        f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ء-حماية | تقرير التحصين الأمني (قبل وبعد)</title>
<style>
:root{{--page:#F3F5FA;--card:#fff;--ink:#182038;--muted:#5B6478;--line:#E3E7EF;--navy:#1F3FA0;--red:#D7141A;--green:#188038;--amber:#F5B400;--chip:#EEF0F4}}
@media (prefers-color-scheme:dark){{:root{{--page:#0E1426;--card:#161E35;--ink:#E8ECF5;--muted:#A6AFC4;--line:#26304D;--navy:#8FA8FF;--red:#FF6B6B;--green:#4CC772;--chip:#1F2846}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font-family:"IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif;line-height:1.75;font-size:15px}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px 80px}}
header,section{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 24px;margin-bottom:18px;box-shadow:0 1px 3px rgb(24 32 56/6%)}}
header{{border-top:6px solid var(--navy)}} h1{{margin:0 0 4px;font-size:26px}} h2{{font-size:20px;margin:0 0 10px;color:var(--navy)}}
.sub{{color:var(--muted);margin:0}} .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:14px}}
.kpi{{background:var(--chip);border-radius:12px;padding:10px 14px}} .kpi b{{display:block;font-size:26px}} .kpi span{{color:var(--muted);font-size:13px}}
.bar{{height:12px;background:var(--line);border-radius:6px;overflow:hidden;margin:4px 0}} .bar i{{display:block;height:100%}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{border:1px solid var(--line);padding:6px 9px;text-align:start;vertical-align:top}}
th{{background:var(--chip)}} td:first-child{{white-space:nowrap}} .tbl{{overflow-x:auto;margin:10px 0}} code{{direction:ltr;unicode-bidi:isolate;background:var(--chip);padding:1px 5px;border-radius:4px;font-size:13px}}
pre{{direction:ltr;text-align:left;background:var(--chip);padding:10px 12px;border-radius:8px;overflow-x:auto;font-size:13px}}
.note{{border-inline-start:4px solid var(--navy);background:var(--chip);padding:10px 14px;border-radius:8px;margin:10px 0}}
.pill{{display:inline-block;border-radius:999px;padding:0 10px;font-size:12px;font-weight:700;color:#3E4657}}
.ok{{color:var(--green);font-weight:700}} .bad{{color:var(--red);font-weight:700}} footer{{color:var(--muted);text-align:center;font-size:13px}}
</style></head><body><div class="wrap">
<header><h1>تقرير التحصين الأمني: قبل وبعد</h1>
<p class="sub">النقطة 15 من خطة المراجعة (المرحلة 4: الوثائق والأمن). قياس فعلي بـ Lynis و nmap و testssl.sh قبل تطبيق
<code>infra/security/harden-host.sh</code> وبعده. التاريخ {
            date.today().isoformat()
        }.</p>
<div class="kpis">
<div class="kpi"><span>مؤشر Lynis قبل</span><b>{
            i0
        }</b><div class="bar"><i style="width:{
            i0
        }%;background:var(--amber)"></i></div></div>
<div class="kpi"><span>مؤشر Lynis بعد</span><b class="ok">{
            i1
        }</b><div class="bar"><i style="width:{
            i1
        }%;background:var(--green)"></i></div></div>
<div class="kpi"><span>ملاحظات Lynis المعالجة</span><b>{
            len(lyn["resolved"])
        }</b><span>من {len(lyn["resolved"]) + len(lyn["remaining"])}</span></div>
<div class="kpi"><span>منافذ TCP مفتوحة بعد</span><b>{
            len(a["nmap_tcp"] or [])
        }</b><span>{", ".join(str(x["port"]) for x in a["nmap_tcp"] or [])}</span></div>
<div class="kpi"><span>بروتوكولات TLS</span><b>{
            " و ".join(tls_a["protocols"]) if tls_a else "—"
        }</b><span>لا SSL ولا TLS 1.0/1.1</span></div>
</div></header>

<section><h2>1. بيئة القياس وحدودها</h2>
{
            table(
                ["العنصر", "القيمة"],
                [
                    ["الجهاز", ENV["where"]],
                    ["الحافة", ENV["edge"]],
                    ["الواجهة البرمجية", ENV["api"]],
                    [
                        "Lynis",
                        f"{b['lynis']['version']} ({b['lynis']['tests']} اختبارا قبل، {a['lynis']['tests']} بعد)",
                    ],
                    [
                        "nmap",
                        "TCP: أشيع 1000 منفذ ومنافذ المنظومة؛ UDP: 53 و123 و161 و443 و5060 و8189",
                    ],
                    [
                        "testssl.sh",
                        "3.2rc3: البروتوكولات، الشهادة، الترويسات، الثغرات المعروفة (Heartbleed، ROBOT، POODLE…)",
                    ],
                ],
            )
        }
<div class="note">الحاوية لا تشغّل systemd ولا تملك نواتها، فبعض الخطوات كُتبت ملفاتها ولم تُفعَّل (sysctl، auditd بالكامل، fail2ban، rsyslog، AppArmor). لذلك مؤشر {
            i1
        } حدّ أدنى؛ على خادم Ubuntu حقيقي تُفعَّل هذه الخطوات كلها بالسكريبت نفسه، ويُعاد القياس بالأمر نفسه. فحص ZAP يحتاج Docker، فلم يُجرَ هنا؛ يُجرى على نسخة التجربة بـ <code>infra/security/zap/run.sh</code> (فحص الواجهة البرمجية بحساب عون) وبـ <code>audit.sh</code> (الفحص السلبي للحافة).</div>
</section>

<section><h2>2. ما يفعله سكريبت التحصين</h2>
<pre>sudo infra/security/harden-host.sh --check  --profile demo   # يعرض ما سيتغير، دون كتابة
sudo infra/security/harden-host.sh --apply  --profile demo   # حاسوب العرض: 443 فقط على الشبكة المحلية
sudo ADMIN_NET=10.20.0.0/24 TELEPHONY=1 infra/security/harden-host.sh --apply --profile prod</pre>
{
            table(
                ["المجال", "الإجراء"],
                [
                    [
                        "الحزم",
                        "ufw و auditd و fail2ban و unattended-upgrades و needrestart و debsums و rkhunter و libpam-pwquality و acct و sysstat و rsyslog و chrony",
                    ],
                    [
                        "النواة والشبكة",
                        "‎/etc/sysctl.d/60-ehimaya.conf: حماية مؤشرات النواة، منع إعادة التوجيه ومسارات المصدر، SYN cookies، تسجيل الحزم الشاذة؛ إعادة توجيه IPv4 تبقى لـ Docker",
                    ],
                    [
                        "الوحدات",
                        "تعطيل dccp و sctp و rds و tipc وأنظمة ملفات غير مستعملة و firewire، وتخزين USB (إلا بـ ALLOW_USB_STORAGE=1)",
                    ],
                    [
                        "الحسابات",
                        "umask 027، عمر كلمة السر، 65536 دورة تجزئة، جودة كلمة السر (12 حرفا، 3 أصناف)، لا تفريغ للذاكرة",
                    ],
                    [
                        "SSH",
                        "مفاتيح فقط، لا دخول للجذر، 3 محاولات، لافتة قانونية؛ مع fail2ban (حظر ساعة بعد 5 محاولات)",
                    ],
                    [
                        "الجدار الناري",
                        "رفض كل وارد افتراضيا؛ العرض: 22 و 443 (TCP و UDP) و 8189/udp؛ الإنتاج: يضاف 80 و SIP و RTP عند TELEPHONY=1؛ SSH من ADMIN_NET فقط",
                    ],
                    [
                        "التدقيق",
                        "قواعد auditd للهوية والصلاحيات و SSH والوقت و Docker وملف الأسرار ‎.env",
                    ],
                    [
                        "Docker",
                        "no-new-privileges، live-restore، سجلات محدودة الحجم، دون userland-proxy",
                    ],
                    [
                        "الملفات",
                        "‎.env بصلاحية 600، المجلدات الشخصية 750، مجلدات cron للجذر، المترجمات للجذر في الإنتاج، Postfix المحلي دون VRFY وعلى loopback",
                    ],
                ],
            )
        }
<p>كل خطوة تفحص قبل أن تكتب، فإعادة التشغيل لا تغيّر شيئا (القياس: <code>--check</code> بعد <code>--apply</code> أعاد «0 تغيير»).</p>
</section>

<section><h2>3. Lynis: من {i0} إلى {i1}</h2>
<h3>ما عولج ({len(lyn["resolved"])})</h3>
{
            table(
                ["الاختبار", "الملاحظة قبل التحصين"],
                [[x["id"], x["text"]] for x in lyn["resolved"]],
            )
        }
<h3>ما بقي ({len(lyn["remaining"])}) ولماذا</h3>
{
            table(
                ["الاختبار", "الموضوع", "السبب", "التصنيف"],
                [
                    [
                        x["id"],
                        REMAINING.get(x["id"], ("—", x["text"], "يُراجع"))[0],
                        REMAINING.get(x["id"], ("", x["text"], ""))[1],
                        f"<span class='pill' style='background:{CLASS_FILL.get(REMAINING.get(x['id'], ('', '', 'يُراجع'))[2], '#FDE8E8')}'>{esc(REMAINING.get(x['id'], ('', '', 'يُراجع'))[2])}</span>",
                    ]
                    for x in lyn["remaining"]
                ],
                raw=True,
            )
        }
{
            (
                "<h3>ما ظهر بعد التحصين</h3>"
                + table(
                    ["الاختبار", "الملاحظة", "السبب"],
                    [
                        [
                            x["id"],
                            x["text"],
                            REMAINING.get(x["id"], ("", "يُراجع", ""))[1],
                        ]
                        for x in lyn["new"]
                    ],
                )
            )
            if lyn["new"]
            else ""
        }
</section>

<section><h2>4. المنافذ المكشوفة (nmap)</h2>
{
            table(
                ["", "قبل", "بعد"],
                [
                    ["TCP", ports(b["nmap_tcp"]), ports(a["nmap_tcp"])],
                    ["UDP", ports(b["nmap_udp"]), ports(a["nmap_udp"])],
                ],
                raw=True,
            )
        }
<p>لا قاعدة بيانات ولا Valkey ولا NATS ولا Keycloak ولا واجهة برمجية مكشوفة: كلها على <code>127.0.0.1</code> أو داخل شبكة Docker، والمدخل الوحيد هو Caddy (80 يحوّل إلى 443). المنفذ 443/udp لبروتوكول HTTP/3. الجدار الناري لا يغيّر هذه القائمة لأنها كانت ضيقة أصلا؛ دوره منع أي خدمة تُضاف لاحقا عن طريق الخطأ.</p>
</section>

<section><h2>5. TLS (testssl.sh)</h2>
{
            table(
                ["الخطورة", "قبل", "بعد", "بعد تثبيت جذر العرض على الجهاز"],
                [
                    [
                        s,
                        str(tls_b["counts"][s]),
                        str(tls_a["counts"][s]),
                        str(ca_counts[s]) if ca_counts else "—",
                    ]
                    for s in sev
                ],
            )
        }
{
            table(
                ["الملاحظة", "النتيجة", "التفسير"],
                [
                    [x["id"], x["finding"], TLS_EXPLAIN.get(x["id"], "يُراجع")]
                    for s in sev
                    for x in tls_a["findings"][s]
                ],
            )
        }
<p class="ok">لا ثغرة معروفة (Heartbleed، CCS، ROBOT، POODLE، BEAST، LUCKY13، SWEET32، FREAK، LOGJAM، DROWN): البروتوكولات المعروضة TLS 1.2 و TLS 1.3 فقط، وكل الشفرات بتبادل مفاتيح ECDHE وتشفير AEAD.</p>
<p>الملاحظات المتبقية كلها عن الشهادة المحلية للعرض دون إنترنت، لا عن الإعداد. في التجربة والإنتاج تُستبدل بشهادة من بنية مفاتيح الديوان أو من ACME (المتغير CADDY_TLS)، ويُعاد القياس.</p>
</section>

<section><h2>6. ترويسات الأمان (الحافة والواجهة البرمجية)</h2>
{
            table(
                ["الترويسة", "القيمة"],
                [
                    [
                        "Strict-Transport-Security",
                        "max-age=31536000; includeSubDomains",
                    ],
                    [
                        "Content-Security-Policy",
                        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                    ],
                    ["X-Content-Type-Options", "nosniff"],
                    ["X-Frame-Options", "DENY"],
                    ["Referrer-Policy", "no-referrer"],
                    ["Cross-Origin-Opener-Policy", "same-origin"],
                    [
                        "Permissions-Policy",
                        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
                    ],
                    ["Cache-Control", "no-store"],
                    ["Server", "محذوفة"],
                ],
            )
        }
<p>والإقلاع بـ APP_ENV=production يرفض أي سر ضعيف: أول محاولة في هذا القياس رُفضت لأن كلمة سر دور قاعدة البيانات أقصر من 16 حرفا، ولم تقلع الواجهة حتى استُبدلت.</p>
</section>

<section><h2>7. لإعادة القياس على خادم التجربة</h2>
<pre>sudo apt install lynis nmap testssl.sh
sudo infra/security/audit.sh before &lt;IP&gt; api.&lt;domain&gt;
sudo ADMIN_NET=&lt;admin network&gt; infra/security/harden-host.sh --apply --profile prod
sudo infra/security/audit.sh after &lt;IP&gt; api.&lt;domain&gt;
python3 infra/security/compare.py audit-before audit-after &gt; hardening.json
python3 docs/deliverables/security/hardening_report.py hardening.json &gt; docs/security/hardening-report.html</pre>
<p>ويبقى قبل الإطلاق: فحص ZAP للواجهة البرمجية بحساب عون، واختبار اختراق خارجي، وتدقيق الوكالة الوطنية للأمن السيبراني (معايير القبول، الملف الوصفي §9.2).</p>
</section>
<footer>ء-حماية e-Himaya · الديوان الوطني للحماية المدنية · المعطيات الخام: docs/security/hardening/</footer>
</div></body></html>"""
    ]
    print("".join(out))


if __name__ == "__main__":
    main()
