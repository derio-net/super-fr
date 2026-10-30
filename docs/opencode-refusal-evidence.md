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
