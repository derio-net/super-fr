# Triage intake trust and driver correctness

Batch `triage-intake`: super-fr#1252, #1213, #1406, #1299, delivered as one PR on
`feat/batch-triage-intake`.

## Background

**#1252: no author-trust gate on batch intake.** On a public repo anyone can open an
issue, and issue text reaches the implementing session's launch brief.
`render_brief` (`packages/fr/src/fr/triage/batch_dispatch.py:131`) writes each member's
collected title (`:154`, `:166`) and the triage agent's `detail` / `note` judgements
(`:167-170`), which the agent derived from the issue body. Nothing marks that text as
untrusted. Trust checks already exist, but for other things:

- claim markers count only from `claim_trusted(config, viewer)`
  (`packages/fr/src/fr/triage/model.py:570`: the viewer `collect` ran as plus the repo's
  `pr_authors`) or from a comment whose association is in `TRUSTED_ASSOCIATIONS`
  (`packages/fr/src/fr/triage/claims.py:44`: OWNER, MEMBER, COLLABORATOR);
- a batch PR's author is checked by `distrust` (`packages/fr/src/fr/triage/batch.py:260`).

Collect already records each issue's `author` (`packages/fr/src/fr/triage/collect.py:465`,
`Issue.author`, `model.py:386`; facts schema 11) and keeps its body up to `BODY_LIMIT`
(`collect.py:443-449`). It records no author association: collect asks for `ISSUE_FIELDS`
(`collect.py:61`), and `gh issue list --json` offers no association field at all. The REST
issues list does return `author_association`, but the REST client's issue record drops it
(`packages/fr/src/fr/real_ghrestclient.py:272-288`).
The comment reads carry it (`real_ghclient.py:374`, `real_ghrestclient.py:299`). Nothing gates
which issues may be ranked (`fr triage check`'s `classify`,
`packages/fr/src/fr/triage/check.py:498`), suggested (`suggest`, `batch.py:780`),
put in a batch (`batch_create_command`,
`packages/fr/src/fr/commands/triage_batch_cmd.py:749`, and `edit`) or dispatched
(`dispatch_batch`, `triage_batch_cmd.py:1763`, shared by `batch dispatch` and the wave
driver). On GitHub only an account with triage permission or higher can add a label to an
issue, so a label is an operator act that an outside author cannot perform. The interim
mitigation is a GitHub interaction limit that expires on 2027-04-28.

**#1213: the merge context outlives its fetch.** `Driver.merge_ctx`
(`triage_batch_cmd.py:4004`) builds a repo's `MergeContext` once per driver lifetime. The
fetch and the triage-config freshness check (`_fresh_config`, `triage_batch_cmd.py:1134`)
run only at that creation. Each pass refreshes `ci_none` and `rules` (`:4033-4034`) but
never fetches again. A later pass whose origin is unreachable acts on the refs from an
earlier fetch instead of holding the repo, which is what R13 of merge-truth does for an
unreadable default branch (`_ctx_or_hold`, `:4050`). The per-pass reset (`:5176-5180`)
already clears a `_fetched` set that `_fetched_reader` (`:4738`) uses to fetch once per pass.
The context also keeps the `version` block and merge `method` it was built with
(`:4011-4031`), so a config change mid-drive merges with the old ones. One caller,
`_closeout_hand_back` (`:6486`), calls `merge_ctx` directly instead of through
`_ctx_or_hold`.

**#1406: cancel never converges on an undefined label.** `batch cancel --yes`
(`triage_batch_cmd.py:895`) calls `edit_issue_labels(..., remove={fr:in-progress})` on
every withdrawn member (`:972-974`). On the gh CLI client this is `gh.swap_issue_labels`
(`gh.py:407-425`), a single `gh issue edit --remove-label`. gh fails the whole call when
the repo does not define the label (`'fr:in-progress' not found`), so the member is
reported as not withdrawn and no cancel event is written, on every rerun. The REST client
already treats GitHub's absent-label 404 as done (`real_ghrestclient.py:1120-1128`).
The dry run also passes while `--yes` then refuses over the clone:
`_tracking_gate` (`triage_batch_cmd.py:1059`) opens the batch's repo strictly only under
`--yes` (`_open_checkout`), and the dry run returns silently when no clone opens (`:1069-1072`).

**#1299: non-forge exceptions escape the gate-tracker close.** `close_gate_trackers`
(`packages/fr/src/fr/gatebackfill/close.py:359`) catches only
`_FAILURES = (*FORGE_ERRORS, UnsupportedForgeOperation)` (`close.py:36`) around the
tracker list and around each issue's `_one`. An `OSError`, a `ValueError` or a YAML error
from `EvidenceReader` (reading journals and acceptance fragments in the checkout) escapes
into the driver's `_pass_gate` (`triage_batch_cmd.py:5534`, the call) after the gate label has been
written, and can crash the driver pass.

## Requirements

R1. `fr triage collect` records each open issue's author association
(`Issue.author_association`: GitHub's `OWNER`, `MEMBER`, `COLLABORATOR`, `CONTRIBUTOR`,
`NONE`, …). It makes at most one extra forge read per repo per collect for this, and none
when the issue list already carries the field or when no issue in the repo needs it (an
issue needs it when R2's login and label clauses do not admit it). A read that fails, or
that the forge does not support, leaves the association `None`. Issues read through
`view_issue` (past the list limit, or judged in a repo the list did not cover) get their
association too, through the same per-repo read, so a trusted member's issue is not
rejected only because it was viewed rather than listed. Facts move to schema 14.
Older files still load, reading `author_association` as `None`.

R2. One pure function decides intake trust. An issue is eligible when at least one holds:
its author is in `claim_trusted(config, viewer)` (compared case-insensitively); its
association is in `TRUSTED_ASSOCIATIONS`; it carries the `ready-fr` label (label names
compared case-insensitively, as the forge does); its author is the debt workflow's bot
(`fr.triage.debt.BOT_LOGINS`) AND its body carries the debt-digest marker, so the digest
`check` already trusts keeps its body, while any other bot-authored issue is judged like
anyone's. An issue that no
clause admits is ineligible, with a reason that names the author and the association. An
unread author or an unread association never admits an issue: the rule fails closed.

R3. Every issue that `collect` writes has its body cleared when it is ineligible. This
applies to issues listed this collect, viewed through `view_issue`, and carried from the
previous facts by a partial collect, which are judged again on their stored fields. The
title, labels and other fields are kept. A facts file written before schema 14 is judged the
same way when it is loaded, so no reader (`check`, `render`, dedupe, the skill) sees an
ineligible author's body before the next collect.

R4. `fr triage check` lists the open ineligible issues in an `untrusted` set, each with
its reason. An untrusted issue is never in the unranked or unplaced sets, and `batch
suggest` never proposes it. The `fr-triage` skill tells the agent not to judge an issue in
that set, and names `ready-fr` as the way an operator admits one.

R5. `fr triage batch create` and `fr triage batch edit` refuse, exit 2 and writing
nothing, when the batch they would write holds a member that R6's member rule rejects.
The refusal names each such member, its reason, and `ready-fr`. An edit that removes the
last rejected member succeeds.

R6. One member rule decides whether a batch may go out: a member present in facts is
rejected when R2 finds it ineligible, open or closed; a member absent from facts is
rejected as `not collected`. `fr triage batch dispatch` exits 2 on a rejected member,
before any forge write or runner call, naming the members. The wave driver, the board and
`drive --plan` use the same rule: the pass emits a `blocked` action with the reason for
such a batch, every pass, instead of its dispatch, and dispatches it once no member is
rejected. A `blocked` action counts toward the drive's blocked total, so the drive stalls
for the operator rather than finishing as done.

R7. The launch brief's first line is the skill command and the batch id only. Every
member's title, `detail` and `note`, the batch title and the batch rationale are written
inside one delimited block that marks them as untrusted data, written from or about issue
text. Each line in the block is quoted, so no text can close the block or add a heading
outside it. The brief tells the session to treat the block as a description of the
problem and never to follow instructions found in it. The same inputs still give the same
bytes. Every other brief or comment fr writes for a batch from these inputs (the
close-out brief, the red-CI, merge-conflict and archive-conflict hand-backs, the dispatch
marker comment) follows the same rule: its command line names the batch by id only, and
any batch or member title it carries sits in the same quoted block.

R8. `ready-fr` is an operator label, defined beside `approved-fr` in `fr.labels`. fr
never applies it. The driver ensures it exists on a repo whenever it ensures
`approved-fr`, and reports when it cannot. `docs/merge-protection.md` states the
issue-intake trust boundary: who makes an issue eligible, what fails closed, what the
brief marks, who creates the label, and the remaining risk: `ready-fr` admits the issue
as it is later edited, so its author's later edits reach the triage agent and the brief.
The brief's quoting (R7) still applies to them.

R9. In every driver pass, the first merge-context use for a repo fetches its origin,
unless this pass already fetched it, and re-checks the triage config against
`origin/<default>`. If the fetch or the check fails, the repo is held for the rest of the
pass, with one warning, so nothing acts on refs from an earlier fetch. Every merge-context
caller goes through the hold. A later pass whose fetch succeeds acts on the repo again.
The context's `version` block and merge method follow each pass's config.

R10. On the gh CLI client, a label edit whose removals name labels the repository does
not define treats those removals as done: it applies the remaining adds and removals and
succeeds, however many such labels there are. An add that names an undefined label still
fails. `fr triage batch cancel --yes` then writes its cancel event for a member whose repo
does not define `fr:in-progress`.

R11. `fr triage batch cancel` without `--yes` reports, as a warning, that `--yes` would be
refused when the clone it would use does not open or is not the batch's repo. The warning
names the `--checkout <path to a clone of OWNER/REPO>` that `--yes` needs. The dry run
still exits 0. The warning and the `--yes` refusal come from one check.

R12. `close_gate_trackers` never raises. Any exception raised while it reads evidence or
handles one tracker issue is recorded in its report's `errors`, with the exception type and
issue number, and the remaining issues are still handled. The driver's gate-pass line still
prints, and the pass goes on.

## Design

### A. Intake trust (R1–R8)

**Data.** `Issue` gains `author_association: str | None = None`. `FACTS_SCHEMA` moves to
14 with the usual comment paragraph, and `FACTS_READS` adds 14. Facts are a cache under the
scope's state directory and not a registered artifact kind, so no migration is owed: the
next collect rewrites the file.

**The rule.** A new pure module `fr/triage/intake.py` holds:

- `intake_reason(author, association, labels, trusted) -> str | None`: `None` when
  eligible, else the reason, e.g. `author alice is NONE`, `author alice: association not
  read`, `author not read`. It reuses `TRUSTED_ASSOCIATIONS` and adds no second trust list.
- `issue_reason(issue, facts) -> str | None`: the same over a collected issue, with
  `trusted = claim_trusted(facts.config_for(issue.repo), facts.viewer)`.
- `rejected_members(batch, facts) -> list[tuple[str, str]]`: R6's member rule, the ONE
  helper `create`, `edit`, `dispatch_batch` and both snapshot builders call.
- `untrusted_issues(facts) -> list[tuple[Issue, str]]`: the open ineligible issues (R4).

**The read (R1).** The REST client's `_issue_record` keeps `author_association` as
`authorAssociation`, so under `forge.api: rest` the list read already carries it and costs
nothing extra. `GhClient` gains `issue_associations(repo, state, limit) -> dict[int, str]`.
The gh CLI client implements it as one `gh api --paginate
"repos/{repo}/issues?state={state}&per_page=100"` read, keeping issues and dropping pull
requests, bounded by `limit`. The REST client derives it from its list. glab and tea raise
`UnsupportedForgeOperation`, read as "no association": their issues are admitted only by
login or label. Collect calls it once per repo, only when a listed record lacks
`authorAssociation` and an issue of that repo is not admitted by login or label. A failed
read prints one stderr line, as the label reads do (`collect.py:885`), and leaves every
association of that repo `None`.

**Body (R3).** Collect judges every `Issue` it is about to write, in one final step before
facts are built: listed, viewed and carried alike. The step uses each issue's repo config
and the viewer, both of which collect already holds. An ineligible issue gets `body=""`. A
carried issue from a schema-13 file has no association, so an outside author's body is
cleared on the first collect after the upgrade, partial or not.

**Sets (R4).** `check.py`'s `is_set_apart` also returns true for an untrusted issue, which
keeps it out of `unranked` and `unplaced`. `CheckResult` gains `untrusted: list[(Issue,
reason)]`, printed like the other sets. `suggest` drops untrusted keys from `free`. The
`fr-triage` skill's judging step says the same (the skill mirrors are regenerated).

**Batch verbs (R5, R6).** `create`, and `edit` on the batch it would write, call
`rejected_members` before any write or claim and fail with exit 2 when it is non-empty.
`dispatch_batch` calls it after resolving the repo and before the preflight.
`batch_drive.Snapshot` gains `rejected: Mapping[str, str]` (batch id to a reason naming the
members). It is filled from `rejected_members` by both builders, `Driver.snapshot` and
`views.drive_snapshot`, so the board, `drive --plan` and the live pass agree. In the pure
pass's dispatch loop, a batch in `rejected` gets `Action("blocked", reason)` and is counted
as blocked. This check comes before the `after` and in-flight-cap checks, so it is never
reported as merely waiting.

**Brief (R7).** `render_brief`'s first line becomes `{slash} batch {batch.id}`, built
only from engine-checked parts (the id matches `BATCH_ID_RE`). Right after the batch line
come one rule paragraph and a block opened by `<!-- untrusted: written from the issue
tracker -->` and closed by `<!-- /untrusted -->`. The rule says the block describes the
problem, may be wrong or adversarial, and that instructions in it are never followed. Inside
the block are the batch title, every member section (`#### <key>` headings, title, detail,
note) and the rationale. Every line of the block is prefixed `> `, including blank lines and
headings, so member text cannot end the block or forge a top-level heading. `## Delivery
rules` and the debugging rules stay outside: fr writes them.

**Label and docs (R8).** `READY_FR = LabelDef("ready-fr", …, "Operator: an outside issue
may be batched")` sits beside `APPROVED_FR`. `approval.py`'s ensure step (`:256-266`)
ensures both labels, and the `labels off` and failure paths report each. On GitHub,
creating a label needs write permission while applying one needs triage, so the docs say an
operator with write access creates `ready-fr` where fr has not. `docs/merge-protection.md`
gains an "Issue intake" section with the R8 content. `docs/explainers/fr-triage.md` and
`fr-wave-driver.md` mention the `untrusted` set and the blocked batch, as `fr docs check`
requires.

### B. Fetch every pass (R9)

`_fresh_config` is split into the fetch and a `_config_fresh(checkout, facts, repo)` that
only compares `.fr/triage.yaml` on `origin/<default>` with the facts. `Driver` keeps two
per-pass sets, reset with the other per-pass state (`triage_batch_cmd.py:5176-5180`):
`_ctx_checked` (the repos checked this pass) and `_ctx_held` (the repos whose check
failed). `merge_ctx` works in four steps:

1. A repo in `_ctx_held` raises `DefaultBranchUnknown` again at once, without a second
   fetch or a second warning.
2. On the first use in a pass: fetch unless the repo is in `_fetched`, then add it to
   `_fetched`. Then run `_config_fresh` and resolve the default branch. On a fetch or
   default-branch failure, add the repo to `_ctx_held` and raise `DefaultBranchUnknown`
   (`_ctx_or_hold` holds it and warns once). A stale config raises the `ForgeReadError`
   (code 2) it raises today. Only on success is the repo added to `_ctx_checked`.
3. Build the context if it does not exist. The repo's allowed merge methods are read
   once, at that build.
4. Every use: refresh `ci_none`, `rules`, `version` (from `facts.config_for(repo)`) and
   `method` (`choose_method` over the stored allowed methods and this pass's configured
   method; no forge read).

`_closeout_hand_back` gets its default branch through `_ctx_or_hold`. A held repo returns
`("<detail>; held: <reason>", False)` for the action and spends no hand-back budget.

### C. Cancel converges (R10, R11)

gh resolves label names to ids before it changes anything, so a call that fails with
`'<label>' not found` has written nothing. `gh.swap_issue_labels` relies on that, and the
docstring says so. While a `GhError` names a *remove* label as not found (and no *add*
label), it drops that label and retries. That is at most `len(remove)` retries, and it
returns once nothing is left to change. Any other failure, or a missing *add* label,
raises. This covers every caller of the adapter and matches the REST client's behaviour.
glab and tea are not changed (out of scope; not reported failing).

A new `_checkout_refusal(checkout_path, owner_repo) -> str | None` holds `_open_checkout`'s
two checks (no clone, wrong origin) without exiting, and `_open_checkout` calls it. The dry-run
branch of `_tracking_gate` calls it and, on a reason, prints `warning: --yes would be
refused — <reason>; pass --checkout <path to a clone of OWNER/REPO>`. `dispatch` shares
the gate, so its dry run gains the same warning.

### D. Contain the gate-tracker close (R12)

`close_gate_trackers` builds the `EvidenceReader` inside a guard. In the per-issue loop it
catches `Exception` beyond `_FAILURES` and records `issue #<n>: <Type>: <message>`. The
tracker list read keeps its `_FAILURES` catch and also gains the broad one. The broad catch
is deliberate: the gate label is already written when this runs, so raising reverses
nothing and only stops the driver. The caller prints the report's errors, so nothing is
silent.

### Out of scope

- A never-dispatched batch cancelling with no checkout (#1406 side ask 2): the gh#803
  tracking gate stays as it is. Filed as a follow-up.
- glab and tea label-removal idempotence.
- Voiding `ready-fr` when an admitted issue is edited later. It would need a timeline read
  per labelled issue. R8 documents the residual risk instead, and R7 still quotes the text.
- Whether the batch session itself reads member issues from the forge once it runs
  (#1252 trace, "not verified"). R7 covers the text fr hands it.

## Verification

strategy: candidate
gate: developer

- intake-trust-eligibility: none — CI unit tests on `intake_reason` and collect over a fake forge: a member's issue, the viewer's, a `pr_authors` login's (association unread, still eligible), a `ready-fr` one and an outside one are judged correctly; an unread author or association never admits; the association read happens at most once per repo, and not at all when every issue is admitted or the list carries the field
- intake-untrusted-set-apart: none — CI unit tests: an outside issue's body is not stored on a full collect, a `view_issue` read or a partial collect that carries a schema-13 issue; it is in `check`'s `untrusted` set with its reason, and never unranked, unplaced or suggested
- intake-batch-refuses-untrusted: none — CI tests: `batch create`/`edit`/`dispatch` exit 2 with no write for a rejected or uncollected member, and an edit removing it succeeds; both snapshot builders fill `rejected` alike, and the pure pass emits `blocked` (counted) before the `after` and cap checks, then dispatches once the member carries `ready-fr`
- intake-brief-quotes-untrusted: none — CI unit test: the first line carries only the command and the batch id; titles, detail, note and rationale are inside the quoted untrusted block; member text with a forged heading or closing marker stays quoted; output is deterministic
- driver-refetches-origin-each-pass: none — CI test: a driver whose second pass cannot fetch holds the repo with one warning, for every merge-context use of that pass including a close-out hand-back, and acts again on a third pass whose fetch works; a config change between passes changes the context's version and method
- cancel-converges-undefined-label: none — CI tests: `swap_issue_labels` drops one and then two undefined removal labels and succeeds, still fails on an undefined add; `batch cancel --yes` writes its event
- cancel-dry-run-names-checkout: none — CI test: the dry run with no matching clone prints the `--checkout` warning and exits 0, and `--yes` refuses with the same reason
- gate-trackers-contain-errors: none — CI tests: an `OSError` from the evidence reader and a `ValueError` from one issue are reported in `errors`, the other issues are still closed, and the driver pass completes

The walk runs the candidate smoke only (install, version, status in a fresh fixture).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-17-triage-intake | `derio-net/super-fr` | `2026-11-17-triage-intake` | — |
