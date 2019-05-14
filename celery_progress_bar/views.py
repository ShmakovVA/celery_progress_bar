import json

from django.http import HttpResponse

from celery_progress_bar.core import TaskProgress


def get_task_progress(request, task_id):
    progress = TaskProgress(task_id)
    info = progress.get_info()
    return HttpResponse(json.dumps(info),
                        content_type='application/json')
