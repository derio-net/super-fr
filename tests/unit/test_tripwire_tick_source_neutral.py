"""Tripwire — `tick` must never couple to `discover_plans` (spec §4.H).

`fr_dispatch.protocols.Source` (name, `discover() -> Iterable[WorkItem]`)
is the seam a future poller extraction will consume: `discover_plans`
becomes its first implementation (`PlansSource`), a Jira query becomes
another, a run-state watcher a third. **Nothing is extracted in this
phase** — the one thing this phase DOES ship is the guarantee that the
extraction stays mechanical, by making the coupling it would otherwise
accrete impossible to add silently.

This is enforced, not promised: a docstring saying "don't do this" is a
suggestion a future patch can violate one line at a time without anyone
noticing (a keyword-argument default that calls `discover_plans()`, a
convenience import "just for this one caller", a string reference in a new
docstring that quietly becomes load-bearing). This test fails the moment
any of those appear, for a reason a diff cannot hide: `tick`'s own body no
longer contains the string `discover_plans` — that source text is the
entire footprint.
"""

from __future__ import annotations

import inspect

import fr_dispatch
from fr_dispatch import tick


def test_tick_never_references_discover_plans():
    """`tick` operates on the source it is handed (`plan: Plan | SpecMeta |
    None`); discovering work is the caller's job today and `Source`'s job
    tomorrow — never `tick`'s own.

    Source-inspects `tick` alone (not the whole module): `discover_plans`
    itself is defined a few lines above `tick` in this same file, so
    asserting against `inspect.getsource(fr_dispatch)` would trivially fail
    for the wrong reason. Isolating the function's own source is what makes
    a future violation (a reference genuinely INSIDE `tick`'s body) the only
    way this test goes red.
    """
    tick_source = inspect.getsource(tick)

    assert "discover_plans" not in tick_source, (
        "fr_dispatch.tick must not reference discover_plans (spec §4.H's "
        "one standing obligation to the future poller extraction). Route "
        "discovery through fr_dispatch.protocols.Source.discover() instead "
        "of calling or importing discover_plans from tick — the whole "
        "point of the Source seam is that (b)'s extraction only ever has "
        "to MOVE discover_plans's body behind that shape, never redesign "
        "tick's inputs. If tick genuinely needs new discovery behavior, "
        "add it via a Source-shaped parameter, not this name."
    )


def test_discover_plans_still_exists_as_the_thing_source_will_wrap():
    """Companion assertion: the tripwire above is meaningful only while
    `discover_plans` is still a real, standalone function `tick` could in
    principle have called — pins that it hasn't been deleted or folded into
    `tick`'s own body as a lazy way to make the tripwire pass."""
    assert callable(fr_dispatch.discover_plans)
    assert fr_dispatch.discover_plans is not tick
    assert "discover_plans" in inspect.getsource(fr_dispatch.discover_plans)


def test_source_protocol_documents_discover_plans_as_its_first_implementation():
    """The Protocol's docstring is the map for whoever does the extraction;
    pin that it still names `discover_plans` as the first implementation
    and says nothing is extracted yet, so a docstring edit that quietly
    drops either claim is caught."""
    from fr_dispatch.protocols import Source

    doc = Source.__doc__ or ""
    assert "discover_plans" in doc
    assert "nothing is extracted" in doc.lower() or "not extracted" in doc.lower()


def test_source_protocol_shape():
    from fr_dispatch.protocols import Source

    assert hasattr(Source, "discover")
    assert "name" in Source.__annotations__
    sig = inspect.signature(Source.discover)
    assert list(sig.parameters) == ["self"]
