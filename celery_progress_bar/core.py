from decimal import Decimal

from celery.result import AsyncResult

PROGRESS_STATE = 'IN_PROGRESS'  # our own
UNKNOWN_STATES = ['PENDING', 'STARTED']

USER_ID_KEY = 'user_id'
PERCENT_ID_KEY = 'percent'

SUCCESS_PROGRESS = {'current': 100, 'total': 100,
                    PERCENT_ID_KEY: 100, USER_ID_KEY: ''}
UNKNOWN_PROGRESS = {'current': 0, 'total': 100,
                    PERCENT_ID_KEY: 0, USER_ID_KEY: ''}


class TaskProgressSetter(object):

    def __init__(self, task, user_id, total=100):
        self.task = task
        self.set_progress(0, total)
        self.user_id = user_id if user_id else ''

    @staticmethod
    def _calc_percent(current, total):
        return round((Decimal(current) / Decimal(total)) * Decimal(100), 2)

    def set_progress(self, current, total=100):
        percent = self._calc_percent(current, total) if total > 0 else 0
        self.task.update_state(
            state=PROGRESS_STATE,
            meta={
                'current': current,
                'total': total,
                PERCENT_ID_KEY: percent,
                USER_ID_KEY: self.user_id,
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
    def in_percents(self):
        return self._get_info_attr(PERCENT_ID_KEY)

    def get_info(self):
        if self.result.ready():
            return {
                'complete': True,
                'success': self.result.successful(),
                'progress': SUCCESS_PROGRESS
            }
        elif self.result.state == PROGRESS_STATE:
            return {
                'complete': False,
                'success': None,
                'progress': self.info,
            }
        elif self.result.state in UNKNOWN_STATES:
            return {
                'complete': False,
                'success': None,
                'progress': UNKNOWN_PROGRESS,
            }
        return self.info
