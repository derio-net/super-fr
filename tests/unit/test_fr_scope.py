"""The fast advisory tier `--fr-scope` and its advisory line (spec
2026-11-19-local-suite-cost R6, R7, §3.E), over a fixture repo."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
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
    unparseable_line,
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
        collect_only=False,
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
        {"collect_only": True},  # l-errors-r7: nothing ran
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
        collectonly=False,
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
        ({"collectonly": True}, "--collect-only"),
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


# --- lens-review fixes (l-tests-r1, r2; l-errors-r5, r7, r8) -------------------------


def test_a_default_ref_refusal_keeps_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """l-errors-r5: the GitRefusal says why there is no default ref; keep it."""
    import fr.git

    monkeypatch.setattr(
        fr.git, "remote_default_ref", lambda root: fr.git.GitRefusal("two remotes, none named")
    )
    with pytest.raises(ScopeError, match="two remotes, none named"):
        resolve_base(tmp_path, DEFAULT_BASE)


def test_an_unparseable_test_file_is_named(tmp_path: Path) -> None:
    """l-errors-r8: a test file `ast` cannot parse has no imports the index can see,
    so its selection gap is named rather than silent."""
    _write(tmp_path, {**FILES, "tests/unit/test_broken.py": "def (:\n"})
    index = ImportIndex.build(tmp_path)
    assert index.unparseable == frozenset({"tests/unit/test_broken.py"})
    line = unparseable_line(index)
    assert line.startswith("fr-scope: ")
    assert "tests/unit/test_broken.py" in line
    assert unparseable_line(ImportIndex.build(_fresh(tmp_path / "ok"))) == ""


def _fresh(root: Path) -> Path:
    _write(root, FILES)
    return root


# A throwaway repository wired with this repo's OWN `tests/conftest.py` and
# `tests/fr_scope.py` (copied, so a change to either is what runs) and its own pytest
# configuration, read from `pyproject.toml`: the hooks run in a real pytest session.
SESSION_TESTS = {
    ".gitignore": "__pycache__/\n",
    "packages/demo/src/demo_mod.py": "VALUE = 1\n",
    "packages/demo/src/other_mod.py": "VALUE = 2\n",
    "tests/unit/helper.py": "def value():\n    import demo_mod\n    return demo_mod\n",
    "tests/unit/test_uses_demo.py": "def test_uses():\n    if False:\n"
    "        import demo_mod  # noqa: F401\n",
    "tests/unit/test_via_helper.py": "from tests.unit.helper import value\n\n"
    "def test_helper():\n    assert value\n",
    "tests/unit/test_other.py": "def test_other():\n    if False:\n"
    "        import other_mod  # noqa: F401\n",
    "tests/unit/test_smoke_set.py": "import pytest\n\n@pytest.mark.smoke\n"
    "def test_smoke():\n    pass\n\ndef test_not_smoke():\n    pass\n",
    "tests/unit/test_scen.py": "import pytest\n\n@pytest.mark.scenario\n"
    "def test_scen():\n    if False:\n        import demo_mod  # noqa: F401\n\n"
    "def test_plain():\n    if False:\n        import demo_mod  # noqa: F401\n",
}

COPIED = ("tests/__init__.py", "tests/unit/__init__.py", "tests/conftest.py", "tests/fr_scope.py")


def _pytest_ini_section() -> str:
    """This repo's `[tool.pytest.ini_options]`, re-emitted (addopts, markers, testpaths)."""
    ini = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    lines = ["[tool.pytest.ini_options]"]
    lines += [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in ini.items()]
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def session_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("scope-session")
    for rel in (*COPIED, "tests/unit/fixture_templates.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, root / rel)
    _write(root, SESSION_TESTS)
    (root / "pyproject.toml").write_text(_pytest_ini_section(), encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _session(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """A real pytest session in *root*, no path argument (pytest collects `testpaths`)."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--no-cov", "-q", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=600,
    )


def _collected(stdout: str) -> set[str]:
    return {line.strip() for line in stdout.splitlines() if "::" in line}


def test_the_fast_tier_collects_exactly_the_dependents_and_the_smoke_set(
    session_repo: Path,
) -> None:
    """l-tests-r1: the `pytest_collection_modifyitems` wiring end to end. One source
    module changed: its importers (directly and through a `tests/` helper) and the
    smoke tests are collected, nothing else, and no scenario test."""
    module = session_repo / "packages/demo/src/demo_mod.py"
    module.write_text("VALUE = 3\n")
    try:
        done = _session(session_repo, "-m", "", "--collect-only", "--fr-scope", "HEAD")
    finally:
        module.write_text(SESSION_TESTS["packages/demo/src/demo_mod.py"])
    assert done.returncode == 0, done.stdout + done.stderr
    assert _collected(done.stdout) == {
        "tests/unit/test_uses_demo.py::test_uses",
        "tests/unit/test_via_helper.py::test_helper",
        "tests/unit/test_scen.py::test_plain",
        "tests/unit/test_smoke_set.py::test_smoke",
    }, done.stdout
    assert "4/7 tests collected (3 deselected)" in done.stdout, done.stdout


def _summary_lines(stdout: str) -> list[str]:
    return [line.strip() for line in stdout.splitlines()]


def test_the_default_local_run_says_why_it_is_advisory(session_repo: Path) -> None:
    """l-tests-r2, l-errors-r7: the plain run from the root (the shipped addopts'
    `-m 'not scenario'`) prints its reasons on the line before the advisory line."""
    done = _session(session_repo)
    assert done.returncode == 0, done.stdout + done.stderr
    lines = _summary_lines(done.stdout)
    at = lines.index(ADVISORY_LINE)
    assert lines[at - 1].startswith("fr-scope: advisory because "), lines
    assert "-m 'not scenario'" in lines[at - 1]
    assert "--collect-only" not in lines[at - 1]


def test_a_keyword_run_says_why_it_is_advisory(session_repo: Path) -> None:
    done = _session(session_repo, "-m", "", "-k", "smoke")
    assert done.returncode == 0, done.stdout + done.stderr
    lines = _summary_lines(done.stdout)
    at = lines.index(ADVISORY_LINE)
    assert lines[at - 1] == "fr-scope: advisory because -k 'smoke'", lines


def test_the_whole_suite_prints_no_advisory_line(session_repo: Path) -> None:
    done = _session(session_repo, "-m", "")
    assert done.returncode == 0, done.stdout + done.stderr
    assert ADVISORY_LINE not in _summary_lines(done.stdout)
    assert not [line for line in _summary_lines(done.stdout) if "advisory because" in line]
