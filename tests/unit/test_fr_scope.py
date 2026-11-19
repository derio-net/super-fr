"""The fast advisory tier `--fr-scope` and its advisory line (spec
2026-11-19-local-suite-cost R6, R7, §3.E), over a fixture repo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.fr_scope import (
    ADVISORY_LINE,
    DEFAULT_BASE,
    ImportIndex,
    ScopeError,
    advisory_reasons,
    changed_paths,
    keep_item,
    resolve_base,
    select,
)

REPO = Path(__file__).resolve().parents[2]

FILES = {
    "packages/fr/src/fr/__init__.py": "",
    "packages/fr/src/fr/a.py": "X = 1\n",
    "packages/fr/src/fr/b.py": "Y = 1\n",
    "packages/fr/src/fr/run/__init__.py": "",
    "packages/fr/src/fr/run/c.py": "Z = 1\n",
    "tests/__init__.py": "",
    "tests/unit/__init__.py": "",
    "tests/unit/helper.py": "from fr.b import Y\n",
    "tests/unit/deep_helper.py": "from tests.unit import helper\n",
    "tests/unit/test_a.py": "from fr.a import X\n\ndef test_a():\n    assert X\n",
    "tests/unit/test_via_helper.py": "from tests.unit.helper import Y\n",
    "tests/unit/test_via_deep.py": "from .deep_helper import helper\n",
    "tests/unit/test_run.py": "import fr.run.c\n",
    "tests/unit/test_top.py": "import fr\n",
    "tests/unit/sub/__init__.py": "",
    "tests/unit/sub/conftest.py": "",
    "tests/unit/sub/test_sub.py": "def test_s():\n    pass\n",
}


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.fixture
def index(tmp_path: Path) -> ImportIndex:
    _write(tmp_path, FILES)
    return ImportIndex.build(tmp_path)


def test_a_changed_source_module_selects_its_direct_importers(index: ImportIndex) -> None:
    assert select(index, {"packages/fr/src/fr/a.py"}) == {"tests/unit/test_a.py"}


def test_a_changed_source_module_selects_through_tests_helpers(index: ImportIndex) -> None:
    assert select(index, {"packages/fr/src/fr/b.py"}) == {
        "tests/unit/test_via_helper.py",
        "tests/unit/test_via_deep.py",
    }


def test_a_changed_package_selects_tests_importing_a_module_inside_it(index: ImportIndex) -> None:
    assert select(index, {"packages/fr/src/fr/run/__init__.py"}) == {"tests/unit/test_run.py"}


def test_importing_only_the_parent_package_does_not_select_for_a_child_change(
    index: ImportIndex,
) -> None:
    assert "tests/unit/test_top.py" not in select(index, {"packages/fr/src/fr/run/c.py"})


def test_a_changed_helper_selects_its_importers(index: ImportIndex) -> None:
    assert select(index, {"tests/unit/deep_helper.py"}) == {"tests/unit/test_via_deep.py"}


def test_a_changed_conftest_selects_its_directory(index: ImportIndex) -> None:
    assert select(index, {"tests/unit/sub/conftest.py"}) == {"tests/unit/sub/test_sub.py"}


def test_a_changed_or_new_test_file_selects_itself(index: ImportIndex) -> None:
    assert select(index, {"tests/unit/test_top.py", "tests/unit/test_new.py"}) == {
        "tests/unit/test_top.py",
        "tests/unit/test_new.py",
    }


def test_a_change_outside_source_and_tests_selects_nothing(index: ImportIndex) -> None:
    assert select(index, {"docs/x.md", "scripts/release.py"}) == set()


def test_smoke_always_runs_and_scenario_never_does() -> None:
    assert keep_item("tests/unit/test_x.py", ["smoke"], set())
    assert not keep_item("tests/unit/test_x.py", ["scenario"], {"tests/unit/test_x.py"})
    assert not keep_item("tests/unit/test_x.py", ["scenario", "smoke"], set())
    assert keep_item("tests/unit/test_x.py", [], {"tests/unit/test_x.py"})
    assert not keep_item("tests/unit/test_x.py", [], set())


def _repo_with_origin(tmp_path: Path) -> Path:
    origin, root = tmp_path / "origin.git", tmp_path / "work"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "init", "-q", "-b", "main", str(root))
    _write(root, {".gitignore": "ignored.txt\n", "tests/unit/test_old.py": "", "a.txt": "a\n"})
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "origin", "main")
    _git(root, "remote", "set-head", "origin", "main")
    _git(root, "switch", "-q", "-c", "feat")
    return root


def test_the_changed_set_is_the_merge_base_diff_plus_untracked_files(tmp_path: Path) -> None:
    root = _repo_with_origin(tmp_path)
    _write(root, {"committed.txt": "c\n"})
    _git(root, "add", "committed.txt")
    _git(root, "commit", "-q", "-m", "on the branch")
    _write(root, {"a.txt": "edited\n", "untracked.py": "", "ignored.txt": "x"})

    assert changed_paths(root, "origin/main") == {"committed.txt", "a.txt", "untracked.py"}


def test_the_base_defaults_to_the_remote_default_ref(tmp_path: Path) -> None:
    root = _repo_with_origin(tmp_path)
    assert resolve_base(root, DEFAULT_BASE) == "origin/main"
    assert resolve_base(root, "HEAD~0") == "HEAD~0"


def test_no_default_ref_is_a_refusal_naming_the_option(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    with pytest.raises(ScopeError, match="--fr-scope <base-ref>"):
        resolve_base(tmp_path, DEFAULT_BASE)


def _reasons(**over: object) -> list[str]:
    kw: dict[str, object] = dict(
        fr_scope=None,
        markexpr="",
        keyword="",
        explicit_args=False,
        last_failed=False,
        stepwise=False,
    )
    kw.update(over)
    return advisory_reasons(**kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "over",
    [
        {"fr_scope": DEFAULT_BASE},
        {"fr_scope": "origin/main"},
        {"markexpr": "not scenario"},  # the default local run (R5)
        {"markexpr": "smoke"},
        {"keyword": "foo"},
        {"explicit_args": True},
        {"last_failed": True},
        {"stepwise": True},
    ],
)
def test_any_narrowed_session_is_advisory(over: dict[str, object]) -> None:
    assert _reasons(**over)


def test_the_whole_configured_suite_is_not_advisory() -> None:
    assert _reasons() == []  # `-m ""` with no other narrowing


def _pytest(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--no-cov", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_a_narrowed_session_prints_the_advisory_line_on_a_line_of_its_own() -> None:
    done = _pytest("--collect-only", "-q", "tests/unit/test_fr_scope.py")
    assert done.returncode == 0, done.stdout + done.stderr
    assert ADVISORY_LINE in [line.strip() for line in done.stdout.splitlines()]


def test_the_fast_tier_runs_from_the_command_line() -> None:
    done = _pytest("--collect-only", "-q", "--fr-scope", "HEAD", "tests/unit/test_fr_scope.py")
    assert done.returncode in (0, 5), done.stdout + done.stderr
    assert ADVISORY_LINE in [line.strip() for line in done.stdout.splitlines()]
