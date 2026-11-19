"""The fast advisory tier `--fr-scope` and its advisory line (spec
2026-11-19-local-suite-cost R6, R7, §3.E), over a fixture repo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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
    session_reasons,
    unreached,
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


MENTIONS = {
    **FILES,
    "tests/unit/test_agent.py": 'AGENT = "plugins/super-fr/agents/fr-phase-executor.md"\n',
    "tests/unit/test_install.py": 'SCRIPT = "scripts/install.sh"\n',
}


def test_a_non_python_change_selects_the_tests_that_name_its_file(tmp_path: Path) -> None:
    """p3-r5: an agent, skill, yaml or shell change reaches no import; the tests
    whose source names its basename are selected instead."""
    _write(tmp_path, MENTIONS)
    index = ImportIndex.build(tmp_path)
    assert select(index, {"plugins/super-fr/agents/fr-phase-executor.md"}) == {
        "tests/unit/test_agent.py"
    }
    assert select(index, {"scripts/install.sh"}) == {"tests/unit/test_install.py"}


def test_changed_paths_no_test_reaches_are_named(tmp_path: Path) -> None:
    """p3-r5: what selects nothing beyond smoke is listed, so the gap is visible;
    fr's run artifacts (no code path) are not."""
    _write(tmp_path, MENTIONS)
    index = ImportIndex.build(tmp_path)
    changed = {
        "packages/fr/src/fr/a.py",
        "scripts/install.sh",
        "plugins/super-fr/skills/x/SKILL.md",
        "packages/fr/src/fr/nobody.py",
        "docs/superpowers/runs/r1.yaml",
    }
    assert unreached(index, changed) == [
        "packages/fr/src/fr/nobody.py",
        "plugins/super-fr/skills/x/SKILL.md",
    ]
    assert unreached(index, {"packages/fr/src/fr/a.py"}) == []


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


def test_a_renamed_module_keeps_its_old_name_in_the_changed_set(tmp_path: Path) -> None:
    """p3-r4: with rename detection the diff names only the new path, so tests
    importing the OLD module (now broken) would not be selected."""
    root = _repo_with_origin(tmp_path)
    _git(root, "switch", "-q", "main")
    _write(root, {"packages/fr/src/fr/old.py": "VALUE = 1\n" * 20})
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "module")
    _git(root, "push", "-q", "origin", "main")
    _git(root, "switch", "-q", "feat")
    _git(root, "merge", "-q", "--ff-only", "main")
    _git(root, "mv", "packages/fr/src/fr/old.py", "packages/fr/src/fr/new.py")
    _git(root, "commit", "-q", "-m", "rename")

    assert changed_paths(root, "origin/main") == {
        "packages/fr/src/fr/old.py",
        "packages/fr/src/fr/new.py",
    }


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
        args_source="TESTPATHS",
        last_failed=False,
        stepwise=False,
        ignore=None,
        ignore_glob=None,
        deselect=None,
        maxfail=0,
        testpaths_overridden=False,
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
        {"args_source": "ARGS"},
        {"args_source": "INVOCATION_DIR"},  # run from a subdirectory (p3-r2)
        {"last_failed": True},
        {"stepwise": True},
        {"ignore": ["tests/integration"]},
        {"ignore_glob": ["*_install_*"]},
        {"deselect": ["tests/unit/test_x.py::test_y"]},
        {"maxfail": 1},  # `-x` is `--maxfail=1`
        {"maxfail": 3},
        {"testpaths_overridden": True},
    ],
)
def test_any_narrowed_session_is_advisory(over: dict[str, object]) -> None:
    assert _reasons(**over)


def test_the_whole_configured_suite_is_not_advisory() -> None:
    assert _reasons() == []  # `-m ""` with no other narrowing
    assert _reasons(ignore=[], ignore_glob=[], deselect=[]) == []


def _config(**option: object) -> SimpleNamespace:
    """A stand-in for `pytest.Config` with pytest's own defaults for the options
    `session_reasons` reads (probed against pytest 9)."""
    opts: dict[str, object] = dict(
        markexpr="",
        keyword="",
        lf=False,
        stepwise=False,
        ignore=None,
        ignore_glob=None,
        deselect=None,
        maxfail=0,
        override_ini=None,
    )
    args_source = option.pop("args_source", "TESTPATHS")
    fr_scope = option.pop("fr_scope", None)
    opts.update(option)
    return SimpleNamespace(
        option=SimpleNamespace(**opts),
        args_source=SimpleNamespace(name=args_source),
        getoption=lambda name: fr_scope if name == "--fr-scope" else None,
    )


def test_a_whole_session_reads_as_whole_from_the_config() -> None:
    assert session_reasons(_config()) == []


@pytest.mark.parametrize(
    ("option", "reason"),
    [
        ({"args_source": "INVOCATION_DIR"}, "not testpaths"),
        ({"args_source": "ARGS"}, "explicit paths"),
        ({"ignore": ["x"]}, "--ignore"),
        ({"ignore_glob": ["x*"]}, "--ignore-glob"),
        ({"deselect": ["t::x"]}, "--deselect"),
        ({"maxfail": 1}, "--maxfail"),
        ({"override_ini": ["testpaths=tests/unit"]}, "testpaths"),
        ({"fr_scope": ""}, "--fr-scope"),
    ],
)
def test_each_narrowing_option_is_read_from_the_config(option: dict, reason: str) -> None:
    got = session_reasons(_config(**option))
    assert any(reason in r for r in got), got


def test_an_unrelated_ini_override_is_not_a_narrowing() -> None:
    assert session_reasons(_config(override_ini=["console_output_style=classic"])) == []


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


def test_a_session_run_from_a_subdirectory_prints_the_advisory_line() -> None:
    """p3-r2: with no path argument pytest collects the invocation directory, not
    `testpaths`, so a run from a subdirectory is narrowed."""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--no-cov", "-m", ""]
        + ["--collect-only", "-q"],
        cwd=REPO / "tests" / "fixtures",
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode in (0, 5), done.stdout + done.stderr
    assert ADVISORY_LINE in [line.strip() for line in done.stdout.splitlines()]


def test_the_fast_tier_runs_from_the_command_line() -> None:
    done = _pytest("--collect-only", "-q", "--fr-scope", "HEAD", "tests/unit/test_fr_scope.py")
    assert done.returncode in (0, 5), done.stdout + done.stderr
    assert ADVISORY_LINE in [line.strip() for line in done.stdout.splitlines()]
