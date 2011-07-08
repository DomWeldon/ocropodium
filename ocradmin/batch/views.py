"""
Batch-related views.
"""

import os
import glob
from types import MethodType
import tarfile
import StringIO

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core import serializers
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseRedirect, \
        HttpResponseServerError
from django.shortcuts import render, render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson as json
from django.utils.encoding import smart_str
from ocradmin.batch import utils as batchutils
from ocradmin.core import generic_views as gv
from ocradmin.core import utils as ocrutils
from ocradmin.core.decorators import project_required, saves_files
from ocradmin.ocrtasks.models import OcrTask, Batch
from ocradmin.core.views import AppException
from ocradmin.presets.models import Preset
from ocradmin.plugins import stages
from nodetree import script, manager

PER_PAGE = 25

MANAGER = manager.ModuleManager()
MANAGER.register_paths(
                glob.glob("plugins/*_nodes.py"), root="ocradmin")


def batch_query(params):
    """
    Query the batch db.
    """
    order = [x for x in params.getlist("order_by") if x != ""] \
            or ["created_on"]

    query = Q()
    for key, val in params.items():
        if key.find("__") == -1 and \
                not key in Batch._meta.get_all_field_names():
            continue
        if not val:
            continue
        query = query & Q(**{str(key): str(val)})
    query = Batch.objects.select_related().filter(query)
    if order and order[0].replace("-", "", 1) == "task_count":
        query = query.annotate(task_count=Count("tasks"))
    return query.order_by(*order)


class BatchForm(forms.ModelForm):
    """
        New project form.
    """
    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)

        # change a widget attribute:
        self.fields['description'].widget.attrs["rows"] = 2
        self.fields['description'].widget.attrs["cols"] = 40

    class Meta:
        model = Batch
        exclude = ["script", "created_on", "updated_on"]
        widgets = dict(
                user=forms.HiddenInput(),
                project=forms.HiddenInput(),
                task_type=forms.HiddenInput(),
        )


@login_required
@project_required
def new(request):
    """
    Present a new batch form.
    """
    tasktype = "run.batchitem"
    template = "batch/new.html" if not request.is_ajax() \
        else "batch/includes/new_form.html"
    return render(request, template, _new_batch_context(request, tasktype))


batchlist = project_required(login_required(gv.GenericListView.as_view(
        model=Batch,
        page_name="OCR Batches",
        fields=["name", "description", "user", "task_type",
                "created_on", "tasks.count"],)))


@login_required
@project_required
@saves_files
@transaction.commit_on_success
def create(request):
    """
    Create a batch from pre-saved images convert them asyncronously.
    """
    taskname = "run.batchitem"

    # get the subject file paths from comma seperated POST data
    paths = _get_batch_file_paths(request)
    preset = get_object_or_404(Preset, pk=request.POST.get("preset", 0))
    form = BatchForm(request.POST)    
    if not request.method == "POST" or not form.is_valid() or not paths:
        return render(request, "batch/new.html", dict(
            form=form, paths=paths, presets=Preset.objects.all().order_by("name"),
        ))

    # create a batch db job
    # TODO: catch potential integrity error for a duplicate
    # batch name within the given project
    batch = form.instance
    batch.script = preset.data
    batch.save()

    ocrtasks = []
    options = dict(loglevel=60, retries=2)
    for path in paths:
        pagescript = script_for_page_file(batch.script,
                path, request.output_path)
        tid = OcrTask.get_new_task_id()
        args = (path, pagescript, request.output_path)
        kwargs = dict()
        ocrtask = OcrTask(
            task_id=tid,
            user=request.user,
            batch=batch,
            project=request.session["project"],
            page_name=os.path.basename(path),
            task_name=taskname,
            status="INIT",
            args=args,
            kwargs=kwargs,
        )
        ocrtask.save()
        ocrtasks.append(ocrtask)
    try:
        # ignoring the result for now
        OcrTask.run_celery_task_multiple(taskname, ocrtasks, **options)
    except StandardError:
        transaction.rollback()
        raise
    transaction.commit()
    return HttpResponseRedirect("/batch/show/%s/" % batch.pk)


@login_required
def results(request, batch_pk):
    """
    Get results for a taskset.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    try:
        start = max(0, int(request.GET.get("start", 0)))
    except ValueError:
        start = 0
    try:
        limit = max(1, int(request.GET.get("limit", 25)))
    except ValueError:
        limit = 25
    statuses = request.GET.getlist("status")
    name = request.GET.get("name")
    if "ALL" in statuses:
        statuses = None
    response = HttpResponse(mimetype="application/json")
    json.dump(_serialize_batch(batch, start, limit, statuses, name),
            response, cls=DjangoJSONEncoder, ensure_ascii=False)
    return response


@login_required
def page_results(request, batch_pk, page_index):
    """
    Get the results for a single page.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    try:
        page = batch.tasks.all().order_by("page_name")[int(page_index)]
    except Batch.DoesNotExist:
        raise

    pyserializer = serializers.get_serializer("python")()
    response = HttpResponse(mimetype="application/json")
    taskssl = pyserializer.serialize(
        [page],
        excludes=("transcripts", "args", "kwargs",),
    )
    taskssl[0]["fields"]["results"] = page.latest_transcript()
    json.dump(taskssl, response,
            cls=DjangoJSONEncoder, ensure_ascii=False)
    return response


@login_required
@project_required
def latest(request):
    """
    View the latest batch.
    """
    try:
        batch = Batch.objects.filter(
            user=request.user,
            project=request.session["project"]
        ).order_by("-created_on")[0]
    except (Batch.DoesNotExist, IndexError):
        batch = None

    return _show_batch(request, batch)


@login_required
@project_required
def show(request, batch_pk):
    """
    View a batch.
    """
    batch = get_object_or_404(
        Batch,
        pk=batch_pk,
        project=request.session["project"]
    )
    return _show_batch(request, batch)


@login_required
@project_required
@saves_files
def upload_files(request):
    """
    Upload files to the server for batch-processing.
    """
    mimetype = "application/json" if not request.POST.get("_iframe") \
            else "text/html"
    relpath = request.session["project"].slug
    try:
        paths = _handle_upload(request, request.output_path)
    except AppException, err:
        return HttpResponse(json.dumps({"error": err.message}),
            mimetype="application/json")
    if not paths:
        return HttpResponse(
                json.dumps({"error": "no valid images found"}),
                mimetype="application/json")

    pathlist = [os.path.join(relpath, os.path.basename(p)) for p in paths]
    return HttpResponse(json.dumps(pathlist), mimetype=mimetype)


@login_required
@project_required
def transcript(request, batch_pk):
    """
    View the transcription of a batch.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    tid = batch.tasks.all()[0]
    return HttpResponseRedirect("/ocr/transcript/%d/" % tid.pk)


def _show_batch(request, batch):
    """
    View a (passed-in) batch.
    """
    template = "batch/show.html" if not request.is_ajax() \
            else "batch/includes/show_batch.html"
    context = {"batch": batch}
    return render_to_response(template, context,
            context_instance=RequestContext(request))


@transaction.commit_on_success
@login_required
def abort_batch(request, batch_pk):
    """
    Abort an entire batch.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    for task in batch.tasks.all():
        task.abort()
    transaction.commit()
    if request.is_ajax():
        return HttpResponse(json.dumps({"ok": True}),
                mimetype="application/json")
    else:
        return HttpResponseRedirect("/batch/show/%s/" % batch_pk)


@transaction.commit_on_success
@login_required
def retry(request, batch_pk):
    """
    Retry all tasks in a batch.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    for task in batch.tasks.all():
        task.retry()
    transaction.commit()
    if request.is_ajax():
        return HttpResponse(json.dumps({"ok": True}),
                mimetype="application/json")
    else:
        return HttpResponseRedirect("/batch/show/%s/" % batch_pk)


@transaction.commit_on_success
@login_required
def retry_errored(request, batch_pk):
    """
    Retry all errored tasks in a batch.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    for task in batch.errored_tasks():
        task.retry()
    transaction.commit()
    if request.is_ajax():
        return HttpResponse(json.dumps({"ok": True}),
                mimetype="application/json")
    else:
        return HttpResponseRedirect("/batch/show/%s/" % batch_pk)


def test(request):
    """
    Test action
    """
    return render_to_response("batch/test.html",
            {}, context_instance=RequestContext(request))


@login_required
def export_options(request, batch_pk):
    """
    Setup export.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    formats = {"text": "Plain Text", "json": "JSON", "hocr": "HOCR HTML"}
    template = "batch/export_options.html" if not request.is_ajax() \
            else "batch/includes/export_form.html"
    context = dict(
        batch=batch,
        formats=formats
    )
    return render_to_response(template, context,
            context_instance=RequestContext(request))


@login_required
def export(request, batch_pk):
    """
    Export a batch as HOCR.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    formats = {"text": "txt", "json": "json", "hocr": "html"}
    reqformats = request.GET.getlist("format")
    if not reqformats:
        reqformats = ["hocr"]

    #temp = tempfile.TemporaryFile()
    response = HttpResponse(content_type="application/x-gzip")
    tar = tarfile.open(fileobj=response, mode='w|gz')
    for task in batch.tasks.all():
        transcript = task.latest_transcript()
        if transcript is None:
            continue
        for fmt, ext in formats.iteritems():
            if not fmt in reqformats:
                continue
            output = getattr(ocrutils, "output_to_%s" % fmt)(transcript)
            info = tarfile.TarInfo(
                    "%s.%s" % (os.path.splitext(task.page_name)[0], ext))
            info.size = len(output)
            buf = StringIO.StringIO(smart_str(output))
            tar.addfile(info, buf)
    tar.close()
    response["Content-Disposition"] = \
            "attachment: filename=%s.tar.gz" % batch.name
    return response


@login_required
def spellcheck(request):
    """
    Spellcheck some POST data.
    """
    jsondata = request.POST.get("data")
    print "Spellcheck data: %s" % jsondata
    if not jsondata:
        return HttpResponseServerError(
                "No data passed to 'spellcheck' function.")
    data = json.loads(jsondata)
    aspell = batchutils.Aspell()
    response = HttpResponse(mimetype="application/json")
    json.dump(aspell.spellcheck(data), response, ensure_ascii=False)
    return response


@login_required
def delete(request, batch_pk):
    """
    Delete a batch and all tasks belonging to it.
    """
    batch = get_object_or_404(Batch, pk=batch_pk)
    if request.user != batch.user:
        messages.warning(request,
                "Unable to delete batch '%s': Permission denied" % batch.name)
        return HttpResponseRedirect
    batch.delete()
    return HttpResponseRedirect("/batch/list/")


def _serialize_batch(batch, start=0, limit=25, statuses=None, name=None):
    """
    Hack around the problem of serializing
    an object AND it's child objects.
    """
    taskqset = batch.tasks.all()
    if statuses:
        taskqset = batch.tasks.filter(status__in=statuses)
    if name:
        taskqset = taskqset.filter(page_name__icontains=name)    
    task_count = taskqset.count()
    pyserializer = serializers.get_serializer("python")()
    batchsl = pyserializer.serialize(
        [batch],
        extras=("estimate_progress", "is_complete",),
        relations={
            "user": {"fields": ("username")},
            "comparison": {"fields": ()},
        },
    )
    taskssl = pyserializer.serialize(
        taskqset.order_by("page_name")[start:start + limit],
        excludes=("args", "kwargs", "traceback",),
    )
    batchsl[0]["fields"]["tasks"] = taskssl
    batchsl[0]["extras"]["task_count"] = task_count
    return batchsl


def _new_batch_context(request, tasktype):
    """
    Template variables for a new batch form.
    """
    # add available seg and bin presets to the context
    # work out the name of the batch - start with how
    # many other batches there are in the projects
    project = request.session["project"]
    batchname = "%s - Batch %d" % (project.name,
            project.batches.count() + 1)
    form = BatchForm(initial=dict(name=batchname, 
            user=request.user, project=project, task_type=tasktype))
    return dict(form=form, presets=Preset.objects.all().order_by("name"))


def _get_batch_file_paths(request):
    """
    Extract the full file paths from the POST data.
    """
    dirpath = os.path.relpath(os.path.join(
        settings.MEDIA_ROOT,
        settings.USER_FILES_PATH
    ))
    filenames = request.POST.get("files", "").split(",")
    return [os.path.join(dirpath, f) for f in sorted(filenames)]


def _handle_upload(request, outdir):
    """
    Save files and extract parameters.  How this happens
    depends on how the file was send - either multipart
    of as the whole POST body.
    """

    if request.GET.get("inlinefile"):
        return _handle_streaming_upload(request, outdir)
    return _handle_multipart_upload(request, outdir)


def _handle_streaming_upload(request, outdir):
    """
    Handle an upload where the params are in GET and
    the whole of the POST body consists of the file.
    """
    fpath = os.path.join(outdir, request.GET.get("inlinefile"))
    if not os.path.exists(outdir):
        os.makedirs(outdir, 0777)
    tmpfile = file(fpath, "wb")
    tmpfile.write(request.raw_post_data)
    tmpfile.close()
    return [fpath]


def _handle_multipart_upload(request, outdir):
    """
    Handle an upload where the file data is multipart
    encoded in the POST body, along with the params.
    """
    if request.POST.get("png"):
        paths = [ocrutils.media_url_to_path(request.POST.get("png"))]
    else:
        paths = ocrutils.save_ocr_images(request.FILES.iteritems(), outdir)
    return paths

def script_for_page_file(scriptjson, filepath, writepath):
    """
    Modify the given script for a specific file.
    """
    tree = script.Script(json.loads(scriptjson), manager=MANAGER) 
    # get the input node and replace it with out path
    inputs = tree.get_nodes_by_attr("stage", stages.INPUT)
    if not inputs:
        raise IndexError("No input stages found in script")
    input = inputs[0]
    input.set_param("path", filepath)
    # attach a fileout node to the binary input of the recognizer and
    # save it as a binary file
    term = tree.get_terminals()[0]
    outpath = ocrutils.get_binary_path(filepath, writepath)
    outbin = tree.add_node("Utils::FileOut", "OutputBinary",
            params=[
                ("path", os.path.abspath(outpath).encode()),
                ("create_dir", True)])
    outbin.set_input(0, term.input(0))
    return json.dumps(tree.serialize(), indent=2)


