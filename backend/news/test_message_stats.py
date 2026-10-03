from copy import deepcopy
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from news import clinic, clinic_ai
from news.clinic_models import ClinicDailyMessage
from news.message_stats import calculate_stats, concrete, is_noise, post_rows
from news.message_structure import clean_structure
from news.test_clinic import account, post, POST_TEXT


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Test przekazu nie może korzystać z sieci')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)


@pytest.mark.parametrize('text', ['W punkt!', 'Dziękuję', '👏❤️👍', 'Brawo! ' * 15, 'Krótka reakcja',
                                 'Bardzo dziękujemy wszystkim za dobre słowa!'])
def test_message_noise(text):
    assert is_noise(text)


@pytest.mark.parametrize('text', ['50 osób', '3.10.2026', 'Kwota: 2,5 mln zł', 'Wzrost o 10%',
                                 'https://example.org/dane', 'www.example.org', 'Rok 2026'])
def test_message_concrete_short_posts_are_not_noise(text):
    assert concrete(text) and not is_noise(text)


def material():
    return [
        {'id': '11', 'author': 'Anna Nowak', 'text': 'Na nowe szkoły przeznaczono 20 mln zł z budżetu.'},
        {'id': '12', 'author': 'Jan Kowalski', 'text': 'Opublikowaliśmy plan: https://example.org/plan'},
        {'id': '13', 'author': 'Anna Nowak', 'text': 'Apelujemy o udział w konsultacjach dotyczących lokalnych szkół.'},
        {'id': '14', 'author': 'Maria Lis', 'text': 'Krytykujemy sposób prowadzenia rozmów o bezpieczeństwie granic.'},
    ]


def structured():
    return {'camp': 'government', 'thesis': 'Rządzący podkreślają nakłady na szkoły i konsultacje z mieszkańcami.',
            'points': [
                {'title': 'Finansowanie szkół', 'summary': 'Autorzy opisują środki na szkoły i plan inwestycji.',
                 'post_ids': ['11', '12', '13'], 'authors': ['Nowak', 'Kowalski']},
                {'title': 'Bezpieczeństwo granic', 'summary': 'Autorka krytykuje sposób prowadzenia rozmów.',
                 'post_ids': ['14'], 'authors': ['Lis']}],
            'tone': [{'post_id': pk, 'label': label} for pk, label in
                     [('11', 'osiagniecie'), ('12', 'osiagniecie'), ('13', 'apel'), ('14', 'atak')]],
            'message': 'Rządzący mówią o szkołach i bezpieczeństwie.', 'analysis': 'Szersza analiza.', 'themes': ['szkoły']}


def test_message_stats_same_measure_distinct_authors_and_all_tones():
    rows = material() + [{'id': '15', 'author': 'Inny Autor', 'text': 'W punkt!'}]
    data = structured()
    stats = calculate_stats(rows, data['points'], data['tone'])
    assert stats == {'version': 1, 'posts': 4, 'authors': 3, 'noise': 1, 'concrete_count': 2,
                     'concrete_pct': 50, 'coherence_authors': 2, 'coherence_pct': 67,
                     'tone': {'atak': 25, 'osiagniecie': 50, 'apel': 25, 'inne': 0}, 'tone_classified': 4}
    data['tone'][0]['label'] = 'inne'
    assert calculate_stats(rows, data['points'], data['tone'])['tone']['inne'] == 25
    assert calculate_stats(rows)['tone'] is None
    assert calculate_stats(rows)['coherence_authors'] is None
    assert calculate_stats([])['concrete_pct'] == 0
    assert calculate_stats(rows, data['points'], data['tone'][:1])['tone'] is None


def test_message_structure_valid_and_legacy_fallback():
    result = clean_structure(structured(), material(), 'government')
    assert result['points'][0]['authors'] == ['Anna Nowak', 'Jan Kowalski']
    assert clean_structure({'message': 'Stary tekst'}, material(), 'government') == {'thesis': '', 'points': [], 'tone': []}


@pytest.mark.parametrize('mutation', [
    lambda d: d.update(camp='opposition'),
    lambda d: d.update(thesis='Politycy PiS podkreślają nakłady na szkoły.'),
    lambda d: d.update(thesis='Rządzący PiS podkreślają nakłady na szkoły.'),
    lambda d: d.update(thesis='Opozycja podkreśla nakłady na szkoły.'),
    lambda d: d.update(thesis='Rządzący mówią — nakłady na szkoły rosną.'),
    lambda d: d.update(thesis='Rządzący mówią ' + 'a' * 160),
    lambda d: d.update(thesis='Rządzący mówią o szkołach. Drugi temat to podatki.'),
    lambda d: d['points'][0].update(post_ids=['999']),
    lambda d: d['points'][0].update(authors=['Zmyślony']),
    lambda d: d['points'][0].update(authors=['Lis']),
    lambda d: d['points'][0].update(title='a' * 71),
    lambda d: d['points'][0].update(summary='Pierwsze zdanie. Drugie zdanie.'),
    lambda d: d.update(points=d['points'][:1]),
    lambda d: d['tone'].pop(),
    lambda d: d['tone'].append(d['tone'][0]),
    lambda d: d['tone'][0].update(label='pochwała'),
    lambda d: d['tone'][0].update(post_id='999'),
])
def test_message_structure_rejects_inventions_and_wrong_camp(mutation):
    data = deepcopy(structured())
    mutation(data)
    with pytest.raises(clinic_ai.ClinicAIError, match='invalid_message_structure'):
        clean_structure(data, material(), 'government')


def test_message_input_uses_source_ids_excludes_noise_and_limits(monkeypatch):
    rows = material() + [{'id': '999', 'author': 'Reakcja', 'text': 'Dziękuję'}]
    seen = []
    def fake(system, prompt, schema, **kwargs):
        seen.append(prompt)
        assert kwargs['max_tokens'] == 2500
        return structured(), 'mock'
    monkeypatch.setattr(clinic_ai, '_free_chat', fake)
    result = clinic_ai.daily_message('obóz rządzący', '2026-10-03', rows)
    assert result['thesis'] == structured()['thesis']
    assert '[11]' in seen[0] and '[999]' not in seen[0] and 'Dziękuję' not in seen[0]
    assert len(seen[0]) <= clinic_ai.DAILY_INPUT_CHARS


def test_message_noise_only_never_calls_model(monkeypatch):
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *a, **kw: pytest.fail('Brak materiału - nie wywołuj AI'))
    with pytest.raises(clinic_ai.ClinicAIError, match='empty_message_material'):
        clinic_ai.daily_message('opozycja', '2026-10-03', [{'author': 'A', 'text': 'Dziękuję'}])


def test_message_sampling_and_validation_use_only_the_actual_input():
    rows = [{'id': str(i), 'author': f'Autor {i}', 'text': 'Opis tematu dnia i stanowiska w sprawie ustawy. ' * 20}
            for i in range(100)]
    prompt, included = clinic_ai._daily_material('opozycja', '2026-10-03', rows)
    assert len(prompt) <= clinic_ai.DAILY_INPUT_CHARS and len(included) < len(rows)
    data = structured()
    data['points'][0]['post_ids'] = ['99']
    with pytest.raises(clinic_ai.ClinicAIError):
        clean_structure(data, included, 'government')


def test_message_opposition_uses_the_same_stats_and_validates_camp():
    data = structured()
    data.update(camp='opposition', thesis='Opozycja podkreśla nakłady na szkoły i konsultacje.')
    result = clean_structure(data, material(), 'opposition')
    assert calculate_stats(material(), result['points'], result['tone']) == calculate_stats(material(), structured()['points'], structured()['tone'])
    with pytest.raises(clinic_ai.ClinicAIError):
        clean_structure(data, material(), 'government')


def test_message_distinct_people_not_account_labels():
    rows = material()[:2]
    for row in rows:
        row['author_id'] = 'same-person'
    assert calculate_stats(rows)['authors'] == 1


@pytest.mark.django_db
def test_message_pipeline_stats_sources_and_backfill(monkeypatch):
    monkeypatch.setattr(clinic, 'send_review_alert', lambda: 'disabled')
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'true')
    records = [post(account('government', f'metric{i}', str(610 + i)), str(810 + i), text=POST_TEXT)
               for i in range(3)]
    noise = post(records[0].account, '820', text='W punkt!')
    # Dwie nowsze reakcje tego samego autora nie wypierają jego wpisu merytorycznego.
    post(records[0].account, '821', text='Dziękuję')
    def fake(label, day, rows, **kwargs):
        assert len(rows) == 3 and all(not is_noise(row['text']) for row in rows)
        return {'message': 'Rządzący mówią o podatkach.', 'themes': [], 'usage': {},
                'thesis': 'Rządzący podkreślają zmiany w podatkach.',
                'points': [{'title': 'Podatki', 'summary': 'Opisują podatki.',
                            'post_ids': [rows[0]['id']], 'authors': [rows[0]['author']]}],
                'tone': [{'post_id': row['id'], 'label': 'inne'} for row in rows]}
    monkeypatch.setattr(clinic_ai, 'daily_message', fake)
    day = timezone.localdate()
    clinic.run_daily_messages(day)
    message = ClinicDailyMessage.objects.get(day=day, camp='government')
    assert message.stats['posts'] == 3 and message.stats['noise'] == 2
    assert message.stats['authors'] == 3 and message.stats['concrete_pct'] == 100
    assert message.posts.filter(pk=noise.pk).exists()
    original = message.stats
    message.stats = {}
    message.save(update_fields=['stats'])
    older = ClinicDailyMessage.objects.create(day=date(2020, 1, 1), camp='government', message='Starszy tekst')
    monkeypatch.setattr(clinic_ai, 'daily_message', lambda *a, **kw: pytest.fail('Backfill wywołał AI'))
    output = StringIO()
    call_command('clinic_message_stats', since=day.isoformat(), stdout=output)
    message.refresh_from_db()
    older.refresh_from_db()
    assert message.stats == original and older.stats == {}
    assert 'Przeliczono przekazy: 1' in output.getvalue()
    assert clinic.daily_message_data('government')['stats'] == original
    assert clinic.message_history()['government'][0]['thesis'] == message.thesis
    call_command('clinic_message_stats', since=day.isoformat(), stdout=output)
    message.refresh_from_db()
    assert message.stats == original


@pytest.mark.django_db
def test_message_backfill_legacy_does_not_invent_ai_assignments():
    p = post(account(), text=POST_TEXT)
    message = ClinicDailyMessage.objects.create(day=date(2026, 9, 20), camp='government', message='Stary tekst')
    message.posts.add(p)
    call_command('clinic_message_stats', since='2026-09-20', stdout=StringIO())
    message.refresh_from_db()
    assert message.stats['posts'] == 1 and message.stats['tone'] is None
    assert message.stats['coherence_authors'] is None and not message.thesis
    with pytest.raises(CommandError):
        call_command('clinic_message_stats', since='zła-data')
