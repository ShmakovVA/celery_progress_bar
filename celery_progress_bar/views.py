# -*- coding: utf-8 -*-
from django.http import JsonResponse

from celery_progress_bar.core import TaskProgressGetter


def get_task_progress(request, task_id):
    progress = TaskProgressGetter(task_id)
    return JsonResponse(progress.get_info())
