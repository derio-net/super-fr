"""Sandboxed, copyable fixture templates (spec 2026-11-19-local-suite-cost §3.B, R2)."""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from _pytest.monkeypatch import notset
from fr.isolation.marker import valid_workspace
from fr.run.code_tree import newest_code_mtime

from tests.conftest import OPERATOR_HOME
from tests.unit import fixture_templates as ft
from tests.unit import record_support
from tests.unit.fixture_templates import TemplateBuildError
from tests.unit.record_support import LAST_BRIEF, RUN, fr, git, snapshot, started_run


def _refs(origin: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(origin), "for-each-ref"], check=True, capture_output=True, text=True
    ).stdout


def test_a_copied_started_run_is_a_valid_workspace_with_a_working_run(tmp_path):
    root = started_run(tmp_path)
    assert valid_workspace(root, "feat/rec").ok
    data = json.loads((root / ".fr-isolation").read_text())
    assert data["toplevel"] == str(root.resolve())
    out = fr(root, ["run", "status", RUN])
    assert out.exit_code == 0, out.output
    assert (
        git(root, "rev-parse", "--git-common-dir").strip()
        != git(root, "rev-parse", "--git-dir").strip()
    )


def test_a_push_in_one_copy_leaves_the_other_copys_origin_alone(tmp_path):
    a = started_run(tmp_path / "a")
    b = started_run(tmp_path / "b")
    before_b = _refs(tmp_path / "b" / "origin.git")
    git(a, "push", "-q", "origin", "feat/rec")
    assert "refs/heads/feat/rec" in _refs(tmp_path / "a" / "origin.git")
    assert _refs(tmp_path / "b" / "origin.git") == before_b
    assert "feat/rec" not in before_b
    assert git(b, "config", "remote.origin.url").strip() == str(tmp_path / "b" / "origin.git")


def test_a_write_in_a_copy_leaves_the_template_unchanged(tmp_path, fixture_templates):
    started_run(tmp_path / "first")
    template = fixture_templates.template_path("started_run", record_support._build_started_run)
    before = snapshot(template)
    root = started_run(tmp_path / "second")
    (root / "scratch.txt").write_text("x")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "scribble", "--no-verify")
    assert snapshot(template) == before
    assert "scratch.txt" not in before


def test_the_templates_home_and_git_config_are_the_sandboxs_not_the_operators(
    tmp_path, fixture_templates
):
    seen: dict[str, str] = {}

    def build(directory: Path) -> dict[str, str]:
        seen.update(HOME=os.environ["HOME"], GIT_CONFIG_GLOBAL=os.environ["GIT_CONFIG_GLOBAL"])
        return {}

    fixture_templates.copy("env-probe", build, tmp_path / "c")
    assert Path(seen["HOME"]) != OPERATOR_HOME
    assert not Path(seen["HOME"]).is_relative_to(OPERATOR_HOME / ".config")
    assert Path(seen["GIT_CONFIG_GLOBAL"]).parent == Path(seen["HOME"])
    assert seen["HOME"] != os.environ["HOME"]  # not this test's own sandbox either
    assert fixture_templates.env["HOME"] == seen["HOME"]
    # and building it did not leak into this process
    assert os.environ["HOME"] != seen["HOME"]


def test_last_brief_is_the_templates_brief_in_each_copy(tmp_path):
    started_run(tmp_path / "a")
    first = json.loads(json.dumps(LAST_BRIEF))
    LAST_BRIEF.clear()
    started_run(tmp_path / "b")
    second = json.loads(json.dumps(LAST_BRIEF))
    assert (first["step"], first["item"]) == ("implement-phase", "phase/1")
    assert LAST_BRIEF["record"]["template"]
    # the brief is the template's, with paths that name the copy rather than the template
    assert str(tmp_path / "a") not in json.dumps(second)
    assert json.dumps(first).replace(str((tmp_path / "a").resolve()), "X") == json.dumps(
        second
    ).replace(str((tmp_path / "b").resolve()), "X")


def test_a_run_cli_template_is_keyed_per_branch(tmp_path, fixture_templates):
    from tests.unit.test_run_cli import _repo

    x = _repo(tmp_path / "x", branch="feat/x")
    y = _repo(tmp_path / "y", branch="feat/y")
    again = _repo(tmp_path / "z", branch="feat/x")
    assert git(x, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/x"
    assert git(y, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/y"
    assert git(again, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/x"
    assert json.loads((y / ".fr-isolation").read_text())["branch"] == "feat/y"
    assert valid_workspace(again, "feat/x").ok


def test_a_template_may_be_built_from_another_template(tmp_path, fixture_templates):
    """`at_deliver` is built by copying `started_run` into its own template directory."""

    def inner(directory: Path) -> str:
        (directory / "inner.txt").write_text("i")
        return "inner"

    def outer(directory: Path) -> str:
        assert fixture_templates.copy("nested-inner", inner, directory / "in") == "inner"
        return "outer"

    assert fixture_templates.copy("nested-outer", outer, tmp_path / "c") == "outer"
    assert (tmp_path / "c" / "in" / "inner.txt").read_text() == "i"


class _Probe:
    value = "real"


def test_a_template_is_built_without_the_patches_of_the_test_that_asked_for_it(
    tmp_path, fixture_templates, monkeypatch
):
    """`test_exit_label_sync_points` patched the label sync before its first `deliver` template was
    built, and the template (and so every later copy) carried the fake's answers."""
    monkeypatch.setattr(_Probe, "value", "patched by this test")
    monkeypatch.setenv("TEMPLATE_PROBE_ENV", "patched by this test")
    monkeypatch.setitem(os.environ, "TEMPLATE_PROBE_ITEM", "x")
    seen: dict[str, str | None] = {}

    def build(directory: Path) -> None:
        seen["attr"] = _Probe.value
        seen["env"] = os.environ.get("TEMPLATE_PROBE_ENV")
        seen["item"] = os.environ.get("TEMPLATE_PROBE_ITEM")
        seen["autouse"] = os.environ.get("FR_HOST_ID")  # an autouse fixture's, kept

    fixture_templates.copy("patch-probe", build, tmp_path / "c")

    assert seen["attr"] == "real" and seen["env"] is None and seen["item"] is None
    assert seen["autouse"] == "feedfacefeedface"
    # and the test's own patches are back afterwards
    assert _Probe.value == "patched by this test"
    assert os.environ["TEMPLATE_PROBE_ENV"] == "patched by this test"
    assert os.environ["TEMPLATE_PROBE_ITEM"] == "x"


# ── review p2-r1: a template is checked after it is built ───────────────


def _repo_with_worktree(directory: Path, *, remotes: tuple[str, ...] = ()) -> None:
    base = directory / "base"
    subprocess.run(["git", "init", "-q", "-b", "main", str(base)], check=True)
    git(base, "config", "user.email", "t@example.com")
    git(base, "config", "user.name", "T")
    (base / "s").write_text("s")
    git(base, "add", "-A")
    git(base, "commit", "-qm", "s")
    git(base, "worktree", "add", "-q", "-b", "b", str(directory / "workspace"))
    for name in remotes:
        git(base, "remote", "add", name, "file:///nonexistent")


def test_a_template_that_fails_to_build_names_itself(tmp_path, fixture_templates):
    def build(directory: Path) -> None:
        raise AssertionError("deliver not briefed")

    with pytest.raises(TemplateBuildError, match=r"template 'broken' .*deliver not briefed"):
        fixture_templates.copy("broken", build, tmp_path / "c")


def test_a_template_with_a_wrong_marker_fails_at_build_not_in_a_later_test(
    tmp_path, fixture_templates
):
    def build(directory: Path) -> None:
        _repo_with_worktree(directory)
        (directory / "workspace" / ".fr-isolation").write_text(
            json.dumps({"toplevel": "/somewhere/else", "branch": "b"})
        )

    with pytest.raises(TemplateBuildError, match=r"template 'bad-marker' .*names /somewhere/else"):
        fixture_templates.copy("bad-marker", build, tmp_path / "c")


def test_a_template_with_a_missing_worktree_fails_at_build(tmp_path, fixture_templates):
    def build(directory: Path) -> None:
        _repo_with_worktree(directory)
        shutil.rmtree(directory / "workspace")

    with pytest.raises(TemplateBuildError, match=r"template 'gone' .*registered but missing"):
        fixture_templates.copy("gone", build, tmp_path / "c")


def test_the_at_deliver_template_checks_its_own_state(tmp_path, fixture_templates):
    """The flake's candidate cause, now a build-time assertion: `suite.log` must postdate every
    code path, else `deliver` refuses it and the later test sees only a refusal."""
    from tests.unit.test_deliver_pr_body import _at_deliver, _build_at_deliver

    root = _at_deliver(tmp_path)
    newest = newest_code_mtime(root, None, ignore=[root / "suite.log"])
    assert newest is not None and (root / "suite.log").lstat().st_mtime >= newest[0]
    src = inspect.getsource(_build_at_deliver)
    assert "stale" in src and "not briefed" in src


# ── review p2-r2: what a build cannot take off, it refuses ──────────────


def test_a_build_is_refused_under_an_active_chdir(tmp_path, fixture_templates, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TemplateBuildError, match="chdir"):
        fixture_templates.copy("chdir-probe", lambda d: None, tmp_path / "c")


def test_a_build_is_refused_under_an_active_syspath_prepend(
    tmp_path, fixture_templates, monkeypatch
):
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(TemplateBuildError, match="syspath_prepend"):
        fixture_templates.copy("syspath-probe", lambda d: None, tmp_path / "c")


def test_a_build_is_refused_after_a_mid_test_undo(tmp_path, fixture_templates, monkeypatch):
    monkeypatch.undo()  # takes the autouse sandbox off too
    with pytest.raises(TemplateBuildError, match="undone"):
        fixture_templates.copy("undo-probe", lambda d: None, tmp_path / "c")


def test_a_build_inside_a_test_with_no_baseline_is_refused(tmp_path, fixture_templates):
    held = ft._BASELINE
    ft.forget_baseline()
    try:
        with pytest.raises(TemplateBuildError, match="no baseline"):
            fixture_templates.copy("no-baseline-probe", lambda d: None, tmp_path / "c")
    finally:
        ft._BASELINE = held


def test_the_private_pytest_apis_the_guard_reads_are_still_there(request, monkeypatch):
    """Each private API the build guard uses, pinned one by one: a pytest upgrade that moves
    one fails here and says which."""
    assert isinstance(monkeypatch._setattr, list), "MonkeyPatch._setattr is no longer a list"
    monkeypatch.setattr(_Probe, "value", "x")
    obj, name, old = monkeypatch._setattr[-1]
    assert (obj, name) == (_Probe, "value") and old == "real", "_setattr entry shape changed"
    monkeypatch.setitem(os.environ, "PIN_PROBE", "1")
    dic, key, old = monkeypatch._setitem[-1]
    assert (dic, key) == (os.environ, "PIN_PROBE") and old is notset, "_setitem entry changed"
    assert monkeypatch._cwd is None, "MonkeyPatch._cwd is gone or no longer None at rest"
    assert monkeypatch._savesyspath is None, "MonkeyPatch._savesyspath changed"
    monkeypatch.chdir(Path.cwd())
    assert monkeypatch._cwd is not None, "chdir no longer records MonkeyPatch._cwd"
    monkeypatch.syspath_prepend(str(Path.cwd()))
    assert monkeypatch._savesyspath is not None, "syspath_prepend no longer records it"
    assert inspect.isclass(type(notset)) and repr(notset), "_pytest.monkeypatch.notset gone"
    names = request.session._fixturemanager._getautousenames(request.node)
    assert "_template_baseline" in list(names), "_getautousenames no longer lists autouse names"


# ── review p2-r5: a copy repairs one worktree and one origin, or refuses ─


def test_a_template_with_a_second_worktree_or_remote_is_refused_without_relink(
    tmp_path, fixture_templates
):
    def two_worktrees(directory: Path) -> None:
        _repo_with_worktree(directory)
        git(directory / "base", "worktree", "add", "-q", "-b", "c", str(directory / "other"))

    def two_remotes(directory: Path) -> None:
        _repo_with_worktree(directory, remotes=("origin", "upstream"))

    with pytest.raises(TemplateBuildError, match="2 linked worktrees"):
        fixture_templates.copy("two-wt", two_worktrees, tmp_path / "a")
    with pytest.raises(TemplateBuildError, match="upstream"):
        fixture_templates.copy("two-remotes", two_remotes, tmp_path / "b")
    # a builder's caller that repairs the rest says so
    fixture_templates.copy("two-wt", two_worktrees, tmp_path / "c", relink=lambda dest: None)


def test_remap_rewrites_a_path_and_refuses_what_it_cannot_remap():
    payload = {"p": Path("/t/x"), "l": [Path("/t/y"), "a/t/z"], "n": 1, "none": None}
    got = ft._remap(payload, ("/t",), "/d")
    assert got == {"p": Path("/d/x"), "l": [Path("/d/y"), "a/d/z"], "n": 1, "none": None}
    with pytest.raises(TypeError, match="object"):
        ft._remap({"x": object()}, ("/t",), "/d")


def test_a_template_payload_that_cannot_be_remapped_fails_at_build(tmp_path, fixture_templates):
    with pytest.raises(TemplateBuildError, match="template 'odd-payload' .*object"):
        fixture_templates.copy("odd-payload", lambda d: object(), tmp_path / "c")


# ── review p2-r6: a build writes inside its own sandbox ─────────────────


def test_a_build_points_the_autouse_path_variables_into_its_own_sandbox(
    tmp_path, fixture_templates
):
    seen: dict[str, str | None] = {}
    watched = tuple(ft.build_paths(tmp_path / "probe"))

    def build(directory: Path) -> None:
        seen.update({k: os.environ.get(k) for k in watched})

    outside = {k: os.environ.get(k) for k in watched}
    fixture_templates.copy("paths-probe", build, tmp_path / "c")
    home = Path(fixture_templates.env["HOME"])
    for key in watched:
        assert seen[key] and Path(seen[key]).is_relative_to(home), (key, seen[key])
        assert not Path(seen[key]).is_relative_to(tmp_path), key
    assert {k: os.environ.get(k) for k in watched} == outside  # restored


def test_every_autouse_path_variable_that_names_a_tests_dir_is_in_the_build_sandbox(
    tmp_path_factory, fixture_templates
):
    """An autouse fixture that points a new variable at a test's own directory must be added
    to `build_paths`, or a build writes its side effects into whichever test asked first."""
    base = str(tmp_path_factory.getbasetemp())
    in_a_tests_dir = {
        k
        for k, v in os.environ.items()
        if v.startswith(base) and k not in {"HOME", "GIT_CONFIG_GLOBAL", "PYTEST_CURRENT_TEST"}
    }
    assert in_a_tests_dir <= set(fixture_templates.env), sorted(
        in_a_tests_dir - set(fixture_templates.env)
    )


# --- lens-review fixes (l-errors-r6) -------------------------------------------------


def test_a_git_failure_in_a_copy_names_the_template_and_carries_gits_stderr(
    tmp_path, fixture_templates
):
    """`copy` points `origin` at the copy's `origin.git`: a base with no `origin`
    remote makes git fail, and that is a TemplateBuildError, not a bare
    CalledProcessError with the stderr dropped."""

    def build(directory: Path) -> None:
        _repo_with_worktree(directory)
        subprocess.run(["git", "init", "-q", "--bare", str(directory / "origin.git")], check=True)

    with pytest.raises(TemplateBuildError, match=r"template 'no-origin'.*(?i:no such remote)"):
        fixture_templates.copy("no-origin", build, tmp_path / "c")


def test_a_git_failure_while_checking_the_shape_names_the_template(tmp_path, fixture_templates):
    def build(directory: Path) -> None:
        (directory / "base").mkdir()  # a directory, but no repository

    with pytest.raises(TemplateBuildError, match=r"template 'not-a-repo'.*git worktree list"):
        fixture_templates.copy("not-a-repo", build, tmp_path / "c")


def _marker_of(directory: Path) -> Path:
    return directory / "workspace" / ".fr-isolation"


def test_a_marker_that_is_not_a_json_object_fails_at_build(tmp_path, fixture_templates):
    def build(directory: Path) -> None:
        _repo_with_worktree(directory)
        _marker_of(directory).write_text("[]")

    with pytest.raises(TemplateBuildError, match=r"template 'list-marker' .*not a JSON object"):
        fixture_templates.copy("list-marker", build, tmp_path / "c")


def test_a_marker_that_is_not_a_json_object_fails_at_copy(tmp_path, fixture_templates):
    def build(directory: Path) -> None:
        _repo_with_worktree(directory)
        work = directory / "workspace"
        _marker_of(directory).write_text(json.dumps({"toplevel": str(work.resolve())}))

    template = fixture_templates.template_path("late-list-marker", build)
    _marker_of(template).write_text('"a string"')
    with pytest.raises(TemplateBuildError, match=r"template 'late-list-marker'.*not a JSON object"):
        fixture_templates.copy("late-list-marker", build, tmp_path / "c")


def test_remap_replaces_a_template_path_only_on_a_path_boundary():
    payload = {"a": "/x/t1/f", "b": "/x/t10/f", "c": "/x/t1", "d": "cd /x/t1 && ls /x/t12"}
    assert ft._remap(payload, ("/x/t1",), "/d") == {
        "a": "/d/f",
        "b": "/x/t10/f",
        "c": "/d",
        "d": "cd /d && ls /x/t12",
    }
