---
name: fr-acceptance
description: >
  Drive the acceptance matrix: backfill an existing repo's business-level
  acceptance tests into docs/acceptance/matrix.yaml, flip row statuses as
  evidence lands, and keep the CI gate honest. Use when: "backfill the
  acceptance matrix", "acceptance debt", "add acceptance rows", a session
  starts with an acceptance-debt nag, or `fr acceptance check` fails.
---

# fr-acceptance

The matrix (`docs/acceptance/matrix.yaml`) is the registry of business-level
acceptance tests × verification levels (unit/api/int/ui) × automation status.
This skill drives the agent-side work; the mechanics live in the CLI.

**Announce at start:** "I'm using fr-acceptance to work the acceptance matrix."

## Statuses — the honesty scale

`ci` / `scheduled` = automated, cannot drift · `skipped` = verification exists
but not in CI (warning, backfill owed) · `not-implemented` = nothing yet
(warning) · `failing` = known red, `fr acceptance check` exits 2 and CI fails.
Statuses move **explicitly, never silently**. The drift channel is precisely
the hand-tracked claims — when in doubt between ci and skipped, **choose skipped**.
Do not inflate coverage; the operator audits statuses at review.

## Backfill an existing repo

1. `fr acceptance init` (idempotent) if the repo has no matrix — scaffolds
   matrix + CI workflow + backfill rule + gitignore entry.
2. `fr acceptance backfill` — emits the inventory (Test Plan specs not yet
   cited, plans without linked rows, test-tree hints) + this protocol.
3. DRAFT rows — **one row per business acceptance, not per test** — via
   `fr acceptance add --id <kebab> --capability <group> --acceptance
   "<operator can X>" --origin <repo>:<path> --level unit=<repo>:<path>
   --status <honest> --notes "<evidence / backfill owed>"`. Never hand-edit
   YAML shapes; `add` validates and appends.
4. `fr acceptance check` → fix errors (unresolved refs, staleness, schema),
   re-run until only honest warnings remain.
5. Open a review PR: the operator audits every status.

## Flip statuses (execution hand-off)

When a plan phase carrying `acceptance: [row-ids]` completes, flip those rows
up the ladder (`not-implemented` → `skipped` → `ci`/`scheduled`), citing the
test refs that justify the move in `levels` and `notes`. `fr plan edit
--complete-phase` warns on unflipped rows — fix or record why in the
completion note.

## Mid-flight additions (encouraged, then defended)

During planning or implementation, ADD a row the moment a legitimate business
need surfaces (a missed edge, a review-found failure mode, a constraint turned
load-bearing) — never silently widen or narrow scope. Every addition is
presented in the PR body ("rows added since brainstorm", generated via
`fr acceptance check --added-since <base-ref>`) with a one-line defense.

## Refs and the gate

Refs are `<repo>:<path>[#Lline|#anchor]` — own repo by its own name, sibling
repos verified only where a checkout exists (`--sibling-root`, default `..`).
Archived specs auto-resolve (`specs/` ↔ `implemented/specs/`) — `check` warns,
never errors, on a moved ref. `fr acceptance report` renders the HTML;
`fr acceptance status` is the terminal nag; `fr acceptance digest` feeds the
weekly "Acceptance debt" issue upsert.
