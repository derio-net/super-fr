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

<!-- fr:journal kind=root-cause scope=debug id=rc-closeout created=2026-11-13T22:32:40+00:00 -->
### rc-closeout · root-cause · close-out from the base clone cannot find a quiet feature's run, reads its spec from the product checkout, and prints repo-placement steps

deliver prints 'fr pickup --run <id>' for the base clone; under quiet the base clone's own feature is its default branch (features/main), so the run is 'never started here'. closeout_brief read spec_file = repo_root / spec_path (silently dropping the Test Plan steps). The brief told the operator to bring up a chore workspace, git add/commit/push and open a housekeeping PR, while under quiet/stealth fr archive --branch records the merge on the placement branch and pushes it, moving nothing (R25). fr archive --issues is silently ignored under quiet (archive returns after the merged record): not fixed here, the brief no longer offers it.

<!-- fr:journal kind=decision scope=debug id=d-origin-fix created=2026-11-13T22:32:42+00:00 -->
### d-origin-fix · decision · a pending row's origin is correctable: amend --op reword --origin, in place, never as an amendment

Defect, not by design: add creates only, set-status moves status/evidence, no amendment op carries origin, and hand-editing a fragment is forbidden. A merged row's origins are history, so --origin is refused for a merged row and for any op but reword. Carried by RecordTarget.acceptance_origins (verb-only, like acceptance_drops), so the record kind's shape does not change. A corrected origin naming another spec moves the row to that spec's fragment (R16 ownership); an emptied fragment is removed.

<!-- fr:journal kind=finding scope=debug id=fix-plan-paths created=2026-11-13T23:25:30+00:00 state=fixed -->
### fix-plan-paths · finding [fixed] · plans belong to their product checkout; deliver, close-out and the staleness guard read artifacts where they live

Source: parser.parse sets Plan.repo_root to the product checkout (fr.artifacts.paths.product_checkout_for, each candidate confirmed by its own space) and Plan.spec_path relative to the plan's artifact root, with Plan.spec_file; plan_ops reads the spec through _plan_spec_file; refs.keeps_spec_ref_verbatim accepts an absolute path below a quiet/stealth artifact root; proportionality reads the plan, spec and journals at their own repo's HEAD and folds acceptance by placement; record/apply and run_cmd name the commit fr made; fr.run.closeout.run_checkout lets fr pickup --run and fr closeout outcome --run find a merged feature's run from the base clone; the brief reads the spec via emitted_path and gives quiet/stealth steps (stealth close-out from its workspace); acceptance check's staleness guard and the backfill inventory glob the feature's specs; ops gap/stub read the spec below the artifact root; fr acceptance amend --op reword --origin corrects a pending row. Tests first: tests/unit/test_placement_plan_paths.py (10, red before each fix), and placement-quiet.sh / placement-stealth.sh drive a fr-goal-light run and a two-phase fr-goal run through every step and close-out (tests/scenarios/_placement_walk.sh); placement-quiet.sh failed on 7.0.0rc4 at the absolute _meta spec.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-11-13T23:25:35+00:00 -->
### review-1 · review · independent review: data loss in the origin move fixed; product_checkout_for and proportionality callers checked

Reviewer (fresh context, given the code, not the conclusions). Raised: (1) serious: an origin correction deleted a fragment whose last row moved even when it held the feature's amendments: fixed, kept unless empty of rows and amendments, test added. (2) a None sentinel in texts would crash a later item of the same record: fixed, deletions tracked apart. (3) no refusal for a target fragment already holding the id: added. (4) product_checkout_for has no cache and walks recorded states per parse of a quiet/stealth plan: accepted (only off-product plans pay it); its fallback to the fr worktree leaves spec_path artifact-relative, which spec_file still resolves. (5) build_report callers pass the product checkout: checked. Not fixed, reported: fr archive --branch under quiet ignores --issues and the Test Plan outcome hold (the brief no longer claims either); the backfill inventory's uncited list ignores logical origins under every placement.
