# Triage board and labels that tell the truth — design

**Date:** 2026-10-12
**Batch:** `board-truth` (derio-net/super-fr#1085, #1065, #1109, #1111, #1122), one PR on `feat/batch-board-truth`.
**Workflow:** `fr-goal`

## Background

Five reports about one thing: the triage engine's outward surfaces — the
`fr:in-progress` label on the forge, the batch board's cards, the page nav, and
the board's view of a repo it could not read — say something the durable state
does not.

- **#1085.** `fr triage batch dispatch` adds `fr:in-progress` to every member
  (`commands/triage_batch_cmd.py:1066-1075`). Only `batch cancel` removes it
  (`triage_batch_cmd.py:833`). The claim release path, `claim_writes.release`
  (`triage/claim_writes.py:193-224`), removes only `fr:claimed`. A batch that merges,
  closes out and archives therefore leaves `fr:in-progress` on every closed member:
  197 such issues on derio-net/super-fr on 2026-10-07. Collect lists only open
  issues (`triage/collect.py:540`), so nothing in fr can see the drift.
- **#1065.** The card front (`triage/kanban_render.py:296-321`) always shows the
  batch session's status pill and builds Jump with `closeout=False` (`:307`).
  During a close-out the front therefore reads, and jumps to, the wrong session.
  The close-out's pill and Jump live only in the body (`:279-286`). The batch
  session's body entry has only a code line, no Jump button (`:274-277`).
- **#1109.** `collect` reads `.fr/triage.yaml` strictly unless `lenient` is
  passed (`triage/collect.py:713-731`). Only the wave driver passes it (gh#998). A
  config written for a newer fr, such as `merge_method` read by an older parser,
  fails the read. In org scope that repo is `skipped` (`collect.py:550-556`), its
  issues vanish from the facts, and its active batch reads as unreachable. The
  skip surfaces only as one line among the board's notes (`triage/render.py:662`).
- **#1111.** `derive_batch_stage` now folds only dispatch/cancel events
  (`triage/batch.py:254-266`, from #1115). `releasing()` treats `cancelled` as
  releasing (`triage/claims.py:289-292`), so a cancelled batch owes no claim. The
  report appears fixed on main, but no test pins the reported sequence
  `dispatch → cancel → claims_released` end to end.
- **#1122.** `page_header()` (`triage/components.py:265-277`) renders the fixed
  four-entry `PAGES` tuple (`:50-64`) whatever the scope has. On org scopes,
  Origins and Architecture link to pages that were never written. `board.html`
  (`commands/triage_kanban_cmd.py:69`) is not a tab and carries no nav
  (`kanban_render.py`'s own `<h1>Batch board</h1>` header). The `PAGES` entry
  titled "Board" is `triage.html`, which clashes with the real board.

## Requirements

R1. When this scope releases a member's claim for a batch that is releasing
(cancelled, abandoned, or archived), it also removes `fr:in-progress` from that
member, but only when no other scope's claim stands on it. The cancel path keeps
its current behaviour.

R2. `fr triage collect` reads, per repo, the closed issues still labelled
`fr:in-progress`. `fr triage check` reports them as a set, "closed but in
progress". A member another scope's un-released claim stands on (`fr:claimed`
present) is listed as held and is not a cleanup target. The board names the set.

R3. A new verb removes `fr:in-progress` from every issue of R2's cleanup set. It
writes nothing without `--yes` and prints its plan instead. It writes only through
the forge adapter: GitHub only, and glab/tea refuse with
`UnsupportedForgeOperation`.

R4. Every `fr triage collect` reads `.fr/triage.yaml` leniently. An unknown
top-level key is dropped and named in the stats, never refused, so a newer config
never skips its repo.

R5. Ignored config keys and skipped repos are a prominent scope-level banner on
`triage.html` and `board.html`, and are named by `fr triage check` (text and
JSON). They are no longer a line among the notes.

R6. While a batch's close-out session is live (status known and not `absent`),
the card front's status pill and Jump button follow the close-out session
(`fr triage batch focus <id> --closeout`). Otherwise the front follows the batch
session as today.

R7. The card body offers a real Jump button for whichever session the front does
not show, beside its focus command.

R8. A batch that was dispatched, then cancelled, then had its claims released
(wave or wave-less, one or several members) derives as `cancelled`, owes no claim
and no release, and never renders as Running. A collect and render right after
keep that state.

R9. One page registry says, for each triage page, its file, tab title, goal
sentence, and when it is present: Backlog (`triage.html`) always; Batches
(`board.html`) when it exists in the state dir or the scope has batches; Origins
when `origins-facts.json` or `origins.html` exists; Architecture when
`architecture.html` exists; History always. Nav order: Backlog, Batches, Origins,
Architecture, History.

R10. Every triage page's nav lists only the pages present, marks the current page
`aria-current="page"`, and is followed by that page's goal sentence. This includes
`board.html`.

R11. Every render rewrites the nav block of every other existing triage page in
the state dir, so all pages agree after any render. A page whose file is absent is
never linked.

R12. `triage.html` is titled "Backlog" and `board.html` "Batches" everywhere: the
nav, the board's own header, and the fr-triage skill's "Pages and state" section,
which also documents which pages exist per scope kind.

## Design

### A. `fr:in-progress` follows the release (R1)

`claim_writes.release` already decides, after re-reading the issue's claims,
whether any other scope's claim stands (`if not [c for c in claims if c.signer !=
signer]`). Under that same condition it removes `fr:in-progress` along with
`fr:claimed`, in one `edit_issue_labels` call. The removal happens only when the
release is for a batch (`batch` set). The bare release of own claims that no
batch owes is unchanged. That release runs for members `batch edit
--remove-issue` dropped, and the cancel path already handles their labels.

Every releasing path reaches this function: the driver's `claim sync`, `batch
merge`'s close-out, `cancel`, and `claim release`. One rule, one writer. A member
another scope holds keeps both labels (claims R6). A legacy batch with no claim
marker returns `Done("none")` before any write, so its labels stay. R2 and R3
cover those.

### B. The closed-but-in-progress set and its cleanup verb (R2, R3)

`Forge.list_issues` gains an optional `labels` filter, implemented for gh and the
REST client (both list by label natively). Collect makes one extra call per
collected repo, `state=closed, labels=[fr:in-progress]`, bounded by
`issue_limit`. The result lands in a new facts field, `stale_in_progress`: key,
title, url, closed_at, and `held` (true when `fr:claimed` is also present). The
facts schema moves 8 → 9. Reading 3–9 keeps working, because the field defaults
to empty. `facts.json` is a cache, not a registered artifact kind, so no artifact
migration is owed.

`fr triage check` adds the set `closed_in_progress` (JSON) and a text section
that lists the held ones apart. The backlog page shows it as a collapsed section,
and the board as a note-level count with the cleanup command.

The verb is `fr triage clean-labels [--yes]`. It is in the triage command group,
which is already exempt from the migration gate. Without `--yes` it prints one
line per target and "nothing written". With `--yes` it removes the label through
`GhClient.edit_issue_labels` from each non-held target and prints one outcome line
per issue. A per-issue failure is reported and the rest continue, with a non-zero
exit if any failed. It acts on the facts' set, so the operator collects first;
the verb says so when facts are older than its own start.

### C. Lenient collect and the skew banner (R4, R5)

`collect_facts` drops its `lenient` parameter and always reads the config
leniently. The facts' stats keep the ignored keys per repo, as they already do
for the driver. A config that is invalid for any other reason (a bad value, a
non-mapping) still skips the repo in org scope and fails in repo scope.

`components.py` gains one `skew_banner(facts)` component. It renders a `role="alert"`
block naming each repo's ignored keys ("written for a newer fr: upgrade fr to read
them") and each skipped repo with its reason. `triage.html` and `board.html`
render it directly under the nav, and `render.py:662`'s skipped-repo note line
goes. `fr triage check` prints the same facts first in text output and adds
`config_ignored` beside the existing skipped list in JSON.

### D. The close-out follows the card front (R6, R7)

`Card` gains a derived `front` choice: `closeout` when `show_closeout_jump`
holds, `batch` otherwise. `_card` renders the front pill and Jump from that
session. `_body` renders the other session's section with a `_jump` button next
to its `_code` line, so each session in the body has the same pair. No data
model or status derivation changes. The `needs_you`/idle logic in `kanban.py`
already considers both statuses.

### E. Pinning the cancelled lifecycle (R8)

No code change is expected. Tests cover `derive_batch_stage`, `owed_claims`,
`owed_releases` and the board's card build over
`dispatch → cancel → claims_released`. They cover a wave batch and a wave-less
batch, each with two members, plus a scenario that renders a board from such a
judgements fixture and refuses "Running". A test that goes red means #1111
regressed, and the fix lands here.

### F. One page registry, navs kept in agreement (R9–R12)

`components.PAGES` becomes the registry. Each `Page` gains `present(state_dir,
judgements) -> bool`, and the tuple is reordered and renamed per R9/R12.
`page_header(current, present_keys)` renders only the present pages. A new
`pages_present(state_dir, judgements)` computes the keys from the state dir.
Every renderer (`render.py`, `history.py`, `origins.py`, `architecture.py`,
`kanban_render.py`) calls it with the keys its command computed. `board.html`
gains the nav and goal sentence ("What is running, and what needs me?") and
keeps its masthead.

After writing its own page, each render command calls one
`refresh_navs(state_dir, judgements)`. It replaces the
`<nav class="pages" …>…</nav>` block of every other present page's file in
place, using the same `page_header` markup with that page as current. The nav
markup is fr's own, so a precise pattern over one line is safe. A page whose nav
block is not found is left untouched and named in a warning, never rewritten
blind. The goal sentence is not part of the rewrite.

## Acceptance rows

One row per requirement group, presented at spec-review: `triage-in-progress-release`
(R1), `triage-closed-in-progress-set` (R2, R3), `triage-config-skew-visible`
(R4, R5), `triage-closeout-card-front` (R6, R7), `triage-cancelled-batch-terminal`
(R8), `triage-nav-present-pages` (R9–R12).

## Verification

strategy: candidate
- triage-in-progress-release: none — label writes need a forge; unit tests drive `claim_writes.release` against a fake client and assert the label removal and the held case.
- triage-closed-in-progress-set: candidate
- triage-config-skew-visible: candidate
- triage-closeout-card-front: none — a live close-out status comes from a runner; unit tests render cards from fixed statuses.
- triage-cancelled-batch-terminal: candidate
- triage-nav-present-pages: candidate

## Test Plan

None post-merge. Every row is proven before merge by CI or the candidate walk.

## Non-goals

- Changing who adds `fr:in-progress` or when (dispatch stays the only adder).
- The bridge's own `fr:in-progress` lifecycle on plan tracking issues (`item_state.py`).
- Carrying a skipped repo's previous facts forward. Lenient reading removes the
  skew cause, and other skip causes are now loud instead.
- Running the one-off cleanup of the 197 labels in this PR. The operator runs
  `fr triage clean-labels --yes` after release.
