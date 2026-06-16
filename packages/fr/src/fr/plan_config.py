"""Strip dead keys from a repo's `docs/superpowers/plan-config.yaml`.

The per-repo plan-config carries keys that no code reads:

- `plan.save_to`
- the entire top-level `dispatch:` block (`target`, `owner`, `project_board`,
  `default_repo`, `labels`)

Only `plan.filename` + `header.required` + `header.status_values` are live
(read by `scripts/validate-plans.sh`). This module removes the dead keys with a
text-based pass — no YAML round-trip — so the live keys, their formatting, and
any comments survive byte-for-byte. It is idempotent: a clean file is returned
unchanged. Wired into `fr repair` and `fr migrate v1-to-v2`.
"""

from __future__ import annotations

import re
from pathlib import Path

# An ACTIVE top-level `dispatch:` line (not a `# dispatch:` comment).
_DISPATCH_RE = re.compile(r"^dispatch:\s*(#.*)?$")
# An ACTIVE indented `save_to:` line (lives under the `plan:` mapping).
_SAVE_TO_RE = re.compile(r"^\s+save_to:")


def strip_dead_keys(text: str) -> tuple[str, list[str]]:
    """Return `(new_text, removals)` with dead keys stripped.

    `removals` lists what was removed (e.g. `["plan.save_to", "dispatch"]`).
    When nothing is dead, the input is returned byte-identical with `[]`.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    removals: list[str] = []
    in_plan_block = False  # only strip `save_to` inside the top-level `plan:` map
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.rstrip("\r\n")
        is_top_level = bool(stripped) and not stripped[:1].isspace()
        if is_top_level and _DISPATCH_RE.match(stripped):
            removals.append("dispatch")
            in_plan_block = False
            i += 1
            # Consume the block body: blank lines and more-indented lines, up to
            # the next top-level key (a line starting with a non-space) or EOF.
            while i < n:
                body = lines[i].rstrip("\r\n")
                if body.strip() == "" or body[:1].isspace():
                    i += 1
                    continue
                break
            continue
        if is_top_level:
            in_plan_block = stripped.startswith("plan:")
        if in_plan_block and _SAVE_TO_RE.match(stripped):
            removals.append("plan.save_to")
            i += 1
            continue
        out.append(line)
        i += 1

    if not removals:
        return text, []

    new_text = "".join(out)
    # Collapse any blank-line run left by a removed block to a single blank, and
    # end with exactly one trailing newline.
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    new_text = new_text.rstrip("\n") + "\n"
    # Report plan.save_to before dispatch for stable ordering.
    ordered = [k for k in ("plan.save_to", "dispatch") if k in removals]
    return new_text, ordered


def strip_dead_keys_file(path: Path) -> list[str]:
    """Strip dead keys from the plan-config file at `path`, in place.

    Returns the list of removals. An absent file or an already-clean file
    returns `[]` and leaves the file untouched (no rewrite).
    """
    if not path.is_file():
        return []
    text = path.read_text()
    new_text, removals = strip_dead_keys(text)
    if removals and new_text != text:
        path.write_text(new_text)
    return removals
