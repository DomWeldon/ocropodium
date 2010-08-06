"""
Callbacks to run when certain celery signals are recieved in response
to the ConvertPageTask.
"""

from celery.registry import tasks
from celery.signals import task_sent, task_prerun, task_postrun
from celery.datastructures import ExceptionInfo

from ocradmin.ocr.tasks import ConvertPageTask, BinarizePageTask 
from ocradmin.ocrtasks.models import OcrTask


def on_task_sent(**kwargs):
    """
    Update the database when a task is sent to the broker.
    """
    task = OcrTask.objects.get(task_id=kwargs.get("task_id"))
    task.status = "PENDING"
    task.save()


def on_task_prerun(**kwargs):
    """
    Update the database when a task is about to run.
    """
    task = OcrTask.objects.get(task_id=kwargs.get("task_id"))
    task.args = kwargs.get("args")
    task.kwargs = kwargs.get("kwargs")
    task.status = "RUNNING"
    task.save()


def on_task_postrun(**kwargs):
    """
    Update the database when a task is finished.
    """
    # don't know what we need to do here yet
    task = OcrTask.objects.get(task_id=kwargs.get("task_id"))
    retval = kwargs.get("retval")
    if isinstance(retval, ExceptionInfo):
        task.error = retval.exception
        task.traceback = retval.traceback
        task.status = "ERROR"
    else:
        task.status = "DONE"
    task.save()

# Connect up signals to the *PageTask
for taskname in [ConvertPageTask.name, BinarizePageTask.name]:
    task_sent.connect(on_task_sent, tasks[taskname])
    task_prerun.connect(on_task_prerun, tasks[taskname])
    task_postrun.connect(on_task_postrun, tasks[taskname])



