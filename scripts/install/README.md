# سكريبتات التنصيب المرقّمة

كل سكريبت يُنفّذ خطوة واحدة من [الدليل التقني للتنصيب](../../docs/install-guide.md)، ورقمه هو أولويته في التنصيب.
تُنفَّذ بالترتيب من جذر المستودع. في أول كل سكريبت شرح دقيق لما يفعله، ومتى يُشغَّل، وأين، وما بعده.

| الرقم | السكريبت | الخطوة | إلزامي؟ | أين | الدليل |
|---|---|---|---|---|---|
| 00 | `00-common.sh` | المكتبة المشتركة (لا يُشغَّل وحده) | — | — | — |
| 01 | `01-system-prepare.sh` | تهيئة Ubuntu 24.04: التحديثات، الوقت، SSH، الجدار الناري، النواة، قرص البيانات | نعم | الخادم | §3 |
| 02 | `02-docker-install.sh` | Docker Engine 27+ و Compose 2.24+ | نعم | الخادم والمطوّر | §5 |
| 03 | `03-project-fetch.sh` | جلب المشروع، `.env`، توليد الأسرار، الطقس (Open-Meteo) | نعم | الخادم | §6 |
| 04 | `04-stack-start.sh` | تشغيل المنظومة الأساسية واختبار الدخان | نعم | الخادم | §7 |
| 05 | `05-first-admin.sh` | أول مدير نظام في Keycloak (كلمة مؤقتة و TOTP إجباري) | نعم | الخادم | §8 |
| 06 | `06-optional-profiles.sh` | الذكاء الاصطناعي، الرؤية، البحث، التوجيه، التضاريس، الحساسات، الدرون | حسب الحاجة | الخادم | §9 |
| 07 | `07-data-load.sh` | الطبقات، البرامج الموسمية، الإحصاء التجريبي [SIM]، فهرس المكتبة | نعم | الخادم | §9، §11.5 |
| 08 | `08-gpu-server.sh` | مشغّل NVIDIA و Container Toolkit والذكاء الاصطناعي على GPU | اختياري | خادم GPU | §10 |
| 09 | `09-production-deploy.sh` | النشر في الإنتاج: DNS، المحاكيات، الجدار الناري، Keycloak، الفحوص | للتجربة الميدانية | الخادم | §11 |
| 10 | `10-monitoring.sh` | Prometheus و Alertmanager | نعم في الإنتاج | الخادم | §11.6 |
| 11 | `11-backup-check.sh` | التحقق اليومي من النسخ (`check`) وتمرين الاستعادة (`drill`) | نعم في الإنتاج | الخادم | §13.1، §13.2 |
| 12 | `12-upgrade.sh` | الترقية إلى إصدار جديد، والرجوع (`rollback`) | عند كل إصدار | الخادم | §13.3 |
| 13 | `13-build-apk.sh` | بناء تطبيقي المواطن والأعوان وتوقيعهما | نعم | جهاز البناء | §14 |
| 14 | `14-dev-tools.sh` | Python و uv، Node.js 22، Flutter و Java | للمطوّر فقط | جهاز المطوّر | §15 |
| 15 | `15-quality-checks.sh` | CI محليًا، OWASP ZAP، تحصين الخادم | قبل كل إصدار | المطوّر والخادم | §16 |
| 16 | `16-final-verify.sh` | قائمة التحقق النهائية (قراءة فقط) | نعم | الخادم | §18 |

## المسار الكامل لخادم التجربة الميدانية

```bash
ADMIN_CIDR=10.20.0.0/24 scripts/install/01-system-prepare.sh && sudo reboot
scripts/install/02-docker-install.sh                        # ثم اخرج وادخل من جديد
WEATHER=open-meteo scripts/install/03-project-fetch.sh
scripts/install/04-stack-start.sh
ADMIN_USER=yamen scripts/install/05-first-admin.sh
scripts/install/06-optional-profiles.sh ai vision search routing terrain
scripts/install/07-data-load.sh layers programmes
# املأ API_HOST و DASHBOARD_HOST و PORTAL_HOST و AUTH_HOST و MEDIA_HOST و CADDY_TLS في .env، ثم:
BANNER=pilot scripts/install/09-production-deploy.sh
scripts/install/10-monitoring.sh
PROD=1 scripts/install/07-data-load.sh knowledge
SMS_NUMBER=<الرقم> scripts/install/13-build-apk.sh          # أو من GitHub Actions دون تثبيت
PROD=1 scripts/install/16-final-verify.sh
```

## قواعد مشتركة

- كل سكريبت يتوقف عند أول خطأ ويذكر رقمه، ويمكن إعادة تشغيله بأمان: كل خطوة تتحقق أولًا هل نُفّذت. `03` لا يغيّر سرًا
  موجودًا، و `05` لا يغيّر كلمة مرور مستخدم موجود.
- لا يُطبع أي سر، إلا كلمة المرور المؤقتة لأول مدير، وتُطبع مرة واحدة.
- كل خطوة لا رجعة فيها (مسح قرص، تحميل بيانات، ترقية) تسأل قبل التنفيذ. `ASSUME_YES=1` يجيب نعم في التنصيب الآلي.
- ملف الإعداد `.env` في جذر المستودع، ويمكن تغييره بـ `EHIMAYA_ENV_FILE`.
- المحاكيات **[SIM]** (الطقس المحاكى، محاكيات البث والمكالمات، السنوات الإحصائية التجريبية) ممنوعة في الإنتاج،
  والسكريبتات `06` و `07` و `09` ترفضها حين `PROD=1`.
- العرض أمام اللجنة على حاسوب واحد دون إنترنت له سكريبته الخاص: `scripts/demo.sh` ([demo.md](../../docs/demo.md)).
