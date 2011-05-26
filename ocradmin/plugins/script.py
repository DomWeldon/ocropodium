"""
Object representation of a Node script.
"""

import manager



class Script(object):
    """
    Object describing the OCR pipeline.
    """
    def __init__(self, script, logger=None):
        """
        Initialiser.
        """
        self.logger = logger
        self._script = script
        self._error = None
        self._tree = {}
        self._manager = manager.ModuleManager()
        self._build_tree()

    def _build_tree(self):
        """
        Wire up the nodes in tree order.
        """
        lookup = {}
        for n in self._script:
            if self._tree.get(n["name"]):
                raise ValueError("Duplicate node in tree: %s" % n["name"])
            lookup[n["name"]] = n
            self._tree[n["name"]] = self._manager.get_new_node(
                    n["type"], n["name"], n["params"], logger=self.logger)
        for name, n in lookup.iteritems():
            for i in range(len(n["inputs"])):            
                self._tree[name].set_input(i, self._tree[n["inputs"][i]])

    def get_node(self, name):
        """
        Find a node in the tree.
        """
        return self._tree.get(name)

    def get_terminals(self):
        """
        Get nodes that end a branch.
        """
        return [n for n in self._tree.itervalues() \
                if not n.has_parents()]

