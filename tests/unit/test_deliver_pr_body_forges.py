"""`deliver`'s live-PR check reads the body through the forge adapter, not
`fr.gh` (gh#742): on a GitLab or Gitea checkout `gh` can never read the PR,
so a gate wired to `fr.gh` refuses forever and the run cannot close out.

Each test drives the real gate against a checkout of that forge and mocks
only the forge CLI's subprocess boundary (`_run_glab` / `_run_tea`), with
`gh` refusing the way it does on a non-GitHub remote — so a regression back
onto `fr.gh` fails here rather than passing on a mocked `fr.gh`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.record_support import RUN, commit_all, fr, write_record
from tests.unit.test_deliver_pr_body import _at_deliver, _body

MR = "https://gitlab.com/example-group/example-project/-/merge_requests/11"
GITEA_PR = "https://gitea.example.com/example-org/example-repo/pulls/7"


@pytest.fixture(autouse=True)
def gh_cannot_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """`gh` on a non-GitHub remote: every read fails."""
    import fr.gh

    def refuse(ref: str, *, cwd: Path | None = None) -> str:
        raise fr.gh.GhError("none of the git remotes point to a known GitHub host")

    monkeypatch.setattr(fr.gh, "view_pr_body", refuse)


def _deliver(root: Path, pr: str):
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": pr}, "evidence": {"tests": "suite.log"},
    }  # fmt: skip
    rec = write_record(root, data)
    return fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])


def _checkout(tmp_path: Path, backend: str) -> Path:
    """A run at `deliver` whose repo declares *backend* — the explicit tier of
    `detect_backend`; `origin` stays the fixture's local bare repo, which the
    gate's merge-base check needs."""
    root = _at_deliver(tmp_path)
    profiles = root / ".devcontainer" / "fr-profiles.yaml"
    profiles.parent.mkdir(parents=True, exist_ok=True)
    profiles.write_text(f"backend: {backend}\n")
    commit_all(root, f"declare {backend}")
    return root


def test_deliver_resolves_on_a_gitlab_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.glab

    root = _checkout(tmp_path, "gitlab")
    served: dict[str, str] = {"description": "never read before the render"}
    calls: list[list[str]] = []

    def run_glab(args: list[str], *, host: str | None = None, cwd: Path | None = None) -> str:
        calls.append(args)
        return json.dumps({"description": served["description"], "web_url": MR})

    monkeypatch.setattr(fr.glab, "_run_glab", run_glab)

    first = _deliver(root, MR)
    assert first.exit_code == 2, first.output
    assert "gh pr" not in first.output
    assert "glab mr update" in first.output
    served["description"] = _body(root).read_text()

    out = _deliver(root, MR)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
    assert calls[-1] == [
        "mr", "view", "11", "--repo", "example-group/example-project", "--output", "json",
    ]  # fmt: skip


def test_deliver_resolves_on_a_gitea_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.tea

    root = _checkout(tmp_path, "gitea")
    served: dict[str, str] = {"body": "never read before the render"}

    def run_tea(args: list[str], *, cwd: Path | None = None) -> str:
        assert args[:2] == ["pulls", "list"], args
        assert "example-org/example-repo" in args
        return json.dumps(
            [
                {"index": "6", "url": GITEA_PR[:-1] + "6", "body": "other", "head": "x"},
                {"index": "7", "url": GITEA_PR, "body": served["body"], "head": "feat/rec"},
            ]
        )

    monkeypatch.setattr(fr.tea, "_run_tea", run_tea)

    first = _deliver(root, GITEA_PR)
    assert first.exit_code == 2, first.output
    assert "gh pr" not in first.output
    assert "tea pulls edit" in first.output
    served["body"] = _body(root).read_text()

    out = _deliver(root, GITEA_PR)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_an_unreadable_mr_names_the_forges_own_create_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.glab

    root = _checkout(tmp_path, "gitlab")

    def run_glab(args: list[str], *, host: str | None = None, cwd: Path | None = None) -> str:
        raise fr.glab.GlabError("no merge request found")

    monkeypatch.setattr(fr.glab, "_run_glab", run_glab)

    out = _deliver(root, MR)

    assert out.exit_code == 2, out.output
    assert "no merge request found" in out.output
    assert "glab mr create" in out.output
    assert "gh pr create" not in out.output
