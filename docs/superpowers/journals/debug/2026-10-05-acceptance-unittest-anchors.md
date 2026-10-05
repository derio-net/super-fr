# Journal: 2026-10-05-acceptance-unittest-anchors

<!-- fr:journal kind=repro scope=debug id=9f19f502254f created=2026-10-05T20:36:40+00:00 -->
### 9f19f502254f · repro · unittest spellings fail both anchor paths

node_line("class TestA:\n    def test_b(self): pass\n", "TestA.test_b") -> None (the :: form -> 2), so `fr acceptance check` reports a live test as "renamed or deleted" (gh#965). collected_node_at(src, 4) for `class FooTests(unittest.TestCase): def test_x` -> None, so the matrix-name-anchors repair never converts a #L<n> that sits in it (gh#893).

<!-- fr:journal kind=root-cause scope=debug id=de7d79a44f9d created=2026-10-05T20:36:48+00:00 -->
### de7d79a44f9d · root-cause · fr.acceptance.anchors models a test identity in pytest's terms only

The one module that defines what a .py fragment names knows pytest's node-id grammar (parts joined by NODE_SEP '::') and pytest's default collection predicate (classes 'Test*'). unittest is the other spelling of the same identity: its ids join with '.', and it collects any unittest.TestCase subclass whatever its name. node_line splits on '::' only (gh#965); is_test_node judges a class by its name only, so it cannot see a TestCase base (gh#893). One cause, two readers of it: check/report resolve names via node_line, the repair picks names via collected_node_at.
