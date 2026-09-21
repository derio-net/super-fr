"""Errors `fr.triage` raises. The command layer maps every one to exit 2.

`ForgeError` is triage's own: `GhForge` translates the forge CLI's failures
(and a missing binary) into it, so nothing above `fr.triage.collect` knows
which forge CLI sits underneath (decision d2).
"""

from __future__ import annotations


class TriageError(Exception):
    """A user-facing triage failure: a bad state file, a bad scope."""


class ForgeError(TriageError):
    """A forge call failed — no access, issues disabled, no forge CLI."""
