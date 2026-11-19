<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-local-suite-cost

<!-- fr:journal kind=finding scope=plan id=p1-call-count-target created=2026-11-19T10:18:37+00:00 phase=1 state=open review_scope=in -->
### p1-call-count-target · finding [open] (reviewer: in scope) · Spec §3.A's ceiling of 500 git starts is out of R1's reach: the cache gets the profiled test to 611 (phase 1)

Measured with tests/unit/test_git_cache_call_count.py (a Popen counter over the
profiled test's own body): 924 without the cache, 611 with it. The cache does what
R1 asks: remote_name and remote_default_ref now cost one answer per fr invocation
(5 git starts each time, 19 invocations: config --system, config --get
checkout.defaultRemote, remote, symbolic-ref, rev-parse --verify), down from about
seven. Spec §2's "about 490 calls" is not all removable, because every CLI call
opens a new scope and asks once. The rest of the 611 comes from call sites R1 leaves
out of scope: rev-parse --verify <ref>^{commit} (51, settings/load.py:108 and the
acceptance fold), rev-parse --git-dir (62), for-each-ref (42), --show-toplevel (29),
rev-parse --verify HEAD (20). The test pins CEILING = 615. Two ways to settle it:
amend §3.A's target to the measured figure, or widen R1 (a process-wide memo of the
system-config path would save 19; caching the ^{commit} lookups would save about 50).

<!-- fr:journal kind=decision scope=plan id=p1-git-cache-imports created=2026-11-19T10:18:37+00:00 phase=1 -->
### p1-git-cache-imports · decision · git_cache imports fr.git's ceiling and git_answer helpers inside its functions, not only types (phase 1)

git.py imports git_cache at module level, so git_cache takes `_ceiling_directories`
(the walk stops where git's discovery stops, as safe_directory_args does) and
`git_answer` (the system-config probe, run with the C locale and time limit) through
function-local imports. That avoids the import cycle and keeps one git seam. It
imports nothing else from fr.

<!-- fr:journal kind=decision scope=plan id=p1-fingerprint-extras created=2026-11-19T10:18:37+00:00 phase=1 -->
### p1-fingerprint-extras · decision · The fingerprint is wider than §3.A's list, and every gap fails toward going to git (phase 1)

Beyond §3.A it also records st_ctime_ns, every GIT_* variable plus HOME and
XDG_CONFIG_HOME (rather than only GIT_CONFIG_COUNT/KEY/VALUE), and the legacy
<common>/remotes and <common>/branches entries `git remote` also lists. locate()
also returns None for a bare repository on the walk, a system-config path git
will not name, and an include key passed through GIT_CONFIG_PARAMETERS or
GIT_CONFIG_KEY_*. An answer is stored only when a fingerprint taken over the
well-known names before git ran still holds after it, so a racing write is never
cached. When the system config file exists but is empty, `config --system --list
--show-origin` names no path, so the probe falls back to `git var GIT_CONFIG_SYSTEM`.

<!-- fr:journal kind=discovery scope=plan id=p1-tdd-order created=2026-11-19T10:18:37+00:00 phase=1 -->
### p1-tdd-order · discovery · Task 2's locate/fingerprint tests were written before git_cache.py but first run after it (phase 1)

Task 3's routing tests were seen RED (one question cached starts no git: 19 != 13;
the call count read 924), then GREEN. Task 2's tests were written first, but they
first ran after git_cache.py existed, so their RED was never observed. They pass.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-19T10:18:37+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-assertion smoke test and a two-key fragment: nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Spec §3.A's ≤500 git-start target unmet; the test ceiling was moved to 615 without amending the spec (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · `git config --system --show-origin` ran once per scope, adding a git start to every command (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Any [include]/[includeIf] in the global config disabled the cache (true on the operator's host) (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Race guard's before-stamp omitted the branch named by refs/remotes/<remote>/HEAD (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Invalidation tests never proved a cache hit before the mutation (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · Legacy GIT_CONFIG env file is read by git but not stat'd (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-19T10:39:38+00:00 phase=1 -->
### review-p1-1 · review · Phase 1 independent review: 6 findings, all in scope, all fixed (phase 1)

Reviewer (general-purpose, separate context) reviewed c2b93b280..0353961fb against spec R1/§3.A. Raised p1-r1..p1-r6 (all in scope). Fixes: 921f5d788 (p1-r2..r6, each red-first) and the spec amendment (p1-r1). Assessment: with fixes.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Spec §3.A's ≤500 git-start target unmet; the test ceiling was moved to 615 without amending the spec (phase 1)

Fixed in the spec: §3.A now pins the measured figure (926 → ≤604, 593 measured after the review fixes) and explains why the 500 estimate was wrong (it counted out-of-scope `rev-parse --verify <ref>^{commit}` call sites).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: `git config --system --show-origin` ran once per scope, adding a git start to every command (phase 1)

Fixed in 921f5d788: the system config path is memoized process-wide (`_SYSTEM_MEMO`), keyed on the git binary, GIT_EXEC_PATH and PREFIX; a failed lookup is not stored; test pins one start across two scopes.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Any [include]/[includeIf] in the global config disabled the cache (true on the operator's host) (phase 1)

Fixed in 921f5d788: every include.path/includeIf.<cond>.path is followed (depth 10, ~/ and relative paths) and stat'd whatever its condition; <gitdir>/HEAD joins the fingerprint for onbranch:; only unresolvable paths, unparseable headers, depth overflow and env-passed includes decline. Tests cover includeIf gitdir, relative include, onbranch flip, cycles.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Race guard's before-stamp omitted the branch named by refs/remotes/<remote>/HEAD (phase 1)

Fixed in 921f5d788: `git_cache.head_target` reads the loose HEAD symref's target before git runs and adds it to the before-stamp; test with a non-well-known `stable` ref removed mid-answer.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Invalidation tests never proved a cache hit before the mutation (phase 1)

Fixed in 921f5d788: each of the seven invalidation tests asks again before the change and asserts zero new git starts (`_hit` helper).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: Legacy GIT_CONFIG env file is read by git but not stat'd (phase 1)

Fixed in 921f5d788: `locate` returns None when GIT_CONFIG is set; test added.

<!-- fr:journal kind=finding scope=plan id=p1-call-count-target-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-call-count-target -->
### p1-call-count-target-resolved · finding [fixed] · resolves p1-call-count-target: Spec §3.A's ceiling of 500 git starts is out of R1's reach: the cache gets the profiled test to 611 (phase 1)

Settled with p1-r1: spec §3.A amended to the measured ceiling (≤604, 593 measured) with the reason; the test pins that figure.
