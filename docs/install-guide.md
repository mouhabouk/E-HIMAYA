# الدليل التقني لتنصيب ء-حماية وتشغيلها

من تنزيل Ubuntu إلى أول بلاغ على خادم التجربة. يجمع هذا الدليل ما تفرّق في `README.md` و `docs/versions.md` و
`docs/deploy-production.md` و `docs/runbooks/` في مسار واحد مرتّب حسب أولوية التنصيب.

| البند | القيمة |
|---|---|
| الإصدار | 1.0 (مرحلة الجاهزية للتجربة، 2026-10-25) |
| يعتمد على | الفرع `main` بعد دمج طلب الدمج #77 (تطبيق الهاتف 0.9.0، 43 ترحيلا) |
| الجمهور | مهندس النظم الذي يجهّز الخادم، والمطوّر الذي يجهّز جهازه |
| المرجع الأعلى للإصدارات | [`docs/versions.md`](versions.md): إذا اختلف رقم هنا عن رقم هناك فالمعتمد ما في `versions.md` |

> للعمل على حاسوب Windows عبر WSL2 انظر [`docs/install-guide-wsl.md`](install-guide-wsl.md).
>
> الأوامر مكتوبة لـ Ubuntu Server 24.04 LTS. ما يحمل الشارة **[SIM]** محاكاة للتجربة فقط، ولا يُشغَّل في الإنتاج
> (الواجهة البرمجية ترفض الإقلاع إذا وجدت محاكيا مفعّلا مع `APP_ENV=production`).

## 0. خريطة الطريق

| الأولوية | الخطوة | إلزامي؟ | أين يُنفَّذ | القسم |
|---|---|---|---|---|
| 1 | تجهيز العتاد واختيار نوع الخادم | نعم | — | 1 |
| 2 | تنزيل Ubuntu 24.04 والتحقق منه وتثبيته | نعم | الخادم | 2 |
| 3 | تهيئة النظام: التحديثات، المستخدم، SSH، الجدار الناري، الوقت | نعم | الخادم | 3 |
| 4 | Git و OpenSSL و curl | نعم | الخادم وجهاز المطوّر | 4 |
| 5 | Docker Engine 27+ و Compose 2.24+ | نعم | الخادم وجهاز المطوّر | 5 |
| 6 | جلب المشروع وإعداد `.env` والأسرار | نعم | الخادم | 6 |
| 7 | تشغيل المنظومة الأساسية واختبار الدخان | نعم | الخادم | 7 |
| 8 | أول مستخدم إداري في Keycloak | نعم | المتصفح | 8 |
| 9 | الملفات الاختيارية: الذكاء الاصطناعي، الرؤية، البحث، التوجيه، التضاريس | حسب الحاجة | الخادم | 9 |
| 10 | خادم GPU (النماذج الكبيرة) | اختياري | خادم GPU | 10 |
| 11 | النشر في الإنتاج: DNS، TLS، `compose.prod.yml`، المراقبة | للتجربة الميدانية | الخادم | 11 |
| 12 | الهاتف والرسائل القصيرة والإشعارات | بعد الاتفاقيات | الخادم | 12 |
| 13 | النسخ الاحتياطي، تمرين الاستعادة، الترقية | نعم في الإنتاج | الخادم | 13 |
| 14 | بناء تطبيق الهاتف للتوزيع | نعم | جهاز البناء | 14 |
| 15 | أدوات التطوير: Python و uv، Node.js، Flutter | للمطوّر فقط | جهاز المطوّر | 15 |
| 16 | فحوص الجودة والأمن محليا (CI، ZAP، k6) | قبل كل إصدار | جهاز المطوّر | 16 |

القسم 17 يلخّص المتطلبات الوظيفية (الأدوار والمكونات)، والقسم 18 قائمة التحقق النهائية.

## 1. العتاد

| الاستعمال | المعالج | الذاكرة | القرص | ملاحظة |
|---|---|---|---|---|
| جهاز تطوير (المنظومة الأساسية) | 4 أنوية | 16 GB | 100 GB SSD | يكفي لكل شيء عدا الذكاء الاصطناعي الكامل |
| خادم التجربة (الأساسية + البحث + المراقبة) | 4 vCPU (مقاس) إلى 8 vCPU (موصى به) | 16 GB (مقاس 15 GiB) إلى 32 GB | 500 GB SSD | القياس في `infra/loadtest/RESULTS.md`: نحو 16 بلاغ SOS في الثانية، p95 = 328 ms على 4 vCPU |
| مع الذكاء الاصطناعي على المعالج (ملف `cpu`) | 8 vCPU | 32 GB | + 10 GB للنماذج | Whisper medium و Qwen3 4B؛ التنزيل الأول نحو 6 GB |
| خادم GPU (ملف `prod` للنماذج) | 8 vCPU | 32 GB | + 30 GB | بطاقة NVIDIA بذاكرة 24 GB موصى بها لـ Whisper large-v3 و Qwen3 8B معا (تقدير، غير مقاس في المشروع) |

- الوسائط (الصور والفيديو والتسجيلات) تكبر مع الاستعمال: خصّص لمجلد `s3data` قرصا منفصلا قابلا للتوسعة.
- النسخ الاحتياطي يحتاج مساحة تساوي سبع نسخ قاعدية على الأقل (`BACKUP_KEEP=7`)، ويُستحسن موقع ثان مشفر.
- الخادم يحتاج اتصالا بالإنترنت عند البناء الأول (الصور، حزم Maven، النماذج، بيانات الطقس من Open-Meteo).

## 2. تنزيل Ubuntu وتثبيته

### 2.1 الإصدار

**Ubuntu Server 24.04 LTS (Noble Numbat)**، آخر إصدار نقطي متاح (24.04.x)، معمارية amd64. هو الإصدار الذي بُنيت عليه
أوامر المشروع واختبارات CI (حزم PostgreSQL 16 لتمرين الاستعادة مأخوذة منه)، ودعمه الأمني إلى 2029. الإصدار 26.04 LTS
لم يُختبر مع المشروع بعد: لا تستعمله للتجربة الأولى.

| المصدر | الرابط |
|---|---|
| صفحة التنزيل الرسمية | <https://ubuntu.com/download/server> |
| أرشيف الإصدارات وبصمات SHA256 | <https://releases.ubuntu.com/24.04/> |
| دليل التثبيت الرسمي | <https://ubuntu.com/tutorials/install-ubuntu-server> |

### 2.2 التحقق من الملف

```bash
# في مجلد التنزيل، بعد تنزيل ملف ISO و SHA256SUMS من releases.ubuntu.com/24.04/
sha256sum -c SHA256SUMS --ignore-missing      # يجب أن يطبع: ubuntu-24.04.x-live-server-amd64.iso: OK
```

على Windows: `certutil -hashfile ubuntu-24.04.x-live-server-amd64.iso SHA256` وقارن بالسطر المقابل في `SHA256SUMS`.

### 2.3 مفتاح USB للإقلاع (خادم فعلي)

| النظام | الأداة | المصدر |
|---|---|---|
| Windows | Rufus (مخطط GPT، الوضع UEFI) | <https://rufus.ie> |
| Windows / macOS / Linux | balenaEtcher | <https://etcher.balena.io> |
| Linux | `dd` | مدمج |

```bash
lsblk                                   # حدّد اسم المفتاح بدقة (مثلا /dev/sdX) — الأمر التالي يمحو محتواه
sudo dd if=ubuntu-24.04.x-live-server-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

على خادم افتراضي (VMware، Proxmox، Hyper-V، سحابة): حمّل ملف ISO مباشرة في المحطة، أو اختر صورة Ubuntu 24.04 الجاهزة
عند المزوّد.

### 2.4 خيارات المثبّت

| الشاشة | الاختيار |
|---|---|
| اللغة ولوحة المفاتيح | English (لسهولة قراءة رسائل الخطأ)، لوحة مفاتيح حسب الجهاز |
| نوع التثبيت | Ubuntu Server (ليس minimized) |
| الشبكة | عنوان IP ثابت للخادم (من مسؤول الشبكة)، و DNS الداخلي |
| التخزين | القرص كاملا مع LVM؛ إن وُجد قرص ثان فاتركه للبيانات (القسم 3.6) |
| الحساب | مستخدم إداري باسم وظيفي (مثلا `ehimaya`)، وليس `root` |
| SSH | **Install OpenSSH server**، واستيراد المفتاح العام إن وُجد |
| Featured snaps | **لا تختر docker** ولا أي شيء آخر: Docker يُثبَّت من مستودعه الرسمي في القسم 5 (نسخة snap لا تدعم ما يحتاجه المشروع) |

بعد انتهاء التثبيت أزل المفتاح وأعد التشغيل، ثم ادخل بـ SSH من جهاز الإدارة: `ssh ehimaya@<عنوان الخادم>`.

## 3. تهيئة النظام

### 3.1 التحديثات والأدوات الأساسية

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y ca-certificates curl gnupg git openssl unattended-upgrades chrony ufw jq htop python3
sudo dpkg-reconfigure -plow unattended-upgrades     # تحديثات الأمان الآلية: Yes
sudo reboot
```

### 3.2 المنطقة الزمنية والوقت

```bash
sudo timedatectl set-timezone Africa/Tunis
timedatectl                                          # System clock synchronized: yes
```

قاعدة البيانات والتطبيقات تعمل بتوقيت UTC داخليا؛ ضبط الوقت مهم لسلسلة التدقيق والشهادات ورموز TOTP.

### 3.3 SSH

```bash
# من جهاز الإدارة: انسخ مفتاحك إن لم تفعل أثناء التثبيت
ssh-copy-id ehimaya@<عنوان الخادم>
# على الخادم: امنع الدخول بكلمة المرور ودخول root
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### 3.4 الجدار الناري (مرحلة التطوير)

```bash
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow from <شبكة الإدارة>/24 to any port 22 proto tcp
sudo ufw enable && sudo ufw status verbose
```

منافذ الإنتاج تُفتح في القسم 11.3. تنبيه: Docker يكتب قواعده في iptables مباشرة ولا يمر بـ ufw، لذلك المشروع يربط كل
منافذ التطوير بـ `127.0.0.1` فقط، وفي الإنتاج لا يُنشر إلا Caddy ومنافذ الوسائط والهاتف.

### 3.5 إعدادات النواة لـ OpenSearch

```bash
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-ehimaya.conf
sudo sysctl --system
```

### 3.6 قرص البيانات (اختياري، موصى به في الإنتاج)

```bash
lsblk                                               # مثلا /dev/sdb
sudo mkfs.ext4 -L ehimaya-data /dev/sdb
sudo mkdir -p /var/lib/docker
echo 'LABEL=ehimaya-data /var/lib/docker ext4 defaults,noatime 0 2' | sudo tee -a /etc/fstab
sudo mount -a && df -h /var/lib/docker
```

نفّذ هذا قبل تثبيت Docker حتى تُحفظ كل الأحجام (قاعدة البيانات، الوسائط، النسخ) على قرص البيانات.

## 4. Git و OpenSSL

مثبتة في القسم 3.1. تحقق:

```bash
git --version && openssl version                    # OpenSSL 3.x
```

## 5. Docker Engine و Compose

| المكون | الإصدار المطلوب | المصدر |
|---|---|---|
| Docker Engine | 27 أو أحدث | <https://docs.docker.com/engine/install/ubuntu/> |
| Docker Compose (الإضافة v2) | 2.24 أو أحدث (يدعم `!reset` و `!override` في `compose.prod.yml`) | تُثبَّت مع الحزمة `docker-compose-plugin` |

التثبيت من مستودع Docker الرسمي (الطريقة الموصى بها للخوادم):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER                       # ثم اخرج وادخل من جديد
docker --version && docker compose version
docker run --rm hello-world
```

على جهاز تطوير يكفي السكربت المختصر `curl -fsSL https://get.docker.com | sh`. على Windows: Docker Desktop مع WSL2
(<https://docs.docker.com/desktop/setup/install/windows-install/>)، وكل أوامر هذا الدليل تُنفَّذ داخل WSL2.

حدود السجلات (حتى لا يمتلئ القرص):

```bash
echo '{ "log-driver": "json-file", "log-opts": { "max-size": "50m", "max-file": "5" } }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

## 6. جلب المشروع وإعداد `.env`

```bash
sudo mkdir -p /opt/ehimaya && sudo chown $USER: /opt/ehimaya
git clone https://github.com/mouhabouk/E-HIMAYA.git /opt/ehimaya && cd /opt/ehimaya
git checkout main                                   # أو وسم الإصدار المعتمد للتجربة
cp .env.example .env && chmod 600 .env
```

المستودع خاص: يحتاج المستعمل حساب GitHub له صلاحية القراءة، أو مفتاح نشر (Deploy key) للقراءة فقط على الخادم.

### 6.1 توليد الأسرار

كل كلمة مرور وكل سر قيمة عشوائية جديدة؛ لا تُترك أبدا قيمة من `.env.example`:

```bash
for v in POSTGRES_PASSWORD EHIMAYA_DB_PASSWORD EHIMAYA_DB_RUNTIME_PASSWORD KEYCLOAK_DB_PASSWORD KEYCLOAK_ADMIN_PASSWORD \
         VALKEY_PASSWORD NATS_APP_PASSWORD S3_SECRET_KEY TUSD_HOOK_SECRET AI_SERVICE_TOKEN METRICS_TOKEN \
         MEDIAMTX_HOOK_TOKEN MEDIAMTX_API_PASSWORD VISION_API_TOKEN VISION_CALLBACK_TOKEN VISION_READ_PASSWORD \
         OPENSEARCH_ADMIN_PASSWORD OPENSEARCH_PASSWORD TELEPHONY_ARI_PASSWORD; do
  sed -i "s|^$v=.*|$v=$(openssl rand -hex 24)|" .env
done
sed -i "s|^ANON_PSEUDONYM_SECRET=.*|ANON_PSEUDONYM_SECRET=$(openssl rand -hex 32)|" .env
sed -i "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)|" .env
sed -i "s|^CERTIFICATE_SIGNING_KEY=.*|CERTIFICATE_SIGNING_KEY=$(openssl rand -base64 32)|" .env
sed -i "s|^SMS_INBOUND_SECRET=.*|SMS_INBOUND_SECRET=$(openssl rand -hex 32)|" .env
grep -n 'change-me' .env | grep -v '_SIM_\|STREAM_SIM' || echo "لا قيمة مثال متبقية"
```

تبقى ثلاث قيم مثال مقصودة لمحاكيات التطوير **[SIM]**: `STREAM_SIM_TOKEN` و `TELEPHONY_SIM_PASSWORD` و
`TELEPHONY_SIM_TOKEN`. تُترك في جهاز التطوير، وتُفرَّغ على خادم التجربة والإنتاج (القسم 11.2).

| السر | لماذا هو حرج |
|---|---|
| `FIELD_ENCRYPTION_KEY` | يفك تشفير الحقول الحساسة في قاعدة البيانات (الأسماء، الهواتف، الأرقام المهنية). ضياعه = بيانات غير قابلة للقراءة |
| `CERTIFICATE_SIGNING_KEY` | يوقّع شهادات السلامة والمكافآت (Ed25519). تغييره يُبطل التحقق من الشهادات السابقة |
| `ANON_PSEUDONYM_SECRET` | يولّد الأسماء المستعارة للمبلّغين المجهولين. تغييره يقطع الربط بين بلاغات المبلّغ نفسه |

انسخ هذه الأسرار الثلاثة إلى خزنة خارج الخادم (مظروف مختوم أو مدير أسرار) قبل أي بيانات حقيقية.

## 7. تشغيل المنظومة الأساسية

```bash
cd /opt/ehimaya
docker compose --env-file .env -f infra/compose.yml up -d --build
docker compose --env-file .env -f infra/compose.yml ps        # كل الخدمات running أو healthy
python3 infra/smoke/smoke_test.py                            # بلاغ مجهول + رفع بالاستئناف + تحقق البصمة
```

البناء الأول يستغرق من 10 إلى 30 دقيقة (صورة قاعدة البيانات مع PostGIS و pgvector، مزود Keycloak بـ Maven، الواجهة
البرمجية). تطبّق الخلفية الترحيلات الـ 43 آليا، ويستورد Keycloak الفضاءين `ehimaya-public` و `ehimaya-staff`.

| الخدمة | العنوان المحلي (على الخادم نفسه) |
|---|---|
| الواجهة البرمجية ووثائقها | http://localhost:8000/docs |
| فحص الجاهزية | http://localhost:8000/health/ready |
| Keycloak (الإدارة) | http://localhost:8080/admin |
| رفع الوسائط (tus) | http://localhost:1080/api/v1/uploads/ |
| صندوق المحاكاة للإشعارات والرسائل **[SIM]** | http://localhost:8090 |

كل المنافذ على `127.0.0.1`. للاطلاع عليها من جهاز الإدارة استعمل نفق SSH:
`ssh -L 8080:localhost:8080 -L 8000:localhost:8000 ehimaya@<الخادم>`.

الخدمات التي تقوم عليها المنظومة الأساسية:

| الخدمة | الدور |
|---|---|
| PostgreSQL 17 + PostGIS 3.5 + pgvector | كل البيانات، أمان مستوى الصفوف، سلسلة التدقيق |
| Valkey 9.1 | الذاكرة المؤقتة وحدود الطلبات |
| NATS 2.15 JetStream | ناقل الأحداث بين الخدمات |
| SeaweedFS 4.48 | تخزين الوسائط المتوافق مع S3 |
| tusd 2.10.1 | رفع الوسائط بالاستئناف من الهاتف |
| Keycloak 26.8 (صورة `ehimaya/keycloak`) | الهوية: الدخول بالهاتف (OTP)، MFA إجباري للموظفين |
| الواجهة البرمجية (FastAPI، Python 3.12) | منطق العمل، والحلقات الخلفية (`worker`) |
| MediaMTX 1.21.2 | البث المباشر WHIP/WHEP و RTSP و RTMP و HLS |
| Asterisk 22.11 | المقسم الهاتفي (يتصل بالمشغّل في القسم 12) |

## 8. أول مستخدم إداري

1. ادخل إلى http://localhost:8080/admin بحساب `KEYCLOAK_ADMIN` وكلمة مروره من `.env`.
2. اختر الفضاء `ehimaya-staff` ثم Users ثم Add user.
3. حدّد السمة `gouvernorat_code` (مثلا `61` لصفاقس) أو `scope_level = national` للنطاق الوطني.
4. أسند الدور: `sysadmin` لمدير النظام، ثم يُنشئ هو بقية الحسابات (القسم 17.1).
5. في تبويب Credentials عيّن كلمة مرور مؤقتة (Temporary = On).
6. عند أول دخول يغيّر المستخدم كلمة المرور ويفعّل التحقق الثنائي TOTP (Google Authenticator، FreeOTP، Microsoft
   Authenticator).

لا تُنشأ حسابات المواطنين يدويا: يسجّلون من التطبيق برقم الهاتف في الفضاء `ehimaya-public`.

## 9. الملفات الاختيارية

كل ملف يُضاف بـ `--profile` إلى أمر التشغيل نفسه:

| الملف | ما يشغّله | متى تحتاجه | الكلفة |
|---|---|---|---|
| `ai` | خدمة الذكاء الاصطناعي و Ollama | تفريغ المكالمات الصوتية، الترجمة، القراءة المهيكلة للبلاغ، البحث الدلالي | نحو 6 GB نماذج في ملف `cpu`، تُنزَّل مرة واحدة |
| `vision` | خدمة الرؤية (YOLOX، ONNX Runtime) | كشف الحريق والدخان والأشخاص في الصور والبث | معالج فقط |
| `search` | OpenSearch 2.19.6 | البحث في مكتبة الأحداث والذاكرة الوطنية (دائم في الإنتاج) | 1 إلى 2 GB ذاكرة |
| `routing` | Valhalla 3.9.1 + خريطة تونس (Geofabrik) | حساب المسارات والوقت إلى الموقع | تنزيل الخريطة وبناؤها مرة واحدة |
| `terrain` | نموذج التضاريس Copernicus GLO-90 | انتشار الحرائق واتجاه الجريان | نحو 115 MB |
| `sim` **[SIM]** | محاكيات البث والمكالمات | العروض والتجارب فقط | — |
| `monitoring` | Prometheus 3.5 و Alertmanager 0.28.1 و node-exporter 1.9.1 | الإنتاج (القسم 11.6) | خفيف |

```bash
docker compose --env-file .env -f infra/compose.yml --profile ai up -d
docker compose --env-file .env -f infra/compose.yml --profile vision up -d
docker compose --env-file .env -f infra/compose.yml --profile search --profile routing --profile terrain up -d
docker compose --env-file .env -f infra/compose.yml --profile sim up -d          # [SIM] للتجربة فقط
```

النماذج وأصولها ورخصها في `docs/versions.md` (طبقة الذكاء الاصطناعي، الرؤية الحاسوبية). كل النماذج تعمل على خوادمنا ولا
تُرسل أي معطيات إلى خدمة خارجية.

### بيانات الطبقات (أماكن الخدمات على الخريطة)

```bash
python3 scripts/osm_layers.py --out build/osm      # من OpenStreetMap، يحتاج اتصالا بـ overpass-api.de
```

ثم استورد كل ملف في طبقته من لوحة التحكم؛ الأماكن تصل معلَّمة «للتثبت».

منذ المرحلة L1a تُحمَّل طبقات OpenStreetMap المستكملة (`data/osm`، 31 طبقة) دفعة واحدة **مسوداتٍ** لا يراها إلا المدير،
ثم يراجع المدير أسماءها وينشر كل طبقة من صفحة «الطبقات»:

```bash
docker compose --env-file .env -f infra/compose.yml run --rm -v "$PWD/data/osm:/data/osm:ro" worker \
  python -m app.modules.layers.cli load-osm /data/osm --dry-run      # العدّ دون كتابة
docker compose --env-file .env -f infra/compose.yml run --rm -v "$PWD/data/osm:/data/osm:ro" worker \
  python -m app.modules.layers.cli load-osm /data/osm                # أو --only hospitals,beaches
```

الطبقتان الحساستان (الثكنات، النفط والغاز) ليستا في المستودع ولا يحمّلهما الأمر؛ يرفعهما المدير من اللوحة ويوسمهما
«حساسة» فلا يراهما إلا الوزير. الطبقة أو المكان المحذوف يبقى `RETENTION_LAYER_DELETED_DAYS` يومًا (30 افتراضيًا)
قابلا للاسترجاع، ثم تمحوه مهمة الاحتفاظ. قبل وصول القوائم الرسمية يمكن استيراد ملفات
`data/sim-layers` في طبقات معلَّمة «بيانات تقريبية **[SIM]**».

### السلامة الساحلية (المرحلة L1b)

بعد `alembic upgrade head` (0054) ونشر طبقة الشواطئ `osm_beaches`، يحسب العامل خطر الغرق لكل شاطئ كل ساعة من الطقس
البحري. القيم الافتراضية في `.env.example` تكفي:

```bash
MARINE_API_URL=https://marine-api.open-meteo.com   # Open-Meteo Marine، دون مفتاح (CC BY 4.0)
COASTAL_LAYER_KEY=osm_beaches                       # الطبقة التي تُعدّ شواطئ
COASTAL_REFRESH_INTERVAL_S=3600                     # دورة التحديث
COASTAL_MAX_BEACHES_PER_CYCLE=300
RETENTION_COASTAL_PRESENCE_HOURS=24                 # محو «أنا في الشاطئ» المجهول
```

يحتاج الخادم الوصول إلى `marine-api.open-meteo.com` (HTTPS). دون ذلك، أو مع `WEATHER_PROVIDER=sim`، يعمل المحاكي وتظهر
الشاشات بشارة **[SIM]**. تُعدَّل قواعد الخطر وعتباتها من صفحة «السلامة الساحلية» في اللوحة (اللجنة المركزية).

### السجل والتوجيهات (المرحلة L3b)

بعد `alembic upgrade head` (0057) تظهر صفحتا «المخططات والتوصيات» و«التوجيهات والردود» في اللوحة. الملفات المرفقة تُحفظ
في مستودع الكائنات الموجود (المتغيرات `S3_*` نفسها)، حتى 20 م.ب للملف. لا خدمة ولا منفذ ولا دور جديد.

### محاور الكوارث وواجهات القيادة (المرحلة L3)

بعد `alembic upgrade head` (0056) يعمل العامل `crisis` مع بقية العمال. يحتاج فضاء الأعوان الدورين `governor` و `minister`:
يُستورد `infra/keycloak/realms/ehimaya-staff-realm.json` من جديد، أو يُضافان من إدارة Keycloak (Realm roles)، ثم يمنحهما
مسؤول الحسابات من صفحة «الحسابات» مع ولاية للوالي ونطاق وطني للوزير. تواتر تقرير الوضع في الإعدادات الوطنية
(`crisis.sitrep_hours`). لا خدمة ولا منفذ جديد.

### البرامج الموسمية وحماية الدخول (المرحلة L2)

بعد `alembic upgrade head` (0055) تُحمَّل برامج 2026 مسودات، ثم يعتمد مدير العمليات كل برنامج من صفحة «البرامج» فيظهر
على الخريطة بين تاريخيه فقط:

```bash
docker compose --env-file .env -f infra/compose.yml run --rm -v "$PWD/data/programmes:/data/programmes:ro" api \
  python -m app.modules.programmes.cli load /data/programmes/2026/programmes_2026.json --dry-run   # العدّ دون كتابة
docker compose --env-file .env -f infra/compose.yml run --rm -v "$PWD/data/programmes:/data/programmes:ro" api \
  python -m app.modules.programmes.cli load /data/programmes/2026/programmes_2026.json
```

أسماء المشرفين وهواتفهم ليست في الملفات؛ تُدخلها القاعات من اللوحة ولا يراها إلا قاعات العمليات.

حماية الدخول جزء من صورة Keycloak: `docker compose --env-file .env -f infra/compose.yml build keycloak` ثم إعادة تشغيله.
في الفضاءات المستوردة سابقا يُستورد الملفان `infra/keycloak/realms/*.json` من جديد (أو يُختار نموذج
`ehimaya-guarded-password-form` في مسار الدخول وتُضبط «Max login failures» على 10 من إدارة Keycloak). التحقق:
`python3 infra/keycloak/check_login_guard.py http://localhost:8080`.

## 10. خادم GPU (اختياري)

| المكون | المصدر |
|---|---|
| مشغّل NVIDIA (الفرع الموصى به لبطاقتك) | `sudo ubuntu-drivers install` أو <https://www.nvidia.com/Download/index.aspx> |
| NVIDIA Container Toolkit | <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html> |

```bash
sudo ubuntu-drivers install && sudo reboot
nvidia-smi                                         # يجب أن تظهر البطاقة
# ثبّت NVIDIA Container Toolkit حسب الرابط أعلاه، ثم:
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
docker compose --env-file .env -f infra/compose.yml -f infra/compose.gpu.yml --profile ai up -d
```

## 11. النشر في الإنتاج (خادم التجربة الميدانية)

التفاصيل الكاملة في [`docs/deploy-production.md`](deploy-production.md). هذا ملخص الخطوات بالترتيب.

### 11.1 أسماء DNS

خمسة أسماء تشير إلى عنوان الخادم العمومي (أو الداخلي إذا كانت التجربة على شبكة الديوان فقط):

| الاسم (مثال) | الدور |
|---|---|
| `api.ehimaya.tn` | الواجهة البرمجية، رفع الوسائط، هاتف المشغّل عبر WebSocket |
| `dashboard.ehimaya.tn` | لوحة التحكم المركزية والجهوية |
| `portal.ehimaya.tn` | بوابة المؤسسات والتحقق من الشهادات |
| `auth.ehimaya.tn` | Keycloak |
| `media.ehimaya.tn` | البث المباشر |

### 11.2 إعدادات `.env` الإضافية

```dotenv
# APP_ENV=production يضبطه compose.prod.yml نفسه
API_HOST=api.ehimaya.tn
DASHBOARD_HOST=dashboard.ehimaya.tn
PORTAL_HOST=portal.ehimaya.tn
AUTH_HOST=auth.ehimaya.tn
MEDIA_HOST=media.ehimaya.tn
CADDY_TLS=ops@ehimaya.tn                     # بريد ACME؛ أو internal لعرض دون أسماء حقيقية
TUSD_CORS_ORIGIN_REGEX=^https://(dashboard|portal)\.ehimaya\.tn$
KEYCLOAK_ADMIN_ALLOW=10.20.0.0/16             # الشبكات التي تفتح إدارة Keycloak
STREAM_SIM_TOKEN=                             # المحاكاة ممنوعة في الإنتاج
TELEPHONY_SIM_PASSWORD=
TELEPHONY_SIM_TOKEN=
ENVIRONMENT_BANNER=auto                       # لا شريط في الإنتاج؛ pilot لخادم التجربة، training للتدريب
```

`ENVIRONMENT_BANNER` يُظهر شريطا كهرمانيا **[SIM]** أعلى اللوحة والبوابة والتطبيق يسمّي البيئة، حتى لا يخلط المشغّل
بين بيانات التجربة والبيانات الحقيقية. على خادم التجربة الميدانية ضع `pilot`، وعلى خادم التدريب `training`.

في Keycloak حدّث Valid redirect URIs و Web origins للعميلين `ehimaya-dashboard` و `ehimaya-portal` إلى
`https://DASHBOARD_HOST/*` و `https://PORTAL_HOST/*`.

### 11.3 الجدار الناري للإنتاج

```bash
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp     # Caddy، HTTP/3
sudo ufw allow 8189/udp                                                       # وسائط WebRTC
sudo ufw allow from <شبكة الكاميرات والطائرات> to any port 8554 proto tcp     # RTSP
sudo ufw allow from <شبكة الكاميرات والطائرات> to any port 1935 proto tcp     # RTMP
# الهاتف (القسم 12)، من عناوين SBC المشغّل فقط:
sudo ufw allow from <SBC المشغّل> to any port 5060,5061 proto tcp
sudo ufw allow from <SBC المشغّل> to any port 5060 proto udp
sudo ufw allow 10000:10099/udp                                                # RTP
```

### 11.4 التشغيل

```bash
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d --build --wait
```

ترتيب الإقلاع: `postgres` ثم `db-roles` ثم `migrate` ثم `api` و `worker` ثم `caddy`. الواجهة البرمجية ترفض الإقلاع إذا
بقي أي سر قيمة مثال أو أقصر من 16 حرفا، وتسمّي الإعداد المعني دون أن تطبع قيمته.

### 11.5 فحوص بعد النشر

```bash
curl -fsS https://api.ehimaya.tn/health/ready                                   # 200 و "status": "ok"
curl -s -o /dev/null -w '%{http_code}\n' https://api.ehimaya.tn/docs           # 404 (الوثائق مخفية في الإنتاج)
curl -s -o /dev/null -w '%{http_code}\n' https://api.ehimaya.tn/metrics        # 404 من الخارج
curl -sI https://dashboard.ehimaya.tn/ | grep -iE 'strict-transport|content-security'
API_URL=https://api.ehimaya.tn TUS_URL=https://api.ehimaya.tn/api/v1/uploads/ NOTIFY_SIM_URL= \
  python3 infra/smoke/smoke_test.py
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml run --rm worker \
  python -m app.modules.knowledge.cli backfill --rebuild                        # فهرسة مكتبة الأحداث أول مرة
```

### 11.6 المراقبة

```bash
mkdir -p infra/monitoring/secrets
grep '^METRICS_TOKEN=' .env | cut -d= -f2- > infra/monitoring/secrets/metrics_token
grep '^MEDIAMTX_API_PASSWORD=' .env | cut -d= -f2- > infra/monitoring/secrets/mediamtx_api_password
chmod 0400 infra/monitoring/secrets/*
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml --profile monitoring up -d
```

قواعد التنبيه في `infra/monitoring/alerts.yml` (منها `WalArchiveLag` و `BaseBackupMissing`)، ووجهة الإشعار في
`infra/monitoring/alertmanager.yml`.

## 12. الهاتف والرسائل القصيرة والإشعارات

كل قناة اختيارية: دون إعداداتها تُسجَّل عمليات الإرسال «متجاوزة» وتواصل القنوات الأخرى عملها.

| القناة | ما يلزم | الإعدادات في `.env` | المرجع |
|---|---|---|---|
| الرسائل القصيرة الصادرة | عقد مع مزود تونسي | `SMS_HTTP_URL`، `SMS_HTTP_TOKEN`، `SMS_SENDER` | `docs/api/notify-sim.md` |
| الرسائل الواردة (البلاغ بالـ SMS) | المزود يرسل إلى `https://API_HOST/internal/sms/inbound` | `SMS_INBOUND_SECRET` (يُسلَّم للمزود) | `docs/deploy-production.md` §9 |
| إشعارات الدفع | مشروع Firebase وحساب خدمة | `FCM_SERVICE_ACCOUNT` (base64)، وفي بناء التطبيق `FIREBASE_*` | `docs/api/notify-sim.md` |
| البريد | خادم SMTP | `SMTP_HOST`، `SMTP_USERNAME`، `SMTP_PASSWORD` | — |
| الخط الهاتفي 8000 | خط SIP من المشغّل (Tunisie Telecom أو Ooredoo أو Orange) | `TELEPHONY_TRUNK_*`، ثم `TELEPHONY_TRUNK_ENABLED=true` | `docs/telephony.md` |

قيود تنظيمية قائمة:

- تسجيل المكالمات معطّل افتراضيا (`TELEPHONY_RECORDING_ENABLED=false`) إلى أن يُصرَّح بالمعالجة لدى الهيئة الوطنية لحماية
  المعطيات الشخصية.
- التحويل إلى 198 معطّل (`TELEPHONY_TRANSFER_198_ENABLED=false`) إلى حين توقيع الاتفاقية مع المشغّل والحماية المدنية.
- أرقام النجدة في التطبيق تبقى دائما مكالمة عادية عبر شريحة الهاتف.

## 13. النسخ الاحتياطي والاستعادة والترقية

### 13.1 النسخ الاحتياطي

يعمل آليا في الإنتاج (`docs/runbooks/backup-restore.md`): أرشفة WAL كل دقيقة على الأكثر، ونسخة قاعدية كل ليلة في
`BACKUP_HOUR`، مع الاحتفاظ بـ `BACKUP_KEEP` نسخ. الهدف: خسارة 5 دقائق على الأكثر (RPO)، والعودة في ساعة (RTO).

```dotenv
BACKUP_HOUR=01               # بتوقيت UTC
BACKUP_KEEP=7
BACKUP_REMOTE=               # موقع ثان عبر rclone (remote:path)، مشفر
```

إضافة إلى ذلك احفظ خارج الخادم: ملف `.env`، والأسرار الثلاثة في القسم 6.1، ونسخة من قاعدة Keycloak.

### 13.2 التحقق اليومي وتمرين الاستعادة

- يوميا (دقيقتان): لا تنبيه `WalArchiveLag` أو `BaseBackupMissing`، وسجل `backup` يذكر نسخة الليلة.
- كل ثلاثة أشهر (30 دقيقة): `sh infra/backup/drill.sh` على جهاز به PostgreSQL 16 و PostGIS و pgvector، ويجب أن ينتهي
  بـ `DRILL PASSED`، ثم استعادة نسخة حقيقية على خادم تجريبي حسب الدليل.

### 13.3 الترقية

```bash
cd /opt/ehimaya && git pull
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml build
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml run --rm migrate
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d --wait
```

الرجوع إلى إصدار سابق: `git checkout <وسم>` ثم البناء والتشغيل؛ والترحيلات قابلة للتراجع
(`run --rm migrate alembic downgrade <revision>`)، لكن جرّب ذلك على نسخة قبل الإنتاج. عند حادث: `docs/runbooks/incident-response.md`.

## 14. بناء تطبيق الهاتف للتوزيع

يحتاج جهاز البناء أدوات القسم 15.3. الإصدار الحالي 0.9.0 (البناء 8).

### 14.1 مفتاح التوقيع (مرة واحدة، يُحفظ إلى الأبد)

```bash
keytool -genkeypair -v -keystore ~/ehimaya-release.jks -keyalg RSA -keysize 4096 -validity 10000 -alias ehimaya
cat > apps/mobile/android/key.properties <<'EOF'
storeFile=/home/<user>/ehimaya-release.jks
storePassword=<كلمة المرور>
keyAlias=ehimaya
keyPassword=<كلمة المرور>
EOF
```

`key.properties` والمفتاح لا يُحفظان في المستودع. ضياع المفتاح يمنع تحديث التطبيق المثبت عند المواطنين.

### 14.2 البناء بعناوين الخادم

```bash
cd apps/mobile && flutter pub get
flutter build apk --release --flavor citizen \
  --dart-define=API_BASE_URL=https://api.ehimaya.tn \
  --dart-define=TUS_URL=https://api.ehimaya.tn/api/v1/uploads/ \
  --dart-define=OIDC_ISSUER=https://auth.ehimaya.tn/realms/ehimaya-public \
  --dart-define=SMS_REPORT_NUMBER=<رقم البلاغ بالرسائل> \
  --dart-define=FIREBASE_API_KEY=... --dart-define=FIREBASE_APP_ID=... \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=... --dart-define=FIREBASE_PROJECT_ID=...
# الملف: build/app/outputs/flutter-apk/app-citizen-release.apk
flutter build appbundle --release --flavor citizen ...   # للنشر في Google Play (نفس المعاملات)
```

لا تمرّر `PUSH_SIMULATOR_URL` في بناء التوزيع (هو محاكي **[SIM]**). للتجربة الميدانية يوزَّع ملف APK على هواتف المشاركين،
أو عبر مسار الاختبار الداخلي في Google Play.

**تطبيق الأعوان (P4a)** يُبنى من نفس المشروع بنقطة دخوله، ويوزَّع على قادة الفرق ومفقّدي الوقاية (منذ P4c). منذ P4d هو
تطبيق مستقل على أندرويد (النكهة `staff`، المعرّف `tn.ehimaya.staff`، الاسم «ء-حماية الأعوان») يُثبَّت بجانب تطبيق المواطن:

```bash
flutter build apk --release --flavor staff -t lib/main_staff.dart \
  --dart-define=API_BASE_URL=https://api.ehimaya.tn \
  --dart-define=STAFF_OIDC_ISSUER=https://auth.ehimaya.tn/realms/ehimaya-staff \
  --dart-define=STAFF_ROOM_PHONE=198 \
  --dart-define=STAFF_SMS_NUMBER=<رقم بوابة الرسائل> \
  --dart-define=FIREBASE_API_KEY=... --dart-define=FIREBASE_APP_ID=<معرّف تطبيق الأعوان في Firebase> \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=... --dart-define=FIREBASE_PROJECT_ID=...
# الملف: build/app/outputs/flutter-apk/app-staff-release.apk
```

منذ P4d: `STAFF_SMS_NUMBER` رقم بوابة الرسائل نفسها (إن تُرك فارغًا يُستعمل `SMS_REPORT_NUMBER`، وإن غاب الاثنان يختفي زر
«أرسل برسالة قصيرة»). يُسجَّل تطبيق الأعوان في مشروع Firebase نفسه كتطبيق أندرويد ثانٍ بالمعرّف `tn.ehimaya.staff`، ويُمرَّر
`FIREBASE_APP_ID` الخاص به. يطلب التطبيق إذن «الإشعارات بملء الشاشة» لتظهر المهمة على شاشة القفل، ويتابع موقع المركبة أثناء
المهمة فقط بخدمة أمامية ظاهرة. تحتفظ قاعدة البيانات بمواقع المركبات `RETENTION_CREW_POSITION_DAYS` يومًا (30 افتراضيًا).

`STAFF_ROOM_PHONE` (منذ P4b) هو رقم القاعة الذي يطلبه زر «اتصال بالقاعة» في شاشة المهمة، والقيمة الافتراضية 198.
يحتاج التطبيق إذنَي الكاميرا والميكروفون للصور والملاحظات الصوتية من الميدان (مصرَّح بهما من قبل في تطبيق المواطن).

يدخل القائد بالرمز الظاهر على الهاتف من صفحة Keycloak (كلمة السر والرمز الثاني)، ثم يختار رمز PIN. يمنح مسؤول الحسابات
الجهوي الدور `team_leader`، ويسحب الهاتف عند ضياعه من صفحة «فرق المناوبة» في اللوحة (مسح عن بعد).

منذ P4c يدخل المفقّد (الدور `org_auditor` بولاية محدّدة) التطبيق نفسه بالطريقة نفسها، فيرى «زيارات الوقاية» مباشرة؛ من له
الدوران يرى المناوبة وزرا إلى الزيارات. الزيارات المنزّلة ومسوداتها وصورها تُحفظ في مجلد التطبيق الخاص مشفّرة
(AES-256-GCM بمفتاح في مخزن الهاتف الآمن)، وتُمحى مع المسح عن بعد أو الخروج. المفقّد على المستوى الوطني (دون ولاية)
لا يسجّل هاتفا في هذه المرحلة.

### 14.3 لوحة التحكم والبوابة

لا تُبنيان يدويا في الإنتاج: `compose.prod.yml` يبني صورتين ثابتتين بـ Caddy مع سياسة CSP محسوبة من الإعداد. للتطوير:
القسم 15.2.

## 15. أدوات التطوير (جهاز المطوّر فقط)

### 15.1 Python 3.12 و uv (الخلفية والخدمات)

| الأداة | الإصدار | المصدر |
|---|---|---|
| uv | 0.13.4 | <https://docs.astral.sh/uv/> |
| Python | 3.12 (عبر uv) | <https://www.python.org/downloads/> |

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
cd services/api && uv sync
export DATABASE_URL=postgresql+asyncpg://ehimaya:<كلمة المرور>@localhost:5432/ehimaya
export ANON_PSEUDONYM_SECRET=$(openssl rand -hex 32) FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)
uv run alembic upgrade head
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run uvicorn app.main:app --reload
```

### 15.2 Node.js 22 LTS (لوحة التحكم والبوابة)

| الأداة | الإصدار | المصدر |
|---|---|---|
| nvm | 0.40.3 | <https://github.com/nvm-sh/nvm> |
| Node.js | 22 LTS مع npm 10+ | <https://nodejs.org> |

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && . ~/.nvm/nvm.sh
nvm install 22
cd apps/dashboard && npm ci && npm run dev          # http://localhost:5173
cd apps/portal    && npm ci && npm run dev          # http://localhost:5174
npm run lint && npm run typecheck && npm test && npm run build
npx playwright install chromium && npm run test:e2e
```

### 15.3 Flutter و Java و Android SDK (تطبيق الهاتف)

| الأداة | الإصدار | المصدر |
|---|---|---|
| Flutter (القناة المستقرة) | 3.47.7 مع Dart 3.13.5 | <https://docs.flutter.dev/get-started/install/linux/android> |
| Java (OpenJDK) | 17 | `sudo apt install -y openjdk-17-jdk` |
| Android Studio و Android SDK | الإصدار الحالي | <https://developer.android.com/studio> |

```bash
sudo apt install -y openjdk-17-jdk clang cmake ninja-build pkg-config libgtk-3-dev
# نزّل Flutter 3.47.7 من الرابط أعلاه وفك ضغطه في ~/flutter، ثم:
echo 'export PATH="$HOME/flutter/bin:$PATH"' >> ~/.bashrc && . ~/.bashrc
flutter --version                                   # Flutter 3.47.7 • Dart 3.13.5
flutter doctor --android-licenses && flutter doctor
cd apps/mobile && flutter pub get && flutter analyze && flutter test
adb reverse tcp:8000 tcp:8000 && adb reverse tcp:8080 tcp:8080 && adb reverse tcp:1080 tcp:1080
flutter run --dart-define=API_BASE_URL=http://localhost:8000 \
  --dart-define=TUS_URL=http://localhost:1080/api/v1/uploads/ \
  --dart-define=OIDC_ISSUER=http://localhost:8080/realms/ehimaya-public
```

### 15.4 مزود Keycloak دون Docker (اختياري)

JDK 21 و Maven 3.9، ثم `mvn -f infra/keycloak/providers/phone-otp/pom.xml verify` (44 اختبارا).

## 16. فحوص الجودة والأمن قبل كل إصدار

| الفحص | الأمر | النتيجة المنتظرة |
|---|---|---|
| كل مهام CI محليا | `scripts/ci-local.sh --keep-going` | تقرير `ci-local-report.md`، لا مهمة FAILED |
| قائمة المهام | `scripts/ci-local.sh --list` | — |
| فحص الأمن الديناميكي (OWASP ZAP 2.16.1) | `infra/security/zap/run.sh` | لا تنبيه عالي الخطورة خارج الاستثناءات الموثقة في `rules.tsv` |
| اختبار الحمل (k6 2.3.0) | انظر `infra/loadtest/` | p95 تحت الحد في `RESULTS.md` |
| تمرين الاستعادة | `sh infra/backup/drill.sh` | `DRILL PASSED` |

التكامل المستمر على GitHub يشغّل 27 فحصا لكل طلب دمج؛ إذا تعذّر (حد الفوترة) فـ `ci-local.sh` هو البديل، أو مُشغّل ذاتي
الاستضافة (`docs/self-hosted-runner.md`).

## 17. المتطلبات الوظيفية

### 17.1 الأدوار

**فضاء الموظفين `ehimaya-staff`** (لوحة التحكم، التحقق الثنائي إجباري):

| الدور | المهمة |
|---|---|
| `operator` | مشغّل غرفة العمليات: استقبال البلاغات والمكالمات وفرزها |
| `ops_manager` | مسؤول العمليات: التوجيه والمتابعة والقرار |
| `field_commander` | قائد ميداني |
| `local_committee` / `central_committee` | اللجنة الجهوية / الوطنية؛ الوطنية (ومسؤول العمليات الوطني) تحرر قوالب التقارير المفصّلة وتعتمدها (P4b) |
| `org_auditor` | مراجعة المؤسسات وملفاتها، وزيارات الوقاية من اللوحة ومن تطبيق الأعوان (منذ P4c: الشبكة في الموقع والصور والتوقيعان والقرار) |
| `content_editor` | دليل الطوارئ والمحتوى التوعوي |
| `medical_coordinator` | المنسّق الطبي الجهوي (محور الأطباء) |
| `team_leader` | قائد فريق التدخل: تطبيق الأعوان فقط (المناوبة، المهام، تقارير الوضع، النجدة والخطر، الصور والصوت، الإصابات والنقل، التقرير المفصّل)، لا يفتح اللوحة |
| `regional_account_admin` | مسؤول الحسابات الجهوية |
| `sysadmin` / `security_admin` / `ai_admin` | إدارة النظام / الأمن / نماذج الذكاء الاصطناعي |

**الفضاء العمومي `ehimaya-public`** (التطبيق والبوابة):

| الدور | المهمة |
|---|---|
| `citizen` | المواطن: البلاغ، السلامة الشخصية، الإشعارات |
| `volunteer` | المتطوع والطبيب المتطوع |
| `org_admin` / `org_member` | مسؤول المؤسسة وأعضاؤها في البوابة |

### 17.2 المكونات الوظيفية

| المكون | ما يقدّمه |
|---|---|
| تطبيق الهاتف (Flutter، ar/fr/en) | البلاغ مع الصور والصوت والموقع ولو دون اتصال، البلاغ المجهول، SOS، البث المباشر، دليل الطوارئ، الأقرب إليّ، جهات الطوارئ وفحص السلامة، الملف الطبي المقفل، فضاء الأطباء |
| لوحة التحكم (React، ar/fr/en) | الخريطة الحية، فرز البلاغات، الهاتف الشبكي للمشغّل، البث، الطقس وخطر الحرائق، التحليلات، الذاكرة الوطنية، إدارة الطبقات والحسابات الجهوية |
| بوابة المؤسسات (React) | ملف المؤسسة، الشهادات والتحقق منها بالبصمة |
| الخلفية | 300 مسار و 362 عملية، أمان مستوى الصفوف، سجل تدقيق متسلسل، تشفير الحقول الحساسة |

المتطلبات التفصيلية في [`docs/01-requirements.html`](01-requirements.html) والهيكلة في
[`docs/02-architecture.html`](02-architecture.html).

### 17.3 ما يجب أن يوفّره الديوان قبل التجربة

| المُدخل | لماذا |
|---|---|
| خادم (القسم 1) وعنوان IP ثابت | تشغيل المنظومة |
| خمسة أسماء DNS وبريد ACME | TLS والدخول الآمن |
| قائمة المستخدمين وأدوارهم وولاياتهم | إنشاء الحسابات (القسم 8) |
| قوائم المستشفيات والمراكز والصيدليات الرسمية | استبدال بيانات **[SIM]** في الطبقات |
| عقد مزود الرسائل القصيرة، ومشروع Firebase | القنوات (القسم 12) |
| خط SIP من المشغّل (اختياري في البداية) | الخط 8000 |
| تصريح الهيئة الوطنية لحماية المعطيات الشخصية | تسجيل المكالمات والمعالجة |

## 18. قائمة التحقق النهائية

- [ ] Ubuntu 24.04 محدّث، الوقت متزامن، SSH بالمفاتيح فقط، الجدار الناري مفعّل.
- [ ] `docker compose version` ≥ 2.24، و `hello-world` يعمل.
- [ ] `.env` بصلاحية 600، ولا قيمة `change-me` (ولا قيمة لمحاكي في الإنتاج)، والأسرار الثلاثة محفوظة خارج الخادم.
- [ ] `smoke_test.py` ناجح.
- [ ] أول مدير نظام دخل وفعّل TOTP.
- [ ] في الإنتاج: `/health/ready` = 200، `/docs` = 404، رؤوس HSTS و CSP حاضرة.
- [ ] المراقبة تعمل، ونسخة الليلة الأولى موجودة.
- [ ] تمرين الاستعادة `DRILL PASSED`.
- [ ] ملف APK موقّع بعناوين الخادم ومثبت على هاتف تجربة، وبلاغ تجريبي وصل إلى اللوحة.
- [ ] `scripts/ci-local.sh` و `infra/security/zap/run.sh` دون فشل.
