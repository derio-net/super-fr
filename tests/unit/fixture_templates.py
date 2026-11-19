"""Sandboxed, copyable repository templates (spec 2026-11-19-local-suite-cost §3.B).

A test that needs "a repo that already has a started run" used to build it from
nothing: dozens of git starts and several `fr run` steps, each of which costs
seconds when the host is loaded. A template is built ONCE per worker, under the
same sandboxed `HOME` / `GIT_CONFIG_GLOBAL` the autouse per-test sandbox gives a
test, and every test gets a copy that is independent of it and of every other
copy: its own `origin.git` (the base's `origin` URL points at the copy), its own
worktree links (`git worktree repair`) and its own `.fr-isolation` toplevel.

`home_sandbox` is the one place that decides what the sandbox is, shared by
`tests/conftest.py`'s autouse fixture and by the factory here.
"""

from __future__ import annotations

import contextlib
import inspect
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import notset

__all__ = [
    "FixtureTemplates",
    "TemplateBuildError",
    "current",
    "forget_baseline",
    "build_paths",
    "home_sandbox",
    "install",
    "note_baseline",
]


class TemplateBuildError(AssertionError):
    """A template could not be built, or was built wrong: it names the template, so the
    failure is at the build and not a refusal in every later test that copies it."""


_BASELINE: tuple[pytest.MonkeyPatch, int, int, bool, bool] | None = None
"""The running test's `monkeypatch`, how many of its patches the AUTOUSE fixtures made, and
whether they had already changed the cwd or `sys.path` (`note_baseline`, called by
`tests/conftest.py` once they have all run)."""


def note_baseline(mp: pytest.MonkeyPatch) -> None:
    global _BASELINE
    _BASELINE = (
        mp,
        len(mp._setattr),  # type: ignore[attr-defined]
        len(mp._setitem),  # type: ignore[attr-defined]
        mp._cwd is not None,  # type: ignore[attr-defined]
        mp._savesyspath is not None,  # type: ignore[attr-defined]
    )


def forget_baseline() -> None:
    global _BASELINE
    _BASELINE = None


def _current(obj: object, name: str) -> object:
    return vars(obj).get(name, notset) if inspect.isclass(obj) else getattr(obj, name, notset)


def _put(obj: object, name: str, value: object) -> None:
    if value is notset:
        with contextlib.suppress(AttributeError):
            delattr(obj, name)
    else:
        setattr(obj, name, value)


@contextlib.contextmanager
def _without_the_tests_own_patches() -> Iterator[None]:
    """A template is built in the first test that asks for one, which may already have patched
    `fr` (a fake label sync, a fake forge) or the environment. Those patches belong to that test:
    were they built in, every later copy would carry them. So the patches made AFTER the
    autouse fixtures ran are taken off for the build and put back after, which leaves what the
    autouse fixtures set up (the sandbox, the forge and migration stubs) in force.

    What this CAN take off: `monkeypatch.setattr/setenv/setitem/delenv/delattr` entries made
    on the asker's own `monkeypatch` after the autouse fixtures. What it refuses to build
    under, because it cannot take them off: an active `monkeypatch.chdir` or `syspath_prepend`
    of the asker, and a mid-test `monkeypatch.undo()` (the lists shrank below the baseline).
    What it CANNOT detect, so a test that does these must not be the first to ask for a
    template: a `monkeypatch.context()` instance (its own lists), `unittest.mock` patches, and
    direct `os.environ` writes.

    Private APIs relied on, each pinned by `test_fixture_templates.py` so that a pytest upgrade
    moving one fails that one test: `MonkeyPatch._setattr`, `_setitem`, `_cwd`, `_savesyspath`,
    `_pytest.monkeypatch.notset`, and conftest's
    `request.session._fixturemanager._getautousenames`."""
    if _BASELINE is None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            raise TemplateBuildError(
                "a template is being built inside a test with no baseline: the autouse "
                "`_template_baseline` fixture (tests/conftest.py) has not run, so the test's "
                "own patches cannot be told from the sandbox's"
            )
        yield
        return
    mp, n_attr, n_item, had_cwd, had_path = _BASELINE
    if len(mp._setattr) < n_attr or len(mp._setitem) < n_item:  # type: ignore[attr-defined]
        raise TemplateBuildError(
            "the asking test's monkeypatch was undone below the autouse baseline "
            "(`monkeypatch.undo()` mid-test): the sandbox is gone, so a template built now "
            "would be built outside it"
        )
    if (mp._cwd is not None and not had_cwd) or (  # type: ignore[attr-defined]
        mp._savesyspath is not None and not had_path  # type: ignore[attr-defined]
    ):
        raise TemplateBuildError(
            "the asking test has an active `monkeypatch.chdir` or `syspath_prepend`, which a "
            "template build cannot take off: ask for the template before changing either"
        )
    attrs = list(mp._setattr[n_attr:])  # type: ignore[attr-defined]
    items = list(mp._setitem[n_item:])  # type: ignore[attr-defined]
    held_attrs = [(obj, name, _current(obj, name)) for obj, name, _ in attrs]
    held_items = [(d, key, d.get(key, notset)) for d, key, _ in items]
    for obj, name, old in reversed(attrs):
        _put(obj, name, old)
    for dic, key, old in reversed(items):
        if old is notset:
            dic.pop(key, None)
        else:
            dic[key] = old
    try:
        yield
    finally:
        for dic, key, value in held_items:
            if value is notset:
                dic.pop(key, None)
            else:
                dic[key] = value
        for obj, name, value in held_attrs:
            _put(obj, name, value)


def home_sandbox(
    home: Path,
    identity: Mapping[str, str],
    operator_home: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Write `<home>/.gitconfig` (only the operator's identity) and return the
    environment that makes `home` the sandbox: `HOME`, `GIT_CONFIG_GLOBAL`, and the
    uv cache and managed Pythons the real home lends the toolchain."""
    environ = os.environ if environ is None else environ
    gitconfig = home / ".gitconfig"
    sections: dict[str, list[str]] = {}
    for key, value in identity.items():
        section, name = key.split(".", 1)
        quoted = value.replace("\\", "\\\\").replace('"', '\\"')
        sections.setdefault(section, []).append(f'\t{name} = "{quoted}"')
    gitconfig.write_text(
        "".join(f"[{section}]\n" + "\n".join(lines) + "\n" for section, lines in sections.items()),
        encoding="utf-8",
    )
    env = {"HOME": str(home), "GIT_CONFIG_GLOBAL": str(gitconfig)}
    lent = {
        "UV_CACHE_DIR": Path(environ.get("XDG_CACHE_HOME") or operator_home / ".cache") / "uv",
        "UV_PYTHON_INSTALL_DIR": Path(
            environ.get("XDG_DATA_HOME") or operator_home / ".local" / "share"
        )
        / "uv"
        / "python",
    }
    for key, path in lent.items():
        if key not in environ and path.exists():
            env[key] = str(path)
    return env


def build_paths(home: Path) -> dict[str, str]:
    """The autouse fixtures point these at the asking test's own `tmp_path`; a template build
    would write its side effects there, and which test that is depends on the order. So a build
    points them inside its own sandbox `home` instead (spec §3.B: the build applies the
    sandbox environment itself). `test_fixture_templates.py` fails when an autouse fixture
    names another path variable that is not here."""
    env = {
        "FR_SESSIONS_DIR": home / "sessions-sandbox",
        "FR_TRANSCRIPT_ROOT": home / "no-transcripts-here",
        "FR_OPENCODE_DB": home / "no-opencode-db-here.db",
        "FR_MODELS_CACHE_DIR": home / "no-models-cache-here",
        "FR_OPS_TRUST_DIR": home / "ops-trust",
        "FR_OPS_GATE_DIR": home / "ops-gate",
    }
    for key in ("FR_OPS_TRUST_DIR", "FR_OPS_GATE_DIR"):
        env[key].mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in env.items()}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _git_out(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _worktrees(base: Path) -> list[Path]:
    """The linked worktrees of `base` (the main one left out)."""
    paths = [
        Path(line.removeprefix("worktree "))
        for line in _git_out(base, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    ]
    return paths[1:]


def _check_shape(key: str, template: Path, payload: Any) -> list[str]:
    """The post-build self-check every template gets: a template that is not what its builder
    meant fails HERE, naming itself, not as a refusal in every later test that copies it.
    Builders add their own asserts about the state they built (the cursor's step, the files).
    Returns what a copy cannot repair by itself (more than one worktree or remote), which `copy`
    refuses unless the builder's caller supplies `relink`."""
    unrepaired: list[str] = []
    problems: list[str] = []
    base = template / "base"
    if base.is_dir():
        linked = _worktrees(base)
        for worktree in linked:
            if not worktree.is_dir():
                problems.append(f"the worktree {worktree} is registered but missing")
                continue
            marker = worktree / ".fr-isolation"
            if marker.is_file():
                try:
                    toplevel = json.loads(marker.read_text())["toplevel"]
                except (ValueError, KeyError) as exc:
                    problems.append(f"{marker} is unreadable ({exc})")
                else:
                    if Path(toplevel).resolve() != worktree.resolve():
                        problems.append(f"{marker} names {toplevel}, not {worktree}")
        if len(linked) > 1:
            unrepaired.append(f"it has {len(linked)} linked worktrees but a copy repairs one")
        remotes = _git_out(base, "remote").split()
        if set(remotes) - {"origin"}:
            unrepaired.append(f"it has remotes {sorted(remotes)} but a copy repairs only `origin`")
    try:
        _remap(payload, (str(template.resolve()), str(template)), "/x")
    except TypeError as exc:
        problems.append(str(exc))
    if problems:
        raise TemplateBuildError(f"template {key!r} was built wrong: " + "; ".join(problems))
    return unrepaired


def _remap(value: Any, old: tuple[str, ...], new: str) -> Any:
    """`value` with every template path inside a string replaced by the copy's."""
    if isinstance(value, str):
        for prefix in old:
            value = value.replace(prefix, new)
        return value
    if isinstance(value, Path):
        return Path(_remap(str(value), old, new))
    if isinstance(value, (list, tuple)):
        return type(value)(_remap(v, old, new) for v in value)
    if isinstance(value, dict):
        return {k: _remap(v, old, new) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(
        f"a template payload holds a {type(value).__name__}, which cannot be remapped to the "
        "copy's paths: return JSON-like values (str, Path, list, tuple, dict, scalars)"
    )


class FixtureTemplates:
    """Builds each template once and hands out independent copies."""

    def __init__(self, root: Path, env: Mapping[str, str]) -> None:
        self.root = root
        self.env = dict(env)
        self._built: dict[str, tuple[Path, Any]] = {}
        self._unrepaired: dict[str, list[str]] = {}
        self._count = 0

    def _build(self, key: str, build: Callable[[Path], Any]) -> tuple[Path, Any]:
        if key not in self._built:
            self._count += 1  # a template may build another (deliver on started_run)
            template = self.root / f"t{self._count}"
            template.mkdir(parents=True)
            with _without_the_tests_own_patches():
                old = {k: os.environ.get(k) for k in self.env}
                os.environ.update(self.env)
                try:
                    try:
                        payload = build(template)
                    except TemplateBuildError:
                        raise
                    except Exception as exc:
                        raise TemplateBuildError(
                            f"template {key!r} failed to build: {type(exc).__name__}: {exc}"
                        ) from exc
                    self._unrepaired[key] = _check_shape(key, template, payload)
                finally:
                    for k, v in old.items():
                        if v is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = v
            self._built[key] = (template, payload)
        return self._built[key]

    def template_path(self, key: str, build: Callable[[Path], Any]) -> Path:
        return self._build(key, build)[0]

    def copy(
        self,
        key: str,
        build: Callable[[Path], Any],
        dest: Path,
        workspace: str = "workspace",
        relink: Callable[[Path], None] | None = None,
    ) -> Any:
        """Copy template `key` (built by `build(template_dir)` the first time, which
        returns a JSON-like payload) into the empty directory `dest`; return the
        payload with the template's paths rewritten to `dest`'s. A template that is
        not the base/origin.git/workspace shape passes `relink(dest)`, which points
        whatever else holds an absolute path (a remote URL, a config) at the copy."""
        template, payload = self._build(key, build)
        if relink is None and self._unrepaired[key]:
            raise TemplateBuildError(
                f"template {key!r} cannot be copied as is: {'; '.join(self._unrepaired[key])}. "
                "Pass `relink` to `copy` to repair the rest."
            )
        shutil.copytree(template, dest, symlinks=True, dirs_exist_ok=True)
        base, work = dest / "base", dest / workspace
        if base.is_dir() and (dest / "origin.git").is_dir():
            _git(base, "remote", "set-url", "origin", str(dest / "origin.git"))
        if base.is_dir() and work.is_dir():
            _git(base, "worktree", "repair", str(work))
            marker = work / ".fr-isolation"
            if marker.is_file():
                data = json.loads(marker.read_text())
                data["toplevel"] = str(work.resolve())
                marker.write_text(json.dumps(data))
        if relink is not None:
            relink(dest)
        old = (str(template.resolve()), str(template))
        return _remap(payload, old, str(dest.resolve()))


_ACTIVE: FixtureTemplates | None = None


def install(factory: FixtureTemplates | None) -> None:
    global _ACTIVE
    _ACTIVE = factory


def current() -> FixtureTemplates:
    if _ACTIVE is None:
        raise RuntimeError("no fixture_templates factory: run under pytest (tests/conftest.py)")
    return _ACTIVE
