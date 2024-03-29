"""
Object representing a helper file for an OCR app.
"""

import datetime
from django.db import models
from django.contrib.auth.models import User
from tagging.fields import TagField
import tagging


class OcrModel(models.Model):
    """
        OCR model objects.
    """
    user = models.ForeignKey(User, related_name="ocrmodels")
    derived_from = models.ForeignKey("self", null=True, blank=True, related_name="derivees")
    tags = TagField()
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_on = models.DateField(editable=False)
    updated_on = models.DateField(editable=False, null=True, blank=True)
    public = models.BooleanField(default=True)
    file = models.FileField(upload_to="models")
    type = models.CharField(max_length=20,
            choices=[("char", "Character"), ("lang", "Language")])
    app = models.CharField(max_length=20,
            choices=[("ocropus", "Ocropus"), ("tesseract", "Tesseract")])

    def __unicode__(self):
        """
        String representation.
        """
        return self.name

    def save(self):
        if not self.id:
            self.created_on = datetime.datetime.now()
        else:
            self.updated_on = datetime.datetime.now()
        super(OcrModel, self).save()

    def get_absolute_url(self):
        """URL to view an object detail"""
        return "/ocrmodels/show/%i/" % self.id

    def get_update_url(self):
        """url to update an object detail"""
        return "/ocrmodels/edit/%i/" % self.id

    def get_delete_url(self):
        """url to update an object detail"""
        return "/ocrmodels/delete/%i/" % self.id

    @classmethod
    def get_list_url(cls):
        """URL to view the object list"""
        return "/ocrmodels/list/"

    @classmethod
    def get_create_url(cls):
        """URL to create a new object"""
        return "/ocrmodels/create/"


