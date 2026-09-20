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
