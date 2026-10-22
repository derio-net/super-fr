"""p4-isolated-python: every `python -m fr` that fr starts runs in isolated mode (`-I`),
so a checkout's own top-level `fr/` package (planted by an untrusted PR) is never
imported in place of the real fr, which then runs with the operator's credentials."""

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


def test_every_python_m_fr_in_the_source_is_isolated() -> None:
    bare = []
    for path in SRC.glob("*/src/**/*.py"):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'sys\.executable,\s*"-m",\s*"fr"', line):
                bare.append(f"{path.relative_to(SRC)}:{n}")
    assert bare == [], "use [sys.executable, '-I', '-m', 'fr', ...]: " + ", ".join(bare)
