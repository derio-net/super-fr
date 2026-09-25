# Plan: accurate OpenCode model apply no-op reporting

The implementation separates how many supported-tier OpenCode agent files were
considered from the subset that needed rewriting. A focused test phase first
pins both reported outcomes; the implementation phase updates the materializer
result and the shared CLI reporting path, then bumps the lockstep patch version
and runs the repository quality gates.

The count deliberately excludes files whose names do not end in a supported
phase tier. The post-merge check is the focused models command and tests agreed
with the operator during the brainstorm gate.
