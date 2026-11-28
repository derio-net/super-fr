"""`--emitted name=path` pairs, as `fr run resolve` records them (spec 2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5. A malformed pair is a `RunStateError`, which the
command prints as it always has.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from pathlib import Path

from fr.run.model import RunStateError
from fr.workflow.artifacts import REPO_TRACKED_ARTIFACTS
from fr.workflow.model import Step


def parse_emitted(pairs: list[str], repo_root: Path, step: Step | None = None) -> dict[str, str]:
    """`--emitted name=path` pairs, validated and made repo-relative.

    **The normalization is the point** (review r5-b2). `emitted.plan` is the
    key `archive.find_run_for_plan` and `run.adopt.adoptable_plans` match a
    run to its plan by, and both compare against a repo-relative posix path.
    A stored ABSOLUTE path matches neither — verified live: it made `fr run
    adopt` create a SECOND run for a plan that already had one, and would
    have left the first behind at `fr archive`. Both are silent no-ops, which
    spec §4.B calls out as worse than failing. And an absolute path is what
    an agent following SKILL.md's `--emitted plan=<path>` produces routinely.

    Only `REPO_TRACKED_ARTIFACTS` (`spec`, `plan`) are path-normalised: `pr`
    is a URL, `report` and `journal:*` have no repo path, and rewriting those
    would be nonsense.

    Five further rules, each closing a way to record a wrong thing quietly
    (review r5-e2):

    1. **Split on the FIRST `=` only.** A path may contain `=`; splitting on
       the last, or on all, silently truncates it.
    2. **Neither half may be empty.** `plan=` records the repo root as the
       plan; `=x` records an artifact with no name.
    3. **The name must be one the step declares it `emits`.** An artifact the
       manifest never mentions is a shape/agent mismatch — the agent emitted
       something the workflow does not know about, or misspelled the name it
       does — and storing it means the run carries a key nothing will ever
       read. The refusal names the step's declared emits.
    4. **No duplicate names in one call.** `--emitted plan=a --emitted plan=b`
       silently kept `b`.
    5. **A repo-tracked artifact must EXIST.** An agent reporting a spec that
       is not on disk is precisely the silent-wrong-state case the run cursor
       exists to prevent.
    """
    result: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")  # partition splits on the FIRST `=`
        if not sep:
            raise RunStateError(f"--emitted must be 'name=path', got {pair!r}")
        name = name.strip()
        if not name:
            raise RunStateError(f"--emitted has an empty artifact name: {pair!r}")
        if not value.strip():
            raise RunStateError(f"--emitted {name}= has an empty value")
        if name in result:
            raise RunStateError(
                f"--emitted {name}= given twice ({result[name]!r} then {value!r}) — "
                "one artifact, one value"
            )
        if step is not None and name not in step.emits:
            emits = ", ".join(sorted(step.emits)) or "(nothing)"
            raise RunStateError(
                f"step {step.id!r} does not emit {name!r}; it declares: {emits}. "
                "Either the workflow shape is missing an `emits:` entry or the "
                "artifact name is misspelled."
            )
        result[name] = repo_relative_artifact(name, value.strip(), repo_root)
    return result


def repo_relative_artifact(name: str, value: str, repo_root: Path) -> str:
    if name not in REPO_TRACKED_ARTIFACTS:
        return value
    from fr.artifacts.paths import REPO, feature_root, space_for

    # The artifact root, not the product checkout: under quiet or stealth the spec and
    # plan live in the `fr` worktree or the tracking clone (R1), and a run records them
    # relative to that root, the same layout as under `repo`. Readers resolve them back
    # through `fr.artifacts.paths.emitted_path`.
    space = space_for(repo_root)
    base = feature_root(space)
    raw = Path(value)
    if raw.is_absolute():
        candidates = [raw]
    else:
        # The logical spelling (`<kind dir>/<file>` below the feature root) first; off
        # `repo`, also the same path spelled from the `fr` worktree or tracking root
        # (`features/<id>/...`).
        candidates = [base / raw]
        if space.placement != REPO:
            candidates.append(space.root / raw)
    # `resolve()` on BOTH sides (review r5-e2): an fr worktree lives under
    # `~/.cache`, which on macOS is reached through `/private/var/...` — so a
    # resolved artifact path and an unresolved repo root have no common
    # prefix and `relative_to` raises on a file that is plainly inside.
    resolved_root = base.resolve()
    inside: list[Path] = []
    for target in candidates:
        try:
            inside.append(target.resolve().relative_to(resolved_root))
        except ValueError:
            continue
    real_inside = [r for r in inside if (resolved_root / r).exists()]
    if not real_inside and any(t.exists() for t in candidates):
        inside = []  # it exists, but only outside the root: say that, not "missing"
    if not inside:
        if space.placement == REPO:
            where, hint = "the repo", "a run records repo-relative artifact paths"
        else:
            where = f"this feature's {space.placement} artifact root"
            hint = "a run records paths below it; `fr settings paths` names its directories"
        raise RunStateError(
            f"--emitted {name}={value!r} is outside {where} ({resolved_root}) — {hint}"
        )
    rel = real_inside[0] if real_inside else inside[0]
    if not (resolved_root / rel).exists():
        raise RunStateError(
            f"--emitted {name}={value!r} does not exist ({resolved_root / rel}). "
            "A run records artifacts that were actually written; recording one "
            "that is not there is the silent-wrong-state this cursor exists to "
            "prevent."
        )
    return rel.as_posix()
