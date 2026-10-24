# End-of-phase update (standing rule)

**Rule (Yamen, 2026-10-24):** at the end of every phase, not after each element, the following four deliverables are
brought up to date together with the phase report and `docs/versions.md`:

| Deliverable | Output | Source to edit and how to rebuild |
|---|---|---|
| Design reference (colours and codes, icons, frames and shapes, fonts, sources and download links) | `docs/design-reference.html` | `python3 docs/deliverables/design-reference.py` from the repo root; it reads the tokens in `apps/mobile/lib/core/ui/tokens.dart`, the icons in `apps/dashboard/src/components/Icon.tsx` and the mobile `Icons.*` in use |
| UML diagrams (context, interactions, architecture, use case, class, sequence, state) | `e-Himaya_Diagrammes_UML.docx` / `.pdf` and `e-Himaya_UML_sources.zip` in the project files (`diagrams/`) | `docs/deliverables/uml/src/*.puml` (PlantUML), then `node docs/deliverables/uml/build.js <out.docx>` with the PNGs in `out/` next to it |
| Project description, written to serve as the specification (cahier des charges): requirements with ID, priority, status and phase; NFR; technical requirements; acceptance criteria; decisions; roadmap | `e-Himaya_Description_V<n>.docx` / `.pdf` in the project files (`spec/`) | `docs/deliverables/description/content.js`, then `node docs/deliverables/description/build.js <out.docx>`; bump the version, keep the previous one |
| Specification chapters | same document as above | requirement statuses move from "approved" to "done" when the phase delivers them |

Checklist at the end of a phase:

1. New or changed requirements: statuses, phase column, counts (API operations, tests, migrations), roadmap row.
2. New flows, entities or actors: the matching use-case, class and sequence diagrams; a new diagram when a flow is new.
3. New colours, icons, components or fonts: the design reference regenerated.
4. The version history line in each document says what changed and in which phase.
5. Files copied to the project files and linked in the phase report.
