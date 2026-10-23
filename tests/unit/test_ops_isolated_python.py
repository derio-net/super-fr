"""p4-isolated-python, p4-r7: every `python -m fr` that fr starts runs with `-P`
(safe_path: no cwd or script dir on sys.path, Python >= 3.11), so a checkout's own
top-level `fr/` package (planted by an untrusted PR) is never imported in place of the
real fr, which then runs with the operator's credentials. `-P` and not `-I`: isolated
mode would also drop the user site and PYTHONPATH an operator's install may rely on."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.triage.gitseam import Worktree, run_this_fr

SRC = Path(__file__).resolve().parents[2] / "packages"


@pytest.fixture
def planted(tmp_path: Path) -> tuple[Path, Path]:
    marker = tmp_path / "pwned"
    pkg = tmp_path / "checkout" / "fr"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
    (pkg / "__main__.py").write_text("raise SystemExit(0)\n")
    return tmp_path / "checkout", marker


def test_run_this_fr_never_imports_a_planted_fr(planted: tuple[Path, Path]) -> None:
    cwd, marker = planted
    code, out = run_this_fr(["--version"], cwd)
    assert not marker.exists()
    assert code == 0 and out.strip()  # the real fr answered


def test_worktree_run_fr_never_imports_a_planted_fr(planted: tuple[Path, Path]) -> None:
    cwd, marker = planted
    code, out = Worktree(cwd).run_fr(["--version"])
    assert not marker.exists()
    assert code == 0 and out.strip()


def test_every_python_m_fr_in_the_source_is_safe_path() -> None:
    bad = []
    for path in SRC.glob("*/src/**/*.py"):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'sys\.executable,.*"-m",\s*"fr"', line) and (
                '"-P"' not in line or '"-I"' in line
            ):
                bad.append(f"{path.relative_to(SRC)}:{n}")
    assert bad == [], "use [sys.executable, '-P', '-m', 'fr', ...]: " + ", ".join(bad)


def test_the_python_floor_has_safe_path() -> None:
    text = (SRC / "fr" / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.11"' in text


# --- p4-r7 (addendum): a relative or empty PYTHONPATH entry is the cwd again ----------


@pytest.mark.parametrize("pythonpath", [":", ".", "lib", "a::b"])
def test_a_relative_pythonpath_never_imports_a_planted_fr(
    planted: tuple[Path, Path], pythonpath: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd, marker = planted
    lib = cwd / "lib" / "fr"
    lib.mkdir(parents=True)
    (lib / "__init__.py").write_text((cwd / "fr" / "__init__.py").read_text())
    (lib / "__main__.py").write_text("raise SystemExit(0)\n")
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    code, out = run_this_fr(["--version"], cwd)
    assert not marker.exists() and code == 0 and out.strip()
    code, out = Worktree(cwd).run_fr(["--version"])
    assert not marker.exists() and code == 0 and out.strip()


def test_safe_fr_env_keeps_only_absolute_pythonpath_entries() -> None:
    from fr.safe_spawn import safe_fr_env

    env = safe_fr_env({"PYTHONPATH": "/opt/a::rel:.:/opt/b", "HOME": "/h"})
    assert env["PYTHONPATH"] == "/opt/a:/opt/b" and env["HOME"] == "/h"
    assert "PYTHONPATH" not in safe_fr_env({"PYTHONPATH": ":.:lib"})
    assert "PYTHONPATH" not in safe_fr_env({})


def test_every_python_m_fr_spawn_goes_through_the_helper() -> None:
    """The argv lives in ONE place (`fr.safe_spawn.fr_argv`), and every file that spawns
    with it also builds the child env with `safe_fr_env`."""
    stray, unsafe = [], []
    for path in SRC.glob("*/src/**/*.py"):
        text = path.read_text()
        if path.name != "safe_spawn.py" and re.search(r'"-m",\s*"fr"', text):
            stray.append(str(path.relative_to(SRC)))
        if "fr_argv(" in text and "safe_fr_env(" not in text and path.name != "safe_spawn.py":
            unsafe.append(str(path.relative_to(SRC)))
    assert stray == [] and unsafe == [], (stray, unsafe)
