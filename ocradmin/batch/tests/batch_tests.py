"""
    OCR batch tests.
"""
import os
import re
import shutil
from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from django.conf import settings

from ocradmin.presets.models import Preset
from ocradmin.batch.models import Batch
from ocradmin.ocrtasks.models import OcrTask
from ocradmin.projects.models import Project
from ocradmin.core.tests import testutils

from django.utils import simplejson as json

TESTFILE = "etc/simple.png"
SCRIPT1 = "nodelib/scripts/valid/tesseract.json"
SCRIPT2 = "nodelib/scripts/valid/ocropus.json"



class BatchTest(TestCase):
    fixtures = [
            "ocrtasks/fixtures/test_task.json",
            "transcripts/fixtures/test_transcript.json",
            "ocrmodels/fixtures/test_fixtures.json",
            "projects/fixtures/test_fixtures.json",
            "presets/fixtures/test_fixtures.json",
            "batch/fixtures/test_batch.json"]

    def setUp(self):
        """
            Setup OCR tests.  Creates a test user.
        """
        with open(SCRIPT1, "r") as s1:
            self.script1 = s1.read()
        with open(SCRIPT2, "r") as s2:
            self.script2 = s2.read()
        testutils.symlink_model_fixtures()
        try:
            os.makedirs("media/files/test_user/test")
        except OSError, (errno, strerr):
            if errno == 17: pass
        try:
            os.symlink(os.path.abspath(TESTFILE),
                    "media/files/test_user/test/%s" % os.path.basename(TESTFILE))
        except OSError, (errno, strerr):
            if errno == 17: pass
        self.testuser = User.objects.create_user("test_user", "test@testing.com", "testpass")
        self.client = Client()
        self.client.login(username="test_user", password="testpass")
        self.project = Project.objects.all()[0]
        self.client.get("/projects/load/%s/" % self.project.pk)

        # create a document in project storage
        self.doc = self.project.get_storage().create_document("Test doc")
        with open(TESTFILE, "rb") as fhandle:
            self.doc.image_content = fhandle
            self.doc.image_mimetype = "image/png"
            self.doc.image_label = os.path.basename(TESTFILE)
            self.doc.save()


    def tearDown(self):
        """
            Cleanup a test.
        """
        self.testuser.delete()
        shutil.rmtree("media/files/test_user")
        self.doc.delete()

    def test_batch_new(self):
        """
        Test the convert view as a standard GET (no processing.)
        """
        self.assertEqual(self.client.get("/batch/new").status_code, 200)

    def test_batch_create(self):
        """
        Test OCRing with minimal parameters.
        """
        self._test_batch_action()

    def test_results_action(self):
        """
        Test fetching task results.  Assume a batch with pk 1
        exists.
        """
        pk = self._test_batch_action()
        r = self.client.get("/batch/results/%s" % pk)
        self.assert_(r.content, "No content returned")
        content = json.loads(r.content)
        self.assertEqual(
                content[0]["fields"]["tasks"][0]["fields"]["page_name"],
                self.doc.pid)
        return pk

    def test_page_results_page_action(self):
        """
        Test fetching task results.  Assume a page with offset 0
        exists.
        """
        pk = self._test_batch_action()
        r = self.client.get("/batch/results/%s/0/" % pk)
        self.assert_(r.content, "No content returned")
        content = json.loads(r.content)
        self.assertEqual(
                content[0]["fields"]["page_name"],
                self.doc.pid)

    def test_save_transcript(self):
        """
        Test fetching task results.  Assume a page with offset 0
        exists.
        """
        pk = self._test_batch_action()
        r = self.client.get("/batch/results/%s/0/" % pk)
        self.assert_(r.content, "No content returned")
        content = json.loads(r.content)
        self.assertEqual(
                content[0]["fields"]["page_name"],
                self.doc.pid)

    def test_show_action(self):
        """
        Test viewing batch details.
        """
        pk = self._test_batch_action()
        r = self.client.get("/batch/show/%s/" % pk)
        self.assertEqual(r.status_code, 200)

    def test_delete_action(self):
        """
        Test viewing batch details.
        """
        before = Batch.objects.count()
        r = self.client.post("/batch/delete/1/", follow=True)
        self.assertRedirects(r, "/batch/list/")
        self.assertEqual(before, Batch.objects.count() + 1)

    def test_builder_edit_task(self):
        task = OcrTask.objects.all()[0]
        r = self.client.get("/presets/builder/%s/" % task.page_name)
        self.assertEqual(r.status_code, 200)

    def _test_batch_action(self, params=None, headers={}):
        """
        Testing actually OCRing a file.
        """
        preset = Preset.objects.filter(profile__isnull=False)[0]
        if params is None:
            params = dict(
                    name="Test Batch",
                    user=self.testuser.pk,
                    project=self.project.pk,
                    task_type="run.batchitem",
                    pid=self.doc.pid,
                    preset=preset.id,
            )
        r = self._get_batch_response(params, headers)
        # check the POST redirected as it should
        self.assertEqual(r.redirect_chain[0][1], 302)
        pkmatch = re.match(".+/batch/show/(\d+)/?", r.redirect_chain[0][0])
        self.assertTrue(pkmatch != None)
        return pkmatch.groups()[0]

    def test_file_upload(self):
        """
        Test uploading files to the server.
        """
        with file(TESTFILE, "rb") as fh:
            params = {}
            params["file1"] = fh
            headers = {}
            r = self.client.post("/batch/upload_files/", params, **headers)
        #fh.close()
        content = json.loads(r.content)
        self.assertEqual(content, [os.path.join(self.project.slug,
            os.path.basename(TESTFILE))])

    def _get_batch_response(self, params={}, headers={}):
        """
        Post images for conversion with the given params, headers.
        """
        headers["follow"] = True
        return self.client.post("/batch/create/", params, **headers)


