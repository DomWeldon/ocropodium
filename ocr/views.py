import os
import traceback
import uuid

from celery import result as celeryresult
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import simplejson

from ocradmin.ocr import tasks
from ocradmin.ocr import utils as ocrutils
from ocradmin.ocrtasks.models import OcrTask, OcrBatch 
from ocradmin.ocrmodels.models import OcrModel
from ocradmin.ocrmodels.views import model_query

class AppException(Exception):
    pass




@login_required
@transaction.commit_manually
def convert(request):
    """
        Save a posted image to the DFS.  Convert it with Celery.
        Then delete the image.
    """

    if not request.method == "POST":
        return render_to_response(
            "ocr/convert.html", {}, 
            context_instance=RequestContext(request)
        )

    # save our files to the DFS and return a list of addresses
    try:
        paths = ocrutils.save_ocr_images(request.FILES.iteritems(), temp=True)
    except AppException, e:
        return HttpResponse(
            simplejson.dumps({"error": e.message}),
            mimetype="application/json"
        )
    if not paths:
        return HttpResponse(
            simplejson.dumps({"error": "no valid images found"}),
            mimetype="application/json"
        )     
    
    # wrangle the params - this needs improving
    userparams = _get_best_params(request.POST.copy())

    # create a batch db job
    batch = OcrBatch(user=request.user, type="ONESHOT")
    batch.save()

    # init the job from our params
    asynctasks = []
    for path in paths:
        tid = "%s::%s" % (os.path.basename(path), uuid.uuid1())
        ocrtask = OcrTask(task_id=tid, batch=batch, 
                page=os.path.basename(path), status="INIT")
        ocrtask.save()
        asynctasks.append(
            tasks.ConvertPageTask.apply_async(
                args=(path.encode(), userparams),
                task_id=tid,
                loglevel=60,
                retries=2,
            )
        )            

    try:
        # aggregate the results
        out = []
        for async in asynctasks:
            results = async.wait() if _should_wait(request) else async.result
            out.append({
                "job_name": async.task_id,
                "status": async.status,
                "results": results,
            })
        # should be past the danger zone now
        transaction.commit()
        return _json_or_text_response(request, out)
    except StandardError, e:        
        transaction.rollback()
        return HttpResponse(
            simplejson.dumps({
                "error": str(e), 
                "trace": traceback.extract_stack()
            }),
            mimetype=mimetype
        ) 


@login_required
def results(request, job_name):
    async = celeryresult.AsyncResult(job_name)
    if async is None:
        raise Http404

    return _json_or_text_response(
        request, {
            "job_name": async.task_id,
            "status": async.status,
            "results": async.result
        }
    )




def _wants_text_format(request):
    """
    Determine whether we should send back plain text instead of JSON.
    """    
    return request.META.get("HTTP_ACCEPT", "") == "text/plain" \
        or request.GET.get("format", "") == "text" \
        or request.POST.get("format", "") == "text"


def _should_wait(request):
    """
    Determine if we should block waiting for the results.  The
    default is to not block.
    """
    return request.GET.get("wait", False)


def _json_or_text_response(request, json):
    """
    Format the output string accordingly.
    """
    results = ""
    mimetype = "application/json"
    if _wants_text_format(request):
        if isinstance(json, dict):
            json = [json]
        mimetype = "text/plain"
        for page in json:
            if page.get("results"):
                results += ocrutils.output_to_plain_text(page.get("results"))
                results += "\n"
    else:
        results = simplejson.dumps(json)
    return HttpResponse(results, mimetype=mimetype)


def _get_best_params(postdict):
    """
    Attempt to determine the best params if not specified in
    POST.  This is continent on data in the models table.
    """

    userparams = postdict
    userparams["engine"] = (postdict.get("engine", "tesseract")).encode()
    userparams["clean"] = (postdict.get("clean", "StandardPreprocessing")).encode()
    userparams["pseg"] = (postdict.get("pseg", "SegmentPageByRAST")).encode()
    for modparam in ("cmodel", "lmodel"):
        try:
            model = OcrModel.objects.get(name=userparams.get(modparam, "???"))
            userparams[modparam] = model.file.path            
        except OcrModel.DoesNotExist, e:
            # try and choose the best model accordingly - this is a model
            # named "Default Something"
            modtype = "char" if modparam == "cmodel" else "lang"
            try:
                model = OcrModel.objects.filter(
                    name__icontains="default",
                    app__iexact=userparams["engine"],
                    type__iexact=modtype,
                )[0]
                userparams[modparam] = model.file.path            
            except IndexError, e:
                userparams[modparam] = "???" 

    return userparams    
