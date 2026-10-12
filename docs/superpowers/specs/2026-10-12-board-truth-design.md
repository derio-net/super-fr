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
  (`triage/claim_writes.py:193-223`), removes only `fr:claimed`. A batch that merges,
  closes out and archives therefore leaves `fr:in-progress` on every closed member:
  197 such issues on derio-net/super-fr on 2026-10-07. Collect lists only open
  issues (`triage/collect.py:541`), so nothing in fr can see the drift.
- **#1065.** The card front (`triage/kanban_render.py:290-317`) always shows the
  batch session's status pill and builds Jump with `closeout=False` (`:307`).
  During a close-out the front therefore reads, and jumps to, the wrong session.
  The close-out's pill and Jump live only in the body (`:279-286`). The batch
  session's body entry has only a code line, no Jump button (`:274-277`).
- **#1109.** `collect` reads `.fr/triage.yaml` strictly unless `lenient` is
  passed (`collect_facts_counted`, `triage/collect.py:486-499`, and
  `collect_into`, `commands/triage_cmd.py:428`). Only the wave driver passes it
  (`triage_batch_cmd.py:2390`, gh#998), and `batch dispatch`'s `_fresh_config`
  (`triage_batch_cmd.py:963-1002`) is strict by default. A config written for a
  newer fr, such as `merge_method` read by an older parser, fails the read. In org
  scope that repo is `skipped` (`collect.py:552-557`), its issues vanish from the
  facts, and its active batch reads as unreachable. The skip surfaces only as one
  line among the board's notes (`triage/render.py:662`). The keys a lenient read
  drops are kept only in the transient `CollectStats.ignored`
  (`collect.py:425-436`), never in `facts.json`.
- **#1111.** `derive_batch_stage` now folds only dispatch/cancel events
  (`triage/batch.py:254-266`, from #1115). `releasing()` treats `cancelled` as
  releasing (`triage/claims.py:289-292`), so a cancelled batch owes no claim. The
  report appears fixed on main, but no test pins the reported sequence
  `dispatch → cancel → claims_released` end to end.
- **#1122.** `page_header()` (`triage/components.py:265-277`) renders the fixed
  four-entry `PAGES` tuple (`:49-64`) whatever the scope has. On org scopes,
  Origins and Architecture link to pages that were never written. `board.html`
  (`commands/triage_kanban_cmd.py:69`) is not a tab and carries no nav
  (`kanban_render.py`'s own `<h1>Batch board</h1>` header). The `PAGES` entry
  titled "Board" is `triage.html`, which clashes with the real board.

## Requirements

R1. Every claim release that `claim sync` executes (the driver's and the
operator's: releases owed by a releasing batch, meaning cancelled, abandoned or
archived, and releases of own claims no batch owes any more) also removes
`fr:in-progress` from that issue, but only when no other scope's claim stands on
it. The operator verbs `claim release` and `scope retire` leave `fr:in-progress`
alone. The cancel path keeps its current behaviour.

R2. `fr triage collect` reads, per repo, the closed issues still labelled
`fr:in-progress`. Collect reads the comments of those that also carry
`fr:claimed`. `fr triage check` reports them as a set, "closed but in progress",
with each entry in one of three states:
- `stale`: no un-released claim stands on it.
- `release-pending`: this scope's own claim stands, and `claim sync` will release
  and unlabel it.
- `held`: another scope's claim stands.

The board names the set.

R3. A new verb, `fr triage clean-labels`, removes `fr:in-progress` from every
`stale` entry of R2's set. It writes nothing without `--yes` and prints its plan
instead. Before each write it re-reads the issue and skips it, saying why, if the
issue is open again or now carries `fr:claimed`. It writes only through the forge
adapter: GitHub only, and glab/tea refuse with `UnsupportedForgeOperation`.

R4. Every triage read of `.fr/triage.yaml` is lenient: every collect, and `batch
dispatch`'s fresh read. An unknown top-level key is dropped and named, never
refused, so a newer config never skips its repo or refuses a dispatch.

R5. Ignored config keys (persisted in `facts.json`) and skipped repos are a
prominent scope-level banner on `triage.html` and `board.html`, and are named by
`fr triage check` in text and in JSON (`skipped`, `config_ignored`). They are no
longer a line among the notes.

R6. While a batch's close-out session is live (it has a status, and that status is
neither `absent` nor `unknown`), the card front's status pill and Jump button follow the
close-out session (`fr triage batch focus <id> --closeout`). Otherwise the front
follows the batch session as today.

R7. The card body offers a real Jump button for whichever session the front does
not show, beside its focus command.

R8. A batch that was dispatched, then cancelled, then had its claims released
(wave or wave-less, one or several members) derives as `cancelled`, owes no claim
and no release, and never renders as Running. A collect and render right after
keep that state.

R9. One page registry says, for each triage page, its file, tab title and goal
sentence. A page is present when its file exists in the state dir, or when it is
the page being rendered now. No other rule applies, so a present page's file
always exists once the render finishes. Nav order: Backlog (`triage.html`),
Batches (`board.html`), Origins (`origins.html`), Architecture
(`architecture.html`), History (`history.html`).

R10. Every triage page's nav lists only the present pages, marks the current page
`aria-current="page"`, and is followed by that page's goal sentence. This includes
`board.html`. The copy of `board.html` that `--publish` hands to the scope's
publish command carries no nav, because its siblings are not published.

R11. Every render rewrites, atomically, the nav block of every other present page
in the state dir, so all pages agree after any render. A page whose nav is already
current is not rewritten.

R12. `triage.html` is titled "Backlog" and `board.html` "Batches" everywhere: the
nav, the board's own header, and the fr-triage skill. The skill's "Pages and
state" section documents which pages exist per scope kind and names
`clean-labels`. The skill stays within its 120-line cap, and both of its mirrors
are regenerated.

## Design

### A. `fr:in-progress` follows the sync release (R1)

`claim_writes.release` gains a keyword, `unlabel: bool = False`. When it is true,
and no other scope's claim stands after the re-read (the existing
`if not [c for c in claims if c.signer != signer]`), the label edit removes
`fr:in-progress` together with `fr:claimed`, in one `edit_issue_labels` call.

`claim_sync.execute` (`claim_sync.py:191-199`) passes `unlabel=True` on every
release it makes. Every pair `plan_sync` turns into a release is a claim that no
non-releasing batch owes (`owed_releases`, `claims.py:333-365`): a releasing
batch's members, or own claims no batch owes any more, such as members `batch edit
--remove-issue` dropped. In both cases nobody is working on the issue under this
scope, so the label is false.

`claim release` and `scope retire` (`triage_claim_cmd.py:308-318, 376-385`)
release a claim without saying anything about the work, so they keep
`unlabel=False`. A closed issue they leave labelled shows up in R2's set and is
cleaned by R3. An open one shows up in `check`'s existing stale-dispatch set.

The re-read guard in `_remove_label` (`claim_writes.py:67-73`, p1-r5) currently
restores only `fr:claimed` when a foreign claim appeared in the meantime. It
restores every label it removed, so the combined edit never strips another
scope's fresh `fr:in-progress`. A legacy batch with no claim marker returns
`Done("none")` before any write, so its labels stay. R2 and R3 cover those.

### B. The closed-but-in-progress set and its cleanup verb (R2, R3)

The label filter crosses the whole chain:
- the `Forge.list_issues` protocol (`collect.py:68-75`) and `ClientForge`;
- the `GhClient.list_issues` protocol (`ghclient.py:315-319`) and its stubs;
- `fr.gh.list_issues` (`gh.py:500-511`, `gh issue list --label`);
- the REST client (`real_ghrestclient.py:606-614`, `&labels=`);
- the test fakes.

Each gains an optional `labels` argument. The call requests `closedAt`, using
`ORIGINS_ISSUE_LIST_FIELDS` (`gh.py:488`), because `ISSUE_LIST_FIELDS` lacks it.

Collect makes one extra call per collected repo, `state=closed,
labels=[fr:in-progress]`, bounded by `issue_limit`. The call is best-effort. It
sits outside the per-repo `try` that skips a repo, so a failure is a warning and
an empty set for that repo, never a skip. A list that hits the limit adds a
`Truncation` warning, as the open lists do. For each hit that also carries
`fr:claimed`, collect reads its comments, the same `read_claims` call it makes for
open issues, to tell an own claim from a foreign one.

Two new facts fields are added:
- `stale_in_progress`: key, title, url, `closed_at`, and `state` (`stale` |
  `release-pending` | `held`).
- `config_ignored`: a dict from repo to its dropped keys.

The facts schema moves 8 → 9, and `FACTS_READS` widens to 3–9. Both fields
default to empty, so older facts read unchanged. `facts.json` is a local cache
(not carried on the state ref, `state_ref.py:53-65`) and not a registered
artifact kind, so no artifact migration is owed.

`fr triage check` gains three JSON keys: `closed_in_progress` (entries with their
state), `skipped` and `config_ignored`. Matching text sections come first in the
text report. The backlog page shows the set as a collapsed section. The board
shows a note-level count and the `clean-labels` command.

The verb is `fr triage clean-labels [--yes]`, in the triage group (already exempt
from the migration gate). Without `--yes` it prints one line per `stale` target
and "nothing written". With `--yes`, for each target it re-reads the issue
(`view_issue`), skips it with a reason if it is open again or now carries
`fr:claimed`, and otherwise removes the label through
`GhClient.edit_issue_labels`. It prints one outcome line per issue. A per-issue
failure is reported and the rest continue, and the verb exits non-zero if any
failed.

### C. Lenient reads and the skew banner (R4, R5)

`collect_facts_counted` and `collect_into` drop their `lenient` parameter and
always read leniently. The driver's call site (`triage_batch_cmd.py:2390`) loses
the keyword. `_fresh_config` and `batch_dispatch`'s config read
(`batch_dispatch.py:238-253`) default to lenient too. Collect writes the dropped
keys into `Facts.config_ignored`. A config that is invalid for any other reason
(a bad value, a non-mapping) still skips the repo in org scope and fails in repo
scope.

`components.py` gains one `skew_banner(facts)` component. It renders a
`role="alert"` block naming each repo's ignored keys ("written for a newer fr:
upgrade fr to read them") and each skipped repo with its reason. `triage.html`
and `board.html` render it directly under the nav, and `render.py:662`'s
skipped-repo note line goes.

### D. The close-out follows the card front (R6, R7)

`Card` gains a derived `front` choice: `closeout` when `closeout_status` is not
`None`, `absent` or `unknown`, and `batch` otherwise. This is deliberately
narrower than `show_closeout_jump` (`kanban.py:456`), which is also true for
`unknown`. `_card` renders the front pill and Jump from the chosen session.
`_body` renders the other session's section with a `_jump` button next to its
`_code` line, so each session in the body has the same pair. No status derivation
changes. The `needs_you`/idle logic in `kanban.py` already considers both
statuses.

### E. Pinning the cancelled lifecycle (R8)

No code change is expected. Tests cover `derive_batch_stage`, `owed_claims`,
`owed_releases` and the board's card build over
`dispatch → cancel → claims_released`. They cover a wave batch and a wave-less
batch, each with two members, plus a scenario that renders a board from such a
judgements fixture and refuses "Running". A test that goes red means #1111
regressed, and the fix lands here.

### F. One page registry, navs kept in agreement (R9–R11)

`components.PAGES` becomes the registry, reordered and renamed per R9 and R12.
`pages_present(state_dir, current) -> tuple[str, ...]` returns the keys whose
file exists, plus *current*. It needs no judgements, so origins, which may render
without them, uses it the same way. `page_header(current, present)` renders only
those. Every renderer (`render.py`, `history.py`, `origins.py`, `architecture.py`,
`kanban_render.py`) takes the present keys from its command. `board.html` gains
the nav and a goal sentence ("What is running, and what needs me?") and keeps its
masthead.

After writing its own page, each render command calls one
`refresh_navs(state_dir, current)`. For every other present page it reads the
file and finds the single-line `<nav class="pages" …>…</nav>` block, which is
fr's own markup. If the block already equals the new nav it skips the page.
Otherwise it writes the file back with the block replaced, through
`write_text_atomic`, so a concurrent render or a driver/watch pass never sees a
half-written page. A page whose nav block is not found is left untouched and
named in a warning. The goal sentence is not part of the rewrite.

`write_board`'s publish step (`triage_kanban_cmd.py:369-385`) hands the publish
command a temporary copy of `board.html` with the nav block removed. The local
`board.html` keeps its nav.

## Acceptance rows

One row per requirement group, presented at spec-review: `triage-in-progress-release`
(R1), `triage-closed-in-progress-set` (R2, R3), `triage-config-skew-visible`
(R4, R5), `triage-closeout-card-front` (R6, R7), `triage-cancelled-batch-terminal`
(R8), `triage-nav-present-pages` (R9–R12).

## Verification

strategy: candidate
- triage-in-progress-release: none — label writes need a forge; unit tests drive `claim_writes.release` and `claim_sync.execute` against a fake client and assert the label removal, the held case and the restore race.
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
