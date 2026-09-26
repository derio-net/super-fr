"""`scripts/release.py` (spec 2026-09-26-version-bump-churn §3.C, §3.E, §5, §7 items 4-5).

Every case runs in temp git repos under `tmp_path` — a bare `origin` plus a
working clone seeded with a minimal copy of the version surfaces — never this
checkout. The bump, the `uv lock --check` and every `gh` call are injected, so
no real `uv` or `gh` runs and nothing reaches a real remote.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release_script", SCRIPT)
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
sys.modules["release_script"] = release
spec.loader.exec_module(release)

sys.path.insert(0, str(REPO / "scripts"))
import version_surfaces as vs  # noqa: E402

BASE = "4.23.0"
BOT = "github-actions[bot]"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _lock(version: str) -> str:
    return (
        "version = 1\n"
        "\n"
        "[[package]]\n"
        'name = "demo"\n'
        f'version = "{version}"\n'
        'source = { editable = "packages/demo" }\n'
        "\n"
        "[[package]]\n"
        'name = "requests"\n'
        'version = "2.31.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        "\n"
        "[[package]]\n"
        'name = "super-fr-workspace"\n'
        f'version = "{version}"\n'
        'source = { editable = "." }\n'
    )


def _seed(repo: Path, version: str = BASE) -> None:
    files = {
        "pyproject.toml": f'[project]\nname = "super-fr-workspace"\nversion = "{version}"\n',
        "packages/demo/pyproject.toml": f'[project]\nname = "demo"\nversion = "{version}"\n',
        "packages/demo/src/demo/__init__.py": 'FLOOR = ">=4.20.0,<5.0.0"\n',
        "packages/fr-opencode-plugin/package.json": json.dumps(
            {"name": "fr-opencode-plugin", "version": version}, indent=2
        )
        + "\n",
        "plugins/super-fr/.claude-plugin/plugin.json": json.dumps(
            {"name": "super-fr", "version": version}, indent=4
        )
        + "\n",
        ".claude-plugin/marketplace.json": json.dumps(
            {"plugins": [{"name": "super-fr", "version": version}]}, indent=4
        )
        + "\n",
        "uv.lock": _lock(version),
        "README.md": "# demo\n",
        ".changes/README.md": "# fragments\n",
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class World:
    """A bare origin, the release clone, and a second clone for 'other people'."""

    def __init__(self, tmp: Path) -> None:
        self.origin = tmp / "origin.git"
        seed = tmp / "seed"
        seed.mkdir()
        _git(seed, "init", "-q", "-b", "main")
        _seed(seed)
        _git(seed, "add", "-A")
        _git(seed, "commit", "-q", "-m", "base")
        _git(seed, "tag", "-a", f"v{BASE}", "-m", f"v{BASE}")
        _git(tmp, "clone", "-q", "--bare", str(seed), str(self.origin))
        self.clone = tmp / "clone"
        _git(tmp, "clone", "-q", str(self.origin), str(self.clone))
        self.other = tmp / "other"
        _git(tmp, "clone", "-q", str(self.origin), str(self.other))
        self.gh_calls: list[list[str]] = []
        self.bump_calls: list[str] = []
        self.lock_ok = True
        self.before_push: Callable[[int], None] = lambda n: None

    # -- other people's pushes -------------------------------------------
    def land(self, rel: str, text: str, message: str = "a merged PR") -> None:
        """Commit `rel` in the other clone and push it to origin (a merged PR)."""
        _git(self.other, "pull", "-q", "--ff-only", "origin", "main")
        path = self.other / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        _git(self.other, "add", "-A")
        _git(self.other, "commit", "-q", "-m", message)
        _git(self.other, "push", "-q", "origin", "HEAD:main")

    def fragment(self, name: str, bump: str, summary: str) -> None:
        self.land(f".changes/{name}.yaml", f"bump: {bump}\nsummary: {summary}\n")

    # -- origin state ----------------------------------------------------
    def origin_show(self, path: str, ref: str = "main") -> str | None:
        r = subprocess.run(
            ["git", "show", f"{ref}:{path}"], cwd=self.origin, capture_output=True, text=True
        )
        return r.stdout if r.returncode == 0 else None

    def origin_version(self) -> str:
        text = self.origin_show("pyproject.toml")
        assert text is not None
        return text.split('version = "', 1)[1].split('"', 1)[0]

    def origin_tags(self) -> list[str]:
        return _git(self.origin, "tag", "--list").split()

    def origin_log(self, fmt: str = "%s") -> list[str]:
        return _git(self.origin, "log", f"--format={fmt}", "main").splitlines()

    # -- injected commands ------------------------------------------------
    def commands(self):  # type: ignore[no-untyped-def]
        push_count = [0]

        def bump(repo: Path, new: str) -> None:
            self.bump_calls.append(new)
            vs.write_version(repo, new)
            push_count[0] += 1
            self.before_push(push_count[0])

        def lock_check(repo: Path) -> str | None:
            return None if self.lock_ok else "uv.lock needs to be updated"

        def gh(args: list[str]) -> subprocess.CompletedProcess[str]:
            self.gh_calls.append(list(args))
            return subprocess.CompletedProcess(["gh", *args], 0, "", "")

        return release.Commands(bump=bump, lock_check=lock_check, gh=gh)

    def run(self, *argv: str) -> int:
        return release.main(list(argv), repo=self.clone, commands=self.commands())


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    # Commits in the clone use the bot identity release.py sets; the other clone
    # and the tests use `-c user.*`. No global identity is assumed.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return World(tmp_path)


def _release_calls(world: World) -> list[list[str]]:
    return [c for c in world.gh_calls if c[:2] == ["release", "create"]]


def _issue_calls(world: World) -> list[list[str]]:
    return [c for c in world.gh_calls if c[:2] == ["issue", "create"]]


def _arg(call: list[str], flag: str) -> str:
    return call[call.index(flag) + 1]


# -- aggregation and the release commit ------------------------------------


def test_fragments_aggregate_to_the_highest_bump_and_are_removed_in_the_release_commit(
    world: World,
) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    world.fragment("feat-b", "minor", "add the feature")
    world.fragment("fix-c", "patch", "fix another thing")

    assert world.run() == 0

    assert world.origin_version() == "4.24.0"
    assert world.origin_log()[0] == "release: v4.24.0"
    author = world.origin_log("%an")[0]
    assert author == BOT
    # Fragments are gone in the SAME commit that moved the version.
    changed = _git(world.origin, "show", "--name-status", "--format=", "main").splitlines()
    assert "D\t.changes/fix-a.yaml" in changed
    assert "D\t.changes/feat-b.yaml" in changed
    assert "D\t.changes/fix-c.yaml" in changed
    assert "M\tpyproject.toml" in changed
    assert world.origin_show(".changes/README.md") is not None
    body = world.origin_log("%b")
    text = "\n".join(body)
    assert text.index("add the feature") < text.index("fix the thing")
    assert "fix another thing" in text
    # Grouped by bump: the minor heading comes before the patch heading.
    assert text.index("Minor") < text.index("Patch")
    assert "v4.24.0" in world.origin_tags()
    (call,) = _release_calls(world)
    assert call[2] == "v4.24.0"
    assert "--generate-notes" in call
    notes = _arg(call, "--notes")
    assert "add the feature" in notes and "fix the thing" in notes


def test_every_surface_moves_and_the_bump_gets_the_explicit_number(world: World) -> None:
    world.fragment("feat-x", "major", "a breaking change")
    assert world.run() == 0
    assert world.bump_calls == ["5.0.0"]
    _git(world.clone, "fetch", "-q", "origin")
    _git(world.clone, "reset", "-q", "--hard", "origin/main")
    assert {s.value for s in vs.version_surfaces(world.clone)} == {"5.0.0"}


def test_no_fragments_and_a_tagged_version_is_a_no_op(world: World) -> None:
    before = world.origin_log("%H")
    assert world.run() == 0
    assert world.origin_log("%H") == before
    assert world.gh_calls == []
    assert world.bump_calls == []
    assert world.origin_tags() == [f"v{BASE}"]


def test_no_fragments_and_an_untagged_version_only_tags(world: World) -> None:
    _git(world.origin, "tag", "-d", f"v{BASE}")
    before = world.origin_log("%H")
    assert world.run() == 0
    assert world.origin_log("%H") == before
    assert world.bump_calls == []
    assert world.origin_tags() == [f"v{BASE}"]
    tag_type = _git(world.origin, "cat-file", "-t", f"v{BASE}").strip()
    assert tag_type == "tag"  # annotated, as auto-tag.yml made them
    (call,) = _release_calls(world)
    assert call[2] == f"v{BASE}"
    # Not a release commit, so there are no notes to read: --generate-notes alone.
    assert "--notes" not in call and "--generate-notes" in call


def test_two_runs_back_to_back_are_safe(world: World) -> None:
    world.fragment("feat-b", "minor", "add the feature")
    assert world.run() == 0
    head = world.origin_log("%H")
    assert world.run() == 0
    assert world.origin_log("%H") == head
    assert len(_release_calls(world)) == 1


# -- the race ----------------------------------------------------------------


def test_a_push_lost_to_a_new_commit_recomputes_and_includes_its_fragment(
    world: World,
) -> None:
    world.fragment("fix-a", "patch", "fix the thing")

    def race(n: int) -> None:
        if n == 1:
            world.fragment("feat-late", "minor", "landed while releasing")

    world.before_push = race
    assert world.run() == 0
    assert world.bump_calls == ["4.23.1", "4.24.0"]
    assert world.origin_version() == "4.24.0"
    assert world.origin_show(".changes/feat-late.yaml") is None
    assert world.origin_show(".changes/fix-a.yaml") is None
    body = "\n".join(world.origin_log("%b"))
    assert "landed while releasing" in body and "fix the thing" in body
    # Recomputed from scratch, never rebased: one release commit on origin.
    assert world.origin_log().count("release: v4.24.0") == 1
    assert not any(s.startswith("release: v4.23.1") for s in world.origin_log())


def test_three_lost_races_exit_non_zero(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    world.before_push = lambda n: world.land(f"docs/n{n}.md", f"{n}\n")
    code = world.run()
    assert code != 0
    assert len(world.bump_calls) == 3
    assert not any(s.startswith("release:") for s in world.origin_log())
    assert world.gh_calls == []
    assert "3" in capsys.readouterr().err


@pytest.mark.parametrize(
    "refusal",
    [
        # Classic branch protection.
        "error: GH006: Protected branch update failed for refs/heads/main.",
        # A ruleset — what THIS repo's `protect main` would send once it gains a
        # required-PR rule (review rp3-f1): no GH006, no "protected branch".
        "error: GH013: Repository rule violations found for refs/heads/main.\\n"
        "- Changes must be made through a pull request.",
        # Any other server-side decline: git reports it as `[remote rejected]`,
        # never as a race's plain `[rejected]`.
        "error: refusing the update",
    ],
    ids=["gh006-classic", "gh013-ruleset", "generic-remote-rejected"],
)
def test_a_protection_refusal_fails_at_once_naming_the_bypass_actor(
    world: World, capsys: pytest.CaptureFixture[str], refusal: str
) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    # A pre-receive hook relays the line as `remote: error: ...`, as GitHub's reply reads.
    hook = world.origin / "hooks" / "pre-receive"
    hook.write_text(f"#!/bin/sh\nprintf '{refusal}\\n' >&2\nexit 1\n")
    hook.chmod(0o755)

    code = world.run()
    assert code != 0
    assert len(world.bump_calls) == 1  # never retried as a lost race
    err = capsys.readouterr().err
    assert "bypass actor" in err
    assert "protection" in err
    assert "lost the push race" not in err


# -- refusals ----------------------------------------------------------------


def test_an_override_not_above_the_current_version_is_refused(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    for version in (BASE, "4.22.9"):
        assert world.run("--version", version) != 0
        assert "above" in capsys.readouterr().err
    assert world.bump_calls == []


def test_an_override_wins_over_the_fragments(world: World) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    assert world.run("--version", "5.0.0") == 0
    assert world.origin_version() == "5.0.0"
    assert world.origin_show(".changes/fix-a.yaml") is None


def test_an_override_with_no_fragments_releases_with_generated_notes_alone(
    world: World,
) -> None:
    assert world.run("--version", "4.23.5") == 0
    assert world.origin_version() == "4.23.5"
    (call,) = _release_calls(world)
    assert "--notes" not in call and "--generate-notes" in call


def test_a_pre_existing_tag_at_the_computed_version_is_bumped_past(world: World) -> None:
    _git(world.other, "tag", "-a", "v4.24.0", "-m", "manual")
    _git(world.other, "push", "-q", "origin", "v4.24.0")
    manual = _git(world.origin, "rev-parse", "v4.24.0").strip()
    world.fragment("feat-b", "minor", "add the feature")
    assert world.run() == 0
    assert world.origin_version() == "4.25.0"
    assert _git(world.origin, "rev-parse", "v4.24.0").strip() == manual  # never re-tagged
    assert "v4.25.0" in world.origin_tags()


def test_an_invalid_fragment_refuses_the_release(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    world.land(".changes/bad.yaml", "bump: huge\nsummary: nope\n")
    assert world.run() != 0
    err = capsys.readouterr().err
    assert "bad.yaml" in err and "bump" in err
    assert world.bump_calls == []
    assert world.origin_version() == BASE


def test_a_failing_lock_check_refuses(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    world.lock_ok = False
    assert world.run() != 0
    assert "uv.lock" in capsys.readouterr().err
    assert world.bump_calls == []
    assert world.origin_version() == BASE


@pytest.mark.parametrize(
    "stray",
    [
        ("README.md", "# demo\nsmuggled\n"),
        ("pyproject.toml", None),  # a non-version line in a surface file
    ],
    ids=["other-file", "other-line-in-a-surface"],
)
def test_a_staged_line_outside_the_version_surfaces_refuses(
    world: World, capsys: pytest.CaptureFixture[str], stray: tuple[str, str | None]
) -> None:
    world.fragment("fix-a", "patch", "fix the thing")
    rel, text = stray

    def smuggle(n: int) -> None:
        path = world.clone / rel
        if text is None:
            path.write_text(path.read_text() + 'description = "smuggled"\n')
        else:
            path.write_text(text)

    world.before_push = smuggle
    assert world.run() != 0
    err = capsys.readouterr().err
    assert rel in err
    assert world.origin_version() == BASE
    assert not any(s.startswith("release:") for s in world.origin_log())


def test_a_rerun_reads_its_notes_from_the_release_commit_body(world: World) -> None:
    world.fragment("feat-b", "minor", "add the feature")
    world.fragment("fix-a", "patch", "fix the thing")
    assert world.run() == 0
    # Simulate a run that pushed the release commit but died before tagging.
    _git(world.origin, "tag", "-d", "v4.24.0")
    world.gh_calls.clear()
    world.fragment("docs", "patch", "x")  # noise: a later PR must not change the notes
    _git(world.other, "rm", "-q", ".changes/docs.yaml")
    _git(world.other, "commit", "-q", "-m", "drop")
    _git(world.other, "push", "-q", "origin", "HEAD:main")

    assert world.run() == 0
    (call,) = _release_calls(world)
    assert call[2] == "v4.24.0"
    notes = _arg(call, "--notes")
    assert "add the feature" in notes and "fix the thing" in notes
    assert "--generate-notes" in call


# -- dry run -------------------------------------------------------------------


def test_dry_run_prints_the_bump_and_writes_nothing(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    (world.clone / ".changes").mkdir(exist_ok=True)
    (world.clone / ".changes" / "feat-b.yaml").write_text("bump: minor\nsummary: add it\n")
    status_before = _git(world.clone, "status", "--porcelain")
    head = world.origin_log("%H")
    assert world.run("--dry-run") == 0
    out = capsys.readouterr().out
    assert "4.24.0" in out and "minor" in out
    assert _git(world.clone, "status", "--porcelain") == status_before
    assert world.origin_log("%H") == head
    assert world.bump_calls == [] and world.gh_calls == []


# -- the release-time floor check (§3.E) ---------------------------------------


def test_a_floor_naming_the_wrong_release_still_tags_then_fails_and_files_an_issue(
    world: World,
) -> None:
    # A PR guessed 4.24.0, but a major landed with it, so this releases as 5.0.0.
    world.land(
        "packages/demo/src/demo/new.py", 'SCOPE_FR_VERSION = ">=4.24.0,<5.0.0"\n', "floor PR"
    )
    world.fragment("feat-b", "minor", "the floor's feature")
    world.fragment("big", "major", "a breaking change")

    code = world.run()
    assert code == release.EXIT_FLOOR
    assert code not in (0, 1)
    assert "v5.0.0" in world.origin_tags()  # the number itself is right, so it tags
    assert len(_release_calls(world)) == 1
    (issue,) = _issue_calls(world)
    title, body = _arg(issue, "--title"), _arg(issue, "--body")
    assert "5.0.0" in title
    assert "packages/demo/src/demo/new.py" in body
    assert ">=4.24.0" in body and ">=5.0.0" in body


def test_a_floor_naming_the_released_version_passes(world: World) -> None:
    world.land(
        "packages/demo/src/demo/new.py", 'SCOPE_FR_VERSION = ">=4.24.0,<5.0.0"\n', "floor PR"
    )
    world.fragment("feat-b", "minor", "the floor's feature")
    assert world.run() == 0
    assert _issue_calls(world) == []


def test_a_historical_floor_never_trips_the_release_check(world: World) -> None:
    world.land(
        "packages/demo/src/demo/__init__.py", 'FLOOR = ">=4.20.0,<6.0.0"  # moved\n', "reformat"
    )
    world.fragment("fix-a", "patch", "fix the thing")
    assert world.run() == 0
    assert _issue_calls(world) == []
