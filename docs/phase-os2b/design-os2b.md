# OS2-3 and OS2-4: statistics and review of the guided call-taking cards

Source: backlog §3.15 (OS2-3, OS2-4), prototyped in isolation on 2026-11-13 (`/mnt/project-files/additions/18-os2-followups/`)
and approved by Yamen the same day («لك التفويض الكلي … خذ نسخة احتياطية ونفذ»). The version before this work is kept on the
branch `archive/before-os2-followups-2026-11-13`.

## 1. What changes and what stays

- New: the cards page has three tabs, «البطاقات» (unchanged), «الإحصاء» (OS2-3) and «مراجعة البطاقات التجريبية» (OS2-4).
- New: the intake form sends when the agent opened it (`started_at`), and the server records the room that wrote the
  report down (`entered_room`).
- Unchanged: the cards' rules, the intake with or without a card, the priority, the field app. Nothing in the review
  changes a card's content by itself: the nine cards keep their [SIM] text until the Office and the doctor send theirs.

## 2. Statistics (OS2-3): `GET /api/v1/staff/call-cards/stats`

Parameters: `days` (1 to 366, default 30), `channel` (comma separated among `phone`, `radio`, `in_person`, `other`),
`room` (`central` or `g:<code>`, national scope only). Readers: the cards' readers (operator, ops_manager,
content_editor, medical_coordinator). Computed in `app/modules/reports/callcard_stats.py` over the reports with
`source = 'room'` received in the period.

| Figure | How |
|---|---|
| Call time | `telephony.call` answered → ended when the report was written from the dashboard's phone; otherwise `received_at − entry_started_at` (opening the form → saving). Outside 0 s – 2 h it is left out; a form opened more than two hours before saving gives no time. |
| Per room | entered, with a card, median with and without a card, nine calls in ten under (p90), field checked and matched. Room: `entered_room`, or the claimed room for reports entered before migration 0109. |
| Per card | uses, median time, «doesn't know» on decisive questions, the comparisons with the scene (`callcards.compare`: matched, nature differs, lives or injured the card did not foresee, band below the toll). |
| Per question | yes / no / doesn't know, times the team answered differently from the scene, instructions read. |

A regional room always gets its own room (whatever `room` says), with the national figures beside it. No agent is named.
The dashboard exports the figures as CSV (UTF-8 with BOM, opened by a spreadsheet).

## 3. Review of the [SIM] cards (OS2-4)

| Action | Who (national scope) | Endpoint | Audit |
|---|---|---|---|
| Where each card stands, with its reviewers | the cards' readers | `GET /call-cards/review` | — |
| Name the Office's reviewer and the doctor | content_editor, ops_manager | `PUT /call-cards/{category}/reviewers` | `call_card.reviewers` |
| Keep the [SIM] text as it is (a new version, `unchanged`, handed over at once) | content_editor, ops_manager | `POST /call-cards/{category}/confirm` | `call_card.confirm` |
| Notes per question (`_card` for the whole card) | with the draft | `notes` in `POST …/draft`, `PUT /call-cards/{id}` | `call_card.draft`, `update` |
| Hand the draft over | content_editor, ops_manager | `POST /call-cards/{id}/submit` | `call_card.submit` |
| Send it back with a note (withdraws a medical validation) | medical_coordinator, ops_manager | `POST /call-cards/{id}/return` | `call_card.return` |
| Medical validation, approval | as in OS2 | as in OS2 | as in OS2 |

Stage of each card: `not_started` (approved [SIM], no draft), `office` (a draft not handed over, or sent back),
`doctor` (handed over, medical, not validated), `approval` (handed over, validated or not medical), `done` (the approved
version is the Office's own). Editing a draft withdraws its medical validation and the handing over. Every write asks for
a reason and the `updated_at` read (409 `version_conflict`). New refusals: `call_card_note`, `call_card_submitted`,
`call_card_not_submitted`, `call_card_not_sim`.

The review tab shows the progress (x of 9), each card's path (Office → doctor → approval, the doctor struck out for a
card without medical text), the draft against the approved version (changed, new and removed questions, the steps of the
instructions), the statistics of each question beside its change, the Office's notes, and the actions of the person's
role. «ملف المراجعة الورقية» prints every card with its questions, the effects of the answers, the instructions and an
empty column for the reviewer's notes, with the names of the reviewers and a signature line.

## 4. Data

Migration `0109_call_card_review` (after `0107_par`): `reports.report.entered_room`, `entry_started_at`;
`reports.call_card.submitted_at`, `submitted_by_name`, `returned_at`, `returned_by_name`, `returned_reason`,
`unchanged`, `notes`; the table `reports.call_card_reviewer` (change journal attached). UML: `7z-state-call-card-review`.

## 5. Not done here

- The content itself: the nine cards wait for the Office's text and, for the medical ones, the doctor's validation.
- A target per room (for example a share of calls with a card) and an alert when it drops: proposed as OS2-5.
