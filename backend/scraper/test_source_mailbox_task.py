from scraper.tasks import sync_source_mailbox


def test_source_mail_task_returns_disabled_without_credentials(monkeypatch):
    class Disabled(Exception):
        pass
    monkeypatch.setattr('news.mailbox.SourceMailboxDisabled', Disabled)
    monkeypatch.setattr('news.mailbox.sync_inbound', lambda: (_ for _ in ()).throw(Disabled('not_configured')))
    assert sync_source_mailbox() == {'status': 'disabled', 'reason': 'not_configured'}
