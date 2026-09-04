"""`CncdRunner` — the CNC control plane's implementation of the Runner
protocol (cnc-fr spec 2026-07-02, §3.5).

A deliberately thin HTTP client over cncd's public API: `dispatch()`
serialises the plan folder verbatim and POSTs it to `POST /v1/ingest`.
No fr internals move here — parsing, rendering, and the queue lifecycle
stay in `fr` / `fr_dispatch`; cncd's server owns validation (the Go
port of the v2 schema, parity-tested against this repo's fixtures
corpus) and files-win upsert semantics.

Config mirrors the VK runner's env convention:

  - `CNCD_URL` — base URL of the cncd server (e.g.
    `http://localhost:8787`). An explicit `base_url=` ctor arg wins.
    `preflight()` fails every eligible phase cleanly when unset.
  - `CNCD_SLOT_BUDGET` — optional per-tick dispatch cap (default
    `DEFAULT_SLOT_BUDGET`). Ingest is cheap and idempotent, so the cap
    only bounds burst traffic, not correctness.

Dedup is server-side by design: cncd ingest upserts by
`(tenant, source_path)` and skips unchanged content hashes (spec §3.3),
so `existing_dispatches(items)` is honestly empty — a re-POST after a lost
GitHub synced-stamp is a no-op, not a duplicate. stdlib `urllib` only;
a thin client earns no third-party HTTP dependency.

**v2 (2026-08-14 workflow-shapes spec §4.D).** `dispatch`/`can_dispatch`
take a `WorkItem` instead of `(plan, phase, repo, issue_number)`;
`dedup_key`/`can_dispatch_repo` are gone. `build_ingest_payload` keeps
every existing wire key byte-stable and gains the item envelope
(`id`, `unit`, `parent`) alongside them — cncd's server-side schema is
additive-only for this cutover.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from fr_dispatch.item_graph import phase_payload

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr_dispatch.work_item import WorkItem

DEFAULT_SLOT_BUDGET = 8
INGEST_PATH = "/v1/ingest"
DEFAULT_TIMEOUT_SECONDS = 30.0


class CncdError(Exception):
    """A cncd API call failed — unreachable server or non-2xx response."""


def _env_base_url() -> str | None:
    return os.environ.get("CNCD_URL") or None


def build_ingest_payload(item: WorkItem) -> dict[str, Any]:
    """The `POST /v1/ingest` body: the plan folder verbatim + dispatch context.

    Files travel byte-for-byte (keyed by filename) because cncd's
    ingestion is files-win and content-hashed — the server, not this
    client, decides what changed. `source_path` is the repo-relative
    plan dir (cncd's upsert key alongside the tenant); it degrades to
    the absolute path only when the plan is outside a git checkout,
    which `fr apply --to` already refuses to dispatch.

    `plan`/`phase`/`issue_number` come out of `item.payload` — the same
    values the pre-cutover `(plan, phase, repo, issue_number)` signature
    took, just carried on the item now. `repo` is `item.repo` (the
    Issue's repo — see `fr_dispatch._eligible_items`). Every existing key
    stays byte-stable; `id`/`unit`/`parent` are new, additive envelope
    fields for a phase-unit item today.

    The three values are narrowed ONCE, by `fr_dispatch.item_graph.
    phase_payload` (review r5-a2). Reaching into the opaque payload here
    cost six `# type: ignore[attr-defined]` — six places where a
    non-phase item became a `KeyError` mid-dispatch instead of a refusal
    at `can_dispatch`.
    """
    plan, phase, issue_number = phase_payload(item)
    files = {p.name: p.read_text() for p in sorted(plan.dir.iterdir()) if p.is_file()}
    return {
        "kind": "plan_folder",
        "schema_version": 2,
        "plan": plan.meta.plan,
        "target_repo": plan.meta.target_repo,
        "repo": item.repo,
        "issue_number": issue_number,
        "phase": phase.phase.number,
        "source_path": plan.repo_relative_dir.as_posix(),
        "files": files,
        "id": item.id,
        "unit": item.unit,
        "parent": item.parent,
    }


class CncdRunner:
    """Runner-protocol adapter over cncd's HTTP API."""

    name = "cncd"

    capabilities = frozenset({"git", "tests", "scm"})

    def __init__(
        self, base_url: str | None = None, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> None:
        raw = base_url if base_url is not None else _env_base_url()
        self.base_url = raw.rstrip("/") if raw else None
        self.timeout = timeout

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        if not self.base_url:
            return (
                "CNCD_URL unset; cannot dispatch to cncd (set the env or pass base_url explicitly)"
            )
        return None

    def refresh(self) -> None:
        # Nothing cached: config is re-read per instance and every
        # dispatch is a fresh POST.
        return None

    def slot_budget(self) -> int:
        return int(os.environ.get("CNCD_SLOT_BUDGET", str(DEFAULT_SLOT_BUDGET)))

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        # Server-side idempotence (content-hash skip on ingest) makes a
        # client-side dedup snapshot unnecessary — and phase-1 cncd has
        # no query surface keyed by GitHub Issue to build one from. So
        # `items` is deliberately unused here: honestly empty, not stale.
        return set()

    def can_dispatch(self, item: WorkItem) -> bool:
        """cncd ingests PLAN FOLDERS, so it takes phase items only.

        Repo is not the limit — cncd ingests any repo's bundle and scopes
        tenants server-side, so there is no client-visible known-repo set.
        The *unit* is: `build_ingest_payload` serialises a plan folder plus
        a phase number, which a run- or spec-unit item does not have.
        Refusing here is what `protocols.Runner.can_dispatch` is for
        (review r5-a2); before it, such an item reached
        `item.payload["plan"]` and failed as `"<id>: 'plan'"` under
        `reason=backend_error`.
        """
        return item.unit == "phase"

    def dispatch(self, item: WorkItem) -> None:
        # preflight() guarantees base_url is set before tick dispatches.
        assert self.base_url is not None
        payload = build_ingest_payload(item)
        self._post_json(f"{self.base_url}{INGEST_PATH}", payload)

    def _post_json(self, url: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        # cncd authenticates every /v1 request: a forward-auth identity
        # header for human principals (plan pushes REQUIRE one — agent run
        # tokens are refused for /v1/ingest). Name/value are operator
        # config mirroring cncd's AUTH_HEADER contract.
        auth_header = os.environ.get("CNCD_AUTH_HEADER", "X-Forwarded-User")
        auth_user = os.environ.get("CNCD_AUTH_USER", "fr-cncd")
        req = urllib.request.Request(  # noqa: S310 — url comes from operator config
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                auth_header: auth_user,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                status = int(resp.status)
                resp.read()
        except urllib.error.HTTPError as e:
            snippet = e.read(200).decode("utf-8", errors="replace")
            raise CncdError(f"cncd ingest failed: HTTP {e.code} at {url}: {snippet}") from e
        except urllib.error.URLError as e:
            raise CncdError(f"cncd unreachable at {url}: {e.reason}") from e
        except TimeoutError as e:
            raise CncdError(f"cncd unreachable at {url}: timed out after {self.timeout}s") from e
        if not 200 <= status < 300:  # pragma: no cover — urlopen raises on >=400
            raise CncdError(f"cncd ingest failed: HTTP {status} at {url}")
