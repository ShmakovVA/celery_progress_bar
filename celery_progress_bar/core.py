from decimal import Decimal

from celery.result import AsyncResult
from celery.signals import task_postrun

PROGRESS_STATE = 'IN_PROGRESS'  # our own `in progress`
SUCCESS_STATE = 'IN_SUCCESS'  # our own `success`
UNKNOWN_STATES = ['PENDING', 'STARTED']

USER_ID_KEY = 'user_id'
PERCENT_KEY = 'percent'
MESSAGE_KEY = 'msg'

READY_PROGRESS = {'current': 100, 'total': 100,
                  PERCENT_KEY: 100, USER_ID_KEY: '', MESSAGE_KEY: 'finished'}
UNKNOWN_PROGRESS = {'current': 0, 'total': 100,
                    PERCENT_KEY: 0, USER_ID_KEY: '', MESSAGE_KEY: 'unknown'}
ERROR_PROGRESS = {'current': 100, 'total': 100,
                  PERCENT_KEY: 100, USER_ID_KEY: '', MESSAGE_KEY: 'failure'}


@task_postrun.connect
def task_postrun(signal, sender, task_id, task, args, kwargs, retval, state):
    print('%s %s %s' % (state, task_id, signal))
    task.update_state(
        state='IN_SUCCESS',
        meta={
            'current': 100,
            'total': 100,
            'percent': 100,
            'user_id': 1,
            'msg': state,
        }
    )


class TaskProgressSetter(object):

    def __init__(self, task, user_id=None, total=100):
        self.task = task
        self.user_id = user_id if user_id else ''
        self.set_progress(0, total)

    @staticmethod
    def _calc_percent(current, total):
        return round((Decimal(current) / Decimal(total)) * Decimal(100), 2)

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


class TaskProgress(object):

    def __init__(self, task_id):
        self.result = AsyncResult(task_id)
        self.info = self.result.info

    def _get_info_attr(self, attribute_name):
        return getattr(self.info, attribute_name, None)

    @property
    def user(self):
        return self._get_info_attr(USER_ID_KEY)

    @property
    def msg(self):
        return self._get_info_attr(MESSAGE_KEY)

    @property
    def in_percents(self):
        return self._get_info_attr(PERCENT_KEY)

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
            return {
                'complete': False,
                'success': None,
                'progress': UNKNOWN_PROGRESS,
            }
