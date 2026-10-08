"""`GhClient.pr_body` per backend (gh#742): the argv each adapter sends and
the field it reads back, for each ref form the deliver gate passes — a PR
URL (the recorded `emitted.pr`), a number, or the head branch (no `pr`
recorded)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient


def test_github_reads_through_gh_view_pr_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fr.gh

    seen: dict[str, object] = {}

    def view(ref: str, *, cwd: Path | None = None) -> str:
        seen.update(ref=ref, cwd=cwd)
        return "body"

    monkeypatch.setattr(fr.gh, "view_pr_body", view)
    assert RealGhClient().pr_body("feat/x", cwd=tmp_path) == "body"
    assert seen == {"ref": "feat/x", "cwd": tmp_path}


@pytest.mark.parametrize(
    ("ref", "argv", "cwd_used"),
    [
        (
            "https://gitlab.example.com/grp/sub/proj/-/merge_requests/11",
            ["mr", "view", "11", "--repo", "grp/sub/proj", "--output", "json"],
            False,
        ),
        ("11", ["mr", "view", "11", "--output", "json"], True),
        ("feat/x", ["mr", "view", "feat/x", "--output", "json"], True),
    ],
)
def test_gitlab_reads_the_mr_description(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ref: str,
    argv: list[str],
    cwd_used: bool,
) -> None:
    import fr.glab

    # glab is logged into the host (gh#1014's trust gate).
    (tmp_path / "glab-config").mkdir()
    (tmp_path / "glab-config" / "config.yml").write_text("hosts:\n    gitlab.example.com: {}\n")
    monkeypatch.setenv("GLAB_CONFIG_DIR", str(tmp_path / "glab-config"))
    seen: dict[str, object] = {}

    def run(args: list[str], *, host: str | None = None, cwd: Path | None = None) -> str:
        seen.update(args=args, host=host, cwd=cwd)
        return json.dumps({"description": "the body", "title": "t"})

    monkeypatch.setattr(fr.glab, "_run_glab", run)
    body = RealGlabClient(host="gitlab.example.com").pr_body(ref, cwd=tmp_path)

    assert body == "the body"
    assert seen["args"] == argv
    assert seen["host"] == "gitlab.example.com"
    assert seen["cwd"] == (tmp_path if cwd_used else None)


def test_gitlab_null_description_reads_as_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fr.glab

    monkeypatch.setattr(
        fr.glab, "_run_glab", lambda args, *, host=None, cwd=None: '{"description": null}'
    )
    assert RealGlabClient().pr_body("3", cwd=tmp_path) == ""


_GITEA_LIST = [
    {"index": "6", "url": "https://gitea.example.com/o/r/pulls/6", "body": "six", "head": "a"},
    {"index": "7", "url": "https://gitea.example.com/o/r/pulls/7", "body": "seven", "head": "b"},
]


@pytest.mark.parametrize(
    ("ref", "expected", "repo_arg"),
    [
        ("https://gitea.example.com/o/r/pulls/7", "seven", ["--repo", "o/r"]),
        ("6", "six", []),
        ("b", "seven", []),
    ],
)
def test_gitea_matches_by_url_index_or_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ref: str,
    expected: str,
    repo_arg: list[str],
) -> None:
    import fr.tea

    seen: dict[str, object] = {}

    def run(args: list[str], *, cwd: Path | None = None) -> str:
        seen.update(args=args, cwd=cwd)
        return json.dumps(_GITEA_LIST)

    monkeypatch.setattr(fr.tea, "_run_tea", run)
    assert RealTeaClient().pr_body(ref, cwd=tmp_path) == expected
    args = seen["args"]
    assert isinstance(args, list)
    assert args[:2] == ["pulls", "list"]
    assert "body" in args[args.index("--fields") + 1].split(",")
    for token in repo_arg:
        assert token in args
    assert seen["cwd"] == tmp_path


def test_gitea_no_matching_pr_raises_tea_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fr.tea

    monkeypatch.setattr(fr.tea, "_run_tea", lambda args, *, cwd=None: json.dumps(_GITEA_LIST))
    with pytest.raises(fr.tea.TeaError, match="no pull request"):
        RealTeaClient().pr_body("nope", cwd=tmp_path)


def _repo_on(tmp_path: Path, backend: str) -> Path:
    profiles = tmp_path / ".devcontainer" / "fr-profiles.yaml"
    profiles.parent.mkdir(parents=True)
    profiles.write_text(f"backend: {backend}\n")
    return tmp_path


@pytest.mark.parametrize(
    ("backend", "ref", "expected"),
    [
        ("github", "https://github.com/o/r/pull/5", "gh pr edit https://github.com/o/r/pull/5 "),
        ("gitlab", "https://gitlab.example.com/g/p/-/merge_requests/11", "glab mr update 11 "),
        ("gitlab", "fix/742", "glab mr update fix/742 "),
        ("gitea", "https://gitea.example.com/o/r/pulls/7", "tea pulls edit 7 "),
    ],
)
def test_pr_command_names_the_forges_own_cli(
    tmp_path: Path, backend: str, ref: str, expected: str
) -> None:
    from fr.hostclient import pr_command

    cmd = pr_command(_repo_on(tmp_path, backend), "edit", ref=ref, body="b.md")
    assert cmd.startswith(expected), cmd
    assert "b.md" in cmd


def test_every_backend_declares_every_pr_operation() -> None:
    from fr.hostclient import PR_COMMANDS

    ops = {frozenset(table) for table in PR_COMMANDS.values()}
    assert ops == {frozenset({"create", "edit", "ready", "fill"})}
    assert set(PR_COMMANDS) == {"github", "github-rest", "gitlab", "gitea"}


@pytest.mark.parametrize("out", ["not json", "[]", '"a string"'])
def test_gitlab_unreadable_output_is_a_glab_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, out: str
) -> None:
    """A CLI that exits 0 with output fr cannot read must still be a forge
    error — the gate refuses on those, and anything else crashes it."""
    import fr.glab

    monkeypatch.setattr(fr.glab, "_run_glab", lambda args, *, host=None, cwd=None: out)
    with pytest.raises(fr.glab.GlabError, match="unreadable"):
        RealGlabClient().pr_body("3", cwd=tmp_path)


@pytest.mark.parametrize("out", ["not json", '{"a": 1}'])
def test_gitea_unreadable_output_is_a_tea_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, out: str
) -> None:
    import fr.tea

    monkeypatch.setattr(fr.tea, "_run_tea", lambda args, *, cwd=None: out)
    with pytest.raises(fr.tea.TeaError, match="unreadable"):
        RealTeaClient().pr_body("3", cwd=tmp_path)
