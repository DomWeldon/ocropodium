import os
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError 
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson
from django import forms
from ocradmin.ocr import utils as ocrutils
from ocradmin.ocr.views import _get_best_params
from ocradmin.ocrpresets.models import OcrPreset
from ocradmin.ocrmodels.models import OcrModel
from ocradmin.ocrtasks.models import OcrTask, OcrBatch
from ocradmin.training.models import OcrComparison, ParameterScore
from ocradmin.projects.models import ReferencePage        
from ocradmin.projects.utils import project_required
from ocradmin.training.tasks import LineTrainTask, ComparisonTask, \
        MakeThumbnailTask


class ReferenceSetForm(forms.Form):
    """
    Form for submitting a new training set.
    """
    name = forms.CharField()
    cmodel = forms.ModelChoiceField(
            queryset=OcrModel.objects.filter(type="char", app="ocropus"))
    notes = forms.CharField(required=False)


class ComparisonForm(forms.Form):
    """
    Form for submitting a new comparison job.
    """
    name = forms.CharField()
    notes = forms.CharField(required=False, widget=forms.widgets.Textarea())

    def __init__(self, *args, **kwargs):
        super(forms.Form, self).__init__(*args, **kwargs)

        # change a widget attribute:
        self.fields['notes'].widget.attrs["rows"] = 2
        self.fields['notes'].widget.attrs["cols"] = 40


def comparison_query(order, **params):
    """
        Query the comparison set.
    """

    try:
        del params["tag"]
    except KeyError:
        pass

    query = Q()
    for key, val in params.items():
        ld = {key:val}
        query = query & Q(**ld)

    # if there's a tag present search by tagged item
    return OcrComparison.objects\
            .filter(query)\
            .order_by(*order)\
            .annotate(groundtruths=Count("parameter_scores__ground_truth"))



@project_required
@login_required
def new(request):
    """
    Show a new training task form.
    """
    # initialize the training set name
    project = request.session["project"]
    trainnum = project.tasks.filter(task_type="train").count() + 1
    name = "%s Training %d" % (project.name, trainnum)

    template = "training/new.html"
    context = dict(
        form=ReferenceSetForm(initial=dict(name=name)),
        project=request.session["project"],
        tsets=request.session["project"].reference_sets.all(),
    )
    return render_to_response(template, context, 
            context_instance=RequestContext(request))


@project_required
@login_required
def create(request):
    """
    Create a new training task.
    """
    project = request.session["project"]
    form = TrainingSetForm(request.POST)
    formok = form.is_valid()
    try: 
        tsets = ReferencePage.objects.filter(pk__in=request.POST.getlist("tset"))
    except ReferencePage.DoesNotExist:
        formok = False

    if not formok:
        template = "training/new.html"          
        context = dict(
            form=form,
            tsets=project.reference_sets.all(),
            project=project,
        )
        return render_to_response(template, context, 
                context_instance=RequestContext(request))
    
    name = form.cleaned_data["name"]
    cmodel = form.cleaned_data["cmodel"]
    # we're ok with the params... now get a temporary
    # output path:
    outpath = ocrutils.FileWrangler(
        username=request.user.username,
        temp=True,
        action="train",
        stamp=True,        
    )()
    
    # make us a new task entry
    tid = ocrutils.get_new_task_id()    
    args = ([t.pk for t in tsets], cmodel.pk, outpath)
    # Note: could add a 'queue' param here
    kwargs = dict(task_id=tid, loglevel=60, retries=2,) 
    task = OcrTask(
        task_id=tid,
        user = request.user,
        project = project,
        page_name=name,
        task_type="train",
        status="INIT",
        args=args,
        kwargs=kwargs,        
    )
    task.save()
    LineTrainTask.apply_async(args=args, **kwargs)

    return HttpResponseRedirect("/ocrtasks/list")


@project_required
@login_required
def compare(request):
    """
    Show a form allowing the user to
    submit a job comparing the results
    of two cmodels on a training set.
    """
    template = "training/compare.html"
    return render_to_response(template, _get_comparison_context(request),
            context_instance=RequestContext(request))


@transaction.commit_on_success
@project_required
@login_required
def score_models(request):
    """
    Run a comparison between two sets of OCR parameters.
    """

    form = ComparisonForm(request.POST)
    project = request.session["project"]

    try:
        tsets = ReferencePage.objects.filter(pk__in=request.POST.getlist("tset"))
        assert(form.is_valid())
    except (ReferencePage.DoesNotExist, AssertionError):
        # FIXME: remove code dup!
        template = "training/compare.html"
        return render_to_response(template, _get_comparison_context(request),
                context_instance=RequestContext(request))

    outdir = ocrutils.FileWrangler(
            username=request.user.username, temp=True, action="compare")()

    asyncparams = []
    # create a batch db job
    batch = OcrBatch(
        user=request.user,
        name="Model Scoring %s" % datetime.now(),
        description="",
        task_type=ComparisonTask.name,
        batch_type="COMPARISON", 
        project=request.session["project"]
    )
    batch.save()

    comparison = OcrComparison(
        name=form.cleaned_data["name"],
        notes=form.cleaned_data["notes"],
        batch=batch,
    )
    comparison.save()

    # get parameter sets
    paramsets = _get_paramset_list(request)
    
    for gtruth in tsets:
        path = gtruth.source_image_path
        for i in range(len(paramsets)):
            params = paramsets[i]
            tid = ocrutils.get_new_task_id(path)
            args = (gtruth.pk, outdir.encode(), params)
            kwargs = dict(task_id=tid, loglevel=60, retries=2)
            task = OcrTask(
                task_id=tid,
                user=request.user,
                batch=batch,
                project=request.session["project"],
                page_name="%s" % os.path.basename(os.path.splitext(path)[0]),
                task_type="compare",
                task_name=ComparisonTask.name,
                status="INIT",
                args=args,
                kwargs=kwargs,
            )
            task.save()
            asyncparams.append((args, kwargs))            

            # create a score record for this task
            score = ParameterScore(
                name="Settings %d" % (i+1),                
                task=task,
                comparison=comparison,
                ground_truth=gtruth
            )
            score.save()
    # launch all the tasks (as comparisons, not converts)
    publisher = ComparisonTask.get_publisher(connect_timeout=5)    
    try:
        for args, kwargs in asyncparams:
            ComparisonTask.apply_async(args=args, publisher=publisher, **kwargs)
    finally:
        publisher.close()
        publisher.connection.close()
    return HttpResponseRedirect("/batch/show/%s/" % batch.pk) 
    

@project_required
@login_required
def comparison_from_batch(request):
    """
    View details of a model comparison.
    """
    batch = get_object_or_404(OcrBatch, pk=request.GET.get("batch", 0))
    try:
        cpk = batch.ocrcomparison.pk
    except OcrComparison.DoesNotExist:
        cpk = 0
    return comparison(request, cpk)


@project_required
@login_required
def comparison(request, comparison_pk):
    """
    View details of a model comparison.
    """
    comparison = get_object_or_404(OcrComparison, pk=comparison_pk)
    scores = comparison.parameter_scores.order_by("pk", "name", "ground_truth")
    ordered = {}
    for score in scores:
        if ordered.get(score.ground_truth.pk):
            ordered[score.ground_truth.pk].append(score)
        else:
            ordered[score.ground_truth.pk] \
                = [score.ground_truth.data["page"], score,]

    name_a = scores[0].name
    name_b = scores[1].name

    # this is really dodgy - total the scores for each model
    total_a = total_b = 0
    count_a = count_b = 0
    for i in range(0, len(scores)):
        if i % 2 == 0:
            if scores[i].score is None:
                continue
            total_a += scores[i].score
            count_a += 1
        else:
            if scores[i].score is None:
                continue
            total_b += scores[i].score
            count_b += 1
    if not total_a is None and not total_b is None:
        total_a /= count_a
        total_b /= count_b

    template = "training/comparison.html" if not request.is_ajax() \
            else "training/includes/comparison_details.html"
        
    context = dict(
        comparison=comparison,
        ordered=ordered,
        model_a=name_a,
        model_b=name_b,
        total_a=total_a,
        total_b=total_b,
    )
    return render_to_response(template, context,
            context_instance=RequestContext(request))


@project_required
@login_required
def show_paramscore(request, paramscore_pk):
    """
    Display the accuracy internals of a model score.
    """
    score = get_object_or_404(ParameterScore, pk=paramscore_pk)
    result = score.task.latest_transcript()
    context = dict(
        modelscore=score,
        task=score.task,
        text=ocrutils.output_to_plain_text(result),
        json=result
    )
    template = "training/show_modelscore.html" if not request.is_ajax() \
            else "training/includes/modelscore.html"
    return render_to_response(template, context,
            context_instance=RequestContext(request))
            

@project_required
@login_required
def save_task(request, task_pk):
    """
    Save a page and it's binary image as 
    training data.
    """
    task = get_object_or_404(OcrTask, pk=task_pk)

    srcpath = task.args[0]
    binurl = request.POST.get("binary_image")
    if not binurl:
        raise HttpResponseServerError("No binary image url given.")
    binpath = ocrutils.media_url_to_path(binurl)
    if not os.path.exists(binpath):
        raise HttpResponseServerError("Binary image does not exist")

    outpath = ocrutils.FileWrangler(
        username=request.user.username,
        project_id=request.session["project"].pk,
        training=True,
        temp=False,
    )()
    if not os.path.exists(outpath):
        os.makedirs(outpath)
        os.chmod(outpath, 0777)
    srcoutpath = os.path.join(outpath, os.path.basename(srcpath))    
    binoutpath = os.path.join(outpath, os.path.basename(binpath))
    import shutil
    shutil.copy2(srcpath, srcoutpath)
    shutil.copy2(binpath, binoutpath)

    # try and create a thumbnail of the file
    MakeThumbnailTask.apply_async((srcoutpath, settings.THUMBNAIL_SIZE), 
            queue="interactive", retries=2)
    
    # create or update the model
    try:
        tpage = ReferencePage.objects.get(
            project=request.session["project"], 
            user=request.user,
            binary_image_path=binoutpath
        )
    except ReferencePage.DoesNotExist:
        tpage = ReferencePage()

    try:
        tpage.page_name = task.page_name
        tpage.user = request.user
        tpage.project = request.session["project"]
        tpage.data = task.latest_transcript()
        tpage.source_image_path = srcoutpath
        tpage.binary_image_path = binoutpath
        tpage.save()
    except IntegrityError, err:
        return HttpResponse(simplejson.dumps({"error": str(err)}),
                mimetype="application/json")
    
    return HttpResponse(simplejson.dumps({"ok": True}),
            mimetype="application/json")

    
@project_required
@login_required
def list(request):
    """
    List training page info.
    """
    project = request.session["project"]
    context = dict(
        project=project,
        reference_sets=project.reference_sets.all(),
    )
    template = "training/list.html" if not request.is_ajax() \
            else "training/includes/reference_set_list.html"
    return render_to_response(template, context,
            context_instance=RequestContext(request))


@project_required
@login_required
def comparisons(request):
    """
    List the Model comparisons.
    """
    order = request.GET.get("order", "created_on")
    fields = [ "name", "created_on", "groundtruths",]
    # add a 'invert token' if we're ordering by the
    # same field again
    fields = map(lambda x: "-%s" % x if x == order else x, fields)
    context = dict(
        comparisons=comparison_query([order, "created_on"]),
        fields=fields,
        order=order,
    )
    template = "training/comparisons.html" if not request.is_ajax() \
            else "training/includes/comparison_list.html"
    return render_to_response(template, context,
            context_instance=RequestContext(request))


@project_required
@login_required
def show(request, page_pk):
    """
    Show training page info.
    """    
    tpage = get_object_or_404(ReferencePage, pk=page_pk)
    context = dict(trainpage=tpage)
    template = "training/show.html" if not request.is_ajax() \
            else "training/includes/show_info.html"
    return render_to_response(template, context,
            context_instance=RequestContext(request))


def _get_paramset_list(request):
    """
    Parse sets of distinct params from the POST data.
    They all have a prefix p0_ .. pN_
    """
    paramsets = []
    pinit = 0
    while True:
        params = _get_best_params(request.POST, with_prefix="p%d_" % pinit)
        if len(params) == 0:
            break
        paramsets.append(params)
        pinit += 1
    return paramsets


def _get_comparison_context(request):
    """
    Get the context for rendering the compare form.
    """
    return dict(
        form=ComparisonForm(initial={"name": "Parameter Comparison"}),
        prefixes=["p0_", "p1_"],
        project=request.session["project"],
        binpresets=OcrPreset.objects.filter(type="binarize").order_by("name"),
        segpresets=OcrPreset.objects.filter(type="segment").order_by("name"),
        tsets=request.session["project"].reference_sets.all(),
    )
    
