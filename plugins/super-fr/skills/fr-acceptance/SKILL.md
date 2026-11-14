---
name: fr-acceptance
description: >
  Drive the acceptance matrix: backfill an existing repo's business-level
  acceptance tests into its per-feature fragments (docs/acceptance/features/), flip row statuses as
  evidence lands, and keep the CI gate honest. Use when: "backfill the
  acceptance matrix", "acceptance debt", "add acceptance rows", a session
  starts with an acceptance-debt nag, `fr acceptance check` fails, or a
  claim is owed a live run on a harness other than the one you are on.
---

# fr-acceptance

The acceptance matrix is the registry of business-level acceptance tests × verification levels (unit/api/int/ui) × automation status. Its rows live in per-feature **fragments**, `docs/acceptance/features/<spec-slug>.yaml`, each owned by the feature (spec) that created it (`legacy.yaml` for rows with no single origin spec); the matrix every command reads is a fold of them, never a stored file. A repo still holding the old single `docs/acceptance/matrix.yaml` is split by `fr migrate artifacts --yes`. This skill drives the agent-side work; the mechanics live in the CLI.

**Announce at start:** "I'm using fr-acceptance to work the acceptance matrix." Check the setting first: If `fr settings show --json` reports `artifacts.acceptance` as `off`, this repo's matrix is disabled by repo setting: there is nothing to backfill, and `fr acceptance add`, `set-status` and `init` refuse. Stop there.

## Statuses — the honesty scale

`ci` / `scheduled` = automated · `walked` = proven live (dated by its walk) · `manual` = never automatable ·
`local` = a test anyone can run, in a repo with no CI (a move to it needs every level ref resolving in this repo, and no CI; `deliver` stamps it) ·
debt: `unwired`, `walk-owed`, `not-implemented`, a `local` row `unstamped` / `stale: <path>` / `promote to ci` / `ci unknown` · `failing` = known red, `fr acceptance check` exits 2.
Statuses move **explicitly, never silently** — with `fr acceptance
set-status`, never a hand-edit; when in doubt between ci and unwired,
**choose unwired**. Do not inflate coverage; the operator audits at review.

## Backfill an existing repo

1. `fr acceptance init` (idempotent) if the repo has no `docs/acceptance/features/` —
   that directory + rule + gitignore entry; a CI workflow only beside existing CI (or `--with-ci`).
2. `fr acceptance backfill` — emits the inventory (Test Plan specs not yet
   cited, plans without linked rows, test-tree hints) + this protocol.
3. DRAFT rows — **one row per business acceptance, not per test** — via
   `fr acceptance add --id <kebab> --capability <group> --acceptance
   "<operator can X>" --origin spec:<slug>#R<n> --level unit=<repo>:<path>#<test>
   --status <honest> --notes "<evidence / backfill owed>"`. The row lands in its
   origin spec's fragment; a row citing no single spec needs `--feature <slug>`
   (`legacy` for none). Never hand-edit a fragment; `add` validates and writes.
4. `fr acceptance check` → fix errors (unresolved refs, staleness, schema),
   re-run until only honest warnings remain.
5. Open a review PR: the operator audits every status.

## Flip statuses (execution hand-off)

When a plan phase carrying `acceptance: [row-ids]` completes, flip those rows
up the ladder (`not-implemented` → `unwired` → `ci`/`scheduled`) with
`fr acceptance set-status --id <row> --status <new> --notes "<why it moved>"
--level unit=<repo>:<path>` — one command for the whole transition: it moves
the row in place when it is still pending on this branch, and adds the test refs that
justify the move; reports are derived, never committed. `--notes` is required, and an unknown id is refused
rather than created (`add`'s job), as is `ci` in a repo with no CI config. Under `ci: none` (see `fr services`) the local suite is the gate: `ci` needs a declared or detected CI service.
`fr plan edit --complete-phase` warns on unflipped rows — fix or record why in the completion note.
**A row an earlier feature MERGED** changes only by amendment, appended to YOUR feature's fragment (`--feature <spec-slug>`, else the spec of this branch's run; with neither, `set-status` refuses too; a post-merge walk names the feature whose gate it closes): `fr acceptance amend --id <row> --op <op> --why "<reason>"`, with `reword` (`--acceptance`/`--capability`), `set-status` (`--status --notes`, optional `--issue`/`--verify`/`--scenario`), `add-level`/`drop-level` (`--level <level>=<ref>`) or `retire` (`--notes`); `set-status` on a merged row writes them for you, and a record's `acceptance:` entry `{row, op, why, …}` is one too. Never edit a merged row in place (`check` refuses it). If another feature amended the row first, `check` and `deliver` fetch the default ref and refuse your stale base (exit 2): review the row, then `fr acceptance amend --rebase`. A stale amendment merged anyway marks the row **contested**: debt until the next amendment at its current revision.

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
   (`FR_SHIPPED_WORKFLOWS_DIR`, `FR_REPO_ROOT`, a redacted `FR_HOSTNAME`).
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

fr's own artifacts are cited **logically** — `spec:<slug>[#R<n>]` (the spec's file name
minus `-design.md`), `plan:<slug>` — so an archive never rewrites a row. Other refs are
`<repo>:<path>[#anchor]`, siblings verified only where a checkout exists
(`--sibling-root`, default `..`); a `.py` anchor names the test (`#TestX::test_y`), never
`#L<n>`. `fr acceptance report [--open] [--format md]` renders the derived report locally (git-ignored, never committed; `check` fails on a tracked one), `pages-check` says whether a Pages site would be no wider than the repo (it fails closed), `comment --pr N --yes` keeps the one PR report comment when `forge.report_comment` is on; `status` is the terminal nag;
`digest` feeds the weekly "Acceptance debt" issue upsert.

A row born from a spec's `## Requirements` list cites the requirement, not just
the spec: `--origin spec:<slug>#R<n>` (repeat `--origin` for several ids).
A row only a live, operator-driven run can prove — never a unit test — carries `--verify live` (the old `post-merge` spelling migrates to it); it keeps nagging in `fr acceptance status` whatever its status, and the PR body lists it under `## Post-merge verification owed`. `--verify <strategy|none>` takes any strategy `fr verification list` resolves, or `none` (verified some other way; the spec's `## Verification` says what); `set-status --verify` sets it too, and omitting the flag preserves what the row already carries.

## Walks, issues and closing on live evidence

A row may cite the issues whose promise it carries (`--issue owner/repo#n`, repeatable), name its walk script (`--scenario <repo-relative path>`; a row on an agent-driven pre-merge strategy needs one) and the harnesses its promise covers (`--harness` on `add`). `set-status --walk <evidence> --harness <h> --model <m> --strategy <s>` appends a walk (all three flags required; `--walk-outcome` defaults to `pass`; evidence is a log path or a note). A row is **walk-verified** once it has a passing walk on every harness it names, or on any one if it names none; until then a post-merge row holds its issues open, and `deliver` refuses a PR body that closes one (it says `Refs`). When a recorded walk makes a row walk-verified, `set-status` PRINTS, for each issue it cites that no other row still holds open, the forge's commands to close it and remove the `fr:awaiting-live` label (manual steps where a forge's command line lacks one; nothing under `tracking: none`) — run them yourself, fr never closes an issue; the post-merge close-out brief prints the matching command that ADDS the label to each issue the PR only `Refs`. Authoring a strategy such as `staging`: `docs/verification-strategies.md`.
