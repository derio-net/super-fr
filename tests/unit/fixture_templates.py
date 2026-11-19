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
    "current",
    "forget_baseline",
    "home_sandbox",
    "install",
    "note_baseline",
]

_BASELINE: tuple[pytest.MonkeyPatch, int, int] | None = None
"""The running test's `monkeypatch` and how many of its patches the AUTOUSE fixtures made
(`note_baseline`, called by `tests/conftest.py` once they have all run)."""


def note_baseline(mp: pytest.MonkeyPatch) -> None:
    global _BASELINE
    _BASELINE = (mp, len(mp._setattr), len(mp._setitem))  # type: ignore[attr-defined]


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
    autouse fixtures set up (the sandbox, the forge and migration stubs) in force."""
    if _BASELINE is None:
        yield
        return
    mp, n_attr, n_item = _BASELINE
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


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _remap(value: Any, old: tuple[str, ...], new: str) -> Any:
    """`value` with every template path inside a string replaced by the copy's."""
    if isinstance(value, str):
        for prefix in old:
            value = value.replace(prefix, new)
        return value
    if isinstance(value, (list, tuple)):
        return type(value)(_remap(v, old, new) for v in value)
    if isinstance(value, dict):
        return {k: _remap(v, old, new) for k, v in value.items()}
    return value


class FixtureTemplates:
    """Builds each template once and hands out independent copies."""

    def __init__(self, root: Path, env: Mapping[str, str]) -> None:
        self.root = root
        self.env = dict(env)
        self._built: dict[str, tuple[Path, Any]] = {}
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
                    payload = build(template)
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
