from news import tasks


def test_political_poll_task_delegates_to_guarded_cycle(monkeypatch):
    expected = {'status': 'idle', 'reason': 'no_confirmed_due_accounts', 'new_posts': 0}
    monkeypatch.setattr('news.political_polling.political_poll_cycle', lambda: expected)

    assert tasks.political_poll_task() == expected
