"""`fr push` (spec 2026-11-04-repo-feature-settings R11-R14).

Every test runs against a real clone of a real local bare origin. The git argv fr
runs is recorded, and no test may ever see a force flag: the squash rewrites only
unpushed commits, so a plain push always fast-forwards.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fr.cli import app
from fr.git_policy import ask as ask_mod
from fr.git_policy import push as push_mod
from typer.testing import CliRunner

from tests.unit.settings_repo import git, land_on_main, make_repo

runner = CliRunner()
BRANCH = "feat/x"
SPEC = "docs/superpowers/specs/2026-11-07-x-design.md"
FORCE = ("-f", "--force", "--force-with-lease", "--force-if-includes", "--mirror")


@pytest.fixture
def argv(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[str]]]:
    """Every git argv `fr push` ran, through the module's one runner."""
    calls: list[list[str]] = []
    real = push_mod.run_git

    def recording(
        cwd: Path,
        args: Sequence[str],
        env: dict[str, str] | None = None,
        stdin: str | None = None,
    ):
        calls.append(list(args))
        return real(cwd, args, env, stdin)

    monkeypatch.setattr(push_mod, "run_git", recording)
    yield calls
    for call in calls:
        assert not any(a in FORCE or a.startswith("--force") for a in call), call
        if call and call[0] == "push":
            assert not any(a.startswith("+") for a in call[1:]), call


def _commit(repo: Path, name: str, subject: str) -> str:
    (repo / name).write_text(f"{name}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", subject)
    return git(repo, "rev-parse", "HEAD").strip()


def _push(repo: Path, *args: str, env: dict[str, str] | None = None):
    return runner.invoke(app, ["push", *args], env={"VK_REPO_ROOT": str(repo), **(env or {})})


def _feature(repo: Path) -> Path:
    git(repo, "switch", "-q", "-c", BRANCH)
    return repo


def _remote_log(repo: Path) -> list[str]:
    origin = repo.parent / "origin.git"
    out = git(origin, "log", "--first-parent", "--format=%s", f"main..{BRANCH}")
    return out.splitlines()[::-1]


def _tree(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", f"{ref}^{{tree}}").strip()


# --- defaults ----------------------------------------------------------------


def test_with_defaults_fr_push_is_git_push_u(tmp_path: Path, argv: list[list[str]]) -> None:
    repo = _feature(make_repo(tmp_path))
    head = _commit(repo, "a", "feat(x): a")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert [c for c in argv if c[0] == "push"] == [["push", "-u", "origin", BRANCH]]
    assert git(repo, "rev-parse", f"origin/{BRANCH}").strip() == head


def test_an_unpushed_commit_whose_subject_does_not_match_refuses_naming_it(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = _feature(make_repo(tmp_path))
    _commit(repo, "a", "feat(x): a")
    bad = _commit(repo, "b", "wip")

    result = _push(repo)

    assert result.exit_code == 2, result.output
    assert bad[:12] in result.output and "wip" in result.output
    assert not [c for c in argv if c[0] == "push"]


def test_a_merge_commit_is_exempt_from_the_subject_check(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    _feature(repo)
    _commit(repo, "a", "feat(x): a")
    git(repo, "switch", "-q", "main")
    _commit(repo, "m", "chore(main): m")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "switch", "-q", BRANCH)
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "main")

    result = _push(repo)

    assert result.exit_code == 0, result.output


# --- squash-unpushed ---------------------------------------------------------

SQUASH = "git:\n  history: squash-unpushed\n"


def test_squash_folds_unpushed_commits_into_one_templated_commit_with_the_same_tree(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    base = git(repo, "rev-parse", "HEAD").strip()
    _feature(repo)
    _commit(repo, "a", "feat(api): add a")
    _commit(repo, "b", "fix(api): b")
    tree = _tree(repo, "HEAD")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["feat(api): add a"]
    assert _tree(repo, "HEAD") == tree
    assert git(repo, "rev-parse", "HEAD^").strip() == base
    assert (
        git(repo, "rev-parse", f"origin/{BRANCH}").strip() == git(repo, "rev-parse", "HEAD").strip()
    )
    assert git(repo, "status", "--porcelain") == ""


def test_squash_never_rewrites_a_pushed_commit(tmp_path: Path, argv: list[list[str]]) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    _feature(repo)
    _commit(repo, "a", "feat(api): a")
    assert _push(repo).exit_code == 0
    pushed = git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "b", "feat(api): b")
    _commit(repo, "c", "fix(api): c")
    tree = _tree(repo, "HEAD")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert git(repo, "rev-parse", "HEAD^").strip() == pushed
    assert _remote_log(repo) == ["feat(api): a", "feat(api): b"]
    assert _tree(repo, "HEAD") == tree


def test_squash_keeps_migration_and_merge_commits_and_squashes_the_segments_between(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    _feature(repo)
    _commit(repo, "a1", "feat(api): a1")
    _commit(repo, "a2", "feat(api): a2")
    migrate = _commit(repo, "m", "chore(fr): migrate 1 artifact to fr 6.1.0")
    _commit(repo, "b1", "fix(api): b1")
    git(repo, "switch", "-q", "main")
    other = _commit(repo, "o", "chore(main): o")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "switch", "-q", BRANCH)
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "main")
    _commit(repo, "c1", "feat(api): c1")
    _commit(repo, "c2", "feat(api): c2")
    tree = _tree(repo, "HEAD")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    subjects = _remote_log(repo)
    assert subjects == [
        "feat(api): a1",
        "chore(fr): migrate 1 artifact to fr 6.1.0",
        "fix(api): b1",
        "Merge branch 'main' into feat/x",
        "feat(api): c1",
    ]
    assert _tree(repo, "HEAD") == tree
    assert _tree(repo, "HEAD~3") == _tree(repo, migrate), "the migration commit keeps its tree"
    merge_parents = git(repo, "rev-list", "--parents", "-n", "1", "HEAD~1").split()
    assert merge_parents[2] == other, "the merge keeps its merged-in parent"


def test_squash_composes_the_subject_with_the_runs_issue(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    _feature(repo)
    _seed_run(repo, issue=42)
    _commit(repo, "a", "feat(api): a (#42)")
    _commit(repo, "b", "feat(api): b (#42)")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["feat(api): a (#42)"]


def test_a_diverged_remote_branch_refuses_and_never_forces(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = _feature(make_repo(tmp_path))
    _commit(repo, "a", "feat(x): a")
    assert _push(repo).exit_code == 0
    git(repo, "reset", "-q", "--hard", "HEAD^")
    _commit(repo, "b", "feat(x): b")

    result = _push(repo)

    assert result.exit_code == 2, result.output
    assert "never force" in result.output


# --- push: ask -----------------------------------------------------------------

ASK = "git:\n  push: ask\n"


def _seed_run(repo: Path, *, issue: int | None = None) -> None:
    (repo / SPEC).parent.mkdir(parents=True, exist_ok=True)
    (repo / SPEC).write_text("# X — design\n")
    runs = repo / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "r1.yaml").write_text(
        "schema_version: 11\nrun: r1\nworkflow: fr-goal@1\nbranch: feat/x\n"
        "started: '2026-11-07T00:00:00Z'\ncursor: implement\nsteps:\n"
        f"  brainstorm:\n    state: done\n    emitted:\n      spec: {SPEC}\n"
        "  implement:\n    state: pending\n" + (f"issue: {issue}\n" if issue else "")
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "chore(fr): run r1 — start" + (f" (#{issue})" if issue else ""))


def _ask_repo(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path)
    land_on_main(repo, ASK)
    _feature(repo)
    _seed_run(repo)
    _commit(repo, "a", "feat(x): a")
    return repo


def _request_id(output: str) -> str:
    for word in output.replace("`", " ").split():
        if word.startswith("push-"):
            return word.rstrip(".,:;")
    raise AssertionError(output)


def _approve(repo: Path, request_id: str) -> None:
    result = runner.invoke(
        app,
        [
            "journal",
            "add",
            "--scope",
            "spec",
            "--slug",
            "2026-11-07-x",
            "--kind",
            "decision",
            "--id",
            request_id,
            "--title",
            "push approved",
            "--answered-by",
            "operator",
        ],
        env={"VK_REPO_ROOT": str(repo)},
    )
    assert result.exit_code == 0, result.output


def _answered(monkeypatch: pytest.MonkeyPatch, value: bool | None) -> None:
    monkeypatch.setattr(ask_mod, "operator_answered_since", lambda env, since: value)


def test_push_ask_without_a_decision_prints_the_request_and_refuses(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, True)

    result = _push(repo)

    assert result.exit_code == 2, result.output
    rid = _request_id(result.output)
    assert rid.startswith("push-feat-x-")
    assert (
        f"fr journal add --scope spec --slug 2026-11-07-x --kind decision --id {rid} "
        in result.output
    )
    assert "--answered-by operator" in result.output
    assert not [c for c in argv if c[0] == "push"]


def test_push_ask_with_an_operator_decision_after_the_request_pushes(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, True)
    rid = _request_id(_push(repo).output)
    _approve(repo, rid)

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert [c for c in argv if c[0] == "push"] == [["push", "-u", "origin", BRANCH]]


def test_push_ask_refuses_when_the_transcript_shows_no_answer(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, False)
    rid = _request_id(_push(repo).output)
    _approve(repo, rid)

    result = _push(repo)

    assert result.exit_code == 2, result.output
    assert "no answered question" in result.output
    assert not [c for c in argv if c[0] == "push"]


def test_push_ask_refuses_naming_the_harness_when_the_transcript_is_unobservable(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, None)
    rid = _request_id(_push(repo).output)
    _approve(repo, rid)

    result = _push(repo, env={"FR_HARNESS": "hermes"})

    assert result.exit_code == 2, result.output
    assert "hermes" in result.output
    assert not [c for c in argv if c[0] == "push"]


def test_push_ask_does_not_accept_no_questions(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, True)

    result = _push(repo, "--no-questions")

    assert result.exit_code == 2, result.output
    assert not [c for c in argv if c[0] == "push"]


def test_a_code_commit_after_the_request_makes_it_stale(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, True)
    rid = _request_id(_push(repo).output)
    _approve(repo, rid)
    _commit(repo, "late", "feat(x): late")

    result = _push(repo)

    assert result.exit_code == 2, result.output
    assert _request_id(result.output) != rid
    assert not [c for c in argv if c[0] == "push"]


def test_the_git_runner_is_the_real_one_by_default() -> None:
    done = push_mod.run_git(Path(os.getcwd()), ["--version"])
    assert isinstance(done, subprocess.CompletedProcess) and done.returncode == 0


def test_a_push_to_a_branch_whose_recorded_pr_merged_is_refused(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The merged-PR push guard (#320) lives in `fr push` too: the shell hook only
    matches `git push`."""

    class Forge:
        def pr_status_by_url(self, url: str) -> dict[str, object]:
            assert url == "https://example.com/o/r/pull/7"
            return {"state": "MERGED", "draft": False}

    monkeypatch.setattr("fr.hostclient.client_for", lambda root: Forge())
    repo = _feature(make_repo(tmp_path))
    _seed_run(repo)
    cursor = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    cursor.write_text(cursor.read_text() + "pr: https://example.com/o/r/pull/7\n")
    git(repo, "commit", "-qam", "chore(fr): run r1 — pr create")

    result = _push(repo)

    assert result.exit_code == 2, result.output
    assert "MERGED" in result.output
    assert not [c for c in argv if c[0] == "push"]


def test_squash_composes_through_a_template_that_names_no_type(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(
        repo,
        'git:\n  history: squash-unpushed\n  commit:\n    without_issue: "[{scope}] {summary}"\n',
    )
    _feature(repo)
    _commit(repo, "a", "[api] add a")
    _commit(repo, "b", "[api] add b")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["[api] add a"]


# --- review p4-r1: a one-commit segment is flushed once ----------------------


def _parents(repo: Path, ref: str) -> list[str]:
    return git(repo, "rev-list", "--parents", "-n", "1", ref).split()[1:]


def test_squash_a_single_commit_then_a_migration_keeps_both(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    _feature(repo)
    a = _commit(repo, "a", "feat(api): a")
    m = _commit(repo, "m", "chore(fr): migrate 1 artifact to fr 6.1.0")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["feat(api): a", "chore(fr): migrate 1 artifact to fr 6.1.0"]
    assert git(repo, "rev-parse", "HEAD").strip() == m, "nothing needed rewriting"
    assert _parents(repo, "HEAD") == [a]


def test_squash_a_single_commit_then_a_merge_keeps_both(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    _feature(repo)
    a = _commit(repo, "a", "feat(api): a")
    git(repo, "switch", "-q", "main")
    other = _commit(repo, "o", "chore(main): o")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "switch", "-q", BRANCH)
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "main")
    tree = _tree(repo, "HEAD")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["feat(api): a", "Merge branch 'main' into feat/x"]
    assert _tree(repo, "HEAD") == tree
    assert _parents(repo, "HEAD") == [a, other]


def test_squash_a_single_commit_a_migration_and_another_keeps_each_subject(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SQUASH)
    _feature(repo)
    a = _commit(repo, "a", "feat(api): a")
    m = _commit(repo, "m", "chore(fr): migrate 1 artifact to fr 6.1.0")
    b = _commit(repo, "b", "fix(api): b")
    tree = _tree(repo, "HEAD")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == [
        "feat(api): a",
        "chore(fr): migrate 1 artifact to fr 6.1.0",
        "fix(api): b",
    ]
    assert git(repo, "rev-parse", "HEAD").strip() == b
    assert _parents(repo, "HEAD") == [m] and _parents(repo, m) == [a]
    assert _tree(repo, "HEAD") == tree
    assert "Squashed by fr push" not in git(repo, "log", "-1", "--format=%B", "HEAD")


# --- review p4-r2: fr's own commits are recognised under any template ----------

SCENARIO = 'git:\n  history: squash-unpushed\n  commit:\n    without_issue: "[{scope}] {summary}"\n'


def _fr_commit(repo: Path, name: str, message: str) -> str:
    """A commit through fr's one committer, as fr writes its own."""
    from fr.artifacts.commit import commit_paths

    (repo / name).write_text(f"{name}\n")
    outcome = commit_paths(repo, [Path(name)], message)
    assert outcome.committed, outcome.reason
    return git(repo, "rev-parse", "HEAD").strip()


def test_under_the_scenario_template_a_migration_commit_is_kept(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SCENARIO)
    _feature(repo)
    _commit(repo, "a1", "[api] a1")
    _commit(repo, "a2", "[api] a2")
    migrate = _fr_commit(repo, "m", "chore(fr): migrate 1 artifact to fr 6.1.0\n\n- m\n")
    _commit(repo, "b1", "[api] b1")
    _commit(repo, "b2", "[api] b2")
    tree = _tree(repo, "HEAD")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["[api] a1", "[fr] migrate 1 artifact to fr 6.1.0", "[api] b1"]
    assert _tree(repo, "HEAD~1") == _tree(repo, migrate)
    assert _tree(repo, "HEAD") == tree


def test_under_the_scenario_template_fr_bookkeeping_never_names_the_squash(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, SCENARIO)
    _feature(repo)
    _fr_commit(repo, "r", "chore(fr): run r1 — start")
    _commit(repo, "a", "[api] add a")
    _commit(repo, "b", "[api] add b")

    result = _push(repo)

    assert result.exit_code == 0, result.output
    assert _remote_log(repo) == ["[api] add a"]


def test_a_migration_commit_written_before_the_trailer_is_still_recognised(
    tmp_path: Path, argv: list[list[str]]
) -> None:
    """The subject parse stays the fallback for commits that carry no trailer."""
    from fr.git_policy.push import Commit, is_migration
    from fr.settings.model import parse_settings

    settings = parse_settings({}, source="test")
    old = Commit("s", ("p",), "t", "chore(fr): migrate 2 artifacts to fr 6.0.0", "", {})
    assert is_migration(settings, old)
    marked = Commit("s", ("p",), "t", "[fr] x", "[fr] x\n\nFr-Commit: migrate\n", {})
    assert is_migration(settings, marked)
    bookkeeping = Commit(
        "s",
        ("p",),
        "t",
        "chore(fr): migrate-ish",
        "chore(fr): migrate x\n\nFr-Commit: bookkeeping\n",
        {},
    )
    assert not is_migration(settings, bookkeeping)


def test_moving_code_into_the_journals_tree_makes_the_request_stale(
    tmp_path: Path, argv: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p4-r6: a rename shows only its destination to a rename-following diff,
    so code moved under docs/superpowers/journals/ kept a stale approval valid."""
    repo = _ask_repo(tmp_path)
    _answered(monkeypatch, True)
    rid = _request_id(_push(repo).output)
    _approve(repo, rid)
    git(repo, "mv", "a", "docs/superpowers/journals/specs/a.md")
    git(repo, "commit", "-qm", "feat(x): move a")

    result = _push(repo)

    assert result.exit_code == 2, result.output
    assert _request_id(result.output) != rid
    assert not [c for c in argv if c[0] == "push"]
