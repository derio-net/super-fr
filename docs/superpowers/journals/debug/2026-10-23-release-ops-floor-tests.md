<!-- fr:journal-schema=3 -->
# Journal: 2026-10-23-release-ops-floor-tests

<!-- fr:journal kind=repro scope=debug id=55fddd698f07 created=2026-10-23T04:17:40+00:00 -->
### 55fddd698f07 · repro · release.yml run 39897787577 refused to cut v6.0.0-rc.3: staged suite red

release.py bumped 6.0.0rc2 -> 6.0.0rc3 and ran the whole suite on the staged tree. One failure: tests/unit/test_ops_artifacts.py::test_the_ops_floor_is_the_predicted_release, assert Version('6.0.0rc3') == Version('6.0.0rc4'). 1 failed, 13458 passed. main and tags untouched.
