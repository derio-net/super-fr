# Journal: 2026-10-05-triage-batch-board

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-05T20:19:20+00:00 input=true -->
### operator-brief · discovery · Operator brief (verbatim)

I would like an extension for the Triage pages, the Wave Driver and the herdr dispatcher.. A new artifact that shows the state of all prepared/dispatched issues as a Kanban board, is refreshed via the state changes (or timer) and can be used to quickly jump to a corresponding herdr session (e.g. clicking on a button copies the herdr command that can be used to jump to the correct session). Each item should be expanded to show more information about it

<!-- fr:journal kind=decision scope=spec id=d1-card-unit created=2026-10-05T20:19:20+00:00 -->
### d1-card-unit · decision · One card per batch

A batch is one session, one branch, one PR; member issues appear inside the expanded card. (Q1, recommended option chosen.)

<!-- fr:journal kind=decision scope=spec id=d2-columns created=2026-10-05T20:19:20+00:00 -->
### d2-columns · decision · Lifecycle columns

Proposed, Waiting, Running, PR open, Closing out, Done; cancelled/abandoned/partial sit in Done with a pill. (Q2, recommended.)

<!-- fr:journal kind=decision scope=spec id=d3-artifact created=2026-10-05T20:19:20+00:00 -->
### d3-artifact · decision · Separate board.html via `fr triage board`

Written beside triage.html in the triage state dir; triage.html links to it. (Q3, recommended.)

<!-- fr:journal kind=decision scope=spec id=d4-refresh created=2026-10-05T20:19:20+00:00 -->
### d4-refresh · decision · Drive re-renders each pass, page reloads on a timer

Drive writes board.html after every acting pass; the page reloads itself (default 30s) keeping expanded cards and scroll; `fr triage board --watch` re-collects and re-renders when no drive runs. (Q4, recommended.)

<!-- fr:journal kind=decision scope=spec id=d5-jump-command created=2026-10-05T20:19:20+00:00 -->
### d5-jump-command · decision · Jump copies a new fr verb

The button copies `fr triage batch focus <batch-id>`, which resolves the session by label through the runner at run time and focuses it. (Q5, recommended.)

<!-- fr:journal kind=decision scope=spec id=d6-live-status created=2026-10-05T20:19:20+00:00 -->
### d6-live-status · decision · Live session status read at render

Render asks each batch's runner for session status through an optional capability; failures show `unknown`, never fail. Blocked sessions are highlighted. (Q6, recommended.)

<!-- fr:journal kind=decision scope=spec id=d7-expanded-content created=2026-10-05T20:19:20+00:00 -->
### d7-expanded-content · decision · Expanded card content

Members + PR + CI, lifecycle details, event timeline with close-out jump, and a next-action hint. (Q7, all four options chosen.)
