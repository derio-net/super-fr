"""Plan parser — regex-driven, supports both flat and phased formats.

Produces a frozen Plan AST from a markdown file.  Body content between
headers is preserved as raw strings for lossless round-trip.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Literal, cast

from fr.plan.format import PlanFormat, detect
from fr.plan.models import Phase, Plan, Step, Task

_TagType = Literal["manual", "agentic"]

# --- Header field patterns ---

_RE_TITLE = re.compile(r"^# (.+)$", re.MULTILINE)
_RE_SPEC = re.compile(r"^\*\*Spec:\*\*\s*`([^`]+)`", re.MULTILINE)
_RE_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE)
_RE_GOAL = re.compile(r"^\*\*Goal:\*\*\s*(.+)$", re.MULTILINE)

# --- Structural patterns ---

_RE_PHASE = re.compile(r"^## Phase (\d+):\s*(.+?)(?:\s+\[(agentic|manual)\])?\s*$", re.MULTILINE)
_RE_TASK = re.compile(r"^### Task (\d+):\s*(.+?)(?:\s+\[(agentic|manual)\])?\s*$", re.MULTILINE)
# Step header. Real-world v1 plans use four variants of step headers:
#   1. ``- [x] **Step 1: title**``               — checkbox + title inside bold
#   2. ``- [x] **Step 1:** title``               — checkbox + bold prefix only
#   3. ``**Step 1: title**``                     — bare bold-paragraph step
#   4. ``**Step 1:** title``                     — bare bold-prefix step
# Without the optional checkbox prefix and the two title-position cases,
# bold-paragraph plans (e.g. frank's argocd-infrastructure) silently parsed
# as ``steps: []`` and the v1→v2 migrator emitted empty phase yamls.
#
# Groups:
#   1 = checkbox state char (None when no checkbox)
#   2 = step number (or dotted label)
#   3 = title-inside-bold (when ``**Step N: title**``)
#   4 = trailing prose after the closing ``**`` (variants 1, 3)
#   5 = title-after-bold (when ``**Step N:** title``, variants 2, 4)
_RE_STEP = re.compile(
    r"^(?:- \[([x \-])\] )?"  # 1: optional checkbox
    r"\*\*Step (\d+(?:\.\d+)*):"  # 2: step number
    r"(?:"
    r"\s*(.+?)\*\*[ \t]*(.*?)"  # 3,4: title inside bold + trailing
    r"|"
    r"\*\*[ \t]*(.*?)"  # 5: title after closing **
    r")[ \t]*$",
    re.MULTILINE,
)
_RE_TRACKING = re.compile(r"^<!-- Tracking:\s*(https?://\S+)\s*-->", re.MULTILINE)
_RE_FILE_MENTION = re.compile(
    r"^- (Create|Edit|Test|Delete|Move|Rename|Modify):\s*`([^`]+)`", re.MULTILINE
)
_DEPENDS_ON_RE = re.compile(
    r"^\*\*Depends on:\*\*\s+(.+?)\s*$",
    re.MULTILINE,
)
_TRACK_RE = re.compile(
    r"^\*\*Track:\*\*\s+(.+?)\s*$",
    re.MULTILINE,
)
_RE_TARGET_REPO = re.compile(r"^\*\*Target repo:\*\*\s*(.+)$", re.MULTILINE)
_PHASE_REF_RE = re.compile(r"^Phase\s+(\d+)$")
# Lines the plan header already captures as structured fields — everything
# else in the header block is retained as ``Plan.preamble``.
_RE_HEADER_STRUCTURED_LINE = re.compile(
    r"^(# .+|\*\*Spec:\*\*.+|\*\*Status:\*\*.+|\*\*Goal:\*\*.+)$",
    re.MULTILINE,
)


def parse_plan(path: Path) -> Plan:
    """Parse a plan markdown file into a frozen Plan AST.

    Raises FileNotFoundError if path does not exist.
    Raises ValueError if the file is not a valid fr plan.
    """
    text = path.read_text(encoding="utf-8")
    fmt = detect(text)

    title = _extract(text, _RE_TITLE, "Untitled Plan")
    spec = _extract_optional(text, _RE_SPEC)
    status = _extract(text, _RE_STATUS, "Not Started")
    goal = _extract(text, _RE_GOAL, "")
    preamble = _extract_preamble(text)

    if fmt is PlanFormat.PHASED:
        phases, has_depends_line = _parse_phases(text)
        return Plan(
            title=title,
            spec=spec,
            status=status,
            goal=goal,
            format=fmt,
            phases=tuple(phases),
            tasks=(),
            preamble=preamble,
            phase_has_depends_line=tuple(has_depends_line),
        )
    else:
        tasks = _parse_tasks(text)
        return Plan(
            title=title,
            spec=spec,
            status=status,
            goal=goal,
            format=fmt,
            phases=(),
            tasks=tuple(tasks),
            preamble=preamble,
        )


def _extract(text: str, pattern: re.Pattern[str], default: str) -> str:
    m = pattern.search(text)
    return m.group(1).strip() if m else default


def _extract_optional(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _find_header_divider(text: str) -> int | None:
    """Return the byte offset of the first ``---`` line that is NOT inside a
    fenced code block, or ``None`` if no such divider exists.

    A simple ``text.find("\\n---")`` — or even a line-anchored regex — is wrong
    here because preambles legitimately embed yaml frontmatter examples whose
    own ``---`` delimiters sit on lines by themselves.  Track fence state as
    we walk the text so those interior ``---``s are skipped.
    """
    in_fence = False
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and stripped == "---":
            return pos
        pos += len(line)
    return None


def _strip_fenced_regions(text: str) -> str:
    """Return ``text`` with fenced-code-block content replaced by spaces.

    Byte offsets are preserved: line lengths are unchanged, only the
    character content inside fences is blanked. This lets regex scans
    (``_RE_PHASE``, ``_RE_TASK``, ``_RE_STEP``) skip embedded plan-format
    examples without disturbing the offsets we later use to slice the
    ORIGINAL text for content extraction.

    The fence markers (``` lines) themselves are preserved so that nested
    toggling still works.
    """
    in_fence = False
    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        # Strip just the trailing newline for the fence check; keep the
        # newline in the output.
        body = line.rstrip("\n")
        newline = line[len(body) :]
        if body.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
        elif in_fence:
            out_lines.append(" " * len(body) + newline)
        else:
            out_lines.append(line)
    return "".join(out_lines)


def _extract_preamble(text: str) -> str:
    """Capture header content that isn't one of title/spec/status/goal.

    Everything between the first line and the first ``---`` divider is
    considered the header block.  The recognized structured fields
    (``# Title``, ``**Spec:**``, ``**Status:**``, ``**Goal:**``) are filtered
    out; the remainder is returned verbatim with leading/trailing blank lines
    trimmed.
    """
    divider_idx = _find_header_divider(text)
    header_block = text[:divider_idx] if divider_idx is not None else text
    remainder = _RE_HEADER_STRUCTURED_LINE.sub("", header_block)
    # Collapse runs of 3+ blank lines that structured-field removal created.
    remainder = re.sub(r"\n{3,}", "\n\n", remainder)
    return remainder.strip("\n")


def _parse_depends_on(phase_body: str, phase_number: int) -> tuple[int, ...]:
    """Return the tuple of dependency phase numbers, or () if the line is absent."""
    match = _DEPENDS_ON_RE.search(phase_body)
    if match is None:
        return ()
    raw = match.group(1).strip()
    if raw in ("—", "None"):
        return ()
    parts = [p.strip() for p in raw.split(",")]
    deps: list[int] = []
    for part in parts:
        ref_match = _PHASE_REF_RE.match(part)
        if ref_match is None:
            raise ValueError(
                f"Phase {phase_number}: could not parse dependency list "
                f"'{raw}'. Expected 'Phase <int>' refs."
            )
        deps.append(int(ref_match.group(1)))
    return tuple(deps)


def _parse_phases(text: str) -> tuple[list[Phase], list[bool]]:
    """Parse all phases from phased-format markdown.

    Returns ``(phases, has_depends_line)`` where ``has_depends_line[i]`` is
    True iff the i-th phase declared a ``**Depends on:**`` line (even
    ``—``/``None``). This lets ``validate_dag`` distinguish "declared root"
    from "line absent" when enforcing the Phase 2 missing-line rule for
    live plans.

    Fenced code blocks are blanked out before regex scans so plan-format
    examples embedded in the document (e.g. ``` ``` ## Phase 1: ... ``` ```)
    don't get mistaken for real phase headers. Offsets are preserved so
    slicing into the original ``text`` for content extraction still works.
    """
    scan_text = _strip_fenced_regions(text)
    phase_matches = list(_RE_PHASE.finditer(scan_text))
    phases: list[Phase] = []
    has_depends_line: list[bool] = []

    for i, pm in enumerate(phase_matches):
        start = pm.end()
        end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else len(text)
        # Use original ``text`` for content (tracking URL, task bodies).
        # Use ``scan_text`` slice for boundary regex searches so fenced
        # examples inside the phase don't confuse task/deps detection.
        section = text[start:end]
        scan_section = scan_text[start:end]

        tracking_match = _RE_TRACKING.search(section)
        tracking_url = tracking_match.group(1) if tracking_match else None

        # Scope **Depends on:** / **Track:** lookup to the phase prelude
        # (before first task). Use the fence-stripped ``scan_section`` slice
        # so that a ``**Depends on:**`` or ``**Track:**`` line nested inside
        # a fenced code-block example can't false-positive into the AST.
        first_task = _RE_TASK.search(scan_section)
        prelude_scan = scan_section[: first_task.start()] if first_task else scan_section
        phase_number = int(pm.group(1))
        depends_on = _parse_depends_on(prelude_scan, phase_number)
        has_depends_line.append(_DEPENDS_ON_RE.search(prelude_scan) is not None)

        track_match = _TRACK_RE.search(prelude_scan)
        # A whitespace-only value (e.g. ``**Track:**    ``) can still match
        # the lazy-capture regex because ``\s+`` backtracks to leave a single
        # space for ``(.+?)``. Coerce the resulting empty string back to
        # ``None`` so the AST distinguishes "line absent" from "line blank"
        # (and the writer never emits ``**Track:** `` with a trailing space).
        track_label = track_match.group(1).strip() if track_match else None
        if track_label == "":
            track_label = None

        target_repo_m = _RE_TARGET_REPO.search(prelude_scan)
        target_repo = target_repo_m.group(1).strip() if target_repo_m else None

        # Spec §1.1: **Depends on:** and **Track:** must live directly under
        # the ## Phase header (or its <!-- Tracking: ... --> comment); any
        # other location is a parse error. A misplaced line below the first
        # task header would otherwise be silently ignored, turning a dependent
        # phase into a root or dropping its track assignment. Check the
        # fence-stripped post-prelude slice so that documentation examples
        # don't false-positive.
        if first_task is not None:
            post_prelude = scan_section[first_task.start() :]
            if _DEPENDS_ON_RE.search(post_prelude):
                raise ValueError(
                    f"Phase {phase_number}: **Depends on:** line appears "
                    f"below the first task header. It must sit directly "
                    f"under the '## Phase {phase_number}:' header "
                    f"(or its '<!-- Tracking: ... -->' comment if present). "
                    f"Move the line up and re-run."
                )
            if _TRACK_RE.search(post_prelude):
                raise ValueError(
                    f"Phase {phase_number}: **Track:** line appears below "
                    f"the first task header. It must sit directly under the "
                    f"'## Phase {phase_number}:' header "
                    f"(or its '<!-- Tracking: ... -->' comment if present). "
                    f"Move the line up and re-run."
                )
            if _RE_TARGET_REPO.search(post_prelude):
                raise ValueError(
                    f"Phase {phase_number}: **Target repo:** line appears below "
                    f"the first task header. It must sit directly under the "
                    f"'## Phase {phase_number}:' header "
                    f"(or its '<!-- Tracking: ... -->' comment if present). "
                    f"Move the line up and re-run."
                )

        tasks = _parse_tasks(section)
        phases.append(
            Phase(
                number=phase_number,
                title=pm.group(2).strip(),
                tag=cast(_TagType, pm.group(3) or "agentic"),
                depends_on=depends_on,
                tasks=tuple(tasks),
                tracking_url=tracking_url,
                track_label=track_label,
                target_repo=target_repo,
            )
        )

    return phases, has_depends_line


def _parse_tasks(text: str) -> list[Task]:
    """Parse all tasks from a section of markdown.

    Like ``_parse_phases``, scans a fence-stripped copy for boundary
    detection so embedded plan-format examples (fenced ``### Task N:`` or
    ``## Phase N:`` inside a ``` block) don't get mistaken for real headers.
    Content slicing uses the original ``text``.
    """
    scan_text = _strip_fenced_regions(text)
    task_matches = list(_RE_TASK.finditer(scan_text))
    tasks: list[Task] = []

    for i, tm in enumerate(task_matches):
        start = tm.end()
        end = task_matches[i + 1].start() if i + 1 < len(task_matches) else len(text)
        section = text[start:end]
        scan_section = scan_text[start:end]

        # Don't cross into the next phase
        next_phase = _RE_PHASE.search(scan_section)
        if next_phase:
            section = section[: next_phase.start()]

        steps = _parse_steps(section)
        file_mentions = _parse_files(section)
        tasks.append(
            Task(
                number=int(tm.group(1)),
                title=tm.group(2).strip(),
                tag=cast(_TagType, tm.group(3)) if tm.group(3) else None,
                steps=tuple(steps),
                files_mentioned=tuple(path for _verb, path in file_mentions),
                file_mention_verbs=tuple(verb for verb, _path in file_mentions),
            )
        )

    return tasks


def _parse_steps(text: str) -> list[Step]:
    """Parse all steps from a task section.

    The step regex also captures any trailing prose on the same line as the
    bold ``**Step N: title**`` header.  When present, the trailing text is
    merged into the step title — otherwise every loose-format step would be
    silently dropped (see ``tests/unit/test_plan_loose_format.py``).

    Fenced code blocks are blanked out before regex scans so checkbox-style
    step headers embedded in plan-format examples (Python test fixtures,
    markdown samples) don't get mistaken for real steps. Without this, plans
    that document the step format in their own body would be permanently
    ``In Progress`` from the parser's perspective. Offsets are preserved so
    body slicing into the original ``text`` still works.
    """
    scan_text = _strip_fenced_regions(text)
    step_matches = list(_RE_STEP.finditer(scan_text))
    steps: list[Step] = []

    for i, sm in enumerate(step_matches):
        start = sm.end()
        end = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(text)
        # ``textwrap.dedent`` removes the common leading whitespace across
        # every body line uniformly, which keeps a fenced code block's marker
        # and its content at the same column.  Plain ``.strip()`` trimmed
        # only the outer whitespace of the whole string, so the fence ``` went
        # to column 0 while the fence's content kept its original indent.
        body = textwrap.dedent(text[start:end]).rstrip()

        state_char = sm.group(1)
        state = state_char if state_char in (" ", "x", "-") else " "

        # Either variant A (``**Step N: title**``) populates groups 3+4,
        # or variant B (``**Step N:** title``) populates group 5.
        if sm.group(3) is not None:
            bold_title = sm.group(3).strip()
            trailing = (sm.group(4) or "").strip()
            title = f"{bold_title} {trailing}".strip() if trailing else bold_title
        else:
            title = (sm.group(5) or "").strip()

        raw_label = sm.group(2)
        # For dotted labels (``"0.1"``), the leading integer is what downstream
        # callers actually use for ordering; the full token is kept in ``label``.
        number = int(raw_label.split(".", 1)[0])
        label = raw_label if "." in raw_label else None

        steps.append(
            Step(
                number=number,
                title=title,
                body=body,
                state=state,  # type: ignore[arg-type]
                label=label,
            )
        )

    return steps


def _parse_files(text: str) -> list[tuple[str, str]]:
    r"""Extract ``(verb, path)`` pairs from the ``**Files:**`` block.

    Preserving the verb (Create/Edit/Test/Delete/Move/Rename/Modify) is what
    keeps ``- Test: \`cmd\``` round-tripping instead of collapsing to a
    fake ``- Create: \`cmd\``` on write.
    """
    return [(m.group(1), m.group(2)) for m in _RE_FILE_MENTION.finditer(text)]
