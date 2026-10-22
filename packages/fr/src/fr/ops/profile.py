"""Whether this process runs inside an ops profile (spec 2026-10-22-fr-ops R6).

A stub until the ops profile lands (plan phase 2): `fr ops status` runs anywhere
and only warns outside one; `apply`, `attest` and `seal` will refuse.
"""

from __future__ import annotations


def in_ops_profile() -> bool:
    """`FR_PROFILE` names an `ops: true` profile and container evidence is present.
    Always `False` until the profile exists."""
    return False
