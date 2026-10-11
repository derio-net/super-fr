"""`scripts/configure-main-protection.sh` (spec 2026-10-11-merge-train-safety §F, R17).

The script is run with a stub `gh` on PATH. The stub records every call, serves a
canned ruleset, installations list, tags and Actions runs from files in a sandbox
directory, and applies a PUT to the served ruleset so a second run sees the first.
Nothing here touches a real repo.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "configure-main-protection.sh"
APP_ID = 424242
SHA = "a" * 40

STUB = r"""#!/usr/bin/env bash
d="$STUB_DIR"
echo "$*" >> "$d/calls.log"
case "$*" in
  "api repos/o/r/rulesets") cat "$d/rulesets.json" ;;
  "api repos/o/r/rulesets/7") cat "$d/ruleset.json" ;;
  "api orgs/o/installations") cat "$d/installations.json" ;;
  "api repos/o/r/tags?per_page=100") cat "$d/tags.json" ;;
  "api repos/o/r/actions/runs?head_sha=$STUB_SHA&event=push") cat "$d/runs.json" ;;
  "api -X PUT repos/o/r/rulesets/7 --input -")
    cat > "$d/ruleset.json"; cp "$d/ruleset.json" "$d/put.json" ;;
  "variable list "*)
    jq -r '.[] | select(.name == "FR_AUTOMATION_APP_ID") | .value' "$d/variables.json" ;;
  "variable set "*) echo "$*" >> "$d/var_set.log" ;;
  *) echo "stub gh: unexpected call: $*" >&2; exit 99 ;;
esac
"""

BASE_RULESET = {
    "id": 7,
    "name": "protect main",
    "target": "branch",
    "enforcement": "active",
    "source": "o/r",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    "bypass_actors": [],
}


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    d = tmp_path / "stub"
    d.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(STUB)
    (bin_dir / "gh").chmod(0o755)
    (d / "rulesets.json").write_text(json.dumps([{"id": 7, "name": "protect main"}]))
    (d / "ruleset.json").write_text(json.dumps(BASE_RULESET))
    (d / "installations.json").write_text(
        json.dumps(
            {
                "installations": [
                    {"app_id": 1, "app_slug": "other"},
                    {"app_id": APP_ID, "app_slug": "derio-fr-automation"},
                ]
            }
        )
    )
    (d / "tags.json").write_text(
        json.dumps(
            [
                {"name": "v5.9.0", "commit": {"sha": "b" * 40}},
                {"name": "v5.21.0", "commit": {"sha": SHA}},
            ]
        )
    )
    (d / "runs.json").write_text(
        json.dumps({"workflow_runs": [{"triggering_actor": {"login": "derio-fr-automation[bot]"}}]})
    )
    (d / "variables.json").write_text("[]")
    return tmp_path


def _run(sandbox: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{sandbox / 'bin'}:{os.environ['PATH']}",
        "STUB_DIR": str(sandbox / "stub"),
        "STUB_SHA": SHA,
        "HOME": str(sandbox),
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "--repo", "o/r", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _put(sandbox: Path) -> dict:
    return json.loads((sandbox / "stub" / "put.json").read_text())


def _calls(sandbox: Path) -> list[str]:
    return (sandbox / "stub" / "calls.log").read_text().splitlines()


def _grant_bypass(sandbox: Path) -> None:
    rs = dict(BASE_RULESET)
    rs["bypass_actors"] = [
        {"actor_id": APP_ID, "actor_type": "Integration", "bypass_mode": "always"}
    ]
    (sandbox / "stub" / "ruleset.json").write_text(json.dumps(rs))


def test_the_script_is_executable_and_shellchecks() -> None:
    assert os.access(SCRIPT, os.X_OK)
    if shutil.which("shellcheck"):
        r = subprocess.run(["shellcheck", str(SCRIPT)], capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stdout


def test_bypass_merges_the_actor_into_the_existing_rules_and_sets_the_variable(
    sandbox: Path,
) -> None:
    r = _run(sandbox, "--stage", "bypass")
    assert r.returncode == 0, r.stderr
    body = _put(sandbox)
    assert body["bypass_actors"] == [
        {"actor_id": APP_ID, "actor_type": "Integration", "bypass_mode": "always"}
    ]
    assert [x["type"] for x in body["rules"]] == ["deletion", "non_fast_forward"]
    assert body["name"] == "protect main" and "id" not in body and "source" not in body
    assert (
        f"variable set FR_AUTOMATION_APP_ID --body {APP_ID} --repo o/r"
        in (sandbox / "stub" / "var_set.log").read_text()
    )


def test_bypass_keeps_an_actor_already_in_the_list(sandbox: Path) -> None:
    rs = dict(BASE_RULESET)
    rs["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
    (sandbox / "stub" / "ruleset.json").write_text(json.dumps(rs))
    assert _run(sandbox, "--stage", "bypass").returncode == 0
    ids = [a["actor_id"] for a in _put(sandbox)["bypass_actors"]]
    assert ids == [5, APP_ID]


def test_bypass_rerun_is_a_no_op(sandbox: Path) -> None:
    assert _run(sandbox, "--stage", "bypass").returncode == 0
    (sandbox / "stub" / "variables.json").write_text(
        json.dumps([{"name": "FR_AUTOMATION_APP_ID", "value": str(APP_ID)}])
    )
    (sandbox / "stub" / "calls.log").write_text("")
    (sandbox / "stub" / "var_set.log").unlink()
    r = _run(sandbox, "--stage", "bypass")
    assert r.returncode == 0, r.stderr
    assert "nothing to change" in r.stdout
    assert not any("-X PUT" in c for c in _calls(sandbox))
    assert not (sandbox / "stub" / "var_set.log").exists()


def test_require_refuses_without_the_bypass_actor(sandbox: Path) -> None:
    r = _run(sandbox, "--stage", "require", "--force")
    assert r.returncode == 1
    assert "--stage bypass first" in r.stderr
    assert not (sandbox / "stub" / "put.json").exists()


def test_require_refuses_when_the_newest_release_was_not_pushed_by_the_app(sandbox: Path) -> None:
    _grant_bypass(sandbox)
    (sandbox / "stub" / "runs.json").write_text(json.dumps({"workflow_runs": []}))
    r = _run(sandbox, "--stage", "require")
    assert r.returncode == 1
    assert "v5.21.0" in r.stderr and "not pushed by the app" in r.stderr
    assert not (sandbox / "stub" / "put.json").exists()


def test_require_refuses_a_run_triggered_by_someone_else(sandbox: Path) -> None:
    _grant_bypass(sandbox)
    (sandbox / "stub" / "runs.json").write_text(
        json.dumps({"workflow_runs": [{"triggering_actor": {"login": "someone"}}]})
    )
    assert _run(sandbox, "--stage", "require").returncode == 1


def test_require_adds_the_strict_ci_ok_check_and_keeps_every_other_rule(sandbox: Path) -> None:
    _grant_bypass(sandbox)
    r = _run(sandbox, "--stage", "require")
    assert r.returncode == 0, r.stderr
    body = _put(sandbox)
    assert [x["type"] for x in body["rules"]] == [
        "deletion",
        "non_fast_forward",
        "required_status_checks",
    ]
    params = body["rules"][2]["parameters"]
    assert params["strict_required_status_checks_policy"] is True
    assert params["required_status_checks"] == [{"context": "ci-ok"}]
    assert body["bypass_actors"][0]["actor_id"] == APP_ID
    # The newest tag was chosen by version, not by listing order.
    assert any(f"head_sha={SHA}" in c for c in _calls(sandbox))


def test_require_rerun_is_a_no_op(sandbox: Path) -> None:
    _grant_bypass(sandbox)
    assert _run(sandbox, "--stage", "require").returncode == 0
    (sandbox / "stub" / "calls.log").write_text("")
    r = _run(sandbox, "--stage", "require")
    assert r.returncode == 0, r.stderr
    assert "nothing to change" in r.stdout
    assert not any("-X PUT" in c for c in _calls(sandbox))


def test_force_skips_only_the_release_check(sandbox: Path) -> None:
    _grant_bypass(sandbox)
    (sandbox / "stub" / "runs.json").write_text(json.dumps({"workflow_runs": []}))
    r = _run(sandbox, "--stage", "require", "--force")
    assert r.returncode == 0, r.stderr
    assert not any("actions/runs" in c for c in _calls(sandbox))
    assert "required_status_checks" in [x["type"] for x in _put(sandbox)["rules"]]


def test_dry_run_prints_the_body_and_writes_nothing(sandbox: Path) -> None:
    r = _run(sandbox, "--stage", "bypass", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["bypass_actors"][0]["actor_id"] == APP_ID
    assert not (sandbox / "stub" / "put.json").exists()
    assert not (sandbox / "stub" / "var_set.log").exists()


def test_a_missing_ruleset_or_app_is_refused(sandbox: Path) -> None:
    (sandbox / "stub" / "rulesets.json").write_text("[]")
    assert _run(sandbox, "--stage", "bypass").returncode == 1
    (sandbox / "stub" / "rulesets.json").write_text(json.dumps([{"id": 7, "name": "protect main"}]))
    (sandbox / "stub" / "installations.json").write_text(json.dumps({"installations": []}))
    assert _run(sandbox, "--stage", "bypass").returncode == 1


def test_bad_arguments_exit_two(sandbox: Path) -> None:
    assert _run(sandbox).returncode == 2
    assert _run(sandbox, "--stage", "nope").returncode == 2
