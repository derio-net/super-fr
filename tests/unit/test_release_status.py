"""`fr release status` — R21 (spec 2026-10-14-exit-gates §G).

Every PR merged since the last FINAL tag (`^v\\d+\\.\\d+\\.\\d+$`; an RC tag never
counts) that still carries `gate:tester` or `gate:devops` without the matching
`gate:<g>-passed` waits, with its gate and owed rows. The forge is faked; the tags come
from a temp git repo, never this checkout.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.artifacts import trigger
from fr.cli import app
from fr.commands import release_cmd
from fr.release_status import (
    FINAL_TAG_RE,
    ReleaseStatus,
    Waiting,
    last_final_tag,
    release_status,
)
from typer.testing import CliRunner

REPO = "derio-net/super-fr"


class FakeForge:
    def __init__(self, prs: list[dict[str, Any]], labels: dict[int, list[str]]) -> None:
        self.prs = prs
        self.label_map = labels
        self.viewed: list[int] = []

    def merged_prs(self) -> list[dict[str, Any]]:
        return self.prs

    def labels(self, number: int) -> list[str]:
        self.viewed.append(number)
        return self.label_map[number]


def _pr(n: int, merged_at: str, branch: str = "") -> dict[str, Any]:
    return {
        "number": n,
        "title": f"PR {n}",
        "url": f"https://github.com/{REPO}/pull/{n}",
        "mergedAt": merged_at,
        "headRefName": branch or f"feat/{n}",
    }


# -- the pure engine -------------------------------------------------------------


def test_the_last_final_tag_ignores_rc_and_foreign_tags_and_orders_by_version() -> None:
    tags = ["v5.9.0", "v5.10.0", "v5.11.0-rc.1", "v5.11.0-rc.2", "vnext", "5.12.0", "v5.10.0x"]
    assert last_final_tag(tags) == "v5.10.0"
    assert last_final_tag(["v1.0.0-rc.1"]) is None
    assert last_final_tag([]) is None
    assert FINAL_TAG_RE.match("v1.2.3") and not FINAL_TAG_RE.match("v1.2.3-rc.1")


def test_only_prs_merged_since_the_last_final_with_an_unpassed_gate_wait() -> None:
    forge = FakeForge(
        [
            _pr(1, "2026-10-01T00:00:00Z"),  # before the tag: never read
            _pr(2, "2026-10-03T00:00:00Z"),  # gate:tester held
            _pr(3, "2026-10-03T01:00:00Z"),  # gate:tester passed
            _pr(4, "2026-10-03T02:00:00Z"),  # no gate
            _pr(5, "2026-10-03T03:00:00Z"),  # devops held, tester passed
            _pr(6, "2026-10-03T04:00:00Z"),  # gate:tests is pre-merge: never waits
        ],
        {
            1: ["gate:tester"],
            2: ["gate:tester", "verification:live"],
            3: ["gate:tester-passed"],
            4: [],
            5: ["gate:devops", "gate:tester-passed"],
            6: ["gate:tests"],
        },
    )
    status = release_status(
        repo=REPO,
        last_final="v5.26.0",
        since="2026-10-02T00:00:00+00:00",
        forge=forge,
        owed_rows=lambda branch: {"tester": ("row-a",)} if branch == "feat/2" else {},
    )

    assert [w.number for w in status.waiting] == [2, 5]
    assert status.waiting[0].gates == ("tester",)
    assert status.waiting[0].owed_rows == {"tester": ("row-a",)}
    assert status.waiting[1].gates == ("devops",)
    assert status.waiting[1].owed_rows == {"devops": ()}
    assert 1 not in forge.viewed


def test_with_no_final_tag_every_merged_pr_counts() -> None:
    forge = FakeForge([_pr(1, "2020-01-01T00:00:00Z")], {1: ["gate:devops"]})
    status = release_status(
        repo=REPO, last_final=None, since=None, forge=forge, owed_rows=lambda b: None
    )
    assert [w.number for w in status.waiting] == [1]
    assert status.waiting[0].owed_rows is None  # unreadable rows say so, never "none owed"


def test_the_json_shape_is_pinned() -> None:
    status = ReleaseStatus(
        repo=REPO,
        last_final="v5.26.0",
        since="2026-10-02T00:00:00+00:00",
        waiting=(
            Waiting(
                number=2,
                title="PR 2",
                url="u",
                merged_at="2026-10-03T00:00:00Z",
                gates=("tester",),
                owed_rows={"tester": ("row-a",)},
            ),
        ),
    )
    assert status.to_json() == {
        "schema": 1,
        "repo": REPO,
        "last_final": "v5.26.0",
        "since": "2026-10-02T00:00:00+00:00",
        "waiting": [
            {
                "number": 2,
                "title": "PR 2",
                "url": "u",
                "merged_at": "2026-10-03T00:00:00Z",
                "gates": ["tester"],
                "owed_rows": {"tester": ["row-a"]},
            }
        ],
    }


# -- the CLI ------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "-A")
    env_date = {
        "GIT_COMMITTER_DATE": "2026-10-02T00:00:00Z",
        "GIT_AUTHOR_DATE": "2026-10-02T00:00:00Z",
    }
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "-q",
            "-m",
            "b",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        env={**__import__("os").environ, **env_date},
    )
    _git(repo, "tag", "v5.26.0")
    _git(repo, "tag", "v5.27.0-rc.1")
    monkeypatch.chdir(repo)
    return repo


class FakeClient:
    def __init__(self, prs: list[dict[str, Any]], labels: dict[int, list[str]]) -> None:
        self._prs, self._labels = prs, labels
        self.calls: list[tuple[str, Any]] = []

    def list_prs(self, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_prs", (repo, state, limit)))
        return self._prs

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.calls.append(("pr_view", number))
        return {"state": "MERGED", "labels": self._labels[number]}


def _install(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    monkeypatch.setattr(release_cmd, "client_for_url", lambda url: client)
    monkeypatch.setattr(release_cmd, "owed_rows_reader", lambda root: lambda branch: {})


def test_status_json_lists_the_waiting_prs_since_the_last_final_tag(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeClient(
        [_pr(7, "2026-10-03T00:00:00Z"), _pr(6, "2026-10-01T00:00:00Z")],
        {7: ["gate:tester"], 6: ["gate:tester"]},
    )
    _install(monkeypatch, client)

    result = CliRunner().invoke(app, ["release", "status", "--json", "--repo", REPO])

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["last_final"] == "v5.26.0"
    assert [w["number"] for w in data["waiting"]] == [7]
    assert data["waiting"][0]["gates"] == ["tester"]
    assert ("pr_view", 6) not in client.calls


def test_status_text_says_when_nothing_waits(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, FakeClient([_pr(7, "2026-10-03T00:00:00Z")], {7: ["gate:tester-passed"]}))

    result = CliRunner().invoke(app, ["release", "status", "--repo", REPO])

    assert result.exit_code == 0, result.output
    assert "v5.26.0" in result.output
    assert "nothing waits" in result.output


def test_status_text_names_each_waiting_pr_its_gate_and_owed_rows(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeClient([_pr(7, "2026-10-03T00:00:00Z")], {7: ["gate:devops"]})
    monkeypatch.setattr(release_cmd, "client_for_url", lambda url: client)
    monkeypatch.setattr(
        release_cmd, "owed_rows_reader", lambda root: lambda branch: {"devops": ("row-x",)}
    )

    result = CliRunner().invoke(app, ["release", "status", "--repo", REPO])

    assert result.exit_code == 0, result.output
    assert "#7" in result.output and "gate:devops" in result.output and "row-x" in result.output


def test_a_forge_failure_fails_closed(checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.gh import GhError

    class Boom(FakeClient):
        def list_prs(self, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
            raise GhError("HTTP 502")

    _install(monkeypatch, Boom([], {}))

    result = CliRunner().invoke(app, ["release", "status", "--json", "--repo", REPO])

    assert result.exit_code == 1
    assert "HTTP 502" in result.output


def test_release_is_a_read_only_command() -> None:
    assert "release" in trigger.READ_ONLY_COMMANDS


def test_the_real_owed_rows_reader_reads_no_run_as_no_row(checkout: Path) -> None:
    read = release_cmd.owed_rows_reader(checkout)
    assert read("feat/none") == {}
    assert read("") is None
