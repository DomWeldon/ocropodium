"""
Project-related view functions.
"""

import os
from datetime import datetime
from django import forms
from django.conf import settings
from django.contrib.formtools.wizard import FormWizard
from django.contrib import messages
from django.core import serializers
from django.template.defaultfilters import slugify
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.template.defaultfilters import slugify

from tagging.models import TaggedItem
from ocradmin.core import utils as ocrutils
from ocradmin.ocrtasks.models import OcrTask
from ocradmin.batch.models import Batch
from ocradmin.projects.models import Project
from ocradmin.core import generic_views as gv


from fedora.adaptor import fcobject
from ordereddict import OrderedDict
PER_PAGE = 10


from ocradmin import storage

class ExportForm(forms.Form):
    """
    Fedora Export form.
    """
    username = forms.CharField(max_length=50)
    password = forms.CharField(max_length=255,
            widget=forms.PasswordInput(render_value=False))
    repository_url = forms.CharField(max_length=255)
    namespace = forms.CharField(max_length=255)


class DublinCoreForm(forms.Form):
    """
    Dublin Core Metadata form.
    """
    title = forms.CharField(max_length=255)
    creator = forms.CharField(max_length=255)
    subject = forms.CharField(max_length=255)
    description = forms.CharField(max_length=255, required=False)
    publisher = forms.CharField(max_length=255, required=False)
    contributors = forms.CharField(max_length=255, required=False)
    date = forms.DateField(required=False)
    type = forms.CharField(max_length=255, required=False)
    format = forms.CharField(max_length=255, required=False)
    identifier = forms.CharField(max_length=255, required=False)
    source = forms.CharField(max_length=255, required=False)
    language = forms.CharField(max_length=255, required=False)
    relation = forms.CharField(max_length=255, required=False)
    coverage = forms.CharField(max_length=255, required=False)
    right = forms.CharField(max_length=255, required=False)




class ProjectForm(forms.ModelForm):
    """New project form."""
    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)

        # change a widget attribute:
        self.fields['description'].widget.attrs["rows"] = 2
        self.fields['description'].widget.attrs["cols"] = 40

    class Meta:
        model = Project
        exclude = ["slug", "created_on", "storage_config_values",]
        widgets = dict(
                user=forms.HiddenInput(),
        )

class DummyStorageForm(forms.Form):
    """Placeholder for dynamically-generated storage
    config form."""


class ProjectWizard(FormWizard):
    """Wizard for project creation."""
    def __init__(self, *args, **kwargs):
        super(ProjectWizard, self).__init__(*args, **kwargs)
        self.initial = {                
                0: {"storage_backend": "FedoraStorage"},
        }

    def process_step(self, request, form, step):
        """Dynamically configure the storage config form
        given the storage backend specified in the first
        wizard page."""
        if step == 0:
            backend = storage.get_backend(
                    form.cleaned_data["storage_backend"])
            self.form_list[1] = backend.configform
            self.initial[1] = backend.defaults
            self.initial[1]["namespace"] = slugify(form.cleaned_data["name"])
        return super(ProjectWizard, self).process_step(request, form, step)

    def render_template(self, request, form, previous_fields, step, context=None):
        self.extra_context.update(
                model=Project,
                page_name="New OCR Project: Step %d of %d" % (
                    step + 1, self.num_steps()    
                ),
                success_url="/projects/list/",
        )
        return super(ProjectWizard, self).render_template(request, form, previous_fields, step, context)

    def get_template(self, step):
        """Get project wizard template."""
        return "projects/create%d.html" % step

    def done(self, request, form_list):
        """Save all form values and redirect to load page."""
        project = form_list[0].instance
        project.save()
        for field, value in form_list[1].cleaned_data.iteritems():
            project.storage_config_values.create(name=field, value=value)

        return HttpResponseRedirect("/projects/load/%s/" % project.pk)
        

projectlist = gv.GenericListView.as_view(
        model=Project,
        page_name="OCR Projects",
        fields=["name", "description", "user", "created_on"],)

projectcreate = gv.GenericCreateView.as_view(
        model=Project,
        form_class=ProjectForm,
        page_name="New OCR Project",
        success_url="/projects/load/%(id)s/",)

projectdetail = gv.GenericDetailView.as_view(
        model=Project,
        page_name="OCR Project",
        fields=["name", "description", "user", "tags", "created_on",
            "updated_on",])

projectedit = gv.GenericEditView.as_view(
        model=Project,
        form_class=ProjectForm,
        page_name="Edit OCR Project",
        success_url="/projects/load/%(id)s/",)

projectdelete = gv.GenericDeleteView.as_view(
        model=Project,
        page_name="Delete OCR Project",
        success_url="/projects/list/",)



def project_query(user, order, **params):
    """
        Query the model set.
    """

    tag = params.get("tag")
    try:
        del params["tag"]
    except KeyError:
        pass

    query = Q()
    for key, val in params.items():
        if key.find("__") == -1 and \
                not key in Project._meta.get_all_field_names():
            continue
        ldata = {key: val}
        query = query & Q(**ldata)

    # if there's a tag present search by tagged item
    if tag:
        return TaggedItem.objects.get_by_model(
            Project.objects.filter(query),
            tag).order_by(*order)
    else:
        return Project.objects.filter(query).order_by(*order)


def load(request, project_pk):
    """
    Open a project (load it in the session).
    """
    project = get_object_or_404(Project, pk=project_pk)
    request.session["project"] = project
    return HttpResponseRedirect("/documents/list/")


def close(request):
    """
    Close the current project.
    """
    try:
        del request.session["project"]
    except KeyError:
        pass
    return HttpResponseRedirect("/ocr/")


