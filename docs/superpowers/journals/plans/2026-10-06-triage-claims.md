# Journal: 2026-10-06-triage-claims

<!-- fr:journal kind=decision scope=plan id=p1-trusted-claim-authors created=2026-10-06T20:03:24+00:00 phase=1 -->
### p1-trusted-claim-authors · decision · Only trusted authors' claim markers count (R17) (phase 1)

Security review (orchestrator scope addition): on a public repo any account can comment, and under
R4 (oldest un-released marker wins, an expired one still holds) a stranger's back-dated `fr-claim`
marker would lock every scope out of the issue. So `read_claims`/`claims_from_comments` take
`trusted` (the repo's allowed authors: `pr_authors`, default `Facts.viewer`, compared
case-insensitively, through the one helper `fr.triage.model.trusted_logins` that
`batch.allowed_authors` now calls) and ignore and count any other author's marker
(`ClaimRead.untrusted`). Collect passes each repo's set; every claim_writes call takes `trusted`
and every re-read applies it; a claim whose own posted marker is by an untrusted author withdraws
it and raises ClaimError, because no reader would count it. Spec gained R17, the Non-goals'
security bullet, and §3.B/§3.D.

<!-- fr:journal kind=decision scope=plan id=p1-claim-precheck-and-stray-releases created=2026-10-06T20:03:24+00:00 phase=1 -->
### p1-claim-precheck-and-stray-releases · decision · claim() checks R4 before posting; owed_releases also covers own stray claims (phase 1)

`claim_writes.claim` reads first and returns Held without writing when another scope already
holds the issue; R4's post-then-re-read still decides races (tested by a racing fake). An own
losing marker found at that read is withdrawn. `claims.owed_releases` takes `own` (this
scope's claims facts show) and adds those on keys no batch owes any more: that is how the
members `batch edit --remove-issue` dropped and a proposed batch whose wave was cleared are
released by a later `claim sync` when the edit ran without `--yes`. Releases of releasing
batches stay derived from the batch (only batches that ever owed claims: a wave or a dispatch),
and a `claims_released` event counts only after the batch's last other event, so a redispatch
owes claims (and later releases) again. `release()` writes nothing when the signer has no
un-released marker there.

<!-- fr:journal kind=decision scope=plan id=p1-dispatch-claims-and-cancel-recording created=2026-10-06T20:03:24+00:00 phase=1 -->
### p1-dispatch-claims-and-cancel-recording · decision · dispatch_batch claims (so the driver's dispatch does too); cancel records only real releases (phase 1)

`dispatch_batch` is shared by `batch dispatch` and the wave driver, so the R3 claims (and R6's
held refusal) live there and every driven dispatch claims first. A wave-less batch owes no claim
until it is dispatched, so when its claims lose a race, fail, or the runner launch fails, the
markers that call posted are withdrawn (best effort; `claim sync` releases the rest). `batch
cancel` appends `claims_released` only for members where a marker was actually released, so a
claim-free cancel reads exactly as before; `claim sync` records the rest. `scope_id` also takes
a scope name, and `claim_env` derives the scope from `facts.scope` (every loader checks the
facts match the scope), so `dispatch_batch` needs no Scope parameter.

<!-- fr:journal kind=discovery scope=plan id=p1-host-id-minted-by-the-suite created=2026-10-06T20:03:24+00:00 phase=1 -->
### p1-host-id-minted-by-the-suite · discovery · A CLI test reaching scope_id minted ~/.config/fr/host-id in the real home (phase 1)

The first run of the check tests after `check` started computing the scope id created
`~/.config/fr/host-id` on the operator's machine: the suite does not isolate HOME. Caused by this
run, so the file was removed (nothing had read it), and `tests/conftest.py` now pins
`FR_HOST_ID` for every test (`_fixed_triage_host_id`); the tests of minting itself delete it and
point HOME at a tmp dir.

<!-- fr:journal kind=finding scope=plan id=p1-r17-default-trust-across-users created=2026-10-06T20:03:24+00:00 phase=1 state=open review_scope=out -->
### p1-r17-default-trust-across-users · finding [open] (reviewer: out of scope) · With no pr_authors, two hosts running as different forge users distrust each other's claims (phase 1)

R17's default trusted set is `Facts.viewer`, the user `collect` ran as. Two scopes driven by
different GitHub accounts on a repo with no `pr_authors` in `.fr/triage.yaml` each ignore the
other's markers, so neither sees the other's claims and both act: the coordination R1-R6 promise
silently does not happen. The safe configuration is to list every driving account in
`pr_authors`; the fr-triage skill (phase 3, R16) should say so, and `scope show` or `check`
could warn when the viewer is the only trusted login.

<!-- fr:journal kind=finding scope=plan id=p1-r17-origin-not-on-matrix created=2026-10-06T20:03:24+00:00 phase=1 state=open review_scope=in -->
### p1-r17-origin-not-on-matrix · finding [open] (reviewer: in scope) · triage-claims-writes does not cite R17 yet (phase 1)

`fr acceptance set-status` has no option that adds an origin, so `#R17` could not be added to
row triage-claims-writes from this phase; the orchestrator adds it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

fr.artifacts.atomic.write_text_atomic replaces into place (os.replace), which overwrites; the host id needs exclusive create (link fails when the file exists), so the helper does not fit the link-into-place shape.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

The batch markers' grammar is `<prefix><item-id> -->` matched by startswith; the claim marker is a JSON payload validated by a model. They share nothing beyond the HTML-comment wrapper, so a shared helper would add indirection without removing code. BatchStage is imported from fr.triage.batch rather than redeclared.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

Two small additions (an id parsed by one regex, one PATCH call) and the mixin method; no duplication arose.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

The read-parse-decide sequence is already one helper (`_read` + `_own` + `holder`) used by every write; take reuses claim; nothing further to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

The one refactor owed was done in the GREEN step: the pr_authors/viewer rule moved into `fr.triage.model.trusted_logins`, which `batch.allowed_authors` and collect both call, so claims and batch PRs share one allowlist (R17). The batch-marker time and the claims come from one comment read (`_comment_facts`).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

The three sets are computed once (`check.claim_sets`) and printed by one function (`triage_cmd.print_claim_sets`) shared by `check` and `claim list`; plan/execute/record live in `fr.triage.claim_sync`, shared by the claim group and the batch verbs. Nothing left duplicated.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

Done as the step asks: `triage_batch_cmd.claim_env(target, facts)` is the one resolver of (client, scope id, scope config), used by create, edit, dispatch, merge, cancel and every `claim` verb; `_refuse_held`/`_settle_claims`/`_claim_ops` are shared by the verbs.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t9 created=2026-10-06T20:03:24+00:00 phase=1 -->
### no-refactor-p1-t9 · discovery · no-refactor-because P1.T9 (phase 1)

Test scaffolding only: two scenario scripts on the existing _common.sh helpers and one fixture generator; nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · R17 default trust (pr_authors else viewer) makes hosts on different GitHub accounts silently ignore each other's claims (phase 1)

R17 default trust (pr_authors else viewer) makes hosts on different GitHub accounts silently ignore each other's claims.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · with pr_authors set the viewer is excluded from the trusted set, so every own claim is refused (phase 1)

with pr_authors set the viewer is excluded from the trusted set, so every own claim is refused.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · owed_releases/release not batch-scoped: releasing an old batch releases a claim rewritten for a new live batch (phase 1)

owed_releases/release not batch-scoped: releasing an old batch releases a claim rewritten for a new live batch.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · batch dispatch skips the R4 re-read for members already claimed for the batch (phase 1)

batch dispatch skips the R4 re-read for members already claimed for the batch.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · release removes fr:claimed from a pre-edit read; refresh/rewrite never re-add it; orphan labels on error paths (phase 1)

release removes fr:claimed from a pre-edit read; refresh/rewrite never re-add it; orphan labels on error paths.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · check's claims_owed also lists members held elsewhere (phase 1)

check's claims_owed also lists members held elsewhere.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · malformed/untrusted marker counts are never surfaced (phase 1)

malformed/untrusted marker counts are never surfaced.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · cancel of a proposed wave'd batch with stale facts skips the release (phase 1)

cancel of a proposed wave'd batch with stale facts skips the release.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · R4 race test uses a back-dated rival and has no case where our older marker wins (phase 1)

R4 race test uses a back-dated rival and has no case where our older marker wins.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-10-06T20:40:50+00:00 phase=1 state=open review_scope=out -->
### p1-r10 · finding [open] (reviewer: out of scope) · batch merge with no ids refuses every queued batch when one is held (phase 1)

Follows R6's literal wording ('the commands refuse with exit 2'); whether a default merge should skip held batches is a spec question, not a defect of this change.

<!-- fr:journal kind=decision scope=plan id=p1-claim-trust-member created=2026-10-06T20:40:50+00:00 phase=1 -->
### p1-claim-trust-member · decision · Claims trust org MEMBER association (accepted residual from a background security review) (phase 1)

Trusting authorAssociation MEMBER also trusts an org member with read-only repo access. Kept: drivers usually get write access through team membership, which GitHub reports as MEMBER, and dropping it reintroduces p1-r1. GitHub computes the association server-side, so it can't be spoofed; strangers on public repos (NONE/CONTRIBUTOR/FIRST_TIME_CONTRIBUTOR) stay excluded, which is R17's threat. A claim coordinates trusted actors and is not a security boundary between them; pr_authors remains for repos that want an explicit list.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-06T20:40:50+00:00 phase=1 -->
### p1-review-1 · review · phase 1 independent review: 9 in-scope findings fixed, 1 out of scope (phase 1)

An independent reviewer (separate context, hard tier) read spec R1-R17, plan phase 1 and the diff f0e5b0fb1..HEAD, and ran the claim test files (343 passed, no real ~/.config writes). It confirmed the R4 race, refresh-not-resurrecting, in-place rewrite, release timing, dispatch-before-launch, held cancel, schema bumps, host-id exclusivity and R17 coverage. It raised p1-r1..p1-r9 (in) and p1-r10 (out). The orchestrator verified r1/r2 (model.py trusted_logins), r3 (claim_writes.release ignores the batch) and r5 (label removal decided pre-edit) against the code and gh's comment fields (authorAssociation present). All nine in-scope findings were fixed test-first in 66892d334..4be36b54c, and a new row triage-claims-trusted-authors (R17) was added. Full suite after the fixes: 9867 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: R17 default trust (pr_authors else viewer) makes hosts on different GitHub accounts silently ignore each other's claims (phase 1)

claim_trusted: viewer ∪ pr_authors ∪ authorAssociation OWNER/MEMBER/COLLABORATOR; PR merge guard unchanged (66892d334).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: with pr_authors set the viewer is excluded from the trusted set, so every own claim is refused (phase 1)

claim_trusted always includes the viewer (66892d334).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: owed_releases/release not batch-scoped: releasing an old batch releases a claim rewritten for a new live batch (phase 1)

owed_releases drops keys still owed by a non-releasing batch; release(batch=) skips a marker naming another batch (6a6530956).

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: batch dispatch skips the R4 re-read for members already claimed for the batch (phase 1)

dispatch sends every member through claim_writes.claim before the runner launch (09ac39f65).

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: release removes fr:claimed from a pre-edit read; refresh/rewrite never re-add it; orphan labels on error paths (phase 1)

release re-reads after removal and restores; refresh/rewrite ensure the label; error paths clean an orphan label (87023cfea).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: check's claims_owed also lists members held elsewhere (phase 1)

claims_owed skips held-elsewhere members (4d73a05c2).

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: malformed/untrusted marker counts are never surfaced (phase 1)

collect warns once per issue with the counts (74031e4ab).

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: cancel of a proposed wave'd batch with stale facts skips the release (phase 1)

cancel treats any batch with a wave as touching the forge (2de99fa80).

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: R4 race test uses a back-dated rival and has no case where our older marker wins (phase 1)

two-writer test with near-simultaneous created_at where ours is older (4be36b54c).

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=open resolves=p1-r10 out_of_scope=true -->
### p1-r10-resolved · finding [out-of-scope] · resolves p1-r10: batch merge with no ids refuses every queued batch when one is held (phase 1)

Not caused by this change's code: it implements R6 as worded. A default merge skipping held batches would be a spec change.

<!-- fr:journal kind=finding scope=plan id=p1-r17-origin-not-on-matrix-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=fixed resolves=p1-r17-origin-not-on-matrix -->
### p1-r17-origin-not-on-matrix-resolved · finding [fixed] · resolves p1-r17-origin-not-on-matrix: triage-claims-writes does not cite R17 yet (phase 1)

R17 got its own row, triage-claims-trusted-authors (status ci, 9 unit refs), added with fr acceptance add (855dd503c).

<!-- fr:journal kind=finding scope=plan id=p1-r17-default-trust-across-users-resolved created=2026-10-06T20:40:50+00:00 phase=1 state=open resolves=p1-r17-default-trust-across-users out_of_scope=true -->
### p1-r17-default-trust-across-users-resolved · finding [out-of-scope] · resolves p1-r17-default-trust-across-users: With no pr_authors, two hosts running as different forge users distrust each other's claims (phase 1)

Duplicate of p1-r1, which the independent reviewer raised in scope and which was fixed in 66892d334; this executor-tagged out-of-scope entry is closed in favour of that one rather than reclassified.

<!-- fr:journal kind=decision scope=plan id=p2-claim-writes-are-not-progress created=2026-10-06T21:17:24+00:00 phase=2 -->
### p2-claim-writes-are-not-progress · decision · A claim, refresh or release write never counts as the pass having acted (phase 2)

`_claim_write` always returns did=False, so a pass whose only work was claim bookkeeping still exits 3
("work remains, nothing moved") exactly as before; a write that wrote nothing (a blind refresh of a
closed member, a release with no marker) prints no line. Refreshes of members facts cannot see (closed
issues: collect reads no closed issue's comments) are owed only under --yes and never announced in a
plan. Releases are recorded through `record_releases` and `_save`; a recording the writer refuses (a
cyclic state file) is warned once and retried next pass, because the forge release is idempotent.

<!-- fr:journal kind=decision scope=plan id=p2-held-batches-block-the-summary created=2026-10-06T21:17:24+00:00 phase=2 -->
### p2-held-batches-block-the-summary · decision · A held batch is reported once, skipped by every step, and counted blocked (phase 2)

drive_pass emits one `held` action per selected, non-cancelled batch with a member in `Snapshot.held`
and skips it in the merge train, close-out, archive and dispatch steps. A live one keeps counting
against --max-inflight (stage unchanged); a proposed one takes no slot. Each counts as `blocked`, so a
drive with nothing else left reads waiting-on-operator rather than done. A claim write that returns Held
at act time (R4) stops later actions for that batch in the same pass.

<!-- fr:journal kind=discovery scope=plan id=p2-yaml-rewrite-breaks-text-edit-tests created=2026-10-06T21:17:24+00:00 phase=2 -->
### p2-yaml-rewrite-breaks-text-edit-tests · discovery · Recording claims_released rewrites judgements.yaml, so a test that text-patches it between passes breaks (phase 2)

`_finish` in test_triage_batch_drive_cmd.py replaced a dispatch-event line in the file text; once an
earlier pass records claims_released the file is re-serialised and the text no longer matches. It now
edits the parsed YAML. Existing archived-batch tests also see one extra claims_released event on the
pass after the close-out is recorded (the release is derived from the archived close-out).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-06T21:17:24+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

The command layer is thin glue over claim_sync (plan_sync, execute, record_releases) and claim_env; the one extraction worth making, _claim_plan, was made in the GREEN step, so nothing was left to clean.
