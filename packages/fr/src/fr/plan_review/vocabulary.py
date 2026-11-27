"""The plan self-review's lint vocabulary: regexes, phrase tables and text helpers
(moved from `fr.plan_ops`, spec 2026-11-27-plan-ops-split R2)."""

from __future__ import annotations

import re
from collections.abc import Iterator

from fr.types import PhaseDoc, Step

# Agentic-purity gate (#252): a skipped (`state: '-'`) step in an AGENTIC
# phase whose note defers it forward is a mis-scoped manual step — an
# agentic phase must be fully agent-completable. The note either names a
# later phase ("Executed in Phase 5") or uses a defer-phrase.
_PHASE_REF_NOTE_RE = re.compile(r"[Pp]hase\s+(\d+)")
_DEFER_PHRASES = ("defer", "executed in", "moved to")

# Part 2 of the gate: manual-operation language in a pending agentic step.
# Deliberately conservative (precision over recall) — the deferred-step
# lint above is the load-bearing detector; this one catches the authoring
# mistake before any deferral happens. Word-boundary, case-insensitive.
_MANUAL_VERB_RES = tuple(
    re.compile(rf"\b{phrase}\b", re.IGNORECASE)
    for phrase in (
        "manually",
        "by hand",
        "via the UI",
        "in the UI",
        "click",
        "SOPS",
        "operator sets",
        "operator provides",
    )
)


# Agentic dispatch-verb gate (#428). `fr-phase-executor` is a leaf on both
# harnesses — Claude Code omits `Agent` from its frontmatter tool grant,
# OpenCode sets `task: deny` — so a step telling it to dispatch a subagent
# is unexecutable by construction. The honest executor does the nearest
# thing it can, reports the deviation, and ticks anyway; the plan then
# records completion for work nobody performed as written (spec §2.E).
#
# Precision is the whole design problem: super-fr is a repo ABOUT dispatch.
# #428's literal proposal `\bdispatch(es|ed|ing)?\b` scores 292 hits across
# this repo's own plan corpus (the bare stem alone scores 262) and every
# one is a false positive (spec §2.D measured 237 on the smaller enforcing
# read) — at error severity the gate would be switched
# off within a week. Both patterns below score ZERO over all 2113 agentic
# steps of that corpus, ticked and pending alike, pinned by
# `tests/unit/test_dispatch_lint_corpus.py`.
#
# "Both patterns, over ALL steps" is the claim that matters and it is the
# one that was nearly shipped false: the first cut added a frameless
# `subagent_type[:=]` arm, which hit a real live plan
# (`2026-09-19-opencode-subagent-dispatch` P4.T1.S2). The corpus test
# stayed green only because that step is ticked and the gate exempts
# ticked steps — so the measurement has to be taken over every step, not
# over the subset the gate happens to look at today.

# Bare imperatives only. An inflected form (`dispatches`, `spawning`) is a
# verb in the indicative or a gerund — it DESCRIBES. The boundary anchors
# position; the bare stem is what anchors mood, and the two together are
# what separate "Dispatch the cold-reader agent" from "Note: dispatch is
# described in the agent docs".
_DISPATCH_VERB = r"""(?:
      dispatch
    | delegate\s+to
    | spawn
    | hand\s+off\s+to
    | fan\s+out\s+to
)\b"""
# The trailing `\b` is load-bearing, not tidiness: without it the stem
# `dispatch` matches the PREFIX of `dispatching`, the window swallows the
# suffix, and the bare-stem rule silently buys nothing — "Add a test:
# dispatching to the fr-phase-executor agent is refused" was flagged.

# ...and the verb must not be followed by a copula, a modal or `of`, all
# of which turn the stem back into a subject or a noun: "dispatch IS
# described", "dispatch OF a subagent belongs in a [manual] phase".
_NOT_A_PREDICATE = r"""(?!\s+(?:
      of|is|are|was|were|isn't|aren't
    | can|cannot|can't|could|should|must|may|might|will|would
    | does|do|did|has|have|had
    | means|happens|occurs|belongs|remains|stays
)\b)"""

# An agent-shaped OBJECT. Every arm requires a ROLE WORD: without one, a
# bare `word:word` token re-admits the 42-hit false-positive class §2.D
# measured (`plan:my-slug`, `fr:synced`, `fr.tracker:GithubTracker`,
# `start:end`, `cli:app`).
_AGENT_ROLE = r"(?:sub-?agents?|agents?|executors?|researchers?|reviewers?|readers?)"
_ROLE_STEM = r"(?:agent|executor|researcher|reviewer|reader)"
_AGENT_OBJECT = rf"""(?:
      `[\w.-]+:[\w.-]*{_ROLE_STEM}[\w.-]*`
    | \b[\w.-]+:[\w.-]*{_ROLE_STEM}[\w.-]*\b
    | \b{_AGENT_ROLE}\b
)"""
# Arm 1 (backticked) is not subsumed by arm 3 even though arm 3 would
# also match `researcher` inside it: it is what makes the reported match
# the COMPLETE token an author can recognise —
# "Dispatch `blog-craft:post-researcher`" rather than a truncation
# missing its closing backtick. Arm 2 catches the glued form
# (`blog-craft:postresearcher`), where arm 3's word boundary fails. Both
# are pinned by tests; delete either and a test goes red.

# An INSTRUCTION BOUNDARY is start-of-text, real sentence punctuation
# followed by whitespace, or a list marker starting a line — NEVER a bare
# newline. Plan step text is hard-wrapped prose, so a bare-newline
# boundary lets a SOFT WRAP fake an imperative: measured over the corpus,
# it flagged this feature's own phase-3 step for saying "...spawn or\nhand
# off to a subagent is a BLOCKER", which describes the contract and
# instructs nothing. A list item is a fresh instruction and keeps its
# anchor; a wrap is a formatting artifact and must not create one.
#
# Two refinements on the punctuation arm, both from measurement:
#   * the trailing `\s+`, without which the ellipsis in `"...spawn` reads
#     as a sentence start;
#   * the abbreviation lookbehinds, because `e.g.`, `i.e.`, `etc.`, `cf.`
#     and `vs.` all satisfy `(?<=[.;:!?])\s+` while continuing the same
#     sentence — "Cf. dispatch to the fr-phase-executor agent" is a
#     cross-reference, not an instruction.
_INSTRUCTION_BOUNDARY = r"""(?:
      \A\s*
    | (?<=[.;:!?])(?<!e\.g\.)(?<!i\.e\.)(?<!etc\.)(?<!cf\.)(?<!vs\.)\s+
    | ^[ \t]*(?:[-*+]|\d+[.)])[ \t]+
)"""

_CONNECTIVE = r"(?:(?:then|and|next|finally|also)\s+)?"

# Pattern 1 — imperative-head dispatch verb with an agent-shaped object
# within ~60 characters of the SAME LINE. The head anchor is what buys the
# precision: it separates INSTRUCTING the executor to dispatch from
# DESCRIBING dispatch, which is what every measured false positive
# ("implement `fr_dispatch.tick()` so it dispatches phases to the runner")
# was doing.
#
# `\n` is excluded from the window deliberately, and it costs recall: a
# verb and its object split by a hard wrap ("Dispatch the\ncold-reader
# agent") is NOT flagged. That is the priced trade — the same window
# spanning newlines lets an object on an unrelated wrapped line manufacture
# a hit, which is the soft-wrap defect one level down. Precision first: a
# gate that fires on prose gets switched off, a gate that misses a wrapped
# instruction still catches the next unwrapped one.
_RE_DISPATCH_HEAD = re.compile(
    _INSTRUCTION_BOUNDARY
    + _CONNECTIVE
    + _DISPATCH_VERB
    + _NOT_A_PREDICATE
    + r"[^.;:!?\n]{0,60}?"
    + _AGENT_OBJECT,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

# Pattern 2 — the explicit mechanism, in an instructional frame, behind
# the SAME instruction boundary as pattern 1. Bare `Agent tool` / `Task
# tool` are ordinary nouns in a repo that documents dispatch: measured
# over the corpus the nominal form flagged 3 steps, all 3 of them this
# feature's own plan describing what the executor lacks. Anchoring and
# bare-stem mood are both needed — "Explain why calling the Agent tool is
# impossible here" is phase 4's own work, and it is not an instruction to
# dispatch.
#
# Arm A requires a NON-EMPTY modifier between `the` and the role word,
# which is what distinguishes naming an agent ("Use the fr-phase-executor
# agent") from using `agent` as a modifier ("Use the agent frontmatter in
# plugins/super-fr/agents/fr-phase-executor.md" — phase 3's own step).
# Arm B is the fixed tool token.
#
# There is deliberately NO frameless `subagent_type[:=]` arm. In YAML and
# in markdown that token is a KEY NAME — a mention, not a call site — and
# a frameless arm hit a legitimate live plan on the corpus. The framed
# form still catches "Call the Task tool with subagent_type:
# general-purpose", so recall for the real instruction survives.
_RE_DISPATCH_MECHANISM = re.compile(
    _INSTRUCTION_BOUNDARY
    + _CONNECTIVE
    + r"""(?:use|call|invoke)\s+the\s+(?:
          (?:[^\s.;:!?]+[ \t]+){1,3}"""
    + _AGENT_ROLE
    + r"""\b
        | (?:Task|Agent)[ \t]+tools?\b
    )""",
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

_DISPATCH_RES = (_RE_DISPATCH_HEAD, _RE_DISPATCH_MECHANISM)

# Fenced code blocks are content being WRITTEN, not an instruction to the
# executor, so they are stripped before the scan. Inline backticks are
# deliberately NOT stripped: the backticked agent name IS the object the
# detector keys on, and removing it turns the observed defect
# "Dispatch `blog-craft:post-researcher` per post" into "Dispatch   per
# post" — the detector goes blind on the one case it exists for (spec
# §4.A).
#
# The opening run is CAPTURED and back-referenced, because a fence is
# closed by a run at least as long as its opener. Matching any ``` as a
# closer mis-pairs a ````-fenced block that quotes a ```-fenced one — and
# a ````markdown block quoting a rejected plan step is exactly the shape
# phases 3 and 4 must write into SKILL.md. The mis-pairing does not merely
# strip too little: it UN-FENCES the quoted instruction, so the gate fires
# on a step that is only quoting the thing it forbids.
#
# An unterminated fence strips to end of text. For a precision-first gate
# that is the safer reading of an ambiguous document: an author who opened
# a block meant everything after it to be content.
_FENCED_CODE_RE = re.compile(
    r"^[ \t]*(`{3,})[^\n]*\n"  # opening run (captured) + info string
    r".*?"  # content
    r"(?:^[ \t]*\1`*[ \t]*$|\Z)",  # a run at least as long, or end of text
    re.DOTALL | re.MULTILINE,
)


def _strip_fenced_code(text: str) -> str:
    """Remove fenced code blocks. Inline backticks survive, by design."""
    return _FENCED_CODE_RE.sub("\n", text)


def _note_defers_forward(note: str, phase_number: int) -> bool:
    """True iff `note` defers execution beyond `phase_number`.

    An explicit phase reference decides outright: forward ("Executed in
    Phase 5" on phase 3) is deferral; backward ("ported from Phase 1") is
    history and disarms the defer-phrases. Only refless notes fall through
    to the phrase scan.
    """
    m = _PHASE_REF_NOTE_RE.search(note)
    if m:
        return int(m.group(1)) > phase_number
    lowered = note.lower()
    return any(phrase in lowered for phrase in _DEFER_PHRASES)


def _not_ticked_steps(phase: PhaseDoc) -> Iterator[Step]:
    """Every not-yet-ticked step of `phase`, in document order.

    The single walk both per-step detectors of the agentic-purity gate
    consume (#252's manual-verb scan and #428's dispatch scan). They share
    an exemption — a completed (`'x'`) step is a claim of performance that
    already happened, so neither gate retro-errors on it — and sharing the
    walk is what stops a future change to that exemption from applying to
    one detector and not the other.
    """
    for task in phase.tasks:
        for step in task.steps:
            state = phase.state.steps.get(step.id)
            if state is not None and state.state == "x":
                continue
            yield step
