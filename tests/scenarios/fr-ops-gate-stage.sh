#!/usr/bin/env bash
# Row fr-ops-gate-stage: `fr ops gate --run <id>` carries a delivered run through the
# DevOps stage's eight stages (spec 2026-10-22-fr-ops R15, §J): a resume after an
# interrupted stage 4, a refusal at stage 6 while a [devops] step is only owed, and its
# recovery (a later outcome recorded in the ops workspace supersedes the owed one).
#
# Credential free and forge free. The forge is a fake inside a small driver that runs the
# candidate's own python: it imports fr, swaps the forge factories, the operator's
# terminal and the interactivity check, and runs `fr ops gate` in process. Every other
# fr the stage starts is the real candidate: `fr isolation up/exec` in host-worktree mode
# (no docker), and `fr ops status/apply` inside that workspace as real processes. The ops
# profile is a fixture fr-profiles.yaml (`ops: true`) plus FR_PROFILE and
# KUBERNETES_SERVICE_HOST as container evidence. `origin` is a local bare repo reached
# by a `file://localhost/...` URL, so fr can name its slug as on a real clone; the fake
# merge moves the bare repo's main.
# `fr ops trust` needs a terminal, so the grant is written by fr's own grant function.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
export HOME="$work/home" MARKS="$work/marks" FR_OPS_TRUST_DIR="$work/trust" FR_OPS_GATE_DIR="$work/gate"
export FR_ISOLATION_TARGET=worktree FR_PROFILE=ops KUBERNETES_SERVICE_HOST=10.0.0.1
mkdir -p "$HOME" "$MARKS" "$FR_OPS_TRUST_DIR"
py="$(candidate_python)"
ORIGIN="$work/derio-net/fixture.git"

git init -q --bare "$ORIGIN" || fail "bare origin"
git init -q . && git symbolic-ref HEAD refs/heads/main || fail "git init"
git remote add origin "file://localhost$ORIGIN"
mkdir -p .devcontainer .fr docs/superpowers/specs
cat > .devcontainer/fr-profiles.yaml <<'YAML'
schema_version: 2
profiles:
  ops: {purpose: operate, secrets: [], ops: true}
default: ops
forge: {type: github}
tracking: {type: none}
YAML
printf 'env_passthrough: [MARKS]\n' > .fr/ops.yaml
"$py" - <<'PY' || fail "could not write the matrix"
from pathlib import Path
from fr.artifacts.registry import ARTIFACT_KINDS
path = Path("docs/acceptance/matrix.yaml")
path.parent.mkdir(parents=True, exist_ok=True)
version = ARTIFACT_KINDS["matrix"].current_version
path.write_text(f"schema_version: {version}\norg: derio-net\nrepo: fixture\nrows: []\n")
PY
run_fr out init validator-wrapper
require_exit 0 "$out"
git add -A && git commit -qm base && git push -q origin main || fail "seed main"

# --- the delivered feature: two runs, each with its plan, ops and a [devops] step ----
git switch -q -c feat/x
for slug in p q; do
  mkdir -p "docs/superpowers/plans/$slug"
  cat > "docs/superpowers/specs/2026-10-22-$slug-design.md" <<'MD'
# Fixture

## Verification

strategy: none
gate: developer

## Test Plan

- [devops] walk the stage
- [tester] click the page
MD
  cat > "docs/superpowers/plans/$slug/ops.yaml" <<YAML
schema_version: 1
ops:
  - {id: pre-$slug, summary: before merge, phase: pre-merge, check: 'test -f "\$MARKS/pre-$slug"', apply: 'touch "\$MARKS/pre-$slug"'}
  - id: post-$slug
    summary: after merge
    phase: post-merge
    ready: 'true'
    check: 'test -f "\$MARKS/post-$slug"'
    apply: 'test -f "\$MARKS/allow-$slug" && touch "\$MARKS/post-$slug"'
YAML
done
"$py" - <<'PY' || fail "could not write the run cursors"
from pathlib import Path
from fr.run.model import RunState, StepRecord, save_run_state
for slug, pr in (("p", 5), ("q", 6)):
    save_run_state(Path.cwd(), RunState(
        run=f"run-{slug}", workflow="fr-goal@1", branch="feat/x",
        started="2026-10-22T00:00:00+00:00", cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": f"docs/superpowers/specs/2026-10-22-{slug}-design.md"}),
            "plan": StepRecord(state="done", emitted={"plan": f"docs/superpowers/plans/{slug}"}),
            "deliver": StepRecord(state="done", emitted={"pr": f"https://github.com/derio-net/fixture/pull/{pr}"}),
        }))
PY
git add -A && git commit -qm feature && git push -q origin feat/x || fail "push the feature"
HEAD_SHA="$(git rev-parse HEAD)"

"$py" - <<'PY' || fail "could not write the trust grants"
from pathlib import Path
from fr.ops.load import load_ops, load_ops_config
from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest
root = Path.cwd()
tree = head_tree(root)
for slug in ("p", "q"):
    ops = load_ops(root / "docs/superpowers/plans" / slug, root).ops
    fp = fingerprint(ops, load_ops_config(root), root, code_tree=tree_digest(tree))
    grant_trust(root, slug, fp, tree=tree)
PY
git reset -q --hard "$HEAD_SHA" && git clean -fdq   # the grant's audit line is not the PR's

# gate <run> <answers…>: `fr ops gate --run <run> --yes` against the fake forge, the
# operator answering each terminal question in turn (y = confirm; text = a step's outcome).
cat > "$work/drive.py" <<'PY'
import json, os, subprocess, sys
from pathlib import Path

from typer.testing import CliRunner

from fr.cli import app
from fr.commands import archive_cmd, gate_cmd, ops_gate_cmd
from fr.triage import gitseam

work = Path(os.environ["WORK"])
run_id, answers = sys.argv[1], list(sys.argv[2:])
MINE = {"run-p": 5, "run-q": 6}[run_id]
state_file = work / "forge.json"
prs = json.loads(state_file.read_text())


def save():
    state_file.write_text(json.dumps(prs))


class Forge:
    def _pr(self, n):
        return prs[str(n)]

    def pr_view(self, repo, n):
        p = self._pr(n)
        return {**p, "draft": False, "mergeable": "MERGEABLE", "title": "t", "body": "b"}

    def pr_required_checks(self, repo, n):
        return [{"name": "ci", "bucket": "pass"}]

    def pr_checks(self, repo, n):
        return [{"name": "ci", "bucket": "pass"}]

    def repo_merge_methods(self, repo):
        return {"default": "merge", "allowed": ["merge"]}

    def pr_merge(self, repo, n, *, head_sha, method):
        p = self._pr(n)
        assert p["head_oid"] == head_sha, "merged a head the stage did not pin"
        subprocess.run(["git", "--git-dir", os.environ["ORIGIN"], "update-ref",
                        "refs/heads/main", head_sha], check=True)
        p["state"] = "MERGED"
        p.setdefault("events", []).append("merged")
        save()

    def open_pr_for_head(self, repo, branch):
        return prs.get("housekeeping", {}).get(branch)

    def pr_create(self, repo, *, head, base, title, body):
        prs.setdefault("housekeeping", {})[head] = {"number": 9, "url": "u"}
        save()
        print(f"FAKE-FORGE pr_create head={head} base={base}")
        return 9

    def pr_for_branch(self, branch, cwd=None, run=None):  # verify-merge's lookup
        p = self._pr(MINE)
        return {"state": p["state"], "url": "u", "mergedAt": "2026-10-22T12:00:00Z"}

    def edit_pr_labels(self, repo, n, *, add, remove):
        p = self._pr(n)
        p["labels"] = sorted((set(p["labels"]) | set(add)) - set(remove))
        save()

    def list_issue_comments(self, repo, n):
        return []

    def ensure_labels(self, repo, names):
        pass

    def comment_pr(self, repo, n, body):
        print(f"FAKE-FORGE comment #{n}: {body}")


class Prompt:
    def confirm(self, text):
        print(f"PROMPT {text.splitlines()[0]}")
        return (answers.pop(0) if answers else "y") == "y"

    def ask(self, text):
        print(f"ASK {text.splitlines()[0]}")
        return answers.pop(0) if answers else ""


def in_process(args, cwd, *, terminal=False):
    if args[:2] == ["isolation", "exec"]:  # the ops run as real processes in the workspace
        done = subprocess.run(["fr", *args], cwd=cwd, stdout=subprocess.PIPE, text=True)
        return done.returncode, done.stdout
    here = os.getcwd()
    os.chdir(cwd)
    try:
        result = CliRunner().invoke(app, list(args))
    finally:
        os.chdir(here)
    sys.stdout.write(result.output)
    if result.exception and not isinstance(result.exception, SystemExit):
        raise result.exception
    return result.exit_code, result.stdout


forge = Forge()
ops_gate_cmd._interactive = lambda: True
ops_gate_cmd._forge = lambda url: forge
ops_gate_cmd._prompt = lambda: Prompt()
gate_cmd.client_for_url = lambda url: forge
archive_cmd._make_gh_client = lambda: forge
import fr.isolation.local as isolation_local  # noqa: E402

isolation_local.client_for = lambda cwd: forge
gitseam.run_this_fr = in_process
result = CliRunner().invoke(app, ["ops", "gate", "--run", run_id, "--yes"])
print(result.output)
if result.exception and not isinstance(result.exception, SystemExit):
    raise result.exception
sys.exit(result.exit_code)
PY
cat > "$work/forge.json" <<JSON
{"5": {"state": "OPEN", "head_oid": "$HEAD_SHA", "head_ref": "feat/x", "base_ref": "main", "labels": ["gate:devops", "gate:tester"]},
 "6": {"state": "OPEN", "head_oid": "$HEAD_SHA", "head_ref": "feat/x", "base_ref": "main", "labels": ["gate:devops", "gate:tester"]}}
JSON
export WORK="$work" ORIGIN
gate() { local __out; __out="$(unset CI; "$py" "$work/drive.py" "$@" 2>&1)"; RC=$?; OUT="$__out"; }

# --- the refusal outside a terminal (CI is set by _common.sh) -------------------------
run_fr out ops gate --run run-p
require_exit 2 "$out"
expect_grep 'terminal' "$out" "a non-interactive context is refused"

# --- run-p: stages 1-3, then stage 4 stops (the post-merge apply fails) --------------
gate run-p y y y
require_exit 1 "$OUT"
expect_grep 'stage 1 \(pre-merge ops\): done' "$OUT" "stage 1 completes"
expect_grep 'PROMPT MERGE PR #5' "$OUT" "the merge asks its own confirmation"
expect_grep 'stage 2 \(merge\): done' "$OUT" "stage 2 merges"
expect_grep 'stage 3 \(verify-merge, rebase, ready\): done' "$OUT" "stage 3 verifies and rebases"
expect_grep 'stage 4 \(post-merge ops\) failed' "$OUT" "stage 4 stops, naming the stage"
[ -f "$MARKS/pre-p" ] || fail "the pre-merge op was not applied"
[ "$(git --git-dir "$ORIGIN" rev-parse main)" = "$HEAD_SHA" ] || fail "main is not the merged head"
[ "$(git rev-parse feat/x)" = "$HEAD_SHA" ] || fail "evidence reached the PR head"

# --- resume: stage 4 onward, no second merge -----------------------------------------
touch "$MARKS/allow-p"
gate run-p y "ran walked it"
require_exit 0 "$OUT"
refuse_grep 'stage [123] \(' "$OUT" "a resume re-ran a recorded stage"
refuse_grep 'PROMPT MERGE' "$OUT" "a resume asked to merge again"
expect_grep 'stage 4 \(post-merge ops\): done' "$OUT" "stage 4 resumes"
expect_grep 'ASK Test Plan step 1 \(devops\)' "$OUT" "stage 5 asks for the devops step"
expect_grep 'stage 6 \(gate pass\): done' "$OUT" "stage 6 passes the gate"
expect_grep 'Tester gate owns: step 2' "$OUT" "the pass comment lists the tester step"
expect_grep 'gate:tester stays' "$OUT" "stage 7 keeps gate:tester"
expect_grep 'FAKE-FORGE pr_create head=chore/ops-p base=main' "$OUT" "stage 8 opens the housekeeping PR"
expect_grep 'DevOps stage is complete' "$OUT" "every stage ran"
grep -q '"gate:devops-passed"' "$work/forge.json" || fail "gate:devops was not passed"
grep -q '"gate:tester"' "$work/forge.json" || fail "gate:tester was dropped"
[ "$(grep -o merged "$work/forge.json" | wc -l | tr -d ' ')" = 1 ] || fail "the PR merged more than once"
git --git-dir "$ORIGIN" rev-parse -q --verify refs/heads/chore/ops-p >/dev/null || fail "the ops branch was not pushed"
gate run-p
require_exit 0 "$OUT"
expect_grep 'every stage is already done; nothing ran' "$OUT" "a rerun of a complete stage does nothing"

# --- run-q: an owed devops step is refused at stage 6 --------------------------------
touch "$MARKS/allow-q"
"$py" - "$work/forge.json" <<'PY' || fail "mark the fake PR merged by hand"
import json, sys
d = json.load(open(sys.argv[1])); d["6"]["state"] = "MERGED"; json.dump(d, open(sys.argv[1], "w"))
PY
gate run-q y y "owed later"
require_exit 1 "$OUT"
expect_grep 'stage 6 \(gate pass\) failed' "$OUT" "an owed devops step stops stage 6"
expect_grep 'owed' "$OUT" "the refusal names the owed step"
expect_grep 'fr closeout outcome --run run-q --step 1 --ran' "$OUT" "the refusal names the recovery command"

# --- the owed step recovers: record it in the ops workspace, re-run --------------------
(unset CI; fr isolation exec --branch chore/ops-q -- fr closeout outcome --run run-q --step 1 --ran --evidence "walked it later") >/dev/null 2>&1 \
  || fail "could not record the owed step's outcome"
gate run-q
require_exit 0 "$OUT"
expect_grep 'stage 6 \(gate pass\): done' "$OUT" "a recorded outcome supersedes the owed one"
expect_grep 'DevOps stage is complete' "$OUT" "the recovered run completes"

echo "ok: fr-ops-gate-stage"
