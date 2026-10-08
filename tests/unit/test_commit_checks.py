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
from tests.unit.github_rest_support import FIXTURES, REPO, FixtureGh, R, parse_api
from tests.unit.test_real_ghrestclient import _RequiredChecksGh

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
    client, fake = client_for_moments("green-head")

    records = _by_name(client.commit_checks(REPO, _sha("green-head")))

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
    for moment in ("green", "green-head", "pending", "rerun"):
        assert (CHECKS / moment / "check-runs.json").is_file(), Path(moment)


# ---- p2-r3: a base sha only from a PR whose head IS the commit ----


def test_a_run_whose_pr_head_moved_on_names_no_base(client_for_moments) -> None:
    """`green/` was read after PR 1088's head had moved on (to `pending/`'s
    commit): every check run still lists the PR, but with its CURRENT head.
    GitHub reports the PR as it is now, so its base may not be the one CI
    merged with: "" (the witness's `unknown`), never the first PR's base."""
    client, _ = client_for_moments("green")

    records = client.commit_checks(REPO, _sha("green"))

    assert records and all(r["base_sha"] == "" for r in records)
    raw = json.loads((CHECKS / "green" / "check-runs.json").read_text())
    heads = {p["head"]["sha"] for r in raw["check_runs"] for p in r["pull_requests"]}
    assert heads == {_sha("pending")}  # the captured fact the rule rests on


# ---- p2-r1: the NAMES the base branch requires, reported or not ----


@pytest.fixture(params=["rest", "graphql"])
def client_on(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Both GitHub clients answering from *fake* (a `FixtureGh`)."""

    def build(fake: Any) -> Any:
        if request.param == "rest":
            return RealGhRestClient(run=fake)
        monkeypatch.setattr(_gh, "_run_gh", fake)
        return RealGhClient()

    return build


def test_required_check_names_read_the_captured_unprotected_main(client_on) -> None:
    """Captured: `main` requires no status check (protection off; the rulesets
    carry deletion and non-fast-forward only)."""
    fake = FixtureGh()

    assert client_on(fake).required_check_names(REPO, "main") == []
    assert fake.routes() == [f"{R}/branches/main", f"{R}/rules/branches/main"]


def test_required_check_names_are_names_whether_or_not_they_reported(client_on) -> None:
    """DERIVED (`_RequiredChecksGh`: the captured `branches/main` and ruleset
    answers with required lists filled in). Only the two branch routes are read:
    no PR, no commit, no check run, so a check not created yet is still named."""
    fake = _RequiredChecksGh()

    names = client_on(fake).required_check_names(REPO, "main")

    assert names == ["ci/external", "lint", "test", "typecheck"]
    assert fake.routes() == [f"{R}/branches/main", f"{R}/rules/branches/main"]


def test_the_fake_serves_required_names_and_the_open_pr() -> None:
    fake = FakeGhClient()
    fake.required_names[(REPO, "main")] = ["ci-ok"]
    fake.add_pr(REPO, 7, head_ref="feat/x")
    fake.add_pr(REPO, 6, head_ref="feat/x", state="CLOSED")

    assert fake.required_check_names(REPO, "main") == ["ci-ok"]
    assert fake.required_check_names(REPO, "dev") == []
    assert fake.open_pr_for_head(REPO, "feat/x") == {
        "number": 7,
        "url": f"https://github.com/{REPO}/pull/7",
    }
    assert fake.open_pr_for_head(REPO, "feat/y") is None


# ---- p2-r7: the open-PR lookup reads no files ----


def test_open_pr_for_head_reads_one_route_and_no_files(client_on) -> None:
    """Captured: PR 1088 is the open PR of `feat/cloud-triage`."""
    fake = FixtureGh()

    got = client_on(fake).open_pr_for_head(REPO, "feat/cloud-triage")

    assert got == {"number": 1088, "url": "https://github.com/derio-net/super-fr/pull/1088"}
    assert fake.routes() == [
        f"{R}/pulls?head=derio-net:feat/cloud-triage&state=open&per_page=100&page=1"
    ]


@pytest.mark.parametrize("client", [RealGlabClient(), RealTeaClient()], ids=["glab", "tea"])
@pytest.mark.parametrize(
    ("op", "call"),
    [
        ("required_check_names", lambda c: c.required_check_names("o/r", "main")),
        ("open_pr_for_head", lambda c: c.open_pr_for_head("o/r", "b")),
    ],
)
def test_glab_and_tea_refuse_the_ci_evidence_reads(client: Any, op: str, call: Any) -> None:
    with pytest.raises(UnsupportedForgeOperation) as exc:
        call(client)
    assert exc.value.op == op
