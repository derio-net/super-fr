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
