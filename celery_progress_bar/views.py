from django.http import JsonResponse

from celery_progress_bar.core import TaskProgress


def get_task_progress(request, task_id):
    progress = TaskProgress(task_id)
    return JsonResponse(progress.get_info())
