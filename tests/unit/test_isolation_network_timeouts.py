"""`_run_network` takes an optional cwd and stays bounded (isolation timeouts)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fr.isolation.local import LocalWorktreeDevcontainerTarget

from tests.unit.test_isolation import make_repo


class _Recorder:
    def __init__(self) -> None:
        self.cwds: list[Path | None] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(
        self,
        argv: list[str],
        cwd: Path | None = None,
        check: bool = False,
        capture: bool = True,
        **kw: Any,
    ) -> subprocess.CompletedProcess[str]:
        self.cwds.append(cwd)
        self.kwargs.append(kw)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


def test_run_network_uses_given_cwd_and_a_timeout(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    rec = _Recorder()
    target = LocalWorktreeDevcontainerTarget(repo, runner=rec)
    target._run_network(["git", "status"], cwd=other)
    assert rec.cwds == [other]
    assert rec.kwargs[0]["timeout"] > 0


def test_run_network_defaults_to_repo_root(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    rec = _Recorder()
    target = LocalWorktreeDevcontainerTarget(repo, runner=rec)
    target._run_network(["git", "status"])
    assert rec.cwds == [target.repo_root]
    assert rec.kwargs[0]["timeout"] > 0
