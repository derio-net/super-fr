"""The approval gate's forge seams: `pr_view` labels, `pr_ready`, `label_exists`
(spec 2026-10-11-merge-train-safety §A "Facts and the label", "Merging", "Label
creation"; R1, R3, R4), on both GitHub backends and the declared-unsupported ones.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fr import gh as _gh
from fr.ghclient import GhClient, UnsupportedBatchOps, UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient

from tests.unit.github_rest_support import REPO, FixtureGh, R, forbidden, parse_api

# ---------------------------------------------------------------- RealGhClient


class _Recorder:
    def __init__(self, answers: dict[tuple[str, ...], str | Exception] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.answers = answers or {}

    def __call__(self, args: list[str]) -> str:
        self.calls.append(list(args))
        for prefix, answer in self.answers.items():
            if tuple(args[: len(prefix)]) == prefix:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return ""


def _gh_404() -> _gh.GhError:
    return _gh.GhError(
        "gh: Not Found (HTTP 404)",
        stderr="gh: Not Found (HTTP 404)\n",
        returncode=1,
        stdout='{"message":"Not Found","status":"404"}',
    )


def test_gh_pr_view_asks_for_and_returns_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    view = json.dumps(
        {"state": "OPEN", "isDraft": True, "headRefOid": "abc",
         "labels": [{"id": "x", "name": "approved-fr", "color": "0E8A16"}]}
    )  # fmt: skip
    fake = _Recorder({("pr", "view"): view})
    monkeypatch.setattr(_gh, "_run_gh", fake)
    got = RealGhClient().pr_view(REPO, 7)
    assert got["labels"] == ["approved-fr"]
    (call,) = fake.calls
    assert "labels" in call[call.index("--json") + 1].split(",")


def test_gh_pr_ready_issues_gh_pr_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _Recorder()
    monkeypatch.setattr(_gh, "_run_gh", fake)
    assert RealGhClient().pr_ready(REPO, 7) is None
    assert fake.calls == [["pr", "ready", "7", "--repo", REPO]]


def test_gh_label_exists_reads_the_label_route(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _Recorder({("api",): '{"name":"approved-fr"}'})
    monkeypatch.setattr(_gh, "_run_gh", fake)
    assert RealGhClient().label_exists(REPO, "approved-fr") is True
    assert fake.calls == [["api", f"repos/{REPO}/labels/approved-fr"]]


def test_gh_label_exists_reads_a_404_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_gh, "_run_gh", _Recorder({("api",): _gh_404()}))
    assert RealGhClient().label_exists(REPO, "approved-fr") is False


def test_gh_label_exists_raises_any_other_error(monkeypatch: pytest.MonkeyPatch) -> None:
    boom = _gh.GhError("gh: Forbidden (HTTP 403)", stderr="HTTP 403", returncode=1)
    monkeypatch.setattr(_gh, "_run_gh", _Recorder({("api",): boom}))
    with pytest.raises(_gh.GhError):
        RealGhClient().label_exists(REPO, "approved-fr")


# ---------------------------------------------------------------- RealGhRestClient


def test_rest_pr_view_returns_the_pulls_labels() -> None:
    got = RealGhRestClient(run=FixtureGh()).pr_view(REPO, 1080)
    assert got["labels"] == []  # the captured draft #1080 carries none


def test_rest_pr_ready_posts_the_ccr_ready_route() -> None:
    fake = FixtureGh(writes={("POST", f"{R}/pulls/7/ccr/ready_for_review"): "{}"})
    assert RealGhRestClient(run=fake).pr_ready(REPO, 7) is None
    assert [parse_api(a)[:3] for a in fake.calls] == [
        ("POST", None, f"{R}/pulls/7/ccr/ready_for_review")
    ]


def test_rest_label_exists_from_the_captured_200_and_404() -> None:
    fake = FixtureGh()
    client = RealGhRestClient(run=fake)
    assert client.label_exists(REPO, "bug") is True
    assert client.label_exists(REPO, "approved-fr") is False
    assert fake.routes() == [f"{R}/labels/bug", f"{R}/labels/approved-fr"]


def test_rest_label_exists_raises_a_403() -> None:
    from fr.gh import GhError

    with pytest.raises(GhError, match="403"):
        RealGhRestClient(run=FixtureGh(fail=forbidden)).label_exists(REPO, "approved-fr")


# ---------------------------------------------------------------- the protocol


def test_both_new_verbs_are_on_the_protocol_and_both_github_clients() -> None:
    for name in ("pr_ready", "label_exists"):
        assert name in GhClient.__dict__, name
        assert callable(getattr(RealGhClient(), name))
        assert callable(getattr(RealGhRestClient(), name))


@pytest.mark.parametrize(
    ("op", "call"),
    [
        ("pr_ready", lambda c: c.pr_ready(REPO, 1)),
        ("label_exists", lambda c: c.label_exists(REPO, "approved-fr")),
    ],
)
def test_an_unsupported_backend_declares_both_verbs(op: str, call: Any) -> None:
    class _Ops(UnsupportedBatchOps):
        backend = "gitlab"

    with pytest.raises(UnsupportedForgeOperation, match=op):
        call(_Ops())
