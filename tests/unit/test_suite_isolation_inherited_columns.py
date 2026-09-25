"""An inherited `COLUMNS` must not freeze fr's module-level consoles.

Found on PR #615's first CI run: under `pytest -n auto` on Linux, four CLI tests
saw rich wrap at 80 columns although `tests/conftest.py` pins `COLUMNS=200` per
test. The chain:

1. pytest's capture plugin runs `_readline_workaround()`, i.e. `import readline`,
   in the MAIN process.
2. GNU readline (Linux; macOS's libedit does not) then `setenv`s `COLUMNS=80`
   and `LINES=24` at the C level — invisible to that process's `os.environ`.
3. execnet starts every xdist worker with `Popen(args)`, no `env=`, so the
   worker inherits them and starts with `COLUMNS=80` in `os.environ`.
4. `fr.commands.*` build `Console()` singletons at import, i.e. at collection;
   rich snapshots `COLUMNS` into `_width` in `Console.__init__`, so they are
   frozen at 80 and never see the per-test 200.

Serial runs never had it in `os.environ`, so their consoles read the width live.
The inner session below hands the worker's inherited `COLUMNS=80` to a copy of
the REAL conftest and checks a real fr console still follows the per-test pin.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"

PROBE = """
from fr.commands import journal_cmd


def test_console_follows_the_per_test_width():
    assert journal_cmd.err_console.width == 200, (
        f"frozen at import: _width={journal_cmd.err_console._width!r}"
    )
"""


def test_an_inherited_columns_does_not_freeze_module_consoles(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "conftest.py").write_text(CONFTEST.read_text())
    (tmp_path / "test_probe.py").write_text(PROBE)
    env = {**os.environ, "COLUMNS": "80", "LINES": "24"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:xdist",
            "-p",
            "no:cov",
            "--rootdir",
            str(tmp_path),
            str(tmp_path / "test_probe.py"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout, result.stdout
