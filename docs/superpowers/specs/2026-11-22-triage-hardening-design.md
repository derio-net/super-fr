# Triage intake hardening: withhold ineligible titles, pin ready-fr to content, owed trackers out of dedupe

Batch `triage-hardening` (derio-net/super-fr#1539, #1542, #1545, #1075, #1561, #1572, #1556,
#1557), one PR.

## Background

The triage engine (`packages/fr/src/fr/triage/`) reads a backlog from the forge into
`facts.json`, which the triage agent reads, `fr triage check` reports and the pages render.
The 2026-11-17 triage-intake work (spec `2026-11-17-triage-intake`) made an issue *eligible* for
batching only when its author is trusted, its author association is OWNER, MEMBER or
COLLABORATOR, it carries the operator's `ready-fr` label, or it is the debt bot's marked digest
(`intake.py:1-19`, `intake_reason` at `intake.py:43-65`). It left eight gaps, which this batch
closes.

1. **Titles of ineligible issues still reach facts (#1539).** `_withhold_untrusted_bodies`
   (`collect.py:553-566`) clears only `body`; `title` stays in facts, in `check`'s
   `untrusted` set (`check.py:243`, text at `commands/triage_cmd.py:891-895`) and on the pages.
   A title is outside-author text, as a body is.
2. **`ready-fr` is not pinned to content (#1542).** `intake_reason` admits any issue carrying
   the label (`intake.py:56-57`). The author can edit the title or body after an operator
   applied it, and the edited text is admitted.
3. **Owed trackers in dedupe (#1545).** `dedupe.candidates` (`dedupe.py:195-206`) takes every
   open issue minus those judged `duplicate_of`. `fr:owed` trackers share a template title
   (`Owed: Test Plan step <n> owed`) and pair on title alone; the only way to clear the group
   is to rank issues that are never ranked. `check` already has the one predicate for the
   issues set apart from ranking, `is_set_apart` (`check.py:456-464`): awaiting live, debt
   digest, owed, untrusted.
4. **Claims across driving accounts (#1075).** `trusted_author` (`claims.py:181-186`) trusts
   a claim marker by login (`claim_trusted`, `model.py:584-591`: the viewer plus the repo's
   `pr_authors`) or by OWNER/MEMBER/COLLABORATOR association. A driving account with neither
   has its claims ignored by other hosts. Collect only prints `ignored N untrusted` to stderr
   (`collect.py:1124-1127`), and the fr-triage skill does not tell operators to list every
   driving account in `pr_authors`.
5. **Never-dispatched batches whose members are all closed (#1561).** `derive_batch_stage`
   (`batch.py:326-348`) returns `proposed` for any batch with no lifecycle event. Such a batch
   stays Proposed for ever, a batch `after` it waits on it for ever (only `merged` meets a
   dependency), and a bare `fr triage batch drive` would dispatch it. Six were cancelled by
   hand on 2026-11-19.
6. **Judged PRs past the PR list's limit (#1572).** Collect lists the 200 newest PRs
   (`PR_LIMIT`, `collect.py:59`). A judged PR older than that is viewed with `view_issue`
   (`collect.py:864-874`), recorded as `Unviewed` with `PR_PAST_LIMIT` (`collect.py:569-572`)
   and stored nowhere, so every pass views it again and `check` reports it unreachable for ever.
   A judged closed *issue* is carried from the previous facts (`collect.py:839`, :857-864).
7. **Privacy guard and snapshots (#1556).** The state ref carries `snapshots/`
   (`state_ref.py`, `REF_FILES`); each snapshot's `issues` map is keyed by issue key
   (`snapshot.py:60-68`). `privacy.state_keys` (`privacy.py:206-220`) reads judgements and
   origins only, so a public state repo can publish a private repo's unjudged issue keys.
8. **Issues page filter script (#1557).** `render.py`'s `SCRIPT` calls `addEventListener` on
   `#q` and `#sort` (`render.py:314-315`) with no null check. Those elements exist only in the
   `backlog-by-tier` section; a manifest without it makes the script throw before
   `PAGE_SCRIPT` runs, and hash links into folds and tabs stop opening them.

The operator's decisions (spec journal, `brainstorm` record): pin `ready-fr` with an admit
marker comment; withhold ineligible titles; derive an `obsolete` stage that meets dependencies
and is listed by `check`; record ignored claim markers as warnings and document `pr_authors`;
verify by CI tests, gate `developer`.

## Requirements

R1. When intake finds an issue ineligible, collect stores it in facts with an empty title, as it already stores an empty body. `fr triage check` (text and `--json`), the pages and dedupe show such an issue only by its key, URL, author and reason. When the issue becomes eligible, the next collect stores its title again.
R2. `fr triage admit <owner/repo#n>` previews, and with `--yes` applies, an admission: it reads the issue's title and body live from the forge, adds the `ready-fr` label, and posts one comment holding an admit marker `<!-- fr-admit:{"v":1,"digest":"sha256:<hex>"} -->` over that title and body, followed by a line saying who may change it. It writes the forge only with `--yes` and only through the `GhClient` adapter; on a forge that cannot, it refuses as batch writes do. For an issue already eligible by author, association or digest it changes nothing and says why.
R3. The admission digest is sha256 over the title, a blank line and the body, with `\r\n` read as `\n`. One function computes it, and both `admit` and intake call it.
R4. A `ready-fr` label admits an issue only together with an admit marker from a trusted author (the claim-marker rule: a `claim_trusted` login or an OWNER/MEMBER/COLLABORATOR association) whose digest equals the issue's current digest; the latest such marker by creation time counts. Without one, the issue is ineligible with a reason that says whether no trusted marker exists or the content changed after admission, and names `fr triage admit <key>`. An unread comment list never admits.
R5. Collect reads the comments of an issue for admit markers only when it carries `ready-fr` and no other clause admits it, and records the latest trusted marker's digest on the issue in facts (facts schema 16). It computes the issue's own digest from the title and body before withholding either.
R6. The dedupe universe leaves out every issue `is_set_apart` names (awaiting live, debt digest, owed, untrusted). There is one definition of that set.
R7. Collect records each claim marker it ignored as untrusted in facts, naming the repo, the issue and the comment's author; `fr triage check` prints it with the fix: list that account in the repo's `.fr/triage.yaml` `pr_authors`. The fr-triage skill tells the operator to list every account that drives a scope in `pr_authors`.
R8. A batch with no lifecycle event whose members are all in facts and all closed or awaiting live derives the stage `obsolete`. An obsolete batch is closed out: it is never dispatched, holds no wave open, is not shown under Proposed or Waiting, and meets an `after` dependency as `merged` does.
R9. `fr triage check` lists the obsolete batches, each with its `fr triage batch cancel` command; the Batches page shows them apart from the open stages.
R10. A proposed batch with some members closed (and others open) stays proposed, and `fr triage check` and its card on the Batches page name the closed members.
R11. A judged PR that is not in the PR list is viewed once as a pull request and recorded in facts' `judged_prs` with its state. A later collect carries a closed or merged one from the previous facts with no forge call. `PR_PAST_LIMIT` is no longer recorded for a PR the forge can read; a failed view is still recorded as unreachable with its reason.
R12. `privacy.state_keys` also returns every issue key held in the carried `snapshots/` files, so the guard refuses a push that would publish them.
R13. The Issues page's filter script returns at once when `#q` or `#sort` is absent, and the rest of the page script still runs.

## Design

### A. Withheld titles (R1)

`_withhold_untrusted_bodies` (renamed `_withhold_untrusted_text`) clears `title` together with
`body` when `intake_reason` gives a reason. Intake must judge the issue before the withholding,
as it already does for the body, so the digest and marker checks (B) see the real title. Every
reader treats an empty title as "withheld": `check`'s text for the `untrusted` set prints
`<key> <url> (<author>: <reason>)`, the pages print the key and a quiet "title withheld" in the
title's place. Dedupe never sees an untrusted issue (C). Carried issues (viewed closed ones, a
`keep` repo's open ones) pass through the same function, so nothing older holds a title.

### B. Admission pinned to content (R2-R5)

New module `fr/triage/admit.py`, pure except for the command:

- `content_digest(title, body) -> str` returns `sha256:<hex>` (R3).
- `ADMIT_MARKER` and `admit_marker(digest)` / `parse_admit(comment_body) -> str | None`, in the
  style of the claim and batch markers. A malformed marker is ignored.
- `latest_admit(comments, trusted) -> str | None`: the digest of the latest marker whose comment
  passes `claims.trusted_author`.

`Issue` gains `admit_digest: str | None = None` (the latest trusted marker's digest; `None`
when no comment was read or none was found) and `admit_read: bool = False` (whether the comment
list was read). `FACTS_SCHEMA` moves to 16 and keeps reading 3-16; an older facts file loads
with both defaults, so a `ready-fr` issue in it is ineligible until the next collect, which is
the fail-closed direction.

Collect, for each issue that carries `ready-fr` and that no other clause admits, reads its
comments (the existing `list_issue_comments`, reused when the claim read already fetched them)
and sets both fields. A failed read leaves `admit_read: False`.

`intake_reason` keeps its clause order. The `ready-fr` clause now also requires a digest:
`issue_reason` passes `admit_digest` and `content_digest(title, body)`, computed from the stored
fields before withholding. Reasons:

- `labelled ready-fr, comments not read`
- `labelled ready-fr without a trusted admit marker: run fr triage admit <key>`
- `edited after admission: run fr triage admit <key> again`

`rejected_members` and both snapshot builders already go through `issue_reason`, so an edited
member blocks its batch's dispatch with the same line (intake R6).

`fr triage admit KEY [--yes]` (`commands/triage_cmd.py`) resolves the repo's client, reads the
issue live (`view_issue`), computes the digest, refuses a key that is a PR, and prints the
label and comment it would write. With `--yes` it ensures and adds `ready-fr` and posts the
comment through `GhClient` (`ghclient.py:184`, :216). It is a forge write in a command group
that is in `READ_ONLY_COMMANDS`; like `batch dispatch`, it touches no registered artifact.
Existing admissions made with the label alone stop admitting; the release note and the skill
say to re-admit them with `fr triage admit`.

### C. Dedupe universe (R6)

`dedupe.candidates` filters its universe with `is_set_apart(issue, facts)`. To keep one
definition without a `dedupe -> check` import cycle, `is_set_apart` and the predicates it calls
(`is_awaiting_live`, `is_debt_digest`, `is_owed`) move to a small module
`fr/triage/sets.py`, which `check` re-exports under the same names.

### D. Claim markers ignored as untrusted (R7)

`collect.py:1124` keeps its stderr line and also records an `IgnoredClaims(repo, number,
authors)` per issue in a new facts field `ignored_claims` (facts schema 16, with B; facts'
`warnings` holds only `Truncation` records, `model.py:663`), naming the ignored authors by login
only (`ClaimRead` gains `untrusted_authors: list[str]`). A `keep` repo's entries are carried
from the previous facts, as its claims are. `check` prints claim warnings in their own
block, each with `add <login> to pr_authors in <repo>'s .fr/triage.yaml`. The fr-triage skill's
phase 3 (claims) states the rule, and the OpenCode and Hermes mirrors are regenerated.

### E. Obsolete batches (R8-R10)

`BatchStage` gains `"obsolete"`, placed in `BATCH_STAGES` after `proposed`. In
`derive_batch_stage`, the no-event branch returns `obsolete` when every member key is in facts
and is closed or awaiting live (the `all_closed` test already at `batch.py:342-346`, moved into
one helper both branches call), else `proposed`. `obsolete` joins `CLOSED_OUT`. Every
dependency check treats `obsolete` as satisfied, as it does `merged`: the drive pass
(`batch_drive.py:2039`, :2063), the board's waiting view (`views.py:612`) and the dependency
state helper in `batch.py`. One predicate, `meets_dependency(stage)`, replaces the three
`== "merged"` tests. The driver selects only open batches,
so it never dispatches one. Snapshots store the stage as a string (`snapshot.py:63`), so an
older reader loads the new value.

`CheckResult` gains `obsolete_batches: list[str]` and `stale_members: dict[str, list[str]]`
(batch id -> closed member keys, for proposed batches only). The text output prints each
obsolete batch with `fr triage batch cancel <id> --yes`, and each partly-closed batch with its
closed members. The Batches page groups obsolete batches under their own heading with the closed
stages, and a proposed card lists its closed members.

### F. Judged PRs past the list limit (R11)

The collect `Forge` protocol gains `view_pr(repo, number) -> dict` (`ClientForge` wraps
`GhClient.pr_view`, `ghclient.py:315`/:594, both the CLI and REST clients). In the judged-key
loop:

1. Before any view, a judged key that the previous facts hold in `judged_prs` as `CLOSED` or
   `MERGED` is carried with no forge call (a collected repo too, unlike today's `keep`-only
   carry at `collect.py:845-849`).
2. When `view_issue` returns a `/pull/` URL, collect calls `view_pr` and records a
   `PullRequest` in `judged_prs`; a failed `view_pr` records `Unviewed` with its error.
3. `PR_PAST_LIMIT` is removed. An open past-limit PR is viewed again on each pass, since its
   state can change.

### G. Snapshot keys in the privacy guard (R12)

`state_keys` loads every `snapshots/*.json` in the state directory with the snapshot reader and
adds the keys of each one's `issues` map. An unreadable snapshot is a `TriageError`, like the
other files: what cannot be read cannot be shown safe.

### H. Filter script guard (R13)

The filter IIFE in `SCRIPT` begins `if (!q || !sort) return;` after it looks the two elements
up. A test renders the Issues page with a manifest that leaves `backlog-by-tier` out and asserts
the guard precedes the first `addEventListener` and that `PAGE_SCRIPT` is in the same script.

## Verification

strategy: none
gate: developer

- intake-title-withheld: none — CI unit tests on collect and check over fake forge facts with an outside author
- intake-admit-pinned: none — CI unit tests on the digest, the marker parser, `intake_reason` (edited, untrusted marker, unread comments) and `fr triage admit` against a fake GhClient
- dedupe-set-apart: none — CI unit test with owed trackers carrying the template title
- claim-untrusted-warning: none — CI unit tests on collect's warnings and check's output
- batch-obsolete-stage: none — CI unit tests on `derive_batch_stage`, dependencies, the drive pass selection, check and the Batches page
- collect-past-limit-pr: none — CI unit tests counting forge calls over two collects with a fake forge
- privacy-snapshot-keys: none — CI unit test of `state_keys` and `guard_state` with a snapshot holding a private key
- issues-page-filter-guard: none — CI unit test rendering the Issues page without `backlog-by-tier`

Every requirement is engine or render behaviour that fakes prove in CI; no released build is
needed to show any of it.

## Out of scope

- Deduplicating owed trackers by identity (spec, row, step): they leave the universe instead.
- A per-repo claim trust check that reads the viewer's association live.
- Driver-side automatic cancellation of obsolete batches: the operator cancels them.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-22-triage-hardening | `derio-net/super-fr` | `2026-11-22-triage-hardening` | — |
