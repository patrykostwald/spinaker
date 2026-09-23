"""Celery tasks owned by the editorial-news domain."""
from celery import shared_task


@shared_task(name="news.tasks.political_poll_task", soft_time_limit=45, time_limit=60)
def political_poll_task():
    """Run at most one due, confirmed political X account.

    ``political_poll_cycle`` is independently opt-in, budgeted and leased.  A
    frequent scheduler tick therefore does not itself make a paid request when
    polling is disabled or no account is due.
    """
    from news.political_polling import political_poll_cycle
    return political_poll_cycle()
