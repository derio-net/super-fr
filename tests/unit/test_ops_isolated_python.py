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
