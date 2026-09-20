# Journal: 2026-09-20-journal-require-reviews

<!-- fr:journal kind=discovery scope=plan id=nrb-p4t1 created=2026-09-20T15:18:40 phase=4 -->
### nrb-p4t1 · discovery · no-refactor-because P4.T1 (phase 4)

P4.T1 edits three SKILL.md prose files. There is no red-green cycle to refactor from: the unit of work is sentences, and the 'refactor' of prose is rewriting the same sentences, which the step already instructs (keep the compressed voice, do not grow the section by more than a couple of lines). The mechanical follow-up that IS separable — regenerating the OpenCode mirrors and running their tripwires — is its own task, P4.T2, rather than a refactor step pretending to be one.

<!-- fr:journal kind=discovery scope=plan id=nrb-p5t2 created=2026-09-20T15:18:40 phase=5 -->
### nrb-p5t2 · discovery · no-refactor-because P5.T2 (phase 5)

P5.T2 writes explainer prose and regenerates the published page with an externally-owned renderer. The .html is generated and must never be hand-edited, so there is nothing in the output to refactor; the .md's quality pass is the writing step itself. The verification that would normally be a refactor step's job is instead P5.T1.S1, which runs BEFORE the prose is written — byte-identical re-render of the unmodified page — because that ordering is what makes the later diff readable.

<!-- fr:journal kind=discovery scope=plan id=nrb-p6t2 created=2026-09-20T15:18:44 phase=6 -->
### nrb-p6t2 · discovery · no-refactor-because P6.T2 (phase 6)

P6.T2 is bumped 4.8.0 -> 4.9.0 in 9 files
running `uv sync`...
`fr --version` -> fr 4.9.0 plus 33 artifact(s) checked — all structurally valid.. Both are single deterministic commands over generated manifests; the script owns the edit and hand-editing the version-bearing surfaces is explicitly forbidden by AGENTS.md. There is no authored code here to clean up. The phase's quality pass is P6.T3, the full CI gate.

<!-- fr:journal kind=discovery scope=plan id=pre-existing-bump created=2026-09-20T15:19:51 phase=6 -->
### pre-existing-bump · discovery · The worktree already carried an uncommitted 4.8.0 to 4.9.0 bump, provenance not this session (phase 6)

Found while running plan self-review, which rebuilt the venv and installed fr==4.9.0 while origin/main is 4.8.0.

The worktree (~/.cache/fr/worktrees/super-fr/feat__journal-require-reviews) was created at 12:54 today and reset to eb85d91; this session began at 15:10. So an earlier session on this same branch ran the bump and left it uncommitted.

Verified it is version-ONLY: the diff over .claude-plugin/marketplace.json, packages/*/pyproject.toml, packages/fr-opencode-plugin/package.json, plugins/*/.claude-plugin/plugin.json and the workspace-root pyproject.toml is exactly five `version = "4.9.0"` lines and five JSON version keys, nothing else. That is byte-equivalent to what `scripts/bump-version.py minor` produces from 4.8.0, which is the bump this PR owes anyway.

Decision: ADOPT it rather than reset-and-redo. Resetting would discard uncommitted work of unknown provenance to reproduce an identical result. P6.T2.S1 is amended to VERIFY the bump (diff is version-only, `bump-version.py --check` passes, `uv run fr --version` reads 4.9.0) and commit it, rather than bumping again — which from a dirty 4.9.0 tree would land 4.10.0 and overshoot.

<!-- fr:journal kind=discovery scope=plan id=d864d12dd9ad created=2026-09-20T15:24:53 phase=1 -->
### d864d12dd9ad · discovery · Phase-1 smoke baseline: --require-reviews rides the existing open-findings rule, exit 1 (phase 1)

Ran the real binary against this repo's own live plan
docs/superpowers/plans/2026-09-04-worktree-traceability, both by --plan-dir
(no --slug) and by --slug (no --plan-dir):

  uv run fr journal check --scope plan --plan-dir docs/superpowers/plans/2026-09-04-worktree-traceability --require-reviews
  uv run fr journal check --scope plan --slug 2026-09-04-worktree-traceability --require-reviews

Both resolve to the same journal and agree byte-for-byte:
"4 open finding(s): d028f3cc945a, a309fda69e5a, 9ecae0965ac4, a3228f0cb118",
exit=1. Phase 2 has not built the review-owed/present gate yet, so
--require-reviews is currently pure plumbing: it changes nothing about what
check does — the plan's pre-existing open findings are what fail it, exactly
as they would without the flag. This is the baseline phase-2 tests are
measured against: once the gate lands, this same command's failure reason
must still include these findings (existing rule keeps firing) but may also
gain phase-owed-review lines, or, if this plan's findings get resolved before
phase 2 lands, may exit 0 purely on the new gate's say-so.

<!-- fr:journal kind=discovery scope=plan id=576256bf712f created=2026-09-20T15:30:28 phase=1 -->
### 576256bf712f · discovery · Full-suite gate: 2 more pre-existing environment-dependent failures beyond the documented workflow_check one (phase 1)

uv run pytest -q --no-cov on this branch: 3296 passed, 80 skipped, 3 failed.
One is the dispatch brief's known-tolerated red
(test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable,
#463/#489). The other two are NOT caused by this phase:

  tests/unit/test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused
  tests/unit/test_run_workspace.py::test_an_external_marker_without_container_evidence_is_refused

Both assert a substring of an error message ("not a linked git worktree",
"container evidence") that Rich has line-wrapped mid-phrase because this
machine's pytest tmp_path is long enough to push the wrap point into the
asserted words — the exact macOS-tmp_path-length failure class already
recorded independently in
docs/superpowers/implemented/journals/plans/2026-09-19-gitlab-contents-ref-and-self-hosted-hosts.md.
Confirmed unrelated to any diff in this worktree: `git diff --stat HEAD --
tests/unit/test_run_workspace.py packages/fr/src/fr/commands/run_cmd.py` is
empty, and running just these two tests in isolation reproduces the same
failure with the same wrap point. Not fixed here (out of phase-1 scope; no
file touched by this phase is anywhere near isolation-marker validation).
