#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 4: تشغيل المنظومة الأساسية واختبار الدخان، الدليل التقني §7.
#
# متى: بعد 03-project-fetch.sh. أين: على الخادم (أو جهاز المطوّر).
#
# ما يفعله:
#   1. يتحقق من وجود .env و Docker؛
#   2. يبني الصور ويشغّل الخدمات الأساسية: PostgreSQL (PostGIS و pgvector)، Valkey، NATS، SeaweedFS، tusd، Keycloak،
#      الواجهة البرمجية والعامل، MediaMTX، Asterisk. البناء الأول يستغرق من 10 إلى 30 دقيقة؛
#      ترتيب الإقلاع يضبطه compose نفسه: postgres ثم db-roles ثم migrate (ترحيلات القاعدة آليًا) ثم api؛
#   3. ينتظر حتى تجيب /health/ready (حتى 10 دقائق) ثم يعرض حالة الحاويات؛
#   4. يشغّل اختبار الدخان infra/smoke/smoke_test.py: بلاغ مجهول، رفع ملف بالاستئناف، والتحقق من البصمة.
#
# الاستعمال: scripts/install/04-stack-start.sh
#            PROFILES="sim" scripts/install/04-stack-start.sh      # مع محاكيات العرض [SIM] (جهاز التطوير والعرض فقط)
# العناوين المحلية بعده (كلها على 127.0.0.1؛ من جهاز الإدارة: ssh -L 8080:localhost:8080 -L 8000:localhost:8000 ...):
#   الواجهة البرمجية http://localhost:8000/docs — Keycloak http://localhost:8080/admin — صندوق المحاكاة http://localhost:8090
# بعده: scripts/install/05-first-admin.sh
source "$(dirname "$0")/00-common.sh"
require_env_file
need docker 02-docker-install.sh

args=()
for p in ${PROFILES:-}; do args+=(--profile "$p"); done

step "1/3 البناء والتشغيل (المرة الأولى طويلة)"
"${COMPOSE[@]}" "${args[@]}" up -d --build

step "2/3 انتظار الجاهزية"
if wait_http http://localhost:8000/health/ready 600; then
  ok "الواجهة البرمجية جاهزة"
else
  "${COMPOSE[@]}" ps
  die "لم تصبح جاهزة في 10 دقائق؛ اقرأ السجل: docker compose --env-file .env -f infra/compose.yml logs --tail 100 api migrate"
fi
"${COMPOSE[@]}" ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}'

step "3/3 اختبار الدخان"
python3 "$ROOT/infra/smoke/smoke_test.py"
ok "المنظومة الأساسية تعمل. التالي: scripts/install/05-first-admin.sh"
