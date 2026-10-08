"""`GhClient.commit_checks(repo, sha)` — spec 2026-10-07-cloud-triage §I (R22).

Every check on one commit as `{name, workflow, status, conclusion, url,
base_sha}`: check runs from `commits/{sha}/check-runs?filter=latest` (the
workflow from the Actions run of the check run's suite), commit statuses from
`commits/{sha}/status`, the latest per (workflow, name). Both GitHub clients
read the same REST routes; glab and tea refuse.

The fixtures are `tests/fixtures/github_rest/commit_checks/<moment>/`, captured
live (see that directory's README section).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fr import gh as _gh
from fr.ghclient import UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient

from tests.unit.fakes import FakeGhClient
from tests.unit.github_rest_support import FIXTURES, REPO, parse_api

CHECKS = FIXTURES / "commit_checks"
BASE = "18fa21e18b67dd02f33d4378ae71d09298323183"


def _sha(moment: str) -> str:
    return (CHECKS / moment / "sha").read_text().strip()


class MomentGh:
    """A fake `gh` (argv without `gh` → stdout) answering the three captured
    routes of each moment directory named, and nothing else."""

    def __init__(self, *moments: str, status: dict[str, Any] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.routes: dict[str, str] = {}
        for m in moments:
            sha, d = _sha(m), CHECKS / m
            r = f"repos/{REPO}"
            self.routes[f"{r}/commits/{sha}/check-runs?filter=latest&per_page=100&page=1"] = (
                d / "check-runs.json"
            ).read_text()
            self.routes[f"{r}/commits/{sha}/status"] = (
                json.dumps(status) if status is not None else (d / "status.json").read_text()
            )
            self.routes[f"{r}/actions/runs?head_sha={sha}&per_page=100&page=1"] = (
                d / "actions-runs.json"
            ).read_text()

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(list(argv))
        method, _header, route, _fields = parse_api(argv)
        assert method == "GET", argv
        if route not in self.routes:
            raise AssertionError(f"no captured fixture for {route!r}")
        return self.routes[route]


def _by_name(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in records:
        assert r["name"] not in out, f"two records for {r['name']!r}"
        out[r["name"]] = r
    return out


@pytest.fixture(params=["rest", "graphql"])
def client_for_moments(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Both GitHub clients, each answering from the captured moments."""

    def build(*moments: str, status: dict[str, Any] | None = None) -> tuple[Any, MomentGh]:
        fake = MomentGh(*moments, status=status)
        if request.param == "rest":
            return RealGhRestClient(run=fake), fake
        monkeypatch.setattr(_gh, "_run_gh", fake)
        return RealGhClient(), fake

    return build


def test_a_green_head_reports_every_check_with_its_workflow_and_base(client_for_moments) -> None:
    client, fake = client_for_moments("green")

    records = _by_name(client.commit_checks(REPO, _sha("green")))

    assert records["ci-ok"] == {
        "name": "ci-ok",
        "workflow": "CI",
        "status": "completed",
        "conclusion": "success",
        "url": records["ci-ok"]["url"],
        "base_sha": BASE,
    }
    assert records["ci-ok"]["url"].startswith("https://github.com/derio-net/super-fr/actions/runs/")
    assert records["matrix"]["workflow"] == "acceptance-report"
    assert all(r["conclusion"] == "success" for r in records.values())
    assert all("graphql" not in " ".join(c) for c in fake.calls)


def test_a_running_head_reports_pending_shards_and_no_gate(client_for_moments) -> None:
    client, _ = client_for_moments("pending")

    records = _by_name(client.commit_checks(REPO, _sha("pending")))

    assert "ci-ok" not in records  # its job `needs` the shards: no check run yet
    shard = records["test (py3.11, 1)"]
    assert shard["status"] == "in_progress" and shard["conclusion"] == ""
    assert records["lint"]["conclusion"] == "success"


def test_a_failed_attempt_re_run_green_yields_one_green_record(client_for_moments) -> None:
    """f1919d4 ran CI twice: `ci-ok` failed, then passed. One record, green."""
    client, _ = client_for_moments("rerun")

    records = client.commit_checks(REPO, _sha("rerun"))

    gates = [r for r in records if r["name"] == "ci-ok"]
    assert len(gates) == 1 and gates[0]["conclusion"] == "success"
    named = _by_name(records)
    assert named["test (py3.11, 2)"]["conclusion"] == "success"
    assert named["coverage"]["conclusion"] == "success"  # skipped first, then run
    assert named["ci-ok"]["base_sha"] == ""  # the PR is merged: no pull_requests


def test_statuses_keep_the_latest_per_context(client_for_moments) -> None:
    """DERIVED: no captured commit in this repo carries a commit status, so the
    two entries below are added to the captured `green/status.json` envelope in
    the field shape GitHub's combined-status route documents (context, state,
    target_url, created_at), the newer listed first as that route lists them."""
    envelope = json.loads((CHECKS / "green" / "status.json").read_text())
    envelope["statuses"] = [
        {
            "context": "legacy/build",
            "state": "success",
            "target_url": "https://ci.example.invalid/2",
            "created_at": "2026-10-08T12:00:00Z",
        },
        {
            "context": "legacy/build",
            "state": "failure",
            "target_url": "https://ci.example.invalid/1",
            "created_at": "2026-10-08T11:00:00Z",
        },
        {
            "context": "legacy/deploy",
            "state": "pending",
            "target_url": "https://ci.example.invalid/3",
            "created_at": "2026-10-08T12:00:00Z",
        },
    ]
    client, _ = client_for_moments("green", status=envelope)

    records = _by_name(client.commit_checks(REPO, _sha("green")))

    assert records["legacy/build"] == {
        "name": "legacy/build",
        "workflow": "",
        "status": "completed",
        "conclusion": "success",
        "url": "https://ci.example.invalid/2",
        "base_sha": "",
    }
    assert records["legacy/deploy"]["status"] == "pending"
    assert records["legacy/deploy"]["conclusion"] == ""


def test_the_routes_are_rest_and_filter_latest() -> None:
    fake = MomentGh("green")

    RealGhRestClient(run=fake).commit_checks(REPO, _sha("green"))

    routes = [parse_api(c)[2] for c in fake.calls]
    assert any("/check-runs?filter=latest" in r for r in routes)
    assert any(r.endswith(f"/commits/{_sha('green')}/status") for r in routes)


def test_the_fake_client_serves_fixtures() -> None:
    fake = FakeGhClient()
    rows = [{"name": "ci-ok", "workflow": "CI", "status": "completed", "conclusion": "success",
             "url": "u", "base_sha": BASE}]  # fmt: skip
    fake.commit_checks_by_sha[(REPO, "abc")] = rows

    assert fake.commit_checks(REPO, "abc") == rows
    assert fake.commit_checks(REPO, "nope") == []
    assert ("commit_checks", {"repo": REPO, "sha": "abc"}) in fake.calls


@pytest.mark.parametrize("client", [RealGlabClient(), RealTeaClient()], ids=["glab", "tea"])
def test_glab_and_tea_refuse(client: Any) -> None:
    with pytest.raises(UnsupportedForgeOperation) as exc:
        client.commit_checks("o/r", "abc")
    assert exc.value.op == "commit_checks"


def test_fixture_moments_exist() -> None:
    for moment in ("green", "pending", "rerun"):
        assert (CHECKS / moment / "check-runs.json").is_file(), Path(moment)
