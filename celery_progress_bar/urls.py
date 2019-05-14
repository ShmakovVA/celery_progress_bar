from django.conf.urls import url

from views import get_task_progress

app_name = "celery_progress_bar"

urlpatterns = [
    url(r'^(?P<task_id>[\w-]+)/$', get_task_progress, name='task_status')
]
