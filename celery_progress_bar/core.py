from decimal import Decimal

from celery.result import AsyncResult

PROGRESS_STATE = 'IN_PROGRESS'  # our own
UNKNOWN_STATES = ['PENDING', 'STARTED']

SUCCESS_PROGRESS = {'current': 100, 'total': 100, 'percent': 100}
UNKNOWN_PROGRESS = {'current': 0, 'total': 100, 'percent': 0}


class TaskProgressSetter(object):

    def __init__(self, task, total=100):
        self.task = task
        self.set_progress(0, total)

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
                'percent': percent,
            }
        )


class TaskProgress(object):

    def __init__(self, task_id):
        self.result = AsyncResult(task_id)

    def get_info(self):
        print(self.result.state)
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
                'progress': self.result.info,
            }
        elif self.result.state in UNKNOWN_STATES:
            return {
                'complete': False,
                'success': None,
                'progress': UNKNOWN_PROGRESS,
            }
        return self.result.info
