<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-placement-plan-paths

<!-- fr:journal kind=repro scope=debug id=repro-self-review created=2026-11-13T22:16:27+00:00 -->
### repro-self-review · repro · quiet: plan self-review refuses a plan whose rows cite its spec logically; plan create stores an absolute spec

Scratch quiet fixture (settings init --quiet, isolation up feat/q, fr-goal-light run, spec below FR_SPECS_DIR, row l-hello origin spec:2026-11-13-l#R1 added by the brainstorm record): fr plan create --spec $FR_SPECS_DIR/2026-11-13-l-design.md writes _meta.yaml spec: <absolute path>; fr plan self-review then errors: 'phase 1 links unknown acceptance row id l-hello (no fragment ...)', 'spec ## Verification: ... no matrix row citing the spec has', 'phase 1 serves no ask ... features/feat__q/docs/superpowers/specs/...', and the candidate-install check looks at <fr worktree>/.fr/candidate-install instead of the product checkout. Same as the live walk.
