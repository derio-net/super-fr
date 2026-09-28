"""`fr services` — the resolved forge / ci / tracking services (spec
2026-09-28-fr-profiles-services §3.F, R7)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

V1_GITLAB = """\
backend: gitlab
host: gitlab.example.com
profiles:
  dev:
    purpose: x
    secrets: []
default: dev
"""


def _repo(tmp_path: Path, *, remote: str, profiles: str | None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    if profiles is not None:
        (repo / ".devcontainer").mkdir()
        (repo / ".devcontainer" / "fr-profiles.yaml").write_text(profiles)
    return repo


def _invoke(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["services", *args])
    return result.exit_code, result.output


def test_services_json_reports_the_forge_of_a_flat_v1_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, remote="https://gitlab.com/example-org/demo.git", profiles=V1_GITLAB)
    code, out = _invoke(repo, monkeypatch, "--json")
    assert code == 0, out
    data = json.loads(out)
    assert data["forge"] == {"type": "gitlab", "host": "gitlab.example.com", "source": "legacy"}


V2 = """\
schema_version: 2
profiles:
  dev:
    purpose: x
default: dev
forge:
  type: gitlab
  host: gitlab.example.com
ci:
  type: none
"""


def test_plain_output_lists_each_service_with_type_host_and_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, remote="https://gitlab.com/example-org/demo.git", profiles=V2)
    code, out = _invoke(repo, monkeypatch)
    assert code == 0, out
    rows = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
    assert rows["forge"] == ["gitlab", "gitlab.example.com", "declared"]
    assert rows["ci"] == ["none", "—", "declared"]
    assert rows["tracking"][:3] == ["gitlab", "gitlab.example.com", "default"]
    assert "forge's own" in " ".join(rows["tracking"])


def test_json_is_keyed_by_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, remote="https://gitlab.com/example-org/demo.git", profiles=V2)
    code, out = _invoke(repo, monkeypatch, "--json")
    assert code == 0, out
    assert json.loads(out) == {
        "forge": {"type": "gitlab", "host": "gitlab.example.com", "source": "declared"},
        "ci": {"type": "none", "host": None, "source": "declared"},
        "tracking": {"type": "gitlab", "host": "gitlab.example.com", "source": "default"},
    }


def test_a_deferred_type_exits_2_naming_the_follow_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(
        tmp_path,
        remote="https://gitlab.com/example-org/demo.git",
        profiles="forge: {type: gitlab}\nci: {type: jenkins}\nprofiles: {}\n",
    )
    code, out = _invoke(repo, monkeypatch)
    assert code == 2
    assert "derio-net/super-fr#795" in out
