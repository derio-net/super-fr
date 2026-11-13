<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-placement-plan-paths

<!-- fr:journal kind=repro scope=debug id=repro-self-review created=2026-11-13T22:16:27+00:00 -->
### repro-self-review · repro · quiet: plan self-review refuses a plan whose rows cite its spec logically; plan create stores an absolute spec

Scratch quiet fixture (settings init --quiet, isolation up feat/q, fr-goal-light run, spec below FR_SPECS_DIR, row l-hello origin spec:2026-11-13-l#R1 added by the brainstorm record): fr plan create --spec $FR_SPECS_DIR/2026-11-13-l-design.md writes _meta.yaml spec: <absolute path>; fr plan self-review then errors: 'phase 1 links unknown acceptance row id l-hello (no fragment ...)', 'spec ## Verification: ... no matrix row citing the spec has', 'phase 1 serves no ask ... features/feat__q/docs/superpowers/specs/...', and the candidate-install check looks at <fr worktree>/.fr/candidate-install instead of the product checkout. Same as the live walk.

<!-- fr:journal kind=root-cause scope=debug id=rc-plan-root created=2026-11-13T22:16:49+00:00 -->
### rc-plan-root · root-cause · Plan.repo_root is the fr worktree (or tracking clone) under quiet/stealth, and Plan.spec_path is relative to it

fr.parser.parse sets repo_root to the git toplevel of the plan dir. Under quiet that is the fr worktree, whose space_for has feature=None, so every reader handed plan.repo_root as 'the checkout' (load_effective/has_fragments, journal_path, workflow_for_plan, .fr/ repo config, candidate-install) reads <fr worktree>/docs/... or <fr worktree>/.fr/..., which never exist. spec_path = res.path.relative_to(repo_root) gives features/<id>/docs/superpowers/specs/x.md, which no logical origin matches (origin_fragment requires a spec dir prefix) and which differs from the run cursor's artifact-root-relative convention (#1435). Separately refs.keeps_spec_ref_verbatim judges 'escapes the repo' against the product checkout only, so an absolute $FR_SPECS_DIR path is kept verbatim in _meta.yaml.

<!-- fr:journal kind=root-cause scope=debug id=rc-deliver-heads created=2026-11-13T22:32:39+00:00 -->
### rc-deliver-heads · root-cause · deliver's proportionality and the commit lines read the product HEAD for artifacts that live on fr

proportionality._phases_at_head/_meta_at_head/_spec_at_head and the journal reads took the plan path relative to the product checkout (ValueError: not in the subpath) and read 'HEAD:' there; under quiet/stealth the plan, spec and journals are committed in the fr worktree or tracking clone. Its Phases section also folded acceptance at the product HEAD, which holds no fragment (R23). record/apply's one-line sha and run_cmd's 'cursor committed as <sha>' named the product HEAD, not the commit fr made.
