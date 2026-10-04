# Journal: 2026-10-04-ci-python-floor

<!-- fr:journal kind=repro scope=debug id=a231597d91ef created=2026-10-04T06:34:01+00:00 -->
### a231597d91ef · repro · CI tests the runner's Python, not the 3.11 floor; CI runs twice per PR push

#940: no workflow pins an interpreter (no .python-version, no UV_PYTHON, no setup-uv python-version), so `uv sync` resolves the first Python satisfying requires-python >=3.11 — ubuntu-latest's /usr/bin/python3 3.12.3. #929 passed locally on 3.14 and failed in CI on a 3.13+ API; nothing anywhere ran 3.11. #941: ci.yml is `on: [push, pull_request]`, so one push to a PR branch fires both events and every check appears twice (seen on #920). acceptance-report.yml has the same shape (`push: branches: ['**']` + `pull_request`).

<!-- fr:journal kind=root-cause scope=debug id=aac6785734fc created=2026-10-04T06:34:04+00:00 -->
### aac6785734fc · root-cause · Workflow config: unpinned interpreter + push trigger not scoped to main

Two mechanical causes in the same workflow files, batched deliberately by the operator (same file, shared CI-load motive) rather than one shared cause: (1) the absence of an interpreter pin lets uv choose the runner Python; (2) an unfiltered `push` trigger overlaps `pull_request` on every PR branch. No source code is involved.

<!-- fr:journal kind=finding scope=debug id=ci-floor-and-trigger created=2026-10-04T06:54:25+00:00 state=fixed -->
### ci-floor-and-trigger · finding [fixed] · CI pins UV_PYTHON=3.11, tests 3.11+3.14, triggers push on main only

ci.yml + release.yml: workflow-level UV_PYTHON=3.11 (an env var, not .python-version, so operators' local runs stay unpinned). ci.yml test matrix gains python: [3.11, 3.14] with job env UV_PYTHON=${{ matrix.python }}; only the 3.11 leg uploads coverage. ci.yml and acceptance-report.yml: push scoped to main. Pinned by tests/unit/test_ci_python_floor.py (5 tests, red before, green after; floor read from requires-python). Full suite run locally on 3.11.15: 8154 passed — the one failure was mirror drift from editing acceptance-matrix.md mid-run, fixed by sync-opencode.py.

<!-- fr:journal kind=review scope=debug id=08972d833f08 created=2026-10-04T06:54:30+00:00 -->
### 08972d833f08 · review · Self-review: no defects; check-context names change

Reviewed the branch diff plus actionlint (clean). Noted, not a defect: test check contexts rename from 'test (N)' to 'test (py3.11, N)' / 'test (py3.14, N)'; main's ruleset requires no status checks and ci-ok is the stable aggregate (#706), so nothing keys on the old names. Not changed (out of scope): the scaffolded consumer acceptance-report template (fr acceptance init) and fr-spec-status.yml's setup-python 3.12 (reusable workflow, not uv-driven).
