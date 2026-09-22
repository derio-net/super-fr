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
- **fr-goal §5** is what the orchestrator follows, and §2 used to present the
  flag as correct for cross-repo agents, so without an explicit contrast §2 read
  as precedent for §5. (That §2 premise was itself false — the flag cuts a
  worktree of the CURRENT repo; 2026-09-22 review p3r-1.)

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

import pytest
from fr.harness import ARGUMENT_VOCABULARY

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


# The constraint may be carried EITHER by the literal Claude Code flag or by
# the harness-neutral phrasing that means the same thing — see
# `test_agent_description_carries_the_constraint` for why both are accepted,
# and `test_a_merely_descriptive_description_does_not_count` for the pre-fix
# wording that must keep failing either way.
# The flag spelling is NOT restated here: `ARGUMENT_VOCABULARY` already owns
# every prose spelling of it (JSON key, `=`, backticks — review p2r-2), and a
# second regex in this module is one that drifts from it.
_ISOLATION_FLAG = ARGUMENT_VOCABULARY["claude-code"]['isolation: "worktree"']
_NEUTRAL_PHRASE = re.compile(r"\bsecond\s+worktree\b", re.IGNORECASE)

# A negation GOVERNS the phrase only when it stands directly in front of it,
# with nothing but these words in between — prepositions, articles and the
# dispatch verbs a prohibition is naturally phrased with.
_NEGATIONS = frozenset({"never", "without", "not", "no"})
_GOVERNED_FILLER = frozenset(
    {"into", "in", "a", "an", "the", "any", "pass", "passing", "use", "using", "with"}
)
_MAX_FILLER = 6
_WORD = re.compile(r"[A-Za-z']+")


def _clauses(description: str) -> list[str]:
    return re.split(r"[.;—]", description)


def _negation_governs(before: str) -> bool:
    """Walk back from the phrase over filler words; True if the first
    non-filler word, within `_MAX_FILLER` words, is a negation."""
    words = [w.lower() for w in _WORD.findall(before)]
    for distance, word in enumerate(reversed(words)):
        if word in _NEGATIONS:
            return True
        if word not in _GOVERNED_FILLER or distance >= _MAX_FILLER:
            return False
    return False


def _rules_out_a_second_worktree(description: str) -> bool:
    """True when some ONE clause names the second worktree AND a negation
    governs that name.

    The rule (2026-09-22, spec 3.E, tightened past the spec's six-word window):

    - split the description into clauses on `.`, `;` and `—`;
    - the phrase is `second worktree`, or Claude Code's isolation flag;
    - a negation token (`never|without|not|no`) must come BEFORE the phrase,
      in the same clause, with at most six words between them — and every one
      of those words must be filler (`into|in|a|an|the|any|pass|passing|
      use|using|with`). "never into a second worktree", "WITHOUT `isolation:
      \"worktree\"`", "do not pass `isolation: \"worktree\"`" and "no second
      worktree" pass.

    Why not the bare six-word window: 'Do not hesitate to pass isolation:
    "worktree"' puts `not` three words before the flag, but it negates
    *hesitate* — the sentence instructs the poisoned dispatch. Requiring only
    filler between negation and phrase is what makes the negation provably
    about the phrase. A negation AFTER the phrase ("a second worktree, not the
    shared one"; "has a second worktree is not our concern") and one in a
    different clause ('pass `isolation: "worktree"` — this is not optional')
    never count.
    """
    for clause in _clauses(description):
        for pattern in (_NEUTRAL_PHRASE, _ISOLATION_FLAG):
            for match in pattern.finditer(clause):
                if _negation_governs(clause[: match.start()]):
                    return True
    return False


def test_agent_description_carries_the_constraint() -> None:
    """The orchestrator reads `description:`, not the body, when choosing.

    Originally this demanded the *literal flag*, on the grounds that a looser
    check ("mentions isolation") passes on the pre-fix description, which
    already said "already-active fr-isolation workspace" — true, and still not
    an instruction about the flag.

    2026-09-21 (#497, agent-body-tool-neutrality) put that in direct conflict
    with the neutrality scan, which now covers agent bodies: `isolation:
    "worktree"` is Claude Code's alone, and a frontmatter `description:` cannot
    carry a `**Harness — ...:**` clause without shipping bold markdown in a YAML
    blurb every harness displays. The flag therefore left the description, and
    this assertion accepts the neutral phrasing that means the same thing.

    THIS IS NOT A #420 REGRESSION, and the two sibling tests that prove it are
    in this file: `test_fr_goal_dispatch_section_says_without_the_flag` (the
    orchestrator's actual instruction source still names the flag verbatim, in a
    scoped clause) and `test_hook_is_registered_for_the_agent_tool` (the
    enforcement). The description is the third copy, and "never a second
    worktree" is not a weaker instruction to the reader holding a flag whose
    value is literally `worktree`.
    """
    description = _front_matter_description(AGENT)
    assert _rules_out_a_second_worktree(description), (
        "fr-phase-executor's `description:` must rule out a second worktree in one "
        'sentence — naming it (`isolation: "worktree"`, or the neutral \'second '
        "worktree') AND negating it. The body is read only by the executor, after "
        "the choice is already made."
    )


def test_a_merely_descriptive_description_does_not_count() -> None:
    """Widening the accepted phrasing is only safe if the widened predicate
    still rejects prose that merely *describes* the workspace. Exercised on the
    synthetic wording the original assertion was written against, so the
    guarantee does not rest on the shipped file happening to be right."""
    assert not _rules_out_a_second_worktree(
        "Implement ONE plan phase, serially, inside an already-active fr-isolation "
        "workspace, then return a structured result."
    ), "a description that only mentions isolation must not satisfy the constraint"
    for blessed in (
        'Dispatch it WITHOUT `isolation: "worktree"`.',
        "Dispatch it INTO that workspace, never into a second worktree.",
    ):
        assert _rules_out_a_second_worktree(blessed), (
            f"a real prohibition must satisfy the constraint: {blessed}"
        )


# 2026-09-22 adversarial review (#532 repair, spec 3.E): each of these names the
# second worktree AND carries a negation in the same sentence, so a
# sentence-level co-occurrence check accepted all four. None forbids anything.
_NEGATION_ELSEWHERE = (
    "Dispatch it with a second worktree, not the shared one.",
    'Pass `isolation: "worktree"` — this is not optional.',
    'Do not hesitate to pass isolation: "worktree".',
    "Knowing whether it has a second worktree is not our concern.",
)


@pytest.mark.parametrize("description", _NEGATION_ELSEWHERE)
def test_a_negation_that_does_not_govern_the_phrase_does_not_count(description: str) -> None:
    assert not _rules_out_a_second_worktree(description), (
        f"the negation here does not govern the second-worktree phrase: {description}"
    )


@pytest.mark.parametrize(
    "description",
    [
        pytest.param(_front_matter_description(AGENT), id="shipped-description"),
        pytest.param('Dispatch it WITHOUT `isolation: "worktree"`.', id="pre-532-literal-flag"),
        pytest.param('Do not pass `isolation: "worktree"` to it.', id="do-not-pass-the-flag"),
        pytest.param("It needs no second worktree.", id="no-second-worktree"),
    ],
)
def test_a_governing_negation_counts(description: str) -> None:
    assert _rules_out_a_second_worktree(description), (
        f"a real prohibition must satisfy the constraint: {description}"
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
# Same vocabulary pattern as `_rules_out_a_second_worktree` — one definition
# of what spells the flag, not two.
_FLAG = _ISOLATION_FLAG


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
