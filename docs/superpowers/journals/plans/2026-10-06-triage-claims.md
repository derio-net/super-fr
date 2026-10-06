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
