"""Errors `fr.triage` raises. The command layer maps every one to exit 2.

`ForgeError` is triage's own: `ClientForge` translates the forge adapter's
failures (a forge CLI's error, an operation the backend does not support, a
missing binary) into it, so nothing above `fr.triage.collect` knows which forge
CLI sits underneath (decision d2).
"""

from __future__ import annotations


class TriageError(Exception):
    """A user-facing triage failure: a bad state file, a bad scope."""


class ForgeError(TriageError):
    """A forge call failed — no access, issues disabled, no forge CLI."""


class ConfigError(TriageError):
    """A repo's or the scope's triage config that fr refuses strictly (a merge method the
    repo does not allow, a bad known key): only its owner can fix it, so a looping driver
    stops on it as a refusal (spec 2026-11-19-batch-train-truth R2)."""
