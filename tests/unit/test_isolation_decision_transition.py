"""The edit gate past S1's transition (spec 2026-11-28-s1-followups R7, R8, R10).

The library decides the end from its own release: `$lib/../../.claude-plugin/plugin.json`
(the Claude Code plugin), else `$lib/../VERSION` (the Hermes hook tree), compared on
major.minor against `FR_REFUSE_FROM=9.2`; neither readable is ended, and
`FR_OLD_PATHS=refuse` ends it whatever the version. Every test here runs a copy of the hook
tree whose version source it chose (`tests/unit/hooks_tree.py`), so none changes side when
the release crosses 9.2.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.hooks_tree import ENDED_VERSION, OPEN_VERSION, Layout, hooks_tree, side_env
from tests.unit.test_isolation_decision_core import (
    NO_FR,
    _git,
    fr_repo,
    quiet_fr_worktree,
    quiet_repo,
    spec_in,
)

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="needs git"),
    pytest.mark.own_artifacts,
]

LIB_NAME = Path("lib") / "fr-isolation-decision.sh"


def _lib(tmp_path: Path, version: str | None, layout: Layout = "claude") -> Path:
    return hooks_tree(tmp_path / f"tree-{layout}-{version}", version, layout=layout) / LIB_NAME


def _run(
    lib: Path, script: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f". {shlex.quote(str(lib))}; {script}"],
        capture_output=True,
        text=True,
        env=side_env(env),
        check=False,
    )


def _ended(lib: Path, env: dict[str, str] | None = None) -> bool:
    return _run(lib, "_fr_transition_ended", env).returncode == 0


@pytest.mark.parametrize(
    ("layout", "version", "ended"),
    [
        ("claude", "9.1.0", False),
        ("claude", "9.1.0-rc.10", False),
        ("claude", "9.2.0", True),
        ("claude", "9.2.0-rc.1", True),
        ("claude", "10.0.0", True),
        ("claude", "8.12.0", False),
        ("hermes", "9.1.0", False),
        ("hermes", "9.2.0", True),
        ("hermes", "9.2.0rc1", True),
        ("hermes", None, True),
        ("claude", None, True),
        ("none", None, True),
        ("claude", "not-a-version", True),
    ],
)
def test_the_end_is_read_from_the_trees_own_version_source(
    tmp_path: Path, layout: Layout, version: str | None, ended: bool
) -> None:
    assert _ended(_lib(tmp_path, version, layout)) is ended


@pytest.mark.parametrize("layout", ["claude", "hermes"])
def test_fr_old_paths_refuse_ends_it_on_a_9_1_tree(tmp_path: Path, layout: Layout) -> None:
    lib = _lib(tmp_path, OPEN_VERSION, layout)
    assert not _ended(lib)
    assert _ended(lib, {"FR_OLD_PATHS": "refuse"})
    assert not _ended(lib, {"FR_OLD_PATHS": "keep"})  # only `refuse` means anything


def test_the_shipped_tree_reads_its_plugin_json() -> None:
    """The real plugin reads `plugins/super-fr/.claude-plugin/plugin.json`: a tree with
    the file removed would count as ended."""
    lib = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "hooks" / LIB_NAME
    out = _run(lib, 'printf "%s\\n" "$FR_DECISION_LIB_DIR"').stdout.strip()
    manifest = Path(out) / ".." / ".." / ".claude-plugin" / "plugin.json"
    assert manifest.resolve().is_file()


def _decide(lib: Path, file: Path, env: dict[str, str] | None = None) -> int:
    return _run(lib, f"fr_isolation_decide_edit {shlex.quote(str(file))}", env).returncode


@pytest.mark.parametrize(
    ("version", "env", "old_allow_allows"),
    [
        (OPEN_VERSION, None, True),
        (ENDED_VERSION, None, False),
        (OPEN_VERSION, {"FR_OLD_PATHS": "refuse"}, False),
    ],
    ids=["open", "ended", "refuse-env"],
)
def test_the_old_allowlist_is_read_only_before_the_end(
    tmp_path: Path, version: str, env: dict[str, str] | None, old_allow_allows: bool
) -> None:
    lib = _lib(tmp_path, version)
    repo = fr_repo(tmp_path)
    (repo / ".fr-isolation-allow").write_text("projects/**\n")
    assert _decide(lib, repo / "projects" / "x.md", env) == (0 if old_allow_allows else 1)
    # the new allowlist is read on both sides, and the old name stays protected
    (repo / ".fr").mkdir()
    (repo / ".fr" / "isolation-allow").write_text("data/**\n*\n")
    assert _decide(lib, repo / "data" / "x.md", env) == 0
    assert _decide(lib, repo / ".fr-isolation-allow", env) == 1


@pytest.mark.parametrize(
    ("version", "editable"), [(OPEN_VERSION, True), (ENDED_VERSION, False)], ids=["open", "ended"]
)
def test_an_old_only_switch_is_gated_but_its_fr_worktree_is_no_write_target(
    tmp_path: Path, version: str, editable: bool
) -> None:
    """R8: past the end an old-only `origin/fr:settings.yaml` naming quiet keeps the repo
    fr-enabled (a base-clone edit is denied) and its `fr` worktree is never a write target."""
    lib = _lib(tmp_path, version)
    home = tmp_path / "home"
    wt = quiet_fr_worktree(tmp_path, home)
    env = {**NO_FR, "HOME": str(home)}
    assert _decide(lib, spec_in(wt), env) == (0 if editable else 1)
    base = tmp_path / "q" / "prod"
    assert _decide(lib, base / "src.py", env) == 1


def _differing_switches(tmp_path: Path) -> Path:
    repo = quiet_repo(tmp_path)  # old switch: placement: quiet
    _git(repo, "checkout", "-q", "--orphan", "fr-config")
    _git(repo, "rm", "-rqf", ".")
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("placement: quiet\n\n")
    _git(repo, "add", ".fr/settings.yaml")
    _git(repo, "commit", "-qm", "new switch")
    _git(repo, "update-ref", "refs/remotes/origin/fr-config", "fr-config")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-qD", "fr-config")
    return repo


@pytest.mark.parametrize(
    ("version", "noted"), [(OPEN_VERSION, True), (ENDED_VERSION, False)], ids=["open", "ended"]
)
def test_differing_switches_add_no_note_past_the_end(
    tmp_path: Path, version: str, noted: bool
) -> None:
    lib = _lib(tmp_path, version)
    repo = _differing_switches(tmp_path)
    out = _run(lib, f"fr_switch_differ_note {shlex.quote(str(repo / 'src.py'))}", NO_FR).stdout
    assert ("fr settings sync" in out) is noted
    # past the end the new switch alone decides: canonical quiet, so the repo is quiet
    quiet = _run(
        lib,
        f"fr_git_resolve; _fr_read_switch {shlex.quote(str(repo))} && "
        '_fr_switch_enabled "$_fr_switch" && [ "$_fr_canon" = "placement: quiet" ]',
        NO_FR,
    )
    assert (quiet.returncode == 0) is (not noted)


@pytest.mark.parametrize("version", [OPEN_VERSION, ENDED_VERSION], ids=["open", "ended"])
@pytest.mark.parametrize("settings", ["placement: repo\n", "other: x\n"], ids=["repo", "none"])
def test_an_old_only_switch_naming_no_quiet_never_gates_a_repo(
    tmp_path: Path, version: str, settings: str
) -> None:
    """Review p2-r1: an unrelated `fr` branch whose root settings.yaml names no quiet
    placement leaves a plain repo ungated on both sides of the end."""
    lib = _lib(tmp_path, version)
    repo = quiet_repo(tmp_path, settings=settings)
    assert _decide(lib, repo / "src.py", NO_FR) == 0
