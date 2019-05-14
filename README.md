# Celery Progress Bars (for Django)
extension for django/celery

## Installation

```bash
pip install -e git+git@github.com:Sportamore/celery_progress_bar@0.2#egg=celery_progress_bar
# until release use: pip install -e git+git@github.com:ShmakovVA/celery_progress_bar@0.2#egg=celery_progress_bar
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
    progress_recorder = TaskProgressSetter(self, user_id)
    <...>
    progress_recorder.set_progress(10)
    <...>
    progress_recorder.set_progress(50)
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

- In the view (Throw to the render context `task id`): 

```python
def progress_view(request):
    context = {}
    <...>
    result = my_task.delay()
    context.update({'task_id': result.task_id})
    <...>
    return render(request, 'display_progress.html', context=context)
```
