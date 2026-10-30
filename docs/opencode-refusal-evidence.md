# Local readiness-refusal evidence (preparation only)

This is a diagnostic, not dispatch approval, readiness evidence, association
attestation, or permission to repeat a launch. Live use requires separate approval.
No environment variable, global setting, CLI default or monitor enables it.

## Explicit API

`HerdrRunner(workspace_id, readiness_evidence_dir=Path(...))` forwards the
destination to `opencode.wait_ready(..., evidence_dir=...)`. Both default to
`None`. `from_env()` does not enable capture. Callers must create a fresh,
absolute, owned **0700** directory for exactly one attempt. No directory is
created or chmodded by the writer. Reusing it cannot overwrite prior evidence.

### Existing native dispatch integration seam (do not execute without approval)

The constructor alone does not configure a CLI invocation. There is **no CLI
flag** for this diagnostic; `HerdrRunner.from_env()` remains disabled. The
existing callable in `fr.commands.triage_batch_cmd` has this source signature:

```python
def dispatch_batch(
    target: Path,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    *,
    to: str | None = None,
    checkout_path: Path | None = None,
    repair: bool = False,
    handle: str | None = None,
    reserved_version: str | None = None,
    yes: bool = False,
    group: str | None = None,
    read_errors: bool = False,
    driver: Driver = HOST,
    load: Callable[[str], Runner] | None = None,
    label_seen: set[str] | None = None,
) -> None: ...
```

Its `load` seam receives the resolved runner name. A separately approved caller
can supply a loader returning a configured **real**
`HerdrRunner(workspace_id=..., readiness_evidence_dir=attempt_directory)` for
`"herdr"`, delegating other runner names to the existing `load_runner`. This
retains `dispatch_batch`'s real preflight, native association and event handling;
it is not a fake runner, manual association, repair or approval bypass. With
`load=None`, the existing `load_runner` path is unchanged and capture stays off.
Do not execute this API as part of preparing or reviewing the diagnostic. A code
or plan review does **not** authorize a live call, capture or another allocation.

Only a terminal rendered-input refusal is captured, from the same immutable
screen string already returned by the owned-pane observation. Identity and
remaining-deadline checks precede it. Retried unknown layouts, startup metadata
frames and transport/deadline failures are not captured by this hook. No extra
pane read, process/status call, poll, prompt or identity association is performed.
The runner's existing exception cleanup executes afterward, unchanged.

## Content and privacy limits

The JSON contains the original fixed refusal reason, a fixed matched-pattern
identifier (or braille-Task category), a lossy shape projection, truncation flag,
focus/metadata-presence booleans, recording timestamp and SHA-256 of the
server/pane/session/item tuple. The hash is a correlatable reference, not proof
of ownership. Category matching reuses the same regex and same observed frame;
metadata is never treated as readiness. It does not diagnose a real plugin fault.

`predicate_span` is either null (no located text/Task predicate), or
`{"start": [row, column], "end": [row, column]}`: zero-based, half-open
character coordinates in the guard's ANSI-stripped, right-trimmed lines joined
with `\n`. Casefold-expanded match offsets are mapped back to the covering
original characters (for example, `ß`/`İ` before a match do not shift columns).
These are not raw ANSI byte offsets or terminal display cells. Only numeric
coordinates are emitted; no matched substring or plugin payload is retained.

`predicate_outside_capture` explicitly reports whether any of that match is
outside the retained rows `[0,64)` or columns `[0,160)`; it is null without a
located predicate. An exclusive end column of 160 is still inside. Current
predicate regexes cannot cross a normalized newline. Diagnostic selection uses
the guard's actual order: `_DIALOG.search(joined.casefold())` before the
braille/Task search, even if a spinner occurs earlier visually. It does not
choose an earlier spinner in place of the text branch that actually refused.

Only spaces and `┃╹▀` are retained in the frame; **every other character** is
replaced with `·`, including drafts, titles, paths, credentials and unrecognized
terminal controls. Recognized CSI sequences are removed. Row and character
positions are implicit array/string offsets, not terminal display-cell columns;
ANSI colours are represented only by the known focused-border boolean. At most
64 rows of 160 characters are retained. Shape, approximate text lengths and
fixed categories are intentionally disclosed; arbitrary text is not.

## Filesystem behavior

Serialization is ASCII JSON bounded to **65,536 bytes** before any file is opened.
All destination components are opened using held directory descriptors and
`O_NOFOLLOW`; symlinks, `..`, foreign ownership and group/world writable parents
are rejected. The leaf must be owned by the current uid with mode exactly 0700.
This intentionally also refuses otherwise convenient shared temporary parents.

A random exclusive 0600 temporary contains **only redacted JSON**. A same-directory
hard link publishes `readiness-refusal.json` atomically without replacing any
existing file or symlink. Temporary cleanup checks device/inode before unlinking;
cleanup errors are swallowed rather than deleting unrelated replacements. A failed
cleanup may leave a redacted temporary. No raw frame is persisted at any stage.

Capture/serialization/filesystem errors preserve the original refusal and attach
only `readiness evidence: unavailable` as an exception note. No path or exception
detail is included. Disabled mode performs no projection or filesystem I/O.

No hard-real-time filesystem latency, crash durability, hostile same-uid process
isolation, or guaranteed error-note rendering by every CLI is claimed. Capture
may delay cleanup through filesystem latency, but cannot extend observation or
submission admission: it runs only after a timely terminal refusal.
