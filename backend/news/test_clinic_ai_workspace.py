import os
import types
import sys

from news import clinic_ai


def test_client_sends_workspace_header_only_when_configured(monkeypatch):
    seen = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setitem(sys.modules, 'anthropic', types.SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'key-for-test-only')
    monkeypatch.delenv('ANTHROPIC_WORKSPACE_ID', raising=False)
    clinic_ai._client()
    assert seen['default_headers'] is None
    monkeypatch.setenv('ANTHROPIC_WORKSPACE_ID', 'wrkspc_test')
    clinic_ai._client()
    assert seen['default_headers'] == {'anthropic-workspace-id': 'wrkspc_test'}
