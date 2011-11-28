# Create your views here.

from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from ocradmin import storage
from ocradmin.core.decorators import project_required
from ocradmin.core import generic_views as gv


class DocumentForm(forms.Form):
    """New document form."""
    label = forms.CharField(max_length=255, required=False)
    file = forms.FileField()


@project_required
def doclist(request):
    """List documents."""
    storage = request.session["project"].get_storage()
    context = dict(
            page_name="%s: Documents" % storage.name,
            objects=storage.list()
    )
    return render(request, "documents/list.html", context)


@project_required
def edit(request, pid):
    """Edit document with `id`."""
    storage = request.session["project"].get_storage()
    doc = storage.get(pid)
    return render(request, "document/edit.html", dict(object=doc))


@project_required
def create(request):
    """Create a new document."""
    store = request.session["project"].get_storage()
    if not request.method == "POST":
        form = DocumentForm()
        return render(request, "documents/create.html", dict(
            form=form, page_name="%s: Add document" % store.name)
        )

    form = DocumentForm(request.POST, request.FILES)
    if form.is_valid():
        if not form.cleaned_data["label"]:
            form.cleaned_data["label"] = request.FILES["file"].name 
        doc = store.create_document(form.cleaned_data["label"])
        doc.image_content = request.FILES["file"]
        doc.image_mimetype = request.FILES["file"].content_type
        doc.image_label = request.FILES["file"].name
        doc.add_metadata("title", form.cleaned_data["label"])
        doc.add_metadata("status", "draft")
        doc.make_thumbnail()
        doc.save()
        # TODO: Make async
        #doc.save()
    return HttpResponseRedirect("/documents/list")
    

@project_required
def detail(request, pid):
    storage = request.session["project"].get_storage()
    doc = storage.get(pid)
    return render(request, "document/details.html", dict(object=doc))


@project_required
def delete(request, pid):
    storage = request.session["project"].get_storage()
    doc = storage.get(pid)
    return render(request, "document/delete.html", dict(object=doc))

