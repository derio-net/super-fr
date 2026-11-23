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

R1. When intake finds an issue ineligible, collect stores it in facts with an empty title, as it already stores an empty body. `fr triage check` (text and `--json`, its `untrusted` and `untrusted_digests` sets alike) and the pages show such an issue only by its key, URL, author and reason. When the issue becomes eligible, the next collect stores its title again. A facts file written before this change is withheld the same way when it loads.
R2. `fr triage admit <owner/repo#n>` previews, and with `--yes` applies, an admission: it reads the issue's title and body live from the forge, adds the `ready-fr` label, and posts one comment holding an admit marker `<!-- fr-admit:{"v":1,"digest":"sha256:<hex>"} -->` over that title and body, followed by a line saying who may change it. It writes the forge only with `--yes` and only through the `GhClient` adapter. It refuses a pull request, and it refuses, before any write, on a forge whose adapter cannot list issue comments (GitLab, Gitea), since no collect there could read the marker. For an issue whose author is already a trusted login it changes nothing and says why. The preview shows the title and body it would pin (inside the quoted untrusted block) and their digest; `--yes` needs `--digest <that digest>`, and the command re-reads the issue and refuses, writing nothing, when the live digest differs, so the operator admits exactly the text they read.
R3. The admission digest is sha256 over the full title, a blank line and the full body (never the body as facts truncate it), with `\r\n` read as `\n`. One function computes it, and both `admit` and collect call it.
R4. A `ready-fr` label admits an issue only together with an admit marker from a trusted author (the claim-marker rule: a `claim_trusted` login or an OWNER/MEMBER/COLLABORATOR association) whose digest equals the issue's current digest; the latest such marker by creation time counts. Without one, the issue is ineligible with a reason that says whether its comments were not read, no trusted marker exists, or the content changed after admission, and names `fr triage admit <key>`; on a forge that cannot list comments the reason says so. An unread comment list never admits. Every operator-facing line that says the label admits an issue says `fr triage admit` instead.
R5. Collect reads an issue's comments for admit markers only when it carries `ready-fr` and no other clause admits it; the label no longer skips the author-association read. Collect records on the issue in facts (schema 16) the digest of the latest trusted marker and the issue's own content digest, both computed from the full forge record before any truncation or withholding. A failed admit read leaves only that issue ineligible.
R6. The dedupe universe leaves out every issue `is_set_apart` names (awaiting live, debt digest, owed, untrusted). There is one definition of that set.
R7. Collect records each claim marker it ignored as untrusted in facts, naming the repo, the issue and the comment's author; `fr triage check` prints it with the fix: list that account in the repo's `.fr/triage.yaml` `pr_authors`. The fr-triage skill tells the operator to list every account that drives a scope in `pr_authors`.
R8. A batch with no lifecycle event whose members are all in facts and all closed or awaiting live derives the stage `obsolete`, which takes precedence over the awaiting-live hold. An obsolete batch is closed out: it is never dispatched, it finishes its wave as a cancelled batch does, it is not shown under Proposed or Waiting, and it meets an `after` dependency as `merged` does.
R9. `fr triage check` lists the obsolete batches, each with its `fr triage batch cancel <id> --yes` command, and that command accepts an obsolete batch (appending a cancel event, touching no member); the Batches page shows obsolete batches apart from the open stages.
R10. A proposed batch with some members closed (and others open) stays proposed, and `fr triage check` and its card on the Batches page name the closed members.
R11. A judged PR that is not in the PR list is viewed once as a pull request and recorded in facts' `judged_prs` with its state. A later collect carries a closed or merged one from the previous facts with no forge call. `PR_PAST_LIMIT` is no longer recorded for a PR the forge can read; a failed view is still recorded as unreachable with its reason.
R12. `privacy.state_keys` also returns every issue and PR key held in the carried `snapshots/` files, and the guard also checks the repos their debt figures name, so it refuses a push that would publish any of them. A snapshot file it cannot parse is a refusal, never skipped.
R13. The Issues page's filter script returns at once when `#q` or `#sort` is absent, and the rest of the page script still runs.

## Design

### A. Withheld titles (R1)

`_withhold_untrusted_bodies` (`collect.py:553-566`, renamed `_withhold_untrusted_text`) clears
`title` together with `body` when `intake_reason` gives a reason. Intake judges the issue before
the withholding, as it already does for the body. Readers treat an empty title as withheld:
`check`'s text for the `untrusted` set (`commands/triage_cmd.py:891-895`) and the
`untrusted_digests` set (:879-883) prints `<key> <url> (<author>: <reason>)`, the JSON rows keep
an empty `title`, and the pages print the key and a quiet "title withheld". Carried issues pass
through the same function. `load_facts` (`model.py:1362-1369`) already re-withholds bodies for a
file below schema 15; it re-runs the new function for any file below 16, so a schema-15 file's
titles, and the bodies of issues the label alone used to admit, never reach a reader.

### B. Admission pinned to content (R2-R5)

New module `fr/triage/admit.py`, pure:

- `content_digest(title, body) -> str` returns `sha256:<hex>` (R3).
- `admit_marker(digest)` / `parse_admit(comment_body) -> str | None`, in the style of the
  claim and batch markers. A malformed marker is ignored.
- `latest_admit(comments, trusted) -> str | None`: the digest of the latest marker, by
  `created_at`, whose comment passes `claims.trusted_author`.

`Issue` gains `content_digest: str | None = None` (computed by collect in `_issue` from the raw,
untruncated record, `collect.py:452-472`, before `_body` cuts it to `BODY_LIMIT`),
`admit_digest: str | None = None` and `admit_read: bool = False`. `FACTS_SCHEMA` moves to 16 and
keeps reading 3-16; an older file loads with the defaults, so a `ready-fr` issue in it is
ineligible until the next collect.

Collect: `_admitted` (`collect.py:484-489`) drops its `ready-fr` clause and keeps the login
clause, so a labelled issue's association is read as any other's (`:516`, `:540`). After the
association is known, an issue that carries `ready-fr` and that no login, association or digest
clause admits gets its comments read. `_comment_facts` (`collect.py:1103-1132`) is split: one
helper fetches the comments, once per issue, when the issue needs the claim read, the admit read
or both, and returns them; the claim and admit parsers run over that list. When the claim read
needs the list, a failure keeps today's rule (it raises, and org scope skips the repo); when only
the admit read needs it, a `ForgeError` (including `UnsupportedForgeOperation` on glab/tea,
`ghclient.py:579-580`) leaves `admit_read: False` on that issue and nothing else changes.

`intake_reason` keeps its clause order. The `ready-fr` clause also requires
`admit_digest is not None and admit_digest == content_digest`. `issue_reason` passes the stored
fields. Reasons, each ending with the command:

- `labelled ready-fr, comments not read: run fr triage collect again`
- `labelled ready-fr, but this forge cannot list comments, so an admit marker cannot be read`
- `labelled ready-fr without a trusted admit marker: run fr triage admit <key>`
- `edited after admission: run fr triage admit <key> again`

The adapter's kind decides the second reason: collect records `admit_read: False` with a reason
of its own, so `Issue` also gains `admit_unread: str | None` (the read's failure text, `None` on
success).

`rejected_members` and both snapshot builders go through `issue_reason`, so an edited member
blocks its batch's dispatch with the same line (intake R6). The texts that say the label admits
change to `fr triage admit`: `rejection_line` (`intake.py:102-108`), check's untrusted header
(`commands/triage_cmd.py:891-893`), the fr-triage skill, `docs/explainers/fr-triage.md:115` and
`docs/explainers/fr-wave-driver.md:51`. The new verb appears in the generated command tree
(`docs/reference/cli.md`) and README table through `scripts/sync-readme.py`.

`fr triage admit KEY [--yes --digest sha256:<hex>]` (`commands/triage_cmd.py`) resolves the repo's client, refuses a
glab or tea adapter before any read, reads the issue live (`view_issue`, refusing a `/pull/`
URL), computes the digest over its full title and body, and prints the label and comment it
would write, with the title and body it pins quoted as untrusted text and the digest. With `--yes`, a
missing `--digest` or one that differs from the live digest (read again just before the write)
is a refusal (exit 2) that prints the current digest and writes nothing. When the author is a `claim_trusted` login it prints that the issue is already
eligible and writes nothing. With `--yes` it ensures and adds `ready-fr` and posts the comment
(`GhClient.edit_issue_labels`, `ghclient.py:184`; `comment_issue`, :216). The `triage` group
stays in `READ_ONLY_COMMANDS`: like `batch dispatch`, `admit` writes the forge only. Existing
admissions made with the label alone stop admitting; the change fragment and the skill say to
re-admit them with `fr triage admit`.

### C. Dedupe universe (R6)

`dedupe.candidates` filters its universe with `is_set_apart(issue, facts)`. `check` imports
`dedupe` (`check.py:71`), so `is_set_apart` and the predicates it calls (`is_awaiting_live`,
`is_debt_digest`, `is_owed`, `check.py:441-464`) move to a new module `fr/triage/sets.py`, which
both import; `check` re-exports the names.

### D. Claim markers ignored as untrusted (R7)

`read_claims` (`claims.py:190-226`) also collects the logins of the untrusted markers it skips,
in `ClaimRead.untrusted_authors: list[str]`. Collect keeps its stderr line and records an
`IgnoredClaims(repo, number, authors)` per issue in a new facts field `ignored_claims` (schema
16; facts' `warnings` holds only `Truncation` records, `model.py:663`). A `keep` repo's entries
are carried from the previous facts, as its claims are. `check` prints them in their own block,
each with `add <login> to pr_authors in <repo>'s .fr/triage.yaml`. The fr-triage skill's claims
phase states the rule, and the OpenCode and Hermes mirrors are regenerated.

### E. Obsolete batches (R8-R10)

`BatchStage` gains `"obsolete"`, after `proposed` in `BATCH_STAGES`. In `derive_batch_stage`
(`batch.py:326-348`) the `all_closed` test (:342-347) becomes a helper both branches call; the
no-event branch returns `obsolete` when it holds, else `proposed`. `obsolete` joins
`CLOSED_OUT`, so `is_open` releases its members and the driver never selects it.

Readers of the stage:

- **Dependencies.** One predicate, `meets_dependency(stage)` (`merged` or `obsolete`), replaces
  the `== "merged"` tests at `batch.py:410` (`dependency_state`; its docstring at :405 too),
  `batch_drive.py:2063` and `views.py:612` (and the "waits for X to merge" wording at :614).
  `batch_drive.py:2039`, which marks a merging batch `merged`, stays.
- **Waves.** `finished_waves` (`batch_drive.py:1238-1250`) counts `obsolete` as terminal with
  `cancelled` and `abandoned`; `preselected_wave` (`views.py:699-702`) adds it to its non-live
  set; `cancelled_waves` (`views.py:669-679`) counts an all-obsolete wave as delivering nothing,
  as an all-cancelled one.
- **Awaiting live.** A never-dispatched batch whose open members all await their walk and whose
  others are closed is `obsolete`, not held (`batch_awaits_live`, `check.py:468-472`;
  `AWAITING_LIVE_HOLD`, `batch_drive.py:2045-2047`): it has no work to dispatch. The members stay
  in the awaiting-live set. The hold still applies to a never-dispatched batch with a member
  missing from the facts; a batch with a lifecycle event derives another stage, which the drive
  never dispatches, so the hold has nothing to stop there.
- **Cancel.** `batch cancel` (`commands/triage_batch_cmd.py:943-945`) refuses `CLOSED_OUT` stages
  except `obsolete`; a never-dispatched batch withdraws nothing (:957-959), so cancelling it only
  appends the cancel event, after which it derives `cancelled`.
- **Snapshots.** They store the stage as a string (`snapshot.py:63`), so an older reader loads it.

`CheckResult` gains `obsolete_batches: list[str]` and `stale_members: dict[str, list[str]]`
(batch id -> closed member keys, for proposed batches only). The text output prints each
obsolete batch with `fr triage batch cancel <id> --yes`, and each partly-closed batch with its
closed members. The Batches page groups obsolete batches under a heading of their own beside the
closed-out stages, and a proposed card lists its closed members.

### F. Judged PRs past the list limit (R11)

The collect `Forge` protocol gains `view_pr(repo, number) -> dict`; `ClientForge` wraps
`GhClient.pr_view` as it already does for `pr_labels` (`collect.py:213-217`; implementations
`real_ghclient.py:416`, `real_ghrestclient.py:772`). In the judged-key loop (`collect.py:842-876`):

1. Before any view, a judged key that the previous facts hold in `judged_prs` as `CLOSED` or
   `MERGED` is carried with no forge call, in a collected repo as in a `keep` one (today only
   `keep`, :845-849).
2. When `view_issue` returns a `/pull/` URL, collect calls `view_pr` and builds a `PullRequest`
   from both records: `number`, `url` and `title` from the issue record, `state`, `is_draft` and
   `head_ref` from `pr_view`. `merged_at`, `created_at` and `author` stay `None` (never read),
   which no attribution trusts. A failed `view_pr` records `Unviewed` with its error.
3. `PR_PAST_LIMIT` is removed. An open past-limit PR is viewed again on each pass, since its
   state can change.

### G. Snapshot keys in the privacy guard (R12)

`state_keys` (`privacy.py:206-220`) reads every `snapshots/*.json` in the state directory with a
new strict reader in `snapshot.py`, `load_snapshot_strict(path)`, which raises `TriageError` on a
file it cannot parse (the existing `_readable`/`stored_snapshots`, `snapshot.py:205-229`, skip such
a file, which would still ride the ref). It adds the keys of each snapshot's `issues` and `prs`
maps. A new `state_repos(state_dir)` returns the repo names of each snapshot's `debt` map, and
`guard_state` adds them to the repos whose visibility it checks.

### H. Filter script guard (R13)

The filter IIFE in `SCRIPT` (`render.py:249-320`, lookup at :252) begins `if (!q || !sort) return;` after it
looks the two elements up. A test renders the Issues page with a manifest that leaves
`backlog-by-tier` out and asserts the guard precedes the first `addEventListener` and that
`PAGE_SCRIPT` is in the same script.

## Verification

strategy: none
gate: developer

- intake-title-withheld: none — CI unit tests on collect and check over fake forge facts with an outside author
- intake-admit-pinned: none — CI unit tests on the digest (a body over `BODY_LIMIT`), the marker parser, `intake_reason` (edited, untrusted marker, unread comments, glab), a MEMBER-authored labelled issue with no marker, the v15 load and `fr triage admit` against a fake GhClient
- dedupe-set-apart: none — CI unit test with owed trackers carrying the template title
- claim-untrusted-warning: none — CI unit tests on collect's warnings and check's output
- batch-obsolete-stage: none — CI unit tests on `derive_batch_stage` (incl. an awaiting-live member), dependencies, `finished_waves`/`preselected_wave`, the drive pass selection, `batch cancel` of an obsolete batch, check and the Batches page
- collect-past-limit-pr: none — CI unit tests counting forge calls over two collects with a fake forge
- privacy-snapshot-keys: none — CI unit tests of `state_keys` and `guard_state` with snapshots holding a private issue key, PR key and debt repo, and an unparseable snapshot
- issues-page-filter-guard: none — CI unit test rendering the Issues page without `backlog-by-tier`

Every requirement is engine or render behaviour that fakes prove in CI; no released build is
needed to show any of it.

## Out of scope

- Deduplicating owed trackers by identity (spec, row, step): they leave the universe instead.
- A per-repo claim trust check that reads the viewer's association live.
- Driver-side automatic cancellation of obsolete batches: the operator cancels them.
- Admission on GitLab and Gitea: their adapters cannot list issue comments, so `admit` refuses there and a `ready-fr` issue stays ineligible with that reason until an adapter can.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-22-triage-hardening | `derio-net/super-fr` | `2026-11-22-triage-hardening` | — |
