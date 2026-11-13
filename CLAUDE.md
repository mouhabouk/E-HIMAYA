# Notes for Claude sessions

- Replies to the project owner (Yamen) are in Arabic.
- Every surface follows `docs/design-system.md` (standing rule).
- Integration first (Yamen, 2026-11-13, standing rule): a new feature joins the screens, pages and data that already
  exist (crisis axis, decision window, interactive map ...) instead of a new standalone page; no duplicated element or
  hazard drawn twice. Any data on a map is also an optional layer of the interactive map, without removing its source.
- Living references follow development (Yamen, 2026-11-13, standing rule): the atlas and the other generated references
  (tracker, mind maps, workbook, model, web) are rebuilt by `scripts/refresh-all.sh`, never edited by hand. A new screen,
  tab or window joins the atlas on the next run; give it a line in `scripts/atlas/apps_catalog.py` (apps) or
  `scripts/atlas/content.py` (dashboard) for a better title, and in `scripts/atlas/chapters.py` if it opens a new system.
- At the end of every phase, update the design reference, the UML diagrams, the project description, the
  specification and the presentation for officials together, as described in `docs/phase-end.md`. Not after each element.
- One HTML report per phase, plus `docs/versions.md`. Simulations carry the amber [SIM] badge.
- Never merge pull requests; the owner merges.
- GitHub visibility (Yamen, 2026-10-25): the repository stays public while work and CI run, to shorten CI time.
  At the end of every step, tell Yamen in so many words "اجعل الجيت هيب عام" (before pushing or while CI must
  run) or "اجعل الجيت هيب خاص" (once a step is merged and nothing needs CI). Never change visibility yourself.
