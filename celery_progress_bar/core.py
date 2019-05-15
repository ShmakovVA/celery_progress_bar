from decimal import Decimal

from celery.result import AsyncResult
from celery.signals import task_postrun, after_task_publish
from celery.states import SUCCESS
from django.core.cache import caches

CACHE = caches['default']  # should be in settings.py

PROGRESS_STATE = 'IN_PROGRESS'  # our own `in progress`
SUCCESS_STATE = 'IN_SUCCESS'  # our own `success`

USER_ID_KEY = 'user_id'
PERCENT_KEY = 'percent'
MESSAGE_KEY = 'msg'

READY_PROGRESS = {'current': 100, 'total': 100,
                  PERCENT_KEY: 100, USER_ID_KEY: '', MESSAGE_KEY: 'finished'}
UNKNOWN_PROGRESS = {'current': 0, 'total': 100,
                    PERCENT_KEY: 0, USER_ID_KEY: '', MESSAGE_KEY: 'pending'}
ERROR_PROGRESS = {'current': 100, 'total': 100,
                  PERCENT_KEY: 100, USER_ID_KEY: '', MESSAGE_KEY: 'failure'}


@task_postrun.connect
def task_postrun(signal, sender, task_id, task, args, kwargs, retval, state):
    if state == SUCCESS:
        user_id = CACHE.get(task_id, '')
        task.update_state(
            state=SUCCESS_STATE,
            meta={
                'current': 100,
                'total': 100,
                PERCENT_KEY: 100,
                USER_ID_KEY: user_id,
                MESSAGE_KEY: state,
            }
        )


@after_task_publish.connect
def after_task_publish(signal, sender, body, exchange, routing_key):
    user_id = body['kwargs'].get('user_id', None)
    task_id = body['id']
    if not CACHE.get(task_id, None):
        CACHE.set(task_id, user_id)


class TaskProgressSetter(object):

    def __init__(self, task, user_id=None, total=100):
        self.task = task
        self.task_id = self.task.request.id or None
        self.user_id = user_id if user_id else ''
        self.set_progress(0, total)

    @staticmethod
    def _calc_percent(current, total):
        return round((Decimal(current) / Decimal(total)) * Decimal(100), 2)

    def _save_user_id(self):
        if not CACHE.get(self.task_id, None):
            CACHE.set(self.task_id, self.user_id)

    def set_progress(self, current, msg=None, total=100):
        percent = self._calc_percent(current, total) if total > 0 else 0
        self.task.update_state(
            state=PROGRESS_STATE,
            meta={
                'current': current,
                'total': total,
                PERCENT_KEY: percent,
                USER_ID_KEY: self.user_id,
                MESSAGE_KEY: msg if msg else '',
            }
        )
        self._save_user_id()


class TaskProgress(object):

    def __init__(self, task_id):
        self.task_id = task_id
        self.result = AsyncResult(task_id)
        self.info = self.result.info

    @property
    def user(self):
        cache_ = CACHE.get(self.task_id, None)
        if self.info:
            return self.info.get(USER_ID_KEY, None) or cache_
        else:
            return cache_

    def get_info(self):
        if self.result.ready():
            success = self.result.successful()
            if success:
                return {
                    'complete': True,
                    'success': True,
                    'progress': READY_PROGRESS,
                }
            else:
                return {
                    'complete': True,
                    'success': None,
                    'progress': ERROR_PROGRESS,
                }
        elif self.result.state == PROGRESS_STATE:
            return {
                'complete': False,
                'success': None,
                'progress': self.info,
            }
        elif self.result.state == SUCCESS_STATE:
            return {
                'complete': True,
                'success': True,
                'progress': self.info,
            }
        else:
            unknown_result = {
                'complete': False,
                'success': None,
                'progress': UNKNOWN_PROGRESS,
            }
            unknown_result['progress'][USER_ID_KEY] = self.user
            return unknown_result


class TaskProgressList(object):

    def __init__(self, task_ids):
        self.task_id_list = []
        self.tasks = self.get_all_tasks()

    @staticmethod
    def get_all_tasks():
        import celery
        tasks = []
        inspect = celery.current_app.control.inspect
        active_tasks_of_workers = inspect().active().values()
        if active_tasks_of_workers:
            for worker_active_tasks in active_tasks_of_workers:
                for task in worker_active_tasks:
                    item = {
                        'task_id': task['id'],
                        'time_start': task['time_start'],
                        'name': task['name']
                    }
                    tasks.append(item)
        return tasks

    def filter_tasks_by_user_id(self, user_id):
        self.task_id_list = []
        filtered_tasks = []
        for task in self.tasks:
            task_id = task['task_id']
            task_user_id = TaskProgress(task_id).user
            if task_user_id == user_id:
                self.task_id_list.append(task_id)
                filtered_tasks.append(task)
        return filtered_tasks
