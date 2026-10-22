"""Eksport offline: zakres, prywatność, integralność i wyłącznie odczyt SQL."""
import hashlib
import io
import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from news.management.commands.export_spinki_archive import counts, model, pseudonym, scopes

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample(settings):
    settings.PUSH_ENABLED = False
    user = get_user_model().objects.create_user(username='archiwistka', email='tajny@example.org')
    public = model('PersonalContextThread').objects.create(
        owner=user, title='Zażółć gęślą jaźń', description='archiwistka: tajny@example.org', is_public=True)
    private = model('PersonalContextThread').objects.create(owner=user, title='PRYWATNY SEKRET')
    hidden = model('PersonalContextThread').objects.create(
        owner=user, title='UKRYTY SEKRET', is_public=True, hidden_at=timezone.now())
    for thread in (public, private, hidden):
        model('PersonalContextThreadItem').objects.create(
            thread=thread, position=0, box_data={'text': thread.title}, note=thread.title)
    old = model('Thread').objects.create(title='Dawna spinka', slug='archiwum', published=True, created_by=user)
    opinion = model('ThreadOpinion').objects.create(user=user, thread=old, polarity='positive', body='tajny@example.org')
    model('ThreadFavorite').objects.create(user=user, thread=old)
    model('CommentReport').objects.create(reporter=user, thread_opinion=opinion, reason='privacy', details='TAJNE ZGŁOSZENIE')
    source = model('Source').objects.create(name='Źródło', url='https://example.org')
    public.sources.add(source)
    article = model('Article').objects.create(source=source, title='Artykuł', url='https://example.org/a')
    other = model('ArticleOpinion').objects.create(user=user, article=article, polarity='positive')
    model('CommentReport').objects.create(reporter=user, article_opinion=other, reason='spam')
    model('Follow').objects.create(user=user, thread=public)
    model('CommunityThreadOpinion').objects.create(user=user, thread=public, polarity='positive', body='Świetnie')
    model('CommunityThreadReport').objects.create(reporter=user, thread=public, reason='spam')
    comment = model('ThreadComment').objects.create(thread=public, author=user, body='Łódź')
    model('ThreadCommentReaction').objects.create(comment=comment, user=user)
    review = model('ThreadReview').objects.create(thread=public, fingerprint='x', payload={'secret': 'TAJNY PAYLOAD'})
    model('ThreadReviewRound').objects.create(review=review, revision=1, role='editor', result='pass', reason='TAJNA RECENZJA')
    report = model('ThreadModerationReport').objects.create(
        thread=public, reporter=user, target_author=user, reason='privacy', snapshot='TAJNY SNAPSHOT')
    decision = model('ThreadModerationDecision').objects.create(report=report, moderator=user, action='hide')
    model('ThreadModerationMail').objects.create(decision=decision, recipient='tajny@example.org')
    for i, topics in enumerate((['nitki-dr-spina', 'obserwowani'], ['spin-dnia'])):
        model('PushSubscription').objects.create(user=user, device=uuid.uuid4(),
            endpoint=f'https://example.org/push/{i}', keys={'auth': 'TAJNY KLUCZ'},
            topics=topics, consent_version='1', consent_at=timezone.now())
    model('NotificationEvent').objects.create(kind='reply', target_id=public.pk)
    model('NotificationEvent').objects.create(kind='post', target_id=public.pk)
    return user


def run(*args):
    output = io.StringIO()
    call_command('export_spinki_archive', *args, stdout=output)
    return output.getvalue()


def test_counts_default_and_explicit(sample):
    data = json.loads(run())
    assert data == json.loads(run('--tylko-liczby'))
    assert data['PersonalContextThread'] == 3
    assert data['PersonalContextThread.publiczne'] == 2
    assert data['PersonalContextThread.prywatne'] == 1
    assert data['PersonalContextThreadItem'] == 3
    for name in ('ThreadFavorite', 'ThreadOpinion', 'Follow', 'CommentReport', 'ThreadReview',
                 'ThreadReviewRound', 'ThreadModerationMail', 'PushSubscription', 'NotificationEvent',
                 'PersonalContextThread_sources'):
        assert data[name] == 1
    assert all(isinstance(n, int) for n in data.values())


@pytest.mark.parametrize('salt', [None, 'stała-sól'])
def test_export_integrity_privacy_read_only(sample, tmp_path, salt):
    destination = tmp_path / 'archive'
    before = counts(scopes())
    with CaptureQueriesContext(connection) as queries:
        run('--eksport', str(destination), *(['--sol', salt] if salt else []))
        run('--tylko-liczby')
    assert counts(scopes()) == before
    assert all(q['sql'].lstrip().upper().startswith('SELECT') for q in queries)
    manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['version'] == 1
    assert manifest['salt'] == salt if salt else len(manifest['salt']) == 64
    for filename, info in manifest['files'].items():
        content = (destination / filename).read_bytes()
        assert hashlib.sha256(content).hexdigest() == info['sha256']
        assert len(content.splitlines()) == info['count']
        assert info['count'] == before[filename.removesuffix('.jsonl')]
    assert hashlib.sha256((destination / 'README.txt').read_bytes()).hexdigest() == manifest['readme_sha256']
    text = '\n'.join(path.read_text(encoding='utf-8') for path in destination.iterdir())
    for secret in ('tajny@example.org', 'archiwistka', 'PRYWATNY SEKRET', 'UKRYTY SEKRET',
                   'TAJNY KLUCZ', 'TAJNY PAYLOAD', 'TAJNY SNAPSHOT', 'TAJNE ZGŁOSZENIE', 'TAJNA RECENZJA', '?' * 2):
        assert secret not in text
    assert 'Zażółć gęślą jaźń' in text
    favorite = json.loads((destination / 'ThreadFavorite.jsonl').read_text(encoding='utf-8'))
    assert 'user_id' not in favorite
    assert favorite['user_hash'] == pseudonym(manifest['salt'], sample.pk)
    threads = [json.loads(line) for line in (destination / 'PersonalContextThread.jsonl').read_text(encoding='utf-8').splitlines()]
    assert sum('title' in row for row in threads) == 1
    assert all(row['owner_hash'] == favorite['user_hash'] for row in threads)


def test_refuse_overwrite_and_error_without_manifest(tmp_path, monkeypatch):
    destination = tmp_path / 'archive'
    destination.mkdir()
    marker = destination / 'keep.txt'
    marker.write_text('zachowaj', encoding='utf-8')
    with pytest.raises(CommandError, match='Nie ukończono'):
        run('--eksport', str(destination))
    assert marker.read_text(encoding='utf-8') == 'zachowaj'
    import news.management.commands.export_spinki_archive as archive
    def broken(*args):
        raise OSError('sensitive@example.org')
    monkeypatch.setattr(archive, 'records', broken)
    with pytest.raises(CommandError, match='Nie ukończono') as exc:
        run('--eksport', str(tmp_path / 'failed'))
    assert 'sensitive@example.org' not in str(exc.value)
    assert not (tmp_path / 'failed' / 'manifest.json').exists()
