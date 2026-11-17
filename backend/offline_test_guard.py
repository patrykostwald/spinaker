"""Opt-in pytest plugin: fail on unmocked HTTP, SMTP or broker connections."""
import pytest


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Unmocked network request in offline tests')
    monkeypatch.setattr('requests.sessions.Session.request', blocked)
    monkeypatch.setattr('smtplib.SMTP', blocked)
    monkeypatch.setattr('smtplib.SMTP_SSL', blocked)
    monkeypatch.setattr('socket.socket.connect', blocked)
