"""The drive pass stays pure (spec 2026-11-18-triage-pages-ux R6): `batch_drive.py` reads no
clock, runs no process and imports no git seam; the clock is passed in. The check is over
the module's syntax tree, so a spelling a text search misses is still found."""

from __future__ import annotations

import ast
from pathlib import Path

from fr.triage import batch_drive

BANNED_MODULES = {"time", "subprocess", "fr.triage.gitseam", "fr.gh", "fr.hostclient"}
BANNED_CALLS = {"now", "utcnow", "today", "time", "monotonic", "perf_counter", "system", "popen"}


def impurities(source: str) -> list[str]:
    """What in *source* reads a clock, starts a process or reaches git, as `line: what`."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names = [base, *(f"{base}.{a.name}" for a in node.names)]
            if base == "os" and any(a.name in {"system", "popen"} for a in node.names):
                found.append(f"{node.lineno}: from os import a process call")
        for name in names:
            if name in BANNED_MODULES or name.split(".")[0] in {"time", "subprocess"}:
                found.append(f"{node.lineno}: imports {name}")
        if isinstance(node, ast.Call):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if called in BANNED_CALLS:
                found.append(f"{node.lineno}: calls {called}()")
    return found


def test_the_drive_pass_reads_no_clock_and_starts_no_process() -> None:
    assert impurities(Path(batch_drive.__file__).read_text(encoding="utf-8")) == []


def test_the_checker_finds_each_kind_of_impurity() -> None:
    impure = """
import time
import subprocess as sp
from datetime import datetime
from fr.triage.gitseam import Checkout
from os import system

def f():
    a = datetime.now()
    b = datetime.utcnow()
    c = datetime.date.today()
    d = time.time()
"""
    found = impurities(impure)
    for needle in ("imports time", "imports subprocess", "imports fr.triage.gitseam",
                   "from os import", "calls now()", "calls utcnow()", "calls today()",
                   "calls time()"):  # fmt: skip
        assert any(needle in line for line in found), (needle, found)


def test_a_pure_source_passes() -> None:
    assert (
        impurities("from datetime import datetime\n\ndef f(now: datetime):\n    return now\n") == []
    )
