"""Print one GitHub Actions `::error` annotation per failed or errored test in a
JUnit XML report, so a failure is readable through the check-run annotations API
where the job log is not (a Claude Code cloud session cannot fetch job logs).

Usage: junit_annotations.py <junit.xml>. Exits 0: the test step already failed
the job; this step only reports. At most MAX annotations (GitHub keeps 10 error
annotations per step), then a count of the rest.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX = 10


def _escape(text: str) -> str:
    """GitHub's workflow-command escaping for a message (`%`, CR, LF)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def failures(report: Path) -> list[tuple[str, str]]:
    """(test id, first lines of the failure) for each failed or errored case."""
    found: list[tuple[str, str]] = []
    for case in ET.parse(report).getroot().iter("testcase"):
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is None:
                continue
            test = f"{case.get('classname', '')}::{case.get('name', '')}"
            detail = (node.get("message") or node.text or kind).strip()
            found.append((test, "\n".join(detail.splitlines()[:12])))
    return found


def main(argv: list[str]) -> int:
    report = Path(argv[1]) if len(argv) > 1 else Path("junit-shard.xml")
    if not report.exists():
        print(f"::error title=no junit report::{report} was not written")
        return 0
    found = failures(report)
    for test, detail in found[:MAX]:
        print(f"::error title={_escape(test)}::{_escape(detail)}")
    if len(found) > MAX:
        print(f"::error title={len(found) - MAX} more failures::see the job log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
