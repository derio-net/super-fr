#!/usr/bin/env bash
# Rows acceptance-local-status-listed, acceptance-local-earned, acceptance-local-stale
# (spec 2026-11-14-acceptance-local-status R1-R3, R5, R9): in a repo that declares no
# CI, `local` is refused for a row with no level ref and written with one; stamped as
# `deliver` would stamp it, `fr acceptance status` and `fr debt` list it as `local`, not
# debt; once its test file changes `fr acceptance check` reports it `local, stale`, a
# `local` row with no stamp is `local, unstamped`, and once the repo declares CI `local`
# is refused. The fixture is a fresh `git init` with no remote and no forge.
# Portable: no GNU-only flags (BSD/macOS and GNU userlands alike).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

scenario_require_fresh_repo
git symbolic-ref HEAD refs/heads/main || fail "name the default branch main"
mkdir -p .devcontainer tests docs/acceptance/features
cat > .devcontainer/fr-profiles.yaml <<'YAML'
profiles:
  dev:
    purpose: scenario
schema_version: 2
ci: {type: none}
YAML
cat > tests/test_x.py <<'PY'
def test_y():
    assert True
PY
cat > docs/acceptance/features/2026-01-01-alpha.yaml <<'YAML'
schema_version: 2
feature: 2026-01-01-alpha
repo: acme/widget
rows:
  - id: earned
    capability: Widget
    acceptance: earned works
    origin:
    - widget:README.md
    status: not-implemented
    notes: owed
  - id: bare
    capability: Widget
    acceptance: bare works
    origin:
    - widget:README.md
    status: not-implemented
    notes: owed
  - id: later
    capability: Widget
    acceptance: later works
    origin:
    - widget:README.md
    status: not-implemented
    notes: owed
YAML
printf '# widget\n' > README.md
git add -A && git commit -qm "feat: alpha" || fail "seed commit"

# R2: no level ref, refused, nothing written.
before="$(cat docs/acceptance/features/2026-01-01-alpha.yaml)"
run_fr out acceptance set-status --id earned --status local --notes "a local test"
require_exit 2 "$out"
expect_grep 'status local needs a level ref' "$out" "local with no level ref is refused"
[ "$(cat docs/acceptance/features/2026-01-01-alpha.yaml)" = "$before" ] || fail "a refusal changed the fragment"

# With the level ref, written.
run_fr out acceptance set-status --id earned --status local \
  --level unit=widget:tests/test_x.py#test_y --notes "tests/test_x.py::test_y verifies it"
require_exit 0 "$out"
expect_grep 'status: local' "$(cat docs/acceptance/features/2026-01-01-alpha.yaml)" "the row is local"
git add -A && git commit -qm "local" >/dev/null 2>&1 || true

# The stamp, written as `deliver` writes it (fr.acceptance.edit.stamp_local).
py="$(candidate_python)"
"$py" - <<'PY' || fail "stamp the row"
import subprocess
from pathlib import Path
from fr.acceptance.edit import stamp_local
from fr.acceptance.model import LocalStamp

blob = subprocess.run(["git", "rev-parse", "HEAD:tests/test_x.py"], capture_output=True,
                      text=True, check=True).stdout.strip()
path = Path("docs/acceptance/features/2026-01-01-alpha.yaml")
stamp = LocalStamp(at="2026-11-14", tree="0" * 64, log="suite.log@0123456789ab",
                   files={"tests/test_x.py": blob})
path.write_text(stamp_local(path.read_text(), "earned", stamp))
PY
git add -A && git commit -qm "deliver: stamp" || fail "commit the stamp"

# R1: listed as local with its stamp date, never debt.
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'earned \[local 2026-11-14\]' "$out" "status lists the fresh local row"
refuse_grep 'earned \[local,' "$out" "a fresh local row is not debt"
run_fr out debt --offline
require_exit 0 "$out"
expect_grep 'earned \[local 2026-11-14\]' "$out" "debt lists the fresh local row as local"
refuse_grep 'earned \[local,' "$out" "debt does not count a fresh local row"
run_fr out acceptance check
require_exit 0 "$out"
refuse_grep 'earned' "$out" "check reports nothing for a fresh local row"

# R5: the test file changes, the row is stale.
printf 'def test_y():\n    assert 1 == 1\n' > tests/test_x.py
git add -A && git commit -qm "test: edit" || fail "commit the test edit"
run_fr out acceptance check
require_exit 0 "$out"
expect_grep 'earned.*local, stale: tests/test_x.py' "$out" "check reports the stale row"
run_fr out acceptance status
expect_grep 'earned \[local, stale: tests/test_x.py\]' "$out" "status shows the stale row as debt"
run_fr out debt --offline
require_exit 0 "$out"
expect_grep 'earned \[local, stale: tests/test_x.py\]' "$out" "debt counts the stale row"
refuse_grep 'earned \[local 2026' "$out" "debt no longer lists the stale row as fresh"

# R5: a local row with no stamp is debt.
run_fr out acceptance set-status --id bare --status local \
  --level unit=widget:tests/test_x.py#test_y --notes "tests/test_x.py::test_y verifies it"
require_exit 0 "$out"
git add -A && git commit -qm "bare local" >/dev/null 2>&1 || true
run_fr out acceptance check
require_exit 0 "$out"
expect_grep 'bare.*local, unstamped' "$out" "check reports the unstamped row"

# R3: once the repo declares CI, local is refused.
sed 's/ci: {type: none}/ci: {type: github-actions}/' .devcontainer/fr-profiles.yaml > profiles.tmp \
  && mv profiles.tmp .devcontainer/fr-profiles.yaml || fail "declare CI"
git add -A && git commit -qm "ci" || fail "commit the CI declaration"
run_fr out acceptance set-status --id later --status local \
  --level unit=widget:tests/test_x.py#test_y --notes "tests/test_x.py::test_y verifies it"
require_exit 2 "$out"
expect_grep 'status local is for a repo with no CI' "$out" "local is refused with CI"
echo "ok: acceptance-local-status"
