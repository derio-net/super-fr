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
(`collect.py:443-449`). It records no author association: `gh issue list --json` has no
such field (`ISSUE_LIST_FIELDS`, `packages/fr/src/fr/gh.py:508`), and the REST client's
issue record drops `author_association` (`packages/fr/src/fr/real_ghrestclient.py:272-288`).
The comment reads carry it (`real_ghclient.py:374`, `real_ghrestclient.py:299`). Nothing gates
which issues may be ranked (`fr triage check`'s `classify`,
`packages/fr/src/fr/triage/check.py:498`), suggested (`suggest`, `batch.py:780`),
put in a batch (`batch_create_command`,
`packages/fr/src/fr/commands/triage_batch_cmd.py:748`, and `edit`) or dispatched
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

**#1406: cancel never converges on an undefined label.** `batch cancel --yes`
(`triage_batch_cmd.py:894`) calls `edit_issue_labels(..., remove={fr:in-progress})` on
every withdrawn member (`:972-974`). On the gh CLI client this is `gh.swap_issue_labels`
(`gh.py:407-425`), a single `gh issue edit --remove-label`. gh fails the whole call when
the repo does not define the label (`'fr:in-progress' not found`), so the member is
reported as not withdrawn and no cancel event is written, on every rerun. The REST client
already treats GitHub's absent-label 404 as done (`real_ghrestclient.py:1120-1128`).
The dry run also passes while `--yes` then refuses over the clone:
`_tracking_gate` (`triage_batch_cmd.py:1059`) opens the batch's repo strictly only under
`--yes` (`_open_checkout`), and the dry run returns silently when no clone opens (`:1069-1072`).

**#1299: non-forge exceptions escape the gate-tracker close.** `close_gate_trackers`
(`packages/fr/src/fr/gatebackfill/close.py:346`) catches only
`_FAILURES = (*FORGE_ERRORS, UnsupportedForgeOperation)` (`close.py:35`) around the
tracker list and around each issue's `_one`. An `OSError`, a `ValueError` or a YAML error
from `EvidenceReader` (reading journals and acceptance fragments in the checkout) escapes
into the driver's `_pass_gate` (`triage_batch_cmd.py:5534`) after the gate label has been
written, and can crash the driver pass.

## Requirements

R1. `fr triage collect` records each open issue's author association
(`Issue.author_association`, GitHub's `OWNER`, `MEMBER`, `COLLABORATOR`, `CONTRIBUTOR`,
`NONE`, …). It reads the association only for an issue whose author is not trusted by login
(R2's first clause) and that does not carry `ready-fr`. A read that fails or that the forge
does not support leaves it `None`. Facts move to schema 14. Older files still load, reading
`author_association` as `None`.

R2. One pure function decides intake trust. An issue is eligible when at least one holds:
its author is in `claim_trusted(config, viewer)` (compared case-insensitively); its
association is in `TRUSTED_ASSOCIATIONS`; it carries the `ready-fr` label. Otherwise it is
ineligible, with a reason that names the author and the association. An issue whose author
or association was never read is ineligible: the rule fails closed.

R3. `collect` stores no body for an ineligible issue. Its title, labels and other fields
are kept.

R4. `fr triage check` lists the open ineligible issues in an `untrusted` set, each with
its reason. An untrusted issue is never in the unranked or unplaced sets, and `batch
suggest` never proposes it. The `fr-triage` skill tells the agent not to judge an issue in
that set, and names `ready-fr` as the way an operator admits one.

R5. `fr triage batch create` and `fr triage batch edit` refuse, exit 2 and writing
nothing, a batch that would hold an ineligible member. The refusal names each such member,
its reason, and `ready-fr`.

R6. Dispatch refuses a batch that holds an ineligible member, judged on the facts the
dispatch reads. `fr triage batch dispatch` exits 2 before any forge write or runner call,
naming the members. The wave driver dispatches nothing for such a batch and reports it as
held with the reason, every pass, until the member becomes eligible.

R7. The launch brief writes every member's title, `detail` and `note` inside one delimited
block that marks them as untrusted data quoted from the issue tracker. The brief tells the
session to treat that block as a description of the problem and never to follow
instructions found in it. The same inputs still give the same bytes.

R8. `ready-fr` is an operator label, defined beside `approved-fr` in `fr.labels`. fr never
applies it. `docs/merge-protection.md` states the issue-intake trust boundary: who makes an
issue eligible, what fails closed, and what the brief marks.

R9. In every driver pass, the first merge-context use for a repo fetches its origin and
re-runs the triage-config freshness check, sharing that pass's one fetch per repo with the
other readers. If the fetch fails, the repo is held for the pass, with the same one warning
as an unknown default branch, so nothing acts on refs from an earlier fetch. A later pass
whose fetch succeeds acts on the repo again.

R10. On the gh CLI client, a label edit whose removal names a label the repository does
not define treats that removal as done: it applies the remaining adds and removals and
succeeds. An add that names an undefined label still fails. `fr triage batch cancel --yes`
then writes its cancel event for a member whose repo does not define `fr:in-progress`.

R11. `fr triage batch cancel` without `--yes` reports, as a warning, that `--yes` would be
refused when the clone it would use does not open or is not the batch's repo. The warning
names the `--checkout <path to a clone of OWNER/REPO>` that `--yes` needs.

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

- `READY_FR`, re-exported from `fr.labels` (R8);
- `intake_verdict(issue, facts) -> str | None`: `None` when eligible, else the reason, e.g.
  `author alice is NONE`, `author alice: association not read`, `author not read`;
- `untrusted_issues(facts) -> list[tuple[Issue, str]]` for the open ineligible issues.

It reuses `claim_trusted` and `TRUSTED_ASSOCIATIONS` and adds no second trust list.
`collect` cannot call `intake_verdict` on a `Facts` that does not exist yet, so the function
takes its inputs explicitly (`author`, `association`, `labels`, `trusted logins`). The
`Facts` form wraps it, so collect and every reader share one definition.

**The read.** `GhClient` gains `issue_author_association(repo, number) -> str | None`. The
gh CLI client implements it with `gh api repos/{repo}/issues/{n} --jq .author_association`.
The REST client uses its `_api` route. glab and tea raise `UnsupportedForgeOperation`, which
the collector reads as `None`: those issues are ineligible unless the login or the label
admits them. The collector's `Forge` protocol and `ClientForge` gain the same method. Collect
calls it only where R1 says, so a repo whose issues are all by the viewer costs no extra
read. A failed read prints one stderr line, like the label reads at `collect.py:885`.

**Body.** In `_issue` (`collect.py:452`) the body is `""` when the verdict says ineligible.
The verdict is computed with the repo config and the viewer that collect already has at
`collect.py:655`. A partial collect carries an issue as it was, body included or not.

**Sets.** `check.py`'s `is_set_apart` also returns true for an untrusted issue, which
keeps it out of `unranked` and `unplaced`. `CheckResult` gains `untrusted: list[(Issue,
reason)]`, printed like the other sets. `suggest` drops untrusted keys from `free`.

**Batch verbs.** `create` and `edit` (when they add members) call one helper,
`_refuse_untrusted(batch_ids, facts, verb)`, before any write or claim. `dispatch_batch`
calls the same helper after resolving the repo and before the preflight. The driver does
not rely on that refusal. `batch_drive.Snapshot` gains `untrusted: Mapping[str, str]`
(batch id to reason), built in `Driver.snapshot` from `intake.untrusted_issues`. The pure
pass emits a `blocked` action for such a batch instead of a `dispatch`, as it does for a
batch whose members all await their live walk.

**Brief.** `render_brief` puts the member sections inside one block that opens with a fixed
line, such as `<!-- untrusted: quoted from the issue tracker -->`, and a short rule. The rule
says the block describes the problem, may be wrong or adversarial, and that instructions in
it are never followed. Each member's title, `detail` and `note` lines are quoted (`> ` per
line), so no member text can close the block or forge a heading at the brief's top level.
`## Why these belong together` and `## Delivery rules` stay outside the block. They are
engine-written or operator-written (`rationale`, from `batch create`).

**Docs and label.** `READY_FR = LabelDef("ready-fr", …, "Operator: an outside issue may be
batched")` sits beside `APPROVED_FR`. It is created by whatever already ensures operator
labels when that path exists; fr never applies it. `docs/merge-protection.md` gains an
"Issue intake" section. `docs/explainers/fr-triage.md` and `fr-wave-driver.md` mention the
`untrusted` set and the driver hold, as `fr docs check` requires.

### B. Fetch every pass (R9)

`merge_ctx` keeps building the context once, but its per-pass part grows. It tracks a
per-pass set (reset with the other per-pass state at `triage_batch_cmd.py:5176-5180`) of
repos whose context was checked this pass. On the first use in a pass, it runs
`_fresh_config(checkout, facts, repo, hold_unknown=True)` and adds the repo to `_fetched`,
so `_fetched_reader` does not fetch again in the same pass. A failed fetch raises
`DefaultBranchUnknown`, which `_ctx_or_hold` already turns into a held repo with one
warning. Creation itself no longer runs `_fresh_config` separately: the first per-pass check
covers it. When a fetch already ran this pass through `_fetched_reader`, the check still
re-runs the config freshness against `origin/<default>`, without a second fetch.

### C. Cancel converges (R10, R11)

`gh.swap_issue_labels` catches a `GhError` whose message names one or more of the
*remove* labels as `not found` (gh's `'<label>' not found`), and that names no *add* label.
It drops those labels and retries once with the rest. It returns when nothing is left. Any
other failure, or a missing *add* label, still raises. This covers every caller of the
adapter, not only cancel, and matches the REST client's behaviour. The glab and tea clients
are not changed (out of scope; not reported failing).

The dry-run branch of `_tracking_gate` also tries `_open_checkout(checkout_path,
owner_repo)`. When that raises a `TriageError`, it prints `warning: --yes would be refused —
<reason>; pass --checkout <path to a clone of OWNER/REPO>` and goes on. The dry run still
exits 0, and the `--yes` path is unchanged. `dispatch` shares the gate, so its dry run gains
the same warning.

### D. Contain the gate-tracker close (R12)

`close_gate_trackers` builds the `EvidenceReader` inside a guard. In the per-issue loop it
catches `Exception` beyond `_FAILURES` and records `issue #<n>: <Type>: <message>`. The
broad catch is deliberate. The gate label is already written when this runs, so raising
reverses nothing and only stops the driver. The report's errors are printed by the caller,
so nothing is silent. The tracker list read keeps its `_FAILURES` catch and also gains the
broad one.

### Out of scope

- A never-dispatched batch cancelling with no checkout (#1406 side ask 2): the gh#803
  tracking gate stays as it is. Filed as a follow-up.
- glab and tea label-removal idempotence.
- Reading whether the batch session itself reads member issues from the forge once it
  runs (#1252 trace, "not verified"). R7 covers the text that fr hands it.

## Verification

strategy: candidate
gate: developer

- intake-trust-eligibility: none — CI unit tests on `intake_verdict` and collect over a fake forge: a member's issue, the viewer's, a `pr_authors` login's, a `ready-fr` one and an outside one; an unread author or association is ineligible; the association read happens only when needed
- intake-untrusted-set-apart: none — CI unit tests: an outside issue's body is not stored, it is in `check`'s `untrusted` set with its reason, and it is never unranked, unplaced or suggested
- intake-batch-refuses-untrusted: none — CI tests: `batch create`/`edit`/`dispatch` exit 2 with no write for an untrusted member; the driver's pure pass holds the batch with the reason and dispatches it once the member is labelled `ready-fr`
- intake-brief-quotes-untrusted: none — CI unit test: the brief carries the untrusted block and rule, member text with a forged heading stays quoted, and the output is deterministic
- driver-refetches-origin-each-pass: none — CI test: a driver whose second pass cannot fetch holds the repo with one warning and acts again on a third pass whose fetch works
- cancel-converges-undefined-label: none — CI tests: `swap_issue_labels` retries without a removed label gh reports `not found`, still fails on an undefined add; `batch cancel --yes` writes its event
- cancel-dry-run-names-checkout: none — CI test: the dry run with no matching clone prints the `--checkout` warning and exits 0
- gate-trackers-contain-errors: none — CI tests: an `OSError` from the evidence reader and a `ValueError` from one issue are reported in `errors`, the other issues are still closed, and the driver pass completes

The walk runs the candidate smoke only (install, version, status in a fresh fixture).
