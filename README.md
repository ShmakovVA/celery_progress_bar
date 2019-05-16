# Celery Progress Bars (for Django)
extension for django/celery

## Installation

```bash
pip install -e git+git@github.com:Sportamore/celery_progress_bar@0.3#egg=celery_progress_bar
# until release use: pip install -e git+git@github.com:ShmakovVA/celery_progress_bar@0.3#egg=celery_progress_bar
```

## Usage

### Prerequisites

- Add `celery_progress_bar` to your `INSTALLED_APPS` in `settings.py`.
- Add the following url config to `urls.py`:

```python
url(r'^celery_progress_bar/', include('celery_progress_bar.urls')),
```
- Make sure that your Celery configuration in `settings.py` allow result backend (for example): 
```python
CELERY_RESULT_BACKEND = 'rpc://'
CELERY_RESULT_PERSISTENT = False
CELERY_TASK_RESULT_EXPIRES = 60 * 60 * 3  # 3h
CELERY_RESULT_SERIALIZER = 'json'
CELERY_IGNORE_RESULT = False
```

### Changing task progress

In the task:

```python
<...>
from celery_progress_bar.core import TaskProgressSetter

@task(bind=True)
def my_task(self, user_id=None):
    progress_setter = TaskProgressSetter(task=self, user_id=user_id)
    <...>
    progress_setter.set_progress(10, msg='Doing X ...')
    <...>
    progress_setter.set_progress(50, msg='Doing Y ...')
    <...>
    return 'done'
```

### Displaying progress

- In the template (Place component in the base template where you want): 
```djangotemplate
<...>
{% include 'progress_bar.html' %}
<...> 
```

- In the view for `single progress bar` (Throw to the render context `task id`): 

```python
def progress_view(request):
    context = {}
    <...>
    result = my_task.delay(user_id=request.user.pk)
    context.update({'task_id_list': [result.task_id]})
    <...>
    return render(request, 'display_progress.html', context=context)
```

or

- In the view for `multiple progress bar` (Throw to the render context list of `task id`):  

```python
def progress_view(request):
    context = {}
    <...>
    from celery_progress_bar.core import CeleryTaskList
    task_list = CeleryTaskList()
    task_list.active_tasks_by_user_id(request.user.pk)
    context.update({'task_id_list': task_list.task_id_list})
    return render(request, 'display_progress.html', context=context)
```
