"""
Nodetree test suite.
"""

from __future__ import absolute_import

import unittest

from . import node, script, cache, test_nodes


class TestScript(unittest.TestCase):
    def setUp(self):
        pass

    def test_create_script(self):
        s = script.Script({})
        self.assertEqual(len(s.serialize()), 0)

    def test_script_add_node(self):
        s = script.Script({})
        n1 = s.add_node("test_nodes.Number", "Val1", (("num", 2),))
        self.assertEqual(len(s.serialize()), 1)

        nget = s.get_node("Val1")
        self.assertEqual(nget, n1)        


class NodeTests(unittest.TestCase):
    def setUp(self):
        self.script = self._buildTestScript()

    def test_add(self):
        t = self.script.get_terminals()[0]
        self.assertEqual(t.label, "Add")
        self.assertEqual(t.eval(), 5)

        op = self.script.get_node("Add")
        op.set_param("operator", "*")
        self.assertEqual(op._params.get("operator"), "*")
        self.assertEqual(op.eval(), 6)

    def test_set_invalid_value(self):
        n = self.script.get_node("Add")
        n.set_param("operator", "!")
        self.assertRaises(node.ValidationError, n.validate)

    def _buildTestScript(self):
        s = script.Script({})
        n1 = s.add_node("test_nodes.Number", "Val1", (("num", 2),))
        n2 = s.add_node("test_nodes.Number", "Val2", (("num", 3),))
        n3 = s.add_node("test_nodes.Arithmetic", "Add", (("operator", "+"),))
        n3.set_input(0, n1)
        n3.set_input(1, n2)
        return s


if __name__ == '__main__':
    import sys
    print __FILE__
    unittest.main()
