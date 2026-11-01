#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 1: تهيئة نظام الخادم (Ubuntu Server 24.04 LTS)، الدليل التقني §3.
#
# متى: مرة واحدة، مباشرة بعد تثبيت Ubuntu 24.04 (الأولوية 2 في الدليل تُنجز يدويًا: تنزيل ISO والتحقق منه والتثبيت).
# أين: على الخادم، بحساب له sudo (وليس root مباشرة).
#
# ما يفعله بالترتيب:
#   1. تحديث النظام وتثبيت الأدوات الأساسية: curl و git و openssl و chrony (مزامنة الوقت) و ufw (الجدار الناري) و jq و python3؛
#   2. تفعيل تحديثات الأمان الآلية (unattended-upgrades)؛
#   3. ضبط المنطقة الزمنية Africa/Tunis (القاعدة تعمل بـ UTC داخليًا، والوقت الصحيح ضروري لسلسلة التدقيق ورموز TOTP)؛
#   4. تقوية SSH: منع الدخول بكلمة المرور ومنع root — فقط إن كان لحسابك مفتاح في ~/.ssh/authorized_keys،
#      وإلا يتجاوز الخطوة حتى لا تُغلق الباب على نفسك؛
#   5. الجدار الناري لمرحلة التطوير: كل الوارد ممنوع إلا SSH من شبكة الإدارة (المتغير ADMIN_CIDR)؛
#   6. إعداد النواة vm.max_map_count=262144 الذي يحتاجه OpenSearch؛
#   7. (اختياري) تهيئة قرص بيانات منفصل لـ /var/lib/docker، فقط إن مرّرت DATA_DISK=/dev/sdX. يمسح القرص: يُسأل قبله.
#
# الاستعمال:
#   ADMIN_CIDR=10.20.0.0/24 scripts/install/01-system-prepare.sh
#   ADMIN_CIDR=10.20.0.0/24 DATA_DISK=/dev/sdb scripts/install/01-system-prepare.sh     # مع قرص البيانات
# بعده: أعد تشغيل الخادم إن طلب ذلك (/var/run/reboot-required)، ثم 02-docker-install.sh.
source "$(dirname "$0")/00-common.sh"

[ -r /etc/os-release ] && . /etc/os-release
[ "${ID:-}" = ubuntu ] || warn "النظام ليس Ubuntu (${ID:-?}); السكريبت مكتوب لـ Ubuntu 24.04 وقد تختلف الحزم"
[ "${VERSION_ID:-}" = 24.04 ] || warn "الإصدار ${VERSION_ID:-?}؛ الإصدار المعتمد 24.04 LTS"

step "1/7 تحديث النظام والأدوات الأساسية"
as_root apt-get update
as_root env DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade
as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates curl gnupg git openssl unattended-upgrades chrony ufw jq htop python3
ok "الأدوات مثبتة: $(git --version), $(openssl version | cut -d' ' -f1-2)"

step "2/7 تحديثات الأمان الآلية"
# الملف 20auto-upgrades هو ما يكتبه «dpkg-reconfigure unattended-upgrades» عند الإجابة بنعم.
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' |
  as_root tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null
ok "مفعّلة"

step "3/7 المنطقة الزمنية ومزامنة الوقت"
as_root timedatectl set-timezone Africa/Tunis
as_root systemctl enable --now chrony >/dev/null 2>&1 || true
timedatectl | grep -E 'Time zone|synchronized' || true

step "4/7 تقوية SSH"
if [ -s "$HOME/.ssh/authorized_keys" ]; then
  as_root sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' \
    /etc/ssh/sshd_config
  as_root systemctl restart ssh
  ok "الدخول بالمفاتيح فقط، و root ممنوع"
else
  warn "لا مفتاح في ~/.ssh/authorized_keys: لم أمنع الدخول بكلمة المرور. انسخ مفتاحك (ssh-copy-id) ثم أعد السكريبت"
fi

step "5/7 الجدار الناري (مرحلة التطوير)"
# Docker يكتب قواعده في iptables مباشرة ولا يمر بـ ufw؛ لذلك كل منافذ التطوير مربوطة بـ 127.0.0.1 في compose.yml،
# ومنافذ الإنتاج (80 و 443 والوسائط والهاتف) يفتحها 09-production-deploy.sh.
if [ -n "${ADMIN_CIDR:-}" ]; then
  as_root ufw default deny incoming
  as_root ufw default allow outgoing
  as_root ufw allow from "$ADMIN_CIDR" to any port 22 proto tcp
  as_root ufw --force enable
  as_root ufw status verbose
else
  warn "ADMIN_CIDR غير محدد (مثلا 10.20.0.0/24): لم أفعّل الجدار الناري حتى لا ينقطع اتصال SSH الحالي"
fi

step "6/7 إعداد النواة لـ OpenSearch"
echo 'vm.max_map_count=262144' | as_root tee /etc/sysctl.d/99-ehimaya.conf >/dev/null
as_root sysctl --system >/dev/null
ok "vm.max_map_count=$(sysctl -n vm.max_map_count)"

step "7/7 قرص البيانات (اختياري)"
if [ -n "${DATA_DISK:-}" ]; then
  # يجب أن يسبق تثبيت Docker، حتى تُحفظ كل الأحجام (القاعدة، الوسائط، النسخ الاحتياطية) على هذا القرص.
  [ -b "$DATA_DISK" ] || die "$DATA_DISK ليس قرصًا"
  if grep -q 'LABEL=ehimaya-data' /etc/fstab; then
    ok "قرص البيانات مهيأ من قبل"
  elif confirm "سيُمسح كل ما في $DATA_DISK ويُركَّب على /var/lib/docker. أتابع؟"; then
    as_root mkfs.ext4 -L ehimaya-data "$DATA_DISK"
    as_root mkdir -p /var/lib/docker
    echo 'LABEL=ehimaya-data /var/lib/docker ext4 defaults,noatime 0 2' | as_root tee -a /etc/fstab >/dev/null
    as_root mount -a
    df -h /var/lib/docker
  fi
else
  ok "لا قرص بيانات منفصل (DATA_DISK غير محدد)"
fi

[ -f /var/run/reboot-required ] && warn "النظام يطلب إعادة التشغيل: sudo reboot ثم 02-docker-install.sh"
ok "انتهت التهيئة. التالي: scripts/install/02-docker-install.sh"
