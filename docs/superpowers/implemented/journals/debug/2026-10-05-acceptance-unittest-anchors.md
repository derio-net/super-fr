# Journal: 2026-10-05-acceptance-unittest-anchors

<!-- fr:journal kind=repro scope=debug id=9f19f502254f created=2026-10-05T20:36:40+00:00 -->
### 9f19f502254f · repro · unittest spellings fail both anchor paths

node_line("class TestA:\n    def test_b(self): pass\n", "TestA.test_b") -> None (the :: form -> 2), so `fr acceptance check` reports a live test as "renamed or deleted" (gh#965). collected_node_at(src, 4) for `class FooTests(unittest.TestCase): def test_x` -> None, so the matrix-name-anchors repair never converts a #L<n> that sits in it (gh#893).

<!-- fr:journal kind=root-cause scope=debug id=de7d79a44f9d created=2026-10-05T20:36:48+00:00 -->
### de7d79a44f9d · root-cause · fr.acceptance.anchors models a test identity in pytest's terms only

The one module that defines what a .py fragment names knows pytest's node-id grammar (parts joined by NODE_SEP '::') and pytest's default collection predicate (classes 'Test*'). unittest is the other spelling of the same identity: its ids join with '.', and it collects any unittest.TestCase subclass whatever its name. node_line splits on '::' only (gh#965); is_test_node judges a class by its name only, so it cannot see a TestCase base (gh#893). One cause, two readers of it: check/report resolve names via node_line, the repair picks names via collected_node_at.

<!-- fr:journal kind=hypothesis scope=debug id=9b2bb2538f9c created=2026-10-05T20:36:51+00:00 -->
### 9b2bb2538f9c · hypothesis · Fix: accept '.' as a part separator; recognise TestCase subclasses from the AST

'.' cannot occur in a Python identifier, so 'A.b' is unambiguous: node_line splits on '::' or '.'. That resolves the anchor in check and in the probing report. The repair keeps writing the canonical '::' form. Collection: a class counts as a test class when its name starts with 'Test' OR it subclasses a *TestCase base (unittest.TestCase, IsolatedAsyncioTestCase, ...), directly or through a class defined in the same module. Inside a TestCase class only 'test*' methods count (the unittest loader prefix). A cross-module base is still not followed: resolution stays ast-only, and check never imports repo code.

<!-- fr:journal kind=finding scope=debug id=9a52594f6f8d created=2026-10-05T20:50:20+00:00 state=fixed -->
### 9a52594f6f8d · finding [fixed] · anchors.py reads unittest's spelling: Class.test resolves, TestCase subclasses are collected

node_line splits parts on '::' or '.'; collected_node_at judges each enclosing class by name (Test*) or by subclassing a *TestCase base (direct, or via a module-level class — Python's own resolution scope for a base name). Pinned by test_node_line_resolves_unittest_dotted_ids, test_check_accepts_a_unittest_dotted_anchor, test_collection_recognises_unittest_testcase_subclasses, test_the_repair_converts_a_line_anchor_inside_a_testcase_subclass, all red first (commit 29d4d37b6).

<!-- fr:journal kind=review scope=debug id=c9c91e3e9fc9 created=2026-10-05T20:50:29+00:00 -->
### c9c91e3e9fc9 · review · Independent review: 2 in-scope findings fixed, 1 out of scope noted

(1) in scope, fixed: the first cut built the TestCase set from ast.walk keyed by bare name, so a function-local class Helper(TestCase) certified a plain module-level Helper. Now each enclosing class node is judged itself and base names resolve among module-level classes only; pinned by test_collection_reads_a_base_where_python_resolves_it (fails on the first cut). The reviewer's suggested fix (module-level classes only) was not taken as-is: it would drop nested classes that enclosing_node reaches. (2) in scope, fixed: tests for 'A..b', '.b' and a base cycle added. (3) out of scope, documented in the docstring: a plain mixin whose name ends in TestCase counts as one — the intended conservative-enough heuristic for an ast-only reader.
