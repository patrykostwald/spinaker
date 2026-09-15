"""PostgreSQL-only proof that two workers cannot close one fetch twice."""
import multiprocessing as mp
import os
import queue
from datetime import timedelta
from uuid import UUID

import pytest


def _close_worker(*, request_id, source_id, instruction_id, url, outcome,
                  barrier, results, settings_module, database_url):
    """Spawn-safe worker: it opens its own Django and PostgreSQL connection."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    # A spawned Windows child boots Django from scratch.  Point it at the
    # parent test database, never at the normal development database.
    os.environ['DATABASE_URL'] = database_url
    import django
    django.setup()

    from django.db import connection, connections
    connections.close_all()
    from news.models import FetchAttempt, Source, SourceAccessInstruction
    from scraper.utils import _close_fetch_request

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_backend_pid()')
        backend_pid = cursor.fetchone()[0]
    try:
        barrier.wait(timeout=15)
        _close_fetch_request(
            request_id=UUID(request_id), source=Source.objects.get(pk=source_id),
            instruction=SourceAccessInstruction.objects.get(pk=instruction_id),
            requested_kind=FetchAttempt.RequestedKind.FEED, url=url, outcome=outcome,
            hostname_transport=True,
            http_status=200 if outcome == FetchAttempt.Outcome.OK else 503,
            bytes_received=5 if outcome == FetchAttempt.Outcome.OK else 0,
            response_sha256='a' * 64 if outcome == FetchAttempt.Outcome.OK else '',
            error_code='' if outcome == FetchAttempt.Outcome.OK else 'http_503',
        )
        results.put({'status': 'won', 'outcome': outcome, 'backend_pid': backend_pid})
    except RuntimeError as exc:
        results.put({'status': 'lost', 'outcome': outcome, 'backend_pid': backend_pid,
                     'reason': str(exc)})
    except Exception as exc:  # Returned to the parent so the test fails clearly.
        results.put({'status': 'error', 'outcome': outcome, 'backend_pid': backend_pid,
                     'reason': f'{type(exc).__name__}: {exc}'})


@pytest.mark.django_db(transaction=True)
def test_postgres_workers_close_a_fetch_request_exactly_once():
    """This must run only against a real PostgreSQL test database."""
    from django.conf import settings
    from django.db import connection
    if connection.vendor != 'postgresql':
        pytest.skip(f'PostgreSQL required; current backend is {connection.vendor!r}.')

    from django.utils import timezone
    from news.models import FetchAttempt, FetchRequest, Source, SourceAccessInstruction
    from scraper.utils import _reserve_fetch_request

    source = Source.objects.create(name='Concurrent PostgreSQL test', url='https://example.org',
        catalog_stage='configured', is_active=True, scrape_enabled=True)
    instruction = SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.RSS,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint='https://example.org/feed', terms_url='https://example.org/terms',
        evidence={'basis': 'test'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=1), minimum_interval_seconds=3,
    )
    from uuid import uuid4
    request_id = uuid4()
    _reserve_fetch_request(source=source, instruction=instruction,
        requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
        hostname_transport=True, request_id=request_id)

    context = mp.get_context('spawn')  # Same behavior on Windows and Unix.
    barrier, results = context.Barrier(2), context.Queue()
    from urllib.parse import quote
    database = connection.settings_dict
    database_url = (
        f"postgres://{quote(str(database['USER']), safe='')}:"
        f"{quote(str(database['PASSWORD']), safe='')}@"
        f"{database['HOST'] or '127.0.0.1'}:{database['PORT'] or '5432'}/"
        f"{database['NAME']}"
    )
    common = dict(request_id=str(request_id), source_id=source.pk, instruction_id=instruction.pk,
        url=instruction.endpoint, barrier=barrier, results=results,
        settings_module=settings.SETTINGS_MODULE, database_url=database_url)
    processes = [
        # Pass strings to spawn workers: pickling a Django TextChoices member
        # imports the model before django.setup() in the child process.
        context.Process(target=_close_worker, kwargs={**common, 'outcome': FetchAttempt.Outcome.OK.value}),
        context.Process(target=_close_worker, kwargs={**common, 'outcome': FetchAttempt.Outcome.HTTP_ERROR.value}),
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=25)
        if process.is_alive():
            process.terminate()
            process.join()
            pytest.fail('Concurrent PostgreSQL worker did not finish; possible deadlock.')
        assert process.exitcode == 0

    try:
        outcome_rows = [results.get(timeout=5), results.get(timeout=5)]
    except queue.Empty:
        pytest.fail('Both PostgreSQL workers must report a result.')
    assert {row['status'] for row in outcome_rows} == {'won', 'lost'}, outcome_rows
    assert len({row['backend_pid'] for row in outcome_rows}) == 2, outcome_rows

    request = FetchRequest.objects.get(request_id=request_id)
    terminal = FetchAttempt.objects.filter(request_id=request_id).exclude(
        outcome=FetchAttempt.Outcome.RESERVED)
    assert request.state == FetchRequest.State.CLOSED
    assert request.closed_at is not None
    assert terminal.count() == 1
    assert terminal.get().outcome in {FetchAttempt.Outcome.OK, FetchAttempt.Outcome.HTTP_ERROR}
