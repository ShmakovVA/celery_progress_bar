# -*- coding: utf-8 -*-
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
CURRENT_KEY = 'current'
TOTAL_KEY = 'total'

SUCCESS_PROGRESS = {CURRENT_KEY: 100, TOTAL_KEY: 100,
                    PERCENT_KEY: 100, USER_ID_KEY: '', MESSAGE_KEY: 'success'}
UNKNOWN_PROGRESS = {CURRENT_KEY: 0, TOTAL_KEY: 100,
                    PERCENT_KEY: 0, USER_ID_KEY: '', MESSAGE_KEY: 'pending'}
ERROR_PROGRESS = {CURRENT_KEY: 100, TOTAL_KEY: 100,
                  PERCENT_KEY: 100, USER_ID_KEY: '', MESSAGE_KEY: 'failure'}


def _make_meta(current, total, percent, user_id, message):
    """
    Meta data for tasks
    :param current: current progress
    :param total: total progress
    :param percent: percentage of completion
    :param user_id:  user_id
    :param message: text message for showing up in progress bar
    :return:
    """
    return {
        CURRENT_KEY: current,
        TOTAL_KEY: total,
        PERCENT_KEY: percent,
        USER_ID_KEY: user_id,
        MESSAGE_KEY: message,
    }


##########################################################################
# Celery-signals for updating meta on after publish and after processing #
##########################################################################

@task_postrun.connect
def task_postrun(signal, sender, task_id, task, args, kwargs, retval, state):
    if state == SUCCESS:
        user_id = CACHE.get(task_id, '')
        task.update_state(
            state=SUCCESS_STATE,
            meta=_make_meta(current=100,
                            total=100,
                            percent=100,
                            user_id=user_id,
                            message=state)
        )


@after_task_publish.connect
def after_task_publish(signal, sender, body, exchange, routing_key):
    user_id = body['kwargs'].get('user_id', None)
    task_id = body['id']
    if not CACHE.get(task_id, None) and user_id:
        CACHE.set(task_id, user_id)


###################################################################
# Classes for set/get/store meta data and status for Celery-tasks #
###################################################################

class TaskProgressSetter(object):
    """ Allow setting the progress of a Celery-task """

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
            meta=_make_meta(current=current,
                            total=total,
                            percent=percent,
                            user_id=self.user_id,
                            message=msg if msg else '')
        )
        self._save_user_id()


class TaskProgressGetter(object):
    """ Allow getting the progress of a Celery-task """

    def __init__(self, task_id):
        self.task_id = task_id
        self.result = AsyncResult(task_id)
        self.info = self.result.info

    @property
    def user(self):
        cache_ = CACHE.get(self.task_id, None)
        try:
            return self.info.get(USER_ID_KEY, None) or cache_
        except Exception as e:
            return cache_

    def _success_result(self):
        success_result = {
            'complete': True,
            'success': True,
            'progress': SUCCESS_PROGRESS,
        }
        success_result['progress'][USER_ID_KEY] = self.user
        return success_result

    def _error_result(self):
        error_result = {
            'complete': True,
            'success': None,
            'progress': ERROR_PROGRESS,
        }
        error_result['progress'][USER_ID_KEY] = self.user
        return error_result

    def _unknown_result(self):
        unknown_result = {
            'complete': False,
            'success': None,
            'progress': UNKNOWN_PROGRESS,
        }
        unknown_result['progress'][USER_ID_KEY] = self.user
        return unknown_result

    def _progress_result(self):
        return {
            'complete': False,
            'success': None,
            'progress': self.info,
        }

    def get_info(self):
        _state = self.result.state
        if self.result.ready():
            if self.result.successful():
                return self._success_result()
            else:
                return self._error_result()
        elif _state == PROGRESS_STATE:
            return self._progress_result()
        elif _state == SUCCESS_STATE:
            return self._success_result()
        else:
            return self._unknown_result()


class CeleryTaskList(object):
    """ Helper for get list of task_id and filter them by user_id """

    def __init__(self):
        self.task_id_list = []
        self.active_tasks = self.get_active_tasks()

    @staticmethod
    def get_active_tasks():
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

    def active_tasks_by_user_id(self, user_id):
        self.task_id_list = []
        user_tasks = []
        for task in self.active_tasks:
            task_id = task['task_id']
            task_user_id = TaskProgressGetter(task_id).user
            if task_user_id == user_id:
                self.task_id_list.append(task_id)
                user_tasks.append(task)
        return user_tasks
