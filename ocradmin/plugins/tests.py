"""
    Test the scripts.
"""
import os
import glob
from django.test import TestCase
from django.utils import simplejson as json
from django.conf import settings

from ocradmin.core.tests import testutils

from nodetree import script, node, manager
import numpy

SCRIPTDIR = "plugins/fixtures/scripts"


class ScriptsTest(TestCase):
    fixtures = ["ocrmodels/fixtures/test_fixtures.json"]

    def setUp(self):
        """
            Setup OCR tests.  These run directly, not via views.
        """
        self.manager = manager.ModuleManager()
        self.manager.register_paths(
                glob.glob("plugins/*_nodes.py"), root="ocradmin")
        testutils.symlink_model_fixtures()
        self.scripts = {}
        for fname in os.listdir(SCRIPTDIR):
            if fname.endswith("json"):
                with open(os.path.join(SCRIPTDIR, fname), "r") as f:
                    self.scripts[fname] = json.load(f)
        
    def tearDown(self):
        """
            Cleanup a test.
        """
        pass

    def test_valid_scripts(self):
        """
        Test the supposedly valid script don't raise errors.
        """
        for name, nodes in self.scripts.iteritems():
            if name.startswith("invalid"):
                continue
            s = script.Script(nodes, manager=self.manager)
            terms = s.get_terminals()
            self.assertTrue(len(terms) > 0, msg="No terminal nodes found.")

            # check we get an expected type from evaling the nodes
            for n in terms:
                out = n.eval()
                self.assertIn(type(out), (unicode, dict, list, numpy.ndarray), 
                        msg="Unexpected output type for node %s: %s" % (
                            n.name, type(out)))

    def test_invalid_scripts(self):
        """
        Test supposedly invalid script DO raise errors.
        """
        for name, nodes in self.scripts.iteritems():
            if not name.startswith("invalid"):
                continue
            s = script.Script(nodes, manager=self.manager)
            terms = s.get_terminals()
            self.assertTrue(len(terms) > 0, msg="No terminal nodes found.")
            # check we get an expected type from evaling the nodes
            for n in terms:
                self.assertRaises(node.ValidationError, n.eval)


        

