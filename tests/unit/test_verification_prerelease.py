"""`fr verification prerelease` and the prerelease workflow
(spec 2026-10-06-verification-strategies §H, R24)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.ghclient import UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient, workflow_run_args
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()
REMOTE = "https://github.com/example-org/example-repo"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    # `origin` is configured as REMOTE (so the slug and printed source are the
    # public form) while git really talks to the bare repo: `ls-remote` is real.
    _git(root, "remote", "add", "origin", REMOTE)
    _git(root, "config", f"url.{bare}.insteadOf", REMOTE)
    (root / "a").write_text("a")
    _git(root, "add", "a")
    _git(root, "commit", "-q", "-m", "a")
    _git(root, "checkout", "-q", "-b", "feat/x")
    _git(root, "push", "-q", "origin", "feat/x")
    return root, _git(root, "rev-parse", "HEAD")


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def dispatch_workflow(self, repo: str, workflow: str, *, inputs: dict[str, str]) -> None:
        self.calls.append((repo, workflow, inputs))


def _invoke(root: Path, argv: list[str], client: Any = None, monkeypatch=None):
    if client is not None:
        monkeypatch.setattr("fr.hostclient.client_for", lambda _root: client)
    return runner.invoke(app, argv, env={**os.environ, "VK_REPO_ROOT": str(root)})


def test_dry_run_prints_the_argv_the_rc_tag_and_the_install_source(repo, monkeypatch) -> None:
    root, sha = repo
    rec = _Recorder()

    result = _invoke(
        root, ["verification", "prerelease", "--branch", "feat/x", "--dry-run"], rec, monkeypatch
    )

    assert result.exit_code == 0, result.output
    assert "gh workflow run prerelease.yml" in result.output
    assert "-f branch=feat/x" in result.output
    assert f"-f sha={sha}" in result.output
    tag = f"rc/feat-x/{sha[:12]}"
    assert tag in result.output
    assert f"git+{REMOTE}@{tag}" in result.output
    assert rec.calls == []


def test_without_dry_run_it_dispatches_through_the_client(repo, monkeypatch) -> None:
    root, sha = repo
    rec = _Recorder()

    result = _invoke(root, ["verification", "prerelease", "--branch", "feat/x"], rec, monkeypatch)

    assert result.exit_code == 0, result.output
    assert rec.calls == [
        ("example-org/example-repo", "prerelease.yml", {"branch": "feat/x", "sha": sha})
    ]
    assert f"git+{REMOTE}@rc/feat-x/{sha[:12]}" in result.output


@pytest.mark.parametrize("client", [RealGlabClient(), RealTeaClient()], ids=["glab", "tea"])
def test_other_forges_exit_2_unsupported(repo, monkeypatch, client) -> None:
    root, _ = repo

    result = _invoke(
        root, ["verification", "prerelease", "--branch", "feat/x"], client, monkeypatch
    )

    assert result.exit_code == 2
    assert "dispatch_workflow" in result.output


def test_an_unknown_branch_is_refused(repo, monkeypatch) -> None:
    root, _ = repo

    result = _invoke(
        root,
        ["verification", "prerelease", "--branch", "nope", "--dry-run"],
        _Recorder(),
        monkeypatch,
    )

    assert result.exit_code == 2


def test_a_local_only_branch_is_refused(repo, monkeypatch) -> None:
    root, _ = repo
    _git(root, "checkout", "-q", "-b", "local-only")

    result = _invoke(
        root,
        ["verification", "prerelease", "--branch", "local-only", "--dry-run"],
        _Recorder(),
        monkeypatch,
    )

    assert result.exit_code == 2
    assert "push it first" in result.output


def test_the_sha_is_the_remote_head_not_a_stale_local_one(repo, monkeypatch) -> None:
    root, sha = repo
    (root / "b").write_text("b")
    _git(root, "add", "b")
    _git(root, "commit", "-q", "-m", "b")  # local ahead of the remote, unpushed
    rec = _Recorder()

    result = _invoke(root, ["verification", "prerelease", "--branch", "feat/x"], rec, monkeypatch)

    assert result.exit_code == 0, result.output
    assert rec.calls[0][2]["sha"] == sha
    assert f"rc/feat-x/{sha[:12]}" in result.output


def test_the_pr_body_route_and_the_command_name_the_same_source_form(repo, monkeypatch) -> None:
    """The PR body's route says the command 'prints the rc's `<source>`' and
    feeds it to `.fr/candidate-install {prefix} {source}`: the printed source
    is the bare `git+<remote>@<tag>` argument, on a line of its own."""
    root, sha = repo
    result = _invoke(
        root,
        ["verification", "prerelease", "--branch", "feat/x", "--dry-run"],
        _Recorder(),
        monkeypatch,
    )
    lines = [line.strip() for line in result.output.splitlines()]
    assert f"git+{REMOTE}@rc/feat-x/{sha[:12]}" in lines


def test_dispatch_workflow_argv() -> None:
    assert workflow_run_args("o/r", "prerelease.yml", {"branch": "feat/x", "sha": "ab"}) == [
        "workflow", "run", "prerelease.yml", "--repo", "o/r",
        "-f", "branch=feat/x", "-f", "sha=ab",
    ]  # fmt: skip


def test_real_gh_client_dispatches_via_gh(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("fr.gh._run_gh", lambda args: calls.append(args) or "")

    RealGhClient().dispatch_workflow("o/r", "prerelease.yml", inputs={"branch": "b"})

    assert calls == [workflow_run_args("o/r", "prerelease.yml", {"branch": "b"})]


@pytest.mark.parametrize("client", [RealGlabClient(), RealTeaClient()], ids=["glab", "tea"])
def test_glab_and_tea_declare_dispatch_workflow_unsupported(client) -> None:
    with pytest.raises(UnsupportedForgeOperation, match="dispatch_workflow"):
        client.dispatch_workflow("o/r", "prerelease.yml", inputs={})


# ---- the workflow file ----

WORKFLOW = REPO_ROOT / ".github/workflows/prerelease.yml"


def _wf() -> dict[Any, Any]:
    return yaml.safe_load(WORKFLOW.read_text())


def test_the_workflow_triggers_only_on_dispatch_with_a_required_branch_input() -> None:
    wf = _wf()
    on = wf.get("on", wf.get(True))
    assert set(on) == {"workflow_dispatch"}
    assert on["workflow_dispatch"]["inputs"]["branch"]["required"] is True


def _steps() -> list[dict[str, Any]]:
    return [s for j in _wf()["jobs"].values() for s in j["steps"]]


def test_the_workflow_takes_a_required_sha_and_refuses_a_head_that_is_not_it() -> None:
    on = _wf().get("on", _wf().get(True))
    assert on["workflow_dispatch"]["inputs"]["sha"]["required"] is True
    guards = [s for s in _steps() if s.get("env", {}).get("SHA") == "${{ inputs.sha }}"]
    assert guards, "no step receives inputs.sha through env:"
    script = guards[0]["run"]
    assert 'git rev-parse HEAD' in script and '"$SHA"' in script and "exit 1" in script


def test_the_workflow_accepts_a_branch_head_and_nothing_else_ref() -> None:
    steps = _steps()
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "refs/heads/${{ inputs.branch }}"
    probe = next(s for s in steps if "git ls-remote" in s.get("run", ""))
    assert 'git ls-remote --exit-code --heads origin "refs/heads/$BRANCH"' in probe["run"]
    assert probe["env"]["BRANCH"] == "${{ inputs.branch }}"
    assert steps.index(probe) < steps.index(next(s for s in steps if "git tag" in s.get("run", "")))


def test_no_run_script_interpolates_an_expression_and_inputs_reach_the_shell_via_env() -> None:
    for step in _steps():
        assert "${{" not in step.get("run", ""), step
    wf_text = WORKFLOW.read_text()
    # every `inputs.` reference sits in an `env:` value or the checkout `with:` ref
    for line in wf_text.splitlines():
        if "inputs." in line and "${{" in line:
            assert line.strip().split(":")[0] in {"BRANCH", "SHA", "ref"}, line


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    import re

    uses = [s["uses"] for s in _steps() if "uses" in s]
    assert uses
    for u in uses:
        assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u), u


def test_the_bash_slug_line_is_pinned_and_rc_tag_agrees_with_it() -> None:
    from fr.commands.verification_cmd import rc_tag

    run = next(s["run"] for s in _steps() if "slug=" in s.get("run", ""))
    assert "          slug=${BRANCH//\\//-}\n".strip() in [ln.strip() for ln in run.splitlines()]
    branch = "feat/a/b-c"
    sha = "0123456789abcdef0123456789abcdef01234567"
    out = subprocess.run(
        ["bash", "-c", f'BRANCH={branch}; sha={sha}; sha12=${{sha:0:12}}; '
         + next(ln.strip() for ln in run.splitlines() if ln.strip().startswith("slug="))
         + '; echo "rc/${slug}/${sha12}"'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    assert out == rc_tag(branch, sha)


def test_the_workflow_may_write_contents_and_read_the_rest() -> None:
    perms = _wf()["permissions"]
    assert perms["contents"] == "write"
    assert {v for k, v in perms.items() if k != "contents"} <= {"read"}


def test_the_workflow_cuts_a_prerelease_and_never_pushes_a_branch() -> None:
    text = WORKFLOW.read_text()
    steps = "\n".join(s.get("run", "") for j in _wf()["jobs"].values() for s in j["steps"])
    assert "rc/${slug}/${sha12}" in steps or "rc/$slug/$sha12" in steps
    assert "gh release create" in steps and "--prerelease" in steps and "--target" in steps
    assert "git tag" in steps and "git push origin" in steps
    for line in steps.splitlines():
        if "git push" in line:
            assert "refs/tags/" in line, line
            assert "main" not in line and "HEAD" not in line
    assert "git commit" not in text and "bump-version" not in text


def test_the_workflow_is_on_the_ci_budget_watch_list() -> None:
    watch = yaml.safe_load((REPO_ROOT / ".github/workflows/ci-budget.yml").read_text())
    on = watch.get("on", watch.get(True))
    assert _wf()["name"] in on["workflow_run"]["workflows"]
