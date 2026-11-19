"""R8: every action a scaffolded workflow uses is pinned by commit SHA, and the GitHub
pins are the ones super-fr's own CI runs (spec 2026-11-18-consumer-delivery)."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest
from fr.acceptance.pin import FrPin
from fr.acceptance.scaffold import ACTION_PINS, render_workflow

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN = FrPin("0123456789abcdef0123456789abcdef01234567", "v8.1.5")
CI_TYPES = ("github-actions", "gitea-actions", "gitlab-ci")
USES = re.compile(r"^\s*(?:- )?uses: (?P<action>\S+?)@(?P<ref>\S+)(?P<tail>.*)$")
PINNED = re.compile(r" # v\d+\.\d+\.\d+$")


def _combos() -> list[tuple[str, bool, bool, bool]]:
    return [
        (ci, debt, pages, comment)
        for ci, debt, pages, comment in itertools.product(
            CI_TYPES, (True, False), (True, False), (True, False)
        )
        if not (ci != "github-actions" and comment)
        if not (ci == "gitea-actions" and pages)
    ]


@pytest.mark.parametrize(("ci", "debt", "pages", "comment"), _combos())
def test_every_uses_line_is_a_sha_pin_with_a_version(
    ci: str, debt: bool, pages: bool, comment: bool
) -> None:
    text = render_workflow(ci, debt=debt, pages=pages, comment=comment, fr_pin=PIN)
    lines = [m for line in text.splitlines() if (m := USES.match(line))]
    assert bool(lines) == (ci != "gitlab-ci")
    for m in lines:
        assert re.fullmatch(r"[0-9a-f]{40}", m["ref"]), m.string
        assert PINNED.search(m["tail"]), m.string


def _own_pins() -> dict[str, tuple[str, str]]:
    pins: dict[str, tuple[str, str]] = {}
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml")):
        for m in re.finditer(
            r"uses:\s*(\S+?)@([0-9a-f]{40})\s*#\s*(v\d+\.\d+\.\d+)", wf.read_text()
        ):
            pins[m.group(1)] = (m.group(2), m.group(3))
    return pins


def test_github_pins_equal_the_pins_of_super_frs_own_ci() -> None:
    own = _own_pins()
    for (action, ci), (sha, version) in ACTION_PINS.items():
        if ci != "github-actions":
            continue
        assert action in own, f"{action} is pinned for consumers but super-fr's CI does not use it"
        assert own[action] == (sha, version), f"{action}: consumer pin differs from super-fr's own"


def test_gitea_keeps_the_older_majors() -> None:
    assert ACTION_PINS[("actions/checkout", "gitea-actions")][1].startswith("v4.")
    assert ACTION_PINS[("astral-sh/setup-uv", "gitea-actions")][1].startswith("v5.")


def test_every_action_a_template_names_has_a_pin() -> None:
    for ci, *_ in [(c,) for c in ("github-actions", "gitea-actions")]:
        text = render_workflow(
            ci, debt=True, pages=ci == "github-actions", comment=ci == "github-actions", fr_pin=PIN
        )
        for m in re.finditer(r"uses: (\S+?)@", text):
            assert (m.group(1), ci) in ACTION_PINS
