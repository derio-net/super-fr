"""The ops gap (spec 2026-11-01-ops-gate-probes R1, R2, §A).

A run has an ops gap when its effective gates include `devops`, its plan declares no
op (in `ops.yaml` or a `# manual-operation` step block; the runbook is excluded) and no
`none:` acknowledgement, and at least one Test Plan step owned by the devops gate
carries a command. Such a run would reach `fr ops gate` stage 5 with nothing to run:
every command step becomes a prose question.

"Carries a command" is a HEURISTIC (R2), and it is documented as one:

- every non-blank line inside a code fence that belongs to the step is a command (the
  fence lines themselves, info string included, are not);
- an inline backtick span is a command when it has at least two words and its first
  word is a shipped operations tool (`SHIPPED_TOOLS`), a path (`./x`, `scripts/x`,
  `/usr/x`), or is followed by a flag (`-x`, `--x`) or a path argument holding `/`.

Its false positives are prose spans that look like commands (`git diff --stat` quoted
as an example); its false negatives are commands outside the shipped list written with
no flag and no path. The plan's `none: <reason>` acknowledgement is the escape for both.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence, Set
from dataclasses import dataclass
from pathlib import Path

from fr.ops.testplan import steps_gated
from fr.spec import FENCE_RE, Step, test_plan_steps

SHIPPED_TOOLS: tuple[str, ...] = (
    "ansible",
    "ansible-playbook",
    "pulumi",
    "terraform",
    "tofu",
    "kubectl",
    "helm",
    "talosctl",
    "docker",
    "podman",
    "ssh",
    "scp",
    "rsync",
    "systemctl",
    "make",
    "curl",
)
"""The operations tools whose name alone makes a two-word span a command (R2)."""

_SPAN_RE = re.compile(r"`([^`\n]+)`")
_FLAG_RE = re.compile(r"^--?[A-Za-z0-9]")


@dataclass(frozen=True)
class CommandStep:
    """A Test Plan step that carries commands: its number, its text, the commands."""

    n: int
    text: str
    commands: tuple[str, ...]


def _is_path(word: str) -> bool:
    return "/" in word


def _span_is_command(span: str) -> bool:
    words = span.split()
    if len(words) < 2:
        return False
    first, rest = words[0], words[1:]
    if first in SHIPPED_TOOLS or _is_path(first):
        return True
    return any(_FLAG_RE.match(w) or _is_path(w) for w in rest)


def _scan(raw: Sequence[str]) -> Iterator[tuple[bool, str]]:
    """The step's lines as `(fenced, line)`, fence lines themselves dropped."""
    fenced = False
    for line in raw:
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        yield fenced, line


def step_commands(step: Step) -> tuple[str, ...]:
    """The commands a step carries (R2), from its raw lines; none for a pointed step."""
    if step.op is not None:
        return ()
    out: list[str] = []
    prose: list[str] = []
    for fenced, line in _scan(step.raw):
        if fenced:
            if line.strip():
                out.append(line.strip())
        else:
            prose.append(line)
    spans = (" ".join(m.group(1).split()) for m in _SPAN_RE.finditer(" ".join(prose)))
    return tuple(out + [s for s in spans if _span_is_command(s)])


def _fenced_commands(lines: Sequence[str]) -> list[str]:
    """Fenced lines as runnable commands (review p3-r2): blank and `#`-comment lines
    dropped, a backslash-continued line joined to the next."""
    out: list[str] = []
    pending = ""
    for line in lines:
        text = line.strip()
        if not pending and (not text or text.startswith("#")):
            continue
        if text.endswith("\\"):
            pending += text[:-1].rstrip() + " "
            continue
        out.append((pending + text).strip())
        pending = ""
    if pending.strip():
        out.append(pending.strip())
    return out


def step_apply_parts(step: Step) -> tuple[list[str], str]:
    """`(runnable commands, prose)` of a step, for `fr ops stub`: the fenced commands
    cleaned by `_fenced_commands`, then the inline command spans; the prose is the step
    text with the fence markup and the fenced lines removed."""
    fenced_lines: list[str] = []
    prose: list[str] = []
    for fenced, line in _scan(step.raw):
        (fenced_lines if fenced else prose).append(line)
    joined = " ".join(prose)
    spans = (" ".join(m.group(1).split()) for m in _SPAN_RE.finditer(joined))
    commands = _fenced_commands(fenced_lines) + [s for s in spans if _span_is_command(s)]
    return commands, joined


def command_steps(steps: Sequence[Step], exit_gates: Set[str]) -> list[CommandStep]:
    """The steps the devops gate owns under `exit_gates` that carry a command."""
    found = ((s, step_commands(s)) for s in steps_gated(steps, exit_gates, "devops"))
    return [CommandStep(s.n, s.text, cmds) for s, cmds in found if cmds]


def ops_gap(
    root: Path, spec_rel: str, plan_dir: Path | None, exit_gates: Set[str]
) -> list[CommandStep]:
    """The run's ops gap (R1): its command steps, or `[]` when it has none. `plan_dir`
    is `None` before the run has a plan. `OpsLoadError` when the plan's ops carriers
    contradict its `none:` acknowledgement."""
    from fr.ops.load import ops_none, plan_has_ops

    if "devops" not in exit_gates:
        return []
    if plan_dir is not None:
        plan_dir = plan_dir if plan_dir.is_absolute() else root / plan_dir
        if ops_none(plan_dir) is not None or plan_has_ops(root, plan_dir):
            return []
    spec = root / spec_rel
    if not spec.is_file():
        return []
    return command_steps(test_plan_steps(spec.read_text()), exit_gates)


def gap_message(steps: list[CommandStep], *, has_plan: bool) -> str:
    """The ops-gap warning (R3) or refusal (R5): each command step with its commands,
    and both fixes."""
    if has_plan:
        head = (
            "ops gap: this run is devops-gated and its plan declares no op, but these "
            "Test Plan steps run commands:"
        )
        where = "the plan's ops.yaml"
    else:
        head = (
            "ops gap: this run is devops-gated and these Test Plan steps run commands, "
            "so they will need ops:"
        )
        where = "the plan's ops.yaml once it is written"
    lines = [head]
    for step in steps:
        lines.append(f"  step {step.n}: " + "; ".join(f"`{c}`" for c in step.commands))
    lines.append(
        "Fix: `fr ops stub` proposes an op per step (then give each a real `check:`) and "
        "points the step at it with `(op: <id>)`; or, when the steps have no ops on "
        f"purpose, say so with `none: <reason>` in {where}."
    )
    return "\n".join(lines)
