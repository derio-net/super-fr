"""CI tripwire: nothing super-fr ships may instruct the poisoned dispatch (#420).

`fr-phase-executor` runs inside the fr-isolation worktree fr-goal already
created. Dispatching it WITH `isolation: "worktree"` puts it in a *second*,
locked worktree cut from `main`, where the spec/plan are invisible, Bash is
denied by fr-isolation-guard.sh and Write/Edit by fr-isolation-required.sh —
and the dispatch still succeeds, so the failure is silent.

Three shipped surfaces have to agree, and each has already drifted once:

- the **hook** is the enforcement (`fr-phase-executor-guard.sh`), and it is
  worthless unregistered;
- the agent's **`description:`** is what the orchestrator reads when choosing —
  the constraint sat in the body, which only the executor itself reads;
- **fr-goal §6** is what the orchestrator follows, and §3 uses the flag
  *correctly*, so without an explicit contrast §3 reads as precedent for §6.

A fourth surface carries the carve-out to the harnesses the hook can't reach:
`plugins/super-fr/rules/fr-isolation-required.md` is the ONE file that ships to
all three — `~/.claude/rules/` via install.sh, `.opencode/instructions/` via
sync-opencode.py, and `~/.hermes/SOUL.md` via sync-hermes.py's managed block.
It also *names* `agent-worktree-default.md`, the org rule that instructs the
harmful default, so without the carve-out super-fr's own rule endorses it
unqualified.

Prose drifts; this fails loud when it does. Style follows
`test_tripwire_claude_p.py`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins" / "super-fr"
HOOK = PLUGIN / "hooks" / "fr-phase-executor-guard.sh"
AGENT = PLUGIN / "agents" / "fr-phase-executor.md"
FR_GOAL = PLUGIN / "skills" / "fr-goal" / "SKILL.md"
RULE = PLUGIN / "rules" / "fr-isolation-required.md"
REPO_RULE_MIRROR = REPO_ROOT / ".claude" / "rules" / "fr-isolation-required.md"
OPENCODE_RULE = REPO_ROOT / ".opencode" / "instructions" / "fr-isolation-required.md"
HERMES_RULES = REPO_ROOT / ".hermes" / "SOUL.d" / "super-fr-rules.md"


def _front_matter_description(path: Path) -> str:
    """The agent's `description:` block — a YAML `>`-folded scalar."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no front matter"
    front = text.split("\n---\n", 1)[0]
    match = re.search(r"^description:\s*>?\s*\n((?:  .*\n)+)", front + "\n", re.MULTILINE)
    assert match, f"{path} has no folded `description:` block"
    return " ".join(line.strip() for line in match.group(1).splitlines())


def test_hook_is_registered_for_the_agent_tool() -> None:
    data = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
    commands = {
        h["command"]
        for entry in data["hooks"]["PreToolUse"]
        if "Agent" in (entry.get("matcher") or "").split("|")
        for h in entry["hooks"]
    }
    assert "${CLAUDE_PLUGIN_ROOT}/hooks/fr-phase-executor-guard.sh" in commands, (
        "the refusal hook must be registered under a PreToolUse matcher covering "
        "the `Agent` subagent tool — "
        "unregistered, it is inert and the poisoned dispatch succeeds silently"
    )


def test_hook_ships_and_is_executable() -> None:
    assert HOOK.is_file(), f"missing {HOOK}"
    assert os.access(HOOK, os.X_OK), f"not executable: {HOOK}"


def test_agent_description_carries_the_constraint() -> None:
    """The orchestrator reads `description:`, not the body, when choosing.

    The assertion demands the *literal flag* and a negation within the same
    sentence. A looser check ("mentions isolation") passes on the pre-fix
    description, which already says "already-active fr-isolation workspace" —
    true, and still not a instruction about the flag.
    """
    description = _front_matter_description(AGENT)
    assert 'isolation: "worktree"' in description, (
        "fr-phase-executor's `description:` must name the flag verbatim — the "
        "body is read only by the executor, after the choice is already made"
    )
    sentence = next(
        s for s in re.split(r"(?<=[.;])\s+", description) if 'isolation: "worktree"' in s
    )
    assert re.search(r"\bwithout\b|\bnever\b|\bdo not\b|\bnot\b", sentence, re.IGNORECASE), (
        f"the sentence naming the flag must rule it OUT, not merely mention it: got {sentence!r}"
    )


def _dispatch_section(text: str) -> str:
    """The section that dispatches `fr-phase-executor`, located by CONTENT.

    This originally split on a hardcoded `### 6.`. When fr-goal became
    manifest-driven the pipeline was renumbered (dispatch moved to §5, the
    cross-repo case into §2) and the hardcoded number silently stopped naming
    the section it meant — the tripwire went red for the right reason but the
    wrong cause. A section number is itself prose that drifts; the agent name
    is the thing this file is actually about, so anchor on that.
    """
    sections = re.split(r"(?m)^### ", text)
    hits = [s for s in sections if "fr-phase-executor" in s]
    assert len(hits) == 1, (
        f"expected exactly one fr-goal section dispatching fr-phase-executor, found {len(hits)}"
    )
    return hits[0]


def test_fr_goal_dispatch_section_says_without_the_flag() -> None:
    body = _dispatch_section(FR_GOAL.read_text(encoding="utf-8"))
    assert 'isolation: "worktree"' in body, (
        "the dispatch section must name the flag it is ruling out"
    )
    assert re.search(r"without\b[^\n]*isolation|isolation[^\n]*\bwithout\b", body, re.IGNORECASE), (
        '§6 must say to dispatch WITHOUT `isolation: "worktree"`'
    )


def test_shipped_rule_carries_the_carve_out() -> None:
    """The rule is the only surface reaching Claude Code, OpenCode AND Hermes.

    It also names `agent-worktree-default.md` — the org rule that instructs the
    harmful default — so without the carve-out super-fr's own shipped rule
    endorses it unqualified on every host.
    """
    text = RULE.read_text(encoding="utf-8")
    assert "agent-worktree-default" in text, "precondition: the rule cites the org convention"
    assert "fr-phase-executor" in text, (
        "the shipped rule must name the one agent exempted from the always-pass-the-flag default"
    )
    assert 'isolation: "worktree"' in text


def test_repo_rule_mirror_carries_the_carve_out() -> None:
    """`.claude/rules/fr-isolation-required.md` is hand-maintained — no script
    regenerates it (AGENTS.md flags it as the one exception), so it silently
    drifts from the plugin rule unless something checks."""
    assert "fr-phase-executor" in REPO_RULE_MIRROR.read_text(encoding="utf-8")


def test_carve_out_reaches_opencode_and_hermes() -> None:
    """Both generated rule mirrors must carry it. The sync tripwires prove the
    mirrors match their source; this proves the *content* actually arrives —
    a rule that never mentioned it would keep both of those green."""
    assert "fr-phase-executor" in OPENCODE_RULE.read_text(encoding="utf-8"), (
        "sync-opencode.py must have carried the carve-out into .opencode/instructions/"
    )
    assert "fr-phase-executor" in HERMES_RULES.read_text(encoding="utf-8"), (
        "sync-hermes.py must have carried the carve-out into the SOUL.md managed block"
    )


def test_fr_goal_contrasts_the_correct_use_of_the_flag() -> None:
    """Another section passes the flag correctly (one fresh pipeline per repo).
    Without an explicit contrast, a reader takes that as precedent for the
    dispatch section — the exact misreading #420 reports. The cross-reference is
    asserted by shape (`§N` / `step N`) rather than a fixed number, so a future
    renumbering cannot quietly drop the contrast while staying green."""
    body = _dispatch_section(FR_GOAL.read_text(encoding="utf-8"))
    assert re.search(r"§\s*\d|\bstep\s+\d", body, re.IGNORECASE), (
        "the dispatch section must point at the section that uses the flag "
        "correctly, so the precedent cannot be misread"
    )


# --- Spec §E, fifth bullet: "no shipped skill/agent instructs dispatching this
# agent *with* the flag". The other four bullets assert that specific surfaces
# say the right thing; this is the only NEGATIVE scan, and so the only one that
# catches a NEW or edited surface reintroducing the instruction the #420 work
# removed from three places. Without it, every existing tripwire stays green
# while a freshly-added skill re-poisons the dispatch. (rev2-f9)

SHIPPED_PROSE = sorted(
    {
        *(REPO_ROOT / "plugins").glob("*/skills/**/SKILL.md"),
        *(REPO_ROOT / "plugins").glob("*/agents/*.md"),
        *(REPO_ROOT / ".opencode" / "skills").glob("**/SKILL.md"),
        *(REPO_ROOT / ".hermes" / "skills").glob("**/SKILL.md"),
    }
)

# A sentence may pair the agent with the flag only to forbid the pairing.
_NEGATED = re.compile(
    r"without|\bnot\b|\bno\b|never|refus|mutually exclusive|wrong|instead of|deadlock",
    re.IGNORECASE,
)
_FLAG = re.compile(r'isolation:\s*[`"\']?worktree', re.IGNORECASE)


def _sentences(text: str) -> list[str]:
    """Crude sentence/blocks split — enough to keep a nearby negation attached
    to the clause it negates, which a whole-file scan would lose."""
    return re.split(r"(?<=[.!?;])\s+|\n\s*\n+|\n(?=\s*[-*#|])", text)


def test_no_shipped_prose_instructs_the_poisoned_dispatch() -> None:
    assert SHIPPED_PROSE, "found no shipped skills/agents to scan — glob is wrong"
    offenders = []
    for path in SHIPPED_PROSE:
        text = path.read_text(encoding="utf-8")
        if "fr-phase-executor" not in text:
            continue
        for sentence in _sentences(text):
            if "fr-phase-executor" not in sentence or not _FLAG.search(sentence):
                continue
            if _NEGATED.search(sentence):
                continue
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {' '.join(sentence.split())[:200]}")

    assert not offenders, (
        "shipped prose appears to instruct dispatching fr-phase-executor WITH "
        'isolation: "worktree" — the combination deadlocks the agent (super-fr#420).\n'
        + "\n".join(offenders)
    )


def test_the_scan_is_not_vacuous() -> None:
    """A negative scan that passes over compliant files proves nothing unless
    the detector fires on a violation. Exercise it on synthetic prose so the
    guarantee does not rest on the shipped files happening to be clean."""
    poisoned = 'Dispatch super-fr:fr-phase-executor with isolation: "worktree" so it is isolated.'
    assert _FLAG.search(poisoned), "the flag pattern must match the shape it hunts"
    assert not _NEGATED.search(poisoned), "an instruction must not read as a prohibition"

    for blessed in (
        'Dispatch fr-phase-executor WITHOUT isolation: "worktree".',
        'fr-phase-executor must never be dispatched with isolation: "worktree".',
        'The two are mutually exclusive: fr-phase-executor + isolation: "worktree" deadlocks.',
    ):
        assert _FLAG.search(blessed) and _NEGATED.search(blessed), (
            f"legitimate prohibition would be reported as an offender: {blessed}"
        )
