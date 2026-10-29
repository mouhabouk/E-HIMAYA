# دليل تنصيب ء-حماية على Windows عبر WSL2

يشرح هذا الدليل تشغيل المشروع كاملا على حاسوب يعمل بنظام Windows، داخل Ubuntu 24.04 مثبت عبر WSL2، من أول تنزيل إلى
أول بلاغ على تطبيق الهاتف. هو مكمّل لـ [`docs/install-guide.md`](install-guide.md) (دليل الخادم): ما يتطابق بين البيئتين
لا يُعاد هنا ويُشار إلى قسمه.

| البند | القيمة |
|---|---|
| الإصدار | 1.0 (2026-10-25) |
| يعتمد على | الفرع `main` بعد دمج طلب الدمج #78 |
| الاستعمال | التطوير والعروض والتجارب المكتبية **[SIM]**. لا يصلح لخادم التجربة الميدانية ولا للإنتاج (القسم 15) |
| المرجع الأعلى للإصدارات | [`docs/versions.md`](versions.md) |

> الأوامر التي تبدأ بـ `PS>` تُنفَّذ في PowerShell على Windows (بصلاحية المسؤول حين يُذكر ذلك)، والأوامر التي تبدأ بـ `$`
> تُنفَّذ في طرفية Ubuntu داخل WSL.

## 0. خريطة الطريق وأولوية التنصيب

| الأولوية | الخطوة | أين | إلزامي؟ | القسم |
|---|---|---|---|---|
| 1 | التحقق من الجهاز: Windows، المعالج، الذاكرة، القرص، المحاكاة الافتراضية | Windows | نعم | 1 |
| 2 | تفعيل WSL2 وتثبيت Ubuntu 24.04 | Windows | نعم | 2 |
| 3 | ضبط موارد WSL (`.wslconfig`) والشبكة | Windows | نعم | 3 |
| 4 | تهيئة Ubuntu: التحديثات، systemd، Git | WSL | نعم | 4 |
| 5 | Docker Engine داخل WSL | WSL | نعم | 5 |
| 6 | جلب المشروع، الأسرار، تشغيل المنظومة، اختبار الدخان | WSL | نعم | 6 |
| 7 | أول مستخدم إداري في Keycloak | متصفح Windows | نعم | 7 |
| 8 | محرر الشيفرة: VS Code مع إضافة WSL | Windows | موصى به | 8 |
| 9 | أدوات الخلفية والواجهات: uv و Python 3.12، Node.js 22 | WSL | للتطوير | 9 |
| 10 | تطبيق الهاتف: Flutter و Android Studio على Windows، والاتصال بالمنظومة | Windows | للتطبيق | 10 |
| 11 | الملفات الاختيارية: الرؤية، البحث، الذكاء الاصطناعي، GPU | WSL | حسب الجهاز | 11 |
| 12 | التشغيل اليومي والإيقاف وتنظيف القرص | الاثنان | — | 12 |
| 13 | حل المشكلات الشائعة | — | — | 13 |

القسم 14 يجمع التوصيات الفنية، والقسم 15 حدود هذه البيئة، والقسم 16 المتطلبات الوظيفية، والقسم 17 قائمة التحقق.

## 1. التحقق من الجهاز

### 1.1 المتطلبات

| المكون | الأدنى | الموصى به | لماذا |
|---|---|---|---|
| Windows | Windows 10 22H2 (البناء 19045) 64 بت | Windows 11 23H2 أو أحدث | الشبكة المعكوسة (mirrored) و systemd وتحرير الذاكرة آليا تعمل كاملة على Windows 11 |
| المعالج | 4 أنوية مع دعم المحاكاة (Intel VT-x أو AMD-V) | 8 أنوية أو أكثر | المنظومة الأساسية نحو 15 حاوية |
| الذاكرة | 16 GB | 32 GB | المنظومة الأساسية تستهلك نحو 6 إلى 8 GB داخل WSL؛ الذكاء الاصطناعي يحتاج 8 GB إضافية |
| القرص | 120 GB فارغة على SSD | 250 GB على SSD، على قرص غير قرص النظام إن وُجد | الصور والأحجام والنماذج و Android SDK |
| بطاقة الرسوم | — | NVIDIA بذاكرة 8 GB أو أكثر | اختيارية لتسريع الذكاء الاصطناعي (القسم 11.3) |
| الشبكة | اتصال بالإنترنت | اتصال مباشر دون VPN أثناء التثبيت | تنزيل نحو 10 GB عند البناء الأول |

### 1.2 أوامر التحقق

```powershell
PS> winver                                                         # رقم الإصدار والبناء
PS> Get-ComputerInfo -Property OsName,OsVersion,CsNumberOfLogicalProcessors,CsTotalPhysicalMemory
PS> Get-PSDrive -PSProvider FileSystem                             # المساحة الفارغة في كل قرص
PS> (Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled  # True = المحاكاة مفعلة في BIOS
```

إذا كانت النتيجة الأخيرة `False`: أعد تشغيل الجهاز وادخل إلى BIOS/UEFI (عادة F2 أو Del أو F10)، وفعّل
Intel Virtualization Technology (VT-x) أو SVM Mode لمعالجات AMD، ثم احفظ. في مدير المهام، تبويب الأداء ← المعالج، يجب أن
يظهر «المحاكاة الافتراضية: ممكّنة».

## 2. تثبيت WSL2 و Ubuntu 24.04

| المكون | الإصدار | المصدر |
|---|---|---|
| WSL (Windows Subsystem for Linux) | 2.x، أحدث إصدار عبر `wsl --update` | <https://learn.microsoft.com/windows/wsl/install> |
| Ubuntu | 24.04 LTS (الاسم في WSL: `Ubuntu-24.04`) | <https://ubuntu.com/desktop/wsl> و Microsoft Store |

في PowerShell **بصلاحية المسؤول**:

```powershell
PS> wsl --install -d Ubuntu-24.04
```

يفعّل هذا الأمر الميزتين المطلوبتين في Windows، وينزّل نواة WSL2، ويثبّت Ubuntu 24.04. أعد تشغيل الجهاز حين يُطلب منك.
عند أول فتح لـ Ubuntu (من قائمة ابدأ) أنشئ اسم مستخدم بالحروف اللاتينية الصغيرة (مثلا `yamen`) وكلمة مرور تحفظها.

ثم تحقق:

```powershell
PS> wsl --update
PS> wsl --set-default-version 2
PS> wsl -l -v            # يجب أن يظهر: Ubuntu-24.04   Running/Stopped   2
PS> wsl --version        # إصدار WSL والنواة
```

إذا ظهر Ubuntu بالإصدار 1: `wsl --set-version Ubuntu-24.04 2`.

### 2.1 نقل Ubuntu إلى قرص آخر (موصى به إذا كان C: صغيرا)

القرص الافتراضي لـ Ubuntu (`ext4.vhdx`) يكبر مع الصور والبيانات. لنقله إلى `D:`، قبل تثبيت أي شيء آخر:

```powershell
PS> wsl --shutdown
PS> mkdir D:\WSL
PS> wsl --manage Ubuntu-24.04 --move D:\WSL\Ubuntu-24.04
```

إذا لم يتعرف إصدار WSL لديك على `--move`، استعمل التصدير ثم الاستيراد:

```powershell
PS> wsl --export Ubuntu-24.04 D:\WSL\ubuntu.tar
PS> wsl --unregister Ubuntu-24.04
PS> wsl --import Ubuntu-24.04 D:\WSL\Ubuntu-24.04 D:\WSL\ubuntu.tar --version 2
PS> ubuntu2404.exe config --default-user yamen      # اسم المستخدم الذي أنشأته
```

## 3. ضبط موارد WSL والشبكة

أنشئ الملف `C:\Users\<اسمك>\.wslconfig` (بالمفكرة، دون امتداد `.txt`):

```ini
[wsl2]
# 10GB on a 16 GB PC, 20GB on a 32 GB PC
memory=10GB
processors=6
swap=8GB
# Windows 11 22H2 or later only
networkingMode=mirrored
dnsTunneling=true
autoProxy=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
```

- `memory`: نصف ذاكرة الجهاز إلى ثلثيها تقريبا (10GB لجهاز 16 GB، و 20GB لجهاز 32 GB)، و `processors` ثلاثة أرباع الأنوية.
- `networkingMode=mirrored`: يتشارك Windows و WSL عنوان `localhost`، فيصل المتصفح والهاتف (عبر `adb`) إلى المنظومة مباشرة.
- `dnsTunneling` و `autoProxy`: يحلّان أغلب مشكلات الاتصال خلف VPN أو وكيل المؤسسة.
- `autoMemoryReclaim` و `sparseVhd`: يعيدان الذاكرة غير المستعملة إلى Windows، ويقلّصان القرص الافتراضي آليا.

ثم طبّق الإعدادات (تسري عند الفتح التالي):

```powershell
PS> wsl --shutdown
```

على Windows 10 احذف السطور `networkingMode` و `dnsTunneling` و `autoProxy`: يبقى توجيه `localhost` من Windows إلى WSL
يعمل افتراضيا.

## 4. تهيئة Ubuntu

```bash
$ sudo apt update && sudo apt full-upgrade -y
$ sudo apt install -y ca-certificates curl gnupg git openssl jq python3 unzip build-essential
$ cat /etc/wsl.conf          # يجب أن يحتوي [boot] ثم systemd=true
```

إذا لم يكن systemd مفعلا:

```bash
$ printf '[boot]\nsystemd=true\n\n[interop]\nappendWindowsPath=false\n' | sudo tee /etc/wsl.conf
```

ثم من PowerShell: `wsl --shutdown` وأعد فتح Ubuntu. `appendWindowsPath=false` يمنع تداخل أدوات Windows (مثل `node`
أو `python` المثبتة على Windows) مع أدوات Ubuntu.

### 4.1 Git ونهايات الأسطر

```bash
$ git config --global user.name "Yamen"
$ git config --global user.email "<بريدك>"
$ git config --global core.autocrlf input      # لا تحويل إلى CRLF داخل Linux
$ git config --global init.defaultBranch main
```

على Windows (لنسخة تطبيق الهاتف في القسم 10) ثبّت Git for Windows واضبط: `git config --global core.autocrlf true`.
سكربتات `.sh` المحفوظة بنهايات CRLF تفشل داخل Linux برسالة `bad interpreter`.

### 4.2 المستودع خاص: الدخول إلى GitHub

```bash
$ ssh-keygen -t ed25519 -C "<بريدك>"       # اضغط Enter للمسار الافتراضي، وضع عبارة مرور
$ cat ~/.ssh/id_ed25519.pub                # انسخه إلى GitHub ← Settings ← SSH and GPG keys ← New SSH key
$ ssh -T git@github.com                    # Hi mouhabouk! ...
```

## 5. Docker داخل WSL

### 5.1 الخيار الموصى به: Docker Engine داخل Ubuntu

لا يحتاج Docker Desktop ولا رخصته، ويطابق خادم الإنتاج تماما. الأوامر نفسها المعتمدة للخادم (القسم 5 من دليل الخادم):

```bash
$ sudo install -m 0755 -d /etc/apt/keyrings
$ sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
$ sudo chmod a+r /etc/apt/keyrings/docker.asc
$ echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
$ sudo apt update
$ sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
$ sudo usermod -aG docker $USER
$ echo '{ "log-driver": "json-file", "log-opts": { "max-size": "50m", "max-file": "3" } }' | sudo tee /etc/docker/daemon.json
$ sudo systemctl enable --now docker && sudo systemctl restart docker
```

أغلق الطرفية وافتحها من جديد (حتى تسري عضوية مجموعة `docker`)، ثم:

```bash
$ docker --version && docker compose version     # Engine 27+ و Compose 2.24+
$ docker run --rm hello-world
```

| المكون | الإصدار المطلوب | المصدر |
|---|---|---|
| Docker Engine | 27 أو أحدث | <https://docs.docker.com/engine/install/ubuntu/> |
| Docker Compose | 2.24 أو أحدث | الحزمة `docker-compose-plugin` |

### 5.2 البديل: Docker Desktop

إذا كان Docker Desktop مثبتا أصلا: Settings ← Resources ← WSL Integration ← فعّل `Ubuntu-24.04`، ولا تثبّت Docker Engine
داخل Ubuntu (لا تجمع بين الاثنين). رخصة Docker Desktop مجانية للاستعمال الشخصي والتعليمي وللمؤسسات الصغيرة، وقد
تتطلب اشتراكا مدفوعا في جهة كبيرة؛ راجع <https://www.docker.com/pricing/>. لهذا السبب الخيار 5.1 هو الموصى به.

## 6. وضع المشروع وتشغيله

### 6.1 المكان الصحيح للمشروع

ضع المشروع **داخل نظام ملفات Linux** (`~/projects`)، وليس في `/mnt/c` أو `/mnt/d` أو مجلد OneDrive:

| المكان | السرعة | الصلاحيات | الحكم |
|---|---|---|---|
| `~/projects/E-HIMAYA` (داخل WSL) | سريعة | صلاحيات Linux صحيحة | **المعتمد** |
| `/mnt/d/E-HIMAYA` (قرص Windows) | أبطأ بكثير في البناء والتثبيت | `chmod` لا يعمل كما يجب | لا |
| مجلد OneDrive | المزامنة تقفل الملفات وتكسر `node_modules` و `.venv` | — | ممنوع |

من مستكشف Windows تصل إلى المجلد عبر `\\wsl.localhost\Ubuntu-24.04\home\<اسمك>\projects`.

### 6.2 الجلب والأسرار

```bash
$ mkdir -p ~/projects && cd ~/projects
$ git clone git@github.com:mouhabouk/E-HIMAYA.git && cd E-HIMAYA
$ cp .env.example .env && chmod 600 .env
```

ثم نفّذ كتلة توليد الأسرار كما هي في القسم 6.1 من [دليل الخادم](install-guide.md). محاكيات التطوير **[SIM]** الثلاثة
(`STREAM_SIM_TOKEN` و `TELEPHONY_SIM_PASSWORD` و `TELEPHONY_SIM_TOKEN`) تبقى بقيمها على هذا الجهاز.
`ENVIRONMENT_BANNER=auto` يُظهر على هذا الجهاز شريط «بيئة تطوير» الكهرماني **[SIM]** في اللوحة والبوابة والتطبيق.

### 6.3 التشغيل واختبار الدخان

```bash
$ docker compose --env-file .env -f infra/compose.yml up -d --build
$ docker compose --env-file .env -f infra/compose.yml ps
$ python3 infra/smoke/smoke_test.py
```

البناء الأول من 15 إلى 40 دقيقة حسب الجهاز والاتصال. افتح العناوين من متصفح Windows مباشرة:

| الخدمة | العنوان |
|---|---|
| الواجهة البرمجية ووثائقها | http://localhost:8000/docs |
| فحص الجاهزية | http://localhost:8000/health/ready |
| Keycloak (الإدارة) | http://localhost:8080/admin |
| صندوق المحاكاة للإشعارات والرسائل **[SIM]** | http://localhost:8090 |

## 7. أول مستخدم إداري

كما في القسم 8 من [دليل الخادم](install-guide.md): ادخل إلى http://localhost:8080/admin بحساب `KEYCLOAK_ADMIN`، ثم الفضاء
`ehimaya-staff` ← Users ← Add user، والسمة `gouvernorat_code` أو `scope_level = national`، والدور، وكلمة مرور مؤقتة.
عند أول دخول يُطلب تفعيل TOTP على هاتفك.

## 8. محرر الشيفرة

| الأداة | المصدر |
|---|---|
| Visual Studio Code (على Windows) | <https://code.visualstudio.com> |
| إضافة WSL (`ms-vscode-remote.remote-wsl`) | من سوق الإضافات داخل VS Code |
| إضافات مفيدة | Python، Pylance، ESLint، Flutter و Dart، Docker |

```bash
$ cd ~/projects/E-HIMAYA && code .      # يفتح VS Code على Windows متصلا بـ WSL
```

## 9. أدوات الخلفية والواجهات (داخل WSL)

نفس أوامر القسمين 15.1 و 15.2 من [دليل الخادم](install-guide.md):

| الأداة | الإصدار | أمر التثبيت |
|---|---|---|
| uv | 0.13.4 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python | 3.12 | `uv python install 3.12` |
| nvm | 0.40.3 | `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh \| bash` |
| Node.js | 22 LTS مع npm 10+ | `nvm install 22` |

```bash
$ cd ~/projects/E-HIMAYA/apps/dashboard && npm ci && npm run dev -- --host 127.0.0.1   # http://localhost:5173
$ cd ~/projects/E-HIMAYA/apps/portal    && npm ci && npm run dev -- --host 127.0.0.1   # http://localhost:5174
$ npx playwright install --with-deps chromium                                           # لاختبارات المتصفح
```

لا تثبّت Node.js أو Python على Windows لهذا المشروع: كل شيء داخل WSL، عدا تطبيق الهاتف.

## 10. تطبيق الهاتف (على Windows)

**التوصية:** Flutter و Android Studio على Windows لا داخل WSL. محاكي أندرويد يحتاج تسريع العتاد الذي يوفره Windows، والهاتف
الموصول بـ USB يراه Windows مباشرة (داخل WSL يحتاج أداة `usbipd` وضبطا إضافيا).

| الأداة | الإصدار | المصدر |
|---|---|---|
| Git for Windows | الحالي | <https://git-scm.com/download/win> |
| Flutter (القناة المستقرة) | 3.47.7 مع Dart 3.13.5 | <https://docs.flutter.dev/get-started/install/windows/mobile> و أرشيف الإصدارات <https://docs.flutter.dev/release/archive> |
| Android Studio | الإصدار المستقر الحالي | <https://developer.android.com/studio> |
| JDK | 17 (Eclipse Temurin) | <https://adoptium.net/temurin/releases/?version=17> |
| تعريف USB لهاتف أندرويد | حسب الشركة المصنعة | <https://developer.android.com/studio/run/oem-usb> |

### 10.1 التثبيت

1. ثبّت Git for Windows، ثم Android Studio (مع Android SDK و Platform-Tools و Command-line Tools من SDK Manager).
2. نزّل أرشيف Flutter 3.47.7 وفك ضغطه في `D:\dev\flutter` (مسار دون مسافات ولا حروف عربية).
3. أضف `D:\dev\flutter\bin` إلى متغير PATH (إعدادات النظام ← متغيرات البيئة).
4. ثبّت JDK 17 ثم:

```powershell
PS> flutter --version                                   # Flutter 3.47.7 • Dart 3.13.5
PS> flutter config --jdk-dir "C:\Program Files\Eclipse Adoptium\jdk-17.<...>-hotspot"
PS> flutter doctor --android-licenses
PS> flutter doctor                                      # Android toolchain: علامة صح
```

### 10.2 نسخة من المشروع على Windows للتطبيق فقط

بناء Flutter عبر مسار `\\wsl.localhost` بطيء وغير مستقر، لذلك خذ نسخة ثانية على Windows لتطبيق الهاتف وحده:

```powershell
PS> cd D:\dev
PS> git clone git@github.com:mouhabouk/E-HIMAYA.git
PS> cd E-HIMAYA\apps\mobile
PS> flutter pub get
PS> flutter analyze; flutter test
```

النسختان تُحدَّثان بـ `git pull` كل واحدة في مكانها. لا تعدّل الملف نفسه في النسختين.

### 10.3 التشغيل على هاتف حقيقي

فعّل «خيارات المطوّر» و«تصحيح USB» في الهاتف، وصِله بالحاسوب، ثم:

```powershell
PS> adb devices                                          # يظهر الهاتف بحالة device
PS> adb reverse tcp:8000 tcp:8000; adb reverse tcp:8080 tcp:8080; adb reverse tcp:1080 tcp:1080
PS> flutter run --dart-define=API_BASE_URL=http://localhost:8000 `
      --dart-define=TUS_URL=http://localhost:1080/api/v1/uploads/ `
      --dart-define=OIDC_ISSUER=http://localhost:8080/realms/ehimaya-public
```

`adb reverse` يجعل `localhost` في الهاتف يشير إلى الحاسوب، ومنه إلى WSL. أعد أوامر `adb reverse` بعد كل إعادة وصل للهاتف.
على المحاكي تعمل الأوامر نفسها.

لبناء ملف APK موقّع للتوزيع: القسم 14 من [دليل الخادم](install-guide.md)، مع عناوين خادم التجربة لا `localhost`.

## 11. الملفات الاختيارية حسب الجهاز

| الملف | 16 GB ذاكرة | 32 GB ذاكرة | ملاحظة |
|---|---|---|---|
| `vision` | نعم | نعم | معالج فقط |
| `search` | نعم (`OPENSEARCH_MEM_LIMIT=1g`) | نعم | تذكّر `vm.max_map_count` (11.1) |
| `routing` و `terrain` | ممكن، واحد في كل مرة | نعم | تنزيل الخريطة مرة واحدة |
| `ai` (ملف cpu) | لا ينصح به | نعم | نحو 6 GB نماذج و 8 GB ذاكرة |
| `sim` **[SIM]** | نعم | نعم | للعروض |

```bash
$ docker compose --env-file .env -f infra/compose.yml --profile vision up -d
```

السلامة الساحلية (المرحلة L1b) لا تحتاج ملفا خاصا: على جهاز التطوير يبقى `WEATHER_PROVIDER` فارغا فيعمل محاكي
الطقس البحري **[SIM]** دون إنترنت. للطقس البحري الحقيقي: `WEATHER_PROVIDER=open-meteo` مع الوصول إلى
`marine-api.open-meteo.com` (التفاصيل في الدليل التقني §9).

البرامج الموسمية (المرحلة L2) لا تحتاج ملفا خاصا: بعد `alembic upgrade head` يحمّلها الأمر
`python -m app.modules.programmes.cli load data/programmes/2026/programmes_2026.json` مسودات (التفاصيل في الدليل التقني
§9). حماية الدخول بعد 3 محاولات فاشلة تأتي مع صورة Keycloak بعد `docker compose build keycloak`.

القائمة الرئيسية ومجلدات الطبقات (المرحلتان UI-3 و UI-3b) لا تحتاج شيئا في WSL: `alembic upgrade head` (0058).

مخططات التدخل والبرمجة (المرحلة PL): `npm ci` في `apps/dashboard` (الحزمة `pdfjs-dist`) ثم `alembic upgrade head`
(0061 و 0062). لا شيء آخر في WSL.

المرحلة L5 (ومعها R3 و R4): `alembic upgrade head` (من 0066 إلى 0075)، ثم أضف `SENSOR_GATEWAY_TOKEN` إلى `.env`
(`openssl rand -hex 24`). الحساسات والدرون [SIM] تعمل في WSL بالملفين الشخصيين `sensors` و `drones`:
`docker compose --env-file .env -f infra/compose.yml --profile sensors --profile drones up -d`. اختبار الضغط في
العملية البيضاء لا يُشغَّل في WSL إلا على نسخة معزولة (`ISOLATED=yes`).

نافذة أصحاب القرار والروزنامة (المرحلة L4) لا تحتاجان شيئا في WSL: `alembic upgrade head` (0063 و 0064 و 0065). الملخص
المكتوب يعمل إن كان Ollama يعمل في WSL بالنموذج المضبوط.

سجل الموارد وخلفية القمر الصناعي (المرحلة R) لا يحتاجان شيئا في WSL: `alembic upgrade head` (0059 و 0060). تظهر صور
القمر الصناعي إذا وصل متصفح Windows إلى `tiles.maps.eox.at` و `*.basemaps.cartocdn.com`.

السجل والتوجيهات (المرحلة L3b) لا تحتاج شيئا في WSL: `alembic upgrade head` (0057)، والملفات في MinIO الموجود.

محاور الكوارث (المرحلة L3) لا تحتاج شيئا في WSL: `alembic upgrade head` (0056)، ثم استيراد فضاء الأعوان من جديد ليظهر
الدوران `governor` و `minister` (التفاصيل في الدليل التقني، «محاور الكوارث وواجهات القيادة»).

### 11.1 إعداد OpenSearch في WSL

```bash
$ echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-ehimaya.conf && sudo sysctl --system
```

### 11.2 نماذج الذكاء الاصطناعي على القرص

النماذج تُنزَّل في حجم Docker داخل `ext4.vhdx`. تأكد من المساحة قبل `--profile ai` (`df -h /`)، ويُستحسن أن يكون Ubuntu
قد نُقل إلى `D:` (القسم 2.1).

### 11.3 بطاقة NVIDIA (اختياري)

في WSL2 يأتي دعم CUDA من **تعريف Windows**: لا تثبّت تعريف NVIDIA داخل Ubuntu.

| المكون | المصدر |
|---|---|
| تعريف NVIDIA لـ Windows (Game Ready أو Studio، حديث) | <https://www.nvidia.com/Download/index.aspx> |
| CUDA على WSL (دليل NVIDIA) | <https://docs.nvidia.com/cuda/wsl-user-guide/> |
| NVIDIA Container Toolkit داخل Ubuntu | <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html> |

```bash
$ nvidia-smi                                     # يعمل داخل WSL بعد تثبيت تعريف Windows
# ثبّت NVIDIA Container Toolkit حسب الرابط، ثم:
$ sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
$ docker compose --env-file .env -f infra/compose.yml -f infra/compose.gpu.yml --profile ai up -d
```

بطاقة بذاكرة 8 GB تكفي لـ Whisper medium و Qwen3 4B، لا لنماذج ملف `prod` الكبيرة.

## 12. التشغيل اليومي

| المهمة | الأمر |
|---|---|
| بدء العمل | افتح Ubuntu ثم `cd ~/projects/E-HIMAYA && docker compose --env-file .env -f infra/compose.yml up -d` |
| إيقاف المنظومة مع حفظ البيانات | `docker compose --env-file .env -f infra/compose.yml stop` |
| تحرير كل ذاكرة WSL | `PS> wsl --shutdown` |
| تحديث المشروع | `git pull` ثم `up -d --build` |
| مسح البيانات المحلية والبدء من الصفر | `docker compose --env-file .env -f infra/compose.yml down -v` (يحذف القاعدة والوسائط المحلية) |
| تنظيف الصور القديمة | `docker system prune -a` ثم `docker builder prune` |
| تقليص القرص الافتراضي (إن لم يعمل `sparseVhd`) | `PS> wsl --shutdown` ثم `PS> wsl --manage Ubuntu-24.04 --set-sparse true` |
| فحوص الجودة قبل طلب الدمج | `scripts/ci-local.sh --keep-going` |

## 13. حل المشكلات الشائعة

| العَرَض | السبب المرجّح | الحل |
|---|---|---|
| الخطأ `0x80370102` عند تثبيت WSL | المحاكاة معطلة في BIOS | القسم 1.2 |
| `wsl --install` لا يجد Ubuntu-24.04 | فهرس قديم | `wsl --update` ثم `wsl --list --online` |
| لا اتصال بالإنترنت داخل WSL، أو فشل `apt` و `docker pull` | VPN أو جدار ناري للمؤسسة | `dnsTunneling=true` و `autoProxy=true` (القسم 3)، أو افصل VPN أثناء التثبيت |
| `permission denied ... docker.sock` | عضوية مجموعة `docker` لم تسرِ | أغلق الطرفية وافتحها، أو `newgrp docker` |
| `bad interpreter: /bin/bash^M` | نهايات أسطر CRLF | `git config core.autocrlf input` ثم `git rm --cached -r . && git reset --hard` |
| `localhost:8000` لا يفتح من Windows | منفذ محجوز أو توجيه localhost معطل | `wsl --shutdown` ثم أعد التشغيل؛ تحقق `docker compose ps`؛ جرّب `networkingMode=mirrored` |
| تعارض منفذ (5432، 8080...) | خدمة على Windows تستعمله (PostgreSQL مثبت على Windows مثلا) | أوقف الخدمة على Windows أو غيّر المنفذ في `.env` |
| ساعة WSL متأخرة بعد السبات، وفشل الدخول بـ TOTP | انحراف الوقت | `sudo hwclock -s` أو `wsl --shutdown` |
| امتلاء الذاكرة وبطء Windows | حد `memory` كبير مع ملفات كثيرة | خفّض `memory` في `.wslconfig`، شغّل ملفات أقل |
| OpenSearch يتوقف فورا | `vm.max_map_count` منخفض | القسم 11.1 |
| `flutter doctor` لا يجد Android SDK أو JDK | المسارات | `flutter config --android-sdk ...` و `--jdk-dir ...` |
| الهاتف لا يصل إلى الخادم | `adb reverse` سقط بعد إعادة الوصل | أعد الأوامر الثلاثة (القسم 10.3) |

## 14. التوصيات الفنية

1. **Windows 11 و 32 GB ذاكرة** هما الفرق بين بيئة مريحة وبيئة تتعثر. مع 16 GB شغّل المنظومة الأساسية فقط.
2. **Docker Engine داخل WSL** (القسم 5.1) بدل Docker Desktop: لا رخصة، ولا طبقة إضافية، وسلوك مطابق للخادم.
3. **المشروع داخل `~/projects`** لا على `/mnt/c` ولا في OneDrive، ونسخة ثانية على Windows لتطبيق الهاتف فقط.
4. **Ubuntu على قرص D:** إذا كان قرص النظام أقل من 250 GB.
5. **`.env` لا يُرفع ولا يُرسل**: هو في `.gitignore`. لا تنسخه إلى OneDrive أو البريد.
6. **لا بيانات حقيقية على هذا الجهاز**: بيانات التجربة **[SIM]** فقط. البيانات الشخصية الحقيقية على الخادم وحده.
7. **BitLocker مفعّل** على قرص Windows إن كان الجهاز محمولا، لأن ملف `ext4.vhdx` يحوي القاعدة والأسرار.
8. **`wsl --shutdown` في نهاية اليوم** يعيد الذاكرة، ويُسقط حالة الشبكة العالقة إن وُجدت.
9. **مكافح الفيروسات**: إذا كان البناء بطيئا جدا، أضف استثناء لمجلد `D:\WSL` في Microsoft Defender (بعلم مسؤول أمن الجهاز).
10. **قبل كل طلب دمج**: `scripts/ci-local.sh` على هذا الجهاز يعطي النتيجة نفسها التي يعطيها التكامل المستمر.

## 15. حدود هذه البيئة

WSL على حاسوب شخصي بيئة تطوير وعرض، وليست خادما:

| الحد | الأثر |
|---|---|
| لا عنوان IP ثابت ولا اسم DNS عمومي | لا TLS حقيقي، ولا وصول للهواتف من خارج الجهاز إلا بـ `adb reverse` |
| السبات وتحديثات Windows وإعادة التشغيل | توقف المنظومة دون إنذار |
| لا نسخ احتياطي آلي | أي عطل في القرص يفقد البيانات المحلية |
| الخط الهاتفي والرسائل القصيرة الحقيقية | تحتاج خادما ثابتا وعقودا (القسم 12 من دليل الخادم) |

للتجربة الميدانية: خادم Ubuntu Server باتباع [`docs/install-guide.md`](install-guide.md).

## 16. المتطلبات الوظيفية

نفسها في البيئتين: الأدوار والمكونات وما يوفّره الديوان مفصلة في القسم 17 من [دليل الخادم](install-guide.md). على هذا الجهاز
تكفي ثلاثة حسابات للعرض: مدير نظام (`sysadmin`) ومشغّل (`operator`) في `ehimaya-staff`، ومواطن يسجّل من التطبيق برقم
هاتف (رمز التحقق يظهر في صندوق المحاكاة **[SIM]** على http://localhost:8090).

## 17. قائمة التحقق

- [ ] المحاكاة مفعلة، و `wsl -l -v` يُظهر `Ubuntu-24.04` بالإصدار 2.
- [ ] `.wslconfig` مضبوط، و systemd مفعّل.
- [ ] `docker run --rm hello-world` يعمل دون `sudo`.
- [ ] المشروع في `~/projects/E-HIMAYA`، و `.env` بصلاحية 600 وأسرار مولّدة.
- [ ] `smoke_test.py` ناجح، و http://localhost:8000/docs يفتح من متصفح Windows.
- [ ] مدير النظام دخل إلى اللوحة بـ TOTP.
- [ ] `flutter doctor` دون أخطاء، والتطبيق يعمل على الهاتف ويرسل بلاغا يظهر في اللوحة.
- [ ] `scripts/ci-local.sh --list` يعمل.
