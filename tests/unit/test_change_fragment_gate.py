"""The `change-fragment` PR gate (spec 2026-09-26-version-bump-churn §3.B, §3.E, §7 items 3, 5).

Table-driven over synthetic git repos under `tmp_path` — never this checkout.
Each case commits a base on `main`, branches, applies an edit and commits a
head, then runs `scripts/check-change-fragment.py`'s `check(repo, "main")`.
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
SCRIPT = REPO / "scripts" / "check-change-fragment.py"
spec = importlib.util.spec_from_file_location("check_change_fragment", SCRIPT)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
sys.modules["check_change_fragment"] = gate
spec.loader.exec_module(gate)

BASE = "4.23.0"


def _lock(version: str, extra: str = "") -> str:
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
        f"{extra}"
    )


def _seed(repo: Path) -> None:
    files = {
        "pyproject.toml": f'[project]\nname = "super-fr-workspace"\nversion = "{BASE}"\n',
        "packages/demo/pyproject.toml": f'[project]\nname = "demo"\nversion = "{BASE}"\n',
        "packages/demo/src/demo/__init__.py": 'FLOOR = ">=4.20.0,<5.0.0"\n',
        "packages/fr-opencode-plugin/package.json": json.dumps(
            {"name": "fr-opencode-plugin", "version": BASE}, indent=2
        )
        + "\n",
        "plugins/super-fr/.claude-plugin/plugin.json": json.dumps(
            {"name": "super-fr", "version": BASE}, indent=4
        )
        + "\n",
        ".claude-plugin/marketplace.json": json.dumps(
            {"plugins": [{"name": "super-fr", "version": BASE}]}, indent=4
        )
        + "\n",
        "uv.lock": _lock(BASE),
        "README.md": "# demo\n",
        ".changes/README.md": "# fragments\n",
        ".changes/old-fragment.yaml": "bump: patch\nsummary: an earlier PR\n",
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GITHUB_HEAD_REF"):
        monkeypatch.delenv(var, raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _seed(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "feat/demo")
    return root


def _commit(repo: Path, edit: Callable[[Path], None]) -> None:
    edit(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "head")


def _write(rel: str, text: str) -> Callable[[Path], None]:
    def edit(repo: Path) -> None:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    return edit


def _all(*edits: Callable[[Path], None]) -> Callable[[Path], None]:
    def edit(repo: Path) -> None:
        for e in edits:
            e(repo)

    return edit


def _replace(rel: str, old: str, new: str) -> Callable[[Path], None]:
    def edit(repo: Path) -> None:
        path = repo / rel
        text = path.read_text()
        assert old in text, (rel, old)
        path.write_text(text.replace(old, new, 1))

    return edit


SRC = _write("packages/demo/src/demo/cli.py", "print('hi')\n")
FRAG_PATCH = _write(".changes/feat-demo.yaml", "bump: patch\nsummary: a demo change\n")
FRAG_MINOR = _write(".changes/feat-demo.yaml", "bump: minor\nsummary: a demo feature\n")
BUMP_ROOT = _replace("pyproject.toml", f'version = "{BASE}"', 'version = "4.24.0"')


def _add_member(version: str) -> Callable[[Path], None]:
    member = (
        "\n[[package]]\n"
        'name = "newpkg"\n'
        f'version = "{version}"\n'
        'source = { editable = "packages/newpkg" }\n'
    )
    return _all(
        _write(
            "packages/newpkg/pyproject.toml",
            f'[project]\nname = "newpkg"\nversion = "{version}"\n',
        ),
        _write("uv.lock", _lock(BASE, member)),
    )


CASES: list[tuple[str, Callable[[Path], None], list[str]]] = [
    ("bump-required path, no fragment", SRC, ["fragment"]),
    ("bump-required path, added fragment", _all(SRC, FRAG_PATCH), []),
    (
        "bump-required path, only a modified existing fragment",
        _all(SRC, _write(".changes/old-fragment.yaml", "bump: minor\nsummary: edited\n")),
        ["fragment"],
    ),
    (
        "bump-required path, invalid added fragment",
        _all(SRC, _write(".changes/feat-demo.yaml", "bump: huge\nsummary: s\n")),
        ["feat-demo.yaml", "bump"],
    ),
    ("root version changed, with a fragment", _all(SRC, FRAG_PATCH, BUMP_ROOT), ["pyproject.toml"]),
    (
        "plugin.json version changed",
        _all(
            FRAG_PATCH,
            _replace(
                "plugins/super-fr/.claude-plugin/plugin.json",
                f'"version": "{BASE}"',
                '"version": "4.24.0"',
            ),
        ),
        ["plugins/super-fr/.claude-plugin/plugin.json"],
    ),
    (
        "marketplace entry changed",
        _replace(".claude-plugin/marketplace.json", f'"version": "{BASE}"', '"version": "4.23.1"'),
        [".claude-plugin/marketplace.json"],
    ),
    (
        "opencode package.json changed",
        _replace(
            "packages/fr-opencode-plugin/package.json", f'"version": "{BASE}"', '"version": "5.0.0"'
        ),
        ["packages/fr-opencode-plugin/package.json"],
    ),
    ("uv.lock member line changed", _write("uv.lock", _lock("4.24.0")), ["uv.lock"]),
    (
        "uv.lock dependency-only change",
        _replace("uv.lock", 'version = "2.31.0"', 'version = "2.32.0"'),
        [],
    ),
    ("added workspace member at the base version", _all(_add_member(BASE), FRAG_PATCH), []),
    (
        "added workspace member at another version",
        _all(_add_member("0.1.0"), FRAG_PATCH),
        ["packages/newpkg/pyproject.toml", "uv.lock"],
    ),
    ("docs-only PR", _write("README.md", "# demo, reworded\n"), []),
    ("empty PR", lambda repo: None, []),
    (
        "floor added at the predicted version (minor)",
        _all(_write("packages/demo/src/demo/new.py", 'F = ">=4.24.0,<5.0.0"\n'), FRAG_MINOR),
        [],
    ),
    (
        "floor added, fragment predicts a different version (patch)",
        _all(_write("packages/demo/src/demo/new.py", 'F = ">=4.24.0,<5.0.0"\n'), FRAG_PATCH),
        ["packages/demo/src/demo/new.py", "4.24.0", "4.23.1"],
    ),
    (
        "floor at or below base",
        _all(_write("packages/demo/src/demo/new.py", 'F = ">=4.23.0,<5.0.0"\n'), FRAG_PATCH),
        [],
    ),
    (
        "historical floor reformatted, upper bound moved",
        _all(
            _write("packages/demo/src/demo/__init__.py", 'FLOOR = (\n    ">=4.20.0, <6.0.0"\n)\n'),
            FRAG_PATCH,
        ),
        [],
    ),
]


@pytest.mark.parametrize(("name", "edit", "needles"), CASES, ids=[c[0] for c in CASES])
def test_gate(repo: Path, name: str, edit: Callable[[Path], None], needles: list[str]) -> None:
    _commit(repo, edit)
    errors = gate.check(repo, "main")
    if not needles:
        assert errors == [], name
    else:
        assert errors, name
        blob = "\n".join(errors)
        for needle in needles:
            assert needle in blob, (name, needle, blob)


def test_version_is_compared_at_the_merge_base_not_the_base_tip(repo: Path) -> None:
    # main released after the branch point: the PR changed no version value.
    _commit(repo, _all(SRC, FRAG_PATCH))
    _git(repo, "checkout", "-q", "main")
    _commit(repo, _all(BUMP_ROOT, _write("uv.lock", _lock("4.24.0"))))
    _git(repo, "checkout", "-q", "feat/demo")
    assert gate.check(repo, "main") == []


def test_missing_fragment_failure_prints_the_fix(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit(repo, SRC)
    assert gate.main(["main"], repo=repo) == 1
    err = capsys.readouterr().err
    assert "add .changes/feat-demo.yaml with bump: patch" in err
    assert "packages/demo/src/demo/cli.py" in err


def test_version_edit_failure_prints_the_fix(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit(repo, _all(FRAG_PATCH, BUMP_ROOT))
    assert gate.main(["main"], repo=repo) == 1
    err = capsys.readouterr().err
    assert "revert the version edit — main assigns the number" in err


def test_a_passing_gate_exits_zero(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _commit(repo, _all(SRC, FRAG_PATCH))
    assert gate.main(["main"], repo=repo) == 0
    assert "ok" in capsys.readouterr().out


def test_usage_error_without_a_base_ref(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 2
    assert "usage" in capsys.readouterr().err


def test_the_gate_leaves_the_repo_untouched(repo: Path) -> None:
    _commit(repo, _all(SRC, FRAG_PATCH, BUMP_ROOT))
    before = (_git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain"))
    gate.check(repo, "main")
    assert (_git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain")) == before
