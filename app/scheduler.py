"""APScheduler for global ticks (bank interest, territory income, daily reset)."""
import os
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None


def start_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    # Don't double-start under Werkzeug reloader child process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        return None

    scheduler = BackgroundScheduler()

    @scheduler.scheduled_job('interval', hours=1, id='bank_interest')
    def bank_interest_job():
        with app.app_context():
            from .db import get_db
            from .game import apply_bank_interest
            apply_bank_interest(get_db())

    @scheduler.scheduled_job('interval', hours=1, id='territory_income')
    def territory_income_job():
        with app.app_context():
            from .db import get_db
            from .game import accrue_territory
            accrue_territory(get_db())

    @scheduler.scheduled_job('cron', hour=0, minute=0, id='daily_reset')
    def daily_reset_job():
        """Mark daily missions as resettable (handled lazily per player)."""
        pass  # lazy reset happens when the player visits missions page

    scheduler.start()
    _scheduler = scheduler
    return scheduler
