<!-- fr:journal-schema=3 -->
# Journal: 2026-10-23-release-ops-floor-tests

<!-- fr:journal kind=repro scope=debug id=55fddd698f07 created=2026-10-23T04:17:40+00:00 -->
### 55fddd698f07 · repro · release.yml run 39897787577 refused to cut v6.0.0-rc.3: staged suite red

release.py bumped 6.0.0rc2 -> 6.0.0rc3 and ran the whole suite on the staged tree. One failure: tests/unit/test_ops_artifacts.py::test_the_ops_floor_is_the_predicted_release, assert Version('6.0.0rc3') == Version('6.0.0rc4'). 1 failed, 13458 passed. main and tags untouched.

<!-- fr:journal kind=root-cause scope=debug id=eeb3983426ba created=2026-10-23T04:17:45+00:00 -->
### eeb3983426ba · root-cause · Both ops-floor tests encode a PR-time fact that the release itself falsifies

_predicted_release() reads packages/fr/pyproject.toml and assumes it is the LAST CUT release, predicting its successor. On a PR tree (6.0.0rc2) that gives rc3 == OPS_FR_FLOOR. On release.py's staged tree pyproject already says 6.0.0rc3 (the release being cut), so it predicts rc4: the release can never pass its own gate. Latent sibling: test_the_ops_floor_is_above_every_cut_release asserts floor > max(v* tags); once v6.0.0-rc.3 is tagged, rc3 > rc3 is false and every CI run (fetch-depth 0, tags present) goes red. The real invariant is about tag CONTENTS: the floor is the first release that ships packages/fr/src/fr/ops.

<!-- fr:journal kind=finding scope=debug id=release-ops-floor-tests created=2026-10-23T04:23:13+00:00 state=fixed -->
### release-ops-floor-tests · finding [fixed] · Ops-floor tests now hold across the release lifecycle

tests/unit/test_ops_artifacts.py: _first_ops_release(tree, cut) = oldest tag shipping fr/ops, else the tree when its version is uncut (release staging), else the next release. Failing test first: test_the_first_ops_release_holds_across_the_release_lifecycle went red on the staged / post-tag / post-final cases under the old prediction, green after. Replaced test_the_ops_floor_is_the_predicted_release and test_the_ops_floor_is_above_every_cut_release with test_the_ops_floor_is_the_first_release_that_ships_ops and test_the_ops_floor_excludes_every_release_without_ops (classifies every tag by content). Verified against the real repo with pyproject at 6.0.0rc3 (staged) and with a temporary local v6.0.0-rc.3 tag: both pass. Test-only, so no change fragment; OPS_FR_FLOOR stays 6.0.0rc3, which was never cut.

<!-- fr:journal kind=review scope=debug id=becee0e82874 created=2026-10-23T04:24:20+00:00 -->
### becee0e82874 · review · Self-review: one finding raised and fixed

Raised: _cut_releases spawned one git cat-file per tag (271 tags, ~13s, called by two tests), fixed with a single --batch-check (2s). Checked and clean: lightweight and annotated tags both peel for tag:path; shallow checkouts with no tags still skip; no acceptance-matrix row anchors on the renamed tests (only append-only journals name them); the parametrized admits test still pins rc3 as the floor. Test-only diff, so no change fragment. The full suite was not run locally; CI runs it.
