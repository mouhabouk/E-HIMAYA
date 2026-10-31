#!/usr/bin/env bash
# تحصين خادم ء-حماية (Ubuntu 24.04 LTS). Host hardening of an e-Himaya server (review point 15, phase 4).
#
#   sudo infra/security/harden-host.sh --check                 # what would change, nothing is written
#   sudo infra/security/harden-host.sh --apply --profile demo  # the demonstration computer: only 443 on the LAN
#   sudo infra/security/harden-host.sh --apply --profile prod  # a server of the pilot or of production
#
# Options (environment):
#   ADMIN_NET=10.20.0.0/24     SSH only from this network (default: any; set it on a real server)
#   EHIMAYA_DIR=/opt/e-himaya  checkout holding .env (made 600) and the compose files
#   ALLOW_USB_STORAGE=1        keep USB storage (the demonstration computer copies files from a key)
#   TELEPHONY=1                open SIP 5060/5061 and the RTP range (prod profile, telephony in use)
#   RESTRICT_COMPILERS=0|1     compilers for root only (default 1 with --profile prod, 0 with demo)
#
# Idempotent: every step checks before it writes, so it can run after each update. Every file it writes carries the
# "ehimaya-harden" marker. Measured effect (Lynis hardening index, nmap, testssl.sh): docs/security/hardening-report.html.
# Docker publishes its ports through its own iptables chain, ahead of ufw: the compose files therefore bind every
# port to an explicit address (127.0.0.1, DEMO_LAN_IP…), and the reference is an nmap scan from another machine.
set -uo pipefail

MODE=check PROFILE=prod
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --apply) MODE=apply ;;
    --profile) PROFILE="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done
case "$PROFILE" in demo|prod) ;; *) echo "--profile demo|prod" >&2; exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)" >&2; exit 1; }

MARK="# ehimaya-harden (infra/security/harden-host.sh) — do not edit, re-run the script"
CHANGED=0 SKIPPED=0
say() { printf '%-8s %s\n' "$1" "$2"; }
# write_file <path> <mode> <content>: writes only when the content differs.
write_file() {
  local path="$1" mode="$2" content="$3"
  if [ -f "$path" ] && [ "$(cat "$path")" = "$content" ]; then say ok "$path"; return 1; fi
  if [ "$MODE" = check ]; then say change "$path"; CHANGED=$((CHANGED + 1)); return 1; fi
  mkdir -p "$(dirname "$path")"; printf '%s\n' "$content" > "$path"; chmod "$mode" "$path"
  say written "$path"; CHANGED=$((CHANGED + 1)); return 0
}
# set_kv <file> <key> <value>: "KEY value" lines of login.defs.
set_kv() {
  local file="$1" key="$2" value="$3"
  # Only setting lines count (a comment that mentions the key is left alone); duplicates are reduced to one line.
  if [ "$(grep -Ec "^\s*${key}\s" "$file")" = 1 ] && grep -Eq "^\s*${key}\s+${value}\s*$" "$file"; then say ok "$file $key $value"; return; fi
  if [ "$MODE" = check ]; then say change "$file $key $value"; CHANGED=$((CHANGED + 1)); return; fi
  if grep -Eq "^\s*${key}\s" "$file"; then
    awk -v k="$key" -v v="$value" '$1 == k { if (!done) { print k "\t" v; done = 1 }; next } { print }' "$file" > "$file.ehimaya" && cat "$file.ehimaya" > "$file" && rm -f "$file.ehimaya"
  else printf '%s\t%s\n' "$key" "$value" >> "$file"; fi
  say written "$file $key $value"; CHANGED=$((CHANGED + 1))
}
service_on() {
  if [ ! -d /run/systemd/system ]; then
    say skip "systemctl enable --now $1 (no systemd here)"; SKIPPED=$((SKIPPED + 1)); return; fi
  [ "$MODE" = apply ] && systemctl enable --now "$1" >/dev/null 2>&1 && say on "$1" || say check "$1 (enable --now)"
}

echo "== e-Himaya host hardening: mode=$MODE profile=$PROFILE"

# 1. Packages: firewall, audit, brute-force ban, automatic security updates, integrity and accounting tools.
PKGS="ufw auditd audispd-plugins fail2ban unattended-upgrades needrestart apt-listchanges apt-show-versions debsums
      libpam-tmpdir libpam-pwquality acct sysstat rsyslog rkhunter chrony"
MISSING=$(for p in $PKGS; do dpkg -s "$p" >/dev/null 2>&1 || echo "$p"; done | xargs)
if [ -z "$MISSING" ]; then say ok "packages"; elif [ "$MODE" = check ]; then say change "install: $MISSING"; CHANGED=$((CHANGED + 1))
else DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $MISSING >/dev/null && say written "installed: $MISSING"; CHANGED=$((CHANGED + 1)); fi

# 2. Kernel and network parameters. IPv4 forwarding stays on: Docker needs it.
write_file /etc/sysctl.d/60-ehimaya.conf 644 "$MARK
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.yama.ptrace_scope = 1
kernel.sysrq = 0
kernel.unprivileged_bpf_disabled = 1
kernel.perf_event_paranoid = 3
net.core.bpf_jit_harden = 2
fs.suid_dumpable = 0
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0" && { sysctl -q -p /etc/sysctl.d/60-ehimaya.conf 2>/dev/null || { say skip "sysctl (read-only here: applied at next boot)"; SKIPPED=$((SKIPPED + 1)); }; }

# 3. Unused protocols and file systems, firewire and (unless kept) USB storage.
MODS="dccp sctp rds tipc cramfs freevxfs hfs hfsplus jffs2 udf firewire-core firewire-ohci"
[ "${ALLOW_USB_STORAGE:-0}" = 1 ] || MODS="$MODS usb-storage"
write_file /etc/modprobe.d/60-ehimaya.conf 644 "$MARK
$(for m in $MODS; do printf 'install %s /bin/true\nblacklist %s\n' "$m" "$m"; done)" || true

# 4. Accounts: umask 027, password ageing and hashing rounds, quality, no core dumps.
set_kv /etc/login.defs UMASK 027
set_kv /etc/login.defs PASS_MAX_DAYS 365
set_kv /etc/login.defs PASS_MIN_DAYS 1
set_kv /etc/login.defs PASS_WARN_AGE 14
set_kv /etc/login.defs SHA_CRYPT_MIN_ROUNDS 65536
set_kv /etc/login.defs SHA_CRYPT_MAX_ROUNDS 65536
write_file /etc/security/pwquality.conf.d/60-ehimaya.conf 644 "$MARK
minlen = 12
minclass = 3
maxrepeat = 3
dictcheck = 1
enforce_for_root" || true
write_file /etc/security/limits.d/60-ehimaya.conf 644 "$MARK
* hard core 0
* soft core 0" || true
write_file /etc/systemd/coredump.conf.d/60-ehimaya.conf 644 "$MARK
[Coredump]
Storage=none
ProcessSizeMax=0" || true

# 5. Legal banner (the Office's wording can replace it).
BANNER="نظام معلومات تابع للديوان الوطني للحماية المدنية. النفاذ مرخّص للأعوان المأذونين فقط، وكل عملية مسجّلة.
Système d'information de l'Office national de la protection civile. Accès réservé aux agents autorisés; toute action est journalisée.
Restricted system of the Civil Protection Office: authorized access only. All activity is monitored and logged; unauthorized use is prohibited and subject to legal action."
write_file /etc/issue 644 "$BANNER" || true
write_file /etc/issue.net 644 "$BANNER" || true

# 6. SSH: keys only, no root, short grace, banner. Only when an SSH server is installed.
if [ -d /etc/ssh/sshd_config.d ]; then
  write_file /etc/ssh/sshd_config.d/60-ehimaya.conf 644 "$MARK
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
MaxAuthTries 3
MaxSessions 4
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
LogLevel VERBOSE
Banner /etc/issue.net" && { sshd -t 2>/dev/null && systemctl reload ssh 2>/dev/null || say check "sshd -t then reload ssh"; }
else say skip "no SSH server"; fi

# 7. Firewall: deny inbound by default, then only what the profile needs.
if command -v ufw >/dev/null; then
  RULES=("22/tcp")
  if [ "$PROFILE" = demo ]; then RULES+=("443/tcp" "443/udp" "8189/udp")
  else RULES+=("80/tcp" "443/tcp" "443/udp" "8189/udp")
    [ "${TELEPHONY:-0}" = 1 ] && RULES+=("5060/udp" "5060/tcp" "5061/tcp" "${TELEPHONY_RTP_START:-10000}:${TELEPHONY_RTP_END:-10099}/udp")
  fi
  if [ "$MODE" = check ] && ufw status verbose 2>/dev/null | grep -q "Default: deny (incoming)"; then say ok "ufw active, deny incoming (--apply re-applies ${RULES[*]})"
  elif [ "$MODE" = check ]; then say change "ufw default deny incoming; allow ${RULES[*]}"; CHANGED=$((CHANGED + 1))
  else
    ufw --force default deny incoming >/dev/null; ufw --force default allow outgoing >/dev/null
    for r in "${RULES[@]}"; do
      if [ "$r" = 22/tcp ] && [ -n "${ADMIN_NET:-}" ]; then ufw allow from "$ADMIN_NET" to any port 22 proto tcp >/dev/null
      else ufw allow "$r" >/dev/null; fi
    done
    ufw logging low >/dev/null
    if ufw --force enable >/dev/null 2>&1; then say on "ufw: ${RULES[*]}"; else say skip "ufw enable (no netfilter here)"; SKIPPED=$((SKIPPED + 1)); fi
  fi
fi

# 8. Audit rules: identity, privileges, SSH, time, Docker and the platform's secrets.
ENVFILE="${EHIMAYA_DIR:-/opt/e-himaya}/.env"
write_file /etc/audit/rules.d/60-ehimaya.rules 640 "$MARK
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k privileges
-w /etc/sudoers.d/ -p wa -k privileges
-w /etc/ssh/sshd_config -p wa -k sshd
-w /etc/ssh/sshd_config.d/ -p wa -k sshd
-a always,exit -F arch=b64 -S adjtimex,settimeofday,clock_settime -k time
-w /etc/docker/ -p wa -k docker
-w /usr/bin/docker -p x -k docker
-w $ENVFILE -p rwa -k ehimaya-secrets
-w /var/log/ -p wa -k logs" && { augenrules --load >/dev/null 2>&1 || say skip "augenrules --load (no audit kernel here)"; }
service_on auditd

# 9. Brute force: ban after 5 SSH failures for one hour.
write_file /etc/fail2ban/jail.local 644 "$MARK
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
[sshd]
enabled = true" || true
service_on fail2ban

# 10. Automatic security updates (not the Docker images: those are pinned and updated by pull request).
write_file /etc/apt/apt.conf.d/20auto-upgrades 644 'APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";' || true
service_on unattended-upgrades

# 11. Process accounting, statistics and logs.
[ -f /etc/default/sysstat ] && { grep -q '^ENABLED="true"' /etc/default/sysstat && say ok "sysstat" || { [ "$MODE" = apply ] && sed -i 's/^ENABLED=.*/ENABLED="true"/' /etc/default/sysstat && say written "sysstat"; CHANGED=$((CHANGED + 1)); }; }
service_on acct
service_on sysstat
service_on rsyslog
service_on chrony

# 12. Docker daemon: no new privileges, bounded logs, live restore, no userland proxy.
if [ -d /etc/docker ] || command -v dockerd >/dev/null; then
  DJ=/etc/docker/daemon.json
  NEW=$(python3 - "$DJ" <<'PY'
import json, os, sys
p = sys.argv[1]
d = json.load(open(p)) if os.path.exists(p) and os.path.getsize(p) else {}
d.update({"no-new-privileges": True, "live-restore": True, "userland-proxy": False,
          "log-driver": "local", "log-opts": {"max-size": "20m", "max-file": "5"}})
print(json.dumps(d, indent=2, sort_keys=True))
PY
)
  write_file "$DJ" 644 "$NEW" && say check "restart Docker at a quiet moment: systemctl restart docker"
else say skip "no Docker"; fi

# 13. File permissions: secrets, homes, compilers.
if [ -f "$ENVFILE" ]; then
  if [ "$(stat -c %a "$ENVFILE")" = 600 ]; then say ok "$ENVFILE 600"
  elif [ "$MODE" = apply ]; then chmod 600 "$ENVFILE"; say written "$ENVFILE 600"; CHANGED=$((CHANGED + 1))
  else say change "$ENVFILE 600"; CHANGED=$((CHANGED + 1)); fi
fi
for h in /root /home/*; do
  [ -d "$h" ] || continue
  want=750; [ "$h" = /root ] && want=700
  [ "$(stat -c %a "$h")" -le "$want" ] && continue
  if [ "$MODE" = apply ]; then chmod "$want" "$h"; say written "$h $want"; else say change "$h $want"; fi; CHANGED=$((CHANGED + 1))
done
# Compilers for root only on servers (prod profile, or RESTRICT_COMPILERS=1); a development computer keeps them.
if [ "${RESTRICT_COMPILERS:-$([ "$PROFILE" = prod ] && echo 1 || echo 0)}" = 1 ]; then
  for c in $(for x in /usr/bin/gcc* /usr/bin/g++* /usr/bin/cc /usr/bin/c++ /usr/bin/clang* /usr/bin/as; do [ -e "$x" ] && readlink -f "$x"; done | sort -u); do
    [ "$(stat -c %a "$c")" = 750 ] && continue
    if [ "$MODE" = apply ]; then chmod 750 "$c"; say written "$c 750"; else say change "$c 750"; fi; CHANGED=$((CHANGED + 1))
  done
else say skip "compilers (demo profile; RESTRICT_COMPILERS=1 to restrict)"; fi

# 14. Scheduled jobs readable by root only; a local mail server (pulled in by some tools) answers no VRFY.
for c in /etc/crontab /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly; do
  [ -e "$c" ] || continue
  want=700; [ -f "$c" ] && want=600
  [ "$(stat -c %a "$c")" = "$want" ] && continue
  if [ "$MODE" = apply ]; then chmod "$want" "$c"; say written "$c $want"; else say change "$c $want"; fi; CHANGED=$((CHANGED + 1))
done
if command -v postconf >/dev/null; then
  if [ "$(postconf -h disable_vrfy_command)" = yes ] && [ "$(postconf -h inet_interfaces)" = loopback-only ]; then say ok "postfix"
  elif [ "$MODE" = apply ]; then postconf -e disable_vrfy_command=yes inet_interfaces=loopback-only smtpd_banner='$myhostname ESMTP'; say written "postfix: no VRFY, loopback only"; CHANGED=$((CHANGED + 1))
  else say change "postfix: no VRFY, loopback only"; CHANGED=$((CHANGED + 1)); fi
fi

echo "== done: $CHANGED change(s)$( [ "$MODE" = check ] && echo ' to apply' ), $SKIPPED step(s) skipped in this environment"
echo "   measure: infra/security/audit.sh after <host>   (then compare.py before after)"
