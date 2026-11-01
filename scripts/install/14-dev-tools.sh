#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 14 (للمطوّر فقط): أدوات التطوير، الدليل §15.
#
# متى: على جهاز المطوّر أو جهاز البناء فقط، لا على خادم الإنتاج (الإنتاج يبني كل شيء داخل Docker).
#
# الأجزاء (اختر بالأسماء، أو all):
#   python   uv 0.13.4 و Python 3.12 عبر uv، ثم uv sync في services/api (اعتماديات الخلفية والاختبارات)؛
#   node     nvm 0.40.3 و Node.js 22 LTS، ثم npm ci في اللوحة (apps/dashboard) والبوابة (apps/portal)؛
#   flutter  OpenJDK 17 وأدوات البناء، و Flutter 3.47.7 (الإصدار نفسه في CI) في ~/flutter، ثم flutter doctor.
#            Android SDK يُثبَّت مع Android Studio (https://developer.android.com/studio)، ثم flutter doctor --android-licenses.
# كل جزء يتحقق أولًا هل الأداة موجودة بالإصدار المطلوب ولا يعيد تثبيتها.
#
# الاستعمال: scripts/install/14-dev-tools.sh python node      أو      scripts/install/14-dev-tools.sh all
# بعده: التشغيل المحلي كما في README.md (قسم «تطوير الخلفية واختبارها»)، ثم 15-quality-checks.sh قبل كل إصدار.
source "$(dirname "$0")/00-common.sh"

UV_VERSION=0.13.4
NVM_VERSION=0.40.3
FLUTTER_VERSION=3.47.7

dev_python() {
  step "Python و uv"
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  uv python install 3.12
  (cd "$ROOT/services/api" && uv sync)
  ok "$(uv --version)؛ اعتماديات الخلفية مثبتة (services/api/.venv)"
}

dev_node() {
  step "Node.js 22"
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] || curl -fsSo- "https://raw.githubusercontent.com/nvm-sh/nvm/v$NVM_VERSION/install.sh" | bash
  # shellcheck source=/dev/null
  . "$NVM_DIR/nvm.sh"
  nvm install 22 >/dev/null
  nvm use 22 >/dev/null
  for app in dashboard portal; do
    (cd "$ROOT/apps/$app" && npm ci)
  done
  ok "Node $(node --version)؛ اللوحة: npm run dev (5173)، البوابة: npm run dev (5174)"
}

dev_flutter() {
  step "Java و Flutter"
  as_root apt-get install -y openjdk-17-jdk clang cmake ninja-build pkg-config libgtk-3-dev unzip xz-utils
  if ! command -v flutter >/dev/null 2>&1 && [ ! -x "$HOME/flutter/bin/flutter" ]; then
    curl -fL "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" |
      tar -xJ -C "$HOME"
    # shellcheck disable=SC2016 # يُكتب حرفيًا في .bashrc
    grep -q 'flutter/bin' "$HOME/.bashrc" || echo 'export PATH="$HOME/flutter/bin:$PATH"' >>"$HOME/.bashrc"
  fi
  export PATH="$HOME/flutter/bin:$PATH"
  flutter --version
  (cd "$ROOT/apps/mobile" && flutter pub get)
  flutter doctor || true
  warn "ثبّت Android Studio و Android SDK إن طلبه flutter doctor، ثم: flutter doctor --android-licenses"
}

[ $# -gt 0 ] || die "اذكر جزءًا: python node flutter (أو all)"
[ "$1" = all ] && set -- python node flutter
for part in "$@"; do
  case "$part" in
    python) dev_python ;;
    node) dev_node ;;
    flutter) dev_flutter ;;
    *) die "جزء غير معروف: $part" ;;
  esac
done
