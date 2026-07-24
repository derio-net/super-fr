"""CI tripwire: .hermes/config.snippet.yaml must reference real hook scripts.

`fr hermes install` merges this snippet's `hooks:` block into the user's Hermes
`config.yaml`, rewriting each `command` to an absolute path under the
installed hooks dir. Every (event, matcher, command) triple here must therefore
name a hook script that actually ships under plugins/super-fr/hooks/, and the
expected four registrations (edit gate, bash guard, push guard, session nag)
must all be present — else install would wire a dangling command.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / ".hermes" / "config.snippet.yaml"
HOOKS_DIR = REPO_ROOT / "plugins" / "super-fr" / "hooks"


def _entries() -> list[tuple[str, str | None, str, int | None]]:
    data = yaml.safe_load(SNIPPET.read_text())
    out: list[tuple[str, str | None, str, int | None]] = []
    for event, entries in (data.get("hooks") or {}).items():
        for entry in entries:
            out.append((event, entry.get("matcher"), entry["command"], entry.get("timeout")))
    return out


def test_every_command_names_a_real_shipped_script() -> None:
    for event, _matcher, command, _timeout in _entries():
        script = HOOKS_DIR / command
        assert script.is_file(), f"{event}: command {command!r} has no shipped script at {script}"


def test_expected_registrations_present() -> None:
    triples = {(event, matcher, command) for event, matcher, command, _timeout in _entries()}
    expected = {
        ("pre_tool_call", "write_file|patch", "hermes/fr-isolation-required.sh"),
        ("pre_tool_call", "terminal|execute_code", "hermes/fr-isolation-guard.sh"),
        ("pre_tool_call", "terminal|execute_code", "hermes/fr-merged-pr-push-guard.sh"),
        ("pre_llm_call", None, "fr-acceptance-nag.sh"),
    }
    assert expected <= triples, f"missing registrations: {expected - triples}"


def test_every_registration_has_a_positive_timeout() -> None:
    for event, _matcher, command, timeout in _entries():
        assert isinstance(timeout, int) and timeout > 0, f"{event}: {command} has invalid timeout"
