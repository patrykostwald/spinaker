import pytest
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from news.models import Article, Source, QualityIssue, ImportState
from scraper import quality
from scraper.quality import scan_quality

@pytest.mark.django_db
def test_quality_preserves_sources_and_resolves_only_flags():
    source = Source.objects.create(name='Test', url='https://example.org')
    a = Article.objects.create(source=source, title='Original', description='Exact text', url='https://example.org/a', category='other')
    before = Article.objects.values().get(pk=a.pk)
    assert scan_quality(1)['findings'] == 2
    assert Article.objects.values().get(pk=a.pk) == before
    assert QualityIssue.objects.filter(active=True).count() == 2
    scan_quality(1)
    assert QualityIssue.objects.count() == 2
    a.published_date = timezone.now(); a.category = 'article'; a.save()
    scan_quality(1)
    assert QualityIssue.objects.filter(active=True).count() == 0
    a.refresh_from_db(); assert a.description == 'Exact text'

@pytest.mark.django_db
def test_duplicates_flagged_not_deleted():
    source = Source.objects.create(name='Test', url='https://example.org')
    date = timezone.now()
    for i in range(2):
        Article.objects.create(source=source, title='Same title', url=f'https://example.org/{i}', published_date=date)
    scan_quality(10)
    assert QualityIssue.objects.filter(code='possible_duplicate', active=True).count() == 2
    assert Article.objects.count() == 2


def make_articles(source, count, prefix='a'):
    return Article.objects.bulk_create([Article(source=source, title=f'{prefix} {i}',
        url=f'https://example.org/{prefix}/{i}', category='other') for i in range(count)])


@pytest.mark.django_db
def test_new_work_does_not_starve_old_review_or_reset_new_cursor():
    source = Source.objects.create(name='Test', url='https://example.org')
    old = make_articles(source, 10, 'old')
    scan_quality(10)
    old[0].published_date = timezone.now()
    old[0].category = 'article'
    old[0].save()
    new = make_articles(source, 20, 'new')
    before_source = Source.objects.values().get(pk=source.pk)
    result = scan_quality(10)
    state = ImportState.objects.get(name='quality:metadata')
    assert result['reviewed'] == 1
    assert result['new_checked'] == 9
    assert not QualityIssue.objects.filter(article=old[0], active=True).exists()
    assert state.cursor['last_pk'] == new[8].pk
    assert state.cursor['review_pk'] == old[0].pk
    assert state.cursor['review_ceiling'] == old[-1].pk
    assert Source.objects.values().get(pk=source.pk) == before_source


@pytest.mark.django_db
def test_old_review_continues_when_new_records_keep_arriving():
    source = Source.objects.create(name='Test', url='https://example.org')
    old = make_articles(source, 3, 'old')
    scan_quality(10)
    for i in range(3):
        make_articles(source, 10, f'new{i}')
        result = scan_quality(10)
        assert result['reviewed'] == 1
        assert result['new_checked'] == 9
        state = ImportState.objects.get(name='quality:metadata')
        assert state.cursor['review_ceiling'] == old[-1].pk
        assert state.cursor['review_pk'] == old[i].pk


@pytest.mark.django_db
def test_failed_batch_rolls_back_flags_and_checkpoint_together():
    source = Source.objects.create(name='Test', url='https://example.org')
    articles = make_articles(source, 120)
    original_create = QualityIssue.objects.bulk_create
    calls = []

    def fail_after_write(*args, **kwargs):
        result = original_create(*args, **kwargs)
        calls.append(len(result))
        if len(calls) == 2:
            raise RuntimeError('Simulated failure after writing flags')
        return result

    with patch.object(QualityIssue.objects, 'bulk_create', side_effect=fail_after_write):
        with pytest.raises(RuntimeError, match='Simulated failure'):
            scan_quality(120)
    state = ImportState.objects.get(name='quality:metadata')
    assert state.cursor['last_pk'] == articles[49].pk
    assert state.cursor['checked'] == 50
    assert 'lease_id' not in state.cursor
    assert 'Simulated failure' in state.last_error
    assert QualityIssue.objects.count() == 100
    assert not QualityIssue.objects.filter(article_id__gte=articles[50].pk).exists()
    scan_quality(120)
    state.refresh_from_db()
    assert state.cursor['last_pk'] == articles[-1].pk
    assert state.last_error == ''
    assert QualityIssue.objects.count() == 240


@pytest.mark.django_db
def test_new_article_created_during_scan_is_not_skipped():
    source = Source.objects.create(name='Test', url='https://example.org')
    articles = make_articles(source, 1)
    original_findings = quality.findings
    inserted = []

    def add_during_read(article, now):
        if not inserted:
            inserted.extend(make_articles(source, 1, 'late'))
        return original_findings(article, now)

    with patch.object(quality, 'findings', side_effect=add_during_read):
        scan_quality(1)
    state = ImportState.objects.get(name='quality:metadata')
    assert state.cursor['last_pk'] == articles[0].pk
    scan_quality(1)
    state.refresh_from_db()
    assert state.cursor['last_pk'] == inserted[0].pk
    assert QualityIssue.objects.filter(article=inserted[0]).count() == 2


@pytest.mark.django_db
def test_busy_lease_and_expired_lease_resume_without_skipping():
    source = Source.objects.create(name='Test', url='https://example.org')
    articles = make_articles(source, 1)
    state = ImportState.objects.create(name='quality:metadata', cursor={
        'last_pk': 0, 'lease_id': 'other-worker',
        'lease_until': (timezone.now() + timedelta(seconds=60)).isoformat()})
    assert scan_quality(1)['status'] == 'busy'
    assert not QualityIssue.objects.exists()
    state.cursor['lease_until'] = (timezone.now() - timedelta(seconds=1)).isoformat()
    state.save()
    assert scan_quality(1)['checked'] == 1
    state.refresh_from_db()
    assert state.cursor['last_pk'] == articles[0].pk
    assert 'lease_id' not in state.cursor


@pytest.mark.django_db
def test_budget_finishes_current_small_batch_and_leaves_remaining_work():
    source = Source.objects.create(name='Test', url='https://example.org')
    articles = make_articles(source, 120)
    original_findings = quality.findings
    clock = [0.0]

    def slow_first_read(article, now):
        clock[0] = 0.08
        return original_findings(article, now)

    with (patch.object(quality, 'findings', side_effect=slow_first_read),
          patch.object(quality.time, 'perf_counter', side_effect=lambda: clock[0]),
          patch.object(quality.time, 'sleep')):
        result = scan_quality(120, max_seconds=0.05)
    assert result['checked'] == 50
    assert result['budget_exhausted'] is True
    assert result['batches'] == 1
    state = ImportState.objects.get(name='quality:metadata')
    assert state.cursor['last_pk'] == articles[49].pk


@pytest.mark.django_db
def test_unrelated_flags_and_first_detected_are_preserved():
    source = Source.objects.create(name='Test', url='https://example.org')
    article = make_articles(source, 1)[0]
    independent = QualityIssue.objects.create(article=article, code='manual_review', evidence={'exact': 'leave'})
    scan_quality(1)
    first_detected = QualityIssue.objects.get(article=article, code='missing_date').first_detected
    before = QualityIssue.objects.values().get(pk=independent.pk)
    scan_quality(1)
    assert QualityIssue.objects.values().get(pk=independent.pk) == before
    assert QualityIssue.objects.get(article=article, code='missing_date').first_detected == first_detected


@pytest.mark.django_db
def test_duplicate_query_preserves_exact_source_title_and_date_semantics():
    source = Source.objects.create(name='Test', url='https://example.org')
    another = Source.objects.create(name='Another', url='https://example.net')
    date = timezone.now()
    target = Article.objects.create(source=source, title='Title', url='https://example.org/target', published_date=date)
    duplicate = Article.objects.create(source=source, title='Title', url='https://example.org/duplicate', published_date=date)
    Article.objects.create(source=source, title='Title', url='https://example.org/later', published_date=date + timedelta(seconds=1))
    Article.objects.create(source=source, title='Different', url='https://example.org/different', published_date=date)
    Article.objects.create(source=another, title='Title', url='https://example.net/same', published_date=date)
    assert quality.findings(target, date)['possible_duplicate']['other_article_ids'] == [duplicate.pk]
