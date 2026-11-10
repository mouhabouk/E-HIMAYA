# OS2: guided call-taking cards and the room agent's guide

Source: idea OS2 of the open-source study (`/mnt/project-files/advice/open-source-ideas.md`), prototyped in isolation
and approved by Yamen on 2026-11-10 ("موافق بإمكانك الشروع في مرحلة التطوير"). The version before this work is kept on
the branch `archive/before-call-cards-2026-11-10`.

## 1. What changes and what stays

- New: one guided card per report category, used by the room agent during a call (telephone, radio, in person).
- New: the room agent's guide page («دليل إجراءات عون القاعة») in the operations menu.
- Unchanged: the citizen's report from the app, the priority formula and its weights, free text entry, the dispatch
  decision (always the head of the room). The card is optional.

## 2. The card (rules shared by `services/api/app/modules/reports/callcards.py` and `apps/dashboard/src/lib/callCards.ts`)

- Questions answered yes, no or doesn't know. A follow-up (`when`) shows once the question it follows got the answer.
- Each answer may carry an effect: a reason, a band, a flag, suggested resources, instructions to read, `lives`, `injured`.
- The band starts at the card's `base_band` and only goes up. A decisive question (`key`) answered «doesn't know» keeps
  the band at **high** at least.
- Instructions to read to the caller have numbered steps; CPR carries a metronome (60 to 140 a minute, 110 seeded).
- The intake form sends `call_card {card_id, version, answers, read}` with `POST /api/v1/staff/reports/room`. The server
  evaluates the answers again against the approved version (409 `call_card_changed` when a new one was approved during
  the call), stores them in `reports.call_card_answer`, prepends an Arabic summary to the report text (the room and every
  dashboard reader see it; the field app's mission does not carry the report text yet, backlog OS2-2), and sets `reports.report.call_card_floor`.
- The SLA band never goes below `call_card_floor`, also when the priority is computed again (`reports/sla.py`).
- The priority: `lives` gives the «life in danger» component 1.0 with the source `call_card`; `injured` gives 0.6 to the
  casualties component (`ai/scoring.py`). The weights do not change.

## 3. Governance (`/api/v1/staff/call-cards`)

| Action | Who (national scope only) | Audit |
|---|---|---|
| Read the cards, try them | operator, ops_manager, content_editor, medical_coordinator | — |
| Write a draft (one per category), edit it, discard it | content_editor, ops_manager | `call_card.draft`, `update`, `discard` |
| Medical validation (medical, drowning, or any medical instruction) | medical_coordinator, content_editor naming the doctor | `call_card.medical_validation` |
| Approve (retires the previous version) | ops_manager | `call_card.approve` |

Editing a draft resets its medical validation. Every write asks for a reason and the `updated_at` read (409
`version_conflict`). The nine seeded cards are version 1, `sim = true`, approved by `[SIM]`: their content waits for the
Office's and the doctor's review.

## 4. The room agent's guide (`/room-guide`)

Eight stages of a report (intake, record, analysis, deadline band, claim, dispatch, closure, after), what is recorded
and who decides, what the card adds, the statuses, the claim deadlines read from the national settings
(`sla.bands`, `sla.claim_delay_s`), and the procedure and rules of the guided call.

## 5. Data

Migration `0100_call_cards`: `reports.call_card`, `reports.call_card_answer` (row-level security like the other
report tables, change journal attached), `reports.report.call_card_floor`, and the nine seeded cards.

## 6. Not done here (backlog OS2-1 to OS2-3)

- Comparing the card's band with what the team found on the scene, to improve the cards.
- Showing the answers on the report page and in the field app (today they are in the report text).
- Statistics of card use and call time per room.
