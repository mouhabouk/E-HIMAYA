#!/usr/bin/env bash
# Rebuilds every living reference of the project in one run (Yamen, 2026-11-13), so they follow the work:
#
#   requests-tracker.html     the request tracker (scripts/tracking/build.py)
#   mindmaps.html             one mind map per phase (scripts/tracking/mindmap.py)
#   ehimaya-ui-reference.xlsx the workbook of every element of every surface (scripts/ui_reference/build.py)
#   model/                    the relational model: DBML, draw.io, PNG, Word (docs/deliverables/data-model)
#   web.html                  the spider web surfaces → screens → server modules → tables (scripts/atlas/web.py)
#   atlas/                    the flowchart atlas in chapters: the dashboard, the portal and both apps with every tab and
#                             window, and the links between each app and the dashboard (scripts/atlas/run.sh)
#   sim-guide.html            the guide to the [SIM] data and how each item becomes real, with what is still [SIM] in
#                             the database (scripts/sim_guide/build.py); docs/sql/sim-guide.md is rewritten with it
#
# The menu's 4 blocks and 20 systems come from one file, apps/dashboard/src/menu/menu.json (Yamen 2026-11-13): the
# workbook's «القائمة» sheet, the atlas's groups, the web's screens and the menu's mind maps all read it, so a change
# there shows everywhere on the next run. The run stops first if the menu and the screens drifted apart.
#
#   scripts/refresh-all.sh <out-dir> [--no-atlas]
#
# Needs what the API tests need (a migrated local database in DATABASE_URL and MIGRATION_DATABASE_URL,
# services/api/.venv), plus openpyxl, Graphviz, docs/deliverables/node_modules and, for the atlas,
# apps/dashboard/node_modules, apps/portal/node_modules and Playwright's Chromium; Flutter (on PATH or in FLUTTER) for the
# two mobile apps, whose screens are skipped otherwise. The tables, schemas and relations are counted on that
# database. The DBML and draw.io files are also written back to docs/data-model/ so the repository keeps them.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$(mkdir -p "${1:?usage: refresh-all.sh <out-dir> [--no-atlas]}" && cd "$1" && pwd)
ATLAS=${2:-}
PY="$ROOT/services/api/.venv/bin/python"
DB=${MIGRATION_DATABASE_URL:-${DATABASE_URL:?DATABASE_URL is needed}}
DB=${DB/+asyncpg/}

echo "0/6 menu: one source, every screen reached"
python3 "$ROOT/scripts/menu/sync.py" --check
python3 "$ROOT/scripts/menu/check.py"
echo "0/6 [SIM] guide: every simulated source of the migrations is in the guide"
python3 "$ROOT/scripts/sim_guide/build.py" --check

echo "1/6 backend dump"
(cd "$ROOT/services/api" && "$PY" ../../scripts/ui_reference/backend_dump.py >"$OUT/backend.json")

echo "2/6 request tracker and mind maps"
python3 "$ROOT/scripts/tracking/build.py" "$OUT/requests-tracker.html"
python3 "$ROOT/scripts/tracking/mindmap.py" "$OUT/mindmaps.html"

echo "3/6 UI reference workbook"
python3 "$ROOT/scripts/ui_reference/build.py" --backend "$OUT/backend.json" --out "$OUT/ehimaya-ui-reference.xlsx"

echo "4/6 relational model"
mkdir -p "$OUT/model"
python3 "$ROOT/docs/deliverables/data-model/extract.py" "$DB" "$OUT/model"
(cd "$ROOT/docs/deliverables" && [ -d node_modules ] || npm install --no-audit --no-fund >/dev/null)
node "$ROOT/docs/deliverables/data-model/build.js" "$OUT/model" "$OUT/model/e-Himaya_Modele_Relationnel.docx"
command -v soffice >/dev/null && (cd "$OUT/model" && soffice --headless --convert-to pdf e-Himaya_Modele_Relationnel.docx >/dev/null 2>&1 || true)
cp "$OUT/model/e-Himaya_Database.dbml" "$OUT/model/e-Himaya_Database.drawio" "$ROOT/docs/data-model/"

echo "5/6 spider web"
python3 "$ROOT/scripts/atlas/web.py" --xlsx "$OUT/ehimaya-ui-reference.xlsx" --backend "$OUT/backend.json" --out "$OUT/web.html"

echo "5b/6 [SIM] data guide"
python3 "$ROOT/scripts/sim_guide/build.py" --html "$OUT/sim-guide.html"

if [ "$ATLAS" != "--no-atlas" ]; then
  echo "6/6 flowchart atlas"
  "$ROOT/scripts/atlas/run.sh" "$OUT/atlas"
else
  echo "6/6 flowchart atlas skipped"
fi
echo "done → $OUT"
