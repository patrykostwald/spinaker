"""Importer Dr. Spina: wpisy, diagnoza jako BOX + BOX z historią wersji, wpis usunięty u źródła, dokumenty, cisza wyborcza."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from news.clinic_models import SpinDiagnosis
from news.political_models import PoliticalAccount, PoliticalPost
from spina3 import importer
from spina3.models import Box, BoxLink, BoxSpinka, HeldPublication, Pin

from .conftest import make_box, make_user, rate

pytestmark = pytest.mark.django_db


def account(handle='posel_test', user_id='101', confirmed=True):
    acc = PoliticalAccount.objects.create(user_id=user_id, handle=handle, display_name='Poseł Test', camp='opposition', enabled=True,
                                          confirmation_url='https://example.org/potwierdzenie')
    if confirmed:
        acc.confirmed_at = timezone.now()
        acc.save(update_fields=['confirmed_at'])
    return acc


def post(acc, post_id='9001', text='Tylko my obronimy Polaków przed kryzysem. Reszta milczy.', hours_ago=1):
    return PoliticalPost.objects.create(account=acc, post_id=post_id, url=f'https://x.com/{acc.handle}/status/{post_id}', text=text,
                                        published_at=timezone.now() - timedelta(hours=hours_ago), camp_at_collection=acc.camp)


def diagnosis(p, status='approved', headline='Liczba bez punktu odniesienia', staff=None):
    d = SpinDiagnosis.objects.create(post=p, status=status, verdict='spin', intensity=70, headline=headline, summary='Krótko o spinie.',
                                     techniques=[{'name': 'fałszywa alternatywa', 'quote': 'Tylko my', 'explanation': '…'}],
                                     reviewed_by=staff, reviewed_at=timezone.now() if status == 'approved' else None)
    return d


def test_import_posts_only_confirmed_accounts():
    acc, unconfirmed = account(), account('inny', '102', confirmed=False)
    post(acc), post(unconfirmed, '9002')
    assert importer.import_posts() == {'posts_created': 1}
    box = Box.objects.get(kind='post')
    assert box.added_by == 'dr_spin' and box.author_handle == 'posel_test' and box.show_quote and not box.show_avatar
    assert box.text.startswith('Tylko my') and box.source_domain == 'x.com'
    assert importer.import_posts() == {'posts_created': 0}   # idempotentne


def test_diagnosis_becomes_box_plus_box_with_system_pin():
    staff = make_user('staff', staff=True)
    acc = account()
    p = post(acc)
    d = diagnosis(p, staff=staff)
    box, system_pin = importer.sync_diagnosis(d)
    post_box = Box.objects.get(post=p)
    assert box.kind == 'diagnosis' and box.url == 'https://spin.clinic/klinika/%d' % d.pk and box.status == 'published'
    link = BoxLink.objects.get(box=post_box, kind='diagnosis_of')
    assert link.target_id == box.pk and link.is_current and link.version == 1
    assert system_pin.kind == 'diagnosis' and system_pin.stance is None and system_pin.pinned_box_id == box.pk
    assert system_pin.technique == 'fałszywa alternatywa' and system_pin.approved_by_id == staff.pk and system_pin.approved_at
    assert post_box.portals['spin_diagnosis_url'] == box.url
    sp = BoxSpinka.objects.get(box=post_box)
    assert sp.n == 0 and sp.level == 'open'                  # diagnoza = jedyne przypięcie wpisu, bez ocen: Otwarta
    # użytkownicy OCENIAJĄ diagnozę (przypięcie systemowe), nie przypinają do wpisu
    rate(make_user('u'), system_pin, -1)
    sp.refresh_from_db()
    assert sp.n == 1 and sp.distribution == {'agree': 0, 'disagree': 1}


def test_politician_post_reserved_for_diagnosis_pin():
    from spina3.pins import PinError, create_box_with_pin
    post_box = importer.import_post(post(account()))
    with pytest.raises(PinError) as exc:
        create_box_with_pin(make_user('ad'), box_kind='box', box_target=post_box.pk, pin_kind='box', pin_target=make_box('Rzecz').pk)
    assert exc.value.code == 'reserved_for_diagnosis'


def test_pending_diagnosis_not_published_and_withdrawn_hides():
    acc = account()
    p = post(acc)
    d = diagnosis(p, status='pending_review')
    box, system_pin = importer.sync_diagnosis(d)
    assert box is None and system_pin is None and not Pin.objects.filter(kind='diagnosis').exists()
    d.status, d.reviewed_at, d.reviewed_by = 'approved', timezone.now(), make_user('s2', staff=True)
    d.save()
    box, system_pin = importer.sync_diagnosis(d)
    assert box.status == 'published' and system_pin.status == 'published'
    d.withdrawn_at = timezone.now()
    d.save(update_fields=['withdrawn_at'])
    box, system_pin = importer.sync_diagnosis(d)
    assert box.status == 'hidden' and system_pin.status == 'hidden'


def test_diagnosis_versions_history():
    staff = make_user('staff3', staff=True)
    acc = account()
    p = post(acc)
    d = diagnosis(p, staff=staff)
    first, _ = importer.sync_diagnosis(d)
    # nowa wersja diagnozy tego samego wpisu (inny rekord: symulujemy przez nowy box pod innym adresem)
    d.pk = None
    d.post = post(acc, '9009')
    d.save()
    post_box = Box.objects.get(post=p)
    second = make_box('Diagnoza v2', kind='diagnosis', url='https://spin.clinic/klinika/999')
    current = BoxLink.objects.get(box=post_box, kind='diagnosis_of', is_current=True)
    current.is_current, current.superseded_at = False, timezone.now()
    current.save()
    BoxLink.objects.create(box=post_box, target=second, kind='diagnosis_of', version=2)
    links = list(BoxLink.objects.filter(box=post_box, kind='diagnosis_of').order_by('version'))
    assert [l.version for l in links] == [1, 2] and links[0].superseded_at and links[1].is_current
    assert BoxLink.objects.filter(box=post_box, kind='diagnosis_of', is_current=True).count() == 1


def test_removed_post_freezes_and_clears_text():
    acc = account()
    p = post(acc)
    box = importer.import_post(p)
    _, system_pin = importer.sync_diagnosis(diagnosis(p, staff=make_user('rm', staff=True)))
    for u in (make_user('rm1'), make_user('rm2'), make_user('rm3')):
        rate(u, system_pin, 1)
    assert BoxSpinka.objects.get(box=box).level == 'P4'
    p.available, p.text = False, ''
    p.save(update_fields=['available', 'text'])
    assert importer.sync_removed_posts() == 1
    box.refresh_from_db()
    sp = BoxSpinka.objects.get(box=box)
    assert box.source_status == 'removed_at_source' and box.text == '' and box.title.startswith('Wpis z')
    assert sp.frozen and sp.level == 'P4' and Pin.objects.filter(box=box, status='published').count() == 1 and sp.n == 3


def test_import_documents_only_official_with_full_text():
    from news.models import Article, ArticleContent, Source
    official = Source.objects.create(name='Sejm', url='https://sejm.gov.pl', source_type='institution')
    press = Source.objects.create(name='Gazeta Przykładowa', url='https://gazeta.example.org')
    a1 = Article.objects.create(source=official, title='Druk nr 123', url='https://sejm.gov.pl/druk/123', category='parliamentary_print',
                                description='Opis druku', published_date=timezone.now())
    ArticleContent.objects.create(article=a1, text='Pełna treść druku', status='full', response_sha256='x', source_url=a1.url)
    Article.objects.create(source=press, title='Artykuł prasowy', url='https://gazeta.example.org/1', category='article', published_date=timezone.now())
    Article.objects.create(source=press, title='Dokument z prasy', url='https://gazeta.example.org/doc', category='document', published_date=timezone.now())
    assert importer.import_documents() == {'documents_created': 1}
    box = Box.objects.get(article=a1)
    assert box.kind == 'document' and box.subtype == 'druk sejmowy' and box.text == 'Pełna treść druku' and box.show_quote
    assert importer.import_press() == {'press_created': 0}   # import_press=false


def test_election_silence_holds_system_publications(spina3_settings):
    now = timezone.now()
    spina3_settings.SPINA3['flags'].update({'election_silence_start': (now - timedelta(hours=1)).isoformat(),
                                            'election_silence_end': (now + timedelta(hours=2)).isoformat()})
    staff = make_user('staff4', staff=True)
    acc = account()
    p = post(acc)
    d = diagnosis(p, staff=staff)
    box, system_pin = importer.sync_diagnosis(d)
    assert box.status == 'held' and system_pin.status == 'held' and HeldPublication.objects.count() == 2
    from spina3.pins import release_held
    assert release_held(now) == 0
    assert release_held(now + timedelta(hours=3)) == 2
    box.refresh_from_db(); system_pin.refresh_from_db()
    assert box.status == 'published' and system_pin.status == 'published'


def test_run_all_without_network(spina3_settings):
    acc = account()
    post(acc)
    out = importer.run_all()
    assert out['posts_created'] == 1 and 'clusters' in out
