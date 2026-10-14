"""S2 pkt 1 i 9: uzasadnienie decyzji (DSA art. 17), e-mail do autora, GET me/decisions/, odwołanie 6 miesięcy, zawieszenie konta."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from spina3 import legal, moderation
from spina3.comments import create_comment
from spina3.models import Appeal, ModerationDecision, Spina3Profile

from .conftest import author_pin, make_box, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def poczta(settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.SPINA3_PUBLIC_URL = 'https://spina3.pl'
    settings.SPINA3_DECISIONS_PATH = '/konto/decyzje'
    settings.SPINA3_DECISION_FROM_EMAIL = legal.DECISION_FROM_EMAIL_DEFAULT


def setup_pin():
    author, staff = make_user('autor_d'), make_user('zespol_d', staff=True)
    pin = author_pin(author, make_box('Box'), make_box('Dowód'), comment='komentarz autora')
    return author, staff, pin


def test_hide_pin_records_decision_and_sends_email():
    author, staff, pin = setup_pin()
    moderation.hide_pin(pin, staff, 'Komentarz zawiera dane osoby prywatnej.', basis=legal.REGULAMIN_SEKCJA_DANE_OSOBOWE)
    row = ModerationDecision.objects.get()
    assert (row.user, row.target_type, row.restriction, row.pin, row.automated) == (author, 'pin', 'hide', pin, False)
    assert row.facts == 'Komentarz zawiera dane osoby prywatnej.' and row.basis == legal.REGULAMIN_SEKCJA_DANE_OSOBOWE
    assert row.basis_text == legal.BASES[legal.REGULAMIN_SEKCJA_DANE_OSOBOWE] and row.decided_by == staff
    assert row.appeal_deadline.date() == legal.add_months(row.created_at, 6).date()
    assert f'me/decisions/{row.pk}/appeal/' in row.appeal_route and '6 miesięcy' in row.appeal_route
    assert len(mail.outbox) == 1 and row.email_sent_at is not None
    msg = mail.outbox[0]
    assert msg.from_email == 'spina3 <kontakt@iapply.pl>' and msg.to == [author.email]
    assert 'https://spina3.pl/konto/decyzje' in msg.body and 'dane osoby prywatnej' in msg.body
    assert 'Środki zautomatyzowane: nie' in msg.body and 'przeprasza' not in msg.body.lower()
    assert '\ufffd' not in msg.body and 'zespol_d' not in msg.body   # bez nazwiska moderatora


def test_every_restricting_action_records_decision():
    author, staff, pin = setup_pin()
    comment, _ = create_comment(make_user('komentator_d'), pin.box, 'Komentarz do ukrycia.')
    own_box = make_box('Box użytkownika', added_by='user', added_by_user=author)
    withdrawn = make_box('Box do wycofania', added_by='user', added_by_user=author)
    moderation.hide_pin(pin, staff, 'Powód 1', sanction='weight_zero_30d')
    moderation.decide_report(moderation.report(author, comment=comment, reason='threat', name='A', email='a@example.org', good_faith=True),
                             staff, 'hide', 'Groźba w komentarzu.')
    moderation.hide_box(own_box, staff, 'Powód 3')
    moderation.withdraw_box(withdrawn, staff, 'Żądanie RODO')
    rows = list(ModerationDecision.objects.order_by('pk'))
    assert [(r.target_type, r.restriction) for r in rows] == [('pin', 'hide'), ('account', 'demote'), ('comment', 'hide'),
                                                              ('box', 'hide'), ('box', 'remove')]
    assert rows[1].until is not None and rows[2].basis == legal.REGULAMIN_SEKCJA_GROZBY and rows[2].report is not None
    assert rows[4].basis == legal.PRZEPIS_RODO_ART_17
    assert len(mail.outbox) == 5


def test_my_decisions_only_own_and_appeal_once(api):
    author, staff, pin = setup_pin()
    other = make_user('inny_d')
    moderation.hide_pin(pin, staff, 'Treść niezgodna z zasadami.')
    row = ModerationDecision.objects.get()
    api.force_authenticate(other)
    assert api.get('/api/spina3/me/decisions/').json() == {'items': []}
    assert api.post(f'/api/spina3/me/decisions/{row.pk}/appeal/', {'text': 'x'}, format='json').status_code == 404
    api.force_authenticate(author)
    items = api.get('/api/spina3/me/decisions/').json()['items']
    assert len(items) == 1 and items[0]['id'] == row.pk and items[0]['can_appeal'] and items[0]['decided_by'] == 'zespół spina3'
    assert items[0]['facts'] == 'Treść niezgodna z zasadami.' and items[0]['restriction_label'] == 'ukrycie'
    r = api.post(f'/api/spina3/me/decisions/{row.pk}/appeal/', {'text': 'To była cytowana wypowiedź publiczna.'}, format='json')
    assert r.status_code == 201 and r.json()['status'] == 'open'
    assert api.post(f'/api/spina3/me/decisions/{row.pk}/appeal/', {'text': 'Jeszcze raz.'}, format='json').status_code == 409
    assert api.post(f'/api/spina3/pin/{pin.pk}/appeal/', {'text': 'Inną drogą.'}, format='json').status_code == 409
    assert api.get('/api/spina3/me/decisions/').json()['items'][0]['appeal']['status'] == 'open'
    appeal = Appeal.objects.get()
    api.force_authenticate(staff)
    queue = api.get('/api/spina3/moderation/queue/').json()
    assert queue['appeals'][0]['decision_id'] == row.pk
    assert api.post(f'/api/spina3/moderation/appeals/{appeal.pk}/', {'decision': 'accept', 'reason': 'Cytat publiczny.'},
                    format='json').status_code == 200
    pin.refresh_from_db()
    row.refresh_from_db()
    assert pin.status == 'published' and row.revoked_at is not None


def test_appeal_window_six_months():
    author, staff, pin = setup_pin()
    moderation.hide_pin(pin, staff, 'Powód')
    row = ModerationDecision.objects.get()
    late = row.created_at + timedelta(days=190)
    with pytest.raises(moderation.ModerationError) as exc:
        moderation.appeal_decision(author, row, 'Za późno', now=late)
    assert exc.value.status == 409
    assert moderation.appeal_decision(author, row, 'W terminie', now=row.created_at + timedelta(days=150)).pk


def test_legacy_pin_appeal_links_decision_and_allows_six_months():
    author, staff, pin = setup_pin()
    moderation.hide_pin(pin, staff, 'Powód')
    appeal = moderation.appeal(author, pin=pin, text='Odwołanie', now=timezone.now() + timedelta(days=30))
    assert appeal.decision == ModerationDecision.objects.get()


def test_suspension_always_through_decision_and_appeal_lifts_it(api):
    author, staff, pin = setup_pin()
    with pytest.raises(moderation.ModerationError):
        moderation.suspend_account(author, staff, '')
    row = moderation.suspend_account(author, staff, 'Powtarzające się naruszenia zasad.', basis=legal.REGULAMIN_SEKCJA_KONTO)
    profile = Spina3Profile.objects.get(user=author)
    assert row.target_type == 'account' and row.restriction == 'suspend' and profile.suspended_until == row.until
    api.force_authenticate(author)
    assert api.put(f'/api/spina3/pin/{pin.pk}/rating/', {'stance': 'agree'}, format='json').status_code == 403
    appeal = moderation.appeal_decision(author, row, 'Proszę o ponowne rozpatrzenie.')
    moderation.decide_appeal(appeal, staff, 'accept', 'Uchylone.')
    profile.refresh_from_db()
    assert profile.suspended_until is None


def test_system_content_has_no_decision():
    staff = make_user('zespol_s', staff=True)
    box = make_box('Box importera')
    moderation.hide_box(box, staff, 'Powód')
    assert not ModerationDecision.objects.exists() and not mail.outbox


def test_mail_failure_keeps_decision(monkeypatch):
    author, staff, pin = setup_pin()

    def broken(*args, **kwargs):
        raise OSError('smtp')
    monkeypatch.setattr('spina3.legal.send_mail', broken)
    moderation.hide_pin(pin, staff, 'Powód')
    row = ModerationDecision.objects.get()
    assert row.email_sent_at is None
