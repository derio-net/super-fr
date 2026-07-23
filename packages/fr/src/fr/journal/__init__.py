"""The `fr journal` primitive — scope-keyed durable run-state.

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.

An append-only, CLI-only log under ``docs/superpowers/journals/``, keyed by
scope (``spec`` | ``plan`` | ``debug``) so one primitive serves fr-goal (spec +
plan scopes) and fr-debugging (debug scope). The file is both human-readable
Markdown and machine-parseable (per-entry HTML-comment delimiters), mirroring
how ``NN.yaml`` is the machine surface and ``_prose.md`` is prose.
"""

from __future__ import annotations

from fr.journal.model import (
    JOURNALS_REL,
    JournalEntry,
    JournalKind,
    JournalParseError,
    JournalScope,
    archived_journal_path,
    journal_path,
    parse_journal,
    serialize_entry,
)

__all__ = [
    "JOURNALS_REL",
    "JournalEntry",
    "JournalKind",
    "JournalParseError",
    "JournalScope",
    "archived_journal_path",
    "journal_path",
    "parse_journal",
    "serialize_entry",
]
