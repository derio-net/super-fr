"""The effective settle modes (spec 2026-11-23-pr-readiness-wait R1, R6).

The repo setting `git.settle`, read from the default branch like every key of
`.fr/settings.yaml`, then one feature's override on top: for a run with a spec, a
`settle.<key>: <mode> — <reason>` line in the spec's `## Verification` section; with no
spec, a debug-journal `decision` whose id is `settle-<key>`, whose title is the mode and
whose body is the reason. A malformed override is a refusal naming it, never ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.settle.model import Modes, SettleRefused

KEYS = ("conflicts", "ci")


def _spec_overrides(repo_root: Path, spec: str) -> dict[str, dict[str, str]]:
    from fr.verification.rows import spec_text_at
    from fr.verification.spec_section import SectionError, settle_overrides

    text = spec_text_at(repo_root, spec)
    try:
        found = settle_overrides(text) if text is not None else {}
    except SectionError as e:
        raise SettleRefused(f"{spec}: {e}") from e
    return {k: {"mode": o.mode, "source": "spec", "reason": o.reason} for k, o in found.items()}


def _journal_overrides(journal: Path) -> dict[str, dict[str, str]]:
    from fr.journal.model import JournalParseError, parse_journal
    from fr.settings.model import SETTLE_MODES

    if not journal.is_file():
        return {}
    try:
        entries = parse_journal(journal.read_text())
    except (OSError, UnicodeDecodeError, JournalParseError) as e:
        raise SettleRefused(f"cannot read the debug journal {journal.name}: {e}") from e
    out: dict[str, dict[str, str]] = {}
    for entry in entries:
        key = entry.id.removeprefix("settle-")
        if entry.kind != "decision" or not entry.id.startswith("settle-") or key not in KEYS:
            continue
        mode, reason = entry.title.strip(), entry.body.strip()
        if mode not in SETTLE_MODES or not reason:
            raise SettleRefused(
                f"{journal.name}: decision {entry.id!r} must have a mode of "
                f"{sorted(SETTLE_MODES)} as its title and the reason as its body "
                f"(title {entry.title!r}, body {'empty' if not reason else 'given'})"
            )
        out[key] = {"mode": mode, "source": "journal", "reason": reason}
    return out


def effective_modes(
    repo_root: Path, *, spec: str | None = None, debug_journal: Path | None = None
) -> Modes:
    """Each key's mode, where it came from and an override's reason. *spec* is the run's
    spec, repo-relative; *debug_journal* the branch's one debug journal, read only when
    there is no spec. `SettingsError` when the setting is unreadable, `SettleRefused`
    when an override is malformed."""
    from fr.settings.load import load_settings

    eff = load_settings(repo_root)
    settle = eff.settings.git.settle
    data: dict[str, Any] = {
        key: {
            "mode": getattr(settle, key),
            "source": eff.sources.get(f"git.settle.{key}", "default"),
        }
        for key in KEYS
    }
    if spec:
        data.update(_spec_overrides(repo_root, spec))
    elif debug_journal is not None:
        data.update(_journal_overrides(debug_journal))
    return Modes.model_validate(data)


def run_modes(repo_root: Path, state: Any) -> Modes:
    """The modes of a run's PR: the setting and the run's spec line (fr-goal's PR body and
    `deliver` witness)."""
    from fr.requirements import run_spec

    return effective_modes(repo_root, spec=run_spec(state))
