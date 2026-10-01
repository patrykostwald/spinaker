from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic
from news.clinic_corrections import corrections_data
from news.clinic_models import ClinicAuthorReply, ClinicDailyMessage, SpinDiagnosis, WeeklyReport
from news.test_clinic import account, post, staff

pytestmark = pytest.mark.django_db


def diagnosis(acc=None, number=1, **kwargs):
    return SpinDiagnosis.objects.create(post=post(acc or account(), str(number)), **{
        'status': 'approved', 'verdict': 'spin', 'intensity': 95, 'headline': 'Błędny nagłówek AI',
        'analysis': 'Błędna analiza AI', 'summary': 'Błędne podsumowanie AI', 'diagnosed_at': timezone.now(),
        **kwargs})


def reply(row, **kwargs):
    return ClinicAuthorReply.objects.create(diagnosis=row, body='Stanowisko autora wypowiedzi.',
                                            source_url='https://example.org/odpowiedz', **kwargs)


@pytest.mark.parametrize('status', ['pending_review', 'rejected', 'flagged', 'queued', 'failed', 'not_applicable', 'withdrawn'])
def test_withdraw_only_from_approved(status):
    row = diagnosis(status=status)
    with pytest.raises(ValueError):
        clinic.withdraw(row, staff(), 'Niepoprawne źródło.')
    row.refresh_from_db()
    assert row.withdrawn_at is None and row.status == status


@pytest.mark.parametrize('reason', ['', '  \n ', 'x' * 401, None])
def test_withdraw_requires_reason(reason):
    row = diagnosis()
    with pytest.raises(ValueError):
        clinic.withdraw(row, staff(), reason)
    assert SpinDiagnosis.objects.get(pk=row.pk).status == 'approved'


def test_withdraw_preserves_ai_and_rejects_stale_objects_and_non_staff():
    row = diagnosis()
    old = SpinDiagnosis.objects.get(pk=row.pk)
    before = SpinDiagnosis.objects.filter(pk=row.pk).values().get()
    member = get_user_model().objects.create_user('reader')
    with pytest.raises(PermissionError):
        clinic.withdraw(row, member, 'Powód')
    member.is_staff = True
    member.save()
    clinic.withdraw(row, member, '  Źródło nie potwierdza wniosku.  ')
    after = SpinDiagnosis.objects.filter(pk=row.pk).values().get()
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {'status', 'withdrawn_at', 'withdrawn_by_id', 'withdrawn_reason'}
    assert row.withdrawn_reason == 'Źródło nie potwierdza wniosku.'
    with pytest.raises(ValueError):
        clinic.withdraw(old, member, 'Drugi powód')


def test_withdraw_removes_public_surfaces_and_cached_stats():
    row = diagnosis()
    client = APIClient()
    cache.clear()
    assert client.get('/api/clinic/stats/').data['totals']['diagnosed']['total'] == 1
    message = ClinicDailyMessage.objects.create(day=timezone.localdate(), camp='opposition', status='approved',
                                               message='Stara synteza', analysis='Stara analiza')
    message.posts.add(row.post)
    reply(row)
    clinic.withdraw(row, staff(), 'Źródło nie potwierdza wniosku.')
    for params in ({}, {'q': 'Błędny'}, {'sort': 'strong', 'page_size': 3}):
        assert client.get('/api/clinic/spins/', params).data['results'] == []
    assert client.get('/api/clinic/stats/').data['totals']['diagnosed']['total'] == 0
    page = client.get('/api/clinic/').data
    assert page['columns']['opposition'] == []
    assert page['spin_of_day'] is None and page['latest_spin'] is None
    assert clinic.daily_message_data('opposition') is None
    assert client.get('/api/clinic/messages/').data['results'] == []
    assert client.get(f'/api/clinic/messages/{message.day}/').status_code == 404
    assert client.get(f'/api/clinic/spins/{row.pk}/card.png').status_code == 404
    assert client.get(f'/api/clinic/spins/{row.pk}/comments/').status_code == 404
    detail = client.get(f'/api/clinic/spins/{row.pk}/')
    assert detail.status_code == 200 and detail.data['status'] == 'withdrawn'
    assert detail['X-Robots-Tag'] == 'noindex' and detail['Cache-Control'] == 'no-store'
    assert set(detail.data) == {'id', 'status', 'withdrawn_at', 'withdrawn_reason', 'author', 'camp', 'camp_label', 'post', 'author_replies'}
    assert set(detail.data['post']) == {'url', 'published_at'}
    assert len(detail.data['author_replies']) == 1
    row.post.available = False
    row.post.save()
    assert client.get(f'/api/clinic/spins/{row.pk}/').status_code == 200


def test_register_three_types_privacy_counts_pagination_and_replies():
    acc = account()
    withdrawn = diagnosis(acc, 1)
    hidden = diagnosis(acc, 2, hidden_at=timezone.now(), hidden_reason='Prywatne dane: adres i nazwisko')
    current = diagnosis(acc, 3)
    pending = diagnosis(acc, 4, status='pending_review')
    reply(current)
    reply(current, published_at=timezone.now() + timedelta(days=1))
    reply(pending)
    clinic.withdraw(withdrawn, staff(), 'Błędne źródło')
    client = APIClient()
    response = client.get('/api/clinic/corrections/')
    assert response.status_code == 200
    data = response.data
    assert data['counts'] == {'published': 3, 'withdrawn': 1, 'hidden': 1, 'replies': 1}
    assert {row['type'] for row in data['results']} == {'withdrawal', 'hiding', 'author_reply'}
    assert data['results'][0]['reason'] == 'Błędne źródło'
    event = next(row for row in data['results'] if row['type'] == 'hiding')
    assert event['author'] is None and event['diagnosis_url'] is None and event['post_date'] is None
    assert event['notice'] == 'Ukryto po zgłoszeniu prawnym'
    assert 'Prywatne dane' not in str(data)
    assert client.get(f'/api/clinic/spins/{hidden.pk}/').status_code == 404
    assert len(client.get(f'/api/clinic/spins/{current.pk}/').data['author_replies']) == 1
    assert client.get(f'/api/clinic/spins/{pending.pk}/').status_code == 404
    for _ in range(22):
        reply(current)
    first = client.get('/api/clinic/corrections/').data
    second = client.get('/api/clinic/corrections/?page=2').data
    assert first['count'] == 25 and len(first['results']) == 20 and first['next_page'] == 2
    assert len(second['results']) == 5 and second['next_page'] is None
    assert not ({r['id'] for r in first['results']} & {r['id'] for r in second['results']})
    for value in ('no', '0', '-1'):
        assert client.get('/api/clinic/corrections/', {'page': value}).status_code == 400


def test_register_redacts_previous_events_when_diagnosis_is_hidden():
    row = diagnosis()
    reply(row)
    clinic.withdraw(row, staff(), 'Powód, którego nie należy ujawniać po ukryciu prawnym')
    row.hidden_at = timezone.now()
    row.save(update_fields=['hidden_at'])
    data = corrections_data()
    assert len(data['results']) == 3
    assert all(event['author'] is None and event['reason'] == '' and event['reply_excerpt'] == '' for event in data['results'])


def test_register_query_count_does_not_grow_with_event_count():
    row = diagnosis()
    reply(row)
    corrections_data()  # rozgrzanie ContentType
    with CaptureQueriesContext(connection) as single:
        corrections_data()
    for i in range(19):
        reply(diagnosis(row.post.account, i + 2))
    with CaptureQueriesContext(connection) as many:
        data = corrections_data()
    assert len(data['results']) == 20
    assert len(many) == len(single) and len(many) <= 9


def test_reply_length_and_admin_immutable_ai(admin_client):
    row = diagnosis()
    answer = reply(row)
    answer.body = 'x' * 1501
    with pytest.raises(ValidationError):
        answer.full_clean()
    url = '/admin/news/spindiagnosis/'
    selected = {'action': 'withdraw_diagnoses', '_selected_action': [row.pk]}
    form = admin_client.post(url, selected)
    assert form.status_code == 200 and 'reason' in form.context['form'].fields
    invalid = admin_client.post(url, {**selected, 'confirm_withdrawal': '1', 'reason': ' '})
    assert invalid.context['form'].errors
    result = admin_client.post(url, {**selected, 'confirm_withdrawal': '1', 'reason': 'Błędne źródło', 'verdict': 'no_spin'})
    assert result.status_code == 302
    row.refresh_from_db()
    assert row.status == 'withdrawn' and row.verdict == 'spin'
    assert row.withdrawn_by.is_superuser
    from news.clinic_admin import SpinDiagnosisAdmin
    for field in ('verdict', 'intensity', 'analysis', 'lab', 'x_thread', 'withdrawn_reason'):
        assert field in SpinDiagnosisAdmin.readonly_fields


def test_social_candidates_and_saved_report_exclude_withdrawal(monkeypatch):
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    from news import social_publish, x_publish, weekly_report
    row = diagnosis()
    report = WeeklyReport.objects.create(week_start=timezone.localdate() - timedelta(days=6),
                                         week_end=timezone.localdate(), data=json.loads(json.dumps(weekly_report.build(), cls=DjangoJSONEncoder)), summary='Stara synteza')
    clinic.withdraw(row, staff(), 'Niepoprawne źródło')
    assert list(x_publish.candidates(10)) == []
    assert list(social_publish.candidates(10, ['facebook'])) == []
    refreshed = weekly_report.report_data(report)
    assert refreshed['summary'] == '' and refreshed['spin_of_week'] is None
    assert refreshed['diagnoses']['opposition'] == 0


def test_legal_hide_after_withdrawal_redacts_detail_and_register():
    row = diagnosis()
    operator = staff()
    clinic.withdraw(row, operator, 'Powód wycofania')
    client = APIClient()
    client.force_authenticate(operator)
    url = f'/api/staff/clinic/diagnoses/{row.pk}/hide/'
    assert client.post(url, {'reason': 'Prywatny powód prawny'}).status_code == 200
    row.refresh_from_db()
    first_hidden = row.hidden_at
    assert client.post(url, {'reason': 'Dalsze dane zgłoszenia'}).status_code == 200
    row.refresh_from_db()
    assert row.hidden_at == first_hidden
    assert APIClient().get(f'/api/clinic/spins/{row.pk}/').status_code == 404
    assert all(event['author'] is None for event in corrections_data()['results'])


def test_saved_video_cannot_be_served_after_withdrawal(monkeypatch, tmp_path):
    from news import social_publish
    row = diagnosis()
    monkeypatch.setenv('SOCIAL_MEDIA_DIR', str(tmp_path))
    name = social_publish.video_name(row.pk)
    (tmp_path / name).write_bytes(b'video-fixture')
    client = APIClient()
    response = client.get(f'/api/social/video/{name}')
    assert response.status_code == 200
    response.close()
    clinic.withdraw(row, staff(), 'Powód wycofania')
    assert client.get(f'/api/social/video/{name}').status_code == 404


def test_withdrawal_during_social_preparation_stops_publication(monkeypatch):
    from news import social_publish, x_publish
    row = diagnosis()
    operator = staff()
    monkeypatch.setattr(social_publish, 'channels', lambda: ['bluesky'])
    def prepare(*args, **kwargs):
        clinic.withdraw(row, operator, 'Nowe dowody')
        return {'bluesky': 'Nie publikuj'}
    monkeypatch.setattr(social_publish, 'texts', prepare)
    monkeypatch.setattr(social_publish, 'post_bluesky', lambda *a: pytest.fail('Wycofana diagnoza nie może trafić do social mediów'))
    assert social_publish.run()['results'] == []
    # X sprawdza bazę także dla każdego kolejnego wpisu wątku.
    row = diagnosis(row.post.account, 2)
    monkeypatch.setattr(x_publish, 'enabled', lambda: True)
    monkeypatch.setattr('news.social_content.prepare', lambda *a, **k: {})
    monkeypatch.setattr('news.x_share.build', lambda *a, **k: ['Pierwszy', 'Drugi'])
    monkeypatch.setattr(x_publish, 'polish', lambda value: value)
    monkeypatch.setattr('news.clinic_card.share_png', lambda *a: b'image')
    monkeypatch.setattr(x_publish, 'upload_image', lambda *a: 'image')
    def first_post(*args, **kwargs):
        clinic.withdraw(row, operator, 'Nowe dowody')
        return 'first'
    monkeypatch.setattr(x_publish, 'post', first_post)
    result = x_publish.run()
    assert result['results'][0]['error'] == 'diagnosis_unavailable'
    row.refresh_from_db()
    assert row.x_posted_ids == ['first'] and row.x_posted_at is None and row.status == 'withdrawn'
