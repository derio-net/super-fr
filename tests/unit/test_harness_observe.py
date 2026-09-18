"""`fr.harness.observe` — what the registration files ACTUALLY wire, per
harness, per shipped hook script. 2026-09-18 harness-parity-matrix spec
§3.B, Phase 2.

The point of this module is that the parity check is *derived*, not
transcribed: `observe()` never reads `parity.yaml`, so a cell cannot agree
with itself. It reads the three registration surfaces:

- claude-code — `plugins/super-fr/hooks/hooks.json`
- hermes      — `.hermes/config.snippet.yaml`, via `fr.hermes.snippet_entries`
- opencode    — `packages/fr-opencode-plugin/src/*.ts`, via the
  `// super-fr-parity: <script>` marker comment (deliberately shallow: the
  marker IS the declaration — see spec §3.B).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.harness.model import HARNESSES, HarnessError
from fr.harness.observe import (
    OBSERVABLE_HARNESSES,
    REGISTRATION_FILES,
    is_super_fr_checkout,
    observe,
)
from fr.hermes import snippet_entries

REPO_ROOT = Path(__file__).resolve().parents[2]

HOOKS_REL = Path("plugins/super-fr/hooks")
SNIPPET_REL = Path(".hermes/config.snippet.yaml")
OPENCODE_SRC_REL = Path("packages/fr-opencode-plugin/src")


def _repo(
    tmp_path: Path,
    *,
    scripts: list[str],
    hooks_json: dict | None = None,
    snippet: str | None = None,
    index_ts: str | None = None,
) -> Path:
    """A minimal fake super-fr checkout carrying only the files `observe`
    reads. Nothing here touches the real repo (single-writer contract)."""
    hooks = tmp_path / HOOKS_REL
    hooks.mkdir(parents=True)
    for name in scripts:
        (hooks / name).write_text("#!/usr/bin/env bash\n")
    if hooks_json is not None:
        (hooks / "hooks.json").write_text(json.dumps(hooks_json))
    if snippet is not None:
        (tmp_path / SNIPPET_REL).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / SNIPPET_REL).write_text(snippet)
    if index_ts is not None:
        (tmp_path / OPENCODE_SRC_REL).mkdir(parents=True, exist_ok=True)
        (tmp_path / OPENCODE_SRC_REL / "index.ts").write_text(index_ts)
    return tmp_path


def _claude_hooks_json(*pairs: tuple[str, str]) -> dict:
    """`{event: [{hooks: [{command: ${CLAUDE_PLUGIN_ROOT}/hooks/<script>}]}]}`."""
    out: dict[str, list[dict]] = {}
    for event, script in pairs:
        out.setdefault(event, []).append(
            {"hooks": [{"type": "command", "command": f"${{CLAUDE_PLUGIN_ROOT}}/hooks/{script}"}]}
        )
    return {"hooks": out}


# --- the observable set ----------------------------------------------------


def test_only_the_three_harnesses_with_a_registration_file_are_observable() -> None:
    """codex/copilot-cli register nothing anywhere, so there is nothing to
    observe about them — `check` must never pretend otherwise."""
    assert OBSERVABLE_HARNESSES == ("claude-code", "opencode", "hermes")


def test_the_observer_table_is_the_only_place_a_harness_is_declared_observable() -> None:
    """`OBSERVABLE_HARNESSES` and `REGISTRATION_FILES` are both derived from
    the one dispatch table, so supporting codex is one entry rather than
    three lists that can drift apart."""
    assert tuple(REGISTRATION_FILES) == OBSERVABLE_HARNESSES
    assert set(OBSERVABLE_HARNESSES) <= set(HARNESSES)
    assert all(f for f in REGISTRATION_FILES.values())


def test_every_registration_file_named_in_a_finding_exists_in_this_repo() -> None:
    """A finding that points at a path nobody can open is a dead end."""
    for harness, rel in REGISTRATION_FILES.items():
        assert (REPO_ROOT / rel).is_file(), f"{harness}: {rel}"


def test_is_super_fr_checkout_is_true_here_and_false_elsewhere(tmp_path: Path) -> None:
    assert is_super_fr_checkout(REPO_ROOT)
    assert not is_super_fr_checkout(tmp_path)


# --- (a) claude-code: hooks.json -------------------------------------------


def test_claude_code_observes_every_script_named_by_any_event(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        scripts=["a.sh", "b.sh", "c.sh"],
        hooks_json=_claude_hooks_json(("SessionStart", "a.sh"), ("PreToolUse", "b.sh")),
    )
    observed = observe(root)
    assert observed["a.sh"]["claude-code"] == "present"
    assert observed["b.sh"]["claude-code"] == "present"
    assert observed["c.sh"]["claude-code"] == "absent"


def test_a_repo_with_no_hooks_json_observes_every_script_absent(tmp_path: Path) -> None:
    root = _repo(tmp_path, scripts=["a.sh"])
    assert observe(root)["a.sh"] == dict.fromkeys(OBSERVABLE_HARNESSES, "absent")


# --- (b) hermes: the snippet, parsed by fr.hermes.snippet_entries ----------

_SNIPPET = """\
hooks:
  pre_tool_call:
    - matcher: "write_file|patch"
      command: "hermes/a.sh"
      timeout: 30
  pre_llm_call:
    - command: "b.sh"
      timeout: 30
"""


def test_hermes_observes_scripts_the_snippet_registers(tmp_path: Path) -> None:
    root = _repo(tmp_path, scripts=["a.sh", "b.sh", "c.sh"], snippet=_SNIPPET)
    observed = observe(root)
    assert observed["a.sh"]["hermes"] == "present"
    assert observed["b.sh"]["hermes"] == "present"
    assert observed["c.sh"]["hermes"] == "absent"


def test_hermes_observation_is_exactly_what_snippet_entries_says(tmp_path: Path) -> None:
    """Not a second YAML walk: the observer must go through
    `fr.hermes.snippet_entries`, so the installer and the parity check can
    never disagree about what the snippet says (spec §3.B)."""
    root = _repo(tmp_path, scripts=["a.sh", "b.sh", "c.sh"], snippet=_SNIPPET)
    expected = {Path(e["command"]).name for e in snippet_entries(root, root / HOOKS_REL)}
    observed = observe(root)
    assert {s for s, per in observed.items() if per["hermes"] == "present"} == expected


def test_a_script_registered_only_on_hermes_is_present_there_and_absent_elsewhere(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, scripts=["a.sh"], snippet=_SNIPPET)
    assert observe(root)["a.sh"] == {
        "claude-code": "absent",
        "opencode": "absent",
        "hermes": "present",
    }


# --- (c) opencode: the marker comment IS the declaration -------------------


def test_opencode_observes_a_script_named_by_a_marker_comment(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        scripts=["a.sh", "b.sh"],
        index_ts="// super-fr-parity: a.sh\nexport const x = 1;\n",
    )
    observed = observe(root)
    assert observed["a.sh"]["opencode"] == "present"
    assert observed["b.sh"]["opencode"] == "absent"


def test_opencode_source_with_no_marker_observes_absent(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        scripts=["a.sh"],
        index_ts="// a plugin that ports a.sh but never says so\nexport const x = 1;\n",
    )
    assert observe(root)["a.sh"]["opencode"] == "absent"


def test_a_marker_naming_a_script_that_does_not_exist_is_an_error(tmp_path: Path) -> None:
    """A typo in a marker must not silently read as `absent` — that is a
    false clean bill of health, the failure mode this whole matrix exists
    to prevent."""
    root = _repo(
        tmp_path,
        scripts=["a.sh"],
        index_ts="// super-fr-parity: nope.sh\n",
    )
    with pytest.raises(HarnessError) as exc:
        observe(root)
    assert "nope.sh" in str(exc.value)


# --- (d) the real repo: the live facts, pinned -----------------------------


def test_the_real_repo_observes_the_acceptance_nag_present_on_hermes() -> None:
    """The live fact issue #436's table gets wrong: `.hermes/config.snippet.yaml`
    registers `fr-acceptance-nag.sh` on `pre_llm_call`."""
    assert observe(REPO_ROOT)["fr-acceptance-nag.sh"]["hermes"] == "present"


def test_the_real_repo_observes_every_shipped_hook_on_claude_code() -> None:
    observed = observe(REPO_ROOT)
    shipped = sorted(p.name for p in (REPO_ROOT / HOOKS_REL).glob("*.sh"))
    assert shipped
    assert [s for s in shipped if observed[s]["claude-code"] != "present"] == []


def test_the_real_repo_observes_isolation_required_present_on_opencode() -> None:
    """The one hook the OpenCode plugin ports — it must carry its marker, or
    the `partial` cell `parity.yaml` declares reads as drift on day one."""
    assert observe(REPO_ROOT)["fr-isolation-required.sh"]["opencode"] == "present"
