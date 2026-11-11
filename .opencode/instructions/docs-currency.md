# Docs currency — a page keeps up with the code it covers

## Rule

In a repo with `.fr/docs.yaml`, each page listed there names in its front matter
the paths it describes (`covers:`) and when it was last checked (`reviewed:
<date> <note>`). **A PR that changes a covered path changes the page too:**
edit it so it describes the change, or, when it is still true, update its
`reviewed` stamp. A repo with no `.fr/docs.yaml` owes nothing.

## How to know

- `fr docs check` reports every page whose covered paths changed on this branch
  while the page did not, plus covers globs that match nothing and tracked files
  no page covers when the config asks for that. Exit 0 clean, 1 findings, 2 a
  usage or environment error. It reads only; it never writes.
- `fr docs status` lists every page, what it covers and its stamp.

## Where it is enforced

fr-goal's `deliver` derives `docs` evidence and refuses while the check fails;
fr-debugging runs it before opening the PR; a repo's CI can run the same
command on every pull request (`fr docs check --base origin/<base>`), which is
the gate no flow can skip.
