// The unified technical and security file (review point 14, phase 4): node build.js <hardening.json> <dict.json> <out.docx>
// Port matrix, secrets to change (read from .env.example, so a new secret appears here), protocols, identity, data
// protection, hardening (measured, point 15), logging, backups, supply chain, threat model and the go-live checklist.
const fs = require('fs');
const path = require('path');
const L = require('../lib/ar-docx.js');
const { C, W, h1, h2, h3, p, note, ul, code, table, kv, toc, cover, document, save } = L;

const ROOT = path.join(__dirname, '..', '..', '..');
const [hardFile, dictFile, out] = process.argv.slice(2);
const hard = JSON.parse(fs.readFileSync(hardFile, 'utf8'));
const dict = JSON.parse(fs.readFileSync(dictFile, 'utf8'));
const today = new Date().toISOString().slice(0, 10);

// Secrets of .env.example: name, example value, the comment above it.
const SECRET = /PASSWORD|SECRET|TOKEN|_KEY$|_KEYS$|SIGNING_KEY|SERVICE_ACCOUNT$/;
const secrets = [];
{
  let com = [];
  for (const l of fs.readFileSync(path.join(ROOT, '.env.example'), 'utf8').split('\n')) {
    if (l.startsWith('#')) { com.push(l.replace(/^#\s*/, '')); continue; }
    const m = l.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && SECRET.test(m[1]) && !['COASTAL_LAYER_KEY', 'CERTIFICATE_PREVIOUS_PUBLIC_KEYS'].includes(m[1])) secrets.push({ name: m[1], example: m[2], comment: com.join(' ') });
    com = [];
  }
}
const AR = {
  POSTGRES_PASSWORD: ['المستعمل الأعلى لـ PostgreSQL (التهيئة فقط)', 'openssl rand -hex 24'],
  EHIMAYA_DB_PASSWORD: ['مالك قاعدة المنظومة (الترحيلات)', 'openssl rand -hex 24'],
  EHIMAYA_DB_RUNTIME_PASSWORD: ['دور التشغيل ehimaya_app (الواجهة البرمجية)، إلزامي في الإنتاج', 'openssl rand -hex 24'],
  KEYCLOAK_DB_PASSWORD: ['قاعدة Keycloak', 'openssl rand -hex 24'],
  KEYCLOAK_ADMIN_PASSWORD: ['مدير Keycloak الأول؛ يُستبدل بحساب شخصي بالتحقق بخطوتين ثم يُعطَّل', 'openssl rand -base64 24'],
  VALKEY_PASSWORD: ['ذاكرة Valkey (الحدود والجلسات)', 'openssl rand -hex 24'],
  NATS_APP_PASSWORD: ['أحداث NATS', 'openssl rand -hex 24'],
  S3_ACCESS_KEY: ['معرّف التخزين S3 (SeaweedFS)', 'اسم غير متوقع'],
  S3_SECRET_KEY: ['سر التخزين S3', 'openssl rand -hex 32'],
  ANON_PSEUDONYM_SECRET: ['اشتقاق الأسماء المستعارة للمبلّغين المجهولين (HMAC)؛ لا يُدوَّر دون خطة ترحيل', 'openssl rand -hex 32'],
  FIELD_ENCRYPTION_KEY: ['مفتاح AES-256 لتشفير الحقول (الإصدار 1)؛ فقدانه يعني فقدان المعطيات المشفّرة', 'openssl rand -base64 32'],
  FIELD_ENCRYPTION_KEYS: ['إصدارات المفتاح التالية عند التدوير «2:…,3:…»', 'openssl rand -base64 32 لكل إصدار'],
  TUSD_HOOK_SECRET: ['نداءات tusd إلى الواجهة البرمجية', 'openssl rand -hex 24'],
  METRICS_TOKEN: ['قراءة Prometheus لـ /metrics (فارغ = معطّل)', 'openssl rand -hex 24'],
  CERTIFICATE_SIGNING_KEY: ['توقيع شهادات السلامة Ed25519؛ يُحفظ نسخة احتياطية دون اتصال', 'openssl rand -base64 32'],
  EVIDENCE_SIGNING_KEY: ['توقيع الختم الساعي لبصمات الأدلة وسجل التدقيق Ed25519', 'openssl rand -base64 32'],
  SMTP_PASSWORD: ['خادم البريد الصادر', 'من مزوّد البريد'],
  FCM_SERVICE_ACCOUNT: ['حساب خدمة Firebase للإيقاظ (دون معطيات شخصية)', 'من حساب الديوان في Firebase'],
  SMS_HTTP_TOKEN: ['بوابة الرسائل القصيرة', 'من مزوّد SMS'],
  AI_SERVICE_TOKEN: ['الواجهة البرمجية ← خدمة الذكاء الاصطناعي', 'openssl rand -hex 24'],
  MEDIAMTX_HOOK_TOKEN: ['نداءات MediaMTX إلى الواجهة البرمجية', 'openssl rand -hex 24'],
  MEDIAMTX_API_PASSWORD: ['الواجهة البرمجية ← واجهة MediaMTX', 'openssl rand -hex 24'],
  STREAM_SIM_TOKEN: ['[SIM] محاكي الكاميرا؛ فارغ في الإنتاج (يُرفض)', 'فارغ'],
  VISION_API_TOKEN: ['الواجهة البرمجية ← خدمة الرؤية', 'openssl rand -hex 24'],
  VISION_CALLBACK_TOKEN: ['خدمة الرؤية ← الواجهة البرمجية', 'openssl rand -hex 24'],
  SENSOR_GATEWAY_TOKEN: ['بوابة الحساسات ← الواجهة البرمجية', 'openssl rand -hex 24'],
  VISION_READ_PASSWORD: ['قراءة البث الداخلي RTSP من كاشف الحرائق', 'openssl rand -hex 24'],
  WEATHER_API_KEY: ['مزوّد الطقس إن كان مدفوعا', 'من المزوّد'],
  OPENSEARCH_ADMIN_PASSWORD: ['مدير OpenSearch (ملف search)', 'openssl rand -base64 24'],
  OPENSEARCH_PASSWORD: ['حساب المنظومة في OpenSearch', 'openssl rand -base64 24'],
  TELEPHONY_ARI_PASSWORD: ['الواجهة البرمجية ← Asterisk ARI', 'openssl rand -hex 24'],
  TELEPHONY_TRUNK_PASSWORD: ['خط الهاتف (SIP trunk) من المشغّل', 'من المشغّل'],
  SMS_INBOUND_SECRET: ['توقيع HMAC للرسائل الواردة من بوابة SMS', 'openssl rand -hex 32'],
  SMS_PHONE_SIGNING_KEY: ['[SIM] هاتف العرض كبوابة SMS؛ ممنوع في الإنتاج', 'openssl rand -hex 32'],
  SMS_PHONE_PASSWORD: ['[SIM] هاتف العرض كبوابة SMS', 'openssl rand -hex 16'],
  OTP_SMS_SECRET: ['الواجهة البرمجية ↔ مزوّد الدخول بالهاتف في Keycloak', 'openssl rand -hex 32'],
  TELEPHONY_SIM_PASSWORD: ['[SIM] محاكي المكالمات؛ فارغ في الإنتاج', 'فارغ'],
  TELEPHONY_SIM_TOKEN: ['[SIM] محاكي المكالمات؛ فارغ في الإنتاج', 'فارغ'],
};

// Ports: exposed per compose file (checked in the files in this phase), then internal only.
const PORTS = [
  ['443/tcp و 443/udp', 'HTTPS و HTTP/3', 'Caddy', 'الإنتاج والعرض', 'المدخل الوحيد: الواجهة البرمجية، اللوحة، البوابة، Keycloak، الوسائط، البث WebRTC/HLS، الهاتف عبر WebSocket'],
  ['80/tcp', 'HTTP', 'Caddy', 'الإنتاج', 'تحويل إلى HTTPS وتحدي ACME فقط؛ غير منشور في العرض'],
  ['8189/udp', 'WebRTC (ICE/DTLS-SRTP)', 'MediaMTX', 'الإنتاج والعرض', 'وسائط البث المباشر من الهواتف وإليها'],
  ['8554/tcp و 1935/tcp', 'RTSP و RTMP', 'MediaMTX', 'الإنتاج، والشبكة المحلية (DEVICES_LAN_IP)', 'الكاميرات الثابتة والدرون؛ بكلمة سر لكل جهاز'],
  ['8088/tcp', 'HTTP موقّع', 'بوابة الحساسات', 'الشبكة المحلية فقط (compose.lan)', 'قراءات موقّعة Ed25519 من الحساسات'],
  ['5060/udp و 5060/tcp', 'SIP', 'Asterisk', 'الإنتاج، عند تفعيل الهاتف', 'خط المشغّل (trunk)؛ يُقيَّد بعنوان المشغّل'],
  ['5061/tcp', 'SIP على TLS', 'Asterisk', 'الإنتاج، عند تفعيل الهاتف', 'المفضل على 5060'],
  ['10000-10099/udp', 'RTP/SRTP', 'Asterisk', 'الإنتاج، عند تفعيل الهاتف', 'صوت المكالمات'],
  ['22/tcp', 'SSH', 'النظام', 'الإدارة', 'بالمفاتيح فقط، ومن ADMIN_NET فقط (harden-host.sh)'],
];
const INTERNAL = [
  ['5432', 'PostgreSQL', 'api، worker، migrate، keycloak، backup'], ['6379', 'Valkey', 'api، worker'], ['4222 و 8222', 'NATS (العميل والمراقبة)', 'api، worker'],
  ['8333', 'SeaweedFS S3', 'api، tusd؛ الروابط الموقّعة عبر Caddy'], ['1080', 'tusd', 'عبر Caddy فقط (/api/v1/uploads)'], ['8080', 'Keycloak', 'عبر Caddy فقط؛ /admin من KEYCLOAK_ADMIN_ALLOW'],
  ['8000', 'الواجهة البرمجية', 'عبر Caddy فقط؛ /internal و /metrics محجوبان'], ['8888 و 8889 و 9997', 'MediaMTX (HLS و WebRTC والواجهة)', 'المسارات /live/<uuid>/ فقط عبر Caddy'],
  ['8088', 'Asterisk ARI و WebSocket', 'api؛ /telephony/ws فقط عبر Caddy'], ['8090 و 8025', 'notify-sim و mailpit [SIM]', 'التطوير فقط (dev-tools)'],
  ['9200', 'OpenSearch', 'api (ملف search)'], ['11434', 'Ollama', 'خدمة ai (ملف ai)'], ['8002', 'Valhalla', 'api (ملف routing)'], ['9090 و 9093', 'Prometheus و Alertmanager', 'ملف monitoring'],
];
const PROTOCOLS = [
  ['HTTPS (TLS 1.2 و 1.3)', 'كل حركة المستعملين', 'شفرات ECDHE + AEAD فقط، HSTS سنة، HTTP/3 (QUIC) اختياري. قيس: testssl.sh دون ثغرة معروفة'],
  ['OpenID Connect و OAuth 2.0 (PKCE)', 'الدخول (Keycloak)', 'فضاء عام (الهاتف ورمز SMS) وفضاء إداري (كلمة سر + TOTP إلزامي)؛ رمز وصول JWT موقّع RS256 قصير العمر'],
  ['REST/JSON', 'الواجهة البرمجية', 'OpenAPI منشور؛ تحقق بالمخطط؛ حدود استعمال؛ تزامن متفائل (version)؛ مفتاح عدم التكرار للكتابات من الهاتف'],
  ['WebSocket', 'الأحداث الفورية للوحة', 'نفس الرمز JWT؛ الأحداث مصفّاة حسب الولاية والدور'],
  ['tus 1.0', 'رفع الوسائط بالاستئناف', 'عبر Caddy؛ تحقق من النوع بالمحتوى؛ بصمة SHA-256 عند الاستلام'],
  ['S3 بروابط موقّعة', 'تنزيل الوسائط', 'رابط لمدة قصيرة لكل طلب؛ CSP sandbox؛ GET فقط'],
  ['WebRTC WHIP/WHEP', 'البث المباشر', 'DTLS-SRTP؛ رمز لكل جلسة؛ مسارات UUID فقط'],
  ['RTSP و RTMP', 'الكاميرات الثابتة والدرون', 'كلمة سر لكل جهاز؛ الشبكة المحلية؛ أحداث الأبراج موقّعة Ed25519 (3 من 5 إطارات)'],
  ['SIP (TLS) و RTP/SRTP', 'الهاتف (198، المكالمات)', 'Asterisk؛ الهاتف البرمجي في اللوحة عبر WSS؛ التسجيل معطّل حتى ترخيص الهيئة'],
  ['SMS موقّعة (EH2، EH3)', 'الفرق والمتطوعون دون إنترنت', 'مفتاح لكل جهاز؛ HMAC؛ رفض الإعادة بالرقم التسلسلي'],
  ['Webhook HMAC', 'بوابة SMS الواردة', 'POST فقط على /internal/sms/inbound، حجم 16 ك.ب، توقيع SMS_INBOUND_SECRET'],
  ['FCM', 'إيقاظ الهواتف', 'دون أي معطى شخصي في الإشعار؛ التطبيق يجلب التفاصيل بعد الدخول'],
  ['NATS JetStream', 'الأحداث بين الخدمات', 'داخلي، بكلمة سر'],
  ['PostgreSQL', 'المعطيات', 'داخلي؛ دوران (مالك وتشغيل)؛ RLS؛ النسخ الاحتياطي WAL مشفّر'],
  ['Ed25519', 'التوقيعات', 'شهادات السلامة، قرارات اللجان، ختم الأدلة، الحساسات والأبراج'],
];

const L0 = hard.lynis.index;
const tcpAfter = (hard.after.nmap_tcp || []).map(x => `${x.port}/${x.proto}`).join(' و ');

const children = [
  ...cover({ title: 'الملف التقني والأمني الموحد', subtitle: 'المنافذ، الأسرار، البروتوكولات، التحصين، والتحقق قبل التشغيل',
    logo: path.join(ROOT, 'apps', 'dashboard', 'public', 'brand', 'logo.png'),
    meta: [['الإصدار', '1.0 (المرحلة 4، النقطة 14)'], ['التاريخ', today], ['المرجع', 'infra/ و .env.example و docs/security/ و docs/runbooks/'],
      ['يجمع', 'ما كان موزعا على الدليل التقني ودليل الإنتاج ونموذج التهديدات و ASVS وتقييم الأثر، مع نتائج التحصين المقيسة']] }),
  ...toc(),
  h1('0. الغرض والنطاق'),
  p('مرجع واحد لمن ينصّب المنظومة أو يدققها: ما يُفتح على الشبكة ولماذا، ما يجب تغييره قبل أي تشغيل، كيف تتحدث المكونات وكيف تُحمى، وما قيس فعلا. الأوامر التفصيلية للتنصيب في الدليل التقني (docs/install-guide.md)، والقرارات الأمنية المفصلة في docs/security/.'),
  ...ul(['ما يحمل الشارة [SIM] محاكاة للتجربة، ويرفض الإنتاج الإقلاع إن وجدها مفعّلة.',
    'كل رقم في هذه الوثيقة مقيس في المرحلة 4 أو مقروء من ملفات المستودع.']),

  h1('1. المناطق والبنية', { pageBreak: true }),
  table([2300, 3300, 4038], ['المنطقة', 'المكونات', 'القاعدة'], [
    ['المستعملون (الإنترنت أو الشبكة المحلية)', 'التطبيق، المتصفح، الكاميرات، الحساسات، خط الهاتف', 'لا يصلون إلا إلى Caddy (443) وما في مصفوفة المنافذ'],
    ['الحافة', 'Caddy', 'TLS، الترويسات، حجب المسارات الداخلية، سجلات دون عناوين IP'],
    ['التطبيقات', 'api، worker، dashboard، portal، keycloak، tusd، mediamtx، telephony، ai، vision', 'شبكة Docker داخلية؛ لا منفذ منشور إلا عبر الحافة'],
    ['المعطيات', 'PostgreSQL، Valkey، NATS، SeaweedFS، OpenSearch', 'داخلية؛ بكلمات سر؛ لا منفذ منشور في الإنتاج'],
    ['الإدارة', 'SSH، Prometheus، النسخ الاحتياطي', 'من ADMIN_NET فقط'],
  ]),
  p('العرض أمام اللجنة: حاسوب واحد، شبكة Wi-Fi محلية دون إنترنت، والمنفذ 443 وحده على عنوان DEMO_LAN_IP (infra/compose.demo.yml)، مع شهادة داخلية (CADDY_TLS=internal) يُثبَّت جذرها على الهاتفين.'),

  h1('2. مصفوفة المنافذ', { pageBreak: true }),
  h2('2.1 المنافذ المنشورة'),
  table([1700, 1500, 1300, 1900, 3238], ['المنفذ', 'البروتوكول', 'الخدمة', 'متى', 'الغرض والقيود'], PORTS, { ltrCols: [0] }),
  note(`قيس في المرحلة 4 (nmap من الشبكة): المفتوح ${tcpAfter} في TCP، و 443/udp. في ملف التطوير infra/compose.yml كل منفذ مربوط بـ 127.0.0.1.`),
  h2('2.2 المنافذ الداخلية (غير منشورة)'),
  table([1700, 3300, 4638], ['المنفذ', 'الخدمة', 'من يتصل بها'], INTERNAL, { ltrCols: [0] }),
  p('تنبيه: Docker ينشر المنافذ بسلسلة iptables خاصة قبل ufw، فلا يحمي الجدار الناري منفذا منشورا في compose. لذلك تُربط كل المنافذ بعنوان صريح، والمرجع فحص nmap من جهاز آخر.'),

  h1('3. الأسرار الواجب تغييرها', { pageBreak: true }),
  p(`${secrets.length} سرا في .env.example. كلها تُولَّد عشوائيا وتُحفظ في .env بصلاحية 600 (harden-host.sh) ولا تُرسل بالبريد. الإقلاع بـ APP_ENV=production يرفض أي قيمة تحمل علامة مثال (change-me…)، أو أقصر من 16 حرفا، أو قليلة العشوائية، ويسمّي المتغير دون كشف قيمته (services/api/app/core/secrets_policy.py).`),
  table([2900, 4238, 2500], ['المتغير', 'الغرض', 'التوليد'],
    secrets.map(s => [s.name, (AR[s.name] || [s.comment.slice(0, 140) || '—'])[0], (AR[s.name] || [, 'openssl rand -hex 24'])[1]]), { ltrCols: [0, 2], size: 16 }),
  h2('3.1 التدوير'),
  ...ul(['FIELD_ENCRYPTION_KEY: إضافة إصدار في FIELD_ENCRYPTION_KEYS ثم python -m app.modules.privacy.cli reencrypt؛ الإصدار 1 يبقى لأنه جذر الفهارس العمياء.',
    'CERTIFICATE_SIGNING_KEY: المفتاح العمومي القديم يوضع في CERTIFICATE_PREVIOUS_PUBLIC_KEYS ليبقى التحقق من الشهادات السابقة.',
    'كلمات سر الخدمات: تُغيَّر في .env ثم docker compose up -d؛ دور قاعدة البيانات يُحدَّث بـ db-roles.',
    'كل تغيير يُسجَّل في سجل الإدارة، ونسخة من .env مشفّرة في خزنة الديوان دون اتصال.']),

  h1('4. البروتوكولات', { pageBreak: true }),
  table([2400, 2200, 5038], ['البروتوكول', 'الاستعمال', 'الحماية'], PROTOCOLS),

  h1('5. الهوية والصلاحيات'),
  ...ul(['فضاءان في Keycloak: عام (المواطن، الدخول برقم الهاتف ورمز SMS) وإداري (الأعوان، كلمة سر قوية + TOTP إلزامي في الإنتاج).',
    'من المحاولة الثالثة الفاشلة تحدٍّ آلي SHA-256 قبل فحص كلمة السر، والإيقاف المؤقت بعد 10 محاولات، دون أي طرف ثالث.',
    'الأدوار والولاية في الرمز؛ الفهرس يمنح الخصائص أو يخفيها لكل حساب أو دور (access.feature_rule).',
    `عزل حسب الولاية بـ Row-Level Security في ${dict.counts.rls_tables} جدولا؛ التطبيق يعمل بدور ehimaya_app الذي لا يملك أي جدول ولا يتجاوز السياسات.`,
    'الوصول الاستثنائي (break-glass) بسبب ومدة ومراجعة لاحقة؛ تطبيق الأعوان مربوط بالجهاز ويُمسح عن بعد.']),

  h1('6. حماية المعطيات'),
  ...ul([`${dict.counts.encrypted_columns} عمودا مشفّرا على مستوى الحقل (AES-256-GCM)، وبصمات HMAC للبحث دون كشف القيمة.`,
    'الملف الطبي والرأي الطبي مشفّران على الهاتف (X25519 و HKDF و Argon2id)؛ الخادم لا يملك مفتاحهما.',
    'المبلّغ المجهول باسم مستعار مشتق (HMAC)؛ لا عناوين IP في سجلات الحافة.',
    'مدد الحفظ آلية (القانون 2004-63): المواقع 72 ساعة، مواقع العربات 30 يوما، البلاغات المغلقة 5 سنوات ثم إخفاء الهوية.',
    'الاستضافة داخل التراب التونسي؛ Firebase للإيقاظ فقط دون معطى شخصي.',
    'التفاصيل: قاموس البيانات وتقييم الأثر (docs/privacy/dpia.md).']),

  h1('7. التحصين (مقيس)', { pageBreak: true }),
  p(`سكريبت infra/security/harden-host.sh يحصّن خادم Ubuntu 24.04 في 14 مجالا، بوضعين (--check يعرض و --apply يطبّق) وملفين شخصيين (demo و prod)، ويعاد تشغيله دون أثر. قيس بـ Lynis و nmap و testssl.sh قبل وبعد (docs/security/hardening-report.html):`),
  table([3400, 2000, 2000, 2238], ['المقياس', 'قبل', 'بعد', 'ملاحظة'], [
    ['مؤشر Lynis', String(L0[0]), String(L0[1]), 'في حاوية دون systemd: حد أدنى'],
    ['ملاحظات Lynis', String(hard.lynis.resolved.length + hard.lynis.remaining.length), String(hard.lynis.remaining.length + hard.lynis.new.length), `${hard.lynis.resolved.length} معالجة`],
    ['منافذ TCP مفتوحة', String((hard.before.nmap_tcp || []).length), String((hard.after.nmap_tcp || []).length), tcpAfter],
    ['بروتوكولات TLS', hard.before.testssl.protocols.join(' و '), hard.after.testssl.protocols.join(' و '), 'لا SSL ولا TLS 1.0/1.1'],
    ['ثغرات TLS معروفة', '0', '0', 'Heartbleed، ROBOT، POODLE…'],
  ]),
  h2('7.1 ما بقي وأين يُعالج'),
  ...ul(['sysctl و auditd و fail2ban و AppArmor: الملفات مكتوبة، وتُفعَّل على خادم حقيقي (الحاوية لا تملك نواة ولا systemd).',
    'أقسام منفصلة لـ /home و /tmp و /var: تُختار عند تنصيب الخادم.',
    'ملاحظات الشهادة في testssl: خاصة بالسلطة المحلية للعرض؛ تُستبدل في الإنتاج بشهادة الديوان أو ACME.',
    'ZAP: فحص الواجهة البرمجية بحساب عون (infra/security/zap/run.sh) على نسخة التجربة، واختبار اختراق خارجي، وتدقيق الوكالة الوطنية للأمن السيبراني.']),
  h2('7.2 الأوامر'),
  code('sudo infra/security/audit.sh before <IP> api.<domain>'),
  code('sudo ADMIN_NET=<admin network> infra/security/harden-host.sh --apply --profile prod'),
  code('sudo infra/security/audit.sh after <IP> api.<domain>'),
  code('python3 infra/security/compare.py audit-before audit-after > hardening.json'),

  h1('8. السجلات والمراقبة والتدقيق'),
  ...ul(['سجل تدقيق إلحاقي مسلسل ببصمات (audit.log)؛ دور التطبيق لا يملك إلا SELECT و INSERT عليه؛ ختم ساعي موقّع Ed25519.',
    'Prometheus بعشر قواعد تنبيه و Alertmanager؛ /metrics برمز ولا يُنشر عبر الحافة.',
    'سجلات الحافة JSON دون عنوان IP ولا X-Forwarded-For؛ سجلات الحاويات محدودة الحجم (daemon.json).',
    'auditd على الخادم: الهوية والصلاحيات و SSH والوقت و Docker وملف .env.']),

  h1('9. النسخ الاحتياطي والاستعادة'),
  ...ul(['نسخة قاعدية يومية مع أرشفة WAL (ehimaya-archive-wal)، سبع نسخ (BACKUP_KEEP=7)، ونسخة مشفّرة في موقع ثان.',
    'تمرين استعادة في CI عند كل طلب دمج: RTO ثانيتان و RPO ثانية في التمرين (الهدف RTO ساعة و RPO 5 دقائق).',
    'دليل التشغيل: docs/runbooks/backup-restore.md، والاستجابة للحوادث: docs/runbooks/incident-response.md.']),

  h1('10. سلسلة التوريد'),
  ...ul(['كل صورة حاوية مثبتة بالبصمة sha256؛ Dependabot يقترح التحديثات وتمر بالفحوص.',
    'Trivy على كل صورة (يفشل البناء عند ثغرة حرجة قابلة للإصلاح)، و pip-audit، وقائمة SBOM بصيغة CycloneDX، وفحص الرخص.',
    'تطبيق الهاتف بمفتاح توقيع واحد دائم محفوظ دون اتصال؛ نسخة «server» تتحدث من خادم الديوان.']),

  h1('11. نموذج التهديدات (STRIDE) و ASVS'),
  table([3000, 6638], ['الحد', 'أهم الضوابط'], [
    ['التطبيق ↔ الواجهة البرمجية', 'TLS، رموز قصيرة، حدود استعمال، عدم التكرار، فحص الوسائط، إثبات العمل للمجهول'],
    ['اللوحة ↔ الواجهة البرمجية', 'TOTP، RLS، CSP صارمة، تدقيق كل اطلاع على معطى شخصي'],
    ['البوابة ↔ الواجهة البرمجية', 'حساب المؤسسة، تأكيد البريد المهني، صلاحيات المؤسسة فقط'],
    ['الواجهة البرمجية ↔ المعطيات', 'دوران، RLS، تشفير الحقول، روابط S3 موقّعة'],
    ['الوسائط والهاتف', 'رموز لكل خطاف، HMAC، مسارات UUID، التسجيل معطّل حتى الترخيص'],
    ['الذكاء الاصطناعي والرؤية', 'خدمات داخلية برموز، دون معطيات إلى الخارج، نماذج برخص مفتوحة'],
    ['Keycloak', '/admin من الشبكة الإدارية فقط، مزوّدان مخصصان مختبران'],
  ]),
  note('التفاصيل: docs/security/threat-model.md و docs/security/asvs-l2.md.'),

  h1('12. قائمة التحقق قبل التشغيل', { pageBreak: true }),
  table([700, 6538, 2400], ['#', 'البند', 'الإثبات'], [
    ['1', 'كل الأسرار في القسم 3 مولّدة ومختلفة عن العرض؛ .env بصلاحية 600 ونسخة مشفّرة في الخزنة', 'إقلاع APP_ENV=production دون رفض'],
    ['2', 'harden-host.sh --apply --profile prod مع ADMIN_NET؛ --check يعيد 0 تغيير', 'مخرجات السكريبت'],
    ['3', 'audit.sh قبل وبعد؛ مؤشر Lynis 80 فأكثر؛ المنافذ مطابقة للقسم 2', 'hardening.json'],
    ['4', 'شهادة الديوان أو ACME؛ testssl دون ملاحظة عالية', 'testssl.json'],
    ['5', 'ZAP على الواجهة البرمجية بحساب عون دون FAIL', 'docs/security/zap-<date>'],
    ['6', 'TOTP مفعّل لكل حساب عون؛ حساب مدير Keycloak الأول معطّل', 'Keycloak'],
    ['7', 'تمرين استعادة على الخادم نفسه', 'سجل التمرين'],
    ['8', 'لا محاكي مفعّل (STREAM_SIM_TOKEN و TELEPHONY_SIM_TOKEN و SMS_PHONE_* فارغة)', 'إقلاع الإنتاج'],
    ['9', 'ترخيص الهيئة الوطنية لحماية المعطيات الشخصية قبل المعطيات الصحية وسجل المواقع', 'الترخيص'],
    ['10', 'اختبار اختراق خارجي وتدقيق الوكالة الوطنية للأمن السيبراني', 'التقريران'],
  ]),
];

save(document({ title: 'الملف التقني والأمني', children }), out);
