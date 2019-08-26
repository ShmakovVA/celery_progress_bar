# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from time import time

import kombu.five  # for trick with celery `time_start`
from celery.result import AsyncResult
from celery.signals import task_postrun, after_task_publish
from celery.states import SUCCESS
from django.core.cache import caches

CACHE = caches['default']  # should be in settings.py

TASK_INFO_KEY = '%s-task_inf'
TASK_RESULT_KEY = '%s-task_res'

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
    # user_id to cache
    if not CACHE.get(task_id, None) and user_id:
        CACHE.set(task_id, user_id)


##########################################################################
#          Celery-helpers for getting info about tickets                 #
##########################################################################

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
                    'time_start': datetime.fromtimestamp(
                        time() - (kombu.five.monotonic() - task['time_start'])
                    ).replace(microsecond=0),
                    'name': task['name']
                }
                tasks.append(item)
    return tasks


def get_task_info_by_task_id(task_id):
    for task in get_active_tasks():
        if task['task_id'] == task_id:
            return '%s : %s' % (task['time_start'], task['name'])


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

    def __init__(self, task_id, task_info=None):
        self.task_id = task_id
        self.task_info = task_info or self._get_task_info()
        self.result = AsyncResult(task_id)
        self.info = self.result.info
        self.is_finished = False

    @property
    def user(self):
        cache_ = CACHE.get(self.task_id, None)
        try:
            return self.info.get(USER_ID_KEY, None) or cache_
        except Exception as e:
            return cache_

    @property
    def cached_task_info(self):
        return CACHE.get(TASK_INFO_KEY % self.task_id, None)

    def _get_task_info(self):
        return get_task_info_by_task_id(self.task_id)

    def _add_task_info_to_response(self, result_dict):
        if not self.task_info:
            task_info = self.cached_task_info or 'no info'
        else:
            task_info = self.task_info
        result_dict.update({'task_info': task_info})
        return result_dict

    def _success_result(self):
        success_result = {
            'complete': True,
            'success': True,
            'progress': SUCCESS_PROGRESS,
        }
        success_result['progress'][USER_ID_KEY] = self.user
        self.is_finished = True
        return self._add_task_info_to_response(success_result)

    def _error_result(self):
        error_result = {
            'complete': True,
            'success': None,
            'progress': ERROR_PROGRESS,
        }
        error_result['progress'][USER_ID_KEY] = self.user
        self.is_finished = True
        return self._add_task_info_to_response(error_result)

    def _unknown_result(self):
        unknown_result = {
            'complete': False,
            'success': None,
            'progress': UNKNOWN_PROGRESS,
        }
        unknown_result['progress'][USER_ID_KEY] = self.user
        return self._add_task_info_to_response(unknown_result)

    def _progress_result(self):
        progress_result = {
            'complete': False,
            'success': None,
            'progress': self.info,
        }
        # task info to cache if not there yet
        if not self.cached_task_info and self.task_info:
            CACHE.set(TASK_INFO_KEY % self.task_id, self.task_info)
        if not self.task_info:  # task slide out somehow and we were looped here
            self.task_info = self.cached_task_info
            return self._success_result()
        return self._add_task_info_to_response(progress_result)

    def store_result_in_cache(self, _result):
        cache_value = CACHE.get(TASK_RESULT_KEY % self.user, None)
        if cache_value:
            if _result not in cache_value:
                cache_value = cache_value.append(_result)
                CACHE.set(TASK_RESULT_KEY % self.user, cache_value)
        else:
            CACHE.set(TASK_RESULT_KEY % self.user, [_result, ])

    def get_info(self):
        _state = self.result.state
        if self.result.ready():
            if self.result.successful():
                _result = self._success_result()
            else:
                _result = self._error_result()
        elif _state == PROGRESS_STATE:
            _result = self._progress_result()
        elif _state == SUCCESS_STATE:
            _result = self._success_result()
        else:
            _result = self._unknown_result()
        if self.is_finished:
            self.store_result_in_cache(_result)
        return _result


class CeleryTaskList(object):
    """ Helper for get list of task_id and filter them by user_id """

    def __init__(self):
        self.task_id_list = []
        self.active_tasks = get_active_tasks()

    @staticmethod
    def finished_task_result(user_id):
        result = CACHE.get(TASK_RESULT_KEY % user_id, None)
        if result:
            CACHE.delete(TASK_RESULT_KEY % user_id)
            return result

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
