"""The `local` acceptance status (spec 2026-11-14-acceptance-local-status).

A `local` row is verified by an automated test anyone can run on any checkout, which
no CI runs. This module is the one definition of why a `local` row is debt
(`local_debt`, R3/R5) and of why a row cannot be set `local` (`local_error`, R2/R3).
"""

from __future__ import annotations
