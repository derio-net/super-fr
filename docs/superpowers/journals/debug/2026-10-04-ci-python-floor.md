# Journal: 2026-10-04-ci-python-floor

<!-- fr:journal kind=repro scope=debug id=a231597d91ef created=2026-10-04T06:34:01+00:00 -->
### a231597d91ef · repro · CI tests the runner's Python, not the 3.11 floor; CI runs twice per PR push

#940: no workflow pins an interpreter (no .python-version, no UV_PYTHON, no setup-uv python-version), so `uv sync` resolves the first Python satisfying requires-python >=3.11 — ubuntu-latest's /usr/bin/python3 3.12.3. #929 passed locally on 3.14 and failed in CI on a 3.13+ API; nothing anywhere ran 3.11. #941: ci.yml is `on: [push, pull_request]`, so one push to a PR branch fires both events and every check appears twice (seen on #920). acceptance-report.yml has the same shape (`push: branches: ['**']` + `pull_request`).

<!-- fr:journal kind=root-cause scope=debug id=aac6785734fc created=2026-10-04T06:34:04+00:00 -->
### aac6785734fc · root-cause · Workflow config: unpinned interpreter + push trigger not scoped to main

Two mechanical causes in the same workflow files, batched deliberately by the operator (same file, shared CI-load motive) rather than one shared cause: (1) the absence of an interpreter pin lets uv choose the runner Python; (2) an unfiltered `push` trigger overlaps `pull_request` on every PR branch. No source code is involved.
