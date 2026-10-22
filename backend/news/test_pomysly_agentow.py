from io import StringIO

import pytest
from django.core.management import call_command

from news.agent_models import AgentNote


@pytest.mark.django_db
def test_pomysly_agentow_lists_ideas():
    AgentNote.objects.create(agent='wynalazca', kind='idea', title='Alerty o osobach', body='Mail co rano', score=80)
    out = StringIO()
    call_command('pomysly_agentow', stdout=out)
    assert 'Alerty o osobach' in out.getvalue() and 'wynalazca: idea 1' in out.getvalue()
