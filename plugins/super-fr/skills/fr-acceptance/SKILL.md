---
name: fr-acceptance
description: >
  Drive the acceptance matrix: backfill an existing repo's business-level
  acceptance tests into docs/acceptance/matrix.yaml, flip row statuses as
  evidence lands, and keep the CI gate honest. Use when: "backfill the
  acceptance matrix", "acceptance debt", "add acceptance rows", a session
  starts with an acceptance-debt nag, `fr acceptance check` fails, or a
  claim is owed a live run on a harness other than the one you are on.
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
Statuses move **explicitly, never silently** — with `fr acceptance
set-status`, never a hand-edit; when in doubt between ci and skipped,
**choose skipped**. Do not inflate coverage; the operator audits at review.

## Backfill an existing repo

1. `fr acceptance init` (idempotent) if the repo has no matrix — matrix +
   rule + gitignore entry; a CI workflow only beside existing CI (or `--with-ci`).
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
up the ladder (`not-implemented` → `skipped` → `ci`/`scheduled`) with
`fr acceptance set-status --id <row> --status <new> --notes "<why it moved>"
--level unit=<repo>:<path>` — one command for the whole transition: it moves
the row in place, adds the test refs that justify the move, and regenerates the
three committed reports. `--notes` is required, and an unknown id is refused
rather than created (`add`'s job), as is `ci` in a repo with no CI config. Under `ci: none` (see `fr services`) the local suite is the gate: `ci` needs a declared or detected CI service.
`fr plan edit --complete-phase` warns on unflipped rows — fix or record why in the completion note.

## Live verification on another harness

Some claims are owed a **live** run: a real binary with a real model, not a
unit test that sets the harness by hand. You can pay that debt without being
on the harness in question — the session doing the work (the **driver**)
steers a second agent session (the **target**) in a neighbouring terminal.
Driver and target can be any two harnesses; nothing below depends on which.
This needs a terminal multiplexer that lets one session start, prompt and read
another — herdr does this today when the driver runs inside it (`HERDR_ENV=1`,
CLI from `herdr --skill`, not memory); any multiplexer with the same abilities
works.

1. **Build a scratch fixture from real artifacts.** Make a throwaway git repo
   with an fr-isolation linked worktree and its marker, and a run parked just
   before the step under test. Copy artifacts from a real (archived) plan. A
   hand-made `_meta.yaml` is refused by the migration gate, as it should be.
2. **Open a sibling terminal in the fixture.** With herdr:
   `herdr pane split --current --direction down --cwd <fixture> --no-focus`.
3. **Clean the target's env before starting it.** fr detects the harness from
   environment keys in a fixed order, so a key leaked from the driver makes fr
   record the **driver** as the harness, and the test goes green on the
   wrong thing. Check the new terminal's env for every harness's detection
   keys and for `FR_HARNESS`, and set neither. Export only fixture plumbing
   (`FR_SHIPPED_WORKFLOWS_DIR`, `VK_REPO_ROOT`, a redacted `FR_HOSTNAME`).
4. **Start the target and give it a closed command list** ("run exactly
   these, one at a time; edit nothing"). With herdr:
   `herdr agent start <name> --kind <kind> --pane <id> -- <args>`, then
   `herdr agent prompt <name> "<commands>" --wait`.
5. **Judge from disk, never from the target's summary.** Read the artifact and
   `git show --name-only HEAD` yourself.
6. **For gates that read the forge**, e.g. `deliver`'s live PR-body check,
   point at an already-merged fr PR whose body has the required sections.
   This only reads the PR. Nothing is written to it.
7. **Record, then tear down.** Move the row with `fr acceptance set-status`.
   The notes name the target harness and its version, and state that detection
   came from the target's own env. Then close the target's terminal and delete
   the fixture.

A closed command list proves fr behaves correctly under the target harness; it
does not prove the target follows a skill's prose over a long run — for that,
prompt the skill itself and wait longer. The notes must say which was proven.

## Mid-flight additions (encouraged, then defended)

During planning or implementation, ADD a row the moment a legitimate business
need surfaces (a missed edge, a review-found failure mode, a constraint turned
load-bearing) — never silently widen or narrow scope. Every addition is
presented in the PR body ("rows added since brainstorm", generated via
`fr acceptance check --added-since <base-ref>`) with a one-line defense.

## Refs, requirement origins and post-merge rows

Refs are `<repo>:<path>[#anchor]` — own repo by its own name, sibling
repos verified only where a checkout exists (`--sibling-root`, default `..`);
a `.py` fragment names the test (`#TestX::test_y`), never a rotting `#L<n>`.
Archived specs auto-resolve (`specs/` ↔ `implemented/specs/`) — `check` warns,
never errors, on a moved ref. `fr acceptance report` renders the HTML;
`fr acceptance status` is the terminal nag; `fr acceptance digest` feeds the
weekly "Acceptance debt" issue upsert.

A row born from a spec's `## Requirements` list cites the requirement, not just
the spec: `--origin <repo>:<spec-path>#R<n>` (repeat `--origin` for several ids).
A row only a live, operator-driven run can prove — never a unit test — carries
`--verify post-merge`; it keeps nagging in `fr acceptance status` whatever its
status, and the PR body lists it under `## Post-merge verification owed`. `set-status --verify post-merge` sets it
too; omitting the flag preserves what the row already carries.
