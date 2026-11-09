"""`scripts/installable.py`: the one definition of an installable path (sweep-fixes R17).

The fixture repos live under `tmp_path`. The only read of this checkout is `git ls-files`.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import installable  # noqa: E402

TAG = "v1.0.0"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _commit(repo: Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _write(repo: Path, rel: str, text: str = "x\n") -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    # Long enough that git's rename detection pairs a move of it, whatever the path.
    _write(root, "plugins/super-fr/hooks/guard.md", "a line of a real file\n" * 20)
    _write(root, "packages/fr/src/fr/x.py", "X = 1\n")
    _write(root, "docs/guide.md", "guide\n")
    _commit(root, "base")
    _git(root, "tag", "-a", TAG, "-m", TAG)
    return root


@pytest.mark.parametrize(
    "path",
    [
        "docs/x",
        "docs/superpowers/runs/a.yaml",
        "tests/x",
        "tests/unit/test_x.py",
        ".github/x",
        ".github/workflows/ci.yml",
        ".changes/README.md",
        ".changes/feat-x.yaml",
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        ".test_durations",
    ],
)
def test_paths_nothing_installs_from(path: str) -> None:
    assert installable.is_installable(path) is False


@pytest.mark.parametrize(
    "path",
    [
        "packages/fr/src/x.py",
        "packages/fr/README.md",
        "plugins/super-fr/hooks/x",
        "plugins/README.md",
        "scripts/install.sh",
        "scripts/release.py",
        "uv.lock",
        "pyproject.toml",
        "a-new-top-level-file",
        "a-new-dir/deep/x.md",
        "docs",  # a file named like the directory, not under it
        "docs-site/x",
        "tests2/x",
        ".github2/x",
        ".changes2/x",
        ".test_durations.bak",
        "packages/fr/.test_durations",
        "packages/docs/x",
        "README.MD",  # the rule names `*.md`; anything else errs towards a spare RC
    ],
)
def test_every_other_path_is_installable(path: str) -> None:
    assert installable.is_installable(path) is True


def _requires_bump():  # type: ignore[no-untyped-def]
    script = REPO / "scripts" / "check-change-fragment.py"
    spec = importlib.util.spec_from_file_location("check_change_fragment_for_installable", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # the module's dataclass looks itself up here
    spec.loader.exec_module(module)
    return module.requires_bump


def test_every_tracked_path_that_requires_a_bump_is_installable() -> None:
    requires_bump = _requires_bump()
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, check=True, capture_output=True
    ).stdout
    paths = [p.decode(errors="surrogateescape") for p in tracked.split(b"\0") if p]
    required = [p for p in paths if requires_bump(p)]

    assert required, "requires_bump matched nothing: this test would pin nothing"
    assert [p for p in required if not installable.is_installable(p)] == []


def test_the_module_is_stdlib_only() -> None:
    tree = ast.parse((REPO / "scripts" / "installable.py").read_text())
    names = {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
    names |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}

    assert {n.split(".")[0] for n in names} <= set(sys.stdlib_module_names)


def test_no_change_since_the_tag_is_false(repo: Path) -> None:
    assert installable.installable_changed(repo, TAG) is False


def test_a_docs_only_diff_is_false(repo: Path) -> None:
    _write(repo, "docs/guide.md", "changed\n")
    _write(repo, "tests/unit/test_new.py", "\n")
    _write(repo, ".changes/feat-x.yaml", "bump: patch\nsummary: x\n")
    _write(repo, "README.md", "readme\n")
    _write(repo, ".github/workflows/x.yml", "name: x\n")
    _write(repo, ".test_durations", "{}\n")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is False


def test_a_code_diff_is_true(repo: Path) -> None:
    _write(repo, "packages/fr/src/fr/x.py", "X = 2\n")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is True


def test_one_code_path_among_docs_is_true(repo: Path) -> None:
    _write(repo, "docs/guide.md", "changed\n")
    _write(repo, "scripts/new.py", "\n")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is True


def test_a_deleted_installable_path_is_true(repo: Path) -> None:
    _git(repo, "rm", "-q", "packages/fr/src/fr/x.py")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is True


def test_a_revert_to_the_tags_tree_is_false(repo: Path) -> None:
    _write(repo, "packages/fr/src/fr/x.py", "X = 2\n")
    _commit(repo)
    assert installable.installable_changed(repo, TAG) is True
    _git(repo, "revert", "--no-edit", "HEAD")

    assert installable.installable_changed(repo, TAG) is False


def test_a_move_out_of_an_installable_path_is_true(repo: Path) -> None:
    # Without --no-renames git pairs the two sides and names only docs/guard.md.
    _git(repo, "mv", "plugins/super-fr/hooks/guard.md", "docs/guard.md")
    _commit(repo)
    renamed = _git(repo, "diff", "--name-only", TAG, "HEAD").split()
    assert renamed == ["docs/guard.md"], "the fixture no longer reads as a rename"

    assert installable.installable_changed(repo, TAG) is True


def test_a_non_ascii_docs_path_is_read_unquoted(repo: Path) -> None:
    # Unquoted reading is what keeps it under docs/: git would print "docs/caf\303\251.md".
    _write(repo, "docs/café.md")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is False


def test_a_non_ascii_installable_path_is_true(repo: Path) -> None:
    _write(repo, "plugins/super-fr/café.md")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is True


def test_a_docs_path_holding_a_newline_is_one_path(repo: Path) -> None:
    _write(repo, "docs/a\nplugins/b")
    _commit(repo)

    assert installable.installable_changed(repo, TAG) is False


def test_a_tag_named_like_a_branch_reads_the_tag(repo: Path) -> None:
    _write(repo, "packages/fr/src/fr/x.py", "X = 2\n")
    _commit(repo)
    _git(repo, "branch", TAG)  # the branch is at the changed code, the tag at the base

    assert installable.installable_changed(repo, TAG) is True


def test_a_failing_git_diff_raises_rather_than_reading_as_no_change(repo: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        installable.installable_changed(repo, "v9.9.9")
