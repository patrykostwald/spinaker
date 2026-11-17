from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_diagnozy_dzis_runs_on_empty_db():
    out = StringIO()
    call_command('diagnozy_dzis', stdout=out)
    assert 'Brak udanych diagnoz' in out.getvalue() and 'W kolejce' in out.getvalue()
