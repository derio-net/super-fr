"""One definition of a GitHub check's verdict: pass, pending or fail.

Spec 2026-11-24-ci-economy R3: every reader that turns a check on a pull-request head or
a merge-queue combination into a verdict reads a ``CANCELLED`` check as superseded, that
is pending, never failing.
"""
