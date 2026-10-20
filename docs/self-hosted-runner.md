# مُشغِّل GitHub Actions ذاتي الاستضافة / Self-hosted GitHub Actions runner

هذه الصفحة لصاحب المستودع. GitHub Actions متوقف حاليا على هذا المستودع الخاص بسبب حد الفوترة في الحساب، فلا يعمل أي
مسار CI. يوجد حلّان، ويمكن استعمالهما معا:

1. **تشغيل الفحوص يدويا على جهازك** بالسكربت `scripts/ci-local.sh` (يحتاج Docker فقط، ولا يعتمد على GitHub)؛
2. **تسجيل جهازك كمُشغِّل (runner) ذاتي الاستضافة** لهذا المستودع، فتعود مسارات CI إلى العمل تلقائيا عند كل دفع (push)
   وكل طلب دمج (pull request)، لكنها تُنفَّذ على جهازك بدل خوادم GitHub.

هذه الصفحة تشرح الحل الثاني. الأوامر تبقى كما هي (بالإنجليزية).

---

## 1. الفوترة: ما نعرفه وما لا نعرفه

- حسب وثائق GitHub، **دقائق المُشغِّلات ذاتية الاستضافة مجانية**: لا تُحتسب من رصيد الدقائق ولا تُدفع.
- **لا يمكنني أن أتحقق من هنا** هل قفل الفوترة الحالي في حسابك يمنع أيضا المهام على المُشغِّلات ذاتية الاستضافة. بعض
  حالات القفل (مثل فاتورة غير مدفوعة أو حساب مقفل) قد توقف Actions بالكامل، أيا كان المُشغِّل.
- **طريقة التحقق**: بعد إتمام الخطوات أدناه، أعد تشغيل أي مسار (Re-run) أو ادفع فرعا جديدا. إذا بقيت المهمة «Queued» ولم
  يلتقطها جهازك، أو ظهرت رسالة من نوع «The job was not started because your account is locked due to a billing
  issue»، فالقفل يشمل المُشغِّلات ذاتية الاستضافة أيضا، ويجب حل مسألة الفوترة في
  Settings → Billing and plans. في هذه الحالة يبقى `scripts/ci-local.sh` هو الحل.

---

## 2. تغيير سير العمل (workflows) الذي تمّ

كل مهمة في `.github/workflows/*.yml` صارت:

```yaml
runs-on: ${{ vars.RUNNER || 'ubuntu-24.04' }}
```

- ما دام متغير المستودع `RUNNER` غير معرَّف، **لا يتغير شيء**: المهام تطلب `ubuntu-24.04` كما في السابق (أبقينا
  `ubuntu-24.04` وليس `ubuntu-latest` لأنه القيمة الموجودة أصلا في المسارات).
- عندما تعرّف `RUNNER` (مثلا `ehimaya`)، كل المهام تذهب إلى المُشغِّل الذي يحمل هذا الوسم (label).
- للرجوع إلى خوادم GitHub: احذف المتغير `RUNNER`.

وأُضيف أيضا شرط على خطوتين تحذفان مجلدات النظام لتوفير مساحة القرص («Free disk space for the models» في `ci.yml`
و«Free runner disk space» في `mobile.yml`):

```yaml
if: runner.environment == 'github-hosted'
```

بدون هذا الشرط كانت هاتان الخطوتان ستنفّذان `sudo rm -rf /usr/share/dotnet /usr/local/lib/android ...` **على جهازك
أنت**. على خوادم GitHub لا يتغير شيء.

---

## 3. أي جهاز؟ (مهم قبل البدء)

المسارات كُتبت لآلات GitHub التي تُمحى بعد كل مهمة. على جهازك لا تُمحى، وهذا يعني:

- المهام تستعمل **أسماء حاويات ثابتة** (`pg`, `opensearch`, `kc`, `telephony`, `sim`, `ollama`, `vision`...) و**منافذ
  ثابتة** (5432, 9200, 8000, 9000, 8088, 11434, 8100...) ولا تحذف الحاويات في آخرها؛
- مهمة `stack` تشغّل `docker compose` باسم المشروع **`ehimaya`**، وهو نفس اسم مشروع بيئة التطوير عندك: لو شاركت نفس
  Docker مع بيئتك اليومية، ستعيد بناء صورك وتستعمل نفس المجلدات (volumes) بأسرار عشوائية جديدة، فتُفسد بيئة التطوير.

لذلك:

- **استعمل Docker مخصصا للمُشغِّل**: جهاز مستقل، أو آلة افتراضية (VM)، أو على Windows **توزيعة WSL2 مخصصة** فيها
  Docker Engine خاص بها (ليس Docker Desktop المشترك مع بيئة التطوير).
- **مُشغِّل واحد فقط لكل Docker**: مُشغِّلان على نفس Docker سيتصادمان في أسماء الحاويات والمنافذ.
- **نظِّف Docker بين المهام** تلقائيا بخطاف (hook) المُشغِّل، القسم 6.

نظام التشغيل: **Ubuntu 24.04** (نفس صورة GitHub؛ المسارات تستعمل `bash` و`apt-get` و`sudo`). مُشغِّل Windows الأصلي
لن يعمل مع هذه المسارات؛ على Windows استعمل WSL2.

المساحة: احسب **60 GB على الأقل** فارغة (صور Docker، ونماذج الذكاء الاصطناعي في مهمة `ai-models` وحدها نحو 25 GB،
و Android SDK إن أردت مهمة `mobile`). الذاكرة: 8 GB على الأقل (OpenSearch و Keycloak و Asterisk معا في مهمة `stack`).

---

## 4. تجهيز الجهاز

### 4.1 على Windows: توزيعة WSL2 مخصصة

في PowerShell (كمسؤول):

```powershell
wsl --install -d Ubuntu-24.04
```

إذا كانت لديك توزيعة Ubuntu-24.04 للتطوير، أنشئ نسخة منفصلة للمُشغِّل (في إصدارات WSL الحديثة: `wsl --install
Ubuntu-24.04 --name ehimaya-runner`، أو `wsl --export` ثم `wsl --import`). داخل التوزيعة فعّل systemd (ضروري لتشغيل
المُشغِّل كخدمة ولـ Docker):

```bash
sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
```

ثم من PowerShell: `wsl --shutdown` وافتح التوزيعة من جديد. لاحظ أن المُشغِّل يعمل فقط والجهاز مشغَّل وWSL مفتوح؛ إذا نام
الحاسوب تبقى المهام في الانتظار.

### 4.2 مستخدم مخصص اسمه `runner`

اسم `runner` ليس اختياريا: مهمتا `ai-models` و`vision-models` تكتبان النماذج في `/home/runner/...` (كما على خوادم
GitHub)، فيجب أن يكون هذا المجلد موجودا وملكا لمستخدم المُشغِّل.

```bash
sudo adduser --disabled-password --gecos "" runner
```

لا تستعمل حسابك الشخصي ولا `root`.

### 4.3 Docker Engine

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker runner
```

> **تنبيه أمني**: الانتماء إلى مجموعة `docker` يساوي صلاحيات `root` على الجهاز (أي حاوية يمكنها تركيب `/` كاملا). كل
> من يستطيع أن يجعل سير عمل يُنفَّذ على هذا المُشغِّل يملك عمليا الجهاز. هذا سبب آخر لجهاز أو توزيعة مخصصة.

### 4.4 أدوات تستعملها المسارات

```bash
sudo apt-get install -y git curl openssl jq unzip xz-utils zstd python3 python3-venv python3-yaml
```

| ما تحتاجه المسارات | كيف يصل إلى المُشغِّل |
|---|---|
| Docker + compose + buildx | يدويا (4.3) — كل مهام `ci.yml` تقريبا |
| `python3` مع `yaml` | يدويا (أعلاه) — مهمة `stack` تستعمل `python3 -c "import yaml"` |
| uv و Python 3.12 | تلقائيا: `astral-sh/setup-uv` و`actions/setup-python` ينزّلانهما |
| Node 22 | تلقائيا: `actions/setup-node` (مهمتا `dashboard` و`portal`) |
| Chromium لاختبارات المتصفح | تلقائيا: `npx playwright install --with-deps chromium` (يحتاج `sudo apt-get`، انظر 4.5) |
| Java 17 و Flutter 3.47.7 | تلقائيا: `actions/setup-java` و`subosito/flutter-action` (مهمة `mobile`) |
| Android SDK | **يدويا**، فقط إن أردت مهمة `mobile` (انظر أسفل) |
| `espeak-ng`, `libsqlite3-dev` | المسارات تثبّتهما بـ `sudo apt-get`؛ أو ثبّتهما مسبقا: `sudo apt-get install -y espeak-ng libsqlite3-dev` |

**Android SDK** (لمهمة `mobile` فقط): ثبّت command-line tools من developer.android.com في
`/home/runner/android-sdk`، ثم:

```bash
export ANDROID_HOME=/home/runner/android-sdk
yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platform-tools" "platforms;android-36" "build-tools;36.0.0"
```

(أرقام المنصة وأدوات البناء أعلاه مثال؛ بعد قبول التراخيص ينزّل Gradle/Flutter أي جزء ناقص، بما فيه NDK، عند أول
`flutter build apk`.) وأضف `ANDROID_HOME=/home/runner/android-sdk` إلى ملف `.env` في مجلد المُشغِّل (القسم 5) حتى تراه المهام. إن لم تُرد
مهمة `mobile` على جهازك فلا تثبّت شيئا: ستفشل تلك المهمة وحدها، أو اترك `mobile.yml` على خوادم GitHub (انظر 7).

### 4.5 `sudo` بدون كلمة سر (محدود)

بعض الخطوات تستدعي `sudo apt-get` (espeak-ng، libsqlite3-dev، مكتبات Chromium) و`sudo chown` (ملكية ملفات Ollama).
على المُشغِّل لا أحد يكتب كلمة السر، فإما أن تثبّت الحزم مسبقا (4.4)، وإما أن تسمح بهذين الأمرين فقط:

```bash
echo 'runner ALL=(root) NOPASSWD: /usr/bin/apt-get, /usr/bin/chown' | sudo tee /etc/sudoers.d/runner
sudo chmod 0440 /etc/sudoers.d/runner
```

(`apt-get` كـ root يعطي عمليا صلاحيات root؛ مع مجموعة `docker` لا يضيف هذا خطرا جديدا، لكنه سبب إضافي لعزل الجهاز.)

---

## 5. تسجيل المُشغِّل في المستودع

1. في GitHub: **Settings → Actions → Runners → New self-hosted runner**.
2. اختر **Linux** و **x64**. تعرض الصفحة أوامر جاهزة فيها رقم الإصدار، وبصمة SHA-256 للملف، ورمز تسجيل (token) صالح
   لساعة واحدة. **انسخ الأوامر من الصفحة نفسها** (الإصدار والبصمة يتغيران)؛ شكلها:

```bash
sudo -iu runner
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-<VERSION>.tar.gz -L https://github.com/actions/runner/releases/download/v<VERSION>/actions-runner-linux-x64-<VERSION>.tar.gz
echo "<SHA256>  actions-runner-linux-x64-<VERSION>.tar.gz" | shasum -a 256 -c
tar xzf ./actions-runner-linux-x64-<VERSION>.tar.gz
./config.sh --url https://github.com/<OWNER>/<REPO> --token <TOKEN> --name ehimaya-runner --labels ehimaya --unattended
```

   الوسم `--labels ehimaya` هو ما سيختاره المتغير `RUNNER`.
3. شغّله كخدمة (يعود تلقائيا بعد إعادة التشغيل)، من حساب لديه sudo (ليس `runner`)، داخل مجلد المُشغِّل:

```bash
cd /home/runner/actions-runner
sudo ./svc.sh install runner
sudo ./svc.sh start
sudo ./svc.sh status
```

4. في **Settings → Actions → Runners** يجب أن يظهر `ehimaya-runner` بحالة **Idle**.
5. عرّف المتغير: **Settings → Secrets and variables → Actions → Variables → New repository variable**،
   الاسم `RUNNER` والقيمة `ehimaya`. أو بسطر واحد:

```bash
gh variable set RUNNER --body ehimaya --repo <OWNER>/<REPO>
```

6. ادفع أي التزام (commit) أو أعد تشغيل آخر مسار، وراقب **Actions**: يجب أن تلتقط المهام `ehimaya-runner`.

للرجوع إلى خوادم GitHub: `gh variable delete RUNNER --repo <OWNER>/<REPO>` (أو احذفه من الواجهة). لإزالة المُشغِّل:
`sudo ./svc.sh stop && sudo ./svc.sh uninstall && ./config.sh remove --token <TOKEN>` (رمز جديد من نفس الصفحة).

---

## 6. تنظيف Docker بين المهام (خطاف المُشغِّل)

على خوادم GitHub تختفي الحاويات مع الآلة. على جهازك تبقى `pg` و`kc` و`opensearch`... فتفشل المهمة التالية («container
name already in use» أو «port is already allocated»). المُشغِّل يقبل سكربتا يُنفَّذ قبل كل مهمة وبعدها:

```bash
sudo -iu runner tee /home/runner/ci-cleanup.sh >/dev/null <<'EOF'
#!/bin/bash
# Docker of this runner only (never the development Docker): remove everything a previous job left behind.
docker ps -aq | xargs -r docker rm -f
docker volume ls -q | xargs -r docker volume rm -f
docker network prune -f
docker image prune -f
EOF
sudo chmod 0755 /home/runner/ci-cleanup.sh
printf 'ACTIONS_RUNNER_HOOK_JOB_STARTED=/home/runner/ci-cleanup.sh\nACTIONS_RUNNER_HOOK_JOB_COMPLETED=/home/runner/ci-cleanup.sh\n' \
  | sudo -u runner tee -a /home/runner/actions-runner/.env
cd /home/runner/actions-runner && sudo ./svc.sh stop && sudo ./svc.sh start
```

هذا السكربت يحذف **كل** الحاويات والمجلدات (volumes) في Docker الذي يراه المُشغِّل: لا تستعمله إلا مع Docker مخصص
للمُشغِّل (القسم 3). من حين لآخر نظّف ذاكرة البناء أيضا: `docker builder prune -af`.

---

## 7. ملاحظات أمنية

- **مستودع خاص فقط**. لا تربط مُشغِّلا ذاتي الاستضافة بمستودع عام: أي شخص يفتح طلب دمج من نسخة (fork) يمكنه تنفيذ
  شيفرته على جهازك.
- **لا تسمح بمسارات طلبات الدمج من النسخ (forks)**: في **Settings → Actions → General → Fork pull request workflows
  in private repositories** أبقِ «Run workflows from fork pull requests» **معطَّلا**. عندها لا يشغّل المُشغِّل إلا شيفرة
  من فروع المستودع نفسه، أي من أشخاص لهم صلاحية الكتابة.
- كل من له صلاحية **الكتابة** على المستودع يستطيع تعديل ملف سير عمل وتنفيذ أي أمر على جهازك (بصلاحيات `runner` ومجموعة
  `docker`، أي عمليا root). امنح صلاحية الكتابة لمن تثق به فقط.
- **مستخدم مخصص** (`runner`) بلا ملفاتك الشخصية، بلا مفاتيح SSH، بلا أسرار الإنتاج. لا تضع ملف `.env` حقيقيا ولا مفاتيح
  الإنتاج على هذا الجهاز: المسارات لا تحتاج أي سر (تولّد قيمها العشوائية بنفسها).
- `permissions: contents: read` موجود في كل المسارات: رمز `GITHUB_TOKEN` الذي يصل إلى جهازك لا يستطيع الكتابة في
  المستودع.
- حدّث المُشغِّل: يحدّث نفسه تلقائيا عادة؛ إن توقف، نزّل الإصدار الجديد من نفس الصفحة.
- إن أردت إبقاء بعض المهام على خوادم GitHub (مثلا `mobile` إذا لم تثبّت Android SDK) بعد حل الفوترة، فالمتغير
  `RUNNER` واحد لكل المسارات؛ يمكن لاحقا استبدال `vars.RUNNER` في ملف واحد بمتغير آخر (مثلا `vars.RUNNER_MOBILE`).

---

## 8. البديل دون GitHub: `scripts/ci-local.sh`

على أي جهاز فيه Docker (حتى جهاز التطوير، لأنه يستعمل أسماء ومنافذ عشوائية ويحذف كل ما ينشئه):

```bash
scripts/ci-local.sh --list                 # المهام
scripts/ci-local.sh --keep-going           # كل المهام، ولا يتوقف عند أول فشل
scripts/ci-local.sh --only api,stack       # مهام محددة
scripts/ci-local.sh --skip ai-models,mobile
```

يختبر آخر التزام (commit) في نسخة نظيفة، ويطبع جدولا (PASS / FAIL / SKIPPED مع السبب والمدة)، ويكتب
`ci-local-report.md` للصقه في طلب الدمج، وسجلّ كل مهمة في `ci-local-logs/`.
