"""
    OCR binarize tests.
"""
import os
import shutil
from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import simplejson


TESTFILE = "etc/simple.png"

class OcrBinarizeTest(TestCase):
    def setUp(self):
        """
            Setup OCR tests.  Creates a test user.
        """
        self.testuser = User.objects.create_user("test_user", "test@testing.com", "testpass")
        self.client = Client()
        self.client.login(username="test_user", password="testpass")

    def tearDown(self):
        """
            Cleanup a test.
        """
        self.testuser.delete()

    def test_binarize_view(self):
        """
        Test the binarize view as a standard GET (no processing.)
        """
        self.assertEqual(self.client.get("/ocr/binarize").status_code, 200)

    def test_binarize_action_basic(self):
        """
        Test OCRing with minimal parameters.
        """
        self._test_binarize_action({
            "%options.engine": "ocropus",
            "%options.engine.ocropus[0].binarizer": 'BinarizeBySauvola',
        })

    def test_results_action(self):
        """
        Test fetching task results.  We can't meaningfully do this
        locally, because when testing the celery backend  is bypassed.
        However we can get the view works and returns a stub task.
        """
        import uuid
        r = self.client.get("/ocr/results/%s" % uuid.uuid1())
        self.assert_(r.content, "No content returned")
        content = simplejson.loads(r.content)
        # unknown tasks should come back with status 'PENDING'
        self.assertEqual(content["status"], "PENDING")

    def _test_binarize_action(self, params=None, headers={}):
        """
        Testing actually OCRing a file.
        """
        if params is None:
            params = {}
        r = self._get_binarize_response(params, headers)
        self.assertEqual(r.status_code, 200)

        # check we recieve JSON back
        self.assert_(r.content, "No content returned")
        content = simplejson.loads(r.content)
        self.assertEqual(len(content), 1)
        # Note: we'd not normally expect any results here because we're
        # not using the "nohang" parameter, but since tests are executed
        # locally we will
        self.assertTrue(content[0]["results"] is not None, "Unable to get results")

    def _get_binarize_response(self, params={}, headers={}):
        """
        Post an image for conversion with the given params, headers.
        """
        tf = open(TESTFILE)
        params["image1"] = tf
        r = self.client.post("/ocr/binarize", params, **headers)
        tf.close()
        return r


